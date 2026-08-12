"""Deterministic narrative attribution grounding for analysis foundation scenes."""

from __future__ import annotations

import re
from typing import Any

from packages.analysis_foundation.contracts import (
    CanonicalCharacter,
    CanonicalIdentityBundle,
    NarrativeEvidenceSpan,
    SceneArtifact,
    SceneNarrativeGrounding,
)


FIRST_PERSON_TERMS = {"i", "me", "my", "mine", "myself", "we", "us", "our", "ours"}
SECOND_PERSON_TERMS = {"you", "your", "yours", "yourself", "yourselves"}
_HEADING_MARKER_PATTERN = re.compile(r"\b(?:part|book|chapter)\s+[ivxlcdm0-9]+\b", re.IGNORECASE)


def ground_scene_narration(
    *,
    scenes: list[SceneArtifact],
    identity_bundle: CanonicalIdentityBundle,
    chapter_texts: list[str] | None = None,
) -> list[SceneNarrativeGrounding]:
    name_index, names_pattern = _identity_name_index(identity_bundle)
    addressee_name_index, addressee_names_pattern = _identity_display_name_index(identity_bundle)
    source_texts = [*(chapter_texts or []), *[scene.text for scene in scenes]]
    narrator_candidate = infer_global_narrator(
        identity_bundle=identity_bundle,
        texts=source_texts,
        _name_index=name_index,
        _names_pattern=names_pattern,
    )
    results: list[SceneNarrativeGrounding] = []
    for scene in scenes:
        narration_text, dialogue_text = split_narration_and_dialogue(scene.text)
        first_person_count = _pronoun_count(narration_text, FIRST_PERSON_TERMS)
        second_person_count = _pronoun_count(narration_text, SECOND_PERSON_TERMS)
        dialogue_first_person_count = _pronoun_count(dialogue_text, FIRST_PERSON_TERMS)
        dialogue_second_person_count = _pronoun_count(dialogue_text, SECOND_PERSON_TERMS)
        raw_first_person_count = first_person_count + dialogue_first_person_count
        raw_second_person_count = second_person_count + dialogue_second_person_count
        diagnostics: list[str] = []
        evidence_spans: list[NarrativeEvidenceSpan] = []
        narrator_character_id = ""
        narrator_name = ""
        narrator_confidence = 0.0
        if identity_bundle.narrator.perspective == "first_person" and first_person_count:
            if narrator_candidate:
                narrator_character_id = str(narrator_candidate["character_id"])
                narrator_name = str(narrator_candidate["display_name"])
                narrator_confidence = float(narrator_candidate["confidence"])
                evidence_spans.extend(list(narrator_candidate.get("evidence_spans") or [])[:3])
            else:
                diagnostics.append("first_person_narrator_unresolved")
        scene_addressees, addressee_evidence = _scene_addressees(
            scene.text,
            name_index=addressee_name_index,
            names_pattern=addressee_names_pattern,
        )
        evidence_spans.extend(addressee_evidence)
        if raw_second_person_count and not scene_addressees:
            diagnostics.append("second_person_addressee_unresolved")
        results.append(
            SceneNarrativeGrounding(
                scene_id=scene.scene_id,
                perspective=identity_bundle.narrator.perspective,
                narrator_character_id=narrator_character_id,
                narrator_name=narrator_name,
                narrator_confidence=round(narrator_confidence, 4),
                addressee_character_ids=[item["character_id"] for item in scene_addressees],
                addressee_names=[item["display_name"] for item in scene_addressees],
                first_person_count=first_person_count,
                second_person_count=second_person_count,
                dialogue_first_person_count=dialogue_first_person_count,
                dialogue_second_person_count=dialogue_second_person_count,
                raw_first_person_count=raw_first_person_count,
                raw_second_person_count=raw_second_person_count,
                evidence_spans=evidence_spans,
                diagnostics=diagnostics,
            )
        )
    return results


