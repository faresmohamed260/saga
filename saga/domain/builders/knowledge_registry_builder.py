"""Builds a deterministic knowledge registry from events and state changes."""

from __future__ import annotations

from typing import Dict, List

from saga.domain.normalization.helpers import stable_slug


class KnowledgeRegistryBuilder:
    """Extract deterministic knowledge-like beats from the event ledger."""

    VERB_MARKERS = ("learn", "discover", "realize", "reveal", "confide", "tell", "explain")
    KNOWLEDGE_CHANGE_TYPES = {"knowledge"}

    def build(
        self,
        *,
        event_ledger: List[Dict],
        scene_analyses: List[Dict],
        state_result: Dict,
    ) -> Dict:
        items: List[Dict] = []
        event_lookup = {
            (item.get("book_index"), item.get("chapter_index"), item.get("scene_index")): item
            for item in event_ledger
        }
        for event in event_ledger:
            summary = (event.get("summary") or "").strip()
            lowered = summary.lower()
            if not any(marker in lowered for marker in self.VERB_MARKERS):
                continue
            participants = event.get("participants") or []
            subject = participants[0] if participants else "unknown"
            items.append({
                "knowledge_id": stable_slug("know", f"{event.get('ledger_event_id', '')}:{subject}"),
                "subject": subject,
                "knowledge_item": summary,
                "acquired_at_event": event.get("ledger_event_id", ""),
                "confidence": "deterministic_heuristic",
                "source_event": event.get("ledger_event_id", ""),
            })
        for scene in scene_analyses:
            anchor_event = event_lookup.get((scene.get("book_index"), scene.get("chapter_index"), scene.get("scene_index")))
            anchor_id = (anchor_event or {}).get("ledger_event_id", "")
            for change in scene.get("state_changes") or []:
                if (change.get("change_type") or "").strip().lower() not in self.KNOWLEDGE_CHANGE_TYPES:
                    continue
                subject = (change.get("entity_name") or "").strip() or "unknown"
                knowledge_item = " ".join(
                    filter(
                        None,
                        [
                            (change.get("attribute") or "").strip(),
                            (change.get("new_state") or "").strip(),
                            (change.get("evidence") or "").strip(),
                        ],
                    )
                )
                if not knowledge_item:
                    continue
                items.append({
                    "knowledge_id": stable_slug("know", f"{anchor_id}:{subject}:{knowledge_item}"),
                    "subject": subject,
                    "knowledge_item": knowledge_item,
                    "acquired_at_event": anchor_id,
                    "confidence": "state_change",
                    "source_event": anchor_id,
                })
        for change in state_result.get("transitions") or []:
            if (change.get("change_type") or "").strip().lower() not in self.KNOWLEDGE_CHANGE_TYPES:
                continue
            source_event = event_lookup.get((change.get("book_index"), change.get("chapter_index"), change.get("scene_index")))
            anchor_id = (source_event or {}).get("ledger_event_id", "")
            subject = (change.get("entity_name") or "").strip() or "unknown"
            knowledge_item = " ".join(
                filter(
                    None,
                    [
                        (change.get("attribute") or "").strip(),
                        (change.get("new_state") or "").strip(),
                        (change.get("evidence") or "").strip(),
                    ]
                )
            )
            if not knowledge_item:
                continue
            items.append({
                "knowledge_id": stable_slug("know", f"{anchor_id}:{subject}:{knowledge_item}"),
                "subject": subject,
                "knowledge_item": knowledge_item,
                "acquired_at_event": anchor_id,
                "confidence": "state_transition",
                "source_event": anchor_id,
            })
        deduped = {}
        for item in items:
            deduped[item["knowledge_id"]] = item
        return {"items": sorted(deduped.values(), key=lambda item: item["knowledge_id"])}
