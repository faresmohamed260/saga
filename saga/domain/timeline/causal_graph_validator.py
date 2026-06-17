from typing import Dict, List, Set


class CausalGraphValidator:
    """
    Cleans LLM causal-graph output so only valid event references remain.
    """

    def validate(self, graph: Dict, valid_event_ids: Set[str]) -> Dict:
        events = []
        for event in graph.get("events", []):
            if not isinstance(event, dict):
                continue
            event_id = event.get("id")
            if event_id not in valid_event_ids:
                continue

            cleaned = {
                "id": event_id,
                "description": str(event.get("description", "")).strip(),
                "event_type": str(event.get("event_type", "ACTION")).strip().upper() or "ACTION",
                "story_impact": self._bounded_int(event.get("story_impact"), default=1),
                "reversibility": self._bounded_int(event.get("reversibility"), default=1),
                "caused_by": self._clean_links(event.get("caused_by", []), valid_event_ids),
                "causes": self._clean_links(event.get("causes", []), valid_event_ids),
                "prevents": self._clean_prevents(event.get("prevents", [])),
                "required_for": self._clean_required_for(event.get("required_for", []), valid_event_ids),
            }
            events.append(cleaned)

        present_event_ids = {event["id"] for event in events}
        return {
            "events": events,
            "critical_path": self._clean_critical_path(graph.get("critical_path", []), present_event_ids),
            "flexible_events": self._clean_flexible_events(graph.get("flexible_events", []), present_event_ids),
            "causal_chains": self._clean_chains(graph.get("causal_chains", []), present_event_ids),
            "divergence_points": self._clean_divergence_points(graph.get("divergence_points", []), present_event_ids),
        }

    def deduplicate(self, graph: Dict) -> Dict:
        deduped_events = []
        seen_event_ids = set()
        for event in graph.get("events", []):
            event_id = event.get("id")
            if not event_id or event_id in seen_event_ids:
                continue
            seen_event_ids.add(event_id)
            deduped_events.append(event)

        def dedupe_dict_items(items: List[Dict], key_fields: List[str]) -> List[Dict]:
            deduped = []
            seen = set()
            for item in items or []:
                key = tuple(item.get(field) for field in key_fields)
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(item)
            return deduped

        return {
            "events": deduped_events,
            "critical_path": dedupe_dict_items(graph.get("critical_path", []), ["event_id"]),
            "flexible_events": dedupe_dict_items(graph.get("flexible_events", []), ["event_id"]),
            "causal_chains": dedupe_dict_items(graph.get("causal_chains", []), ["chain_id"]),
            "divergence_points": dedupe_dict_items(graph.get("divergence_points", []), ["event_id"]),
            **({k: v for k, v in graph.items() if k not in {"events", "critical_path", "flexible_events", "causal_chains", "divergence_points"}}),
        }

    def _clean_links(self, links: List[Dict], valid_event_ids: Set[str]) -> List[Dict]:
        cleaned = []
        for item in links or []:
            if not isinstance(item, dict) or item.get("event_id") not in valid_event_ids:
                continue
            cleaned.append({
                "event_id": item["event_id"],
                "relationship": str(item.get("relationship", "")).strip().upper(),
                "explanation": str(item.get("explanation", "")).strip(),
            })
        return cleaned

    def _clean_prevents(self, prevents: List[Dict]) -> List[Dict]:
        cleaned = []
        for item in prevents or []:
            if not isinstance(item, dict):
                continue
            alternative = str(item.get("alternative", "")).strip()
            why_blocked = str(item.get("why_blocked", "")).strip()
            if not alternative and not why_blocked:
                continue
            cleaned.append({
                "alternative": alternative,
                "why_blocked": why_blocked,
            })
        return cleaned

    def _clean_required_for(self, required_for: List[Dict], valid_event_ids: Set[str]) -> List[Dict]:
        cleaned = []
        for item in required_for or []:
            if not isinstance(item, dict) or item.get("event_id") not in valid_event_ids:
                continue
            cleaned.append({
                "event_id": item["event_id"],
                "why_required": str(item.get("why_required", "")).strip(),
            })
        return cleaned

    def _clean_critical_path(self, critical_path: List[Dict], valid_event_ids: Set[str]) -> List[Dict]:
        cleaned = []
        for item in critical_path or []:
            if not isinstance(item, dict) or item.get("event_id") not in valid_event_ids:
                continue
            cleaned.append({
                "event_id": item["event_id"],
                "criticality_score": self._bounded_int(item.get("criticality_score"), default=1),
                "why_critical": str(item.get("why_critical", "")).strip(),
            })
        return cleaned

    def _clean_flexible_events(self, flexible_events: List[Dict], valid_event_ids: Set[str]) -> List[Dict]:
        cleaned = []
        for item in flexible_events or []:
            if not isinstance(item, dict) or item.get("event_id") not in valid_event_ids:
                continue
            cleaned.append({
                "event_id": item["event_id"],
                "flexibility_score": self._bounded_int(item.get("flexibility_score"), default=1),
                "why_flexible": str(item.get("why_flexible", "")).strip(),
            })
        return cleaned

    def _clean_chains(self, chains: List[Dict], valid_event_ids: Set[str]) -> List[Dict]:
        cleaned = []
        for item in chains or []:
            if not isinstance(item, dict):
                continue
            sequence = [event_id for event_id in item.get("event_sequence", []) if event_id in valid_event_ids]
            if not sequence:
                continue
            cleaned.append({
                "chain_id": str(item.get("chain_id", "")).strip() or f"chain_{len(cleaned) + 1}",
                "description": str(item.get("description", "")).strip(),
                "event_sequence": sequence,
                "chain_type": str(item.get("chain_type", "")).strip().upper(),
                "story_function": str(item.get("story_function", "")).strip(),
            })
        return cleaned

    def _clean_divergence_points(self, divergence_points: List[Dict], valid_event_ids: Set[str]) -> List[Dict]:
        cleaned = []
        for item in divergence_points or []:
            if not isinstance(item, dict) or item.get("event_id") not in valid_event_ids:
                continue
            alternatives = [str(option).strip() for option in item.get("alternatives", []) if str(option).strip()]
            cleaned.append({
                "event_id": item["event_id"],
                "decision_made": str(item.get("decision_made", "")).strip(),
                "alternatives": alternatives,
                "divergence_potential": self._bounded_int(item.get("divergence_potential"), default=1),
                "alternate_timeline": str(item.get("alternate_timeline", "")).strip(),
            })
        return cleaned

    def _bounded_int(self, value, default: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return max(1, min(10, parsed))
