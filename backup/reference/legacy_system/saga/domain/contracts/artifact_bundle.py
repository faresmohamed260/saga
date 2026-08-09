"""Contracts for the main analysis-complete artifact bundle."""

from __future__ import annotations

from typing import Dict, List, NotRequired, TypedDict


class ArcRegistry(TypedDict):
    items: List[Dict]


class KnowledgeRegistry(TypedDict):
    items: List[Dict]


class ConstraintRegistry(TypedDict):
    items: List[Dict]


class DivergenceWorkspace(TypedDict):
    divergence_event_id: str
    divergence_statement: str
    locked_canon_before: List[str]
    stable_downstream_facts: List[str]
    unstable_downstream_facts: List[str]
    invalidated_events: List[str]
    required_continuity_constraints: List[str]
    target_arcs: List[str]


class RewriteOutline(TypedDict):
    beats: List[Dict]


class ArtifactBundle(TypedDict):
    bundle_version: str
    event_ledger: List[Dict]
    character_profiles: List[Dict]
    relationship_profiles: List[Dict]
    entity_profiles: List[Dict]
    canon_snapshots: List[Dict]
    arc_registry: ArcRegistry
    knowledge_registry: KnowledgeRegistry
    constraint_registry: ConstraintRegistry
    divergence_workspace: DivergenceWorkspace
    rewrite_outline: RewriteOutline
    raw_outputs: Dict[str, object]
    metadata: Dict[str, object]