def apply_scene_narrative_grounding(
    *,
    scenes: list[SceneArtifact],
    identity_bundle: CanonicalIdentityBundle,
    chapter_texts: list[str] | None = None,
) -> list[SceneArtifact]:
    grounding_by_scene_id = {
        item.scene_id: item
        for item in ground_scene_narration(scenes=scenes, identity_bundle=identity_bundle, chapter_texts=chapter_texts)
    }
    updated: list[SceneArtifact] = []
    for scene in scenes:
        grounding = grounding_by_scene_id.get(scene.scene_id)
        metadata = dict(scene.metadata or {})
        if grounding is not None:
            metadata["narrative_grounding"] = grounding.model_dump()
        updated.append(scene.model_copy(update={"metadata": metadata}))
    return updated


def infer_global_narrator(
    *,
    identity_bundle: CanonicalIdentityBundle,
    texts: list[str],
    _name_index: dict[str, CanonicalCharacter] | None = None,
    _names_pattern: str = "",
) -> dict[str, Any] | None:
    if identity_bundle.narrator.perspective != "first_person":
        return None
    joined = "\n\n".join(str(text or "") for text in texts if str(text or "").strip())
    if not joined:
        return None
    name_index, names_pattern = (
        (_name_index, _names_pattern)
        if _name_index is not None
        else _identity_name_index(identity_bundle)
    )
    if not name_index or not names_pattern:
        return None
    scores_by_character: dict[str, float] = {}
    evidence_by_character: dict[str, list[NarrativeEvidenceSpan]] = {}
    patterns = [
        (rf"\bthere\s+was\s+a\s+girl\s+named\s+(?P<name>{names_pattern})(?!\w)", 7.0, "self_story_name"),
        (rf"\bonce\s+upon\s+a\s+time[^.\n]{{0,120}}(?P<name>{names_pattern})(?!\w)", 5.0, "self_story_name"),
        (rf"(?<!\w)(?P<name>{names_pattern})\s*,\s+you(?:'re| are| were| have| had)?\b", 4.0, "direct_address_to_narrator"),
        (rf"\bmy\s+name\s+is\s+(?P<name>{names_pattern})(?!\w)", 8.0, "explicit_self_name"),
        (rf"\bi\s+am\s+(?P<name>{names_pattern})(?!\w)", 8.0, "explicit_self_name"),
    ]
    for pattern, weight, kind in patterns:
        for match in re.finditer(pattern, joined, flags=re.IGNORECASE):
            character = name_index.get(_normalized_name(match.group("name")))
            if character is None:
                continue
            window = _window(joined, match.start(), match.end(), radius=360)
            if _pronoun_count(window, FIRST_PERSON_TERMS) <= 0:
                continue
            scores_by_character[character.character_id] = (
                scores_by_character.get(character.character_id, 0.0) + weight
            )
            evidence_by_character.setdefault(character.character_id, []).append(
                NarrativeEvidenceSpan(
                    kind=kind,
                    text=_clean_excerpt(window, max_chars=280),
                    start_char=max(0, match.start() - 360),
                    end_char=min(len(joined), match.end() + 360),
                    character_id=character.character_id,
                    character_name=character.display_name,
                )
            )
    characters = {item.character_id: item for item in identity_bundle.characters}
    scores = [
        (score, characters[character_id], evidence_by_character.get(character_id, []))
        for character_id, score in scores_by_character.items()
        if character_id in characters and score > 0
    ]
    if not scores:
        return None
    scores.sort(key=lambda item: (-item[0], item[1].display_name.casefold()))
    best_score, character, evidence = scores[0]
    runner_up = scores[1][0] if len(scores) > 1 else 0.0
    confidence = best_score / max(best_score + runner_up, 1.0)
    if best_score < 4.0 or confidence < 0.55:
        return None
    return {
        "character_id": character.character_id,
        "display_name": character.display_name,
        "confidence": confidence,
        "score": best_score,
        "evidence_spans": evidence,
    }


