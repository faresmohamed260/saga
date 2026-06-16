"""Main Streamlit dashboard for S.A.G.A.

This app is the primary product surface for ingesting books, running the
analysis pipeline, browsing outputs, and exporting the JSON contract.
"""

import json
import math
import logging
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple
import streamlit as st

from analysis.scene_analysis_orchestrator import SceneAnalysisOrchestrator
from analysis.scene_extractor import SceneExtractor
from core.pipeline_contract import (
    apply_identity_updates as contract_apply_identity_updates,
    build_scene_context as contract_build_scene_context,
    canonical_lookup as contract_canonical_lookup,
    canonicalize_name as contract_canonicalize_name,
    is_forbidden_identity as contract_is_forbidden_identity,
    looks_like_proper_name as contract_looks_like_proper_name,
    normalize_identity_key as contract_normalize_identity_key,
    provider_canonicalize_name as contract_provider_canonicalize_name,
    provider_identity_locked as contract_provider_identity_locked,
    rebuild_resolved_scene_analyses as contract_rebuild_resolved_scene_analyses,
    resolve_existing_canonical_name as contract_resolve_existing_canonical_name,
    resolve_scene_analysis as contract_resolve_scene_analysis,
    sanitize_alias_map as contract_sanitize_alias_map,
)
from entities.character_profile_service import CharacterProfileService
from entities.entity_registry_service import EntityRegistryService
from infrastructure.llm_client import LLMClient
from query.story_query_service import StoryQueryService
from rag.story_index_service import StoryIndexService
from redesign_lab.identity.identity_provider import (
    DEFAULT_BOOKNLP_PIPELINE_IDENTITY_JSON,
    resolve_identity_provider_input,
)
from services.narrative_generation_service import NarrativeGenerationService
from services.series_processor import SeriesProcessor
from services.dashboard_artifact_service import (
    build_contract_summary,
    discover_contract_files,
    discover_encode_runs,
    discover_identity_files,
    discover_prompt_pack_files,
    discover_report_files,
    discover_retrieval_context_files,
    discover_state_snapshot_files,
    discover_visual_world_state_files,
    read_json_file,
    read_text_file,
)
from state.canon_state_service import CanonStateService
from state.state_transition_service import StateTransitionService
from timeline.character_normalizer import CharacterNormalizer
from timeline.character_timeline_service import CharacterTimelineService
from timeline.causal_graph_service import CausalGraphService
from timeline.event_ledger_service import EventLedgerService
from timeline.timeline_service import TimelineService


UPLOAD_DIR = Path(r"B:\Documents\PyCharm\graduationProject\uploads")
DEFAULT_SCENE_TARGET_WORDS = 0
SCENE_FALLBACK_TARGETS = [2400, 1800, 1400, 1100, 900, 700, 500, 350, 250]
MODEL_OPTIONS = ["gpt_oss", "general_compute", "codex", "mistral", "gemini"]
LIVE_RENDER_INTERVAL_SECONDS = 2.0
EXPORT_CONTRACT_VERSION = "1.0.0"
FORBIDDEN_IDENTITY_LABELS = {
    "i",
    "me",
    "my",
    "myself",
    "he",
    "she",
    "they",
    "them",
    "him",
    "her",
    "his",
    "hers",
    "their",
    "theirs",
    "it",
    "its",
    "narrator",
    "protagonist",
    "person",
    "character",
}
GENERIC_ALIAS_LABELS = {"man", "woman", "boy", "girl", "person", "figure", "voice"}
MOCK_NEO4J_COUNTS = {
    "Book": 5,
    "Chapter": 249,
    "Scene": 249,
    "Character": 46,
    "Event": 1244,
    "Location": 95,
    "Entity": 237,
    "Relationship": 312,
}
MOCK_CONFIG_PRESETS = [
    {
        "name": "Full ACOTAR BookNLP Clean",
        "analysis_model": "gpt_oss",
        "identity_provider": "booknlp_clean",
        "provider_mode": "same_provider_rotating",
        "scene_failure_policy": "fail_fast",
    },
    {
        "name": "Fast Smoke Validation",
        "analysis_model": "mistral",
        "identity_provider": "booknlp_clean",
        "provider_mode": "single_provider",
        "scene_failure_policy": "tolerate_with_report",
    },
]

st.set_page_config(page_title="S.A.G.A.", layout="wide")

if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
else:
    logging.getLogger().setLevel(logging.INFO)


