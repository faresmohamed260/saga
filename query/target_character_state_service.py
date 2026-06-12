from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional

from core.builders.relationship_profile_builder import RelationshipProfileBuilder
from core.pipeline_contract import (
    build_canon_snapshot,
    build_character_timelines,
    build_entity_registry,
    build_event_ledger,
    build_formal_character_profiles,
    build_state_result,
    build_timeline,
    normalize_character_timelines,
    rebuild_resolved_scene_analyses,
)
from redesign_lab.identity.identity_provider import resolve_identity_provider_input


def _scene_ref_key(book_index: int, chapter_index: int, scene_index: int) -> tuple[int, int, int]:
    return int(book_index or 0), int(chapter_index or 0), int(scene_index or 0)


def _normalize_text_list(values: Iterable[str]) -> List[str]:
    seen = set()
    rows: List[str] = []
    for value in values or []:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append(text)
    return rows


def _target_scope_label(target_point: Dict[str, Any]) -> str:
    mode = str(target_point.get("mode") or "")
    if mode == "post_series":
        return f"after_book_{int(target_point.get('after_book_index') or 0)}"
    if mode == "post_book":
        return f"after_book_{int(target_point.get('after_book_index') or target_point.get('book_index') or 0)}"
    if mode == "mid_canon":
        return f"book_{int(target_point.get('book_index') or 0)}_chapter_{int(target_point.get('chapter') or 0)}"
    if mode == "custom":
        return (
            f"book_{int(target_point.get('book_index') or 0)}_"
            f"chapter_{int(target_point.get('chapter') or 0)}_"
            f"scene_{int(target_point.get('scene_index') or 0)}"
        )
    if mode == "pre_canon":
        return "pre_canon"
    return mode or "unknown"


def _parse_scene_index(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    match = re.search(r"_s(\d+)$", text)
    if match:
        return int(match.group(1))
    raise ValueError(f"Could not parse scene index from scene identifier: {value}")


@dataclass
class TargetPoint:
    mode: str
    book_index: int | None = None
    chapter: int | None = None
    scene_index: int | None = None
    after_book_index: int | None = None
    include_future_facts: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "book_index": self.book_index,
            "chapter": self.chapter,
            "scene_index": self.scene_index,
            "after_book_index": self.after_book_index,
            "include_future_facts": self.include_future_facts,
        }


