"""Contracts for query results over the core artifact bundle."""

from __future__ import annotations

from typing import Dict, TypedDict


class CanonQueryResult(TypedDict):
    found: bool
    item: Dict
    query_type: str
