"""Projection of the frozen v2 identity result into V3 comparison contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ..fingerprint import stable_id
from ..ir import AcceptanceState, Entity, EntityType, Mention, SourceSpan
from ..source import NormalizedSource


@dataclass(frozen=True, slots=True)
class V2IdentityProjection:
    mentions: tuple[Mention, ...]
    entities: tuple[Entity, ...]
    unresolved_mention_ids: tuple[str, ...]
    quarantined_mention_ids: tuple[str, ...]
    v2_output_fingerprint: str


def _source_unit_key(source: NormalizedSource, structural_locator: str | None, start_offset: int) -> str:
    if structural_locator is not None:
        for section in source.sections:
            if section.source_locator == structural_locator or section.stable_key == structural_locator:
                return section.stable_key
    section = source.section_for_offset(start_offset)
    if section is None:
        raise ValueError(f"v2 mention offset is outside known source units: {start_offset}")
    return section.stable_key


def adapt_v2_identity_result(
    *,
    source: NormalizedSource,
    payload: Mapping[str, Any],
) -> V2IdentityProjection:
    """Adapt `CharacterIdentityResult` without repairing or re-resolving v2 output."""

    if str(payload.get("normalizedInputFingerprint", "")) != source.source_fingerprint:
        raise ValueError("v2 identity result is bound to a different normalized input fingerprint")

    raw_mentions = payload.get("mentions")
    raw_characters = payload.get("characters")
    if not isinstance(raw_mentions, Sequence) or isinstance(raw_mentions, (str, bytes, bytearray)):
        raise ValueError("v2 mentions must be a sequence")
    if not isinstance(raw_characters, Sequence) or isinstance(raw_characters, (str, bytes, bytearray)):
        raise ValueError("v2 characters must be a sequence")

    mentions: list[Mention] = []
    mention_id_by_evidence_id: dict[str, str] = {}
    mention_ids_by_character: dict[str, list[str]] = {}
    unresolved: list[str] = []
    quarantined: list[str] = []

    for raw in raw_mentions:
        if not isinstance(raw, Mapping):
            raise ValueError("each v2 mention must be an object")
        start = int(raw["startOffset"])
        end = int(raw["endOffset"])
        text = str(raw["surfaceText"])
        if source.normalized_text[start:end] != text:
            raise ValueError(f"v2 mention text/offset mismatch: {raw.get('evidenceId')}")
        unit_key = _source_unit_key(source, raw.get("structuralLocator"), start)
        state = str(raw["resolutionState"])
        acceptance = {
            "linked": AcceptanceState.ACCEPTED,
            "unresolved": AcceptanceState.UNRESOLVED,
            "quarantined": AcceptanceState.REJECTED,
        }.get(state)
        if acceptance is None:
            raise ValueError(f"unsupported v2 resolutionState: {state}")

        mention = Mention.create(
            source_fingerprint=source.source_fingerprint,
            source_unit_key=unit_key,
            span=SourceSpan(start, end),
            entity_type=EntityType.CHARACTER,
            text=text,
            acceptance=acceptance,
            attributes={
                "v2_evidence_id": str(raw["evidenceId"]),
                "v2_mention_kind": str(raw["mentionKind"]),
                "v2_evidence_tier": str(raw["evidenceTier"]),
                "v2_decision_reason": str(raw["decisionReason"]),
            },
        )
        mentions.append(mention)
        mention_id_by_evidence_id[str(raw["evidenceId"])] = mention.mention_id

        character_key = raw.get("characterKey")
        if state == "linked" and character_key:
            mention_ids_by_character.setdefault(str(character_key), []).append(mention.mention_id)
        elif state == "unresolved":
            unresolved.append(mention.mention_id)
        else:
            quarantined.append(mention.mention_id)

    entities: list[Entity] = []
    for raw in raw_characters:
        if not isinstance(raw, Mapping):
            raise ValueError("each v2 character must be an object")
        character_key = str(raw["characterKey"])
        mention_ids = tuple(mention_ids_by_character.get(character_key, ()))
        if not mention_ids:
            # Preserve v2 output faithfully but do not fabricate source evidence.
            continue
        aliases_raw = raw.get("aliases") or []
        aliases = tuple(
            str(alias["surfaceForm"])
            for alias in aliases_raw
            if isinstance(alias, Mapping) and alias.get("surfaceForm")
        )
        canonical = str(raw["canonicalName"])
        entities.append(
            Entity(
                entity_id=stable_id("v2-character-projection", source.source_fingerprint, character_key, prefix="v2ent"),
                entity_type=EntityType.CHARACTER,
                canonical_name=canonical,
                mention_ids=mention_ids,
                aliases=aliases or (canonical,),
                acceptance=AcceptanceState.ACCEPTED,
            )
        )

    return V2IdentityProjection(
        mentions=tuple(sorted(mentions, key=lambda item: (item.evidence.span.start_offset, item.mention_id))),
        entities=tuple(sorted(entities, key=lambda item: item.entity_id)),
        unresolved_mention_ids=tuple(sorted(unresolved)),
        quarantined_mention_ids=tuple(sorted(quarantined)),
        v2_output_fingerprint=str(payload.get("outputFingerprint", "")),
    )
