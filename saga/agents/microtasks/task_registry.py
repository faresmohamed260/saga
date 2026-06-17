"""Registry for bounded semantic micro-tasks and their preferred local models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class MicroTaskConfig:
    name: str
    model: str
    timeout: int
    enabled: bool = True


class MicroTaskRegistry:
    """Source of truth for micro-task model assignments."""

    def __init__(self, default_local_model: str = "mistral:7b") -> None:
        self.default_local_model = default_local_model
        self._tasks: Dict[str, MicroTaskConfig] = {
            "normalize_candidate_surface_form": MicroTaskConfig(
                name="normalize_candidate_surface_form",
                model=default_local_model,
                timeout=30,
            ),
            "classify_candidate_identity_type": MicroTaskConfig(
                name="classify_candidate_identity_type",
                model=default_local_model,
                timeout=30,
            ),
            "validate_character_candidate": MicroTaskConfig(
                name="validate_character_candidate",
                model=default_local_model,
                timeout=30,
            ),
            "validate_entity_candidate": MicroTaskConfig(
                name="validate_entity_candidate",
                model=default_local_model,
                timeout=30,
            ),
            "score_alias_merge": MicroTaskConfig(
                name="score_alias_merge",
                model=default_local_model,
                timeout=30,
            ),
            "extract_scene_events": MicroTaskConfig(
                name="extract_scene_events",
                model=default_local_model,
                timeout=45,
            ),
            "classify_relationship_change": MicroTaskConfig(
                name="classify_relationship_change",
                model=default_local_model,
                timeout=30,
            ),
            "classify_state_change_importance": MicroTaskConfig(
                name="classify_state_change_importance",
                model=default_local_model,
                timeout=30,
            ),
            "rank_event_significance": MicroTaskConfig(
                name="rank_event_significance",
                model=default_local_model,
                timeout=30,
            ),
        }

    def get(self, name: str) -> MicroTaskConfig:
        if name not in self._tasks:
            raise KeyError(f"Unknown micro-task: {name}")
        return self._tasks[name]
