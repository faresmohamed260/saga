"""Stable adapters that reuse existing repo components inside redesign_lab."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from core.pipeline_contract import (
    build_canon_snapshot,
    build_character_timelines,
    build_entity_registry,
    build_event_ledger,
    build_export_contract_payload,
    build_formal_character_profiles,
    build_state_result,
    build_story_index_summary,
    build_timeline,
    normalize_character_timelines,
)
from infrastructure.llm_client import LLMClient
from services.series_processor import SeriesProcessor


CONFIG_DIR = Path(__file__).parents[1] / "configs"


def load_json_config(name: str) -> Dict[str, Any]:
    return json.loads((CONFIG_DIR / name).read_text(encoding="utf-8"))


def load_acotar_books() -> Dict[str, Any]:
    return load_json_config("acotar_books.json")


def load_acotar_chapters(*, llm_mode: str = LLMClient.MODE_GPT_OSS, model_override: str = "") -> Dict[str, Any]:
    config = load_acotar_books()
    llm = LLMClient(mode=llm_mode, ollama_model_override=model_override, max_retries=1, base_delay=0.0, timeout=60)
    processor = SeriesProcessor(llm_client=llm)
    chapters = processor.process(deepcopy(config["books"]))
    return {
        "series_id": config["series_id"],
        "series_title": config["series_title"],
        "books": deepcopy(config["books"]),
        "chapters": chapters,
    }


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_redesign_contract(
    *,
    series_id: str,
    series_title: str,
    prepared_books: List[Dict[str, Any]],
    configuration: Dict[str, Any],
    scene_analyses: List[Dict[str, Any]],
    identity_result: Dict[str, Any],
    stable_character_states: List[Dict[str, Any]],
    causal_graph_result: Dict[str, Any],
    runtime: Dict[str, Any],
) -> Dict[str, Any]:
    entity_registry = build_entity_registry(scene_analyses)
    state_result = build_state_result(scene_analyses)
    timeline = build_timeline(scene_analyses)
    event_ledger = build_event_ledger(scene_analyses, timeline, causal_graph_result)
    character_timelines = normalize_character_timelines(build_character_timelines(timeline), identity_result)
    character_profiles = build_formal_character_profiles(
        character_timelines,
        entity_registry,
        state_result,
        identity_result,
        scene_analyses,
    )
    canon_snapshot = build_canon_snapshot(
        state_result,
        (
            scene_analyses[-1]["book_index"] if scene_analyses else 1,
            scene_analyses[-1]["chapter_index"] if scene_analyses else 1,
            scene_analyses[-1]["scene_index"] if scene_analyses else 1,
        ),
    )
    story_index_summary = build_story_index_summary(
        scene_analyses,
        timeline,
        event_ledger,
        character_timelines,
        character_profiles,
        entity_registry,
        canon_snapshot,
        state_result,
        identity_result,
        causal_graph_result,
    )
    return build_export_contract_payload(
        app_name="S.A.G.A. Redesign Lab",
        pipeline_status="Redesign pipeline completed.",
        configuration=configuration,
        inputs={
            "books": prepared_books,
            "series": {
                "series_id": series_id,
                "series_title": series_title,
                "book_index_base": 1,
            },
        },
        outputs={
            "chapters": [],
            "scene_analyses": scene_analyses,
            "resolved_scene_analyses": scene_analyses,
            "entity_registry": entity_registry,
            "state_result": state_result,
            "canon_snapshot": canon_snapshot,
            "timeline": timeline,
            "event_ledger": event_ledger,
            "character_timelines": character_timelines,
            "character_profiles": character_profiles,
            "stable_character_states": stable_character_states,
            "identity_result": identity_result,
            "causal_graph_result": causal_graph_result,
            "sequel_artifacts": {"context": {}, "blueprint": {}},
            "story_index_summary": story_index_summary,
        },
        runtime=runtime,
    )

