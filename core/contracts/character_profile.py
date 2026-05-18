"""Contracts for character profile artifacts."""

from __future__ import annotations

from typing import Dict, List, TypedDict


class CharacterProfile(TypedDict):
    character_id: str
    canonical_name: str
    aliases: List[str]
    core_description: str
    traits: List[str]
    personality: List[str]
    speech_style: List[str]
    goals: List[str]
    fears: List[str]
    loyalties: List[str]
    abilities: List[str]
    constraints: List[str]
    important_history: List[Dict]
    relationship_refs: List[Dict]
    state_history: List[Dict]
    state_at_latest: Dict[str, str]
    first_seen: Dict
    event_count: int
    mention_count: int