def narrative_grounding_summary(scenes: list[SceneArtifact]) -> dict[str, Any]:
    groundings = [
        SceneNarrativeGrounding.model_validate(scene.metadata.get("narrative_grounding"))
        for scene in scenes
        if isinstance(scene.metadata.get("narrative_grounding"), dict)
    ]
    diagnostics = [code for item in groundings for code in item.diagnostics]
    return {
        "grounded_scene_count": len(groundings),
        "first_person_perspective_scene_count": sum(1 for item in groundings if item.perspective == "first_person"),
        "third_person_perspective_scene_count": sum(1 for item in groundings if item.perspective == "third_person"),
        "narration_first_person_evidence_scene_count": sum(1 for item in groundings if item.first_person_count > 0),
        "dialogue_first_person_evidence_scene_count": sum(1 for item in groundings if item.dialogue_first_person_count > 0),
        "resolved_narrator_scene_count": sum(1 for item in groundings if item.narrator_character_id),
        "addressee_scene_count": sum(1 for item in groundings if item.addressee_character_ids),
        "diagnostic_codes": sorted(set(diagnostics)),
    }


def split_narration_and_dialogue(text: str) -> tuple[str, str]:
    """Split prose without treating dialogue pronouns as narrator evidence."""
    narration: list[str] = []
    dialogue: list[str] = []
    in_curly_quote = False
    in_straight_quote = False
    for character in str(text or ""):
        if character == "“":
            in_curly_quote = True
            continue
        if character == "”":
            in_curly_quote = False
            continue
        if character == '"':
            in_straight_quote = not in_straight_quote
            continue
        target = dialogue if in_curly_quote or in_straight_quote else narration
        target.append(character)
    narration_text = _HEADING_MARKER_PATTERN.sub(" ", "".join(narration))
    return narration_text, "".join(dialogue)


def _scene_addressees(
    text: str,
    *,
    name_index: dict[str, CanonicalCharacter],
    names_pattern: str,
) -> tuple[list[dict[str, str]], list[NarrativeEvidenceSpan]]:
    matched: list[dict[str, str]] = []
    evidence: list[NarrativeEvidenceSpan] = []
    if not names_pattern:
        return [], []
    explicit_you_pattern = re.compile(
        rf"\byou\s*,\s*(?P<after>{names_pattern})(?!\w)",
        flags=re.IGNORECASE,
    )
    vocative_pattern = re.compile(
        rf"(?:^|[.!?]\s+)(?:oh\s+|please\s+)?(?P<leading>{names_pattern})\s*,"
        rf"|,\s*(?P<trailing>{names_pattern})(?=\s*[.!?])",
        flags=re.IGNORECASE,
    )
    recipient_pattern = re.compile(
        rf"\b(?:said|spoke|whispered|called|shouted)\s+to\s+(?P<to>{names_pattern})(?!\w)",
        flags=re.IGNORECASE,
    )
    for match in explicit_you_pattern.finditer(text):
        character = _matched_character(match, name_index)
        if character is not None:
            matched.append({"character_id": character.character_id, "display_name": character.display_name})
            evidence.append(_addressee_evidence("explicit_second_person_address", text, match.start(), match.end(), character))
    for quote, quote_start, quote_end in _quoted_spans(text):
        for match in vocative_pattern.finditer(quote):
            character = _matched_character(match, name_index)
            if character is not None:
                matched.append({"character_id": character.character_id, "display_name": character.display_name})
                evidence.append(_addressee_evidence("direct_vocative", text, quote_start + match.start(), quote_start + match.end(), character))
        if _pronoun_count(quote, SECOND_PERSON_TERMS) <= 0:
            continue
        context_start = max(0, quote_start - 140)
        context_end = min(len(text), quote_end + 140)
        context = text[context_start:context_end]
        for match in recipient_pattern.finditer(context):
            character = _matched_character(match, name_index)
            if character is not None:
                matched.append({"character_id": character.character_id, "display_name": character.display_name})
                evidence.append(_addressee_evidence("named_speech_recipient", text, context_start + match.start(), context_start + match.end(), character))
    unique = _unique_character_rows(matched)
    allowed_ids = {item["character_id"] for item in unique}
    return unique, [item for item in evidence if item.character_id in allowed_ids]


