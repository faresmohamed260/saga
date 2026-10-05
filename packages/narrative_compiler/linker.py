"""Conservative model-light identity primitives.

These are foundation/reference implementations, not a production identity
winner. Learned scorers plug into the contracts in `stages.py`.
"""

from __future__ import annotations

from collections import defaultdict
import re
from typing import Sequence

from .fingerprint import artifact_fingerprint, config_fingerprint, stable_id
from .ir import AcceptanceState, Entity, EntityType, Mention, StageRunDescriptor
from .source import NormalizedSource
from .stages import LinkerResult


_WHITESPACE = re.compile(r"\s+")


def normalized_surface(text: str) -> str:
    return _WHITESPACE.sub(" ", text.strip()).casefold()


class ExactSurfaceCharacterLinker:
    """Group only exact normalized character-name surfaces.

    This deliberately refuses pronouns, descriptions and fuzzy aliases. It is a
    deterministic safety/reference floor for V3.0 contract tests.
    """

    stage_name = "character-linker-exact-surface"
    stage_version = "v3.0.0"

    def link(
        self,
        *,
        source: NormalizedSource,
        mentions: Sequence[Mention],
        upstream_fingerprints: Sequence[str] = (),
    ) -> LinkerResult:
        character_mentions = [m for m in mentions if m.entity_type is EntityType.CHARACTER]
        groups: dict[str, list[Mention]] = defaultdict(list)
        unresolved: list[Mention] = []

        for mention in character_mentions:
            surface = normalized_surface(mention.text)
            if not surface or surface in {"he", "she", "they", "him", "her", "them", "i", "you"}:
                unresolved.append(mention)
                continue
            groups[surface].append(mention)

        entities: list[Entity] = []
        for surface in sorted(groups):
            group = sorted(groups[surface], key=lambda item: (item.evidence.span.start_offset, item.mention_id))
            aliases = tuple(dict.fromkeys(item.text for item in group))
            entities.append(
                Entity(
                    entity_id=stable_id(
                        "entity-v3-exact-surface",
                        source.source_fingerprint,
                        surface,
                        prefix="ent",
                    ),
                    entity_type=EntityType.CHARACTER,
                    canonical_name=group[0].text,
                    mention_ids=tuple(item.mention_id for item in group),
                    aliases=aliases,
                    confidence=1.0,
                    acceptance=AcceptanceState.CANDIDATE,
                )
            )

        unresolved_entities = [Entity.unresolved_singleton(item) for item in unresolved]
        all_entities = tuple(entities + unresolved_entities)
        config = {"policy": "exact-normalized-surface", "pronouns": "unresolved"}
        artifact = artifact_fingerprint(
            source_fingerprint=source.source_fingerprint,
            stage_name=self.stage_name,
            stage_version=self.stage_version,
            config=config,
            upstream_fingerprints=upstream_fingerprints,
        )
        return LinkerResult(
            run=StageRunDescriptor(
                stage_name=self.stage_name,
                stage_version=self.stage_version,
                config_fingerprint=config_fingerprint(config),
                artifact_fingerprint=artifact,
            ),
            entities=all_entities,
            unresolved_mention_ids=tuple(item.mention_id for item in unresolved),
        )
