"""Contracts for canonical event ledger artifacts."""

from __future__ import annotations

from typing import List, TypedDict


class EventLedgerEntry(TypedDict):
    ledger_event_id: str
    time_index: int
    source_event_id: str
    title: str
    summary: str
    book_index: int
    chapter_index: int
    scene_index: int
    participants: List[str]
    location: str
    time_signals: List[str]
    preconditions: List[str]
    direct_consequences: List[str]
    causal_parents: List[str]
    causal_children: List[str]
    stakes: List[str]
    tags: List[str]