def inject_dashboard_styles():
    st.markdown(
        """
        <style>
        div[data-baseweb="tab-list"] {
            gap: 0.3rem;
        }
        div[data-baseweb="tab"] {
            padding-top: 0.55rem;
            padding-bottom: 0.55rem;
            font-weight: 600;
        }
        .saga-panel {
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 14px;
            padding: 1rem 1rem 0.75rem 1rem;
            background: rgba(255,255,255,0.02);
            margin-bottom: 1rem;
        }
        .saga-panel h4 {
            margin: 0 0 0.35rem 0;
            font-size: 1rem;
        }
        .saga-panel p {
            margin: 0;
            color: rgba(250,250,250,0.78);
            font-size: 0.93rem;
        }
        .saga-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin: 0.5rem 0 1rem 0;
        }
        .saga-chip {
            display: inline-block;
            padding: 0.2rem 0.55rem;
            border-radius: 999px;
            background: rgba(255,255,255,0.06);
            color: rgba(250,250,250,0.92);
            font-size: 0.82rem;
            border: 1px solid rgba(255,255,255,0.08);
        }
        .saga-chip-warn {
            background: rgba(255,177,66,0.12);
            border-color: rgba(255,177,66,0.3);
            color: #ffd08a;
        }
        .saga-chip-risk {
            background: rgba(255,99,99,0.12);
            border-color: rgba(255,99,99,0.3);
            color: #ff9c9c;
        }
        .saga-chip-good {
            background: rgba(70,201,125,0.12);
            border-color: rgba(70,201,125,0.28);
            color: #99edb3;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state():
    defaults = {
        "book_inputs": [],
        "chapters": [],
        "scene_analyses": [],
        "resolved_scene_analyses": [],
        "entity_registry": [],
        "state_result": {"transitions": [], "latest_state": []},
        "canon_snapshot": [],
        "timeline": [],
        "event_ledger": [],
        "character_timelines": [],
        "character_profiles": [],
        "identity_result": {"alias_map": {}, "rejected_non_characters": [], "decisions": [], "alias_history": []},
        "story_index_result": None,
        "causal_graph_result": {"graph": {"events": [], "critical_path": [], "flexible_events": [], "causal_chains": [], "divergence_points": []}, "metrics": {}},
        "analysis_model": "gpt_oss",
        "identity_model": "gpt_oss",
        "identity_provider": "booknlp_clean",
        "identity_json_path": str(DEFAULT_BOOKNLP_PIPELINE_IDENTITY_JSON),
        "analysis_mode": "structured",
        "sequel_model": NarrativeGenerationService.DEFAULT_NARRATIVE_MODEL_MODE,
        "sequel_prompt": "Focus on the strongest unresolved emotional arc while preserving canon consequences.",
        "sequel_chapter_count": 25,
        "sequel_canon_position": "post_canon",
        "sequel_new_plot": "",
        "sequel_relationship_target_count": 0,
        "sequel_continuity_anchor": "",
        "sequel_anchor_after_label": "",
        "sequel_anchor_before_label": "",
        "sequel_divergence_anchor_label": "",
        "sequel_preserve_event_labels": [],
        "target_scene_words": DEFAULT_SCENE_TARGET_WORDS,
        "book_order_rows": [],
        "pipeline_running": False,
        "latest_status": "Idle",
        "latest_scene_summary": "",
        "current_scene_ref": None,
        "processed_scene_count": 0,
        "estimated_total_scenes": 0,
        "run_started_at": 0.0,
        "elapsed_seconds": 0.0,
        "last_scene_seconds": 0.0,
        "avg_scene_seconds": 0.0,
        "last_live_render_at": 0.0,
        "post_run_refresh_pending": False,
        "sequel_context_result": None,
        "sequel_blueprint_result": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def reset_pipeline_outputs():
    st.session_state["chapters"] = []
    st.session_state["scene_analyses"] = []
    st.session_state["resolved_scene_analyses"] = []
    st.session_state["entity_registry"] = []
    st.session_state["state_result"] = {"transitions": [], "latest_state": []}
    st.session_state["canon_snapshot"] = []
    st.session_state["timeline"] = []
    st.session_state["event_ledger"] = []
    st.session_state["character_timelines"] = []
    st.session_state["character_profiles"] = []
    st.session_state["identity_result"] = {"alias_map": {}, "rejected_non_characters": [], "decisions": [], "alias_history": []}
    st.session_state["story_index_result"] = None
    st.session_state["causal_graph_result"] = {"graph": {"events": [], "critical_path": [], "flexible_events": [], "causal_chains": [], "divergence_points": []}, "metrics": {}}
    st.session_state["pipeline_running"] = False
    st.session_state["latest_status"] = "Idle"
    st.session_state["latest_scene_summary"] = ""
    st.session_state["current_scene_ref"] = None
    st.session_state["processed_scene_count"] = 0
    st.session_state["estimated_total_scenes"] = 0
    st.session_state["run_started_at"] = 0.0
    st.session_state["elapsed_seconds"] = 0.0
    st.session_state["last_scene_seconds"] = 0.0
    st.session_state["avg_scene_seconds"] = 0.0
    st.session_state["last_live_render_at"] = 0.0
    st.session_state["post_run_refresh_pending"] = False
    st.session_state["sequel_context_result"] = None
    st.session_state["sequel_blueprint_result"] = None


def save_uploaded_books(uploaded_files) -> List[Dict]:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved = []
    for uploaded in uploaded_files:
        destination = UPLOAD_DIR / uploaded.name
        destination.write_bytes(uploaded.getbuffer())
        suffix = destination.suffix.lower()
        if suffix not in {".epub", ".pdf"}:
            continue
        saved.append({
            "path": str(destination),
            "type": suffix.lstrip("."),
            "title": uploaded.name,
        })
    return saved


def resolve_book_inputs() -> List[Dict]:
    edited_rows = st.session_state.get("book_order_rows") or []
    if edited_rows:
        ordered = sorted(edited_rows, key=lambda row: int(row["order"]))
        return [
            {"path": row["path"], "type": row["type"], "title": row["title"]}
            for row in ordered
        ]
    return []


def paged_items(items: List[Dict], key_prefix: str, page_size: int = 10) -> List[Dict]:
    if not items:
        return []

    total_pages = max(1, math.ceil(len(items) / page_size))
    page = st.number_input(
        f"{key_prefix} page",
        min_value=1,
        max_value=total_pages,
        value=1,
        step=1,
        key=f"{key_prefix}_page",
    )
    start = (page - 1) * page_size
    end = start + page_size
    st.caption(f"Showing {start + 1}-{min(end, len(items))} of {len(items)}")
    return items[start:end]


def build_chapters(book_inputs: List[Dict], model_mode: str) -> List[Dict]:
    logging.info("Chapter build started | books=%s | model=%s", len(book_inputs), model_mode)
    processor = SeriesProcessor(
        llm_client=LLMClient(
            mode=model_mode,
            max_retries=1,
            base_delay=0.0,
        )
    )
    chapters = processor.process(book_inputs)
    logging.info("Chapter build completed | chapters=%s", len(chapters))
    return chapters


def run_identity_resolution(book_inputs: List[Dict]) -> Dict:
    """Run identity resolution over all selected books."""
    provider = resolve_identity_provider_input(
        provider_mode="booknlp_clean",
        input_json=st.session_state.get("identity_json_path") or None,
    )
    return provider.build_identity_result_compat()


def format_duration(seconds: float) -> str:
    total_seconds = max(0, int(round(float(seconds or 0.0))))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def safe_avg(values: List[float]) -> float:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return 0.0
    return sum(clean) / len(clean)


def render_panel(title: str, body: str):
    st.markdown(
        f"""
        <div class="saga-panel">
            <h4>{title}</h4>
            <p>{body}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_chip_row(items: List[Tuple[str, str]]):
    if not items:
        return
    chips = []
    for label, tone in items:
        css_class = "saga-chip"
        if tone == "warn":
            css_class += " saga-chip-warn"
        elif tone == "risk":
            css_class += " saga-chip-risk"
        elif tone == "good":
            css_class += " saga-chip-good"
        chips.append(f'<span class="{css_class}">{label}</span>')
    st.markdown(f'<div class="saga-chip-row">{"".join(chips)}</div>', unsafe_allow_html=True)


def summarize_scene_flags(scene: Dict) -> List[Tuple[str, str]]:
    flags: List[Tuple[str, str]] = []
    if scene.get("error"):
        flags.append((f"Error: {scene.get('error')}", "risk"))
    if scene.get("fallback_targets") and len(scene.get("fallback_targets") or []) > 1:
        flags.append(("Fallback split", "warn"))
    if scene.get("comparison_results"):
        flags.append(("Compare mode", "good"))
    if not (scene.get("canonical_characters") or []):
        flags.append(("No canonicals", "warn"))
    if not (scene.get("events") or []):
        flags.append(("No events", "warn"))
    if scene.get("rejected_identity_candidates"):
        flags.append((f"Rejected: {len(scene.get('rejected_identity_candidates') or [])}", "warn"))
    return flags


def scene_summary_rows(scene_analyses: List[Dict]) -> List[Dict]:
    rows = []
    for scene in scene_analyses:
        chapter_label = str(scene.get("chapter_index"))
        if scene.get("end_chapter_index") and scene.get("end_chapter_index") != scene.get("chapter_index"):
            chapter_label = f"{scene.get('chapter_index')}-{scene.get('end_chapter_index')}"
        rows.append({
            "book": scene.get("book_index"),
            "chapter": chapter_label,
            "scene": scene.get("scene_index"),
            "summary": scene.get("scene_summary") or "",
            "canonicals": len(scene.get("canonical_characters") or []),
            "events": len(scene.get("events") or []),
            "state_changes": len(scene.get("state_changes") or []),
            "relationship_changes": len(scene.get("relationship_changes") or []),
            "issues": ", ".join(label for label, _ in summarize_scene_flags(scene)),
        })
    return rows


def build_run_health_summary() -> Dict:
    scenes = st.session_state.get("scene_analyses") or []
    timeline = st.session_state.get("timeline") or []
    identity = st.session_state.get("identity_result") or {}
    causal = st.session_state.get("causal_graph_result") or {}
    graph = causal.get("graph") or {}
    return {
        "scene_errors": sum(1 for item in scenes if item.get("error")),
        "fallback_scenes": sum(1 for item in scenes if len(item.get("fallback_targets") or []) > 1),
        "avg_events_per_scene": round(safe_avg([len(item.get("events") or []) for item in scenes]), 2),
        "avg_characters_per_scene": round(safe_avg([len(item.get("canonical_characters") or []) for item in scenes]), 2),
        "aliases": len(identity.get("alias_map") or {}),
        "rejections": len(identity.get("rejected_non_characters") or []),
        "timeline_rows": len(timeline),
        "causal_events": len(graph.get("events") or []),
        "causal_warning": graph.get("warning") or graph.get("error") or "",
        "compare_scenes": sum(1 for item in scenes if item.get("comparison_results")),
        "tool_calls_seen": sum(((item.get("tool_runtime") or {}).get("content") or {}).get("tool_calls_seen", 0) + ((item.get("tool_runtime") or {}).get("identity") or {}).get("tool_calls_seen", 0) for item in scenes),
        "tool_calls_ignored": sum(((item.get("tool_runtime") or {}).get("content") or {}).get("tool_calls_ignored", 0) + ((item.get("tool_runtime") or {}).get("identity") or {}).get("tool_calls_ignored", 0) for item in scenes),
    }


def summarize_compare_mode(scene_analyses: List[Dict]) -> Dict:
    scenes = [item for item in scene_analyses if item.get("comparison_results")]
    if not scenes:
        return {"scene_count": 0}
    tool_only_events = 0
    structured_only_events = 0
    tool_only_characters = 0
    structured_only_characters = 0
    for scene in scenes:
        summary = build_comparison_summary(scene)
        tool_only_events += len(summary["tool_only_events"])
        structured_only_events += len(summary["structured_only_events"])
        tool_only_characters += len(summary["tool_only_characters"])
        structured_only_characters += len(summary["structured_only_characters"])
    return {
        "scene_count": len(scenes),
        "tool_only_events": tool_only_events,
        "structured_only_events": structured_only_events,
        "tool_only_characters": tool_only_characters,
        "structured_only_characters": structured_only_characters,
    }


def build_character_profiles(
    character_timelines: List[Dict],
    entity_registry: List[Dict],
    state_result: Dict,
    identity_result: Dict,
    scene_analyses: List[Dict] | None = None,
) -> List[Dict]:
    formal_profiles = st.session_state.get("character_profiles") or []
    if formal_profiles:
        return formal_profiles
    registry_by_name = {
        (item.get("name") or "").strip().lower(): item
        for item in entity_registry
        if item.get("entity_type") == "character"
    }
    latest_state_by_name = {
        (item.get("entity_name") or "").strip().lower(): item
        for item in (state_result.get("latest_state") or [])
        if item.get("entity_type") == "character"
    }
    alias_map = identity_result.get("alias_map") or {}
    decisions = identity_result.get("decisions") or []
    profiles = []

    for item in character_timelines:
        character = (item.get("character") or "").strip()
        if not character:
            continue
        normalized = character.lower()
        registry_entry = registry_by_name.get(normalized) or {}
        latest_state = latest_state_by_name.get(normalized, {})
        aliases = alias_map.get(character, [character])
        descriptions = registry_entry.get("descriptions") or []
        state_changes = registry_entry.get("state_changes") or []
        decision_rows = [
            decision
            for decision in decisions
            if (decision.get("canonical_name") or "").strip().lower() == normalized
            or (decision.get("character") or "").strip().lower() == normalized
        ]
        recent_events = sorted(item.get("events") or [], key=lambda event: event.get("time_index", 0), reverse=True)
        profiles.append({
            "character": character,
            "aliases": aliases,
            "event_count": len(item.get("events") or []),
            "events": item.get("events") or [],
            "recent_events": recent_events[:8],
            "first_seen": registry_entry.get("first_seen") or ((item.get("events") or [{}])[0] if item.get("events") else {}),
            "latest_state": latest_state.get("attributes") or {},
            "descriptions": descriptions[:10],
            "state_changes": state_changes[:12],
            "decision_count": len(decision_rows),
            "decisions": decision_rows[:12],
            "mention_count": registry_entry.get("mention_count", 0),
        })

    return sorted(profiles, key=lambda profile: (-profile["event_count"], profile["character"].lower()))


def render_all_throttled(
    container: st.delta_generator.DeltaGenerator,
    compact: bool,
    force: bool = False,
):
    now = time.perf_counter()
    last_render_at = float(st.session_state.get("last_live_render_at") or 0.0)
    if force or (now - last_render_at) >= LIVE_RENDER_INTERVAL_SECONDS:
        render_all(container, compact=compact)
        st.session_state["last_live_render_at"] = now


def normalize_identity_key(name: str) -> str:
    return contract_normalize_identity_key(name)


def article_insensitive_key(name: str) -> str:
    normalized = normalize_identity_key(name)
    for prefix in ("the ", "a ", "an "):
        if normalized.startswith(prefix):
            return normalized[len(prefix):]
    return normalized


def is_forbidden_identity(name: str) -> bool:
    return contract_is_forbidden_identity(name)


def is_generic_alias(name: str) -> bool:
    return normalize_identity_key(name) in GENERIC_ALIAS_LABELS


def looks_like_proper_name(name: str) -> bool:
    return contract_looks_like_proper_name(name)


def canonical_lookup(alias_map: Dict[str, List[str]]) -> Dict[str, str]:
    return contract_canonical_lookup(alias_map)


def resolve_existing_canonical_name(name: str, alias_map: Dict[str, List[str]]) -> str:
    return contract_resolve_existing_canonical_name(name, alias_map)


def sanitize_alias_map(alias_map: Dict[str, List[str]]) -> Dict[str, List[str]]:
    return contract_sanitize_alias_map(alias_map)


def canonicalize_name(name: str, alias_map: Dict[str, List[str]], rejected: List[str]) -> str:
    return contract_canonicalize_name(name, alias_map, rejected)


def provider_identity_locked(identity_result: Dict) -> bool:
    return contract_provider_identity_locked(identity_result)


def provider_canonicalize_name(name: str, alias_map: Dict[str, List[str]], rejected: List[str]) -> str:
    return contract_provider_canonicalize_name(name, alias_map, rejected)


def build_scene_context(scene_text: str, resolved_scene_analyses: List[Dict], state_result: Dict, identity_result: Dict, window: int = 6) -> str:
    return contract_build_scene_context(scene_text, resolved_scene_analyses, state_result, identity_result, window=window)


def resolve_scene_analysis(scene_analysis: Dict, identity_result: Dict) -> Dict:
    return contract_resolve_scene_analysis(scene_analysis, identity_result)


def rebuild_resolved_scene_analyses(scene_analyses: List[Dict], identity_result: Dict) -> List[Dict]:
    return contract_rebuild_resolved_scene_analyses(scene_analyses, identity_result)


def apply_identity_updates(scene_analysis: Dict, alias_result: Dict):
    contract_apply_identity_updates(scene_analysis, alias_result)


def build_entity_registry(scene_analyses: List[Dict]) -> List[Dict]:
    return EntityRegistryService().build(scene_analyses)


def build_state_result(scene_analyses: List[Dict]) -> Dict:
    return StateTransitionService().build(scene_analyses)


def build_canon_snapshot(state_result: Dict, scene_ref: Tuple[int, int, int]) -> List[Dict]:
    return CanonStateService().snapshot_at(state_result.get("transitions", []), scene_ref=scene_ref)


def build_timeline(scene_analyses: List[Dict]) -> List[Dict]:
    return TimelineService().build_from_scene_analyses(scene_analyses)


def build_event_ledger(scene_analyses: List[Dict], timeline: List[Dict], causal_graph_result: Dict) -> List[Dict]:
    return EventLedgerService().build(scene_analyses, timeline, causal_graph_result)


def build_character_timelines(timeline: List[Dict]) -> List[Dict]:
    return CharacterTimelineService().build(timeline)


def build_formal_character_profiles(
    character_timelines: List[Dict],
    entity_registry: List[Dict],
    state_result: Dict,
    identity_result: Dict,
    scene_analyses: List[Dict],
) -> List[Dict]:
    return CharacterProfileService().build(character_timelines, entity_registry, state_result, identity_result, scene_analyses)


def normalize_character_timelines(character_timelines: List[Dict], identity_result: Dict) -> List[Dict]:
    normalized = CharacterNormalizer().normalize(character_timelines)
    if provider_identity_locked(identity_result):
        return normalized.get("character_timelines", character_timelines)
    existing_alias_map = identity_result.setdefault("alias_map", {})

    for canonical_name, aliases in normalized.get("alias_map", {}).items():
        merged = set(existing_alias_map.get(canonical_name, []))
        merged.update(aliases)
        merged.add(canonical_name)
        existing_alias_map[canonical_name] = sorted(merged, key=str.lower)

    identity_result["alias_map"] = sanitize_alias_map(existing_alias_map)
    return normalized.get("character_timelines", character_timelines)


def build_story_index(
    scene_analyses: List[Dict],
    timeline: List[Dict],
    event_ledger: List[Dict],
    character_timelines: List[Dict],
    character_profiles: List[Dict],
    entity_registry: List[Dict],
    canon_snapshot: List[Dict],
    state_result: Dict,
    identity_result: Dict,
) -> Dict:
    service = StoryIndexService()
    result = service.build(
        scene_analyses=scene_analyses,
        timeline=timeline,
        event_ledger=event_ledger,
        character_timelines=character_timelines,
        character_profiles=character_profiles,
        entity_registry=entity_registry,
        canon_snapshot=canon_snapshot,
        state_result=state_result,
        identity_result=identity_result,
        causal_graph_result=st.session_state.get("causal_graph_result") or {},
    )
    return {"service": service, "query_service": StoryQueryService(), **result}


def build_export_contract() -> Dict:
    story_index_result = st.session_state.get("story_index_result") or {}
    causal_graph_result = st.session_state.get("causal_graph_result") or {}

    return {
        "contract_version": EXPORT_CONTRACT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "app": {
            "name": "S.A.G.A.",
            "pipeline_status": st.session_state.get("latest_status", "Idle"),
        },
        "configuration": {
            "analysis_model": st.session_state.get("analysis_model"),
            "identity_model": st.session_state.get("identity_model"),
            "analysis_mode": st.session_state.get("analysis_mode"),
            "sequel_model": st.session_state.get("sequel_model"),
            "sequel_prompt": st.session_state.get("sequel_prompt"),
            "sequel_chapter_count": st.session_state.get("sequel_chapter_count"),
            "sequel_canon_position": st.session_state.get("sequel_canon_position"),
            "sequel_new_plot": st.session_state.get("sequel_new_plot"),
            "sequel_relationship_target_count": st.session_state.get("sequel_relationship_target_count"),
            "sequel_continuity_anchor": st.session_state.get("sequel_continuity_anchor"),
            "sequel_anchor_after_label": st.session_state.get("sequel_anchor_after_label"),
            "sequel_anchor_before_label": st.session_state.get("sequel_anchor_before_label"),
            "sequel_divergence_anchor_label": st.session_state.get("sequel_divergence_anchor_label"),
            "sequel_preserve_event_labels": st.session_state.get("sequel_preserve_event_labels") or [],
            "target_scene_words": st.session_state.get("target_scene_words"),
        },
        "inputs": {
            "books": st.session_state.get("book_inputs") or [],
        },
        "outputs": {
            "chapters": st.session_state.get("chapters") or [],
            "scene_analyses": st.session_state.get("scene_analyses") or [],
            "resolved_scene_analyses": st.session_state.get("resolved_scene_analyses") or [],
            "entity_registry": st.session_state.get("entity_registry") or [],
            "state_result": st.session_state.get("state_result") or {"transitions": [], "latest_state": []},
            "canon_snapshot": st.session_state.get("canon_snapshot") or [],
            "timeline": st.session_state.get("timeline") or [],
            "event_ledger": st.session_state.get("event_ledger") or [],
            "character_timelines": st.session_state.get("character_timelines") or [],
            "character_profiles": st.session_state.get("character_profiles") or [],
            "identity_result": st.session_state.get("identity_result") or {"alias_map": {}, "rejected_non_characters": [], "decisions": [], "alias_history": []},
            "causal_graph_result": causal_graph_result,
            "sequel_artifacts": {
                "context": st.session_state.get("sequel_context_result") or {},
                "blueprint": st.session_state.get("sequel_blueprint_result") or {},
            },
            "story_index_summary": {
                "document_count": story_index_result.get("document_count", 0),
            },
        },
        "runtime": {
            "elapsed_seconds": st.session_state.get("elapsed_seconds", 0.0),
            "last_scene_seconds": st.session_state.get("last_scene_seconds", 0.0),
            "avg_scene_seconds": st.session_state.get("avg_scene_seconds", 0.0),
            "processed_scene_count": st.session_state.get("processed_scene_count", 0),
            "estimated_total_scenes": st.session_state.get("estimated_total_scenes", 0),
        },
    }


def export_contract_json() -> str:
    return json.dumps(build_export_contract(), ensure_ascii=False, indent=2)


def build_generation_option_catalog() -> Dict:
    character_names: List[str] = []
    seen_characters = set()

    def add_character(name: str):
        cleaned = str(name or "").strip()
        if not cleaned:
            return
        key = cleaned.lower()
        if key in seen_characters:
            return
        seen_characters.add(key)
        character_names.append(cleaned)

    identity_result = st.session_state.get("identity_result") or {}
    for canonical_name in (identity_result.get("alias_map") or {}).keys():
        add_character(canonical_name)

    for profile in st.session_state.get("character_profiles") or []:
        if not isinstance(profile, dict):
            continue
        add_character(profile.get("character"))
        add_character(profile.get("name"))
        add_character(profile.get("canonical_name"))

    for scene in st.session_state.get("resolved_scene_analyses") or []:
        if not isinstance(scene, dict):
            continue
        for value in scene.get("canonical_characters") or []:
            if isinstance(value, dict):
                add_character(value.get("name") or value.get("canonical_name") or value.get("character"))
            else:
                add_character(value)

    relationship_types = sorted(NarrativeGenerationService.ALLOWED_RELATIONSHIP_TYPES)
    seen_relationship_types = {item.lower() for item in relationship_types}
    for row in (st.session_state.get("sequel_context_result") or {}).get("relationship_summary") or []:
        rel_type = str((row or {}).get("relationship_type") or (row or {}).get("type") or "").strip().lower()
        if rel_type and rel_type not in seen_relationship_types:
            relationship_types.append(rel_type)
            seen_relationship_types.add(rel_type)

    event_records: List[Dict] = []
    events_by_id: Dict[str, Dict] = {}
    events_by_label: Dict[str, Dict] = {}

    def add_event_record(*, event_id: str = "", description: str = "", chapter: Any = None, source: str = ""):
        cleaned_description = str(description or "").strip()
        cleaned_id = str(event_id or "").strip()
        if not cleaned_description and not cleaned_id:
            return
        label_core = cleaned_description or cleaned_id
        if chapter is not None and str(chapter).strip() != "":
            label = f"Ch {chapter}: {label_core}"
        else:
            label = label_core
        if label in events_by_label:
            return
        record = {
            "event_id": cleaned_id,
            "description": cleaned_description or cleaned_id,
            "chapter": chapter,
            "label": label,
            "source": source,
        }
        event_records.append(record)
        events_by_label[label] = record
        if cleaned_id:
            events_by_id[cleaned_id] = record

    causal_graph = ((st.session_state.get("causal_graph_result") or {}).get("graph") or {})
    for event in causal_graph.get("events") or []:
        if not isinstance(event, dict):
            continue
        add_event_record(
            event_id=event.get("id") or event.get("event_id") or "",
            description=event.get("description") or event.get("summary") or "",
            chapter=event.get("chapter_index"),
            source="causal_event",
        )
    for thread in causal_graph.get("critical_path") or []:
        if not isinstance(thread, dict):
            continue
        event_id = thread.get("event_id") or ""
        backing = events_by_id.get(str(event_id).strip(), {})
        add_event_record(
            event_id=event_id,
            description=backing.get("description") or thread.get("why_critical") or thread.get("description") or "",
            chapter=backing.get("chapter"),
            source="critical_path",
        )
    for point in causal_graph.get("divergence_points") or []:
        if not isinstance(point, dict):
            continue
        event_id = point.get("event_id") or ""
        backing = events_by_id.get(str(event_id).strip(), {})
        add_event_record(
            event_id=event_id,
            description=backing.get("description") or point.get("decision_made") or point.get("alternate_timeline") or "",
            chapter=backing.get("chapter"),
            source="divergence_point",
        )
    for row in st.session_state.get("timeline") or []:
        if not isinstance(row, dict):
            continue
        add_event_record(
            event_id=row.get("event_id") or "",
            description=row.get("summary") or row.get("event") or row.get("description") or "",
            chapter=row.get("chapter_index"),
            source="timeline",
        )
    for row in st.session_state.get("event_ledger") or []:
        if not isinstance(row, dict):
            continue
        add_event_record(
            event_id=row.get("event_id") or "",
            description=row.get("event_description") or row.get("description") or row.get("summary") or "",
            chapter=row.get("chapter_index"),
            source="event_ledger",
        )

    return {
        "character_options": sorted(character_names, key=str.lower),
        "relationship_type_options": sorted(relationship_types, key=str.lower),
        "event_records": event_records,
        "event_options": [item["label"] for item in event_records],
        "events_by_label": events_by_label,
    }


def build_dashboard_generation_controls() -> Dict:
    catalog = build_generation_option_catalog()
    events_by_label = catalog["events_by_label"]
    relationship_directions = []
    relationship_target_count = int(st.session_state.get("sequel_relationship_target_count") or 0)
    for index in range(relationship_target_count):
        char_a = str(st.session_state.get(f"sequel_relationship_{index}_char_a") or "").strip()
        char_b = str(st.session_state.get(f"sequel_relationship_{index}_char_b") or "").strip()
        relationship_type = str(st.session_state.get(f"sequel_relationship_{index}_type") or "other").strip().lower()
        desired_direction = str(st.session_state.get(f"sequel_relationship_{index}_direction") or "").strip()
        notes = str(st.session_state.get(f"sequel_relationship_{index}_notes") or "").strip()
        if char_a and char_b and desired_direction:
            relationship_directions.append({
                "characters": [char_a, char_b],
                "relationship_type": relationship_type,
                "desired_direction": desired_direction,
                "notes": notes,
            })

    preserved = []
    for label in st.session_state.get("sequel_preserve_event_labels") or []:
        record = events_by_label.get(label)
        if record:
            preserved.append({
                "event_id": record.get("event_id") or "",
                "description": record.get("description") or "",
            })

    anchor_after_label = str(st.session_state.get("sequel_anchor_after_label") or "").strip()
    anchor_before_label = str(st.session_state.get("sequel_anchor_before_label") or "").strip()
    divergence_anchor_label = str(st.session_state.get("sequel_divergence_anchor_label") or "").strip()
    anchor_after_record = events_by_label.get(anchor_after_label, {})
    anchor_before_record = events_by_label.get(anchor_before_label, {})
    divergence_record = events_by_label.get(divergence_anchor_label, {})

    return {
        "chapter_count": int(st.session_state.get("sequel_chapter_count") or 25),
        "canon_position": st.session_state.get("sequel_canon_position") or "post_canon",
        "new_plot": st.session_state.get("sequel_new_plot") or "",
        "primary_pov_character": st.session_state.get("sequel_primary_pov_character") or "",
        "relationship_directions": relationship_directions,
        "canon_elements_to_preserve": preserved,
        "continuity_anchor": st.session_state.get("sequel_continuity_anchor") or "",
        "divergence_anchor": divergence_record.get("description") or divergence_anchor_label,
        "anchor_after": anchor_after_record.get("description") or anchor_after_label,
        "anchor_before": anchor_before_record.get("description") or anchor_before_label,
    }


def build_sequel_blueprint_from_contract(contract: Dict, prompt: str, model_mode: str, generation_controls: Dict) -> Tuple[Dict, Dict]:
    llm_client = LLMClient(
        mode=model_mode,
        ollama_model_override=NarrativeGenerationService.DEFAULT_NARRATIVE_OLLAMA_MODEL,
        max_retries=2,
        base_delay=0.0,
        timeout=180,
    )
    decoder = NarrativeGenerationService(llm_client=llm_client)
    sequel_context, blueprint = decoder.build_or_load_blueprint(
        contract,
        user_prompt=prompt,
        generation_controls=generation_controls,
        prefer_exported_context=True,
        prefer_exported_blueprint=False,
    )
    return sequel_context, blueprint


def has_exportable_outputs() -> bool:
    return bool(
        st.session_state.get("chapters")
        or st.session_state.get("scene_analyses")
        or st.session_state.get("timeline")
        or st.session_state.get("entity_registry")
    )


def build_causal_graph(timeline: List[Dict], scene_analyses: List[Dict], model_mode: str) -> Dict:
    logging.info(
        "Causal graph build started | timeline_rows=%s | scenes=%s | model=%s",
        len(timeline),
        len(scene_analyses),
        model_mode,
    )
    service = CausalGraphService(
        llm_client=LLMClient(mode=model_mode, max_retries=2, base_delay=0.0, timeout=120),
        batch_size=20,
    )
    result = service.build(timeline, scene_analyses)
    graph = result.get("graph", {})
    logging.info(
        "Causal graph build completed | events=%s | warning=%s | error=%s",
        len(graph.get("events", [])),
        graph.get("warning", ""),
        graph.get("error", ""),
    )
    return result


def is_overflow_error(result: Dict) -> bool:
    error_blob = " ".join([str(result.get("error", "")), str(result.get("last_error", ""))]).lower()
    return any(keyword in error_blob for keyword in ["context", "token", "overflow", "length", "too long", "prompt"])


def next_smaller_scene_target(target_words: int) -> int | None:
    if target_words == 0:
        return SCENE_FALLBACK_TARGETS[0]
    for candidate in SCENE_FALLBACK_TARGETS:
        if candidate < target_words:
            return candidate
    return None


def analyze_scene_with_fallback(
    scene: Dict,
    target_scene_words: int,
    analysis_model: str,
    identity_model: str,
    analysis_mode: str,
    alias_result: Dict,
    state_result: Dict,
    resolved_scene_analyses: List[Dict],
) -> Tuple[List[Dict], List[int]]:
    current_target = target_scene_words
    attempted_targets = []
    orchestrator = SceneAnalysisOrchestrator(
        analysis_model=analysis_model,
        identity_model=identity_model,
    )
    working_scenes = [scene]

    while current_target is not None:
        attempted_targets.append(current_target)
        analyzed = []
        overflow_triggered = False

        for current_scene in working_scenes:
            scene_context = build_scene_context(
                current_scene.get("text", ""),
                resolved_scene_analyses,
                state_result,
                alias_result,
            )
            result = orchestrator.analyze_scene(
                current_scene,
                alias_map=alias_result["alias_map"],
                rejected_identities=alias_result["rejected_non_characters"],
                scene_context=scene_context,
                analysis_mode=analysis_mode,
            )
            if result.get("error") and is_overflow_error(result):
                overflow_triggered = True
                break
            analyzed.append(result)

        if not overflow_triggered:
            return analyzed, attempted_targets

        current_target = next_smaller_scene_target(current_target)
        if current_target is not None:
            extractor = SceneExtractor.from_target_words(current_target)
            next_working_scenes = []
            for item in working_scenes:
                next_working_scenes.extend(extractor.split_scene(item, current_target))
            working_scenes = next_working_scenes

    fallback_error = {
        "book_index": scene["book_index"],
        "chapter_index": scene["chapter_index"],
        "scene_index": 1,
        "length": len(scene.get("text", "").split()),
        "text": scene.get("text", ""),
        "scene_summary": "",
        "events": [],
        "entities_present": [],
        "entity_descriptions": [],
        "state_changes": [],
        "relationship_changes": [],
        "location": {},
        "time_signals": [],
        "canonical_characters": [],
        "character_mentions": [],
        "alias_updates": [],
        "rejected_identity_candidates": [],
        "error": "context_overflow_unresolved",
        "last_error": "",
        "fallback_targets": attempted_targets,
    }
    return [fallback_error], attempted_targets


def render_books(container, book_inputs: List[Dict]):
    with container.container():
        st.subheader("Selected Books")
        rows = [
            {
                "order": index,
                "title": item.get("title") or Path(item["path"]).name,
                "type": item.get("type", ""),
                "path": item["path"],
            }
            for index, item in enumerate(book_inputs, start=1)
        ]
        render_panel(
            "Input Set",
            "Review the ordered input corpus before a run. This is the authoritative processing order for cross-book context and downstream state.",
        )
        cols = st.columns(3)
        cols[0].metric("Books", len(rows))
        cols[1].metric("EPUB", sum(1 for row in rows if row["type"] == "epub"))
        cols[2].metric("PDF", sum(1 for row in rows if row["type"] == "pdf"))
        st.dataframe(rows, width="stretch")


def render_chapters(container, chapters: List[Dict], compact: bool):
    with container.container():
        st.subheader("Chapters")
        render_panel(
            "Extraction Overview",
            "Use this view to check whether chapter extraction produced a sane narrative structure before deeper analysis starts.",
        )
        st.write(f"Rows: {len(chapters)}")
        if compact:
            preview = chapters[-3:]
            if preview:
                st.caption("Latest chapters")
                for chapter in preview:
                    st.write(f"Book {chapter['book_index']} | Chapter {chapter['chapter_index']} | {chapter['chapter_title']}")
            return
        title_counter = Counter(chapter.get("book_index") for chapter in chapters)
        st.dataframe(
            [{"book": book_index, "chapters": count} for book_index, count in sorted(title_counter.items())],
            width="stretch",
        )
        items = paged_items(chapters, "chapters", page_size=5)
        for chapter in items:
            with st.expander(f"Book {chapter['book_index']} | Chapter {chapter['chapter_index']} | {chapter['chapter_title']}"):
                st.text(f"Source: {chapter['source_file']}")
                st.code(chapter["content"])


def build_comparison_summary(scene: Dict) -> Dict:
    comparison = scene.get("comparison_results") or {}
    structured = comparison.get("structured") or {}
    tool = comparison.get("tool") or {}

    def character_names(payload: Dict) -> set[str]:
        return {str(item.get("name")).strip() for item in payload.get("canonical_characters") or [] if str(item.get("name") or "").strip()}

    def mention_texts(payload: Dict) -> set[str]:
        return {str(item.get("mention_text")).strip() for item in payload.get("character_mentions") or [] if str(item.get("mention_text") or "").strip()}

    def event_descriptions(payload: Dict) -> set[str]:
        return {str(item.get("description")).strip() for item in payload.get("events") or [] if str(item.get("description") or "").strip()}

    def aliases(payload: Dict) -> set[str]:
        return {
            f"{str(item.get('alias') or '').strip()} -> {str(item.get('canonical_name') or '').strip()}"
            for item in payload.get("alias_updates") or []
            if str(item.get("alias") or "").strip() and str(item.get("canonical_name") or "").strip()
        }

    return {
        "tool_only_characters": sorted(character_names(tool) - character_names(structured)),
        "structured_only_characters": sorted(character_names(structured) - character_names(tool)),
        "tool_only_mentions": sorted(mention_texts(tool) - mention_texts(structured)),
        "structured_only_mentions": sorted(mention_texts(structured) - mention_texts(tool)),
        "tool_only_events": sorted(event_descriptions(tool) - event_descriptions(structured)),
        "structured_only_events": sorted(event_descriptions(structured) - event_descriptions(tool)),
        "tool_only_aliases": sorted(aliases(tool) - aliases(structured)),
        "structured_only_aliases": sorted(aliases(structured) - aliases(tool)),
    }


def render_scenes(container, scene_analyses: List[Dict], compact: bool):
    with container.container():
        st.subheader("Scenes")
        render_panel(
            "Scene Review",
            "This is the primary inspection surface for chunk-level quality. Look for missing events, weak character grounding, fallback splits, and compare-mode differences.",
        )
        st.write(f"Scenes: {len(scene_analyses)}")
        if scene_analyses:
            cols = st.columns(5)
            cols[0].metric("Scenes", len(scene_analyses))
            cols[1].metric("Avg Events", round(safe_avg([len(item.get("events") or []) for item in scene_analyses]), 2))
            cols[2].metric("Avg Canonicals", round(safe_avg([len(item.get("canonical_characters") or []) for item in scene_analyses]), 2))
            cols[3].metric("Errors", sum(1 for item in scene_analyses if item.get("error")))
            cols[4].metric("Compare Runs", sum(1 for item in scene_analyses if item.get("comparison_results")))
            flagged = [row for row in scene_summary_rows(scene_analyses) if row["issues"]]
            if flagged:
                st.caption("Flagged scenes")
                st.dataframe(flagged[:12], width="stretch")
        items = scene_analyses[-3:] if compact else paged_items(scene_analyses, "scenes", page_size=6)
        for scene in items:
            chapter_label = f"Chapter {scene['chapter_index']}"
            if scene.get("end_chapter_index") and scene.get("end_chapter_index") != scene["chapter_index"]:
                chapter_label = f"Chapters {scene['chapter_index']}-{scene['end_chapter_index']}"
            with st.expander(f"Book {scene['book_index']} | {chapter_label} | Scene {scene['scene_index']}"):
                render_chip_row(summarize_scene_flags(scene))
                info_cols = st.columns([2, 1])
                with info_cols[0]:
                    st.write(f"Summary: {scene.get('scene_summary') or 'None'}")
                with info_cols[1]:
                    st.metric("Events", len(scene.get("events") or []))
                    st.metric("Canonicals", len(scene.get("canonical_characters") or []))
                if scene.get("fallback_targets"):
                    st.write(f"Fallback target words tried: {scene.get('fallback_targets')}")
                if scene.get("error"):
                    st.warning(f"Analysis error: {scene['error']} | {scene.get('last_error', '')}")
                overview_cols = st.columns(2)
                with overview_cols[0]:
                    st.write("Canonical characters")
                    st.dataframe(scene.get("canonical_characters") or [], width="stretch")
                    st.write("Events")
                    st.dataframe(scene.get("events") or [], width="stretch")
                with overview_cols[1]:
                    st.write("Character mentions")
                    st.dataframe(scene.get("character_mentions") or [], width="stretch")
                    st.write("Alias updates")
                    st.dataframe(scene.get("alias_updates") or [], width="stretch")
                tool_runtime = scene.get("tool_runtime") or {}
                if tool_runtime.get("content") or tool_runtime.get("identity"):
                    st.write("Tool runtime")
                    st.dataframe(
                        [
                            {"channel": "content", **(tool_runtime.get("content") or {})},
                            {"channel": "identity", **(tool_runtime.get("identity") or {})},
                        ],
                        width="stretch",
                    )
                with st.expander("Local evidence"):
                    st.write(scene.get("local_evidence") or {})
                if scene.get("comparison_results"):
                    st.write("Comparison summary")
                    st.dataframe([build_comparison_summary(scene)], width="stretch")
                    with st.expander("Full compare payloads"):
                        st.write("Raw local evidence")
                        st.write(scene.get("local_evidence_raw") or {})
                        st.write(scene.get("comparison_results"))
                if scene.get("state_changes") or scene.get("relationship_changes"):
                    details_cols = st.columns(2)
                    with details_cols[0]:
                        st.write("State changes")
                        st.dataframe(scene.get("state_changes") or [], width="stretch")
                    with details_cols[1]:
                        st.write("Relationship changes")
                        st.dataframe(scene.get("relationship_changes") or [], width="stretch")
                if scene.get("rejected_identity_candidates"):
                    st.write("Rejected identities")
                    st.write(scene.get("rejected_identity_candidates") or [])
                st.code(scene["text"])


def render_entity_registry(container, entity_registry: List[Dict], compact: bool):
    with container.container():
        st.subheader("Entity Registry")
        render_panel(
            "Tracked World Model",
            "This registry is the durable inventory of narrative entities. Use it to spot over-fragmentation, missing major actors, and noisy one-off objects.",
        )
        st.write(f"Entities: {len(entity_registry)}")
        if not entity_registry:
            st.info("No entity registry entries yet.")
            return
        type_counts = Counter(item.get("entity_type", "unknown") for item in entity_registry)
        cols = st.columns(max(1, min(4, len(type_counts))))
        for idx, (entity_type, count) in enumerate(sorted(type_counts.items())):
            cols[idx % len(cols)].metric(entity_type.title(), count)
        st.caption("Highest mention counts")
        st.dataframe(sorted(entity_registry, key=lambda item: item.get("mention_count", 0), reverse=True)[:10], width="stretch")
        if compact:
            st.caption("Latest entities")
            for item in entity_registry[-5:]:
                st.write(f"{item['name']} | {item['entity_type']} | mentions={item['mention_count']}")
            return
        items = paged_items(entity_registry, "entity_registry", page_size=8)
        for item in items:
            with st.expander(f"{item['name']} | {item['entity_type']} | mentions={item['mention_count']}"):
                st.write(item)


def render_state_result(container, state_result: Dict, compact: bool):
    with container.container():
        transitions = state_result.get("transitions", [])
        latest_state = state_result.get("latest_state", [])
        st.subheader("State Transitions")
        render_panel(
            "Change Tracking",
            "This view answers what became newly true, what the latest known world state looks like, and whether state extraction is too sparse or too noisy.",
        )
        st.write(f"Transitions: {len(transitions)}")
        if not transitions:
            st.info("No state changes yet.")
        else:
            cols = st.columns(3)
            cols[0].metric("Transitions", len(transitions))
            cols[1].metric("Entities with State", len(latest_state))
            cols[2].metric("Avg Changes/Scene", round(len(transitions) / max(1, len(st.session_state.get("scene_analyses") or [])), 2))
            if compact:
                for item in transitions[-5:]:
                    st.write(f"State {item['state_index']} | {item['entity_name']} | {item['attribute']} -> {item['new_state']}")
            else:
                items = paged_items(transitions, "state_transitions", page_size=8)
                for item in items:
                    with st.expander(f"State {item['state_index']} | {item['entity_name']} | {item['attribute']} -> {item['new_state']}"):
                        st.write(item)
        st.subheader("Latest Known State")
        if not latest_state:
            st.caption("No latest state yet.")
        elif compact:
            for item in latest_state[-5:]:
                st.write(f"{item['entity_name']} | {item['entity_type']}")
        else:
            items = paged_items(latest_state, "latest_state", page_size=8)
            for item in items:
                with st.expander(f"{item['entity_name']} | {item['entity_type']}"):
                    st.write(item["attributes"])


def render_canon_snapshot(container, canon_snapshot: List[Dict], compact: bool):
    with container.container():
        st.subheader("Canon Snapshot")
        render_panel(
            "Point-in-Time Canon",
            "This snapshot is the currently reconstructed world state at the latest processed reading position.",
        )
        st.write(f"Entities in snapshot: {len(canon_snapshot)}")
        if not canon_snapshot:
            st.info("No canon state available up to the current point yet.")
            return
        if compact:
            for item in canon_snapshot[-5:]:
                st.write(f"{item['entity_name']} | {item['entity_type']}")
            return
        items = paged_items(canon_snapshot, "canon_snapshot", page_size=8)
        for item in items:
            with st.expander(f"{item['entity_name']} | {item['entity_type']}"):
                st.write(item["attributes"])


def render_timeline(container, timeline: List[Dict], compact: bool):
    with container.container():
        st.subheader("Timeline")
        render_panel(
            "Narrative Sequence",
            "Use the timeline to judge pacing, event coverage, and whether scene summaries compress important plot beats too aggressively.",
        )
        st.write(f"Timeline rows: {len(timeline)}")
        if not timeline:
            st.info("No timeline rows yet.")
            return
        cols = st.columns(4)
        cols[0].metric("Rows", len(timeline))
        cols[1].metric("Books", len({row.get("book_index") for row in timeline}))
        cols[2].metric("Scenes Covered", len({(row.get("book_index"), row.get("chapter_index"), row.get("scene_index")) for row in timeline}))
        cols[3].metric("Avg Rows/Scene", round(len(timeline) / max(1, len(st.session_state.get("scene_analyses") or [])), 2))
        if compact:
            for row in timeline[-5:]:
                st.write(f"Time {row['time_index']} | Book {row['book_index']} | Chapter {row['chapter_index']} | Scene {row['scene_index']} | {row['summary']}")
            return
        items = paged_items(timeline, "timeline", page_size=12)
        for row in items:
            with st.expander(f"Time {row['time_index']} | Book {row['book_index']} | Chapter {row['chapter_index']} | Scene {row['scene_index']}"):
                st.write(row)


def render_event_ledger(container, event_ledger: List[Dict], compact: bool):
    with container.container():
        st.subheader("Event Ledger")
        render_panel(
            "Canonical Event Anchors",
            "This is the first durable event artifact for later canon querying, divergence selection, and rewrite planning.",
        )
        st.write(f"Ledger events: {len(event_ledger)}")
        if not event_ledger:
            st.info("No event ledger yet.")
            return
        cols = st.columns(4)
        cols[0].metric("Events", len(event_ledger))
        cols[1].metric("With Causal Links", sum(1 for item in event_ledger if item.get("causal_parents") or item.get("causal_children")))
        cols[2].metric("With Location", sum(1 for item in event_ledger if item.get("location")))
        cols[3].metric("Tagged", sum(1 for item in event_ledger if item.get("tags")))
        if compact:
            for item in event_ledger[-5:]:
                st.write(f"{item['ledger_event_id']} | {item['title']}")
            return
        st.dataframe(
            [
                {
                    "ledger_event_id": item.get("ledger_event_id"),
                    "time_index": item.get("time_index"),
                    "title": item.get("title"),
                    "participants": ", ".join(item.get("participants", [])),
                    "location": item.get("location", ""),
                    "tags": ", ".join(item.get("tags", [])),
                }
                for item in event_ledger[:12]
            ],
            width="stretch",
        )
        items = paged_items(event_ledger, "event_ledger", page_size=8)
        for item in items:
            with st.expander(f"{item['ledger_event_id']} | {item['title']}"):
                st.write(item)


def render_character_timelines(container, character_timelines: List[Dict], compact: bool):
    with container.container():
        st.subheader("Character Timelines")
        render_panel(
            "Character Coverage",
            "This is the fastest way to judge identity quality. Look for duplicate canonicals, major characters with thin coverage, and descriptor leakage.",
        )
        st.write(f"Characters: {len(character_timelines)}")
        if not character_timelines:
            st.info("No character timelines yet.")
            return
        entity_registry = st.session_state.get("entity_registry") or []
        state_result = st.session_state.get("state_result") or {"latest_state": []}
        identity_result = st.session_state.get("identity_result") or {"alias_map": {}, "decisions": []}
        profiles = build_character_profiles(
            character_timelines,
            entity_registry,
            state_result,
            identity_result,
            st.session_state.get("resolved_scene_analyses") or [],
        )
        sorted_characters = sorted(character_timelines, key=lambda item: len(item.get("events") or []), reverse=True)
        st.dataframe(
            [{"character": item["character"], "events": len(item.get("events") or [])} for item in sorted_characters[:12]],
            width="stretch",
        )
        if compact:
            for item in character_timelines[-5:]:
                st.write(f"{item['character']} | {len(item['events'])} events")
            return
        st.subheader("Character Profile")
        selected_character = st.selectbox(
            "Inspect character",
            [profile["character"] for profile in profiles],
            key="character_profile_select",
        )
        selected_profile = next((profile for profile in profiles if profile["character"] == selected_character), None)
        if selected_profile:
            header_cols = st.columns(5)
            header_cols[0].metric("Events", selected_profile["event_count"])
            header_cols[1].metric("Aliases", len(selected_profile["aliases"]))
            header_cols[2].metric("Registry Mentions", selected_profile["mention_count"])
            header_cols[3].metric("State Changes", len(selected_profile["state_changes"]))
            header_cols[4].metric("Identity Decisions", selected_profile["decision_count"])
            render_chip_row([(alias, "good") for alias in selected_profile["aliases"][:8]])

            first_seen = selected_profile.get("first_seen") or {}
            latest_state = selected_profile.get("latest_state") or {}
            overview_cols = st.columns(2)
            with overview_cols[0]:
                st.write("Profile Overview")
                st.write({
                    "character": selected_profile["character"],
                    "first_seen": {
                        "book_index": first_seen.get("book_index"),
                        "chapter_index": first_seen.get("chapter_index"),
                        "scene_index": first_seen.get("scene_index"),
                    },
                    "latest_known_state": latest_state,
                })
            with overview_cols[1]:
                st.write("Descriptive evidence")
                if selected_profile["descriptions"]:
                    st.dataframe(selected_profile["descriptions"], width="stretch")
                else:
                    st.caption("No descriptive evidence recorded yet.")

            detail_cols = st.columns(2)
            with detail_cols[0]:
                st.write("Recent timeline events")
                if selected_profile["recent_events"]:
                    st.dataframe(selected_profile["recent_events"], width="stretch")
                else:
                    st.caption("No recent events recorded.")
            with detail_cols[1]:
                st.write("State history")
                if selected_profile["state_changes"]:
                    st.dataframe(selected_profile["state_changes"], width="stretch")
                else:
                    st.caption("No state history recorded.")

            with st.expander("Identity decision trail"):
                if selected_profile["decisions"]:
                    st.dataframe(selected_profile["decisions"], width="stretch")
                else:
                    st.caption("No identity decisions recorded for this character.")

            with st.expander("Full event history"):
                st.dataframe(selected_profile["events"], width="stretch")

        st.subheader("All Character Timelines")
        items = paged_items(character_timelines, "character_timelines", page_size=8)
        for item in items:
            with st.expander(f"{item['character']} | {len(item['events'])} events"):
                st.write(item["events"])


def render_alias_map(container, identity_result: Dict, compact: bool):
    with container.container():
        alias_map = identity_result.get("alias_map", {})
        st.subheader("Alias Map")
        render_panel(
            "Identity Memory",
            "Review canonical names, alias breadth, and rejected labels here. This is the best place to catch over-merging or unresolved duplication.",
        )
        st.write(f"Canonical characters with aliases: {len(alias_map)}")
        if not alias_map:
            st.info("No alias decisions yet.")
        else:
            items = [{"canonical_name": name, "aliases": aliases} for name, aliases in alias_map.items()]
            cols = st.columns(3)
            cols[0].metric("Canonicals", len(items))
            cols[1].metric("Total Aliases", sum(len(item["aliases"]) for item in items))
            cols[2].metric("Avg Aliases/Canonical", round(safe_avg([len(item["aliases"]) for item in items]), 2))
            if compact:
                for item in items[-5:]:
                    st.write(f"{item['canonical_name']} | {len(item['aliases'])} aliases")
            else:
                st.caption("Largest alias sets")
                st.dataframe(
                    sorted(
                        [{"canonical_name": item["canonical_name"], "alias_count": len(item["aliases"])} for item in items],
                        key=lambda row: row["alias_count"],
                        reverse=True,
                    )[:12],
                    width="stretch",
                )
                items = paged_items(items, "alias_map", page_size=8)
                for item in items:
                    with st.expander(f"{item['canonical_name']} | {len(item['aliases'])} aliases"):
                        st.write(item["aliases"])
        st.subheader("Rejected Non-Characters")
        rejected = identity_result.get("rejected_non_characters") or []
        if compact:
            st.write(rejected[-5:])
        else:
            st.write(rejected)
        st.subheader("Alias Resolution History")
        history = identity_result.get("alias_history") or []
        st.write(history[-5:] if compact else history)


def render_identity_decisions(container, identity_result: Dict, compact: bool):
    with container.container():
        decisions = identity_result.get("decisions", [])
        st.subheader("Identity Decisions")
        render_panel(
            "Identity Audit Trail",
            "These decisions explain how the system accepted, rejected, merged, or promoted identities over time.",
        )
        st.write(f"Decisions: {len(decisions)}")
        if not decisions:
            st.info("No identity decisions yet.")
            return
        decision_counts = Counter(item.get("decision_type", "unknown") for item in decisions)
        st.dataframe(
            [{"decision_type": key, "count": count} for key, count in sorted(decision_counts.items(), key=lambda item: item[1], reverse=True)],
            width="stretch",
        )
        if compact:
            for item in decisions[-5:]:
                st.write(f"{item.get('decision_type')} | {item.get('character')} | {item.get('canonical_name', '')}")
            return
        items = paged_items(decisions, "identity_decisions", page_size=8)
        for item in items:
            with st.expander(f"{item.get('decision_type')} | {item.get('character')} | {item.get('canonical_name', '')}"):
                st.write(item)


def render_story_search(container, story_index_result: Dict, compact: bool):
    with container.container():
        st.subheader("Story Search")
        render_panel(
            "Cross-Output Retrieval",
            "Search across the indexed story artifacts when you want to inspect grounding, coverage, or evidence for a narrative claim.",
        )
        if not story_index_result:
            st.info("Story index has not been built yet.")
            return
        if compact or st.session_state.get("pipeline_running"):
            st.info("Search controls will appear after the live run completes. Indexed document count is updating in real time.")
            st.caption(f"Indexed documents so far: {story_index_result.get('document_count', 0)}")
            return
        query = st.text_input(
            "Search the indexed story outputs",
            value="Feyre was going under the mountain to save Tamlin",
            key="story_search_query",
        )
        min_similarity = st.slider(
            "Story search minimum similarity",
            min_value=0.0,
            max_value=1.0,
            value=0.05,
            step=0.01,
            key="story_search_min_similarity",
        )
        max_results = st.slider(
            "Story search max results",
            min_value=1,
            max_value=12,
            value=8,
            step=1,
            key="story_search_max_results",
        )
        results = story_index_result["query_service"].search(story_index_result["service"], query, min_similarity=min_similarity, max_results=max_results)
        st.caption(f"Indexed documents: {story_index_result.get('document_count', 0)} | Matches: {len(results)}")
        for item in results:
            meta = item["metadata"]
            title = f"{item['item_type']} | score={item['score']:.3f}"
            if meta.get("book_index") is not None:
                title += f" | Book {meta.get('book_index')} Chapter {meta.get('chapter_index')} Scene {meta.get('scene_index')}"
            with st.expander(title):
                st.write(f"Summary: {item['summary']}")
                st.write(f"Scene reference: {item['scene_ref']}")
                st.write(f"Metadata: {meta}")
                st.code(item["text"])


def render_sequel_workspace(container, compact: bool):
    with container.container():
        st.subheader("Narrative Workspace")
        render_panel(
            "Downstream Generation Artifacts",
            "Inspect the decoder-facing narrative context and the latest generated blueprint built from the current contract. "
            "This workspace stays at planning level; full narrative prose generation remains a CLI/service workflow.",
        )
        sequel_context = st.session_state.get("sequel_context_result") or {}
        blueprint = st.session_state.get("sequel_blueprint_result") or {}
        if not sequel_context and not blueprint:
            st.info("No narrative artifacts yet. Generate a narrative blueprint from the sidebar after the pipeline finishes.")
            return

        if sequel_context:
            stats = sequel_context.get("stats") or {}
            st.caption("Narrative context summary")
            cols = st.columns(6)
            cols[0].metric("Characters", stats.get("characters_retrieved", 0))
            cols[1].metric("Relationships", stats.get("relationship_pairs", 0))
            cols[2].metric("Threads", stats.get("unresolved_threads", 0))
            cols[3].metric("Chains", stats.get("causal_chains", 0))
            cols[4].metric("Flexible", stats.get("flexible_events", 0))
            cols[5].metric("Critical Tail", stats.get("critical_ending_events", 0))

            ending = sequel_context.get("story_ending") or {}
            if ending.get("last_scene"):
                st.write("Last scene summary")
                st.write((ending.get("last_scene") or {}).get("summary") or "")

            if compact:
                st.write("Top characters:", [item.get("name") for item in (sequel_context.get("character_states") or [])[:5]])
                st.write("Top threads:", [item.get("event_description") for item in (sequel_context.get("unresolved_threads") or [])[:3]])
            else:
                with st.expander("Character states"):
                    st.dataframe(sequel_context.get("character_states") or [], width="stretch")
                with st.expander("Relationship summary"):
                    st.dataframe(sequel_context.get("relationship_summary") or [], width="stretch")
                with st.expander("Unresolved threads"):
                    st.dataframe(sequel_context.get("unresolved_threads") or [], width="stretch")
                with st.expander("Causal chains"):
                    st.dataframe(sequel_context.get("causal_chains") or [], width="stretch")
                with st.expander("Flexible events"):
                    st.dataframe(sequel_context.get("flexible_events") or [], width="stretch")

        if blueprint:
            st.caption("Latest blueprint")
            cols = st.columns(4)
            cols[0].metric("Title", blueprint.get("title", "Untitled"))
            cols[1].metric("Chapters", blueprint.get("total_chapters", 0))
            cols[2].metric("Acts", len(blueprint.get("acts") or []))
            cols[3].metric("Primary Arcs", len(blueprint.get("primary_arcs") or []))
            st.write(blueprint.get("premise") or "")
            if compact:
                st.write("Conflict:", blueprint.get("central_conflict") or "")
            else:
                with st.expander("Blueprint details", expanded=True):
                    st.write({
                        "central_conflict": blueprint.get("central_conflict", ""),
                        "structure_type": blueprint.get("structure_type", ""),
                        "tone": blueprint.get("tone", ""),
                        "world_threads_activated": blueprint.get("world_threads_activated", []),
                    })
                with st.expander("Primary arcs"):
                    st.dataframe(blueprint.get("primary_arcs") or [], width="stretch")
                with st.expander("Acts"):
                    st.dataframe(blueprint.get("acts") or [], width="stretch")


def render_causal_graph(container, causal_graph_result: Dict, compact: bool):
    with container.container():
        graph = (causal_graph_result or {}).get("graph", {})
        events = graph.get("events", [])
        st.subheader("Causal Graph")
        render_panel(
            "Cause-and-Effect Review",
            "Inspect which events the system believes are causally linked, where the critical path runs, and whether a batch failure left gaps.",
        )
        st.write(f"Causal events: {len(events)}")
        if graph.get("error"):
            st.warning(f"Causal graph error: {graph.get('error')} | {graph.get('last_error', '')}")
        if not events:
            st.info("No causal graph events yet.")
            return
        render_chip_row(
            [(f"Warning: {graph.get('warning')}", "warn")] if graph.get("warning") else []
        )
        st.dataframe(
            [{"id": item.get("id"), "time_index": item.get("time_index"), "type": item.get("event_type"), "summary": item.get("summary", "")} for item in events[:12]],
            width="stretch",
        )
        if compact:
            for item in events[-5:]:
                st.write(f"{item['id']} | time {item.get('time_index')} | {item.get('event_type')}")
            return
        items = paged_items(events, "causal_graph_events", page_size=12)
        for item in items:
            with st.expander(f"{item['id']} | time {item.get('time_index')} | {item.get('event_type')}"):
                st.write(item)


def render_causal_metrics(container, causal_graph_result: Dict):
    with container.container():
        metrics = (causal_graph_result or {}).get("metrics", {})
        graph = (causal_graph_result or {}).get("graph", {})
        st.subheader("Causal Metrics")
        render_panel(
            "Graph Summary",
            "These metrics help judge whether the causal layer is producing a sparse skeleton or a rich explanatory structure.",
        )
        if not metrics:
            st.info("No causal metrics yet.")
            return
        cols = st.columns(6)
        cols[0].metric("Events", metrics.get("total_events", 0))
        cols[1].metric("Links", metrics.get("total_links", 0))
        cols[2].metric("Avg Links/Event", metrics.get("avg_links_per_event", 0))
        cols[3].metric("Critical Path", metrics.get("critical_path_length", 0))
        cols[4].metric("Chains", metrics.get("causal_chain_count", 0))
        cols[5].metric("Divergence", metrics.get("divergence_count", 0))

        st.subheader("Critical Path")
        st.write(graph.get("critical_path") or [])
        st.subheader("Flexible Events")
        st.write(graph.get("flexible_events") or [])
        st.subheader("Causal Chains")
        st.write(graph.get("causal_chains") or [])
        st.subheader("Divergence Points")
        st.write(graph.get("divergence_points") or [])


def render_status(container, compact: bool):
    with container.container():
        st.subheader("Run Status")
        render_panel(
            "Operational Overview",
            "This page summarizes pipeline health, coverage, timing, and the most important warnings so you can decide where to inspect next.",
        )
        st.markdown(f"**{st.session_state.get('latest_status', 'Idle')}**")

        metric_cols = st.columns(6)
        metric_cols[0].metric("Chapters", len(st.session_state.get("chapters") or []))
        processed = int(st.session_state.get("processed_scene_count") or 0)
        total = int(st.session_state.get("estimated_total_scenes") or 0)
        scene_label = f"{processed} / {total}" if total else str(processed)
        metric_cols[1].metric("Scenes", scene_label)
        metric_cols[2].metric("Aliases", len((st.session_state.get("identity_result") or {}).get("alias_map", {})))
        metric_cols[3].metric("Indexed Docs", int((st.session_state.get("story_index_result") or {}).get("document_count", 0)))
        metric_cols[4].metric("Elapsed", format_duration(float(st.session_state.get("elapsed_seconds") or 0.0)))
        metric_cols[5].metric("Last Scene", format_duration(float(st.session_state.get("last_scene_seconds") or 0.0)))

        identity_result = st.session_state.get("identity_result") or {}
        if identity_result.get("identity_provider") == "booknlp_clean":
            narrator = identity_result.get("narrator") or {}
            reference_entities = identity_result.get("reference_entities") or []
            provider_cols = st.columns(4)
            provider_cols[0].metric("Identity Source", "BookNLP clean")
            provider_cols[1].metric("Stable Characters", len(identity_result.get("alias_map") or {}))
            provider_cols[2].metric("Reference Entities", len(reference_entities))
            provider_cols[3].metric("Narrator", narrator.get("display_name") or "none")

        info_cols = st.columns(2)
        with info_cols[0]:
            st.caption("Current Scene")
            st.write(st.session_state.get("current_scene_ref") or "Not started")
        with info_cols[1]:
            st.caption("Latest Scene Summary")
            st.write(st.session_state.get("latest_scene_summary") or "No scene analyzed yet")

        st.caption(f"Average scene analysis time: {format_duration(float(st.session_state.get('avg_scene_seconds') or 0.0))}")
        summary = build_run_health_summary()
        alert_items = []
        if summary["scene_errors"]:
            alert_items.append((f"Scene errors: {summary['scene_errors']}", "risk"))
        if summary["fallback_scenes"]:
            alert_items.append((f"Fallback scenes: {summary['fallback_scenes']}", "warn"))
        if summary["rejections"]:
            alert_items.append((f"Rejected identities: {summary['rejections']}", "warn"))
        if summary["causal_warning"]:
            alert_items.append((f"Causal issue: {summary['causal_warning']}", "warn"))
        if not alert_items:
            alert_items.append(("No critical warnings", "good"))
        render_chip_row(alert_items)
        blueprint = st.session_state.get("sequel_blueprint_result") or {}
        if blueprint:
            st.subheader("Latest Narrative Blueprint")
            st.caption("This is the most recent sequel-planning artifact generated from the current contract.")
            cols = st.columns(4)
            cols[0].metric("Title", blueprint.get("title", "Untitled"))
            cols[1].metric("Chapters", blueprint.get("total_chapters", 0))
            cols[2].metric("Acts", len(blueprint.get("acts") or []))
            cols[3].metric("Primary Arcs", len(blueprint.get("primary_arcs") or []))
            st.write(blueprint.get("premise") or "")
            if not compact:
                st.write({
                    "central_conflict": blueprint.get("central_conflict", ""),
                    "world_threads_activated": blueprint.get("world_threads_activated", []),
                    "tone": blueprint.get("tone", ""),
                })

        health_cols = st.columns(4)
        health_cols[0].metric("Avg Events/Scene", summary["avg_events_per_scene"])
        health_cols[1].metric("Avg Canonicals/Scene", summary["avg_characters_per_scene"])
        health_cols[2].metric("Timeline Rows", summary["timeline_rows"])
        health_cols[3].metric("Causal Events", summary["causal_events"])

        if summary["tool_calls_seen"] or summary["compare_scenes"]:
            tool_cols = st.columns(4)
            tool_cols[0].metric("Compare Scenes", summary["compare_scenes"])
            tool_cols[1].metric("Tool Calls Seen", summary["tool_calls_seen"])
            tool_cols[2].metric("Tool Calls Ignored", summary["tool_calls_ignored"])
            tool_cols[3].metric(
                "Tool Ignore Rate",
                f"{(summary['tool_calls_ignored'] / max(1, summary['tool_calls_seen'])) * 100:.1f}%",
            )
            compare_summary = summarize_compare_mode(st.session_state.get("scene_analyses") or [])
            if compare_summary.get("scene_count"):
                st.caption("Compare-mode divergence")
                st.dataframe([compare_summary], width="stretch")

        if compact:
            st.caption("Live mode: deterministic downstream modules are rebuilt after each analyzed scene.")


def load_selected_json_artifact(artifacts: List[Dict], label: str, key: str) -> Tuple[Dict, Dict] | Tuple[None, None]:
    if not artifacts:
        st.info(f"No {label.lower()} found yet.")
        return None, None
    options = {f"{item['name']}  |  {item['display_path']}": item for item in artifacts}
    selected_label = st.selectbox(label, list(options.keys()), key=key)
    selected = options[selected_label]
    return selected, read_json_file(selected["path"])


def render_artifact_downloads(path: Path, key_prefix: str):
    if path.suffix.lower() == ".json":
        st.download_button(
            "Download JSON",
            data=path.read_text(encoding="utf-8"),
            file_name=path.name,
            mime="application/json",
            key=f"{key_prefix}_download_json",
        )
    else:
        st.download_button(
            "Download file",
            data=path.read_text(encoding="utf-8", errors="replace"),
            file_name=path.name,
            mime="text/plain",
            key=f"{key_prefix}_download_file",
        )


def render_operations_overview(container: st.delta_generator.DeltaGenerator, compact: bool):
    with container.container():
        runs = discover_encode_runs()
        contracts = discover_contract_files()
        reports = discover_report_files()
        state_snapshots = discover_state_snapshot_files()
        visual_states = discover_visual_world_state_files()
        prompt_packs = discover_prompt_pack_files()
        retrieval_contexts = discover_retrieval_context_files()
        latest_run = runs[0] if runs else None

        st.subheader("Operations Overview")
        cols = st.columns(5)
        cols[0].metric("Encode runs", len(runs), latest_run["status"] if latest_run else "none")
        cols[1].metric("Contracts", len(contracts), "file-backed")
        cols[2].metric("Reports", len(reports), "audits + markdown")
        cols[3].metric("State snapshots", len(state_snapshots), "target-aware")
        cols[4].metric("Prompt packs", len(prompt_packs), "ComfyUI-ready")

        cols = st.columns(4)
        cols[0].metric("Visual world states", len(visual_states), "real artifacts")
        cols[1].metric("Retrieval contexts", len(retrieval_contexts), "validation")
        cols[2].metric("Current pipeline status", st.session_state.get("latest_status") or "Idle")
        cols[3].metric("Neo4j status", "Planned", "viewer mock wired")

        if latest_run:
            render_chip_row([
                (f"Latest series: {latest_run['series_id']}", "good"),
                (f"Run: {latest_run['run_id']}", "good"),
                (f"Contracts: {latest_run['contract_count']}", "good"),
                (f"Reports: {latest_run['report_count']}", "warn" if latest_run["report_count"] == 0 else "good"),
            ])
            st.dataframe(
                [{
                    "series": latest_run["series_id"],
                    "run_id": latest_run["run_id"],
                    "status": latest_run["status"],
                    "books": latest_run["book_count"],
                    "completed": latest_run["completed_books"],
                    "failed": latest_run["failed_books"],
                    "started_at": latest_run["started_at"],
                    "updated_at": latest_run["updated_at"],
                }],
                width="stretch",
            )
        else:
            st.info("No persisted encode runs found under analysis_outputs/pipeline_runtime yet.")

        st.caption("Operational milestone status")
        st.dataframe(
            [
                {"section": "Overview", "status": "real data"},
                {"section": "Encode Runs", "status": "real data"},
                {"section": "Book Analysis Viewer", "status": "real data"},
                {"section": "Identity Viewer", "status": "real data"},
                {"section": "Character States", "status": "real data"},
                {"section": "Visual World State", "status": "real data"},
                {"section": "ComfyUI Prompt Packs", "status": "real data"},
                {"section": "Retrieval Context", "status": "real data"},
                {"section": "Neo4j Ops", "status": "mock / backend hooks next"},
                {"section": "Analysis Config", "status": "current controls + preset mock"},
                {"section": "Decoder Workspace", "status": "current blueprint hooks"},
                {"section": "Reports", "status": "real data"},
            ],
            width="stretch",
        )

        if compact:
            st.caption("The operational tabs stay readable during live pipeline runs, while the legacy tabs keep the scene-level debug detail.")


def render_encode_runs_dashboard(container: st.delta_generator.DeltaGenerator):
    with container.container():
        st.subheader("Encode Runs")
        runs = discover_encode_runs()
        if not runs:
            st.info("No encode runs found under analysis_outputs/pipeline_runtime.")
            return

        series_filter = st.selectbox(
            "Series filter",
            ["All"] + sorted({run["series_id"] for run in runs}),
            key="ops_encode_series_filter",
        )
        status_filter = st.selectbox(
            "Status filter",
            ["All"] + sorted({run["status"] for run in runs}),
            key="ops_encode_status_filter",
        )
        filtered = [
            run for run in runs
            if (series_filter == "All" or run["series_id"] == series_filter)
            and (status_filter == "All" or run["status"] == status_filter)
        ]
        st.dataframe(
            [
                {
                    "series": run["series_id"],
                    "run_id": run["run_id"],
                    "status": run["status"],
                    "books": run["book_count"],
                    "completed": run["completed_books"],
                    "failed": run["failed_books"],
                    "contracts": run["contract_count"],
                    "reports": run["report_count"],
                    "started_at": run["started_at"],
                }
                for run in filtered
            ],
            width="stretch",
        )
        if not filtered:
            st.warning("No runs match the current filters.")
            return

        option_map = {f"{run['series_id']} / {run['run_id']}": run for run in filtered}
        selected = option_map[st.selectbox("Open run", list(option_map.keys()), key="ops_encode_selected_run")]
        cols = st.columns(4)
        cols[0].metric("Requested books", selected["total_requested"])
        cols[1].metric("Contracts", selected["contract_count"])
        cols[2].metric("Reports", selected["report_count"])
        cols[3].metric("Remaining", selected["remaining_books"])
        st.caption(selected["display_path"])
        st.json(selected["latest_status"] or selected["status_data"])
        st.dataframe(selected["status_data"].get("books") or [], width="stretch")


def render_book_analysis_dashboard(container: st.delta_generator.DeltaGenerator):
    with container.container():
        st.subheader("Book Analysis Viewer")
        selected, contract = load_selected_json_artifact(discover_contract_files(), "Contract", "ops_contract_select")
        if not selected:
            return
        summary = build_contract_summary(contract)
        cols = st.columns(5)
        cols[0].metric("Chapters", summary["chapter_count"])
        cols[1].metric("Scenes", summary["scene_count"])
        cols[2].metric("Timeline", summary["timeline_count"])
        cols[3].metric("Profiles", summary["character_profile_count"])
        cols[4].metric("Aliases", summary["alias_count"])
        st.caption(selected["display_path"])
        render_artifact_downloads(selected["path"], "contract_viewer")

        outputs = contract.get("outputs") or {}
        query = (st.text_input("Search character/entity/location/event", key="ops_contract_search") or "").strip().lower()
        scenes = outputs.get("scene_analyses") or outputs.get("scenes") or []
        profiles = outputs.get("character_profiles") or []
        timeline_rows = outputs.get("timeline") or []
        diagnostics = contract.get("diagnostics") or {}

        scene_rows = [
            {
                "scene_id": scene.get("scene_id", ""),
                "chapter": scene.get("chapter_index", ""),
                "summary": scene.get("scene_summary", ""),
                "entities": ", ".join(scene.get("entities_present") or []),
                "events": len(scene.get("events") or []),
                "state_changes": len(scene.get("state_changes") or []),
            }
            for scene in scenes
            if not query or query in json.dumps(scene, ensure_ascii=False).lower()
        ]
        profile_rows = [
            {
                "character": profile.get("character") or profile.get("display_name") or "",
                "aliases": ", ".join(profile.get("aliases") or []),
                "event_count": len(profile.get("events") or profile.get("recent_key_events") or []),
                "state": json.dumps(profile.get("latest_state") or profile.get("canon_state") or {}, ensure_ascii=False),
            }
            for profile in profiles
            if not query or query in json.dumps(profile, ensure_ascii=False).lower()
        ]
        timeline_filtered = [
            row for row in timeline_rows
            if not query or query in json.dumps(row, ensure_ascii=False).lower()
        ]

        scene_tab, profile_tab, timeline_tab, diagnostic_tab, raw_tab = st.tabs(
            ["Scenes", "Profiles", "Timeline", "Diagnostics", "Raw JSON"]
        )
        with scene_tab:
            st.dataframe(scene_rows[:200], width="stretch")
        with profile_tab:
            st.dataframe(profile_rows[:200], width="stretch")
        with timeline_tab:
            st.dataframe(timeline_filtered[:200], width="stretch")
        with diagnostic_tab:
            st.json(diagnostics)
        with raw_tab:
            st.json(contract)


def render_identity_dashboard(container: st.delta_generator.DeltaGenerator):
    with container.container():
        st.subheader("Identity Viewer")
        selected, identity = load_selected_json_artifact(discover_identity_files(), "Identity JSON", "ops_identity_select")
        if not selected:
            return

        compare_artifacts = discover_identity_files()
        compare_options = {"None": None}
        for item in compare_artifacts:
            if item["path"] != selected["path"]:
                compare_options[f"{item['name']}  |  {item['display_path']}"] = item
        compare_choice = st.selectbox("Compare against", list(compare_options.keys()), key="ops_identity_compare")
        compare_data = read_json_file(compare_options[compare_choice]["path"]) if compare_options[compare_choice] else None

        alias_index = identity.get("alias_index") or identity.get("alias_map") or {}
        narrator = identity.get("narrator") or {}
        risky_aliases = identity.get("risky_aliases") or identity.get("diagnostics", {}).get("risky_aliases") or []
        suppressed = identity.get("suppressed_clusters") or identity.get("diagnostics", {}).get("suppressed_clusters") or []

        cols = st.columns(4)
        cols[0].metric("Alias entries", len(alias_index))
        cols[1].metric("Risky aliases", len(risky_aliases))
        cols[2].metric("Suppressed clusters", len(suppressed))
        cols[3].metric("Narrator confidence", narrator.get("confidence", "n/a"))
        st.caption(selected["display_path"])
        if compare_data:
            st.info(
                f"Comparison loaded: alias entries {len(alias_index)} vs {len(compare_data.get('alias_index') or compare_data.get('alias_map') or {})}"
            )
        st.json({"narrator": narrator, "alias_index_sample": dict(list(alias_index.items())[:50])})
        if risky_aliases:
            st.dataframe(risky_aliases[:100], width="stretch")
        else:
            st.caption("No explicit risky aliases field found in this identity artifact.")


def render_character_state_dashboard(container: st.delta_generator.DeltaGenerator):
    with container.container():
        st.subheader("Character State Viewer")
        selected, snapshot = load_selected_json_artifact(
            discover_state_snapshot_files(),
            "State snapshot",
            "ops_state_snapshot_select",
        )
        if not selected:
            return
        states = snapshot.get("character_states") or []
        target = snapshot.get("target_point") or {}
        cols = st.columns(4)
        cols[0].metric("Characters", len(states))
        cols[1].metric("Target mode", target.get("mode", "n/a"))
        cols[2].metric("After book", target.get("after_book_index", "n/a"))
        cols[3].metric("Future facts", str(target.get("include_future_facts", False)))
        st.caption(selected["display_path"])
        search = (st.text_input("Filter characters", key="ops_state_filter") or "").strip().lower()
        filtered = [item for item in states if not search or search in json.dumps(item, ensure_ascii=False).lower()]
        if not filtered:
            st.warning("No character states match the current filter.")
            return
        state_map = {item.get("display_name") or item.get("character_id") or f"character_{idx}": item for idx, item in enumerate(filtered)}
        selected_name = st.selectbox("Character", list(state_map.keys()), key="ops_state_character_select")
        selected_state = state_map[selected_name]
        st.json(selected_state)
        render_artifact_downloads(selected["path"], "state_snapshot")


def render_visual_world_state_dashboard(container: st.delta_generator.DeltaGenerator):
    with container.container():
        st.subheader("Visual World-State Viewer")
        selected, visual_state = load_selected_json_artifact(
            discover_visual_world_state_files(),
            "Visual world-state JSON",
            "ops_visual_state_select",
        )
        if not selected:
            return
        diagnostics = visual_state.get("diagnostics") or {}
        cols = st.columns(4)
        cols[0].metric("Character states", len(visual_state.get("character_visual_states") or []))
        cols[1].metric("Entity states", len(visual_state.get("entity_visual_states") or []))
        cols[2].metric("Location states", len(visual_state.get("location_visual_states") or []))
        cols[3].metric("Noisy entries", len(diagnostics.get("noisy_entries_flagged") or []))
        search = (st.text_input("Filter visual entries", key="ops_visual_filter") or "").strip().lower()
        confidence_filter = st.selectbox("Confidence", ["All", "high", "medium", "low"], key="ops_visual_confidence")
        category = st.selectbox(
            "Category",
            ["character_visual_states", "entity_visual_states", "location_visual_states"],
            key="ops_visual_category",
        )
        rows = []
        for item in visual_state.get(category) or []:
            confidence = item.get("confidence", "low")
            if confidence_filter != "All" and confidence != confidence_filter:
                continue
            if search and search not in json.dumps(item, ensure_ascii=False).lower():
                continue
            rows.append(item)
        st.dataframe(
            [{
                "name": item.get("display_name") or item.get("character_id") or item.get("entity_id") or item.get("location_id"),
                "confidence": item.get("confidence", ""),
                "risk_flags": ", ".join(item.get("risk_flags") or []),
            } for item in rows[:200]],
            width="stretch",
        )
        if rows:
            choice_map = {
                (item.get("display_name") or item.get("character_id") or item.get("entity_id") or item.get("location_id")): item
                for item in rows
            }
            selected_name = st.selectbox("Open visual entry", list(choice_map.keys()), key="ops_visual_entry_select")
            st.json(choice_map[selected_name])
        render_artifact_downloads(selected["path"], "visual_world_state")


def render_prompt_pack_dashboard(container: st.delta_generator.DeltaGenerator):
    with container.container():
        st.subheader("ComfyUI Prompt Pack Viewer")
        selected, prompt_pack = load_selected_json_artifact(
            discover_prompt_pack_files(),
            "Prompt pack JSON",
            "ops_prompt_pack_select",
        )
        if not selected:
            return
        prompts = prompt_pack.get("prompt_packs") or {}
        category = st.selectbox(
            "Prompt category",
            ["characters", "locations", "objects", "scenes"],
            key="ops_prompt_category",
        )
        items = prompts.get(category) or []
        cols = st.columns(4)
        cols[0].metric("Characters", len(prompts.get("characters") or []))
        cols[1].metric("Locations", len(prompts.get("locations") or []))
        cols[2].metric("Objects", len(prompts.get("objects") or []))
        cols[3].metric("Scenes", len(prompts.get("scenes") or []))
        confidence_filter = st.selectbox("Confidence", ["All", "high", "medium", "low"], key="ops_prompt_confidence")
        filtered = [
            item for item in items
            if confidence_filter == "All" or item.get("confidence", "high") == confidence_filter
        ]
        if not filtered:
            st.warning("No prompts match the current category/confidence filter.")
            return
        item_map = {
            item.get("display_name") or item.get("title") or item.get("character_id") or item.get("scene_key") or f"item_{idx}": item
            for idx, item in enumerate(filtered)
        }
        selected_name = st.selectbox("Open prompt", list(item_map.keys()), key="ops_prompt_item_select")
        selected_item = item_map[selected_name]
        st.json(selected_item)
        render_artifact_downloads(selected["path"], "prompt_pack")


def render_retrieval_context_dashboard(container: st.delta_generator.DeltaGenerator):
    with container.container():
        st.subheader("Retrieval Context Viewer")
        selected, retrieval = load_selected_json_artifact(
            discover_retrieval_context_files(),
            "Retrieval / generation context JSON",
            "ops_retrieval_context_select",
        )
        if not selected:
            return
        meta = retrieval.get("context_meta") or {}
        compiled = retrieval.get("compiled_context") or {}
        cols = st.columns(4)
        cols[0].metric("Retrieval type", meta.get("retrieval_type", "n/a"))
        cols[1].metric("Book set", len(meta.get("book_titles") or []))
        cols[2].metric("Characters", len(compiled.get("characters") or []))
        cols[3].metric("Reference entities", len(compiled.get("reference_entities") or []))
        st.caption(selected["display_path"])
        st.text_area("User prompt", compiled.get("user_prompt", ""), height=90, key="ops_retrieval_user_prompt")
        st.json({"context_meta": meta, "story_ending": compiled.get("story_ending") or {}, "narrator": compiled.get("narrator") or {}})
        render_artifact_downloads(selected["path"], "retrieval_context")


def render_neo4j_dashboard(container: st.delta_generator.DeltaGenerator):
    with container.container():
        st.subheader("Neo4j Browser / Ingest Manager")
        st.info("This tab is the first operational scaffold. Neo4j browsing and deletion confirmation are intentionally not wired yet.")
        cols = st.columns(4)
        for idx, (label, value) in enumerate(MOCK_NEO4J_COUNTS.items()):
            cols[idx % 4].metric(label, value)
        st.dataframe(
            [
                {"operation": "Connection check", "status": "planned"},
                {"operation": "Series/book listing", "status": "planned"},
                {"operation": "Graph summary", "status": "planned"},
                {"operation": "Dry-run delete", "status": "must require confirmation"},
                {"operation": "Confirm delete", "status": "blocked until dry-run payload + typed ID"},
            ],
            width="stretch",
        )
        st.code(
            "Dry-run delete rules:\n"
            "- show exact series/book ID\n"
            "- show node counts to remove\n"
            "- require typed confirmation before real delete\n"
            "- never delete local contracts unless selected separately"
        )


def render_analysis_config_dashboard(container: st.delta_generator.DeltaGenerator):
    with container.container():
        st.subheader("Analysis Configuration")
        preset = st.selectbox(
            "Preset mock",
            [item["name"] for item in MOCK_CONFIG_PRESETS],
            key="ops_config_preset_select",
        )
        st.caption(f"Selected preset: {preset}")
        config_snapshot = {
            "analysis_model": st.session_state.get("analysis_model"),
            "identity_model": st.session_state.get("identity_model"),
            "identity_provider": st.session_state.get("identity_provider"),
            "identity_strategy": "booknlp_clean",
            "analysis_mode": st.session_state.get("analysis_mode"),
            "target_scene_words": st.session_state.get("target_scene_words"),
            "scene_failure_policy": "fail_fast",
            "max_failed_scenes_absolute": 3,
            "max_failed_scene_ratio": 0.1,
            "min_nonempty_scene_ratio": 0.8,
            "max_parallel_books": 1,
            "skip_ingest": True,
        }
        st.json(config_snapshot)
        st.caption("Preset save/load APIs are not wired yet. The current sidebar still acts as the live source of truth.")


def render_decoder_workspace_dashboard(container: st.delta_generator.DeltaGenerator):
    with container.container():
        st.subheader("Decoder / Generation Workspace")
        contracts = discover_contract_files()
        selected_contracts = st.multiselect(
            "Selected contracts",
            [item["name"] for item in contracts[:20]],
            default=[item["name"] for item in contracts[:1]],
            key="ops_decoder_contracts",
        )
        st.dataframe(
            [
                {"field": "Target mode", "value": st.session_state.get("sequel_canon_position")},
                {"field": "Generation model", "value": st.session_state.get("sequel_model")},
                {"field": "Target scene words", "value": st.session_state.get("target_scene_words")},
                {"field": "Selected contracts", "value": len(selected_contracts)},
            ],
            width="stretch",
        )
        st.text_area("Generation prompt", st.session_state.get("sequel_prompt") or "", height=120, key="ops_decoder_prompt")
        if st.session_state.get("sequel_blueprint_result"):
            st.success("Narrative blueprint available from the current contract.")
            st.json(st.session_state["sequel_blueprint_result"])
        else:
            st.info("Long-form decoder runs are intentionally not first in scope. The current dashboard already exposes blueprint generation as the first backend hook.")


def render_reports_dashboard(container: st.delta_generator.DeltaGenerator):
    with container.container():
        st.subheader("Reports")
        reports = discover_report_files()
        if not reports:
            st.info("No reports found yet.")
            return
        options = {f"{item['name']}  |  {item['display_path']}": item for item in reports}
        selected = options[st.selectbox("Report", list(options.keys()), key="ops_report_select")]
        st.caption(selected["display_path"])
        render_artifact_downloads(selected["path"], "report_viewer")
        if selected["path"].suffix.lower() == ".md":
            st.markdown(read_text_file(selected["path"]))
        elif selected["path"].suffix.lower() == ".json":
            st.json(read_json_file(selected["path"]))
        else:
            st.text(read_text_file(selected["path"]))


def render_all(placeholders: Dict[str, st.delta_generator.DeltaGenerator], compact: bool):
    render_operations_overview(placeholders["overview"], compact)
    render_encode_runs_dashboard(placeholders["encode_runs"])
    render_book_analysis_dashboard(placeholders["analysis_viewer"])
    render_identity_dashboard(placeholders["identity_viewer"])
    render_character_state_dashboard(placeholders["character_states_viewer"])
    render_visual_world_state_dashboard(placeholders["visual_world_state_viewer"])
    render_prompt_pack_dashboard(placeholders["prompt_pack_viewer"])
    render_retrieval_context_dashboard(placeholders["retrieval_context_viewer"])
    render_neo4j_dashboard(placeholders["neo4j_viewer"])
    render_analysis_config_dashboard(placeholders["analysis_config_viewer"])
    render_decoder_workspace_dashboard(placeholders["decoder_workspace_viewer"])
    render_reports_dashboard(placeholders["reports_viewer"])
    render_status(placeholders["status"], compact)
    render_books(placeholders["books"], st.session_state.get("book_inputs") or [])
    render_chapters(placeholders["chapters"], st.session_state.get("chapters") or [], compact)
    render_scenes(placeholders["scenes"], st.session_state.get("scene_analyses") or [], compact)
    render_entity_registry(placeholders["entities"], st.session_state.get("entity_registry") or [], compact)
    render_state_result(placeholders["state"], st.session_state.get("state_result") or {"transitions": [], "latest_state": []}, compact)
    render_canon_snapshot(placeholders["snapshot"], st.session_state.get("canon_snapshot") or [], compact)
    render_timeline(placeholders["timeline"], st.session_state.get("timeline") or [], compact)
    render_event_ledger(placeholders["event_ledger"], st.session_state.get("event_ledger") or [], compact)
    render_character_timelines(placeholders["characters"], st.session_state.get("character_timelines") or [], compact)
    render_alias_map(placeholders["aliases"], st.session_state.get("identity_result") or {"alias_map": {}, "rejected_non_characters": [], "alias_history": []}, compact)
    render_identity_decisions(placeholders["decisions"], st.session_state.get("identity_result") or {"decisions": []}, compact)
    render_causal_graph(placeholders["causal_graph"], st.session_state.get("causal_graph_result") or {"graph": {"events": []}}, compact)
    render_causal_metrics(placeholders["causal_metrics"], st.session_state.get("causal_graph_result") or {"metrics": {}})
    render_story_search(placeholders["search"], st.session_state.get("story_index_result"), compact)
    render_sequel_workspace(placeholders["sequel"], compact)


init_state()
if st.session_state.get("post_run_refresh_pending"):
    st.session_state["post_run_refresh_pending"] = False
inject_dashboard_styles()
st.title("S.A.G.A.")
st.caption("Story Analysis, Generation, and Archives")
st.caption("Operational dashboard first, scene-level debugging second. Live downstream modules still refresh as each scene finishes.")
overview_tab, encode_runs_tab, analysis_viewer_tab, identity_viewer_tab, character_states_viewer_tab, visual_world_state_viewer_tab, prompt_pack_viewer_tab, retrieval_context_viewer_tab, neo4j_viewer_tab, analysis_config_viewer_tab, decoder_workspace_viewer_tab, reports_viewer_tab, status_tab, books_tab, chapters_tab, scenes_tab, entities_tab, state_tab, snapshot_tab, timeline_tab, event_ledger_tab, characters_tab, aliases_tab, decisions_tab, causal_graph_tab, causal_metrics_tab, search_tab, sequel_tab = st.tabs(
    [
        "Overview",
        "Encode Runs",
        "Book Analysis",
        "Identity Viewer",
        "Character States",
        "Visual World State",
        "Prompt Packs",
        "Retrieval Context",
        "Neo4j Ops",
        "Analysis Config",
        "Decoder Workspace",
        "Reports",
        "Status",
        "Books",
        "Chapters",
        "Scenes",
        "Entity Registry",
        "State Transitions",
        "Canon Snapshot",
        "Timeline",
        "Event Ledger",
        "Character Timelines",
        "Alias Map",
        "Identity Decisions",
        "Causal Graph",
        "Causal Metrics",
        "Story Search",
        "Narrative",
    ]
)
placeholders = {
    "overview": overview_tab.empty(),
    "encode_runs": encode_runs_tab.empty(),
    "analysis_viewer": analysis_viewer_tab.empty(),
    "identity_viewer": identity_viewer_tab.empty(),
    "character_states_viewer": character_states_viewer_tab.empty(),
    "visual_world_state_viewer": visual_world_state_viewer_tab.empty(),
    "prompt_pack_viewer": prompt_pack_viewer_tab.empty(),
    "retrieval_context_viewer": retrieval_context_viewer_tab.empty(),
    "neo4j_viewer": neo4j_viewer_tab.empty(),
    "analysis_config_viewer": analysis_config_viewer_tab.empty(),
    "decoder_workspace_viewer": decoder_workspace_viewer_tab.empty(),
    "reports_viewer": reports_viewer_tab.empty(),
    "status": status_tab.empty(),
    "books": books_tab.empty(),
    "chapters": chapters_tab.empty(),
    "scenes": scenes_tab.empty(),
    "entities": entities_tab.empty(),
    "state": state_tab.empty(),
    "snapshot": snapshot_tab.empty(),
    "timeline": timeline_tab.empty(),
    "event_ledger": event_ledger_tab.empty(),
    "characters": characters_tab.empty(),
    "aliases": aliases_tab.empty(),
    "decisions": decisions_tab.empty(),
    "causal_graph": causal_graph_tab.empty(),
    "causal_metrics": causal_metrics_tab.empty(),
    "search": search_tab.empty(),
    "sequel": sequel_tab.empty(),
}

with st.sidebar:
    st.header("Controls")
    if st.session_state.get("book_order_editor") is None and "book_order_editor" in st.session_state:
        del st.session_state["book_order_editor"]
    uploaded_files = st.file_uploader("Upload one or more books", type=["epub", "pdf"], accept_multiple_files=True)
    if uploaded_files:
        uploaded_books = save_uploaded_books(uploaded_files)
        if uploaded_books:
            order_rows = [
                {"order": index, "title": item.get("title") or Path(item["path"]).name, "type": item["type"], "path": item["path"]}
                for index, item in enumerate(uploaded_books, start=1)
            ]
            edited_rows = st.data_editor(order_rows, num_rows="fixed", width="stretch", key="book_order_editor")
            st.session_state["book_order_rows"] = edited_rows
        else:
            st.session_state["book_order_rows"] = []
            st.error("The uploaded files are not supported. Please upload EPUB or PDF books.")
    else:
        st.session_state["book_order_rows"] = []
        st.info("Upload one or more EPUB or PDF books to begin.")

    st.selectbox("Scene analysis model", MODEL_OPTIONS, key="analysis_model")
    st.selectbox("Identity model", MODEL_OPTIONS, key="identity_model")
    st.selectbox("Identity source", ["booknlp_clean"], key="identity_provider")
    st.text_input("Identity JSON path", key="identity_json_path")
    st.caption("Production mode: BookNLP-clean identity is the active source of truth.")
    st.selectbox("Analysis mode", ["structured", "tool", "compare"], key="analysis_mode")
    st.selectbox("Generation model", MODEL_OPTIONS, key="sequel_model")
    st.text_area(
        "Generation prompt",
        key="sequel_prompt",
        height=110,
        help="Used only when generating a narrative blueprint from the current contract.",
    )
    sequel_catalog = build_generation_option_catalog()
    character_options = [""] + (sequel_catalog.get("character_options") or [])
    event_options = sequel_catalog.get("event_options") or []
    relationship_type_options = sequel_catalog.get("relationship_type_options") or sorted(
        NarrativeGenerationService.ALLOWED_RELATIONSHIP_TYPES
    )
    st.number_input("Target chapters", min_value=1, max_value=80, key="sequel_chapter_count")
    st.selectbox(
        "Canon position",
        ["pre_canon", "mid_canon_insert", "mid_canon_divergent", "post_canon"],
        key="sequel_canon_position",
        help="Choose whether the new story happens before canon, inserts within canon, branches from canon midstream, or continues after canon.",
    )
    st.selectbox(
        "Primary POV character",
        character_options,
        key="sequel_primary_pov_character",
        help="Optional primary viewpoint character to keep chapter outlines anchored to one lead perspective.",
    )
    st.text_area(
        "New plot to introduce",
        key="sequel_new_plot",
        height=80,
        help="Optional new plotline you want the generated book to introduce.",
    )
    st.number_input(
        "Relationship goals",
        min_value=0,
        max_value=8,
        key="sequel_relationship_target_count",
        help="How many relationship trajectories you want to steer in this generation.",
    )
    for index in range(int(st.session_state.get("sequel_relationship_target_count") or 0)):
        render_panel(f"Relationship Goal {index + 1}", "Select the characters, relationship type, and target direction.")
        left_col, right_col = st.columns(2)
        with left_col:
            st.selectbox(
                f"Character A {index + 1}",
                character_options,
                key=f"sequel_relationship_{index}_char_a",
            )
            st.selectbox(
                f"Relationship type {index + 1}",
                relationship_type_options,
                key=f"sequel_relationship_{index}_type",
            )
        with right_col:
            st.selectbox(
                f"Character B {index + 1}",
                character_options,
                key=f"sequel_relationship_{index}_char_b",
            )
            st.text_input(
                f"Desired direction {index + 1}",
                key=f"sequel_relationship_{index}_direction",
                help="Examples: rebuild trust, slide toward romance, become political rivals.",
            )
        st.text_input(
            f"Relationship notes {index + 1}",
            key=f"sequel_relationship_{index}_notes",
            help="Optional extra constraint or payoff for this relationship arc.",
        )
    st.text_input(
        "Continuity anchor",
        key="sequel_continuity_anchor",
        help="Free-text rule for where the new story must fit relative to canon.",
    )
    st.selectbox(
        "Anchor after",
        [""] + event_options,
        key="sequel_anchor_after_label",
        help="Optional canon event that should precede the new story.",
    )
    st.selectbox(
        "Anchor before",
        [""] + event_options,
        key="sequel_anchor_before_label",
        help="Optional canon event that should still happen after this story.",
    )
    if st.session_state.get("sequel_canon_position") == "mid_canon_divergent":
        st.selectbox(
            "Divergence anchor",
            [""] + event_options,
            key="sequel_divergence_anchor_label",
            help="The canon event where the rewritten branch begins.",
        )
        st.multiselect(
            "Canon events or facts to preserve",
            event_options,
            key="sequel_preserve_event_labels",
            help="Select canon beats that should survive even after the branch diverges.",
        )
    else:
        st.selectbox(
            "Divergence anchor",
            [""] + event_options,
            key="sequel_divergence_anchor_label",
            help="Only used for divergent mid-canon generation.",
        )
        st.multiselect(
            "Canon events or facts to preserve",
            event_options,
            key="sequel_preserve_event_labels",
            help="Optional preserved canon beats to keep visible in the generated branch.",
        )
    st.slider("Target scene size (words)", min_value=0, max_value=5000, key="target_scene_words")
    if st.session_state["target_scene_words"] == 0:
        st.caption("Scene size 0 means one full chapter per scene.")
    else:
        st.caption("Chunks can span chapter boundaries when the target size is larger than a single chapter.")

    run_clicked = st.button("Run Pipeline", width="stretch")
    reset_clicked = st.button("Reset Results", width="stretch")

    export_ready = has_exportable_outputs() and not st.session_state.get("pipeline_running")
    sequel_blueprint_clicked = st.button(
        "Generate Narrative Blueprint",
        width="stretch",
        disabled=not export_ready,
        help="Build narrative context from the current contract and generate a planning blueprint without leaving the dashboard. Full long-form generation stays CLI-only.",
    )
    st.download_button(
        label="Export JSON Contract",
        data=export_contract_json() if has_exportable_outputs() else "{}",
        file_name="saga_contract.json",
        mime="application/json",
        width="stretch",
        key="sidebar_export_json_contract",
        disabled=not export_ready,
    )
    if not has_exportable_outputs():
        st.caption("Run the pipeline to enable JSON export.")
    elif st.session_state.get("pipeline_running"):
        st.caption("JSON export will be enabled when the current run finishes.")
    elif st.session_state.get("sequel_blueprint_result"):
        if st.session_state.get("sequel_context_result"):
            st.download_button(
                label="Download Narrative Context",
                data=json.dumps(st.session_state["sequel_context_result"], ensure_ascii=False, indent=2),
                file_name="saga_narrative_context.json",
                mime="application/json",
                width="stretch",
                key="sidebar_export_narrative_context",
            )
        st.download_button(
            label="Download Narrative Blueprint",
            data=json.dumps(st.session_state["sequel_blueprint_result"], ensure_ascii=False, indent=2),
            file_name="saga_narrative_blueprint.json",
            mime="application/json",
            width="stretch",
            key="sidebar_export_narrative_blueprint",
        )

    if reset_clicked:
        reset_pipeline_outputs()

    if sequel_blueprint_clicked and export_ready:
        try:
            st.session_state["latest_status"] = "Building narrative blueprint..."
            render_all(placeholders, compact=True)
            st.session_state["last_live_render_at"] = time.perf_counter()
            contract = build_export_contract()
            sequel_context, blueprint = build_sequel_blueprint_from_contract(
                contract,
                st.session_state.get("sequel_prompt") or "",
                st.session_state.get("sequel_model") or NarrativeGenerationService.DEFAULT_NARRATIVE_MODEL_MODE,
                build_dashboard_generation_controls(),
            )
            st.session_state["sequel_context_result"] = sequel_context
            st.session_state["sequel_blueprint_result"] = blueprint
            st.session_state["latest_status"] = "Narrative blueprint ready."
            logging.info(
                "Narrative blueprint ready | title=%s | chapters=%s | acts=%s",
                blueprint.get("title", ""),
                blueprint.get("total_chapters", 0),
                len(blueprint.get("acts") or []),
            )
            render_all(placeholders, compact=False)
        except Exception as exc:
            logging.error("Narrative blueprint generation failed | error=%s", repr(exc))
            st.session_state["latest_status"] = f"Narrative blueprint failed: {exc}"
            st.error(f"Narrative blueprint generation failed: {exc}")
            render_all(placeholders, compact=False)

if reset_clicked:
    render_all(placeholders, compact=False)
else:
    st.session_state["book_inputs"] = resolve_book_inputs()
    render_all(placeholders, compact=False)

if run_clicked:
    reset_pipeline_outputs()
    st.session_state["pipeline_running"] = True
    st.session_state["book_inputs"] = resolve_book_inputs()
    if not st.session_state["book_inputs"]:
        st.session_state["pipeline_running"] = False
        st.session_state["latest_status"] = "No books selected."
        st.error("No books selected. Upload one or more EPUB or PDF files before running the pipeline.")
        render_all(placeholders, compact=False)
        st.stop()
    st.session_state["run_started_at"] = time.perf_counter()
    st.session_state["latest_status"] = "Loading chapters..."
    render_all(placeholders, compact=True)
    st.session_state["last_live_render_at"] = time.perf_counter()

    chapters = build_chapters(st.session_state["book_inputs"], st.session_state["analysis_model"])
    st.session_state["chapters"] = chapters
    st.session_state["latest_status"] = "Resolving character identities..."
    render_all(placeholders, compact=True)
    st.session_state["last_live_render_at"] = time.perf_counter()

    try:
        identity_result = run_identity_resolution(st.session_state["book_inputs"])
        st.session_state["identity_result"] = identity_result
        logging.info(
            "Identity result ready | aliases=%s | rejected=%s | decisions=%s",
            len(identity_result.get("alias_map") or {}),
            len(identity_result.get("rejected_non_characters") or []),
            len(identity_result.get("decisions") or []),
        )
    except Exception as exc:
        logging.error("Identity resolution failed at pipeline level | error=%s", repr(exc))

    base_extractor = SceneExtractor.from_target_words(st.session_state["target_scene_words"])
    planned_scenes = base_extractor.extract_many(chapters, allow_cross_chapter=True)
    st.session_state["estimated_total_scenes"] = len(planned_scenes)
    render_all(placeholders, compact=True)
    st.session_state["last_live_render_at"] = time.perf_counter()

    progress = st.sidebar.progress(0.0)
    total_scenes = len(planned_scenes)

    for scene_position, planned_scene in enumerate(planned_scenes, start=1):
        chapter_label = f"Chapter {planned_scene['chapter_index']}"
        if planned_scene.get("end_chapter_index") and planned_scene["end_chapter_index"] != planned_scene["chapter_index"]:
            chapter_label = f"Chapters {planned_scene['chapter_index']}-{planned_scene['end_chapter_index']}"
        st.session_state["latest_status"] = f"Processing scene {scene_position}/{total_scenes}: {chapter_label}"
        logging.info(
            "Scene analysis started | position=%s/%s | book=%s | chapter=%s | end_chapter=%s | scene=%s | target_words=%s",
            scene_position,
            total_scenes,
            planned_scene["book_index"],
            planned_scene["chapter_index"],
            planned_scene.get("end_chapter_index", planned_scene["chapter_index"]),
            planned_scene["scene_index"],
            st.session_state["target_scene_words"],
        )
        analyzed_scenes, attempted_targets = analyze_scene_with_fallback(
            planned_scene,
            st.session_state["target_scene_words"],
            st.session_state["analysis_model"],
            st.session_state["identity_model"],
            st.session_state["analysis_mode"],
            st.session_state["identity_result"],
            st.session_state["state_result"],
            st.session_state["resolved_scene_analyses"],
        )

        for scene_analysis in analyzed_scenes:
            scene_analysis["fallback_targets"] = attempted_targets
            apply_identity_updates(scene_analysis, st.session_state["identity_result"])
            st.session_state["scene_analyses"].append(scene_analysis)
            st.session_state["resolved_scene_analyses"] = rebuild_resolved_scene_analyses(
                st.session_state["scene_analyses"],
                st.session_state["identity_result"],
            )

            st.session_state["entity_registry"] = build_entity_registry(st.session_state["resolved_scene_analyses"])
            st.session_state["state_result"] = build_state_result(st.session_state["resolved_scene_analyses"])
            st.session_state["timeline"] = build_timeline(st.session_state["resolved_scene_analyses"])
            st.session_state["event_ledger"] = build_event_ledger(
                st.session_state["resolved_scene_analyses"],
                st.session_state["timeline"],
                st.session_state.get("causal_graph_result") or {},
            )
            st.session_state["character_timelines"] = build_character_timelines(st.session_state["timeline"])
            st.session_state["character_timelines"] = normalize_character_timelines(
                st.session_state["character_timelines"],
                st.session_state["identity_result"],
            )
            st.session_state["character_profiles"] = build_formal_character_profiles(
                st.session_state["character_timelines"],
                st.session_state["entity_registry"],
                st.session_state["state_result"],
                st.session_state["identity_result"],
                st.session_state["resolved_scene_analyses"],
            )
            st.session_state["processed_scene_count"] = len(st.session_state["scene_analyses"])
            st.session_state["last_scene_seconds"] = float(scene_analysis.get("analysis_duration_seconds") or 0.0)
            processed = max(st.session_state["processed_scene_count"], 1)
            total_elapsed = time.perf_counter() - float(st.session_state.get("run_started_at") or 0.0)
            st.session_state["elapsed_seconds"] = round(total_elapsed, 2)
            st.session_state["avg_scene_seconds"] = round(total_elapsed / processed, 2)
            current_chapter_label = f"Chapter {scene_analysis['chapter_index']}"
            if scene_analysis.get("end_chapter_index") and scene_analysis["end_chapter_index"] != scene_analysis["chapter_index"]:
                current_chapter_label = f"Chapters {scene_analysis['chapter_index']}-{scene_analysis['end_chapter_index']}"
            st.session_state["current_scene_ref"] = f"Book {scene_analysis['book_index']} | {current_chapter_label} | Scene {scene_analysis['scene_index']}"
            st.session_state["latest_scene_summary"] = scene_analysis.get("scene_summary") or "No summary"
            st.session_state["canon_snapshot"] = build_canon_snapshot(
                st.session_state["state_result"],
                (scene_analysis["book_index"], scene_analysis["chapter_index"], scene_analysis["scene_index"]),
            )
            st.session_state["story_index_result"] = build_story_index(
                st.session_state["resolved_scene_analyses"],
                st.session_state["timeline"],
                st.session_state["event_ledger"],
                st.session_state["character_timelines"],
                st.session_state["character_profiles"],
                st.session_state["entity_registry"],
                st.session_state["canon_snapshot"],
                st.session_state["state_result"],
                st.session_state["identity_result"],
            )
            render_all_throttled(placeholders, compact=True)

        logging.info(
            "Scene analysis completed | book=%s | chapter=%s | end_chapter=%s | produced=%s | attempted_targets=%s",
            planned_scene["book_index"],
            planned_scene["chapter_index"],
            planned_scene.get("end_chapter_index", planned_scene["chapter_index"]),
            len(analyzed_scenes),
            attempted_targets,
        )
        if len(analyzed_scenes) != 1:
            st.session_state["estimated_total_scenes"] += len(analyzed_scenes) - 1
        progress.progress(scene_position / total_scenes if total_scenes else 1.0)
        render_all_throttled(placeholders, compact=True, force=True)

    st.session_state["latest_status"] = "Building causal graph..."
    render_all(placeholders, compact=True)
    st.session_state["last_live_render_at"] = time.perf_counter()
    st.session_state["causal_graph_result"] = build_causal_graph(
        st.session_state["timeline"],
        st.session_state["resolved_scene_analyses"],
        st.session_state["analysis_model"],
    )
    st.session_state["event_ledger"] = build_event_ledger(
        st.session_state["resolved_scene_analyses"],
        st.session_state["timeline"],
        st.session_state["causal_graph_result"],
    )
    st.session_state["character_profiles"] = build_formal_character_profiles(
        st.session_state["character_timelines"],
        st.session_state["entity_registry"],
        st.session_state["state_result"],
        st.session_state["identity_result"],
        st.session_state["resolved_scene_analyses"],
    )
    st.session_state["story_index_result"] = build_story_index(
        st.session_state["resolved_scene_analyses"],
        st.session_state["timeline"],
        st.session_state["event_ledger"],
        st.session_state["character_timelines"],
        st.session_state["character_profiles"],
        st.session_state["entity_registry"],
        st.session_state["canon_snapshot"],
        st.session_state["state_result"],
        st.session_state["identity_result"],
    )
    progress.progress(1.0)
    st.session_state["pipeline_running"] = False
    total_elapsed = time.perf_counter() - float(st.session_state.get("run_started_at") or 0.0)
    st.session_state["elapsed_seconds"] = round(total_elapsed, 2)
    graph = (st.session_state.get("causal_graph_result") or {}).get("graph", {})
    if graph.get("error"):
        st.session_state["latest_status"] = f"Pipeline completed with causal-graph issue: {graph.get('error')}"
    elif graph.get("warning"):
        st.session_state["latest_status"] = f"Pipeline completed with warning: {graph.get('warning')}"
    else:
        st.session_state["latest_status"] = "Pipeline completed."
    render_all(placeholders, compact=False)
    st.session_state["post_run_refresh_pending"] = True
    st.rerun()
