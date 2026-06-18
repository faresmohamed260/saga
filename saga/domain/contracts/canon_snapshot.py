"""Contracts for canon snapshot artifacts."""

from __future__ import annotations

from typing import Dict, List, TypedDict


class CanonSnapshot(TypedDict):
    snapshot_id: str
    anchor_event_id: str
    scene_ref: Dict[str, int]
    character_states: List[Dict]
    relationship_states: List[Dict]
    entity_states: List[Dict]
    active_goals: List[str]
    active_threats: List[str]
    known_information: List[str]
    unresolved_threads: List[str]
