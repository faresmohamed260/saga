"""Legacy adapter for character-profile construction.

The formal contract now lives in :mod:`saga.domain.builders.character_profile_builder`.
This service remains as a compatibility layer for callers that still import the
older location.
"""

from __future__ import annotations

from typing import Dict, List

from saga.domain.builders.character_profile_builder import CharacterProfileBuilder


class CharacterProfileService:
    """Compatibility wrapper around the core character-profile builder."""

    def __init__(self) -> None:
        self.builder = CharacterProfileBuilder()

    def build(
        self,
        character_timelines: List[Dict],
        entity_registry: List[Dict],
        state_result: Dict,
        identity_result: Dict,
        scene_analyses: List[Dict],
    ) -> List[Dict]:
        return self.builder.build(
            character_timelines=character_timelines,
            entity_registry=entity_registry,
            state_result=state_result,
            identity_result=identity_result,
            scene_analyses=scene_analyses,
        )
