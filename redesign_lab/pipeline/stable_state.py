"""Stable state stage for redesign-local scene analyses."""

from __future__ import annotations

from typing import Any, Dict, List

from core.pipeline_contract import (
    build_canon_snapshot,
    build_character_timelines,
    build_entity_registry,
    build_formal_character_profiles,
    build_state_result,
    build_timeline,
    normalize_character_timelines,
)
from core.stable_character_state import StableCharacterStateBuilder
from redesign_lab.pipeline.contracts import validate_contract


class StableStateStage:
    """Build durable character facts from redesign-local scene analyses."""

    def __init__(self) -> None:
        self.builder = StableCharacterStateBuilder()

    def build(self, scene_analyses: List[Dict[str, Any]], identity_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        entity_registry = build_entity_registry(scene_analyses)
        state_result = build_state_result(scene_analyses)
        timeline = build_timeline(scene_analyses)
        character_timelines = normalize_character_timelines(build_character_timelines(timeline), identity_result)
        character_profiles = build_formal_character_profiles(
            character_timelines,
            entity_registry,
            state_result,
            identity_result,
            scene_analyses,
        )
        canon_snapshot = build_canon_snapshot(
            state_result,
            (
                scene_analyses[-1]["book_index"] if scene_analyses else 1,
                scene_analyses[-1]["chapter_index"] if scene_analyses else 1,
                scene_analyses[-1]["scene_index"] if scene_analyses else 1,
            ),
        )
        built = self.builder.build(
            character_profiles=character_profiles,
            identity_result=identity_result,
            canon_snapshot=canon_snapshot,
            state_result=state_result,
        )
        normalized = []
        for item in built:
            payload = {
                "canonical_name": str(item.get("canonical_name") or item.get("name") or "").strip(),
                "facts": item.get("stable_state") or item.get("facts") or {},
                "source_refs": item.get("source_refs") or [],
            }
            normalized.append(validate_contract("stable_character_state", payload))
        return normalized

