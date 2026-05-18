"""Hybrid graph + embedding retrieval for focused narrative generation packets."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional

from rag.hybrid_embedding_index_service import HybridEmbeddingIndexService


class HybridNarrativeRetriever:
    """Build focused context packets for chapter outlining and scene prose."""

    def __init__(self, *, index_service: Optional[HybridEmbeddingIndexService] = None) -> None:
        self.index_service = index_service or HybridEmbeddingIndexService()

    def build_outline_context_packet(
        self,
        *,
        retrieval_context: Dict[str, Any],
        compiled_context: Dict[str, Any],
        blueprint: Dict[str, Any],
        world_state: Dict[str, Any],
        current_story_position: Dict[str, Any],
        chapter_number: int,
        previous_summaries: List[str],
        chapter_controls: Dict[str, Any],
    ) -> Dict[str, Any]:
        index_payload = self._ensure_index(retrieval_context)
        controls = compiled_context.get("generation_controls") or {}
        pov_name = str(chapter_controls.get("primary_pov_character") or controls.get("primary_pov_character") or "").strip()
        beat_text = " ".join(chapter_controls.get("assigned_plot_beats") or [])
        query_text = " ".join(
            filter(
                None,
                [
                    pov_name,
                    str(blueprint.get("central_conflict") or "").strip(),
                    beat_text,
                    str(blueprint.get("new_plot_thread") or "").strip(),
                    str(current_story_position.get("latest_generated_ending") or "").strip(),
                    str(previous_summaries[-1] if previous_summaries else "").strip(),
                ],
            )
        )
        retrieved_items = self.index_service.query(
            index_payload=index_payload,
            query_text=query_text,
            top_k=6,
            allowed_types={"scene", "event", "trajectory", "thread"},
            character_bias=[pov_name] if pov_name else [],
        )
        active_names = self._unique_names(
            [pov_name] +
            self._characters_from_relationship_targets(blueprint.get("relationship_targets") or []) +
            self._characters_from_world_state(world_state)
        )
        relevant_threads = self._relevant_threads(
            retrieval_context.get("unresolved_threads") or [],
            query_text=query_text,
            names=active_names,
            top_k=4,
        )
        relevant_causal = self._relevant_causal_chains(
            retrieval_context.get("causal_chains") or [],
            query_text=query_text,
            top_k=3,
        )
        relevant_relationships = self._relevant_relationships(
            retrieval_context.get("relationship_summary") or [],
            active_names,
            top_k=6,
        )
        canon_facts = self._select_relevant_canon_facts(
            controls.get("canon_elements_to_preserve") or [],
            names=active_names,
            topical_text=query_text,
        )
        return {
            "query_summary": {
                "chapter_number": chapter_number,
                "pov_character": pov_name,
                "query_text": query_text,
                "assigned_plot_beats": chapter_controls.get("assigned_plot_beats") or [],
            },
            "source_ending_baseline": compiled_context.get("story_ending", {}) or {},
            "current_story_position": current_story_position,
            "pov_character_packet": self._character_packet(retrieval_context, pov_name),
            "active_relationship_packet": relevant_relationships,
            "relevant_unresolved_threads": relevant_threads,
            "relevant_causal_items": relevant_causal,
            "retrieved_memories": retrieved_items,
            "canon_facts_for_this_chapter": canon_facts,
            "chapter_relationship_focus": chapter_controls.get("relationship_focus") or [],
            "recent_summaries": previous_summaries[-3:] if previous_summaries else [],
        }

    def build_scene_context_packet(
        self,
        *,
        retrieval_context: Dict[str, Any],
        compiled_context: Dict[str, Any],
        scene_outline: Dict[str, Any],
        chapter_outline: Dict[str, Any],
        world_state: Dict[str, Any],
        scene_memory: Dict[str, Any],
        previous_scene_ending: str,
        chapter_controls: Dict[str, Any],
    ) -> Dict[str, Any]:
        index_payload = self._ensure_index(retrieval_context)
        controls = compiled_context.get("generation_controls") or {}
        pov_name = str(chapter_outline.get("pov_character") or controls.get("primary_pov_character") or "").strip()
        present_names = self._unique_names(list(scene_outline.get("characters_present") or []))
        monologue_bias = self._is_internal_monologue_scene(scene_outline)
        scene_type = self._scene_type(scene_outline, chapter_controls)
        query_text = " ".join(
            filter(
                None,
                [
                    pov_name,
                    str(scene_outline.get("summary") or "").strip(),
                    str(scene_outline.get("purpose") or "").strip(),
                    str(scene_outline.get("ends_on") or "").strip(),
                    " ".join(chapter_controls.get("assigned_plot_beats") or []),
                    str(previous_scene_ending or "").strip(),
                ],
            )
        )
        character_bias = [pov_name] if monologue_bias and pov_name else (present_names or ([pov_name] if pov_name else []))
        retrieved_items = self.index_service.query(
            index_payload=index_payload,
            query_text=query_text,
            top_k=5 if monologue_bias else 7,
            allowed_types={"scene", "event", "trajectory", "thread"},
            character_bias=character_bias,
        )
        names_for_filters = self._unique_names(([pov_name] if pov_name else []) + present_names)
        participant_relationships = self._relevant_relationships(
            retrieval_context.get("relationship_summary") or [],
            names_for_filters,
            top_k=5,
            relationship_focus=chapter_controls.get("relationship_focus") or [],
        )
        canon_guardrails = self._select_relevant_canon_facts(
            controls.get("canon_elements_to_preserve") or [],
            names=names_for_filters,
            topical_text=query_text,
        )
        filtered_memories = self._filter_memories_for_scene_type(
            retrieved_items,
            scene_type=scene_type,
            active_names=names_for_filters,
        )
        current_threads = self._relevant_threads(
            retrieval_context.get("unresolved_threads") or [],
            query_text=query_text,
            names=names_for_filters,
            top_k=3,
        )
        return {
            "query_summary": {
                "scene_number": scene_outline.get("scene_number"),
                "pov_character": pov_name,
                "scene_type": scene_type,
                "query_text": query_text,
            },
            "pov_character_packet": self._character_packet(retrieval_context, pov_name),
            "scene_participants": self._character_packets(retrieval_context, present_names),
            "participant_relationships": participant_relationships,
            "chapter_local_memory": {
                "previous_scene_ending": previous_scene_ending,
                "scene_memory": scene_memory,
            },
            "retrieved_memories": filtered_memories,
            "canon_guardrails": canon_guardrails,
            "required_plot_beats": chapter_controls.get("assigned_plot_beats") or [],
            "relationship_focus": chapter_controls.get("relationship_focus") or [],
            "current_world_threads": current_threads,
            "retrieval_debug": {
                "selected_entity_packets": [item.get("name", "") for item in self._character_packets(retrieval_context, names_for_filters)],
                "selected_event_ids": [item.get("document_id", "") for item in filtered_memories if str(item.get("source_type") or "") == "event"],
                "selected_canon_facts": [str(item.get("description") or item.get("event_id") or "").strip() for item in canon_guardrails],
                "discarded_noisy_candidates_count": max(0, len(retrieved_items) - len(filtered_memories))
                + max(0, len(retrieval_context.get("relationship_summary") or []) - len(participant_relationships))
                + max(0, len((controls.get("canon_elements_to_preserve") or [])) - len(canon_guardrails)),
            },
        }

    def _ensure_index(self, retrieval_context: Dict[str, Any]) -> Dict[str, Any]:
        meta = retrieval_context.get("meta", {}) or {}
        documents = list(retrieval_context.get("retrieval_documents") or [])
        scope_key = self._scope_key(meta)
        return self.index_service.ensure_index(
            series_id=str(meta.get("series_id") or "standalone"),
            scope_key=scope_key,
            documents=documents,
        )

    def _scope_key(self, meta: Dict[str, Any]) -> str:
        matched_titles = meta.get("matched_book_titles") or meta.get("book_titles") or []
        if matched_titles:
            return "__".join(self._slug(title) for title in matched_titles)
        return self._slug(str(meta.get("book_title") or "default"))

    def _character_packets(self, retrieval_context: Dict[str, Any], names: Iterable[str]) -> List[Dict[str, Any]]:
        return [packet for packet in [self._character_packet(retrieval_context, name) for name in names] if packet]

    def _character_packet(self, retrieval_context: Dict[str, Any], name: str) -> Dict[str, Any]:
        canonical = self._norm_name(name)
        if not canonical:
            return {}
        for item in retrieval_context.get("character_states") or []:
            candidates = [item.get("name", "")] + list(item.get("aliases") or [])
            if any(self._norm_name(candidate) == canonical for candidate in candidates):
                return {
                    "name": item.get("name", ""),
                    "descriptions": item.get("descriptions", []) or [],
                    "canon_state": item.get("canon_state", {}) or {},
                    "recent_changes": (item.get("state_transitions") or [])[-4:],
                    "aliases": item.get("aliases", []) or [],
                }
        return {}

    def _relevant_relationships(
        self,
        relationships: List[Dict[str, Any]],
        names: List[str],
        top_k: int,
        relationship_focus: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        if not names:
            return []
        target_names = {self._norm_name(name) for name in names if self._norm_name(name)}
        focus_names = {
            self._norm_name(name)
            for item in (relationship_focus or [])
            for name in (item.get("characters") or [])
            if self._norm_name(name)
        }
        rows: List[Dict[str, Any]] = []
        for item in relationships:
            a = self._norm_name(item.get("entity_a") or item.get("between", "").split("<->")[0])
            b = self._norm_name(item.get("entity_b") or item.get("between", "").split("<->")[-1])
            if a in target_names or b in target_names or (focus_names and (a in focus_names or b in focus_names)):
                rows.append(item)
        return rows[:top_k]

    def _relevant_threads(self, threads: List[Dict[str, Any]], *, query_text: str, names: List[str], top_k: int) -> List[Dict[str, Any]]:
        query_tokens = self._tokens(query_text)
        name_tokens = {self._norm_name(name) for name in names if self._norm_name(name)}
        scored: List[tuple[int, Dict[str, Any]]] = []
        for item in threads:
            text = " ".join(
                filter(
                    None,
                    [
                        str(item.get("event_description") or "").strip(),
                        str(item.get("decision_made") or "").strip(),
                        " ".join(item.get("alternatives") or []),
                    ],
                )
            )
            tokens = self._tokens(text)
            score = len(tokens & query_tokens)
            if name_tokens and any(name in self._norm_name(text) for name in name_tokens):
                score += 2
            score += int(item.get("divergence_potential") or 0)
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda row: row[0], reverse=True)
        return [item for _, item in scored[:top_k]]

    def _relevant_causal_chains(self, causal_chains: List[Dict[str, Any]], *, query_text: str, top_k: int) -> List[Dict[str, Any]]:
        query_tokens = self._tokens(query_text)
        scored: List[tuple[int, Dict[str, Any]]] = []
        for item in causal_chains:
            text = " ".join(
                filter(
                    None,
                    [
                        str(item.get("description") or "").strip(),
                        str(item.get("story_function") or "").strip(),
                        " ".join(str(event.get("description") or "").strip() for event in (item.get("events") or [])),
                    ],
                )
            )
            score = len(self._tokens(text) & query_tokens)
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda row: row[0], reverse=True)
        return [item for _, item in scored[:top_k]]

    def _select_relevant_canon_facts(
        self,
        canon_facts: List[Dict[str, Any]],
        *,
        names: List[str],
        topical_text: str,
    ) -> List[Dict[str, Any]]:
        if not canon_facts:
            return []
        topical_tokens = self._tokens(topical_text)
        normalized_names = {self._norm_name(name) for name in names if self._norm_name(name)}
        relevant: List[Dict[str, Any]] = []
        fallback: List[Dict[str, Any]] = []
        for item in canon_facts:
            description = str(item.get("description") or item.get("event_id") or "").strip()
            if not description:
                continue
            fallback.append(item)
            description_norm = self._norm_name(description)
            if normalized_names and any(name and name in description_norm for name in normalized_names):
                relevant.append(item)
                continue
            if self._tokens(description) & topical_tokens:
                relevant.append(item)
        return (relevant or fallback)[:5]

    def _characters_from_relationship_targets(self, rows: List[Dict[str, Any]]) -> List[str]:
        names: List[str] = []
        for item in rows:
            names.extend(item.get("characters") or [])
        return names

    def _characters_from_world_state(self, world_state: Dict[str, Any]) -> List[str]:
        return [item.get("name", "") for item in (world_state.get("characters") or []) if item.get("name")]

    def _is_internal_monologue_scene(self, scene_outline: Dict[str, Any]) -> bool:
        characters_present = scene_outline.get("characters_present") or []
        if len(characters_present) <= 1:
            return True
        text = " ".join(
            filter(
                None,
                [
                    str(scene_outline.get("summary") or "").strip(),
                    str(scene_outline.get("purpose") or "").strip(),
                ],
            )
        ).lower()
        return any(token in text for token in ["reflect", "remembers", "vision", "thinks", "considers", "internal"])

    def _scene_type(self, scene_outline: Dict[str, Any], chapter_controls: Dict[str, Any]) -> str:
        if self._is_internal_monologue_scene(scene_outline):
            return "internal_monologue"
        text = " ".join(
            filter(
                None,
                [
                    str(scene_outline.get("summary") or "").strip(),
                    str(scene_outline.get("purpose") or "").strip(),
                    " ".join(str(item.get("desired_direction") or "") for item in (chapter_controls.get("relationship_focus") or [])),
                ],
            )
        ).lower()
        if any(token in text for token in ["court", "council", "treaty", "war room", "politic", "alliance", "minister"]):
            return "political"
        if any(token in text for token in ["kiss", "touch", "desire", "romance", "forbidden", "bond", "longing", "intimate"]):
            return "romance"
        return "interactive"

    def _filter_memories_for_scene_type(
        self,
        retrieved_items: List[Dict[str, Any]],
        *,
        scene_type: str,
        active_names: List[str],
    ) -> List[Dict[str, Any]]:
        normalized_names = {self._norm_name(name) for name in active_names if self._norm_name(name)}
        filtered: List[Dict[str, Any]] = []
        for item in retrieved_items:
            metadata = item.get("metadata", {}) or {}
            characters = {self._norm_name(name) for name in (metadata.get("characters") or []) if self._norm_name(name)}
            source_type = str(item.get("source_type") or "")
            summary = str(item.get("summary") or "").lower()
            if scene_type == "internal_monologue":
                if source_type == "trajectory":
                    filtered.append(item)
                    continue
                if normalized_names and characters and not (characters & normalized_names):
                    continue
            elif scene_type == "political":
                if "politic" not in summary and "court" not in summary and "war" not in summary and source_type == "thread":
                    continue
            elif scene_type == "romance":
                if source_type == "thread" and not any(token in summary for token in ["bond", "romance", "desire", "mate", "forbidden"]):
                    continue
            filtered.append(item)
        return filtered or retrieved_items[:5]

    def _tokens(self, text: str) -> set[str]:
        return {token for token in re.findall(r"[a-z0-9']+", str(text).lower()) if len(token) > 2}

    def _unique_names(self, values: Iterable[str]) -> List[str]:
        result: List[str] = []
        seen = set()
        for value in values:
            name = str(value or "").strip()
            key = self._norm_name(name)
            if not key or key in seen:
                continue
            result.append(name)
            seen.add(key)
        return result

    def _norm_name(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())

    def _slug(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-") or "default"
