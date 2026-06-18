"""Builds the long-term artifact bundle from current pipeline outputs."""

from __future__ import annotations

from typing import Dict, List

from saga.domain.builders.canon_snapshot_builder import CanonSnapshotBuilder
from saga.domain.builders.character_profile_builder import CharacterProfileBuilder
from saga.domain.builders.constraint_registry_builder import ConstraintRegistryBuilder
from saga.domain.builders.entity_profile_builder import EntityProfileBuilder
from saga.domain.builders.event_ledger_builder import EventLedgerBuilder
from saga.domain.builders.knowledge_registry_builder import KnowledgeRegistryBuilder
from saga.domain.builders.relationship_profile_builder import RelationshipProfileBuilder
from saga.domain.builders.arc_registry_builder import ArcRegistryBuilder


class ArtifactBundleBuilder:
    """Central builder for durable narrative artifacts."""

    BUNDLE_VERSION = "0.1.0"

    def __init__(self):
        self.event_ledger_builder = EventLedgerBuilder()
        self.character_profile_builder = CharacterProfileBuilder()
        self.relationship_profile_builder = RelationshipProfileBuilder()
        self.entity_profile_builder = EntityProfileBuilder()
        self.canon_snapshot_builder = CanonSnapshotBuilder()
        self.arc_registry_builder = ArcRegistryBuilder()
        self.knowledge_registry_builder = KnowledgeRegistryBuilder()
        self.constraint_registry_builder = ConstraintRegistryBuilder()

    def build(
        self,
        *,
        resolved_scene_analyses: List[Dict],
        identity_result: Dict,
        timeline: List[Dict],
        state_result: Dict,
        entity_registry: List[Dict],
        causal_graph_result: Dict,
        character_timelines: List[Dict],
    ) -> Dict:
        event_ledger = self.event_ledger_builder.build(
            scene_analyses=resolved_scene_analyses,
            timeline=timeline,
            causal_graph_result=causal_graph_result,
        )
        relationship_profiles = self.relationship_profile_builder.build(scene_analyses=resolved_scene_analyses)
        entity_profiles = self.entity_profile_builder.build(
            entity_registry=entity_registry,
            scene_analyses=resolved_scene_analyses,
            state_result=state_result,
        )
        character_profiles = self.character_profile_builder.build(
            character_timelines=character_timelines,
            entity_registry=entity_registry,
            state_result=state_result,
            identity_result=identity_result,
            scene_analyses=resolved_scene_analyses,
        )
        canon_snapshots = self.canon_snapshot_builder.build(
            event_ledger=event_ledger,
            state_result=state_result,
            relationship_profiles=relationship_profiles,
        )
        arc_registry = self.arc_registry_builder.build(
            character_profiles=character_profiles,
            relationship_profiles=relationship_profiles,
        )
        knowledge_registry = self.knowledge_registry_builder.build(
            event_ledger=event_ledger,
            scene_analyses=resolved_scene_analyses,
            state_result=state_result,
        )
        constraint_registry = self.constraint_registry_builder.build(
            character_profiles=character_profiles,
            entity_profiles=entity_profiles,
            event_ledger=event_ledger,
        )
        return {
            "bundle_version": self.BUNDLE_VERSION,
            "event_ledger": event_ledger,
            "character_profiles": character_profiles,
            "relationship_profiles": relationship_profiles,
            "entity_profiles": entity_profiles,
            "canon_snapshots": canon_snapshots,
            "arc_registry": arc_registry,
            "knowledge_registry": knowledge_registry,
            "constraint_registry": constraint_registry,
            "divergence_workspace": {
                "divergence_event_id": "",
                "divergence_statement": "",
                "locked_canon_before": [],
                "stable_downstream_facts": [],
                "unstable_downstream_facts": [],
                "invalidated_events": [],
                "required_continuity_constraints": [],
                "target_arcs": [],
            },
            "rewrite_outline": {"beats": []},
            "raw_outputs": {
                "resolved_scene_analyses": resolved_scene_analyses,
                "identity_result": identity_result,
                "timeline": timeline,
                "state_result": state_result,
                "entity_registry": entity_registry,
                "causal_graph_result": causal_graph_result,
                "character_timelines": character_timelines,
            },
            "metadata": {
                "scene_count": len(resolved_scene_analyses),
                "timeline_rows": len(timeline),
                "character_count": len(character_profiles),
                "relationship_count": len(relationship_profiles),
                "entity_count": len(entity_profiles),
                "snapshot_count": len(canon_snapshots),
                "arc_count": len(arc_registry.get("items", [])),
                "knowledge_count": len(knowledge_registry.get("items", [])),
                "constraint_count": len(constraint_registry.get("items", [])),
            },
        }
