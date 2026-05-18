"""Contracts for relationship profile artifacts."""

from __future__ import annotations

from typing import List, TypedDict


class RelationshipProfile(TypedDict):
    relationship_id: str
    source_character: str
    target_character: str
    relationship_type: str
    baseline_dynamic: str
    trust_level: str
    conflict_level: str
    romantic_signal: str
    shared_history: List[str]
    change_log: List[dict]