class TargetCharacterStateService:
    def __init__(self) -> None:
        self.relationship_builder = RelationshipProfileBuilder()

    def normalize_target_point(self, target_point: Dict[str, Any]) -> TargetPoint:
        if not isinstance(target_point, dict):
            raise ValueError("target_point must be a JSON object.")
        mode = str(target_point.get("mode") or "").strip()
        if not mode:
            raise ValueError("target_point.mode is required.")
        include_future = bool(target_point.get("include_future_facts", False))
        point = TargetPoint(
            mode=mode,
            book_index=int(target_point["book_index"]) if target_point.get("book_index") is not None else None,
            chapter=int(target_point["chapter"]) if target_point.get("chapter") is not None else None,
            scene_index=_parse_scene_index(
                target_point.get("scene_index", target_point.get("scene_id"))
            ),
            after_book_index=int(target_point["after_book_index"]) if target_point.get("after_book_index") is not None else None,
            include_future_facts=include_future,
        )
        if point.mode == "post_series":
            if point.after_book_index is None:
                raise ValueError("target_point.after_book_index is required for post_series.")
        elif point.mode == "post_book":
            if point.after_book_index is None and point.book_index is None:
                raise ValueError("target_point.after_book_index or book_index is required for post_book.")
        elif point.mode == "mid_canon":
            if point.book_index is None or point.chapter is None:
                raise ValueError("target_point.book_index and chapter are required for mid_canon.")
        elif point.mode == "custom":
            if point.book_index is None or point.chapter is None or point.scene_index is None:
                raise ValueError("target_point.book_index, chapter, and scene_index are required for custom.")
        elif point.mode == "pre_canon":
            pass
        else:
            raise ValueError(f"Unsupported target_point.mode: {point.mode}")
        return point

    def build_character_state_snapshot(
        self,
        *,
        contract_paths: List[str | Path],
        target_point: Dict[str, Any],
        identity_json_path: str | Path | None = None,
        character_ids: Optional[List[str]] = None,
        include_reference_entities: bool = False,
    ) -> Dict[str, Any]:
        if not contract_paths:
            raise ValueError("At least one contract path is required.")
        normalized_target = self.normalize_target_point(target_point)
        contracts = [json.loads(Path(path).read_text(encoding="utf-8")) for path in contract_paths]
        books: List[Dict[str, Any]] = []
        for contract in contracts:
            books.extend(((contract.get("inputs") or {}).get("books") or []))

        if identity_json_path:
            provider = resolve_identity_provider_input(
                provider_mode="booknlp_clean",
                input_json=identity_json_path,
                book_inputs=books or None,
            )
            try:
                identity_result = provider.build_identity_result_compat(book_inputs=books or None)
                pipeline_identity = provider.build_pipeline_identity(book_inputs=books or None)
            except TypeError:
                identity_result = provider.build_identity_result_compat()
                pipeline_identity = provider.build_pipeline_identity()
        else:
            identity_result = (contracts[-1].get("outputs") or {}).get("identity_result") or {"alias_map": {}}
            pipeline_identity = (contracts[-1].get("outputs") or {}).get("pipeline_identity") or {}

        scene_analyses: List[Dict[str, Any]] = []
        for contract in contracts:
            scene_analyses.extend(((contract.get("outputs") or {}).get("scene_analyses") or []))
        resolved_scenes = rebuild_resolved_scene_analyses(scene_analyses, identity_result)
        filtered_scenes = self._filter_scenes(resolved_scenes, normalized_target)
        state_result = build_state_result(filtered_scenes)
        timeline = build_timeline(filtered_scenes)
        event_ledger = build_event_ledger(filtered_scenes, timeline, {"graph": {"events": []}})
        entity_registry = build_entity_registry(filtered_scenes)
        character_timelines = build_character_timelines(timeline)
        character_timelines = normalize_character_timelines(character_timelines, identity_result)
        timeline_by_name = {
            str(item.get("character") or "").strip().lower(): item
            for item in character_timelines
            if str(item.get("character") or "").strip()
        }
        character_profiles = build_formal_character_profiles(
            character_timelines,
            entity_registry,
            state_result,
            identity_result,
            filtered_scenes,
        )
        latest_scene = filtered_scenes[-1] if filtered_scenes else {}
        canon_snapshot = build_canon_snapshot(
            state_result,
            (
                latest_scene.get("book_index", 0),
                latest_scene.get("chapter_index", 0),
                latest_scene.get("scene_index", 0),
            ),
        ) if filtered_scenes else []
        relationship_profiles = self.relationship_builder.build(scene_analyses=filtered_scenes)

        allowed_ids = {item.strip() for item in (character_ids or []) if str(item or "").strip()}
        states = []
        for profile in character_profiles:
            if allowed_ids and str(profile.get("character_id") or "").strip() not in allowed_ids:
                continue
            states.append(
                self._snapshot_for_profile(
                    profile=profile,
                    character_timeline=timeline_by_name.get(str(profile.get("canonical_name") or "").strip().lower(), {}),
                    relationship_profiles=relationship_profiles,
                    state_result=state_result,
                    target_point=normalized_target.to_dict(),
                )
            )

        diagnostics = {
            "contract_count": len(contracts),
            "scene_count_before_filter": len(resolved_scenes),
            "scene_count_after_filter": len(filtered_scenes),
            "character_profile_count": len(character_profiles),
            "character_state_count": len(states),
            "event_ledger_count": len(event_ledger),
            "timeline_count": len(timeline),
            "state_transition_count": len((state_result.get("transitions") or [])),
            "reference_entity_count": len((pipeline_identity.get("reference_entities") or [])),
            "include_reference_entities": include_reference_entities,
            "identity_provider": identity_result.get("identity_provider") or "booknlp_clean",
            "provider_locked": bool(identity_result.get("provider_locked")),
            "future_fact_filtering": not normalized_target.include_future_facts,
            "target_scope": _target_scope_label(normalized_target.to_dict()),
            "filtered_scene_refs": [
                {
                    "book_index": row.get("book_index"),
                    "chapter_index": row.get("chapter_index"),
                    "scene_index": row.get("scene_index"),
                }
                for row in filtered_scenes[-10:]
            ],
        }
        return {
            "target_point": normalized_target.to_dict(),
            "character_states": states,
            "reference_entities": (pipeline_identity.get("reference_entities") or []) if include_reference_entities else [],
            "diagnostics": diagnostics,
        }

    def _filter_scenes(self, scenes: List[Dict[str, Any]], target_point: TargetPoint) -> List[Dict[str, Any]]:
        if target_point.include_future_facts:
            return list(scenes)
        filtered = [scene for scene in scenes if self._scene_in_scope(scene, target_point)]
        return sorted(filtered, key=lambda row: _scene_ref_key(row.get("book_index", 0), row.get("chapter_index", 0), row.get("scene_index", 0)))

    def _scene_in_scope(self, scene: Dict[str, Any], target_point: TargetPoint) -> bool:
        ref = _scene_ref_key(scene.get("book_index", 0), scene.get("chapter_index", 0), scene.get("scene_index", 0))
        if target_point.mode == "pre_canon":
            return False
        if target_point.mode in {"post_series", "post_book"}:
            limit = int(target_point.after_book_index or target_point.book_index or 0)
            return ref[0] <= limit
        if target_point.mode == "mid_canon":
            target_ref = (int(target_point.book_index or 0), int(target_point.chapter or 0), 10**9)
            return ref <= target_ref
        if target_point.mode == "custom":
            target_ref = (
                int(target_point.book_index or 0),
                int(target_point.chapter or 0),
                int(target_point.scene_index or 0),
            )
            return ref <= target_ref
        return True

    def _snapshot_for_profile(
        self,
        *,
        profile: Dict[str, Any],
        character_timeline: Dict[str, Any],
        relationship_profiles: List[Dict[str, Any]],
        state_result: Dict[str, Any],
        target_point: Dict[str, Any],
    ) -> Dict[str, Any]:
        canonical_name = str(profile.get("canonical_name") or "").strip()
        latest = dict(profile.get("state_at_latest") or {})
        current_roles = _normalize_text_list([
            latest.get("role", ""),
            latest.get("title", ""),
            latest.get("court_role", ""),
            latest.get("political_role", ""),
            latest.get("family_role", ""),
        ])
        relationships = self._relationships_for_character(canonical_name, relationship_profiles)
        emotional_state = self._pick_first(latest, ["emotional_state", "mood", "grief", "trust"])
        physical_state = self._pick_first(latest, ["physical_state", "condition", "status"])
        powers = _normalize_text_list([
            latest.get("power_status", ""),
            *list(profile.get("abilities") or []),
        ])
        affiliations = _normalize_text_list([
            latest.get("court", ""),
            latest.get("allegiance", ""),
            latest.get("loyalty", ""),
            latest.get("residence", ""),
        ])
        timeline_events = list(character_timeline.get("events") or [])
        recent_events = [
            {
                "book_index": item.get("book_index"),
                "chapter": item.get("chapter_index"),
                "scene_id": f"b{item.get('book_index')}_c{item.get('chapter_index')}_s{item.get('scene_index')}",
                "event_id": item.get("event_id"),
                "summary": item.get("summary"),
            }
            for item in timeline_events[-6:]
        ]
        stable_facts = _normalize_text_list(
            [profile.get("core_description", "")]
            + [f"{key}={value}" for key, value in latest.items() if str(value or "").strip()]
        )
        evidence = self._evidence_for_profile(profile, timeline_events)
        confidence = self._confidence_for_profile(profile, relationships, latest)
        risk_flags = []
        if confidence == "low":
            risk_flags.append("sparse_profile")
        if not latest:
            risk_flags.append("no_current_state_attributes")
        if not relationships:
            risk_flags.append("limited_relationship_evidence")
        first_seen = profile.get("first_seen") or {}
        return {
            "character_id": profile.get("character_id"),
            "display_name": canonical_name,
            "aliases": list(profile.get("aliases") or []),
            "state_scope": _target_scope_label(target_point),
            "core_description": profile.get("core_description", ""),
            "traits": list(profile.get("traits") or []),
            "mention_count": int(profile.get("mention_count", 0) or 0),
            "event_count": int(profile.get("event_count", 0) or 0),
            "first_seen": {
                "book_index": first_seen.get("book_index"),
                "chapter_index": first_seen.get("chapter_index"),
                "scene_index": first_seen.get("scene_index"),
                "summary": first_seen.get("summary", ""),
            } if isinstance(first_seen, dict) else {"value": first_seen},
            "current_roles": current_roles,
            "relationships": relationships,
            "emotional_state": emotional_state,
            "physical_state": physical_state,
            "powers_or_abilities": powers,
            "affiliations": affiliations,
            "known_goals": list(profile.get("goals") or []),
            "open_conflicts": [row["other_character"] for row in relationships if row.get("conflict_level") in {"medium", "high"}],
            "recent_key_events": recent_events,
            "stable_facts": stable_facts,
            "evidence": evidence,
            "confidence": confidence,
            "risk_flags": risk_flags,
        }

    def _relationships_for_character(self, canonical_name: str, relationship_profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        lowered = canonical_name.lower()
        for item in relationship_profiles:
            source = str(item.get("source_character") or "").strip()
            target = str(item.get("target_character") or "").strip()
            if lowered not in {source.lower(), target.lower()}:
                continue
            other = target if source.lower() == lowered else source
            latest_change = (item.get("change_log") or [])[-1] if (item.get("change_log") or []) else {}
            rows.append(
                {
                    "other_character": other,
                    "relationship_type": item.get("relationship_type", ""),
                    "trust_level": item.get("trust_level", "unknown"),
                    "conflict_level": item.get("conflict_level", "unknown"),
                    "romantic_signal": item.get("romantic_signal", "none"),
                    "latest_change": latest_change.get("change", ""),
                    "evidence": latest_change.get("evidence", ""),
                }
            )
        rows.sort(key=lambda row: row["other_character"].lower())
        return rows

    def _pick_first(self, attrs: Dict[str, Any], keys: List[str]) -> str:
        for key in keys:
            value = str(attrs.get(key) or "").strip()
            if value:
                return value
        return ""

    def _evidence_for_profile(self, profile: Dict[str, Any], timeline_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for item in timeline_events[-6:]:
            rows.append(
                {
                    "book_index": item.get("book_index"),
                    "chapter": item.get("chapter_index"),
                    "scene_id": f"b{item.get('book_index')}_c{item.get('chapter_index')}_s{item.get('scene_index')}",
                    "source": "character_profile",
                    "event_id": item.get("event_id"),
                    "summary": item.get("summary"),
                }
            )
        for item in (profile.get("state_history") or [])[-4:]:
            rows.append(
                {
                    "book_index": item.get("book_index"),
                    "chapter": item.get("chapter_index"),
                    "scene_id": f"b{item.get('book_index')}_c{item.get('chapter_index')}_s{item.get('scene_index')}",
                    "source": "state_change",
                    "event_id": "",
                    "summary": f"{item.get('attribute')}={item.get('new_state')}",
                }
            )
        for item in (profile.get("relationship_refs") or [])[-4:]:
            rows.append(
                {
                    "book_index": item.get("book_index"),
                    "chapter": item.get("chapter_index"),
                    "scene_id": f"b{item.get('book_index')}_c{item.get('chapter_index')}_s{item.get('scene_index')}",
                    "source": "relationship_change",
                    "event_id": "",
                    "summary": item.get("evidence") or item.get("change") or item.get("relationship"),
                }
            )
        return rows

    def _confidence_for_profile(self, profile: Dict[str, Any], relationships: List[Dict[str, Any]], latest: Dict[str, Any]) -> str:
        mention_count = int(profile.get("mention_count", 0) or 0)
        event_count = int(profile.get("event_count", 0) or 0)
        if event_count >= 8 or mention_count >= 20 or len(latest) >= 3:
            return "high"
        if (event_count >= 3 or mention_count >= 5) and (relationships or latest or event_count >= 4):
            return "medium"
        return "low"
