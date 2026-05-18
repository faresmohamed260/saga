"""Contracts for entity and location profile artifacts."""

from __future__ import annotations

from typing import List, TypedDict


class EntityProfile(TypedDict):
    entity_id: str
    name: str
    entity_type: str
    description: str
    rules_or_constraints: List[str]
    connected_characters: List[str]
    status_history: List[dict]
