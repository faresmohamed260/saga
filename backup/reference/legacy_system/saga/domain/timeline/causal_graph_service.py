"""Batched causal graph construction over the normalized event saga.domain.timeline."""

import logging
from typing import Dict, List, Optional

from packages.reasoning_runtime.contracts import ReasoningClient
from saga.providers.reasoning_runtime_adapter import MODE_GENERAL_COMPUTE, MODE_GPT_OSS, create_runtime_client
from saga.prompts.causal_graph_prompt import causal_graph_prompt
from saga.domain.timeline.causal_graph_metrics import CausalGraphMetrics
from saga.domain.timeline.causal_graph_validator import CausalGraphValidator


class CausalGraphService:
    """
    Builds a validated causal graph from the current timeline and scene summaries.
    """

    def __init__(
        self,
        llm_client: Optional[ReasoningClient] = None,
        max_attempts: int = 2,
        batch_size: int = 20,
    ):
        self.llm = llm_client or create_runtime_client()
        self.max_attempts = max_attempts
        self.batch_size = max(10, int(batch_size))
        self.validator = CausalGraphValidator()
        self.metrics = CausalGraphMetrics()

    def build(self, timeline: List[Dict], scene_analyses: List[Dict]) -> Dict:
        event_catalog = self._event_catalog(timeline)
        logging.info("Causal graph catalog prepared | events=%s | batch_size=%s", len(event_catalog), self.batch_size)
        if not event_catalog:
            empty_graph = {
                "events": [],
                "critical_path": [],
                "flexible_events": [],
                "causal_chains": [],
                "divergence_points": [],
            }
            return {"graph": empty_graph, "metrics": self.metrics.compute(empty_graph)}

        scene_lookup = {
            (scene.get("book_index"), scene.get("chapter_index"), scene.get("scene_index")): scene
            for scene in scene_analyses
        }
        id_to_event = {item["graph_id"]: item for item in event_catalog}
        merged_graph = {
            "events": [],
            "critical_path": [],
            "flexible_events": [],
            "causal_chains": [],
            "divergence_points": [],
        }
        batch_errors: List[str] = []

        batches = self._batched_events(event_catalog)
        batch_total = len(batches)

        for batch_index, batch in enumerate(batches, start=1):
            logging.info(
                "Causal batch started | batch=%s/%s | events=%s | range=%s-%s",
                batch_index,
                batch_total,
                len(batch),
                batch[0]["graph_id"],
                batch[-1]["graph_id"],
            )
            character_lines = self._character_lines(batch, scene_lookup)
            state_lines = self._state_lines(batch, scene_lookup)
            relationship_lines = self._relationship_lines(batch, scene_lookup)
            prompt = causal_graph_prompt(
                self._event_lines(batch),
                self._scene_lines(batch, scene_lookup),
                character_lines,
                state_lines,
                relationship_lines,
            )
            logging.info(
                "Causal batch context | batch=%s | characters=%s | state_changes=%s | relationship_changes=%s",
                batch_index,
                len(character_lines),
                len(state_lines),
                len(relationship_lines),
            )
            last_response = None
            validated = None

            for _attempt in range(1, self.max_attempts + 1):
                response = self.llm.generate_json(prompt, strict=True, validator=self._validate_shape)
                last_response = response
                if "error" in response:
                    continue
                valid_event_ids = {item["graph_id"] for item in batch}
                validated = self.validator.validate(response, valid_event_ids)
                break

            if not validated:
                if isinstance(last_response, dict):
                    logging.warning(
                        "Causal batch failed | batch=%s | error=%s | last_error=%s",
                        batch_index,
                        last_response.get("error", "unknown_error"),
                        last_response.get("last_error", ""),
                    )
                    batch_errors.append(
                        f"batch_{batch_index}: {last_response.get('error', 'unknown_error')} | {last_response.get('last_error', '')}"
                    )
                else:
                    logging.warning("Causal batch failed | batch=%s | error=unknown_error", batch_index)
                    batch_errors.append(f"batch_{batch_index}: unknown_error")
                continue

            for event in validated.get("events", []):
                source = id_to_event.get(event["id"])
                if not source:
                    continue
                event["time_index"] = source["time_index"]
                event["book_index"] = source["book_index"]
                event["chapter_index"] = source["chapter_index"]
                event["scene_index"] = source["scene_index"]
                event["characters"] = list(source["characters"])
                event["source_summary"] = source["summary"]

            merged_graph["events"].extend(validated.get("events", []))
            merged_graph["critical_path"].extend(validated.get("critical_path", []))
            merged_graph["flexible_events"].extend(validated.get("flexible_events", []))
            merged_graph["causal_chains"].extend(validated.get("causal_chains", []))
            merged_graph["divergence_points"].extend(validated.get("divergence_points", []))
            logging.info(
                "Causal batch completed | batch=%s | events=%s | links=%s",
                batch_index,
                len(validated.get("events", [])),
                sum(len(event.get("causes", [])) + len(event.get("caused_by", [])) for event in validated.get("events", [])),
            )

        merged_graph = self.validator.deduplicate(merged_graph)

        if not merged_graph["events"] and batch_errors:
            merged_graph["error"] = "batch_generation_failed"
            merged_graph["last_error"] = "; ".join(batch_errors[:3])

        result = {
            "graph": merged_graph,
            "metrics": self.metrics.compute(merged_graph),
        }
        if batch_errors and merged_graph["events"]:
            result["graph"]["warning"] = f"Some causal batches failed: {len(batch_errors)}"
            result["graph"]["last_error"] = "; ".join(batch_errors[:3])
        return result

    def _event_catalog(self, timeline: List[Dict]) -> List[Dict]:
        return [
            {
                "graph_id": f"t_{item['time_index']}",
                "time_index": item.get("time_index"),
                "book_index": item.get("book_index"),
                "chapter_index": item.get("chapter_index"),
                "scene_index": item.get("scene_index"),
                "event_id": item.get("event_id"),
                "summary": item.get("summary", ""),
                "characters": item.get("characters", []),
            }
            for item in timeline
            if item.get("time_index") is not None and item.get("summary")
        ]

    def _validate_shape(self, response: Dict) -> bool:
        return (
            isinstance(response, dict)
            and isinstance(response.get("events"), list)
            and isinstance(response.get("critical_path"), list)
            and isinstance(response.get("flexible_events"), list)
            and isinstance(response.get("causal_chains"), list)
            and isinstance(response.get("divergence_points"), list)
        )

    def _batched_events(self, event_catalog: List[Dict]) -> List[List[Dict]]:
        return [
            event_catalog[index:index + self.batch_size]
            for index in range(0, len(event_catalog), self.batch_size)
        ]

    def _event_lines(self, items: List[Dict]) -> List[str]:
        return [
            (
                f"{item['graph_id']} | time={item['time_index']} | "
                f"book={item['book_index']} chapter={item['chapter_index']} scene={item['scene_index']} | "
                f"characters={', '.join(item['characters']) or 'None'} | "
                f"summary={item['summary']}"
            )
            for item in items
        ]

    def _scene_lines(self, items: List[Dict], scene_lookup: Dict) -> List[str]:
        lines = []
        for item in items:
            key = (item["book_index"], item["chapter_index"], item["scene_index"])
            scene = scene_lookup.get(key, {})
            lines.append(f"{item['graph_id']} -> scene_summary={scene.get('scene_summary', '')}")
        return lines

    def _character_lines(self, items: List[Dict], scene_lookup: Dict) -> List[str]:
        seen = set()
        lines = []
        for item in items:
            key = (item["book_index"], item["chapter_index"], item["scene_index"])
            scene = scene_lookup.get(key, {})
            for character in scene.get("canonical_characters", []) or []:
                name = str(character.get("name", "")).strip()
                if not name or name in seen:
                    continue
                seen.add(name)
                aliases = ", ".join(character.get("names_used", []) or []) or "None"
                role = str(character.get("role", "")).strip() or "unspecified"
                lines.append(f"{name} | role={role} | names_used={aliases}")
        return lines

    def _state_lines(self, items: List[Dict], scene_lookup: Dict) -> List[str]:
        lines = []
        for item in items:
            key = (item["book_index"], item["chapter_index"], item["scene_index"])
            scene = scene_lookup.get(key, {})
            for change in scene.get("state_changes", []) or []:
                entity_name = str(change.get("entity_name", "")).strip()
                attribute = str(change.get("attribute", "")).strip()
                new_state = str(change.get("new_state", "")).strip()
                if not entity_name or not attribute:
                    continue
                lines.append(
                    f"{item['graph_id']} | {entity_name} | {attribute} -> {new_state or 'unknown'}"
                )
        return lines

    def _relationship_lines(self, items: List[Dict], scene_lookup: Dict) -> List[str]:
        lines = []
        for item in items:
            key = (item["book_index"], item["chapter_index"], item["scene_index"])
            scene = scene_lookup.get(key, {})
            for change in scene.get("relationship_changes", []) or []:
                source = str(change.get("source", "")).strip()
                target = str(change.get("target", "")).strip()
                relation_type = str(change.get("relationship_type", "")).strip()
                summary = str(change.get("summary", "")).strip()
                if not source or not target:
                    continue
                lines.append(
                    f"{item['graph_id']} | {source} -> {target} | type={relation_type or 'unknown'} | {summary}"
                )
        return lines