def _quoted_spans(text: str) -> list[tuple[str, int, int]]:
    spans: list[tuple[str, int, int]] = []
    start = -1
    closing = ""
    for index, character in enumerate(str(text or "")):
        if start < 0 and character in {'“', '"'}:
            start = index + 1
            closing = '”' if character == '“' else '"'
        elif start >= 0 and character == closing:
            spans.append((text[start:index], start, index))
            start = -1
            closing = ""
    return spans


def _matched_character(match: re.Match[str], name_index: dict[str, CanonicalCharacter]) -> CanonicalCharacter | None:
    raw_name = next((value for value in match.groupdict().values() if value), "")
    return name_index.get(_normalized_name(raw_name))


def _addressee_evidence(
    kind: str,
    text: str,
    start: int,
    end: int,
    character: CanonicalCharacter,
) -> NarrativeEvidenceSpan:
    return NarrativeEvidenceSpan(
        kind=kind,
        text=_clean_excerpt(_window(text, start, end, radius=100), max_chars=260),
        start_char=max(0, start - 100),
        end_char=min(len(text), end + 100),
        character_id=character.character_id,
        character_name=character.display_name,
    )


def _identity_name_index(
    identity_bundle: CanonicalIdentityBundle,
) -> tuple[dict[str, CanonicalCharacter], str]:
    candidates: dict[str, list[tuple[str, CanonicalCharacter]]] = {}
    for character in identity_bundle.characters:
        for raw_name in [character.display_name, *list(character.aliases or [])]:
            name = " ".join(str(raw_name or "").split()).strip()
            normalized = _normalized_name(name)
            if not normalized or len(normalized) < 2:
                continue
            candidates.setdefault(normalized, []).append((name, character))
    unique: dict[str, CanonicalCharacter] = {}
    display_names: dict[str, str] = {}
    for normalized, rows in candidates.items():
        character_ids = {character.character_id for _, character in rows}
        if len(character_ids) != 1:
            continue
        unique[normalized] = rows[0][1]
        display_names[normalized] = max((name for name, _ in rows), key=len)
    pattern = "|".join(
        re.escape(display_names[key])
        for key in sorted(display_names, key=lambda item: (-len(display_names[item]), item))
    )
    return unique, pattern


def _identity_display_name_index(
    identity_bundle: CanonicalIdentityBundle,
) -> tuple[dict[str, CanonicalCharacter], str]:
    candidates: dict[str, list[tuple[str, CanonicalCharacter]]] = {}
    for character in identity_bundle.characters:
        name = " ".join(str(character.display_name or "").split()).strip()
        normalized = _normalized_name(name)
        if normalized and len(normalized) >= 2:
            candidates.setdefault(normalized, []).append((name, character))
    unique = {
        normalized: rows[0][1]
        for normalized, rows in candidates.items()
        if len({character.character_id for _, character in rows}) == 1
    }
    display_names = {normalized: rows[0][0] for normalized, rows in candidates.items() if normalized in unique}
    pattern = "|".join(
        re.escape(display_names[key])
        for key in sorted(display_names, key=lambda item: (-len(display_names[item]), item))
    )
    return unique, pattern


def _normalized_name(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


def _pronoun_count(text: str, terms: set[str]) -> int:
    if not text:
        return 0
    pattern = "|".join(re.escape(term) for term in sorted(terms, key=len, reverse=True))
    return len(re.findall(rf"\b(?:{pattern})\b", text, flags=re.IGNORECASE))


def _window(text: str, start: int, end: int, *, radius: int) -> str:
    return str(text or "")[max(0, start - radius): min(len(text), end + radius)]


def _clean_excerpt(text: str, *, max_chars: int) -> str:
    cleaned = " ".join(str(text or "").split()).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def _unique_character_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    results: list[dict[str, str]] = []
    for row in rows:
        key = str(row.get("character_id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        results.append(row)
    return results
