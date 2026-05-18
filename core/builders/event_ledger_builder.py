"""Builds canonical event ledger entries from existing pipeline outputs."""

from __future__ import annotations

from typing import Dict, List

from core.normalization.helpers import dedupe_strings


class EventLedgerBuilder:
    """Create a durable event ledger from timeline, scene, and causal outputs."""

    def build(
        self,
        *,
        scene_analyses: List[Dict],
        timeline: List[Dict],
        causal_graph_result: Dict | None = None,
    ) -> List[Dict]:
        scene_lookup = {
            (scene.get("book_index"), scene.get("chapter_index"), scene.get("scene_index")): scene
            for scene in scene_analyses
        }
        causal_events = {
            (item.get("time_index"), item.get("book_index"), item.get("chapter_index"), item.get("scene_index")): item
            for item in ((causal_graph_result or {}).get("graph", {}) or {}).get("events", [])
        }
        output = []
        for row in sorted(timeline, key=lambda item: item.get("time_index", 0)):
            scene = scene_lookup.get((row.get("book_index"), row.get("chapter_index"), row.get("scene_index")), {})
            causal = causal_events.get((row.get("time_index"), row.get("book_index"), row.get("chapter_index"), row.get("scene_index")), {})
            summary = (row.get("summary") or "").strip()
            output.append({
                "ledger_event_id": f"canon_evt_{row.get('time_index')}",
                "time_index": int(row.get("time_index") or 0),
                "source_event_id": str(row.get("event_id") or ""),
                "title": self._title_from_summary(summary),
                "summary": summary,
                "book_index": int(row.get("book_index") or 0),
                "chapter_index": int(row.get("chapter_index") or 0),
                "scene_index": int(row.get("scene_index") or 0),
                "participants": dedupe_strings(row.get("characters") or []),
                "location": (scene.get("location") or {}).get("name", ""),
                "time_signals": dedupe_strings(scene.get("time_signals") or []),
                "preconditions": self._scene_preconditions(scene),
                "direct_consequences": self._scene_direct_consequences(scene),
                "causal_parents": dedupe_strings(item.get("event_id", "") for item in causal.get("caused_by", [])),
                "causal_children": dedupe_strings(item.get("event_id", "") for item in causal.get("causes", [])),
                "stakes": self._scene_stakes(scene, summary),
                "tags": self._derive_tags(scene, summary),
            })
        return self._enrich_with_neighbor_context(output)

    def _title_from_summary(self, summary: str) -> str:
        if not summary:
            return "Untitled event"
        first_sentence = summary.split(".")[0].strip()
        return first_sentence if len(first_sentence) <= 90 else first_sentence[:87].rstrip() + "..."

    def _derive_tags(self, scene: Dict, summary: str) -> List[str]:
        lowered = (summary or "").lower()
        tags = []
        if any(keyword in lowered for keyword in {"fight", "battle", "duel", "attack"}):
            tags.append("conflict")
        if any(keyword in lowered for keyword in {"learn", "discover", "realize", "find"}):
            tags.append("discovery")
        if scene.get("state_changes"):
            tags.append("state_change")
        if scene.get("relationship_changes"):
            tags.append("relationship")
        if (scene.get("location") or {}).get("name"):
            tags.append("location_anchored")
        return dedupe_strings(tags)

    def _scene_preconditions(self, scene: Dict) -> List[str]:
        preconditions = []
        location = (scene.get("location") or {}).get("name", "").strip()
        if location:
            preconditions.append(f"Scene is anchored at {location}.")
        for signal in scene.get("time_signals") or []:
            cleaned = str(signal).strip()
            if cleaned:
                preconditions.append(f"Time context: {cleaned}.")
        for change in (scene.get("state_changes") or [])[:3]:
            previous_state = (change.get("previous_state") or "").strip()
            attribute = (change.get("attribute") or "").strip()
            entity_name = (change.get("entity_name") or "").strip()
            if entity_name and attribute and previous_state:
                preconditions.append(f"Before this event, {entity_name} had {attribute}={previous_state}.")
        return dedupe_strings(preconditions)

    def _scene_direct_consequences(self, scene: Dict) -> List[str]:
        consequences = []
        for change in (scene.get("state_changes") or [])[:4]:
            entity_name = (change.get("entity_name") or "").strip()
            attribute = (change.get("attribute") or "").strip()
            new_state = (change.get("new_state") or "").strip()
            if entity_name and attribute and new_state:
                consequences.append(f"{entity_name} now has {attribute}={new_state}.")
        for change in (scene.get("relationship_changes") or [])[:3]:
            source = (change.get("source_entity") or "").strip()
            target = (change.get("target_entity") or "").strip()
            relationship = (change.get("relationship") or "").strip()
            state_change = (change.get("change") or "").strip()
            if source and target and (relationship or state_change):
                consequences.append(
                    f"Relationship shift: {source} and {target} -> {relationship or 'relationship'} ({state_change})."
                )
        return dedupe_strings(consequences)

    def _scene_stakes(self, scene: Dict, summary: str) -> List[str]:
        stakes = []
        lowered = (summary or "").lower()
        if any(keyword in lowered for keyword in {"battle", "fight", "attack", "duel"}):
            stakes.append("Physical safety is at risk.")
        if any(keyword in lowered for keyword in {"discover", "learn", "realize", "reveal", "confide"}):
            stakes.append("Important information may change future decisions.")
        for change in scene.get("state_changes") or []:
            attribute = (change.get("attribute") or "").strip().lower()
            if attribute in {"status", "condition", "physical_state", "grief", "trust", "location", "knowledge"}:
                stakes.append(f"{change.get('entity_name', 'An entity')} undergoes a consequential {attribute} change.")
        for entity in scene.get("entities_present") or []:
            entity_type = (entity.get("entity_type") or "").strip().lower()
            name = (entity.get("name") or "").strip()
            if name and entity_type in {"object", "location", "creature"}:
                stakes.append(f"{name} may matter to later canon as a {entity_type}.")
        return dedupe_strings(stakes[:6])

    def _enrich_with_neighbor_context(self, rows: List[Dict]) -> List[Dict]:
        source_to_ledger = {
            item.get("source_event_id"): item.get("ledger_event_id")
            for item in rows
            if item.get("source_event_id") and item.get("ledger_event_id")
        }
        ledger_lookup = {
            item.get("ledger_event_id"): item
            for item in rows
            if item.get("ledger_event_id")
        }
        for item in rows:
            parent_summaries = []
            for parent in item.get("causal_parents") or []:
                parent_ledger = parent if parent in ledger_lookup else source_to_ledger.get(parent, "")
                parent_row = ledger_lookup.get(parent_ledger) or {}
                if parent_row.get("title"):
                    parent_summaries.append(f"Depends on: {parent_row['title']}.")
            child_summaries = []
            for child in item.get("causal_children") or []:
                child_ledger = child if child in ledger_lookup else source_to_ledger.get(child, "")
                child_row = ledger_lookup.get(child_ledger) or {}
                if child_row.get("title"):
                    child_summaries.append(f"Leads to: {child_row['title']}.")
            item["preconditions"] = dedupe_strings((item.get("preconditions") or []) + parent_summaries)
            item["direct_consequences"] = dedupe_strings((item.get("direct_consequences") or []) + child_summaries)
        return rows
