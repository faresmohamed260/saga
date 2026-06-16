"""Adapter from SAGA outputs to the narrative-generation retrieval schema."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any, Dict, List, Optional

from core.builders.artifact_bundle_builder import ArtifactBundleBuilder
from core.pipeline_contract import (
    build_character_timelines,
    build_entity_registry,
    build_event_ledger,
    build_formal_character_profiles,
    build_state_result,
    build_timeline,
    normalize_character_timelines,
    rebuild_resolved_scene_analyses,
)
from query.target_character_state_service import TargetCharacterStateService
from query.visual_world_state_service import VisualWorldStateService
from rag.story_index_service import StoryIndexService
from services.sqlite_contract_adapter import is_db_book_ref, load_contract_like


class NarrativeContextService:
    """Build decoder-ready narrative context from the current SAGA contract."""

    REQUIRED_CONTEXT_KEYS = {
        "meta",
        "story_ending",
        "character_states",
        "relationship_summary",
        "unresolved_threads",
        "causal_chains",
        "flexible_events",
        "character_trajectories",
        "reference_entities",
        "narrator",
        "alias_index",
        "retrieval_documents",
        "stats",
    }

    REQUIRED_REBUILD_OUTPUT_KEYS = {
        "resolved_scene_analyses",
        "entity_registry",
        "state_result",
        "timeline",
        "identity_result",
        "causal_graph_result",
        "character_timelines",
    }

    def __init__(self) -> None:
        self.bundle_builder = ArtifactBundleBuilder()
        self.target_state_service = TargetCharacterStateService()
        self.visual_world_state_service = VisualWorldStateService()
        self.story_index_service = StoryIndexService()

    def build_from_contract(
        self,
        contract: Dict[str, Any],
        *,
        prefer_exported: bool = True,
        top_characters: int = 10,
        top_threads: int = 8,
        top_flexible_events: int = 5,
        top_character_trajectories: int = 6,
        target_point: Optional[Dict[str, Any]] = None,
        identity_json_path: str | Path | None = None,
        contract_paths: Optional[List[str | Path]] = None,
        include_visual_world_state: bool = False,
    ) -> Dict[str, Any]:
        if prefer_exported and not target_point:
            try:
                exported_context = self.load_exported_context(contract)
            except ValueError:
                exported_context = None
            if exported_context:
                return exported_context
        outputs = self.validate_contract_for_rebuild(contract)
        bundle = self._build_bundle(outputs)
        return self._assemble_context(
            bundle=bundle,
            contract=contract,
            outputs=outputs,
            top_characters=top_characters,
            top_threads=top_threads,
            top_flexible_events=top_flexible_events,
            top_character_trajectories=top_character_trajectories,
            target_point=target_point,
            identity_json_path=identity_json_path,
            contract_paths=contract_paths,
            include_visual_world_state=include_visual_world_state,
        )

    def build_from_contract_file(self, path: str | Path, **kwargs) -> Dict[str, Any]:
        if is_db_book_ref(str(path)):
            contract = load_contract_like(str(path))
        else:
            with Path(path).open("r", encoding="utf-8") as handle:
                contract = json.load(handle)
        contract_paths = kwargs.pop("contract_paths", None)
        if contract_paths is None:
            contract_paths = [path]
        return self.build_from_contract(contract, contract_paths=contract_paths, **kwargs)

    def build_from_contracts(
        self,
        contracts: List[Dict[str, Any]],
        *,
        top_characters: int = 10,
        top_threads: int = 8,
        top_flexible_events: int = 5,
        top_character_trajectories: int = 6,
        target_point: Optional[Dict[str, Any]] = None,
        identity_json_path: str | Path | None = None,
        contract_paths: Optional[List[str | Path]] = None,
        include_visual_world_state: bool = False,
    ) -> Dict[str, Any]:
        if not contracts:
            raise ValueError("At least one contract is required.")
        validated_outputs = [self.validate_contract_for_rebuild(contract) for contract in contracts]
        aggregate_contract = self._aggregate_contracts(contracts, validated_outputs)
        outputs = aggregate_contract["outputs"]
        bundle = self._build_bundle(outputs)
        return self._assemble_context(
            bundle=bundle,
            contract=aggregate_contract,
            outputs=outputs,
            top_characters=top_characters,
            top_threads=top_threads,
            top_flexible_events=top_flexible_events,
            top_character_trajectories=top_character_trajectories,
            target_point=target_point,
            identity_json_path=identity_json_path,
            contract_paths=contract_paths,
            include_visual_world_state=include_visual_world_state,
        )

    def write_context(self, context: Dict[str, Any], path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            json.dump(context, handle, ensure_ascii=False, indent=2, default=str)
        return target

    def load_exported_context(self, contract: Dict[str, Any]) -> Dict[str, Any] | None:
        outputs = (contract.get("outputs") or {})
        artifacts = outputs.get("sequel_artifacts")
        if not artifacts:
            return None
        if not isinstance(artifacts, dict):
            raise ValueError(
                "Contract outputs.sequel_artifacts is malformed. Expected an object containing "
                "`context` and `blueprint`."
            )
        if "context" not in artifacts or not artifacts.get("context"):
            return None
        context = artifacts.get("context")
        if not isinstance(context, dict):
            raise ValueError("Contract outputs.sequel_artifacts.context is malformed. Expected a JSON object.")
        missing = sorted(self.REQUIRED_CONTEXT_KEYS - set(context.keys()))
        if missing:
            raise ValueError(
                "Contract outputs.sequel_artifacts.context is malformed. Missing keys: "
                + ", ".join(missing)
            )
        return context

    def validate_contract_for_rebuild(self, contract: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(contract, dict):
            raise ValueError("Contract must be a JSON object.")
        for key in ("contract_version", "inputs", "outputs"):
            if key not in contract:
                raise ValueError(f"Missing required top-level contract key: {key}")
        outputs = contract.get("outputs") or {}
        if not isinstance(outputs, dict):
            raise ValueError("Contract outputs is malformed. Expected a JSON object.")
        missing = sorted(key for key in self.REQUIRED_REBUILD_OUTPUT_KEYS if key not in outputs)
        if missing:
            raise ValueError(
                "Contract outputs missing required keys for sequel-context rebuild: "
                + ", ".join(missing)
            )
        return outputs

    def _build_bundle(self, outputs: Dict[str, Any]) -> Dict[str, Any]:
        resolved_scenes = outputs.get("resolved_scene_analyses") or outputs.get("scene_analyses") or []
        return self.bundle_builder.build(
            resolved_scene_analyses=resolved_scenes,
            identity_result=outputs.get("identity_result") or {"alias_map": {}, "decisions": []},
            timeline=outputs.get("timeline") or [],
            state_result=outputs.get("state_result") or {"transitions": [], "latest_state": []},
            entity_registry=outputs.get("entity_registry") or [],
            causal_graph_result=outputs.get("causal_graph_result") or {"graph": {"events": []}},
            character_timelines=outputs.get("character_timelines") or [],
        )

    def _aggregate_contracts(
        self,
        contracts: List[Dict[str, Any]],
        outputs_list: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        books: List[Dict[str, Any]] = []
        scene_analyses: List[Dict[str, Any]] = []
        resolved_scene_analyses: List[Dict[str, Any]] = []
        graph_events: List[Dict[str, Any]] = []
        critical_path: List[Dict[str, Any]] = []
        flexible_events: List[Dict[str, Any]] = []
        causal_chains: List[Dict[str, Any]] = []
        divergence_points: List[Dict[str, Any]] = []
        identity_result = (outputs_list[-1].get("identity_result") or {"alias_map": {}, "decisions": []})

        for contract, outputs in zip(contracts, outputs_list):
            books.extend(((contract.get("inputs") or {}).get("books") or []))
            scene_analyses.extend(outputs.get("scene_analyses") or [])
            resolved_scene_analyses.extend(outputs.get("resolved_scene_analyses") or outputs.get("scene_analyses") or [])
            graph = ((outputs.get("causal_graph_result") or {}).get("graph") or {})
            graph_events.extend(graph.get("events") or [])
            critical_path.extend(graph.get("critical_path") or [])
            flexible_events.extend(graph.get("flexible_events") or [])
            causal_chains.extend(graph.get("causal_chains") or [])
            divergence_points.extend(graph.get("divergence_points") or [])

        if not resolved_scene_analyses and scene_analyses:
            resolved_scene_analyses = rebuild_resolved_scene_analyses(scene_analyses, identity_result)
        entity_registry = build_entity_registry(resolved_scene_analyses)
        state_result = build_state_result(resolved_scene_analyses)
        timeline = build_timeline(resolved_scene_analyses)
        character_timelines = build_character_timelines(timeline)
        character_timelines = normalize_character_timelines(character_timelines, identity_result)
        causal_graph_result = {
            "graph": {
                "events": graph_events,
                "critical_path": critical_path,
                "flexible_events": flexible_events,
                "causal_chains": causal_chains,
                "divergence_points": divergence_points,
            }
        }
        event_ledger = build_event_ledger(resolved_scene_analyses, timeline, causal_graph_result)
        character_profiles = build_formal_character_profiles(
            character_timelines,
            entity_registry,
            state_result,
            identity_result,
            resolved_scene_analyses,
        )
        return {
            "contract_version": contracts[-1].get("contract_version", "1.0.0"),
            "inputs": {"books": books},
            "outputs": {
                "scene_analyses": scene_analyses,
                "resolved_scene_analyses": resolved_scene_analyses,
                "entity_registry": entity_registry,
                "state_result": state_result,
                "timeline": timeline,
                "identity_result": identity_result,
                "causal_graph_result": causal_graph_result,
                "character_timelines": character_timelines,
                "character_profiles": character_profiles,
                "event_ledger": event_ledger,
            },
        }

    def _assemble_context(
        self,
        *,
        bundle: Dict[str, Any],
        contract: Dict[str, Any],
        outputs: Dict[str, Any],
        top_characters: int,
        top_threads: int,
        top_flexible_events: int,
        top_character_trajectories: int,
        target_point: Optional[Dict[str, Any]] = None,
        identity_json_path: str | Path | None = None,
        contract_paths: Optional[List[str | Path]] = None,
        include_visual_world_state: bool = False,
    ) -> Dict[str, Any]:
        event_lookup = self._event_lookup(outputs)
        snapshot_payload = None
        visual_world_state_payload = None
        if target_point:
            if not contract_paths:
                raise ValueError("contract_paths are required when building target-aware character states.")
            snapshot_payload = self.target_state_service.build_character_state_snapshot(
                contract_paths=[Path(path) for path in contract_paths],
                target_point=target_point,
                identity_json_path=identity_json_path,
            )
            character_states = self._character_states_from_snapshot(
                snapshot_payload.get("character_states") or [],
                top_characters=top_characters,
            )
            if include_visual_world_state:
                visual_world_state_payload = self.visual_world_state_service.build_visual_world_state(
                    contract_paths=[Path(path) for path in contract_paths],
                    target_point=target_point,
                    identity_json_path=identity_json_path,
                )
        else:
            character_states = self._character_states(bundle, outputs, top_characters)
        relationship_summary = self._relationship_summary(bundle)
        unresolved_threads = self._unresolved_threads(outputs, event_lookup, top_threads)
        causal_chains = self._causal_chains(outputs, event_lookup)
        flexible_events = self._flexible_events(outputs, event_lookup, top_flexible_events)
        trajectories = self._character_trajectories(bundle, top_character_trajectories)
        retrieval_documents = self._retrieval_documents(bundle=bundle, outputs=outputs)

        context = {
            "meta": {
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "retrieval_type": "sequel_setup",
                "book_title": self._book_title(contract),
                "contract_version": contract.get("contract_version", ""),
                "target_point": snapshot_payload.get("target_point") if snapshot_payload else None,
                "book_titles": [book.get("title", "") for book in (((contract.get("inputs") or {}).get("books") or [])) if book.get("title")],
            },
            "story_ending": {
                "last_scene": self._last_scene(outputs),
                "critical_path_tail": self._critical_path_tail(outputs, event_lookup),
            },
            "character_states": character_states,
            "relationship_summary": relationship_summary,
            "unresolved_threads": unresolved_threads,
            "causal_chains": causal_chains,
            "flexible_events": flexible_events,
            "character_trajectories": trajectories,
            "reference_entities": list(((outputs.get("identity_result") or {}).get("reference_entities") or [])),
            "narrator": dict(((outputs.get("identity_result") or {}).get("narrator") or {})),
            "alias_index": self._alias_index(outputs),
            "retrieval_documents": retrieval_documents,
            "stats": {
                "critical_ending_events": len(self._critical_path_tail(outputs, event_lookup)),
                "characters_retrieved": len(character_states),
                "relationship_pairs": len(relationship_summary),
                "unresolved_threads": len(unresolved_threads),
                "causal_chains": len(causal_chains),
                "flexible_events": len(flexible_events),
                "retrieval_documents": len(retrieval_documents),
            },
        }
        if snapshot_payload:
            context["target_character_state_snapshot"] = snapshot_payload
        if visual_world_state_payload:
            context["visual_world_state"] = visual_world_state_payload
            context["character_visual_states"] = visual_world_state_payload.get("character_visual_states") or []
            context["entity_visual_states"] = visual_world_state_payload.get("entity_visual_states") or []
            context["location_visual_states"] = visual_world_state_payload.get("location_visual_states") or []
        return context

    def _character_states_from_snapshot(
        self,
        states: List[Dict[str, Any]],
        *,
        top_characters: int,
    ) -> List[Dict[str, Any]]:
        ordered = sorted(
            states or [],
            key=lambda item: (
                -int(item.get("mention_count", 0) or 0),
                -int(item.get("event_count", 0) or 0),
                str(item.get("display_name") or "").lower(),
            ),
        )
        rows: List[Dict[str, Any]] = []
        for item in ordered[:top_characters]:
            relationships = item.get("relationships") or []
            canon_state = {
                "roles": item.get("current_roles") or [],
                "emotional_state": item.get("emotional_state", ""),
                "physical_state": item.get("physical_state", ""),
                "powers_or_abilities": item.get("powers_or_abilities") or [],
                "affiliations": item.get("affiliations") or [],
                "open_conflicts": item.get("open_conflicts") or [],
                "state_scope": item.get("state_scope", ""),
                "confidence": item.get("confidence", ""),
            }
            descriptions = [item.get("core_description", "")] + list(item.get("traits") or [])
            first_seen = item.get("first_seen") or {}
            rows.append(
                {
                    "name": item.get("display_name", ""),
                    "mention_count": int(item.get("mention_count", 0) or 0),
                    "first_seen_chapter": first_seen.get("chapter_index"),
                    "descriptions": [text for text in descriptions if str(text or "").strip()],
                    "aliases": item.get("aliases", []) or [],
                    "canon_state": canon_state,
                    "state_transitions": [
                        {
                            "attribute": "relationship",
                            "previous_state": "",
                            "new_state": rel.get("latest_change", "") or rel.get("relationship_type", ""),
                            "change_type": rel.get("relationship_type", ""),
                            "evidence": rel.get("evidence", ""),
                            "chapter": None,
                        }
                        for rel in relationships[:6]
                    ]
                    + [
                        {
                            "attribute": "evidence",
                            "previous_state": "",
                            "new_state": row.get("summary", ""),
                            "change_type": row.get("source", ""),
                            "evidence": row.get("summary", ""),
                            "chapter": row.get("chapter"),
                        }
                        for row in (item.get("evidence") or [])[:6]
                    ],
                }
            )
        return rows

    def character_states_from_snapshot(
        self,
        snapshot_payload: Dict[str, Any],
        *,
        top_characters: int = 10,
    ) -> List[Dict[str, Any]]:
        return self._character_states_from_snapshot(
            snapshot_payload.get("character_states") or [],
            top_characters=top_characters,
        )

    def _retrieval_documents(self, *, bundle: Dict[str, Any], outputs: Dict[str, Any]) -> List[Dict[str, Any]]:
        summary = self.story_index_service.build(
            artifact_bundle=bundle,
            scene_analyses=(outputs.get("resolved_scene_analyses") or outputs.get("scene_analyses") or []),
            timeline=outputs.get("timeline") or [],
            event_ledger=bundle.get("event_ledger") or outputs.get("event_ledger") or [],
            character_timelines=outputs.get("character_timelines") or [],
            character_profiles=bundle.get("character_profiles") or outputs.get("character_profiles") or [],
            relationship_profiles=bundle.get("relationship_profiles") or [],
            entity_profiles=bundle.get("entity_profiles") or [],
            canon_snapshots=bundle.get("canon_snapshots") or [],
            entity_registry=outputs.get("entity_registry") or [],
            state_result=outputs.get("state_result") or {},
            identity_result=outputs.get("identity_result") or {},
            causal_graph_result=outputs.get("causal_graph_result") or {"graph": {"events": []}},
        )
        if int(summary.get("document_count", 0) or 0) <= 0:
            return []
        documents: List[Dict[str, Any]] = []
        for index, doc in enumerate(self.story_index_service.documents):
            documents.append(
                {
                    "document_id": f"doc_{index}",
                    "source_type": doc.get("item_type", ""),
                    "summary": doc.get("summary", ""),
                    "text": doc.get("text", ""),
                    "metadata": doc.get("metadata", {}),
                }
            )
        return documents

    def _alias_index(self, outputs: Dict[str, Any]) -> Dict[str, str]:
        identity_result = outputs.get("identity_result") or {}
        provider_alias_index = identity_result.get("provider_alias_index") or {}
        if provider_alias_index:
            provider_name_by_id = {
                str(row.get("id") or "").strip(): str(row.get("display_name") or "").strip()
                for row in (identity_result.get("provider_characters") or [])
                if str(row.get("id") or "").strip() and str(row.get("display_name") or "").strip()
            }
            return {
                str(alias or "").strip().lower(): provider_name_by_id.get(str(canonical or "").strip(), str(canonical or "").strip())
                for alias, canonical in provider_alias_index.items()
                if str(alias or "").strip() and str(canonical or "").strip()
            }
        alias_map = (identity_result.get("alias_map") or {})
        index: Dict[str, str] = {}
        for canonical_name, aliases in alias_map.items():
            canonical = (canonical_name or "").strip()
            if not canonical:
                continue
            index[canonical.lower()] = canonical
            for alias in aliases or []:
                cleaned = (alias or "").strip()
                if cleaned:
                    index[cleaned.lower()] = canonical
        return index

    def _book_title(self, contract: Dict[str, Any]) -> str:
        books = ((contract.get("inputs") or {}).get("books") or [])
        if books:
            first = books[0] or {}
            title = (first.get("title") or "").strip()
            if title:
                return title
            path = (first.get("path") or "").strip()
            if path:
                return Path(path).stem
        return "Unknown"

    def _last_scene(self, outputs: Dict[str, Any]) -> Dict[str, Any]:
        resolved = outputs.get("resolved_scene_analyses") or outputs.get("scene_analyses") or []
        if not resolved:
            return {}
        scene = resolved[-1]
        return {
            "summary": scene.get("scene_summary", ""),
            "book_index": scene.get("book_index"),
            "chapter_index": scene.get("chapter_index"),
            "scene_index": scene.get("scene_index"),
            "location": scene.get("location"),
            "entities_present": scene.get("entities_present", []) or [],
            "relationship_changes": scene.get("relationship_changes", []) or [],
            "state_changes": scene.get("state_changes", []) or [],
        }

    def _event_lookup(self, outputs: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        graph = ((outputs.get("causal_graph_result") or {}).get("graph") or {})
        timeline = outputs.get("timeline") or []
        lookup: Dict[str, Dict[str, Any]] = {}
        for event in graph.get("events", []) or []:
            if event.get("id"):
                lookup[event["id"]] = dict(event)
        for row in timeline:
            source_id = row.get("event_id")
            if source_id:
                lookup.setdefault(source_id, {
                    "id": source_id,
                    "description": row.get("summary", ""),
                    "time_index": row.get("time_index"),
                    "book_index": row.get("book_index"),
                    "chapter_index": row.get("chapter_index"),
                    "scene_index": row.get("scene_index"),
                    "characters": row.get("characters", []) or [],
                })
            graph_id = f"t_{row.get('time_index')}" if row.get("time_index") is not None else ""
            if graph_id:
                lookup.setdefault(graph_id, {
                    "id": graph_id,
                    "description": row.get("summary", ""),
                    "time_index": row.get("time_index"),
                    "book_index": row.get("book_index"),
                    "chapter_index": row.get("chapter_index"),
                    "scene_index": row.get("scene_index"),
                    "characters": row.get("characters", []) or [],
                })
        return lookup

    def _critical_path_tail(self, outputs: Dict[str, Any], event_lookup: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        graph = ((outputs.get("causal_graph_result") or {}).get("graph") or {})
        rows = []
        for item in graph.get("critical_path", []) or []:
            event = event_lookup.get(item.get("event_id", ""), {})
            rows.append({
                "id": item.get("event_id"),
                "description": event.get("description", ""),
                "chapter": event.get("chapter_index"),
                "score": item.get("criticality_score"),
                "why_critical": item.get("why_critical", ""),
                "order": item.get("critical_order"),
                "story_impact": event.get("story_impact"),
            })
        rows.sort(key=lambda row: ((row.get("order") if row.get("order") is not None else 10**9), row.get("chapter") or 0))
        return rows[-10:]

    def _character_states(self, bundle: Dict[str, Any], outputs: Dict[str, Any], top_characters: int) -> List[Dict[str, Any]]:
        profiles = sorted(
            bundle.get("character_profiles") or [],
            key=lambda item: (-int(item.get("mention_count", 0)), -int(item.get("event_count", 0))),
        )
        if not profiles:
            provider_characters = ((outputs.get("identity_result") or {}).get("provider_characters") or [])
            fallback_rows = []
            for row in provider_characters[:top_characters]:
                fallback_rows.append({
                    "name": row.get("display_name", ""),
                    "mention_count": row.get("mention_count", 0),
                    "first_seen_chapter": row.get("first_seen"),
                    "descriptions": [],
                    "aliases": row.get("aliases", []) or [],
                    "canon_state": {},
                    "state_transitions": [],
                })
            return fallback_rows
        registry_by_name = {
            (row.get("name") or "").strip().lower(): row
            for row in (outputs.get("entity_registry") or [])
        }
        transitions = outputs.get("state_result", {}).get("transitions", []) if outputs.get("state_result") else []
        result = []
        for profile in profiles[:top_characters]:
            name = profile.get("canonical_name", "")
            if not name:
                continue
            registry_entry = registry_by_name.get(name.lower(), {})
            result.append({
                "name": name,
                "mention_count": profile.get("mention_count", 0),
                "first_seen_chapter": (profile.get("first_seen") or {}).get("chapter_index"),
                "descriptions": self._description_strings(registry_entry, profile),
                "aliases": profile.get("aliases", []) or [],
                "canon_state": profile.get("state_at_latest", {}) or {},
                "state_transitions": [
                    {
                        "attribute": row.get("attribute", ""),
                        "previous_state": row.get("previous_state", ""),
                        "new_state": row.get("new_state", ""),
                        "change_type": row.get("change_type", ""),
                        "evidence": row.get("evidence", ""),
                        "chapter": row.get("chapter_index"),
                    }
                    for row in transitions
                    if (row.get("entity_name") or "").strip().lower() == name.lower()
                ],
            })
        return result

    def _description_strings(self, registry_entry: Dict[str, Any], profile: Dict[str, Any]) -> List[str]:
        descriptions = [
            row.get("description", "")
            for row in (registry_entry.get("descriptions") or [])
            if row.get("description")
        ]
        if not descriptions and profile.get("core_description"):
            descriptions = [profile["core_description"]]
        return descriptions

    def _relationship_summary(self, bundle: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows = []
        for profile in bundle.get("relationship_profiles") or []:
            changes = profile.get("change_log") or []
            latest = changes[-1] if changes else {}
            rows.append({
                "entity_a": profile.get("source_character", ""),
                "entity_b": profile.get("target_character", ""),
                "relationship_type": profile.get("relationship_type", ""),
                "latest_change": latest.get("change", ""),
                "evidence": latest.get("evidence", ""),
                "last_seen_chapter": latest.get("chapter_index"),
            })
        return rows

    def _unresolved_threads(
        self,
        outputs: Dict[str, Any],
        event_lookup: Dict[str, Dict[str, Any]],
        top_threads: int,
    ) -> List[Dict[str, Any]]:
        graph = ((outputs.get("causal_graph_result") or {}).get("graph") or {})
        rows = []
        for item in sorted(
            graph.get("divergence_points", []) or [],
            key=lambda row: row.get("divergence_potential", 0),
            reverse=True,
        )[:top_threads]:
            event = event_lookup.get(item.get("event_id", ""), {})
            rows.append({
                "event_id": item.get("event_id"),
                "event_description": event.get("description", ""),
                "chapter": event.get("chapter_index"),
                "is_critical": any(
                    critical.get("event_id") == item.get("event_id")
                    for critical in graph.get("critical_path", []) or []
                ),
                "decision_made": item.get("decision_made", ""),
                "alternatives": item.get("alternatives", []) or [],
                "divergence_potential": item.get("divergence_potential"),
                "alternate_timeline": item.get("alternate_timeline", ""),
            })
        return rows

    def _causal_chains(self, outputs: Dict[str, Any], event_lookup: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        graph = ((outputs.get("causal_graph_result") or {}).get("graph") or {})
        rows = []
        for chain in graph.get("causal_chains", []) or []:
            events = []
            for event_id in chain.get("event_sequence", []) or []:
                event = event_lookup.get(event_id, {})
                events.append({
                    "event_id": event_id,
                    "description": event.get("description", ""),
                    "chapter": event.get("chapter_index"),
                    "time_index": event.get("time_index"),
                })
            rows.append({
                "chain_id": chain.get("chain_id", ""),
                "description": chain.get("description", ""),
                "chain_type": chain.get("chain_type", ""),
                "story_function": chain.get("story_function", ""),
                "events": events,
            })
        return rows

    def _flexible_events(
        self,
        outputs: Dict[str, Any],
        event_lookup: Dict[str, Dict[str, Any]],
        top_flexible_events: int,
    ) -> List[Dict[str, Any]]:
        graph = ((outputs.get("causal_graph_result") or {}).get("graph") or {})
        rows = []
        for item in sorted(
            graph.get("flexible_events", []) or [],
            key=lambda row: row.get("flexibility_score", 0),
            reverse=True,
        )[:top_flexible_events]:
            event = event_lookup.get(item.get("event_id", ""), {})
            rows.append({
                "event_id": item.get("event_id"),
                "description": event.get("description", ""),
                "chapter": event.get("chapter_index"),
                "flexibility_score": item.get("flexibility_score"),
                "why_flexible": item.get("why_flexible", ""),
            })
        return rows

    def _character_trajectories(self, bundle: Dict[str, Any], top_character_trajectories: int) -> List[Dict[str, Any]]:
        rows = []
        for profile in sorted(
            bundle.get("character_profiles") or [],
            key=lambda item: (-int(item.get("event_count", 0)), -int(item.get("mention_count", 0))),
        )[:top_character_trajectories]:
            rows.append({
                "character": profile.get("canonical_name", ""),
                "last_events": [
                    {
                        "summary": event.get("summary", ""),
                        "time_index": event.get("time_index"),
                    }
                    for event in (profile.get("important_history") or [])[-5:]
                ],
            })
        return rows
