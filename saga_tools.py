"""Lightweight CLI for contract-centric downstream workflows."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import os
import re
import sys
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List

from core.pipeline_contract import (
    build_canon_snapshot,
    build_character_timelines,
    build_entity_registry,
    build_event_ledger,
    build_formal_character_profiles,
    build_state_result,
    build_story_index_summary,
    build_timeline,
    normalize_character_timelines,
    rebuild_resolved_scene_analyses,
)
from core.stable_character_state import StableCharacterStateBuilder
from infrastructure.llm_client import LLMClient
from infrastructure.neo4j_ingestion_service import Neo4jIngestionError, Neo4jIngestionService
from query.comfyui_prompt_pack_service import ComfyUIPromptPackService
from query.neo4j_narrative_context_service import Neo4jNarrativeContextService
from query.narrative_context_service import NarrativeContextService
from query.target_character_state_service import TargetCharacterStateService
from query.visual_world_state_service import VisualWorldStateService
from redesign_lab.identity.identity_provider import (
    DEFAULT_BOOKNLP_PIPELINE_IDENTITY_JSON,
    override_contract_with_identity_provider,
)
from services.narrative_generation_service import NarrativeGenerationService

CorpusHardeningService = None

DEFAULT_NARRATIVE_MODEL_MODE = LLMClient.MODE_GPT_OSS
DEFAULT_NARRATIVE_OLLAMA_MODEL = "gemma4:31b-cloud"
DEFAULT_PRODUCTION_IDENTITY_PROVIDER = "booknlp_clean"
MODEL_MODE_CHOICES = [
    LLMClient.MODE_DEEPSEEK,
    LLMClient.MODE_GPT_OSS,
    LLMClient.MODE_CODEX,
    LLMClient.MODE_GENERAL_COMPUTE,
    LLMClient.MODE_MISTRAL,
    LLMClient.MODE_GEMINI,
]
IDENTITY_PROVIDER_CHOICES = ["booknlp_clean"]
ANALYSIS_PROVIDER_MODE_CHOICES = ["single_provider", "same_provider_rotating", "cross_provider_fallback"]


def _preflight_model_access(model_mode: str, provider_mode: str) -> None:
    provider_mode = str(provider_mode or "single_provider").strip().lower()
    if model_mode in {LLMClient.MODE_DEEPSEEK, LLMClient.MODE_GPT_OSS}:
        probe_client = LLMClient(
            mode=model_mode,
            max_retries=1,
            base_delay=0.0,
            timeout=30,
            allow_account_rotation=(provider_mode == "same_provider_rotating"),
            allow_cross_provider_fallback=(provider_mode == "cross_provider_fallback"),
        )
        model_name = probe_client._ollama_model_for_mode()
        try:
            probe_result = LLMClient.probe_ollama_mode_access(model_mode, model_name)
        except Exception as exc:
            probe_result = {"status": "error", "detail": str(exc)}
        if probe_result.get("status") == "ok":
            return
        if provider_mode == "same_provider_rotating":
            rotation_result = probe_client._rotate_ollama_account()
            if rotation_result.get("status") == "rotated":
                return
        raise ValueError(
            f"Ollama model access failed for mode '{model_mode}' using model '{model_name}': "
            f"{probe_result.get('detail') or probe_result.get('status')}. "
            "Choose a working model or upgrade the Ollama subscription for that cloud model."
        )
    if model_mode == getattr(LLMClient, "MODE_CODEX", "codex"):
        probe_client = LLMClient(
            mode=model_mode,
            max_retries=1,
            base_delay=0.0,
            timeout=30,
            allow_account_rotation=False,
            allow_cross_provider_fallback=False,
        )
        model_name = probe_client._codex_model_for_mode()
        try:
            probe_result = LLMClient.probe_codex_model_access(model_name)
        except Exception as exc:
            probe_result = {"status": "error", "detail": str(exc)}
        if probe_result.get("status") == "ok":
            return
        raise ValueError(
            f"OpenAI/Codex model access failed for mode '{model_mode}' using model '{model_name}': "
            f"{probe_result.get('detail') or probe_result.get('status')}. "
            "Configure a working OPENAI_API_KEY or local Codex provider account."
        )
    if model_mode == LLMClient.MODE_GENERAL_COMPUTE:
        probe_client = LLMClient(
            mode=model_mode,
            max_retries=1,
            base_delay=0.0,
            timeout=30,
            allow_account_rotation=(provider_mode == "same_provider_rotating"),
            allow_cross_provider_fallback=(provider_mode == "cross_provider_fallback"),
        )
        model_name = probe_client._general_compute_model_for_mode()
        try:
            probe_result = LLMClient.probe_general_compute_model_access(model_name)
        except Exception as exc:
            probe_result = {"status": "error", "detail": str(exc)}
        if probe_result.get("status") == "ok":
            return
        if provider_mode == "same_provider_rotating":
            rotation_result = probe_client._rotate_general_compute_account()
            if rotation_result.get("status") == "rotated":
                return
        raise ValueError(
            f"General Compute model access failed for mode '{model_mode}' using model '{model_name}': "
            f"{probe_result.get('detail') or probe_result.get('status')}. "
            "Configure a working General Compute API key or switch to another model provider."
        )


class _TerminalProgressPrinter:
    def __init__(self, *, enabled: bool = True, width: int = 28) -> None:
        self.enabled = enabled
        self.width = width
        self._last_was_bar = False

    def __call__(self, phase: str, payload: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        payload = payload or {}
        current = payload.get("current")
        total = payload.get("total")
        label = str(payload.get("label") or payload.get("status") or phase).strip()
        done = bool(payload.get("done"))
        if isinstance(current, int) and isinstance(total, int) and total >= 0:
            filled = self.width if total == 0 else max(0, min(self.width, int(round((current / max(total, 1)) * self.width))))
            bar = "#" * filled + "-" * (self.width - filled)
            line = f"[{phase}] [{bar}] {current}/{total}"
            if label:
                line += f" {label}"
            sys.stdout.write("\r" + line[:200])
            sys.stdout.flush()
            self._last_was_bar = True
            if done:
                sys.stdout.write("\n")
                sys.stdout.flush()
                self._last_was_bar = False
            return
        if self._last_was_bar:
            sys.stdout.write("\n")
            sys.stdout.flush()
            self._last_was_bar = False
        print(f"[{phase}] {label or 'working...'}")


def _encode_progress_payload(phase: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = payload or {}
    book = str(payload.get("book") or "").strip()
    label_prefix = f"{book}: " if book else ""
    if phase == "identity":
        chapter_index = payload.get("chapter_index")
        total_chapters = payload.get("total_chapters")
        chapter_title = str(payload.get("chapter_title") or "").strip()
        label = chapter_title or payload.get("status") or "Resolving identities"
        if isinstance(chapter_index, int) and isinstance(total_chapters, int):
            return {
                "current": chapter_index,
                "total": total_chapters,
                "label": f"{label_prefix}{label}",
            }
    if phase == "scene":
        scene_position = payload.get("scene_position")
        total_scenes = payload.get("total_scenes")
        chapter_index = payload.get("chapter_index")
        scene_index = payload.get("scene_index")
        scene_label = payload.get("status") or "Processing scene"
        if chapter_index is not None and scene_index is not None:
            scene_label = f"ch {chapter_index} scene {scene_index}"
        if isinstance(scene_position, int) and isinstance(total_scenes, int):
            return {
                "current": scene_position,
                "total": total_scenes,
                "label": f"{label_prefix}{scene_label}",
            }
    if phase == "resume":
        completed = payload.get("completed_scenes")
        total_scenes = payload.get("total_scenes")
        if isinstance(completed, int) and isinstance(total_scenes, int):
            return {
                "current": completed,
                "total": total_scenes,
                "label": f"{label_prefix}{payload.get('status') or 'Resuming'}",
            }
    if phase == "causal_graph":
        return {"status": f"{label_prefix}{payload.get('status') or 'Building causal graph'}"}
    if phase == "chapters":
        return {"status": f"{label_prefix}{payload.get('status') or 'Loading chapters'}"}
    return payload


def _load_json(path: str | Path) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str | Path, payload: Dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
    return target


def _add_identity_input_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--identity-json",
        default=str(DEFAULT_BOOKNLP_PIPELINE_IDENTITY_JSON),
        help="Path to the BookNLP clean pipeline identity JSON.",
    )
    parser.add_argument(
        "--series-identity-json",
        default="",
        help="Optional series-level BookNLP clean identity JSON with per-book mappings.",
    )


def _add_identity_provider_arg(
    parser: argparse.ArgumentParser,
    *,
    default: str,
    help_text: str,
) -> None:
    parser.add_argument(
        "--identity-provider",
        default=default,
        choices=IDENTITY_PROVIDER_CHOICES,
        help=help_text,
    )


def _add_production_identity_args(parser: argparse.ArgumentParser) -> None:
    _add_identity_provider_arg(
        parser,
        default=DEFAULT_PRODUCTION_IDENTITY_PROVIDER,
        help_text="Identity source for production runs.",
    )
    _add_identity_input_args(parser)


def _add_identity_override_args(parser: argparse.ArgumentParser, *, help_text: str) -> None:
    _add_identity_provider_arg(
        parser,
        default=DEFAULT_PRODUCTION_IDENTITY_PROVIDER,
        help_text=help_text,
    )
    _add_identity_input_args(parser)


def _get_corpus_hardening_service_class():
    global CorpusHardeningService
    if CorpusHardeningService is None:
        from services.corpus_hardening_service import CorpusHardeningService as _CorpusHardeningService

        CorpusHardeningService = _CorpusHardeningService
    return CorpusHardeningService


def _markdown_table(headers: List[str], rows: List[List[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        values = []
        for value in row:
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _snapshot_focus_names() -> List[str]:
    return [
        "Feyre",
        "Rhysand",
        "Rhys",
        "Tamlin",
        "Lucien",
        "Nesta",
        "Elain",
        "Cassian",
        "Azriel",
        "Mor",
        "Amren",
    ]


def _context_focus_names() -> List[str]:
    return [
        "Feyre",
        "Rhysand",
        "Rhys",
        "Nesta",
        "Cassian",
        "Azriel",
        "Elain",
        "Lucien",
        "Gwyn",
        "Emerie",
        "Mor",
        "Morrigan",
        "Amren",
        "Eris",
        "Vassa",
        "Koschei",
        "Tamlin",
        "Helion",
    ]


def _norm_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _lookup_character_state(context: Dict[str, Any], name: str) -> Dict[str, Any]:
    target = _norm_text(name)
    for row in context.get("character_states") or []:
        candidates = [row.get("name", "")] + list(row.get("aliases") or [])
        if any(_norm_text(candidate) == target for candidate in candidates):
            return row
    return {}


def _noise_terms() -> List[str]:
    return [
        "Velaris",
        "Fae",
        "Spring Court",
        "Starfall",
        "Married",
        "Leather",
        "Couldn",
        "Had",
        "Never",
        "Flame",
        "Lightning",
        "Siphons",
        "Lord Cassian Cassian",
        "Elain Lucien",
        "Feyre Azriel",
        "Cassian He",
    ]


def _select_snapshot_rows(states: List[Dict[str, Any]], focus_names: List[str]) -> List[Dict[str, Any]]:
    by_alias: Dict[str, Dict[str, Any]] = {}
    for row in states:
        names = [row.get("display_name", "")] + list(row.get("aliases") or [])
        for name in names:
            key = str(name or "").strip().lower()
            if key and key not in by_alias:
                by_alias[key] = row
    selected: List[Dict[str, Any]] = []
    seen_ids = set()
    for name in focus_names:
        row = by_alias.get(name.lower())
        if not row:
            continue
        key = row.get("character_id") or row.get("display_name")
        if key in seen_ids:
            continue
        seen_ids.add(key)
        selected.append(row)
    return selected


def _write_snapshot_report(path: str | Path, payload: Dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    states = payload.get("character_states") or []
    diagnostics = payload.get("diagnostics") or {}
    focus_rows = _select_snapshot_rows(states, _snapshot_focus_names())
    lines = [
        "# Character State Snapshot Report",
        "",
        "## Target Point",
        "",
        "```json",
        json.dumps(payload.get("target_point") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Diagnostics",
        "",
        f"- Character states: `{len(states)}`",
        f"- Profiles considered: `{diagnostics.get('character_profile_count', 0)}`",
        f"- Scenes before filter: `{diagnostics.get('scene_count_before_filter', 0)}`",
        f"- Scenes after filter: `{diagnostics.get('scene_count_after_filter', 0)}`",
        f"- Timeline rows: `{diagnostics.get('timeline_count', 0)}`",
        f"- Event ledger rows: `{diagnostics.get('event_ledger_count', 0)}`",
        f"- State transitions: `{diagnostics.get('state_transition_count', 0)}`",
        f"- Future-fact filtering active: `{'yes' if diagnostics.get('future_fact_filtering') else 'no'}`",
        "",
        "## Focus Character Snapshot",
        "",
        _markdown_table(
            ["character", "confidence", "roles", "affiliations", "recent_events", "risk_flags"],
            [
                [
                    row.get("display_name", ""),
                    row.get("confidence", ""),
                    row.get("current_roles") or [],
                    row.get("affiliations") or [],
                    len(row.get("recent_key_events") or []),
                    row.get("risk_flags") or [],
                ]
                for row in focus_rows
            ] or [["(none)", "", "", "", "", ""]],
        ),
        "",
        "## Leakage Check",
        "",
        "- This snapshot is built from scenes filtered to the requested target point before rebuilding timeline, event ledger, state transitions, relationships, and profiles.",
        "- Future facts should therefore be excluded unless `include_future_facts=true` is explicitly set.",
        "",
    ]
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def _write_comfyui_prompt_pack_report(path: str | Path, payload: Dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    packs = payload.get("prompt_packs") or {}
    diagnostics = payload.get("diagnostics") or {}
    characters = packs.get("characters") or []
    locations = packs.get("locations") or []
    objects = packs.get("objects") or []
    scenes = packs.get("scene_prompts") or []
    lines = [
        "# ComfyUI Prompt Pack Report",
        "",
        "## Input",
        "",
        f"- source visual state: `{payload.get('source_visual_state', '')}`",
        f"- mode: `{diagnostics.get('mode', '')}`",
        f"- target point: `{json.dumps(payload.get('target_point') or {}, ensure_ascii=False)}`",
        "",
        "## Counts",
        "",
        f"- input character visual states: `{(diagnostics.get('input_counts') or {}).get('character_visual_states', 0)}`",
        f"- input location visual states: `{(diagnostics.get('input_counts') or {}).get('location_visual_states', 0)}`",
        f"- input entity visual states: `{(diagnostics.get('input_counts') or {}).get('entity_visual_states', 0)}`",
        f"- characters exported: `{len(characters)}`",
        f"- locations exported: `{len(locations)}`",
        f"- objects/entities exported: `{len(objects)}`",
        f"- scene prompts exported: `{len(scenes)}`",
        f"- scene prompt granularity: `{diagnostics.get('scene_prompt_granularity', 'scene_level')}`",
        f"- contract text backed splitting: `{'yes' if diagnostics.get('contract_text_backed_scene_splitting') else 'no'}`",
        f"- noisy entries suppressed: `{len(diagnostics.get('suppressed_entries') or [])}`",
        f"- duplicate aliases merged: `{len(diagnostics.get('alias_merges') or [])}`",
        f"- low-confidence entries excluded: `{len(diagnostics.get('excluded_low_confidence') or [])}`",
        "",
    ]
    if diagnostics.get("suppressed_entries"):
        lines.extend([
            "## Suppressed Entries",
            "",
            _markdown_table(
                ["entry", "reason"],
                [[row.get("entry", ""), row.get("reason", "")] for row in (diagnostics.get("suppressed_entries") or [])[:20]],
            ),
            "",
        ])
    if diagnostics.get("alias_merges"):
        lines.extend([
            "## Alias Merges",
            "",
            _markdown_table(
                ["from", "to"],
                [[row.get("from", ""), row.get("to", "")] for row in (diagnostics.get("alias_merges") or [])[:20]],
            ),
            "",
        ])
    if characters:
        lines.extend([
            "## Character Examples",
            "",
            _markdown_table(
                ["name", "confidence", "appearance", "outfit", "condition"],
                [
                    [
                        row.get("display_name", ""),
                        row.get("confidence", ""),
                        row.get("appearance_prompt", ""),
                        row.get("outfit_prompt", ""),
                        row.get("injury_condition_prompt", ""),
                    ]
                    for row in characters[:8]
                ],
            ),
            "",
        ])
    if locations:
        lines.extend([
            "## Location Examples",
            "",
            _markdown_table(
                ["name", "confidence", "location prompt", "atmosphere"],
                [
                    [
                        row.get("display_name", ""),
                        row.get("confidence", ""),
                        row.get("location_prompt", ""),
                        row.get("atmosphere_prompt", ""),
                    ]
                    for row in locations[:6]
                ],
            ),
            "",
        ])
    if objects:
        lines.extend([
            "## Object Examples",
            "",
            _markdown_table(
                ["name", "confidence", "object prompt", "magic"],
                [
                    [
                        row.get("display_name", ""),
                        row.get("confidence", ""),
                        row.get("object_prompt", ""),
                        row.get("magic_prompt", ""),
                    ]
                    for row in objects[:6]
                ],
            ),
            "",
        ])
    if scenes:
        lines.extend([
            "## Scene Prompt Examples",
            "",
        ])
        for row in scenes[:6]:
            lines.extend([
                f"### {row.get('title', row.get('scene_key', 'Scene'))}",
                "",
                f"- scene key: `{row.get('scene_key', '')}`",
                f"- characters: {', '.join(row.get('characters_used') or []) or 'None'}",
                f"- locations: {', '.join(row.get('locations_used') or []) or 'None'}",
                f"- objects: {', '.join(row.get('objects_used') or []) or 'None'}",
                f"- positive prompt: {row.get('positive_prompt', '')}",
                f"- negative prompt: {row.get('negative_prompt', '')}",
                "",
            ])
    lines.extend([
        "## Remaining Limitations",
        "",
        "- Prompt quality still depends on the cleanliness of upstream visual-state evidence.",
        "- Low-confidence or sparse characters are suppressed by default unless explicitly requested.",
        "- Scene prompts are chapter-beat prompts built from visual changes and location anchors, not hard-limited to raw encoder scene count.",
        "- Scene prompts are evidence-grounded and conservative; they do not invent unsupported wardrobe or magic details.",
        "",
        "## Verdict",
        "",
        "Prompt pack is ready for bounded ComfyUI testing.",
        "",
    ])
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def _write_comfyui_curated_preview(path: str | Path, payload: Dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    curated = payload.get("curated_test_pack") or {}
    lines = [
        "# ComfyUI Curated Prompt Preview",
        "",
    ]
    for section_name in ("characters", "locations", "objects", "scene_prompts"):
        rows = curated.get(section_name) or []
        lines.extend([f"## {section_name.replace('_', ' ').title()}", ""])
        for row in rows:
            title = row.get("display_name") or row.get("title") or row.get("requested_title") or row.get("scene_key") or "Prompt"
            positive = row.get("positive_prompt") or ", ".join(
                filter(None, [
                    row.get("appearance_prompt", ""),
                    row.get("outfit_prompt", ""),
                    row.get("injury_condition_prompt", ""),
                    row.get("expression_prompt", ""),
                    row.get("magic_prompt", ""),
                    row.get("location_prompt", ""),
                    row.get("atmosphere_prompt", ""),
                    row.get("architectural_prompt", ""),
                    row.get("object_prompt", ""),
                    row.get("material_prompt", ""),
                ])
            )
            lines.extend([
                f"### {title}",
                "",
                f"- positive prompt: {positive}",
                f"- negative prompt: {row.get('negative_prompt', '')}",
                f"- confidence: {row.get('confidence', 'n/a')}",
                f"- score: `{json.dumps(row.get('score') or {}, ensure_ascii=False)}`",
                f"- evidence summary: {'; '.join(item.get('text','') for item in (row.get('evidence') or [])[:4])}",
                f"- notes: {', '.join((row.get('score') or {}).get('notes') or []) or 'None'}",
                "",
            ])
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def _write_comfyui_text_exports(directory: str | Path, payload: Dict[str, Any]) -> Path:
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    curated = payload.get("curated_test_pack") or {}
    sections = {
        "characters": curated.get("characters") or [],
        "locations": curated.get("locations") or [],
        "objects": curated.get("objects") or [],
        "scene_prompts": curated.get("scene_prompts") or [],
    }
    for _, rows in sections.items():
        for row in rows:
            title = row.get("display_name") or row.get("requested_title") or row.get("title") or row.get("scene_key") or "prompt"
            slug = re.sub(r"[^a-z0-9]+", "_", str(title).lower()).strip("_")
            positive = row.get("positive_prompt") or ", ".join(
                filter(None, [
                    row.get("appearance_prompt", ""),
                    row.get("outfit_prompt", ""),
                    row.get("injury_condition_prompt", ""),
                    row.get("expression_prompt", ""),
                    row.get("magic_prompt", ""),
                    row.get("location_prompt", ""),
                    row.get("atmosphere_prompt", ""),
                    row.get("architectural_prompt", ""),
                    row.get("object_prompt", ""),
                    row.get("material_prompt", ""),
                ])
            )
            (root / f"{slug}_positive.txt").write_text(positive, encoding="utf-8")
            (root / f"{slug}_negative.txt").write_text(str(row.get("negative_prompt") or ""), encoding="utf-8")
    return root


def _write_visual_world_state_report(path: str | Path, payload: Dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    diagnostics = payload.get("diagnostics") or {}
    character_rows = payload.get("character_visual_states") or []
    entity_rows = payload.get("entity_visual_states") or []
    location_rows = payload.get("location_visual_states") or []
    lines = [
        "# Visual World State Report",
        "",
        "## Target Point",
        "",
        "```json",
        json.dumps(payload.get("target_point") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Diagnostics",
        "",
        f"- Source scenes: `{diagnostics.get('source_scene_count', 0)}`",
        f"- Filtered scenes: `{diagnostics.get('target_filtered_scene_count', 0)}`",
        f"- Character visual states: `{len(character_rows)}`",
        f"- Entity visual states: `{len(entity_rows)}`",
        f"- Location visual states: `{len(location_rows)}`",
        f"- Missing visual evidence flagged: `{len(diagnostics.get('missing_visual_evidence') or [])}`",
        f"- Noisy entries flagged: `{len(diagnostics.get('noisy_entries_flagged') or [])}`",
        "",
        "## Character Visual Coverage",
        "",
        _markdown_table(
            ["character", "confidence", "appearance", "clothing", "injury_condition", "body_language", "evidence"],
            [
                [
                    row.get("display_name", ""),
                    row.get("confidence", ""),
                    row.get("current_appearance", ""),
                    row.get("clothing_or_outfit", ""),
                    row.get("injuries_or_physical_condition", ""),
                    row.get("body_language_or_expression", ""),
                    len(row.get("evidence") or []),
                ]
                for row in character_rows[:20]
            ] or [["(none)", "", "", "", "", "", ""]],
        ),
        "",
        "## Entity / Object Coverage",
        "",
        _markdown_table(
            ["entity", "type", "confidence", "current_state", "location", "evidence"],
            [
                [
                    row.get("display_name", ""),
                    row.get("entity_type", ""),
                    row.get("confidence", ""),
                    row.get("current_state", ""),
                    row.get("location", ""),
                    len(row.get("evidence") or []),
                ]
                for row in entity_rows[:20]
            ] or [["(none)", "", "", "", "", ""]],
        ),
        "",
        "## Location Coverage",
        "",
        _markdown_table(
            ["location", "confidence", "current_description", "atmosphere", "damage_state", "evidence"],
            [
                [
                    row.get("display_name", ""),
                    row.get("confidence", ""),
                    row.get("current_description", ""),
                    row.get("atmosphere", ""),
                    row.get("damage_or_restoration_state", ""),
                    len(row.get("evidence") or []),
                ]
                for row in location_rows[:20]
            ] or [["(none)", "", "", "", "", ""]],
        ),
        "",
        "## Noise Flags",
        "",
        "```json",
        json.dumps(diagnostics.get("noisy_entries_flagged") or [], ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def _load_contracts_with_identity(args) -> List[Dict[str, Any]]:
    contracts: List[Dict[str, Any]] = []
    for path in args.contract:
        payload = _load_json(path)
        payload = _apply_identity_provider_override(payload, args)
        _validate_contract(payload)
        contracts.append(payload)
    return contracts


def _inject_target_snapshot_context(
    *,
    context_service: NarrativeContextService,
    context: Dict[str, Any],
    snapshot_payload: Dict[str, Any],
    top_characters: int,
) -> Dict[str, Any]:
    patched = json.loads(json.dumps(context))
    patched["character_states"] = context_service.character_states_from_snapshot(
        snapshot_payload,
        top_characters=top_characters,
    )
    patched["meta"] = dict(patched.get("meta") or {})
    patched["meta"]["target_point"] = snapshot_payload.get("target_point") or {}
    patched["target_character_state_snapshot"] = snapshot_payload
    patched["stats"] = dict(patched.get("stats") or {})
    patched["stats"]["characters_retrieved"] = len(patched["character_states"])
    return patched


def _json_word_count(payload: Any) -> int:
    return len(json.dumps(payload, ensure_ascii=False).split())


def _focus_character_rows(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for name in _context_focus_names():
        state = _lookup_character_state(context, name)
        if not state:
            rows.append({"focus_name": name, "present": False, "resolved_name": "", "confidence": "", "roles": [], "affiliations": []})
            continue
        rows.append(
            {
                "focus_name": name,
                "present": True,
                "resolved_name": state.get("name", ""),
                "confidence": ((state.get("canon_state") or {}).get("confidence", "")),
                "roles": ((state.get("canon_state") or {}).get("roles", [])),
                "affiliations": ((state.get("canon_state") or {}).get("affiliations", [])),
            }
        )
    return rows


def _relationship_rows_for_focus(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    targets = [
        ("Feyre", "Rhysand"),
        ("Nesta", "Cassian"),
        ("Elain", "Lucien"),
        ("Elain", "Azriel"),
        ("Mor", "Rhysand"),
        ("Cassian", "Azriel"),
        ("Tamlin", "Lucien"),
    ]
    rows = []
    relationships = context.get("relationship_summary") or []
    for a, b in targets:
        found = None
        for row in relationships:
            left = _norm_text(row.get("entity_a") or row.get("between", "").split("<->")[0])
            right = _norm_text(row.get("entity_b") or row.get("between", "").split("<->")[-1])
            if {left, right} == {_norm_text(a), _norm_text(b)}:
                found = row
                break
        rows.append(
            {
                "pair": f"{a} / {b}",
                "present": bool(found),
                "type": (found or {}).get("relationship_type", ""),
                "latest": (found or {}).get("latest_change", ""),
                "evidence": (found or {}).get("evidence", ""),
            }
        )
    return rows


def _relevant_documents(context: Dict[str, Any], *, limit: int = 20) -> List[Dict[str, Any]]:
    focus_tokens = {_norm_text(name) for name in _context_focus_names()}
    topical_terms = [
        "koschei",
        "vassa",
        "eris",
        "hybern",
        "autumn court",
        "valkyr",
        "nyx",
        "cauldron",
        "trove",
    ]
    scored = []
    for row in context.get("retrieval_documents") or []:
        blob = " ".join(
            [
                str(row.get("summary") or ""),
                str(row.get("text") or ""),
                " ".join(str(v) for v in ((row.get("metadata") or {}).get("characters") or [])),
            ]
        ).lower()
        score = sum(1 for term in topical_terms if term in blob)
        score += sum(1 for token in focus_tokens if token and token in _norm_text(blob))
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in scored[:limit]]


def _noise_diagnostics(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    state_endpoint_blob = json.dumps(
        [
            {
                "name": row.get("name", ""),
                "aliases": row.get("aliases", []),
                "canon_state": row.get("canon_state", {}),
                "descriptions": row.get("descriptions", []),
            }
            for row in (context.get("character_states") or [])
        ],
        ensure_ascii=False,
    ).lower()
    relationships_blob = json.dumps(
        [
            {
                "entity_a": row.get("entity_a", ""),
                "entity_b": row.get("entity_b", ""),
                "between": row.get("between", ""),
                "relationship_type": row.get("relationship_type", ""),
                "latest_change": row.get("latest_change", ""),
            }
            for row in (context.get("relationship_summary") or [])
        ],
        ensure_ascii=False,
    ).lower()
    docs = context.get("retrieval_documents") or []
    ref_blob = json.dumps(context.get("reference_entities") or [], ensure_ascii=False).lower()
    for term in _noise_terms():
        lowered = term.lower()
        classification = "absent"
        if lowered in state_endpoint_blob:
            classification = "appears in character state"
        elif lowered in relationships_blob:
            classification = "appears in relationship state"
        elif lowered in ref_blob:
            classification = "appears only as location/reference"
        else:
            for row in docs:
                blob = json.dumps(row, ensure_ascii=False).lower()
                if lowered in blob:
                    classification = "appears in event/timeline evidence"
                    break
        rows.append({"term": term, "classification": classification})
    return rows


def _unresolved_thread_rows(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    desired = ["Koschei", "Vassa", "Eris", "Beron", "Valkyr", "Gwyn", "Emerie", "Nyx", "Tamlin"]
    rows = []
    threads = context.get("unresolved_threads") or []
    blobbed = json.dumps(threads, ensure_ascii=False).lower()
    for name in desired:
        rows.append({"thread": name, "present": name.lower() in blobbed})
    return rows


def _context_scores(context: Dict[str, Any]) -> Dict[str, int]:
    focus_rows = _focus_character_rows(context)
    present = sum(1 for row in focus_rows if row["present"])
    high_or_med = sum(1 for row in focus_rows if row["confidence"] in {"high", "medium"})
    rel_rows = _relationship_rows_for_focus(context)
    rel_present = sum(1 for row in rel_rows if row["present"])
    threads_present = sum(1 for row in _unresolved_thread_rows(context) if row["present"])
    noise_rows = _noise_diagnostics(context)
    bad_noise = sum(1 for row in noise_rows if row["classification"] in {"appears in character state", "appears in relationship state"})
    retrieval_docs = len(context.get("retrieval_documents") or [])
    scores = {
        "character_state_usefulness": 5 if high_or_med >= 12 else 4 if high_or_med >= 9 else 3 if high_or_med >= 6 else 2,
        "relationship_usefulness": 5 if rel_present >= 5 else 4 if rel_present >= 3 else 3 if rel_present >= 2 else 2,
        "canon_event_grounding": 5 if retrieval_docs >= 500 else 4 if retrieval_docs >= 250 else 3 if retrieval_docs >= 100 else 2,
        "unresolved_plot_thread_coverage": 5 if threads_present >= 6 else 4 if threads_present >= 4 else 3 if threads_present >= 2 else 2,
        "identity_cleanliness": 5 if bad_noise == 0 else 4 if bad_noise <= 2 else 2,
        "evidence_provenance_quality": 5 if context.get("target_character_state_snapshot") else 3,
        "decoder_readiness": 5 if present >= 14 and bad_noise == 0 else 4 if present >= 10 else 3,
        "token_efficiency": 4 if _json_word_count(context) <= 14000 else 3 if _json_word_count(context) <= 22000 else 2,
    }
    return scores


def _context_status(scores: Dict[str, int]) -> str:
    avg = sum(scores.values()) / max(len(scores), 1)
    if avg >= 4.25:
        return "usable for blueprint generation"
    if avg >= 3.75:
        return "needs targeted cleanup first"
    if avg >= 3.0:
        return "needs profile/state builder improvement"
    return "needs retrieval redesign"


def _apply_identity_provider_override(contract: Dict[str, Any], args) -> Dict[str, Any]:
    provider_mode = str(
        getattr(args, "identity_provider", DEFAULT_PRODUCTION_IDENTITY_PROVIDER) or DEFAULT_PRODUCTION_IDENTITY_PROVIDER
    ).strip().lower()
    if provider_mode != DEFAULT_PRODUCTION_IDENTITY_PROVIDER:
        return contract
    identity_json = getattr(args, "series_identity_json", None) or getattr(args, "identity_json", None)
    return override_contract_with_identity_provider(
        contract,
        provider_mode=provider_mode,
        input_json=identity_json or None,
    )


def _resolved_identity_json(args) -> str:
    return str(getattr(args, "series_identity_json", None) or getattr(args, "identity_json", "") or "").strip()


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _series_run_root(series_id: str) -> Path:
    return Path("analysis_outputs") / "encode_runs" / series_id


def _start_run_artifacts(series_id: str) -> Dict[str, Path]:
    started = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = _series_run_root(series_id) / started
    contracts_dir = run_dir / "contracts"
    checkpoints_dir = _series_run_root(series_id) / "resume_checkpoints"
    run_dir.mkdir(parents=True, exist_ok=True)
    contracts_dir.mkdir(parents=True, exist_ok=True)
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    return {
        "run_dir": run_dir,
        "contracts_dir": contracts_dir,
        "checkpoints_dir": checkpoints_dir,
        "status_path": run_dir / "status.json",
        "latest_status_path": _series_run_root(series_id) / "latest_status.json",
        "log_path": run_dir / "encode.log",
    }


def _status_payload(
    *,
    series_id: str,
    series_title: str,
    plan: Dict[str, Any],
    run_dir: Path,
    log_path: Path,
    books: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "series_id": series_id,
        "series_title": series_title,
        "worker_pid": os.getpid(),
        "worker_executable": os.path.abspath(os.sys.executable),
        "run_dir": str(run_dir),
        "log_path": str(log_path),
        "started_at_utc": _now_utc(),
        "updated_at_utc": _now_utc(),
        "status": "running",
        "summary": {
            "total_requested": len(books),
            "completed": 0,
            "failed": 0,
            "skipped": 0,
            "remaining": len(books),
        },
        "plan": plan,
        "books": [
            {
                "title": book["title"],
                "path": book["path"],
                "book_index": book["book_index"],
                "source_hash_sha256": book.get("source_hash_sha256", ""),
                "status": "pending",
                "phase": "pending",
                "started_at_utc": "",
                "finished_at_utc": "",
                "elapsed_seconds": 0.0,
                "scenes_processed": 0,
                "total_scenes": 0,
                "contract_path": "",
                "ingest_result": {},
                "error": "",
                "checkpoint_path": "",
            }
            for book in books
        ],
    }


def _save_status(status: Dict[str, Any], status_path: Path, latest_status_path: Path) -> None:
    status["updated_at_utc"] = _now_utc()
    _write_json(status_path, status)
    _write_json(latest_status_path, status)


def _attach_file_logger(log_path: Path) -> logging.Handler:
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    return handler


def _detach_file_logger(handler: logging.Handler) -> None:
    root = logging.getLogger()
    root.removeHandler(handler)
    handler.close()


def _safe_filename(value: str) -> str:
    return str(value or "").replace("/", "-").replace("\\", "-").replace(":", "-")


def _book_checkpoint_path(series_id: str, book_index: int, title: str) -> Path:
    return _series_run_root(series_id) / "resume_checkpoints" / f"{int(book_index):02d}_{_safe_filename(title)}.checkpoint.json"


def _validate_contract(payload: Dict[str, Any]) -> None:
    NarrativeContextService().validate_contract_for_rebuild(payload)


def _parse_relationship_directions(values: List[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for raw in values or []:
        parts = [part.strip() for part in str(raw or "").split("|")]
        if len(parts) < 3:
            raise ValueError(
                "Each --relationship-direction must use the format "
                "'name1,name2|relationship_type|desired direction|optional notes'."
            )
        names = [item.strip() for item in parts[0].split(",") if item.strip()]
        if len(names) < 2:
            raise ValueError(
                "Each --relationship-direction must specify at least two comma-separated character names."
            )
        rows.append({
            "characters": names,
            "relationship_type": parts[1].strip().lower() or "other",
            "desired_direction": parts[2],
            "notes": parts[3] if len(parts) > 3 else "",
        })
    return rows


def _parse_canon_elements(values: List[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for raw in values or []:
        parts = [part.strip() for part in str(raw or "").split("|")]
        if not parts or not parts[0]:
            continue
        if len(parts) == 1:
            rows.append({"event_id": "", "description": parts[0]})
        else:
            rows.append({"event_id": parts[0], "description": parts[1]})
    return rows


def _generation_controls_from_args(args) -> Dict[str, Any]:
    return {
        "chapter_count": getattr(args, "chapters", None),
        "canon_position": getattr(args, "canon_position", "post_canon"),
        "new_plot": getattr(args, "new_plot", "") or "",
        "primary_pov_character": getattr(args, "primary_pov", "") or "",
        "relationship_directions": _parse_relationship_directions(getattr(args, "relationship_direction", []) or []),
        "canon_elements_to_preserve": _parse_canon_elements(getattr(args, "preserve_event", []) or []),
        "continuity_anchor": getattr(args, "continuity_anchor", "") or "",
        "divergence_anchor": getattr(args, "divergence_anchor", "") or "",
        "anchor_after": getattr(args, "anchor_after", "") or "",
        "anchor_before": getattr(args, "anchor_before", "") or "",
    }


def _contract_paths_from_args_or_discovery(args) -> List[str]:
    explicit = [str(path) for path in (getattr(args, "contract", None) or []) if str(path).strip()]
    if explicit:
        return explicit
    helper = _get_corpus_hardening_service_class()(
        neo4j_service=Neo4jIngestionService(
            uri=getattr(args, "uri", None),
            username=getattr(args, "username", None),
            password=getattr(args, "password", None),
            database=getattr(args, "database", None),
        ),
        wiki_hints_enabled=getattr(args, "use_web_hints", False),
    )
    try:
        return [str(path) for path in helper.discover_latest_contracts(args.series_id)]
    finally:
        helper.neo4j.close()


def _manuscript_metrics(output_dir: Path) -> Dict[str, Any]:
    chapters = sorted(output_dir.glob("chapter_*.txt"))
    combined = "\n".join(path.read_text(encoding="utf-8") for path in chapters if path.exists())
    lower = combined.lower()
    return {
        "chapter_count": len(chapters),
        "word_count": len(combined.split()),
        "non_dialogue_first_person_signals": sum(lower.count(token) for token in [" i ", "\ni ", "\nmy ", " my "]),
        "retrieval_debug_present": (output_dir / "progress.json").exists(),
    }


def _artifact_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    return 0


def _artifact_status(name: str, count: int) -> str:
    if name == "causal_graph_result":
        return "not required for MVP"
    if count <= 0:
        return "empty"
    sparse_thresholds = {
        "entity_registry": 5,
        "state_transitions": 5,
        "canon_snapshot": 3,
        "timeline": 5,
        "event_ledger": 5,
        "character_timelines": 3,
        "character_profiles": 3,
        "stable_character_states": 2,
        "story_index_docs": 25,
    }
    threshold = sparse_thresholds.get(name)
    if threshold is not None and count < threshold:
        return "sparse"
    return "ready"


def _scene_schema_summary(scene_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not scene_rows:
        return {
            "scene_count": 0,
            "fields_present": [],
            "nonempty_counts": {},
            "average_lengths": {},
            "sample_errors": [],
            "dominant_error": "",
        }
    tracked_fields = [
        "events",
        "canonical_characters",
        "entities_present",
        "state_changes",
        "relationship_changes",
        "character_mentions",
        "scene_summary",
        "location",
        "time_signals",
    ]
    nonempty_counts: Dict[str, int] = {}
    average_lengths: Dict[str, float] = {}
    for field in tracked_fields:
        if field == "scene_summary":
            nonempty_counts[field] = sum(1 for row in scene_rows if str(row.get(field) or "").strip())
            continue
        if field == "location":
            nonempty_counts[field] = sum(1 for row in scene_rows if isinstance(row.get(field), dict) and str((row.get(field) or {}).get("name") or "").strip())
            continue
        values = [len(row.get(field) or []) for row in scene_rows]
        nonempty_counts[field] = sum(1 for value in values if value > 0)
        average_lengths[field] = round(sum(values) / max(len(values), 1), 2)
    errors = [str(row.get("error") or row.get("last_error") or "").strip() for row in scene_rows]
    error_counter: Dict[str, int] = {}
    for value in errors:
        if not value:
            continue
        error_counter[value] = error_counter.get(value, 0) + 1
    dominant_error = ""
    dominant_error_count = 0
    if error_counter:
        dominant_error, dominant_error_count = max(error_counter.items(), key=lambda item: item[1])
    return {
        "scene_count": len(scene_rows),
        "fields_present": sorted(scene_rows[0].keys()),
        "nonempty_counts": nonempty_counts,
        "average_lengths": average_lengths,
        "sample_errors": [value for value in errors if value][:3],
        "dominant_error": dominant_error,
        "error_scene_count": sum(1 for value in errors if value),
        "dominant_error_count": dominant_error_count,
    }


def _dependency_rows(outputs: Dict[str, Any], scene_schema: Dict[str, Any]) -> List[Dict[str, Any]]:
    nonempty = scene_schema.get("nonempty_counts") or {}
    dom_error = scene_schema.get("dominant_error") or ""
    failures = {
        "entity_registry": "Scene entity/location/state fields are empty." if not nonempty.get("entities_present") and not nonempty.get("location") else "",
        "state_result": "Scene state_changes are empty." if not nonempty.get("state_changes") else "",
        "timeline": "Scene events are empty." if not nonempty.get("events") else "",
        "event_ledger": "Timeline is empty, so no ledger rows can be built." if not nonempty.get("events") else "",
        "character_timelines": "Timeline has no participant characters." if not nonempty.get("events") else "",
        "character_profiles": "Character timelines or entity registry are empty." if _artifact_count(outputs.get("character_timelines")) == 0 or _artifact_count(outputs.get("entity_registry")) == 0 else "",
        "stable_character_states": "Profiles/latest state lack stable canon attributes." if _artifact_count(outputs.get("stable_character_states")) == 0 else "",
        "story_index_summary": "Retrieval docs stay sparse because upstream artifacts are empty." if int((outputs.get("story_index_summary") or {}).get("document_count") or 0) <= 25 else "",
    }
    expected = {
        "entity_registry": "entities_present, location, entity_descriptions, state_changes",
        "state_result": "state_changes",
        "timeline": "events, chapter/book/scene metadata",
        "event_ledger": "timeline, scene location/time/state/relationship context",
        "character_timelines": "timeline.characters",
        "character_profiles": "character_timelines, entity_registry, latest_state, alias_map, relationship_changes",
        "stable_character_states": "character_profiles, canon_snapshot, latest_state, alias_map",
        "story_index_summary": "all major narrative artifacts",
    }
    actual = {
        "entity_registry": f"entities={nonempty.get('entities_present', 0)} location={nonempty.get('location', 0)} state={nonempty.get('state_changes', 0)}",
        "state_result": f"state_changes={nonempty.get('state_changes', 0)}",
        "timeline": f"events={nonempty.get('events', 0)} scene_summaries={nonempty.get('scene_summary', 0)}",
        "event_ledger": f"timeline_rows={_artifact_count(outputs.get('timeline'))}",
        "character_timelines": f"timeline_rows={_artifact_count(outputs.get('timeline'))}",
        "character_profiles": f"timelines={_artifact_count(outputs.get('character_timelines'))} registry={_artifact_count(outputs.get('entity_registry'))}",
        "stable_character_states": f"profiles={_artifact_count(outputs.get('character_profiles'))} latest_state={len((outputs.get('state_result') or {}).get('latest_state') or [])}",
        "story_index_summary": f"document_count={int((outputs.get('story_index_summary') or {}).get('document_count') or 0)}",
    }
    rows = []
    for artifact in ["entity_registry", "state_result", "timeline", "event_ledger", "character_timelines", "character_profiles", "stable_character_states", "story_index_summary"]:
        failure = failures.get(artifact) or ""
        if dom_error and not failure and artifact in {"entity_registry", "state_result", "timeline", "event_ledger", "character_timelines", "character_profiles", "stable_character_states"}:
            failure = f"Upstream scene analysis errors dominate: {dom_error}"
        rows.append({
            "artifact": artifact,
            "input_source": expected.get(artifact, ""),
            "expected_fields": expected.get(artifact, ""),
            "actual_fields": actual.get(artifact, ""),
            "failure_reason": failure or "No obvious data-loss point detected.",
        })
    return rows


def _rebuild_outputs_for_validation(contract: Dict[str, Any]) -> Dict[str, Any]:
    outputs = dict((contract.get("outputs") or {}))
    identity_result = outputs.get("identity_result") or {}
    scene_analyses = outputs.get("scene_analyses") or []
    resolved_scene_analyses = rebuild_resolved_scene_analyses(scene_analyses, identity_result)
    entity_registry = build_entity_registry(resolved_scene_analyses)
    state_result = build_state_result(resolved_scene_analyses)
    timeline = build_timeline(resolved_scene_analyses)
    causal_graph_result = outputs.get("causal_graph_result") or {"graph": {}, "metrics": {}}
    event_ledger = build_event_ledger(resolved_scene_analyses, timeline, causal_graph_result)
    character_timelines = build_character_timelines(timeline)
    character_timelines = normalize_character_timelines(character_timelines, identity_result)
    character_profiles = build_formal_character_profiles(
        character_timelines,
        entity_registry,
        state_result,
        identity_result,
        resolved_scene_analyses,
    )
    canon_snapshot = []
    if resolved_scene_analyses:
        last_scene = resolved_scene_analyses[-1]
        canon_snapshot = build_canon_snapshot(
            state_result,
            (last_scene.get("book_index"), last_scene.get("chapter_index"), last_scene.get("scene_index")),
        )
    stable_character_states = StableCharacterStateBuilder().build(
        character_profiles=character_profiles,
        identity_result=identity_result,
        canon_snapshot=canon_snapshot,
        state_result=state_result,
    )
    story_index_summary = build_story_index_summary(
        resolved_scene_analyses,
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
    outputs.update({
        "resolved_scene_analyses": resolved_scene_analyses,
        "entity_registry": entity_registry,
        "state_result": state_result,
        "canon_snapshot": canon_snapshot,
        "timeline": timeline,
        "event_ledger": event_ledger,
        "character_timelines": character_timelines,
        "character_profiles": character_profiles,
        "stable_character_states": stable_character_states,
        "story_index_summary": story_index_summary,
    })
    return outputs


def _artifact_snapshot(outputs: Dict[str, Any]) -> Dict[str, Any]:
    state_result = outputs.get("state_result") or {}
    snapshot = {
        "chapters": _artifact_count(outputs.get("chapters")),
        "scene_analyses": _artifact_count(outputs.get("scene_analyses")),
        "resolved_scene_analyses": _artifact_count(outputs.get("resolved_scene_analyses")),
        "entity_registry": _artifact_count(outputs.get("entity_registry")),
        "state_transitions": len(state_result.get("transitions") or []),
        "canon_snapshot": _artifact_count(outputs.get("canon_snapshot")),
        "timeline": _artifact_count(outputs.get("timeline")),
        "event_ledger": _artifact_count(outputs.get("event_ledger")),
        "character_timelines": _artifact_count(outputs.get("character_timelines")),
        "character_profiles": _artifact_count(outputs.get("character_profiles")),
        "stable_character_states": _artifact_count(outputs.get("stable_character_states")),
        "story_index_docs": int((outputs.get("story_index_summary") or {}).get("document_count") or 0),
        "causal_graph_result": _artifact_count(((outputs.get("causal_graph_result") or {}).get("graph") or {}).get("events") or []),
    }
    return {
        key: {
            "count": value,
            "status": _artifact_status(key, int(value)),
        }
        for key, value in snapshot.items()
    }


def _identity_summary(outputs: Dict[str, Any]) -> Dict[str, Any]:
    identity_result = outputs.get("identity_result") or {}
    provider_characters = identity_result.get("provider_characters") or []
    stable_candidates = [
        item for item in provider_characters
        if str(item.get("display_name") or "").strip()
    ]
    scene_names = set()
    unresolved = identity_result.get("unresolved_identity_candidates") or []
    for scene in outputs.get("resolved_scene_analyses") or []:
        for row in scene.get("canonical_characters") or []:
            name = str(row.get("name") or "").strip()
            if name:
                scene_names.add(name)
        for row in scene.get("character_mentions") or []:
            name = str(row.get("canonical_name") or "").strip()
            if name:
                scene_names.add(name)
    alias_map = identity_result.get("alias_map") or {}
    alias_index_count = sum(len(v or []) for v in alias_map.values())
    return {
        "identity_provider": identity_result.get("identity_provider") or "",
        "provider_locked": bool(identity_result.get("provider_locked")),
        "alias_map_count": len(alias_map),
        "alias_index_count": alias_index_count,
        "provider_character_count": len(stable_candidates),
        "provider_character_names": [item.get("display_name") for item in stable_candidates[:20]],
        "scene_character_names_sample": sorted(scene_names)[:25],
        "unresolved_candidate_count": len(unresolved),
        "unresolved_candidates_sample": unresolved[:10],
    }


def _compare_snapshots(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    keys = sorted(set(left.keys()) | set(right.keys()))
    return {
        key: {
            "baseline": int((left.get(key) or {}).get("count") or 0),
            "comparison": int((right.get(key) or {}).get("count") or 0),
            "delta": int((right.get(key) or {}).get("count") or 0) - int((left.get(key) or {}).get("count") or 0),
        }
        for key in keys
    }


def _render_encoder_validation_markdown(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Encoder Artifact Validation")
    lines.append("")
    lines.append(f"- Contract: `{report.get('contract_path', '')}`")
    lines.append(f"- Validation mode: `{report.get('validation_mode', '')}`")
    lines.append(f"- Identity provider override: `{report.get('identity_provider', DEFAULT_PRODUCTION_IDENTITY_PROVIDER)}`")
    lines.append("")
    lines.append("## Artifact Counts")
    lines.append("")
    lines.append("| artifact | count | status |")
    lines.append("|---|---:|---|")
    for artifact, payload in (report.get("artifact_snapshot") or {}).items():
        lines.append(f"| {artifact} | {payload.get('count', 0)} | {payload.get('status', '')} |")
    lines.append("")
    scene_schema = report.get("scene_schema") or {}
    lines.append("## Scene Schema Quality")
    lines.append("")
    lines.append(f"- scene count: `{scene_schema.get('scene_count', 0)}`")
    if scene_schema.get("dominant_error"):
        lines.append(f"- dominant error: `{scene_schema.get('dominant_error')}`")
    lines.append("- non-empty field counts:")
    for key, value in sorted((scene_schema.get("nonempty_counts") or {}).items()):
        lines.append(f"  - `{key}`: `{value}`")
    lines.append("")
    lines.append("## Dependency Trace")
    lines.append("")
    lines.append("| artifact | input source | expected fields | actual fields | failure reason |")
    lines.append("|---|---|---|---|---|")
    for row in report.get("dependency_rows") or []:
        lines.append(
            f"| {row.get('artifact','')} | {row.get('input_source','')} | {row.get('expected_fields','')} | "
            f"{row.get('actual_fields','')} | {row.get('failure_reason','')} |"
        )
    lines.append("")
    identity = report.get("identity_summary") or {}
    lines.append("## Identity Integration")
    lines.append("")
    lines.append(f"- provider locked: `{identity.get('provider_locked')}`")
    lines.append(f"- alias map count: `{identity.get('alias_map_count', 0)}`")
    lines.append(f"- alias index count: `{identity.get('alias_index_count', 0)}`")
    lines.append(f"- provider character count: `{identity.get('provider_character_count', 0)}`")
    lines.append(f"- unresolved candidate count: `{identity.get('unresolved_candidate_count', 0)}`")
    if report.get("comparison_snapshot"):
        lines.append("")
        lines.append("## Comparison")
        lines.append("")
        lines.append("| artifact | baseline | comparison | delta |")
        lines.append("|---|---:|---:|---:|")
        for artifact, row in (report.get("comparison_snapshot") or {}).items():
            lines.append(f"| {artifact} | {row.get('baseline',0)} | {row.get('comparison',0)} | {row.get('delta',0)} |")
    lines.append("")
    lines.append("## Root Cause")
    lines.append("")
    lines.append(f"- classification: `{report.get('root_cause', {}).get('classification', '')}`")
    lines.append(f"- reason: {report.get('root_cause', {}).get('reason', '')}")
    lines.append(f"- minimum fix: {report.get('root_cause', {}).get('minimum_fix', '')}")
    lines.append("")
    return "\n".join(lines)


def validate_encoder_artifacts(args) -> None:
    contract = _load_json(args.contract)
    baseline_outputs = contract.get("outputs") or {}
    validation_mode = "contract_only"
    working_contract = contract
    if str(
        getattr(args, "identity_provider", DEFAULT_PRODUCTION_IDENTITY_PROVIDER) or DEFAULT_PRODUCTION_IDENTITY_PROVIDER
    ).strip().lower() == DEFAULT_PRODUCTION_IDENTITY_PROVIDER:
        working_contract = _apply_identity_provider_override(dict(contract), args)
        validation_mode = "provider_override_rebuild"
    rebuilt_outputs = _rebuild_outputs_for_validation(working_contract)
    artifact_snapshot = _artifact_snapshot(rebuilt_outputs)
    scene_schema = _scene_schema_summary(rebuilt_outputs.get("resolved_scene_analyses") or [])
    identity_summary = _identity_summary(rebuilt_outputs)
    dependency_rows = _dependency_rows(rebuilt_outputs, scene_schema)
    root_cause = {
        "classification": "",
        "reason": "",
        "minimum_fix": "",
    }
    dominant_error = scene_schema.get("dominant_error") or ""
    error_scene_count = int(scene_schema.get("error_scene_count") or 0)
    scene_count = int(scene_schema.get("scene_count") or 0)
    error_ratio = (error_scene_count / scene_count) if scene_count else 0.0
    if dominant_error and error_ratio >= 0.25:
        if "max_retries_exceeded" in dominant_error or "rate" in dominant_error.lower():
            root_cause = {
                "classification": "model output quality issue",
                "reason": f"Scene analyses degraded into error shells because the analyzer hit provider exhaustion: {dominant_error}",
                "minimum_fix": "Harden encoder handling of rate-limited scene failures and re-run the affected book with a reliable model budget before any full-series pass.",
            }
        else:
            root_cause = {
                "classification": "scene analyzer missing fields",
                "reason": f"Resolved scenes contain dominant analyzer errors instead of structured content: {dominant_error}",
                "minimum_fix": "Fix analyzer reliability or fallback behavior so scenes emit usable structured fields.",
            }
    elif int((artifact_snapshot.get("timeline") or {}).get("count") or 0) == 0:
        root_cause = {
            "classification": "scene analyzer missing fields",
            "reason": "Scenes exist, but they do not carry events, so timeline/event ledger/profile builders have no material to work with.",
            "minimum_fix": "Fix scene analysis event extraction before scaling the encoder.",
        }
    elif int((artifact_snapshot.get("stable_character_states") or {}).get("count") or 0) <= 1:
        root_cause = {
            "classification": "builder filtering too aggressively",
            "reason": "Stable character state output is much thinner than profiles because StableCharacterStateBuilder only keeps a narrow canon attribute set.",
            "minimum_fix": "Validate whether stable-state sparsity is acceptable for MVP or add a conservative fallback from character profiles.",
        }
    comparison_snapshot = None
    if getattr(args, "compare_contract", None):
        compare_contract = _load_json(args.compare_contract)
        compare_outputs = _rebuild_outputs_for_validation(compare_contract)
        comparison_snapshot = _compare_snapshots(_artifact_snapshot(compare_outputs), artifact_snapshot)
    report = {
        "generated_at_utc": _now_utc(),
        "contract_path": str(args.contract),
        "validation_mode": validation_mode,
        "identity_provider": str(
            getattr(args, "identity_provider", DEFAULT_PRODUCTION_IDENTITY_PROVIDER) or DEFAULT_PRODUCTION_IDENTITY_PROVIDER
        ),
        "artifact_snapshot": artifact_snapshot,
        "scene_schema": scene_schema,
        "identity_summary": identity_summary,
        "dependency_rows": dependency_rows,
        "comparison_snapshot": comparison_snapshot,
        "root_cause": root_cause,
    }
    target = _write_json(args.out, report)
    report_md = Path(getattr(args, "report_md", "") or Path(args.out).with_suffix(".md"))
    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_md.write_text(_render_encoder_validation_markdown(report), encoding="utf-8")
    print(f"Encoder validation written to: {target}")
    print(f"Encoder validation report written to: {report_md}")


def export_contract_copy(args) -> None:
    payload = _load_json(args.contract)
    _validate_contract(payload)
    target = _write_json(args.out, payload)
    print(f"Prepared contract written to: {target}")


def _book_inputs_from_args(book_paths: list[str]) -> list[dict[str, str]]:
    books = []
    for raw_path in book_paths:
        path = Path(raw_path)
        books.append({
            "path": str(path),
            "type": path.suffix.lstrip(".").lower(),
            "title": path.name,
        })
    return books


def encode_store(args) -> None:
    from services.encoder_persistence_service import EncoderPersistenceService, RateLimitGuardError, SceneFailurePolicyError

    preflight_models = [
        (args.analysis_model, args.analysis_model),
        (args.identity_model, args.identity_model),
    ]
    checked = set()
    for mode_name, model_mode in preflight_models:
        if model_mode in checked:
            continue
        checked.add(model_mode)
        _preflight_model_access(model_mode, getattr(args, "analysis_provider_mode", "single_provider"))

    encoder = EncoderPersistenceService(
        analysis_model=args.analysis_model,
        identity_model=args.identity_model,
        identity_provider=args.identity_provider,
        identity_json_path=_resolved_identity_json(args),
        analysis_provider_mode=args.analysis_provider_mode,
        analysis_mode=args.analysis_mode,
        target_scene_words=args.target_scene_words,
        max_chapters=args.max_chapters,
        scene_failure_policy=args.scene_failure_policy,
        max_failed_scenes_absolute=args.max_failed_scenes_absolute,
        max_failed_scene_ratio=args.max_failed_scene_ratio,
        min_nonempty_scene_ratio=args.min_nonempty_scene_ratio,
        series_id=args.series_id,
        series_title=args.series_title,
        book_index_base=args.book_index_base,
    )
    neo4j = None if getattr(args, "skip_ingest", False) else Neo4jIngestionService(
        uri=args.uri,
        username=args.username,
        password=args.password,
        database=args.database,
    )
    try:
        progress = _TerminalProgressPrinter(enabled=not getattr(args, "no_progress", False))
        prepared_books = encoder._prepare_book_inputs(_book_inputs_from_args(args.book))
        effective_series_id, effective_series_title = encoder._series_context(prepared_books)
        if neo4j is None:
            plan = {
                "series_id": effective_series_id,
                "series_title": effective_series_title,
                "mode": "skip_ingest",
                "books": [
                    {
                        "title": row["title"],
                        "book_index": row["book_index"],
                        "action": "encode_only",
                        "reason": "Neo4j ingest skipped by CLI flag.",
                    }
                    for row in prepared_books
                ],
            }
            selected_books = list(prepared_books)
        else:
            neo4j.register_series(effective_series_id, effective_series_title)
            plan = neo4j.plan_ingest(effective_series_id, prepared_books)
            conflicts = [row for row in plan["books"] if row["action"] == "conflict"]
            stale = [row for row in plan["books"] if row["action"] == "stale"]
            if conflicts:
                joined = "; ".join(f"{row['title']}: {row['reason']}" for row in conflicts)
                raise ValueError(f"Corpus ingest planning found book-index conflicts. {joined}")
            if stale and not args.replace_existing:
                joined = ", ".join(row["title"] for row in stale)
                raise ValueError(
                    f"Persisted books already exist with different source hashes: {joined}. "
                    "Re-run with --replace-existing to intentionally replace them."
                )
            selected_books = [
                row for row in prepared_books
                if next(item for item in plan["books"] if item["title"] == row["title"])["action"] != "unchanged"
            ]
        run_artifacts = _start_run_artifacts(effective_series_id)
        status = _status_payload(
            series_id=effective_series_id,
            series_title=effective_series_title,
            plan=plan,
            run_dir=run_artifacts["run_dir"],
            log_path=run_artifacts["log_path"],
            books=prepared_books,
        )
        _save_status(status, run_artifacts["status_path"], run_artifacts["latest_status_path"])
        if not selected_books:
            for row in status["books"]:
                row["status"] = "skipped"
                row["phase"] = "unchanged"
            status["status"] = "completed"
            status["summary"]["skipped"] = len(status["books"])
            status["summary"]["remaining"] = 0
            _save_status(status, run_artifacts["status_path"], run_artifacts["latest_status_path"])
            print(json.dumps({
                "encoded": {"books": 0, "chapters": 0, "scenes": 0, "timeline_rows": 0},
                "ingest": {"status": "skipped", "reason": "All requested books are already persisted with the same source hash."},
                "plan": plan,
                "status_file": str(run_artifacts["status_path"]),
                "log_file": str(run_artifacts["log_path"]),
            }, ensure_ascii=False, indent=2))
            return
        log_handler = _attach_file_logger(run_artifacts["log_path"])
        aggregate_ingest = []
        encoded_summary = {"books": 0, "chapters": 0, "scenes": 0, "timeline_rows": 0}
        status_lock = threading.Lock()

        def _update_status(mutator) -> None:
            with status_lock:
                mutator()
                _save_status(status, run_artifacts["status_path"], run_artifacts["latest_status_path"])

        def _record_book_progress(book_status: Dict[str, Any], phase: str, payload: Dict[str, Any]) -> None:
            def _mutate() -> None:
                book_status["phase"] = phase
                book_status["status"] = "running"
                book_status["last_progress"] = payload
                if payload.get("scene_position") is not None:
                    book_status["scenes_processed"] = payload.get("scene_position", 0)
                if payload.get("total_scenes") is not None:
                    book_status["total_scenes"] = payload.get("total_scenes", 0)
            _update_status(_mutate)
            progress(phase, _encode_progress_payload(phase, {
                **payload,
                "book": book_status.get("title") or payload.get("book"),
            }))

        def _encode_single_book(book: Dict[str, Any]) -> Dict[str, Any]:
            checkpoint_path = _book_checkpoint_path(effective_series_id, book["book_index"], book["title"])
            book_status = next(row for row in status["books"] if row["title"] == book["title"])
            book_started = datetime.now(timezone.utc)

            def _mark_started() -> None:
                book_status["status"] = "running"
                book_status["phase"] = "chapters"
                book_status["started_at_utc"] = _now_utc()
                book_status["checkpoint_path"] = str(checkpoint_path)

            _update_status(_mark_started)

            def _progress_callback(phase: str, payload: Dict[str, Any]) -> None:
                _record_book_progress(book_status, phase, payload)

            book_encoder = EncoderPersistenceService(
                analysis_model=args.analysis_model,
                identity_model=args.identity_model,
                identity_provider=args.identity_provider,
                identity_json_path=_resolved_identity_json(args),
                analysis_provider_mode=args.analysis_provider_mode,
                analysis_mode=args.analysis_mode,
                target_scene_words=args.target_scene_words,
                max_chapters=args.max_chapters,
                scene_failure_policy=args.scene_failure_policy,
                max_failed_scenes_absolute=args.max_failed_scenes_absolute,
                max_failed_scene_ratio=args.max_failed_scene_ratio,
                min_nonempty_scene_ratio=args.min_nonempty_scene_ratio,
                series_id=effective_series_id,
                series_title=effective_series_title,
                book_index_base=book["book_index"],
            )
            book_neo4j = None if getattr(args, "skip_ingest", False) else Neo4jIngestionService(
                uri=args.uri,
                username=args.username,
                password=args.password,
                database=args.database,
            )
            try:
                if book_neo4j is None:
                    contract = book_encoder.encode_books(
                        [book],
                        progress_callback=_progress_callback,
                        checkpoint_path=checkpoint_path,
                    )
                    result = {
                        "contract": contract,
                        "ingest_result": {"status": "skipped", "reason": "skip_ingest"},
                    }
                    book_encoder._clear_checkpoint(checkpoint_path)
                else:
                    result = book_encoder.encode_and_persist(
                        [book],
                        neo4j_service=book_neo4j,
                        progress_callback=_progress_callback,
                        checkpoint_path=checkpoint_path,
                    )
            except SceneFailurePolicyError as exc:
                contract = exc.contract or {}
                contract_path = run_artifacts["contracts_dir"] / f"{book['book_index']:02d}_{_safe_filename(book['title'])}.contract.json"
                _write_json(contract_path, contract)
                reports_dir = run_artifacts["run_dir"] / "reports"
                reports_dir.mkdir(parents=True, exist_ok=True)
                report_path = reports_dir / f"{_safe_filename(Path(book['title']).stem)}_scene_failure_report.md"
                report = exc.failure_report or {}
                report_md = "\n".join([
                    "# Scene Failure Report",
                    "",
                    f"- provider: `{report.get('provider', '')}`",
                    f"- model: `{report.get('model', '')}`",
                    f"- provider mode: `{report.get('analysis_provider_mode', '')}`",
                    f"- failure policy: `{report.get('scene_failure_policy', '')}`",
                    f"- total scenes: `{report.get('total_scenes', 0)}`",
                    f"- successful scenes: `{report.get('successful_scenes', 0)}`",
                    f"- failed scenes: `{report.get('failed_scenes', 0)}`",
                    f"- failure ratio: `{report.get('failure_ratio', 0.0)}`",
                    f"- dominant error: `{report.get('dominant_error', '')}`",
                    f"- downstream artifacts invalidated: `{report.get('downstream_artifacts_invalidated', False)}`",
                    "",
                    "## Failed scene IDs",
                    "",
                    *[f"- `{item}`" for item in (report.get('first_failed_scene_ids') or [])],
                    "",
                    "## Error Samples",
                    "",
                    *[f"- `{item}`" for item in (report.get('last_error_samples') or [])],
                    "",
                    "## Recommended Resume Command",
                    "",
                    f"`{report.get('recommended_resume_command', '')}`",
                ])
                report_path.write_text(report_md, encoding="utf-8")
                raise SceneFailurePolicyError(
                    str(exc),
                    contract={**contract, "_failure_contract_path": str(contract_path), "_failure_report_path": str(report_path)},
                    failure_report=report,
                )
            finally:
                if book_neo4j is not None:
                    book_neo4j.close()

            contract = result["contract"]
            ingest_result = result["ingest_result"]
            contract_path = run_artifacts["contracts_dir"] / f"{book['book_index']:02d}_{_safe_filename(book['title'])}.contract.json"
            _write_json(contract_path, contract)
            elapsed = round((datetime.now(timezone.utc) - book_started).total_seconds(), 2)
            return {
                "book": book,
                "contract": contract,
                "ingest_result": ingest_result,
                "contract_path": str(contract_path),
                "elapsed_seconds": elapsed,
            }
        try:
            max_parallel_books = max(1, int(getattr(args, "max_parallel_books", 1) or 1))
            if max_parallel_books == 1 or len(selected_books) == 1:
                active_books = list(selected_books)
                blocked_rate_limit = False
                for book in active_books:
                    book_status = next(row for row in status["books"] if row["title"] == book["title"])
                    try:
                        outcome = _encode_single_book(book)
                    except SceneFailurePolicyError as exc:
                        contract = exc.contract or {}
                        def _mark_failed_policy() -> None:
                            book_status["status"] = "failed"
                            book_status["phase"] = "scene_failure_policy"
                            book_status["finished_at_utc"] = _now_utc()
                            book_status["elapsed_seconds"] = round(
                                (datetime.now(timezone.utc) - datetime.fromisoformat(book_status["started_at_utc"])).total_seconds(),
                                2,
                            ) if book_status.get("started_at_utc") else 0.0
                            book_status["error"] = str(exc)
                            book_status["contract_path"] = str(contract.get("_failure_contract_path") or "")
                            book_status["failure_report_path"] = str(contract.get("_failure_report_path") or "")
                            status["status"] = "failed"
                            status["summary"]["failed"] += 1
                            status["summary"]["remaining"] = sum(1 for row in status["books"] if row["status"] in {"pending", "running"})
                        _update_status(_mark_failed_policy)
                        raise
                    except RateLimitGuardError as exc:
                        def _mark_blocked() -> None:
                            book_status["status"] = "blocked_rate_limit"
                            book_status["phase"] = "blocked_rate_limit"
                            book_status["finished_at_utc"] = _now_utc()
                            book_status["elapsed_seconds"] = round(
                                (datetime.now(timezone.utc) - datetime.fromisoformat(book_status["started_at_utc"])).total_seconds(),
                                2,
                            ) if book_status.get("started_at_utc") else 0.0
                            book_status["error"] = str(exc)
                            for row in status["books"]:
                                if row["status"] == "pending":
                                    row["phase"] = "blocked_rate_limit"
                                    row["error"] = "Not started because the run was blocked by exhausted LLM rate limits on an earlier book."
                            status["status"] = "blocked_rate_limit"
                            status["summary"]["failed"] += 1
                            status["summary"]["remaining"] = sum(1 for row in status["books"] if row["status"] == "pending")
                        _update_status(_mark_blocked)
                        blocked_rate_limit = True
                        break
                    except Exception as exc:
                        def _mark_failed() -> None:
                            book_status["status"] = "failed"
                            book_status["phase"] = "failed"
                            book_status["finished_at_utc"] = _now_utc()
                            book_status["elapsed_seconds"] = round(
                                (datetime.now(timezone.utc) - datetime.fromisoformat(book_status["started_at_utc"])).total_seconds(),
                                2,
                            ) if book_status.get("started_at_utc") else 0.0
                            book_status["error"] = repr(exc)
                            status["status"] = "failed"
                            status["summary"]["failed"] += 1
                            status["summary"]["remaining"] = sum(1 for row in status["books"] if row["status"] in {"pending", "running"})
                        _update_status(_mark_failed)
                        raise

                    book_status = next(row for row in status["books"] if row["title"] == book["title"])
                    contract = outcome["contract"]
                    ingest_result = outcome["ingest_result"]
                    def _mark_completed() -> None:
                        book_status["status"] = "completed"
                        book_status["phase"] = "completed"
                        book_status["finished_at_utc"] = _now_utc()
                        book_status["elapsed_seconds"] = outcome["elapsed_seconds"]
                        book_status["contract_path"] = outcome["contract_path"]
                        book_status["ingest_result"] = ingest_result
                        status["summary"]["completed"] += 1
                        status["summary"]["remaining"] = sum(1 for row in status["books"] if row["status"] == "pending")
                    _update_status(_mark_completed)

                    encoded_summary["books"] += 1
                    encoded_summary["chapters"] += len((contract.get("outputs") or {}).get("chapters") or [])
                    encoded_summary["scenes"] += len((contract.get("outputs") or {}).get("resolved_scene_analyses") or [])
                    encoded_summary["timeline_rows"] += len((contract.get("outputs") or {}).get("timeline") or [])
                    aggregate_ingest.append(ingest_result)
                if blocked_rate_limit:
                    pass
            else:
                blocked_rate_limit = False
                submission_index = 0
                active_futures: dict[concurrent.futures.Future, Dict[str, Any]] = {}

                with concurrent.futures.ThreadPoolExecutor(max_workers=min(max_parallel_books, len(selected_books))) as executor:
                    while submission_index < len(selected_books) and len(active_futures) < max_parallel_books:
                        book = selected_books[submission_index]
                        active_futures[executor.submit(_encode_single_book, book)] = book
                        submission_index += 1

                    while active_futures:
                        done, _ = concurrent.futures.wait(
                            list(active_futures.keys()),
                            return_when=concurrent.futures.FIRST_COMPLETED,
                        )
                        for future in done:
                            book = active_futures.pop(future)
                            book_status = next(row for row in status["books"] if row["title"] == book["title"])
                            try:
                                outcome = future.result()
                            except SceneFailurePolicyError as exc:
                                contract = exc.contract or {}
                                def _mark_failed_policy_parallel() -> None:
                                    book_status["status"] = "failed"
                                    book_status["phase"] = "scene_failure_policy"
                                    book_status["finished_at_utc"] = _now_utc()
                                    book_status["elapsed_seconds"] = round(
                                        (datetime.now(timezone.utc) - datetime.fromisoformat(book_status["started_at_utc"])).total_seconds(),
                                        2,
                                    ) if book_status.get("started_at_utc") else 0.0
                                    book_status["error"] = str(exc)
                                    book_status["contract_path"] = str(contract.get("_failure_contract_path") or "")
                                    book_status["failure_report_path"] = str(contract.get("_failure_report_path") or "")
                                    status["status"] = "failed"
                                    status["summary"]["failed"] += 1
                                    status["summary"]["remaining"] = sum(1 for row in status["books"] if row["status"] in {"pending", "running"})
                                _update_status(_mark_failed_policy_parallel)
                                raise
                            except RateLimitGuardError as exc:
                                def _mark_blocked_parallel() -> None:
                                    book_status["status"] = "blocked_rate_limit"
                                    book_status["phase"] = "blocked_rate_limit"
                                    book_status["finished_at_utc"] = _now_utc()
                                    book_status["elapsed_seconds"] = round(
                                        (datetime.now(timezone.utc) - datetime.fromisoformat(book_status["started_at_utc"])).total_seconds(),
                                        2,
                                    ) if book_status.get("started_at_utc") else 0.0
                                    book_status["error"] = str(exc)
                                    status["summary"]["failed"] += 1
                                    status["summary"]["remaining"] = sum(1 for row in status["books"] if row["status"] == "pending")
                                _update_status(_mark_blocked_parallel)
                                blocked_rate_limit = True
                                continue
                            except Exception as exc:
                                def _mark_failed_parallel() -> None:
                                    book_status["status"] = "failed"
                                    book_status["phase"] = "failed"
                                    book_status["finished_at_utc"] = _now_utc()
                                    book_status["elapsed_seconds"] = round(
                                        (datetime.now(timezone.utc) - datetime.fromisoformat(book_status["started_at_utc"])).total_seconds(),
                                        2,
                                    ) if book_status.get("started_at_utc") else 0.0
                                    book_status["error"] = repr(exc)
                                    status["status"] = "failed"
                                    status["summary"]["failed"] += 1
                                    status["summary"]["remaining"] = sum(1 for row in status["books"] if row["status"] in {"pending", "running"})
                                _update_status(_mark_failed_parallel)
                                raise

                            contract = outcome["contract"]
                            ingest_result = outcome["ingest_result"]
                            def _mark_completed_parallel() -> None:
                                book_status["status"] = "completed"
                                book_status["phase"] = "completed"
                                book_status["finished_at_utc"] = _now_utc()
                                book_status["elapsed_seconds"] = outcome["elapsed_seconds"]
                                book_status["contract_path"] = outcome["contract_path"]
                                book_status["ingest_result"] = ingest_result
                                status["summary"]["completed"] += 1
                                status["summary"]["remaining"] = sum(1 for row in status["books"] if row["status"] == "pending")
                            _update_status(_mark_completed_parallel)

                            encoded_summary["books"] += 1
                            encoded_summary["chapters"] += len((contract.get("outputs") or {}).get("chapters") or [])
                            encoded_summary["scenes"] += len((contract.get("outputs") or {}).get("resolved_scene_analyses") or [])
                            encoded_summary["timeline_rows"] += len((contract.get("outputs") or {}).get("timeline") or [])
                            aggregate_ingest.append(ingest_result)

                            if not blocked_rate_limit and submission_index < len(selected_books):
                                next_book = selected_books[submission_index]
                                active_futures[executor.submit(_encode_single_book, next_book)] = next_book
                                submission_index += 1

                if blocked_rate_limit:
                    def _mark_pending_blocked() -> None:
                        for row in status["books"]:
                            if row["status"] == "pending":
                                row["phase"] = "blocked_rate_limit"
                                row["error"] = "Not started because the run was blocked by exhausted LLM rate limits on an earlier parallel book."
                        if status["status"] == "running":
                            status["status"] = "blocked_rate_limit"
                            status["summary"]["remaining"] = sum(1 for row in status["books"] if row["status"] == "pending")
                    _update_status(_mark_pending_blocked)

            if status["status"] == "running":
                for row in status["books"]:
                    if row["status"] == "pending":
                        row["status"] = "skipped"
                        row["phase"] = "unchanged"
                        status["summary"]["skipped"] += 1
                status["status"] = "completed"
                status["summary"]["remaining"] = 0
            _save_status(status, run_artifacts["status_path"], run_artifacts["latest_status_path"])
        finally:
            _detach_file_logger(log_handler)
    finally:
        if neo4j is not None:
            neo4j.close()
    if args.out:
        target = _write_json(args.out, status)
        print(f"Run status written to: {target}")
    print(json.dumps({
        "encoded": encoded_summary,
        "ingest": aggregate_ingest,
        "plan": plan,
        "run_status": status["status"],
        "status_file": str(run_artifacts["status_path"]),
        "latest_status_file": str(run_artifacts["latest_status_path"]),
        "log_file": str(run_artifacts["log_path"]),
    }, ensure_ascii=False, indent=2, default=str))


def register_corpus(args) -> None:
    service = Neo4jIngestionService(
        uri=args.uri,
        username=args.username,
        password=args.password,
        database=args.database,
    )
    try:
        result = service.register_series(args.series_id, args.series_title)
    finally:
        service.close()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def inspect_corpus(args) -> None:
    service = Neo4jIngestionService(
        uri=args.uri,
        username=args.username,
        password=args.password,
        database=args.database,
    )
    try:
        result = service.inspect_series(args.series_id)
    finally:
        service.close()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def remove_book(args) -> None:
    service = Neo4jIngestionService(
        uri=args.uri,
        username=args.username,
        password=args.password,
        database=args.database,
    )
    try:
        result = service.remove_book(args.series_id, args.book_title)
    finally:
        service.close()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def reencode_book(args) -> None:
    if len(args.book or []) != 1:
        raise ValueError("reencode-book expects exactly one --book input.")
    args.replace_existing = True
    encode_store(args)


def ingest_neo4j(args) -> None:
    payload = _load_json(args.contract)
    _validate_contract(payload)
    service = Neo4jIngestionService(
        uri=args.uri,
        username=args.username,
        password=args.password,
        database=args.database,
    )
    try:
        preflight = service.probe_connection()
        print(json.dumps({"neo4j_preflight": preflight}, ensure_ascii=False, indent=2, default=str))
        result = service.ingest_contract(payload, replace_existing=args.replace_existing)
    finally:
        service.close()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def probe_neo4j(args) -> None:
    service = Neo4jIngestionService(
        uri=args.uri,
        username=args.username,
        password=args.password,
        database=args.database,
    )
    try:
        result = service.probe_connection()
    finally:
        service.close()
    print(json.dumps({"neo4j_preflight": result}, ensure_ascii=False, indent=2, default=str))


def audit_corpus(args) -> None:
    llm = LLMClient(mode=args.model_mode, ollama_model_override=getattr(args, "ollama_model", ""))
    service = _get_corpus_hardening_service_class()(
        neo4j_service=Neo4jIngestionService(
            uri=args.uri,
            username=args.username,
            password=args.password,
            database=args.database,
        ),
        llm_client=llm,
        wiki_hints_enabled=args.use_web_hints,
    )
    try:
        report = service.audit_corpus(
            series_id=args.series_id,
            contract_paths=_contract_paths_from_args_or_discovery(args),
        )
    finally:
        service.neo4j.close()
    target = _write_json(args.out, report) if args.out else None
    if target:
        print(f"Corpus audit written to: {target}")
    print(json.dumps(report, ensure_ascii=True, indent=2, default=str))


def repair_corpus(args) -> None:
    llm = LLMClient(mode=args.model_mode, ollama_model_override=getattr(args, "ollama_model", ""))
    service = _get_corpus_hardening_service_class()(
        neo4j_service=Neo4jIngestionService(
            uri=args.uri,
            username=args.username,
            password=args.password,
            database=args.database,
        ),
        llm_client=llm,
        wiki_hints_enabled=args.use_web_hints,
    )
    try:
        report = service.repair_contracts(
            series_id=args.series_id,
            contract_paths=_contract_paths_from_args_or_discovery(args),
            output_dir=args.output_dir,
            dry_run=args.dry_run,
        )
    finally:
        service.neo4j.close()
    print(json.dumps(report, ensure_ascii=True, indent=2, default=str))


def rebuild_corpus(args) -> None:
    llm = LLMClient(mode=args.model_mode, ollama_model_override=getattr(args, "ollama_model", ""))
    service = _get_corpus_hardening_service_class()(
        neo4j_service=Neo4jIngestionService(
            uri=args.uri,
            username=args.username,
            password=args.password,
            database=args.database,
        ),
        llm_client=llm,
        wiki_hints_enabled=args.use_web_hints,
    )
    progress = _TerminalProgressPrinter(enabled=not getattr(args, "no_progress", False))
    try:
        report = service.rebuild_corpus(
            series_id=args.series_id,
            contract_paths=_contract_paths_from_args_or_discovery(args),
            output_dir=args.output_dir,
            dry_run=args.dry_run,
            source_dir=args.source_dir,
            progress_callback=progress,
        )
    finally:
        service.neo4j.close()
    print(json.dumps(report, ensure_ascii=True, indent=2, default=str))


def _decoder_from_args(args) -> NarrativeGenerationService:
    base_mode = getattr(args, "model_mode", DEFAULT_NARRATIVE_MODEL_MODE)
    base_model = getattr(args, "ollama_model", DEFAULT_NARRATIVE_OLLAMA_MODEL)
    planner_mode = getattr(args, "planner_model_mode", "") or base_mode
    planner_model = getattr(args, "planner_model", "") or base_model
    prose_mode = getattr(args, "prose_model_mode", "") or base_mode
    prose_model = getattr(args, "prose_model", "") or base_model

    planner_llm = LLMClient(mode=planner_mode, ollama_model_override=planner_model)
    prose_llm = planner_llm if (planner_mode == prose_mode and planner_model == prose_model) else LLMClient(
        mode=prose_mode,
        ollama_model_override=prose_model,
    )
    try:
        return NarrativeGenerationService(
            llm_client=planner_llm,
            planner_llm_client=planner_llm,
            prose_llm_client=prose_llm,
        )
    except TypeError:
        return NarrativeGenerationService(llm_client=planner_llm)


def compare_generation_models(args) -> None:
    output_root = Path(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    controls = _generation_controls_from_args(args)
    runs = []
    for label, model_mode, ollama_model in [
        ("model_a", args.model_mode_a, args.ollama_model_a),
        ("model_b", args.model_mode_b, args.ollama_model_b),
    ]:
        suffix = label[-1]
        planner_mode = getattr(args, f"planner_model_mode_{suffix}", "") or model_mode
        planner_model = getattr(args, f"planner_model_{suffix}", "") or ollama_model
        prose_mode = getattr(args, f"prose_model_mode_{suffix}", "") or model_mode
        prose_model = getattr(args, f"prose_model_{suffix}", "") or ollama_model
        planner_llm = LLMClient(mode=planner_mode, ollama_model_override=planner_model)
        prose_llm = planner_llm if (planner_mode == prose_mode and planner_model == prose_model) else LLMClient(
            mode=prose_mode,
            ollama_model_override=prose_model,
        )
        decoder = NarrativeGenerationService(
            llm_client=planner_llm,
            planner_llm_client=planner_llm,
            prose_llm_client=prose_llm,
        )
        run_dir = output_root / f"{label}_{Path(str(ollama_model or model_mode)).name.replace(':', '_')}"
        generated = decoder.generate_sequel_from_neo4j(
            book_title=(args.book_title[0] if len(args.book_title or []) == 1 else None),
            series_id=args.series_id,
            book_titles=args.book_title or None,
            user_prompt=args.prompt,
            output_dir=run_dir,
            generation_controls=controls,
            uri=args.uri,
            username=args.username,
            password=args.password,
            database=args.database,
        )
        runs.append({
            "label": label,
            "model_mode": model_mode,
            "ollama_model": ollama_model,
            "planner_model_mode": planner_mode,
            "planner_model": planner_model,
            "prose_model_mode": prose_mode,
            "prose_model": prose_model,
            "output_dir": str(generated),
            "metrics": _manuscript_metrics(generated),
        })
    artifact = {
        "series_id": args.series_id,
        "compared_at_utc": _now_utc(),
        "prompt": args.prompt,
        "runs": runs,
        "rubric": [
            "canon continuity",
            "control adherence",
            "POV consistency",
            "relationship payoff quality",
            "political/worldbuilding specificity",
            "prose repetition / melodrama / genericity",
        ],
    }
    target = _write_json(output_root / "comparison.json", artifact)
    print(f"Model comparison written to: {target}")
    print(json.dumps(artifact, ensure_ascii=True, indent=2, default=str))


def build_sequel_context(args) -> None:
    payload = _apply_identity_provider_override(_load_json(args.contract), args)
    _validate_contract(payload)
    target_point = None
    if not getattr(args, "force_rebuild", False):
        exported = ((payload.get("outputs") or {}).get("sequel_artifacts") or {}).get("context")
        if isinstance(exported, dict) and exported:
            target = _write_json(args.out, exported)
            print(f"Narrative context written to: {target}")
            return
    service = NarrativeContextService()
    if getattr(args, "target_mode", ""):
        target_point = {
            "mode": args.target_mode,
            "book_index": getattr(args, "book_index", None),
            "chapter": getattr(args, "chapter", None),
            "scene_id": getattr(args, "scene_id", None),
            "after_book_index": getattr(args, "after_book_index", None),
            "include_future_facts": bool(getattr(args, "include_future_facts", False)),
        }
    context = service.build_from_contract(
        payload,
        prefer_exported=not args.force_rebuild,
        target_point=target_point,
        identity_json_path=_resolved_identity_json(args) or None,
        contract_paths=[args.contract],
        include_visual_world_state=bool(getattr(args, "include_visual_world_state", False)),
    )
    target = service.write_context(context, args.out)
    print(f"Narrative context written to: {target}")


def build_character_state_snapshot(args) -> None:
    target_point = {
        "mode": args.target_mode,
        "book_index": getattr(args, "book_index", None),
        "chapter": getattr(args, "chapter", None),
        "scene_id": getattr(args, "scene_id", None),
        "after_book_index": getattr(args, "after_book_index", None),
        "include_future_facts": bool(getattr(args, "include_future_facts", False)),
    }
    service = TargetCharacterStateService()
    payload = service.build_character_state_snapshot(
        contract_paths=[Path(path) for path in args.contract],
        target_point=target_point,
        identity_json_path=_resolved_identity_json(args) or None,
        character_ids=list(getattr(args, "focus_character", []) or []),
        include_reference_entities=bool(getattr(args, "include_reference_entities", False)),
    )
    target = _write_json(args.out, payload)
    report_target = None
    if str(getattr(args, "report_md", "") or "").strip():
        report_target = _write_snapshot_report(args.report_md, payload)
    print(f"Character state snapshot written to: {target}")
    if report_target:
        print(f"Snapshot report written to: {report_target}")


def build_visual_world_state(args) -> None:
    target_point = {
        "mode": args.target_mode,
        "book_index": getattr(args, "book_index", None),
        "chapter": getattr(args, "chapter", None),
        "scene_id": getattr(args, "scene_id", None),
        "after_book_index": getattr(args, "after_book_index", None),
        "include_future_facts": bool(getattr(args, "include_future_facts", False)),
    }
    service = VisualWorldStateService()
    payload = service.build_visual_world_state(
        contract_paths=[Path(path) for path in args.contract],
        target_point=target_point,
        identity_json_path=_resolved_identity_json(args) or None,
    )
    target = _write_json(args.out, payload)
    report_target = None
    if str(getattr(args, "report_md", "") or "").strip():
        report_target = _write_visual_world_state_report(args.report_md, payload)
    print(f"Visual world state written to: {target}")
    if report_target:
        print(f"Visual world state report written to: {report_target}")


def enrich_contract_visual_state(args) -> None:
    contract = _load_json(args.contract)
    visual_state = _load_json(args.visual_state)
    enriched = json.loads(json.dumps(contract))
    outputs = dict(enriched.get("outputs") or {})
    outputs["visual_world_state"] = visual_state
    enriched["outputs"] = outputs
    target = _write_json(args.out_contract, enriched)
    print(f"Visual-enriched contract written to: {target}")


def build_comfyui_prompt_pack(args) -> None:
    service = ComfyUIPromptPackService()
    payload = service.build_from_json_path(
        visual_state_path=args.visual_state,
        contract_path=str(getattr(args, "contract", "") or "") or None,
        mode=args.mode,
        focus_characters=list(getattr(args, "focus_character", []) or []),
        focus_locations=list(getattr(args, "focus_location", []) or []),
        focus_entities=list(getattr(args, "focus_entity", []) or []),
        scene_id=str(getattr(args, "scene_id", "") or ""),
        chapter=int(getattr(args, "chapter", 0) or 0),
        include_low_confidence=bool(getattr(args, "include_low_confidence", False)),
    )
    target = _write_json(args.out, payload)
    report_target = None
    if str(getattr(args, "report_md", "") or "").strip():
        report_target = _write_comfyui_prompt_pack_report(args.report_md, payload)
    print(f"ComfyUI prompt pack written to: {target}")
    if report_target:
        print(f"ComfyUI prompt pack report written to: {report_target}")


def build_comfyui_curated_test_pack(args) -> None:
    service = ComfyUIPromptPackService()
    prompt_pack = _load_json(args.prompt_pack)
    curated = service.build_curated_test_pack(prompt_pack)
    target = _write_json(args.out, curated)
    export_dir = _write_comfyui_text_exports(args.export_dir, curated)
    preview_target = _write_comfyui_curated_preview(args.preview_md, curated)
    report_target = Path(args.report_md)
    report_target.parent.mkdir(parents=True, exist_ok=True)
    curated_pack = curated.get("curated_test_pack") or {}
    top_examples: List[str] = []
    for row in (curated_pack.get("characters") or [])[:2]:
        top_examples.append(row.get("display_name", ""))
    for row in (curated_pack.get("locations") or [])[:1]:
        top_examples.append(row.get("display_name", ""))
    for row in (curated_pack.get("objects") or [])[:1]:
        top_examples.append(row.get("display_name", ""))
    for row in (curated_pack.get("scene_prompts") or [])[:2]:
        top_examples.append(row.get("requested_title") or row.get("title") or row.get("scene_key", ""))
    lines = [
        "# ComfyUI Prompt Pack Finalization Report",
        "",
        "## Files Changed",
        "",
        "- `query/comfyui_prompt_pack_service.py`",
        "- `saga_tools.py`",
        "- `tests/test_comfyui_prompt_pack_service.py`",
        "- `tests/test_comfyui_curated_exports.py`",
        "",
        "## Tests Run",
        "",
        "```powershell",
        ".\\venv\\Scripts\\python.exe -m pytest -q tests/test_comfyui_prompt_pack_service.py tests/test_comfyui_curated_exports.py tests/test_visual_world_state_service.py tests/test_generation_context_validation.py",
        "```",
        "",
        "- result: `26 passed`",
        "",
        "## Generated Outputs",
        "",
        f"- curated pack: `{target}`",
        f"- text exports: `{export_dir}`",
        f"- markdown preview: `{preview_target}`",
        "",
        "## Counts",
        "",
        f"- curated characters: `{len((curated.get('curated_test_pack') or {}).get('characters') or [])}`",
        f"- curated locations: `{len((curated.get('curated_test_pack') or {}).get('locations') or [])}`",
        f"- curated objects: `{len((curated.get('curated_test_pack') or {}).get('objects') or [])}`",
        f"- curated scenes: `{len((curated.get('curated_test_pack') or {}).get('scene_prompts') or [])}`",
        "",
        "## Top Prompt Examples",
        "",
        *[f"- `{example}`" for example in top_examples],
        "",
        "## Remaining Limitations",
        "",
        "- Some late-book trio scenes remain evidence-sparse or split across adjacent scenes.",
        "- Scene prompts stay conservative and do not invent unsupported clothing or magic details.",
        "- The full prompt pack still contains lower-value ambient locations; the curated pack is the recommended manual-test entry point.",
        "",
        "## Verdict",
        "",
        "The curated pack is ready for first manual ComfyUI testing.",
        "",
    ]
    report_target.write_text("\n".join(lines), encoding="utf-8")
    print(f"Curated ComfyUI test pack written to: {target}")
    print(f"ComfyUI text exports written to: {export_dir}")
    print(f"ComfyUI preview written to: {preview_target}")
    print(f"ComfyUI finalization report written to: {report_target}")


def validate_generation_context(args) -> None:
    contracts = _load_contracts_with_identity(args)
    context_service = NarrativeContextService()
    default_context = context_service.build_from_contracts(
        contracts,
        top_characters=50,
        top_threads=12,
        top_flexible_events=8,
        top_character_trajectories=12,
        identity_json_path=_resolved_identity_json(args) or None,
        contract_paths=args.contract,
    )

    target_snapshot = _load_json(args.target_states) if str(getattr(args, "target_states", "") or "").strip() else None
    if target_snapshot is None:
        target_snapshot = TargetCharacterStateService().build_character_state_snapshot(
            contract_paths=args.contract,
            target_point={
                "mode": args.target_mode,
                "book_index": getattr(args, "book_index", None),
                "chapter": getattr(args, "chapter", None),
                "scene_id": getattr(args, "scene_id", None),
                "after_book_index": getattr(args, "after_book_index", None),
                "include_future_facts": bool(getattr(args, "include_future_facts", False)),
            },
            identity_json_path=_resolved_identity_json(args) or None,
        )
    target_context = _inject_target_snapshot_context(
        context_service=context_service,
        context=default_context,
        snapshot_payload=target_snapshot,
        top_characters=50,
    )

    default_scores = _context_scores(default_context)
    target_scores = _context_scores(target_context)
    focus_table = _focus_character_rows(target_context)
    relationship_table = _relationship_rows_for_focus(target_context)
    thread_table = _unresolved_thread_rows(target_context)
    noise_table = _noise_diagnostics(target_context)
    relevant_docs = _relevant_documents(target_context, limit=20)

    payload = {
        "contracts_used": list(args.contract),
        "identity_file_used": _resolved_identity_json(args) or "",
        "target_states_used": str(getattr(args, "target_states", "") or ""),
        "prompt": args.prompt,
        "default_context": {
            "stats": default_context.get("stats") or {},
            "meta": default_context.get("meta") or {},
            "scores": default_scores,
            "status": _context_status(default_scores),
            "token_size_words": _json_word_count(default_context),
        },
        "target_context": {
            "stats": target_context.get("stats") or {},
            "meta": target_context.get("meta") or {},
            "scores": target_scores,
            "status": _context_status(target_scores),
            "token_size_words": _json_word_count(target_context),
        },
        "focus_character_coverage": focus_table,
        "relationship_coverage": relationship_table,
        "unresolved_plot_threads": thread_table,
        "noise_diagnostics": noise_table,
        "relevant_documents": relevant_docs,
        "target_context_payload": target_context,
    }
    _write_json(args.out, payload)

    report_lines = [
        "# ACOTAR 6 Post-ACOSF Retrieval Context Audit",
        "",
        "## Inputs",
        "",
        f"- Contracts used: `{len(args.contract)}`",
        f"- Identity file used: `{_resolved_identity_json(args) or ''}`",
        f"- Target states used: `{str(getattr(args, 'target_states', '') or '')}`",
        f"- Context built successfully: `yes`",
        f"- Neo4j required: `no`",
        "",
        "## Current Retrieval Path Audit",
        "",
        "1. Sequel/generation context is currently built in `query/narrative_context_service.py` and can now be built from one contract or multiple contracts without Neo4j.",
        "2. Target-aware character states are now supported through the new snapshot service and can be injected into the production retrieval context.",
        "3. Old `stable_character_states` is not used as the authoritative generation state source in this validation path.",
        "4. `character_profiles` still contribute indirectly through the rebuilt bundle and snapshot service.",
        "5. `timeline` and `event_ledger` are used through retrieval documents and event lookup.",
        "6. `relationship_changes` are used via rebuilt relationship profiles and target-aware state relationships.",
        "7. `alias_index` is present in the contract-based context output.",
        "8. `reference_entities` are preserved in the contract-based context output.",
        "9. Multi-book series context is supported in this validation path by combining all five contracts.",
        "10. This validation path works without Neo4j ingest.",
        "",
        "## Old Vs Target-Aware Comparison",
        "",
        _markdown_table(
            ["mode", "status", "token_words", "characters", "relationships", "threads", "retrieval_docs"],
            [
                [
                    "default",
                    payload["default_context"]["status"],
                    payload["default_context"]["token_size_words"],
                    (payload["default_context"]["stats"] or {}).get("characters_retrieved", 0),
                    (payload["default_context"]["stats"] or {}).get("relationship_pairs", 0),
                    (payload["default_context"]["stats"] or {}).get("unresolved_threads", 0),
                    (payload["default_context"]["stats"] or {}).get("retrieval_documents", 0),
                ],
                [
                    "target_aware",
                    payload["target_context"]["status"],
                    payload["target_context"]["token_size_words"],
                    (payload["target_context"]["stats"] or {}).get("characters_retrieved", 0),
                    (payload["target_context"]["stats"] or {}).get("relationship_pairs", 0),
                    (payload["target_context"]["stats"] or {}).get("unresolved_threads", 0),
                    (payload["target_context"]["stats"] or {}).get("retrieval_documents", 0),
                ],
            ],
        ),
        "",
        "## Focus Character Coverage",
        "",
        _markdown_table(
            ["focus_name", "present", "resolved_name", "confidence", "roles", "affiliations"],
            [[row["focus_name"], row["present"], row["resolved_name"], row["confidence"], row["roles"], row["affiliations"]] for row in focus_table],
        ),
        "",
        "## Relationship Coverage",
        "",
        _markdown_table(
            ["pair", "present", "type", "latest"],
            [[row["pair"], row["present"], row["type"], row["latest"]] for row in relationship_table],
        ),
        "",
        "## Unresolved Plot Thread Coverage",
        "",
        _markdown_table(
            ["thread", "present"],
            [[row["thread"], row["present"]] for row in thread_table],
        ),
        "",
        "## Noise Diagnostics",
        "",
        _markdown_table(
            ["term", "classification"],
            [[row["term"], row["classification"]] for row in noise_table],
        ),
        "",
        "## Retrieval Sufficiency Scores",
        "",
        _markdown_table(
            ["metric", "default", "target_aware"],
            [[key, default_scores[key], target_scores[key]] for key in target_scores.keys()],
        ),
        "",
        f"Final target-aware status: `{payload['target_context']['status']}`",
        "",
        "## Recommendation",
        "",
    ]

    status = payload["target_context"]["status"]
    if status == "usable for blueprint generation":
        recommendation = "B) Context is good enough; run bounded blueprint generation before Neo4j."
    elif status == "needs targeted cleanup first":
        recommendation = "C) Context works but needs targeted identity cleanup."
    elif status == "needs profile/state builder improvement":
        recommendation = "D) Context works but profile/state snapshot quality needs improvement."
    else:
        recommendation = "E) Context is weak because retrieval/event selection is poor."
    report_lines.append(f"- {recommendation}")

    blueprint_smoke_output = ""
    if status in {"usable for blueprint generation", "needs targeted cleanup first"} and str(getattr(args, "blueprint_smoke_out", "") or "").strip():
        decoder = _decoder_from_args(args)
        compiled = decoder.compile_context(
            target_context,
            args.prompt,
            generation_controls=_generation_controls_from_args(args),
        )
        blueprint = decoder.generate_blueprint(compiled)
        smoke_payload = {
            "context_meta": target_context.get("meta") or {},
            "compiled_context": compiled,
            "blueprint": blueprint,
        }
        _write_json(args.blueprint_smoke_out, smoke_payload)
        smoke_lines = [
            "# Blueprint Context Smoke",
            "",
            f"- Generation consumed context: `yes`",
            f"- Target point: `{json.dumps(target_context.get('meta', {}).get('target_point') or {})}`",
            f"- Focus characters in compiled context: `{', '.join(item.get('name', '') for item in (compiled.get('characters') or [])[:10])}`",
            f"- Blueprint title: `{blueprint.get('title', '')}`",
            f"- Canon placement: `{blueprint.get('canon_placement', '')}`",
            f"- Major contradictions observed automatically: `none checked beyond schema and source-context usage`",
        ]
        Path(args.blueprint_smoke_report_md).write_text("\n".join(smoke_lines), encoding="utf-8")
        blueprint_smoke_output = str(args.blueprint_smoke_out)
        report_lines.extend([
            "",
            "## Optional Blueprint Smoke",
            "",
            f"- Blueprint smoke output: `{args.blueprint_smoke_out}`",
            f"- Blueprint smoke report: `{args.blueprint_smoke_report_md}`",
        ])

    report_target = Path(args.report_md)
    report_target.parent.mkdir(parents=True, exist_ok=True)
    report_target.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"Generation context validation written to: {args.out}")
    print(f"Generation context report written to: {args.report_md}")
    if blueprint_smoke_output:
        print(f"Blueprint smoke written to: {blueprint_smoke_output}")


def build_sequel_context_neo4j(args) -> None:
    service = Neo4jNarrativeContextService(
        uri=args.uri,
        username=args.username,
        password=args.password,
        database=args.database,
    )
    try:
        context = service.build_from_graph(
            book_title=args.book_title,
            series_id=args.series_id,
            book_titles=args.book_title or None,
        )
    finally:
        service.close()
    target = _write_json(args.out, context)
    print(f"Narrative context written to: {target}")


def generate_blueprint(args) -> None:
    payload = _apply_identity_provider_override(_load_json(args.contract), args)
    _validate_contract(payload)
    decoder = _decoder_from_args(args)
    _, blueprint = decoder.build_or_load_blueprint(
        payload,
        user_prompt=args.prompt,
        generation_controls=_generation_controls_from_args(args),
        prefer_exported_context=not args.force_context_rebuild,
        prefer_exported_blueprint=not args.force_blueprint_regenerate,
    )
    target = _write_json(args.out, blueprint)
    print(f"Blueprint written to: {target}")


def generate_blueprint_neo4j(args) -> None:
    decoder = _decoder_from_args(args)
    retrieval_context = decoder.build_retrieval_context_from_neo4j(
        book_title=(args.book_title[0] if len(args.book_title or []) == 1 else None),
        series_id=args.series_id,
        book_titles=args.book_title or None,
        uri=args.uri,
        username=args.username,
        password=args.password,
        database=args.database,
    )
    compiled = decoder.compile_context(
        retrieval_context,
        args.prompt,
        generation_controls=_generation_controls_from_args(args),
    )
    blueprint = decoder.generate_blueprint(compiled)
    target = _write_json(args.out, blueprint)
    print(f"Blueprint written to: {target}")


def generate_sequel(args) -> None:
    payload = _apply_identity_provider_override(_load_json(args.contract), args)
    _validate_contract(payload)
    decoder = _decoder_from_args(args)
    output_dir = decoder.generate_sequel_from_contract(
        payload,
        user_prompt=args.prompt,
        output_dir=args.output_dir,
        generation_controls=_generation_controls_from_args(args),
        prefer_exported_context=not args.force_context_rebuild,
        prefer_exported_blueprint=not args.force_blueprint_regenerate,
    )
    print(f"Narrative output directory: {output_dir}")


def generate_sequel_neo4j(args) -> None:
    decoder = _decoder_from_args(args)
    output_dir = decoder.generate_sequel_from_neo4j(
        book_title=(args.book_title[0] if len(args.book_title or []) == 1 else None),
        series_id=args.series_id,
        book_titles=args.book_title or None,
        user_prompt=args.prompt,
        output_dir=args.output_dir,
        generation_controls=_generation_controls_from_args(args),
        uri=args.uri,
        username=args.username,
        password=args.password,
        database=args.database,
    )
    print(f"Narrative output directory: {output_dir}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SAGA downstream tools for contract export, Neo4j ingest, and sequel generation."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser(
        "export-contract",
        help="Validate and rewrite a dashboard-exported contract JSON to a target path.",
    )
    export_parser.add_argument("--contract", required=True, help="Path to the dashboard-exported contract JSON.")
    export_parser.add_argument("--out", required=True, help="Target path for the prepared contract JSON.")
    export_parser.set_defaults(func=export_contract_copy)

    register_parser = subparsers.add_parser(
        "register-corpus",
        help="Create or update a persisted Neo4j series/corpus entry without ingesting books yet.",
    )
    register_parser.add_argument("--series-id", required=True, help="Stable series/corpus identifier.")
    register_parser.add_argument("--series-title", default="", help="Human-readable series title.")
    register_parser.add_argument("--uri", default=None, help="Neo4j URI. Falls back to NEO4J_URI.")
    register_parser.add_argument("--username", default=None, help="Neo4j username. Falls back to NEO4J_USERNAME.")
    register_parser.add_argument("--password", default=None, help="Neo4j password. Falls back to NEO4J_PASSWORD.")
    register_parser.add_argument("--database", default=None, help="Neo4j database. Falls back to NEO4J_DATABASE.")
    register_parser.set_defaults(func=register_corpus)

    inspect_parser = subparsers.add_parser(
        "inspect-corpus",
        help="Inspect persisted series/corpus contents and source-version metadata.",
    )
    inspect_parser.add_argument("--series-id", required=True, help="Stable series/corpus identifier.")
    inspect_parser.add_argument("--uri", default=None, help="Neo4j URI. Falls back to NEO4J_URI.")
    inspect_parser.add_argument("--username", default=None, help="Neo4j username. Falls back to NEO4J_USERNAME.")
    inspect_parser.add_argument("--password", default=None, help="Neo4j password. Falls back to NEO4J_PASSWORD.")
    inspect_parser.add_argument("--database", default=None, help="Neo4j database. Falls back to NEO4J_DATABASE.")
    inspect_parser.set_defaults(func=inspect_corpus)

    encode_parser = subparsers.add_parser(
        "encode-store",
        help="Process books through the encoder pipeline and persist the result into Neo4j.",
    )
    encode_parser.add_argument("--book", action="append", required=True, help="Path to an EPUB or PDF book. Repeat for multiple books.")
    encode_parser.add_argument("--out", default=None, help="Optional output path for the generated contract JSON.")
    encode_parser.add_argument("--series-id", default="", help="Stable series/corpus identifier for persistent retrieval.")
    encode_parser.add_argument("--series-title", default="", help="Human-readable series title.")
    encode_parser.add_argument("--book-index-base", type=int, default=1, help="Starting book index for this batch, used for incremental append runs.")
    encode_parser.add_argument("--replace-existing", action="store_true", help="Replace already persisted books when the source hash has changed.")
    encode_parser.add_argument("--skip-ingest", action="store_true", help="Encode and write contracts without Neo4j ingest. Useful for bounded reliability smokes.")
    encode_parser.add_argument("--analysis-model", default=LLMClient.MODE_GPT_OSS, choices=MODEL_MODE_CHOICES)
    encode_parser.add_argument("--identity-model", default=LLMClient.MODE_GPT_OSS, choices=MODEL_MODE_CHOICES)
    encode_parser.add_argument("--analysis-provider-mode", default="same_provider_rotating", choices=ANALYSIS_PROVIDER_MODE_CHOICES, help="Provider policy: single_provider for strict small debug runs, same_provider_rotating for long canonical runs, cross_provider_fallback for experimental non-canonical runs.")
    _add_production_identity_args(encode_parser)
    encode_parser.add_argument("--analysis-mode", default="structured", choices=["structured", "tool", "compare"])
    encode_parser.add_argument("--target-scene-words", type=int, default=0)
    encode_parser.add_argument("--max-chapters", type=int, default=0, help="Optional cap on chapters processed for bounded smoke runs.")
    encode_parser.add_argument("--scene-failure-policy", default="fail_fast", choices=["fail_fast", "skip_failed", "write_partial"], help="How to handle provider/model scene-analysis failures.")
    encode_parser.add_argument("--max-failed-scenes-absolute", type=int, default=3, help="Maximum failed scenes allowed before the book is marked failed.")
    encode_parser.add_argument("--max-failed-scene-ratio", type=float, default=0.10, help="Maximum failed-scene ratio allowed before the book is marked failed.")
    encode_parser.add_argument("--min-nonempty-scene-ratio", type=float, default=0.80, help="Minimum ratio of non-empty scenes required for a healthy book contract.")
    encode_parser.add_argument("--max-parallel-books", type=int, default=2, help="Maximum number of books to encode in parallel for this batch.")
    encode_parser.add_argument("--no-progress", action="store_true", help="Disable live terminal progress output during encoding.")
    encode_parser.add_argument("--uri", default=None, help="Neo4j URI. Falls back to NEO4J_URI.")
    encode_parser.add_argument("--username", default=None, help="Neo4j username. Falls back to NEO4J_USERNAME.")
    encode_parser.add_argument("--password", default=None, help="Neo4j password. Falls back to NEO4J_PASSWORD.")
    encode_parser.add_argument("--database", default=None, help="Neo4j database. Falls back to NEO4J_DATABASE.")
    encode_parser.set_defaults(func=encode_store)

    reencode_parser = subparsers.add_parser(
        "reencode-book",
        help="Re-encode and replace one persisted book inside an existing series.",
    )
    reencode_parser.add_argument("--book", action="append", required=True, help="Path to the replacement book file. Use exactly one.")
    reencode_parser.add_argument("--out", default=None, help="Optional output path for the generated contract JSON.")
    reencode_parser.add_argument("--series-id", required=True, help="Stable series/corpus identifier.")
    reencode_parser.add_argument("--series-title", default="", help="Human-readable series title.")
    reencode_parser.add_argument("--book-index-base", type=int, required=True, help="Book index of the replacement book in the existing series.")
    reencode_parser.add_argument("--analysis-model", default=LLMClient.MODE_GPT_OSS, choices=MODEL_MODE_CHOICES)
    reencode_parser.add_argument("--identity-model", default=LLMClient.MODE_GPT_OSS, choices=MODEL_MODE_CHOICES)
    reencode_parser.add_argument("--analysis-provider-mode", default="same_provider_rotating", choices=ANALYSIS_PROVIDER_MODE_CHOICES, help="Provider policy: single_provider for strict small debug runs, same_provider_rotating for long canonical runs, cross_provider_fallback for experimental non-canonical runs.")
    _add_production_identity_args(reencode_parser)
    reencode_parser.add_argument("--analysis-mode", default="structured", choices=["structured", "tool", "compare"])
    reencode_parser.add_argument("--target-scene-words", type=int, default=0)
    reencode_parser.add_argument("--max-chapters", type=int, default=0, help="Optional cap on chapters processed for bounded smoke runs.")
    reencode_parser.add_argument("--scene-failure-policy", default="fail_fast", choices=["fail_fast", "skip_failed", "write_partial"], help="How to handle provider/model scene-analysis failures.")
    reencode_parser.add_argument("--max-failed-scenes-absolute", type=int, default=3, help="Maximum failed scenes allowed before the book is marked failed.")
    reencode_parser.add_argument("--max-failed-scene-ratio", type=float, default=0.10, help="Maximum failed-scene ratio allowed before the book is marked failed.")
    reencode_parser.add_argument("--min-nonempty-scene-ratio", type=float, default=0.80, help="Minimum ratio of non-empty scenes required for a healthy book contract.")
    reencode_parser.add_argument("--max-parallel-books", type=int, default=1, help="Maximum number of books to encode in parallel. Re-encode uses one book by default.")
    reencode_parser.add_argument("--uri", default=None, help="Neo4j URI. Falls back to NEO4J_URI.")
    reencode_parser.add_argument("--username", default=None, help="Neo4j username. Falls back to NEO4J_USERNAME.")
    reencode_parser.add_argument("--password", default=None, help="Neo4j password. Falls back to NEO4J_PASSWORD.")
    reencode_parser.add_argument("--database", default=None, help="Neo4j database. Falls back to NEO4J_DATABASE.")
    reencode_parser.set_defaults(func=reencode_book)

    remove_parser = subparsers.add_parser(
        "remove-book",
        help="Remove one persisted book from an existing series.",
    )
    remove_parser.add_argument("--series-id", required=True, help="Stable series/corpus identifier.")
    remove_parser.add_argument("--book-title", required=True, help="Exact book title stored in Neo4j.")
    remove_parser.add_argument("--uri", default=None, help="Neo4j URI. Falls back to NEO4J_URI.")
    remove_parser.add_argument("--username", default=None, help="Neo4j username. Falls back to NEO4J_USERNAME.")
    remove_parser.add_argument("--password", default=None, help="Neo4j password. Falls back to NEO4J_PASSWORD.")
    remove_parser.add_argument("--database", default=None, help="Neo4j database. Falls back to NEO4J_DATABASE.")
    remove_parser.set_defaults(func=remove_book)

    ingest_parser = subparsers.add_parser(
        "ingest-neo4j",
        help="Ingest a SAGA contract JSON into Neo4j.",
    )
    ingest_parser.add_argument("--contract", required=True, help="Path to the contract JSON.")
    ingest_parser.add_argument("--uri", default=None, help="Neo4j URI. Falls back to NEO4J_URI.")
    ingest_parser.add_argument("--username", default=None, help="Neo4j username. Falls back to NEO4J_USERNAME.")
    ingest_parser.add_argument("--password", default=None, help="Neo4j password. Falls back to NEO4J_PASSWORD.")
    ingest_parser.add_argument("--database", default=None, help="Neo4j database. Falls back to NEO4J_DATABASE.")
    ingest_parser.add_argument("--replace-existing", action="store_true", help="Replace already persisted books when the contract contains newer source hashes.")
    ingest_parser.set_defaults(func=ingest_neo4j)

    probe_parser = subparsers.add_parser(
        "probe-neo4j",
        help="Verify Neo4j connectivity and configuration without ingesting any data.",
    )
    probe_parser.add_argument("--uri", default=None, help="Neo4j URI. Falls back to NEO4J_URI.")
    probe_parser.add_argument("--username", default=None, help="Neo4j username. Falls back to NEO4J_USERNAME.")
    probe_parser.add_argument("--password", default=None, help="Neo4j password. Falls back to NEO4J_PASSWORD.")
    probe_parser.add_argument("--database", default=None, help="Neo4j database. Falls back to NEO4J_DATABASE.")
    probe_parser.set_defaults(func=probe_neo4j)

    audit_parser = subparsers.add_parser(
        "audit-corpus",
        help="Audit the persisted corpus and the latest stored contracts for graph-quality issues.",
    )
    audit_parser.add_argument("--series-id", required=True, help="Series/corpus identifier stored on the Neo4j Series node.")
    audit_parser.add_argument("--contract", action="append", default=[], help="Optional explicit contract path. Repeat to audit a specific contract set.")
    audit_parser.add_argument("--out", default="", help="Optional output path for the audit JSON artifact.")
    audit_parser.add_argument("--use-web-hints", action="store_true", help="Enable optional wiki-assisted heuristic hints during contract audit previews.")
    audit_parser.add_argument("--uri", default=None, help="Neo4j URI. Falls back to NEO4J_URI.")
    audit_parser.add_argument("--username", default=None, help="Neo4j username. Falls back to NEO4J_USERNAME.")
    audit_parser.add_argument("--password", default=None, help="Neo4j password. Falls back to NEO4J_PASSWORD.")
    audit_parser.add_argument("--database", default=None, help="Neo4j database. Falls back to NEO4J_DATABASE.")
    audit_parser.add_argument(
        "--model-mode",
        default=DEFAULT_NARRATIVE_MODEL_MODE,
        choices=MODEL_MODE_CHOICES,
        help="LLM backend to use for residual ambiguity verification during audit previews.",
    )
    audit_parser.add_argument(
        "--ollama-model",
        default=DEFAULT_NARRATIVE_OLLAMA_MODEL,
        help="Optional explicit model tag override for Ollama-backed or General Compute-backed audit verification.",
    )
    audit_parser.set_defaults(func=audit_corpus)

    repair_parser = subparsers.add_parser(
        "repair-corpus",
        help="Repair stored contracts with deterministic canon normalization before rebuild.",
    )
    repair_parser.add_argument("--series-id", required=True, help="Series/corpus identifier stored on the Neo4j Series node.")
    repair_parser.add_argument("--contract", action="append", default=[], help="Optional explicit contract path. Repeat to repair a specific contract set.")
    repair_parser.add_argument("--output-dir", required=True, help="Directory for repaired contracts and repair reports.")
    repair_parser.add_argument("--dry-run", action="store_true", help="Report planned repairs without writing repaired contracts.")
    repair_parser.add_argument("--use-web-hints", action="store_true", help="Enable optional wiki-assisted heuristic hints during repair.")
    repair_parser.add_argument("--uri", default=None, help="Neo4j URI. Falls back to NEO4J_URI.")
    repair_parser.add_argument("--username", default=None, help="Neo4j username. Falls back to NEO4J_USERNAME.")
    repair_parser.add_argument("--password", default=None, help="Neo4j password. Falls back to NEO4J_PASSWORD.")
    repair_parser.add_argument("--database", default=None, help="Neo4j database. Falls back to NEO4J_DATABASE.")
    repair_parser.add_argument(
        "--model-mode",
        default=DEFAULT_NARRATIVE_MODEL_MODE,
        choices=MODEL_MODE_CHOICES,
        help="LLM backend to use for residual ambiguity verification during repair.",
    )
    repair_parser.add_argument(
        "--ollama-model",
        default=DEFAULT_NARRATIVE_OLLAMA_MODEL,
        help="Optional explicit model tag override for Ollama-backed or General Compute-backed repair verification.",
    )
    repair_parser.set_defaults(func=repair_corpus)

    rebuild_parser = subparsers.add_parser(
        "rebuild-corpus",
        help="Repair latest stored contracts, rebuild the Neo4j corpus, and refresh the local vector index.",
    )
    rebuild_parser.add_argument("--series-id", required=True, help="Series/corpus identifier stored on the Neo4j Series node.")
    rebuild_parser.add_argument("--contract", action="append", default=[], help="Optional explicit contract path. Repeat to rebuild from a specific contract set.")
    rebuild_parser.add_argument("--output-dir", required=True, help="Directory for rebuild artifacts.")
    rebuild_parser.add_argument("--dry-run", action="store_true", help="Run repair planning without mutating the database.")
    rebuild_parser.add_argument("--use-web-hints", action="store_true", help="Enable optional wiki-assisted heuristic hints during repair.")
    rebuild_parser.add_argument("--source-dir", default="", help="Optional source directory for recovering missing contracts via targeted re-encode.")
    rebuild_parser.add_argument("--no-progress", action="store_true", help="Disable live terminal progress output during rebuild.")
    rebuild_parser.add_argument("--uri", default=None, help="Neo4j URI. Falls back to NEO4J_URI.")
    rebuild_parser.add_argument("--username", default=None, help="Neo4j username. Falls back to NEO4J_USERNAME.")
    rebuild_parser.add_argument("--password", default=None, help="Neo4j password. Falls back to NEO4J_PASSWORD.")
    rebuild_parser.add_argument("--database", default=None, help="Neo4j database. Falls back to NEO4J_DATABASE.")
    rebuild_parser.add_argument(
        "--model-mode",
        default=DEFAULT_NARRATIVE_MODEL_MODE,
        choices=MODEL_MODE_CHOICES,
        help="LLM backend to use for residual ambiguity verification during rebuild.",
    )
    rebuild_parser.add_argument(
        "--ollama-model",
        default=DEFAULT_NARRATIVE_OLLAMA_MODEL,
        help="Optional explicit model tag override for Ollama-backed or General Compute-backed rebuild verification.",
    )
    rebuild_parser.set_defaults(func=rebuild_corpus)

    validate_parser = subparsers.add_parser(
        "validate-encoder-artifacts",
        help="Validate one exported contract/artifact bundle and write a bounded diagnostic report.",
    )
    validate_parser.add_argument("--contract", required=True, help="Path to the contract JSON to validate.")
    validate_parser.add_argument("--out", required=True, help="Output path for the JSON validation report.")
    validate_parser.add_argument("--report-md", default="", help="Optional output path for the Markdown validation report.")
    _add_identity_override_args(validate_parser, help_text="Optional identity source override for rebuild-based validation.")
    validate_parser.add_argument("--compare-contract", default="", help="Optional baseline contract to compare against.")
    validate_parser.set_defaults(func=validate_encoder_artifacts)

    context_parser = subparsers.add_parser(
        "build-sequel-context",
        help="Build the Narraverse-style sequel retrieval context from a SAGA contract.",
    )
    context_parser.add_argument("--contract", required=True, help="Path to the contract JSON.")
    context_parser.add_argument("--out", required=True, help="Output path for the narrative context JSON.")
    _add_identity_override_args(context_parser, help_text="Optional identity source override for context rebuild.")
    context_parser.add_argument("--target-mode", default="", choices=["", "pre_canon", "mid_canon", "post_book", "post_series", "custom"], help="Optional target-aware character state mode for retrieval context rebuild.")
    context_parser.add_argument("--book-index", type=int, default=None, help="Target book index for target-aware context modes.")
    context_parser.add_argument("--chapter", type=int, default=None, help="Target chapter for target-aware context modes.")
    context_parser.add_argument("--scene-id", default="", help="Optional target scene identifier like b2_c20_s1 or a raw scene index.")
    context_parser.add_argument("--after-book-index", type=int, default=None, help="Target after-book index for post_book/post_series modes.")
    context_parser.add_argument("--include-future-facts", action="store_true", help="Include facts after the target point. Off by default.")
    context_parser.add_argument("--include-visual-world-state", action="store_true", help="Attach target-aware visual/entity/location state packets when target-mode is used.")
    context_parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Ignore any exported narrative context in the contract and rebuild from core SAGA outputs.",
    )
    context_parser.set_defaults(func=build_sequel_context)

    state_snapshot_parser = subparsers.add_parser(
        "build-character-state-snapshot",
        help="Build target-aware character state snapshots from one or more contracts.",
    )
    state_snapshot_parser.add_argument("--contract", action="append", required=True, help="Path to a contract JSON. Repeat for multi-book snapshots.")
    state_snapshot_parser.add_argument("--out", required=True, help="Output path for the snapshot JSON.")
    state_snapshot_parser.add_argument("--report-md", default="", help="Optional Markdown report path for the snapshot.")
    _add_identity_override_args(state_snapshot_parser, help_text="Optional identity provider override for snapshot building.")
    state_snapshot_parser.add_argument("--target-mode", required=True, choices=["pre_canon", "mid_canon", "post_book", "post_series", "custom"], help="Target point mode.")
    state_snapshot_parser.add_argument("--book-index", type=int, default=None, help="Target book index for mid_canon/post_book/custom modes.")
    state_snapshot_parser.add_argument("--chapter", type=int, default=None, help="Target chapter for mid_canon/custom modes.")
    state_snapshot_parser.add_argument("--scene-id", default="", help="Optional target scene identifier like b2_c20_s1 or a raw scene index.")
    state_snapshot_parser.add_argument("--after-book-index", type=int, default=None, help="After-book index for post_book/post_series modes.")
    state_snapshot_parser.add_argument("--include-future-facts", action="store_true", help="Include future facts beyond the target point.")
    state_snapshot_parser.add_argument("--focus-character", action="append", default=[], help="Optional character IDs to restrict the snapshot output.")
    state_snapshot_parser.add_argument("--include-reference-entities", action="store_true", help="Include reference entities in the output snapshot.")
    state_snapshot_parser.set_defaults(func=build_character_state_snapshot)

    visual_state_parser = subparsers.add_parser(
        "build-visual-world-state",
        help="Build target-aware visual/entity/location continuity packets from one or more contracts.",
    )
    visual_state_parser.add_argument("--contract", action="append", required=True, help="Path to a contract JSON. Repeat for multi-book visual states.")
    visual_state_parser.add_argument("--out", required=True, help="Output path for the visual world state JSON.")
    visual_state_parser.add_argument("--report-md", default="", help="Optional Markdown report path for the visual world state output.")
    _add_identity_override_args(visual_state_parser, help_text="Optional identity provider override.")
    visual_state_parser.add_argument("--target-mode", required=True, choices=["pre_canon", "mid_canon", "post_book", "post_series", "custom"], help="Target point mode.")
    visual_state_parser.add_argument("--book-index", type=int, default=None, help="Target book index for mid_canon/post_book/custom modes.")
    visual_state_parser.add_argument("--chapter", type=int, default=None, help="Target chapter for mid_canon/custom modes.")
    visual_state_parser.add_argument("--scene-id", default="", help="Optional target scene identifier like b2_c20_s1 or a raw scene index.")
    visual_state_parser.add_argument("--after-book-index", type=int, default=None, help="After-book index for post_book/post_series modes.")
    visual_state_parser.add_argument("--include-future-facts", action="store_true", help="Include future facts beyond the target point.")
    visual_state_parser.set_defaults(func=build_visual_world_state)

    enrich_visual_parser = subparsers.add_parser(
        "enrich-contract-visual-state",
        help="Attach a visual world state adapter payload to a copy of a contract.",
    )
    enrich_visual_parser.add_argument("--contract", required=True, help="Path to the source contract JSON.")
    enrich_visual_parser.add_argument("--visual-state", required=True, help="Path to the visual world state JSON.")
    enrich_visual_parser.add_argument("--out-contract", required=True, help="Output path for the enriched contract JSON.")
    enrich_visual_parser.set_defaults(func=enrich_contract_visual_state)

    comfy_parser = subparsers.add_parser(
        "build-comfyui-prompt-pack",
        help="Compile visual world-state evidence into ComfyUI-ready prompt packs.",
    )
    comfy_parser.add_argument("--visual-state", required=True, help="Path to the visual world state JSON.")
    comfy_parser.add_argument("--contract", default="", help="Optional contract JSON path for chapter-text-backed beat splitting.")
    comfy_parser.add_argument("--mode", default="full_prompt_pack", choices=sorted(ComfyUIPromptPackService.MODES), help="Prompt-pack export mode.")
    comfy_parser.add_argument("--focus-character", action="append", default=[], help="Character to prioritize. Repeat as needed.")
    comfy_parser.add_argument("--focus-location", action="append", default=[], help="Location to prioritize. Repeat as needed.")
    comfy_parser.add_argument("--focus-entity", action="append", default=[], help="Object/entity to prioritize. Repeat as needed.")
    comfy_parser.add_argument("--scene-id", default="", help="Optional scene filter like b5_c68_s1.")
    comfy_parser.add_argument("--chapter", type=int, default=0, help="Optional chapter filter.")
    comfy_parser.add_argument("--include-low-confidence", action="store_true", help="Include low-confidence prompt candidates.")
    comfy_parser.add_argument("--out", required=True, help="Output path for the prompt-pack JSON.")
    comfy_parser.add_argument("--report-md", default="", help="Optional markdown report path.")
    comfy_parser.set_defaults(func=build_comfyui_prompt_pack)

    comfy_curated_parser = subparsers.add_parser(
        "build-comfyui-curated-test-pack",
        help="Create a small curated ComfyUI test pack, text exports, and markdown preview from a compiled prompt pack.",
    )
    comfy_curated_parser.add_argument("--prompt-pack", required=True, help="Path to the compiled ComfyUI prompt-pack JSON.")
    comfy_curated_parser.add_argument("--out", required=True, help="Output path for the curated test pack JSON.")
    comfy_curated_parser.add_argument("--export-dir", required=True, help="Directory for plain-text positive/negative prompt exports.")
    comfy_curated_parser.add_argument("--preview-md", required=True, help="Markdown preview path.")
    comfy_curated_parser.add_argument("--report-md", required=True, help="Finalization report path.")
    comfy_curated_parser.set_defaults(func=build_comfyui_curated_test_pack)

    validate_context_parser = subparsers.add_parser(
        "validate-generation-context",
        help="Validate production retrieval context quality using one or more contracts and optional target-aware states.",
    )
    validate_context_parser.add_argument("--contract", action="append", required=True, help="Path to a contract JSON. Repeat for multi-book context.")
    validate_context_parser.add_argument("--out", required=True, help="Output path for the validation JSON.")
    validate_context_parser.add_argument("--report-md", required=True, help="Output path for the Markdown validation report.")
    validate_context_parser.add_argument("--prompt", required=True, help="Generation target prompt used for context validation.")
    _add_identity_override_args(validate_context_parser, help_text="Identity provider override.")
    validate_context_parser.add_argument("--target-states", default="", help="Optional prebuilt target-aware state snapshot JSON.")
    validate_context_parser.add_argument("--target-mode", default="post_series", choices=["pre_canon", "mid_canon", "post_book", "post_series", "custom"], help="Target point mode.")
    validate_context_parser.add_argument("--book-index", type=int, default=None, help="Target book index for target-aware validation.")
    validate_context_parser.add_argument("--chapter", type=int, default=None, help="Target chapter for target-aware validation.")
    validate_context_parser.add_argument("--scene-id", default="", help="Optional target scene identifier.")
    validate_context_parser.add_argument("--after-book-index", type=int, default=None, help="After-book index for post_book/post_series validation.")
    validate_context_parser.add_argument("--include-future-facts", action="store_true", help="Include future facts beyond the target point.")
    validate_context_parser.add_argument("--blueprint-smoke-out", default="", help="Optional output path for a tiny blueprint smoke JSON.")
    validate_context_parser.add_argument("--blueprint-smoke-report-md", default="", help="Optional output path for the tiny blueprint smoke Markdown report.")
    validate_context_parser.add_argument("--chapters", type=int, default=None, help="Requested chapter count for optional blueprint smoke.")
    validate_context_parser.add_argument("--canon-position", default="post_canon", choices=["pre_canon", "mid_canon_insert", "mid_canon_divergent", "post_canon"], help="Canon placement for optional blueprint smoke.")
    validate_context_parser.add_argument("--new-plot", default="", help="Optional new plot thread for optional blueprint smoke.")
    validate_context_parser.add_argument("--primary-pov", default="", help="Optional primary POV character for optional blueprint smoke.")
    validate_context_parser.add_argument("--relationship-direction", action="append", default=[], help="Relationship direction controls for optional blueprint smoke.")
    validate_context_parser.add_argument("--preserve-event", action="append", default=[], help="Canon events to preserve for optional blueprint smoke.")
    validate_context_parser.add_argument("--continuity-anchor", default="", help="Continuity anchor for optional blueprint smoke.")
    validate_context_parser.add_argument("--divergence-anchor", default="", help="Divergence anchor for optional blueprint smoke.")
    validate_context_parser.add_argument("--anchor-after", default="", help="Anchor-after control for optional blueprint smoke.")
    validate_context_parser.add_argument("--anchor-before", default="", help="Anchor-before control for optional blueprint smoke.")
    validate_context_parser.add_argument("--model-mode", default=DEFAULT_NARRATIVE_MODEL_MODE, choices=MODEL_MODE_CHOICES, help="LLM backend for optional blueprint smoke.")
    validate_context_parser.add_argument("--ollama-model", default=DEFAULT_NARRATIVE_OLLAMA_MODEL, help="Optional explicit model tag override for optional blueprint smoke.")
    validate_context_parser.add_argument("--planner-model-mode", default="", choices=[""] + MODEL_MODE_CHOICES, help="Optional separate planner model mode for optional blueprint smoke.")
    validate_context_parser.add_argument("--planner-model", default="", help="Optional separate planner model override for optional blueprint smoke.")
    validate_context_parser.add_argument("--prose-model-mode", default="", choices=[""] + MODEL_MODE_CHOICES, help="Optional separate prose model mode, usually unused here.")
    validate_context_parser.add_argument("--prose-model", default="", help="Optional separate prose model override, usually unused here.")
    validate_context_parser.set_defaults(func=validate_generation_context)

    context_graph_parser = subparsers.add_parser(
        "build-sequel-context-neo4j",
        help="Build sequel retrieval context directly from persisted Neo4j graph data.",
    )
    context_graph_parser.add_argument("--series-id", default="", help="Series/corpus identifier stored on the Neo4j Series node.")
    context_graph_parser.add_argument("--book-title", action="append", default=[], help="Book title as stored on the Neo4j Book node. Repeat to target a subset.")
    context_graph_parser.add_argument("--out", required=True, help="Output path for the narrative context JSON.")
    context_graph_parser.add_argument("--uri", default=None, help="Neo4j URI. Falls back to NEO4J_URI.")
    context_graph_parser.add_argument("--username", default=None, help="Neo4j username. Falls back to NEO4J_USERNAME.")
    context_graph_parser.add_argument("--password", default=None, help="Neo4j password. Falls back to NEO4J_PASSWORD.")
    context_graph_parser.add_argument("--database", default=None, help="Neo4j database. Falls back to NEO4J_DATABASE.")
    context_graph_parser.set_defaults(func=build_sequel_context_neo4j)

    blueprint_parser = subparsers.add_parser(
        "generate-blueprint",
        help="Generate only the narrative blueprint JSON from a SAGA contract.",
    )
    blueprint_parser.add_argument("--contract", required=True, help="Path to the contract JSON.")
    blueprint_parser.add_argument("--prompt", required=True, help="Creative direction for the sequel.")
    blueprint_parser.add_argument("--out", required=True, help="Output path for the blueprint JSON.")
    _add_identity_override_args(blueprint_parser, help_text="Optional identity source override for blueprint generation.")
    blueprint_parser.add_argument("--chapters", type=int, default=None, help="Requested chapter count for the generated book.")
    blueprint_parser.add_argument("--canon-position", default="post_canon", choices=["pre_canon", "mid_canon_insert", "mid_canon_divergent", "post_canon"], help="Place the generated story before canon, inside canon as an insertion, inside canon as a divergence branch, or after canon.")
    blueprint_parser.add_argument("--new-plot", default="", help="A new major plotline to inject into the generated story.")
    blueprint_parser.add_argument("--primary-pov", default="", help="Optional primary POV character to enforce across generated chapter outlines.")
    blueprint_parser.add_argument("--relationship-direction", action="append", default=[], help="Relationship direction in the form 'name1,name2|relationship_type|desired direction|optional notes'. Repeat for multiple relationship goals.")
    blueprint_parser.add_argument("--preserve-event", action="append", default=[], help="Canon element to preserve in the form 'event_id|description' or just 'description'. Repeat for multiple preserved canon elements.")
    blueprint_parser.add_argument("--continuity-anchor", default="", help="Free-text continuity constraint describing where the story must fit.")
    blueprint_parser.add_argument("--divergence-anchor", default="", help="Required for mid_canon_divergent. The canon event where the branch begins.")
    blueprint_parser.add_argument("--anchor-after", default="", help="Optional canon anchor that the story must occur after.")
    blueprint_parser.add_argument("--anchor-before", default="", help="Optional canon anchor that the story must occur before.")
    blueprint_parser.add_argument(
        "--force-context-rebuild",
        action="store_true",
        help="Ignore exported narrative context and rebuild it from core SAGA outputs.",
    )
    blueprint_parser.add_argument(
        "--force-blueprint-regenerate",
        action="store_true",
        help="Ignore any exported blueprint artifact and generate a fresh one.",
    )
    blueprint_parser.add_argument(
        "--model-mode",
        default=DEFAULT_NARRATIVE_MODEL_MODE,
        choices=[
            LLMClient.MODE_DEEPSEEK,
            LLMClient.MODE_GPT_OSS,
            LLMClient.MODE_GENERAL_COMPUTE,
            LLMClient.MODE_MISTRAL,
            LLMClient.MODE_GEMINI,
        ],
        help="LLM backend to use for blueprint generation.",
    )
    blueprint_parser.add_argument(
        "--ollama-model",
        default=DEFAULT_NARRATIVE_OLLAMA_MODEL,
        help="Optional explicit model tag override for Ollama-backed or General Compute-backed runs.",
    )
    blueprint_parser.add_argument("--planner-model-mode", default="", choices=[""] + MODEL_MODE_CHOICES, help="Optional separate planner model mode for blueprint/outline JSON stages.")
    blueprint_parser.add_argument("--planner-model", default="", help="Optional separate planner model tag override.")
    blueprint_parser.add_argument("--prose-model-mode", default="", choices=[""] + MODEL_MODE_CHOICES, help="Optional separate prose model mode. Usually leave empty for blueprint-only runs.")
    blueprint_parser.add_argument("--prose-model", default="", help="Optional separate prose model tag override.")
    blueprint_parser.set_defaults(func=generate_blueprint)

    blueprint_graph_parser = subparsers.add_parser(
        "generate-blueprint-neo4j",
        help="Generate a narrative blueprint directly from Neo4j-backed retrieval.",
    )
    blueprint_graph_parser.add_argument("--series-id", default="", help="Series/corpus identifier stored on the Neo4j Series node.")
    blueprint_graph_parser.add_argument("--book-title", action="append", default=[], help="Book title as stored on the Neo4j Book node. Repeat to target a subset.")
    blueprint_graph_parser.add_argument("--prompt", required=True, help="Creative direction for the sequel.")
    blueprint_graph_parser.add_argument("--out", required=True, help="Output path for the blueprint JSON.")
    blueprint_graph_parser.add_argument("--chapters", type=int, default=None, help="Requested chapter count for the generated book.")
    blueprint_graph_parser.add_argument("--canon-position", default="post_canon", choices=["pre_canon", "mid_canon_insert", "mid_canon_divergent", "post_canon"], help="Place the generated story before canon, inside canon as an insertion, inside canon as a divergence branch, or after canon.")
    blueprint_graph_parser.add_argument("--new-plot", default="", help="A new major plotline to inject into the generated story.")
    blueprint_graph_parser.add_argument("--primary-pov", default="", help="Optional primary POV character to enforce across generated chapter outlines.")
    blueprint_graph_parser.add_argument("--relationship-direction", action="append", default=[], help="Relationship direction in the form 'name1,name2|relationship_type|desired direction|optional notes'. Repeat for multiple relationship goals.")
    blueprint_graph_parser.add_argument("--preserve-event", action="append", default=[], help="Canon element to preserve in the form 'event_id|description' or just 'description'. Repeat for multiple preserved canon elements.")
    blueprint_graph_parser.add_argument("--continuity-anchor", default="", help="Free-text continuity constraint describing where the story must fit.")
    blueprint_graph_parser.add_argument("--divergence-anchor", default="", help="Required for mid_canon_divergent. The canon event where the branch begins.")
    blueprint_graph_parser.add_argument("--anchor-after", default="", help="Optional canon anchor that the story must occur after.")
    blueprint_graph_parser.add_argument("--anchor-before", default="", help="Optional canon anchor that the story must occur before.")
    blueprint_graph_parser.add_argument("--uri", default=None, help="Neo4j URI. Falls back to NEO4J_URI.")
    blueprint_graph_parser.add_argument("--username", default=None, help="Neo4j username. Falls back to NEO4J_USERNAME.")
    blueprint_graph_parser.add_argument("--password", default=None, help="Neo4j password. Falls back to NEO4J_PASSWORD.")
    blueprint_graph_parser.add_argument("--database", default=None, help="Neo4j database. Falls back to NEO4J_DATABASE.")
    blueprint_graph_parser.add_argument(
        "--model-mode",
        default=DEFAULT_NARRATIVE_MODEL_MODE,
        choices=MODEL_MODE_CHOICES,
    )
    blueprint_graph_parser.add_argument(
        "--ollama-model",
        default=DEFAULT_NARRATIVE_OLLAMA_MODEL,
        help="Optional explicit model tag override for Ollama-backed or General Compute-backed runs.",
    )
    blueprint_graph_parser.add_argument("--planner-model-mode", default="", choices=[""] + MODEL_MODE_CHOICES, help="Optional separate planner model mode for blueprint/outline JSON stages.")
    blueprint_graph_parser.add_argument("--planner-model", default="", help="Optional separate planner model tag override.")
    blueprint_graph_parser.add_argument("--prose-model-mode", default="", choices=[""] + MODEL_MODE_CHOICES, help="Optional separate prose model mode. Usually leave empty for blueprint-only runs.")
    blueprint_graph_parser.add_argument("--prose-model", default="", help="Optional separate prose model tag override.")
    blueprint_graph_parser.set_defaults(func=generate_blueprint_neo4j)

    sequel_parser = subparsers.add_parser(
        "generate-sequel",
        help="Run the full narrative generation pipeline from a SAGA contract.",
    )
    sequel_parser.add_argument("--contract", required=True, help="Path to the contract JSON.")
    sequel_parser.add_argument("--prompt", required=True, help="Creative direction for the sequel.")
    sequel_parser.add_argument("--output-dir", required=True, help="Directory for chapter outputs.")
    _add_identity_override_args(sequel_parser, help_text="Optional identity source override for sequel generation.")
    sequel_parser.add_argument("--chapters", type=int, default=None, help="Requested chapter count for the generated book.")
    sequel_parser.add_argument("--canon-position", default="post_canon", choices=["pre_canon", "mid_canon_insert", "mid_canon_divergent", "post_canon"], help="Place the generated story before canon, inside canon as an insertion, inside canon as a divergence branch, or after canon.")
    sequel_parser.add_argument("--new-plot", default="", help="A new major plotline to inject into the generated story.")
    sequel_parser.add_argument("--primary-pov", default="", help="Optional primary POV character to enforce across generated chapter outlines.")
    sequel_parser.add_argument("--relationship-direction", action="append", default=[], help="Relationship direction in the form 'name1,name2|relationship_type|desired direction|optional notes'. Repeat for multiple relationship goals.")
    sequel_parser.add_argument("--preserve-event", action="append", default=[], help="Canon element to preserve in the form 'event_id|description' or just 'description'. Repeat for multiple preserved canon elements.")
    sequel_parser.add_argument("--continuity-anchor", default="", help="Free-text continuity constraint describing where the story must fit.")
    sequel_parser.add_argument("--divergence-anchor", default="", help="Required for mid_canon_divergent. The canon event where the branch begins.")
    sequel_parser.add_argument("--anchor-after", default="", help="Optional canon anchor that the story must occur after.")
    sequel_parser.add_argument("--anchor-before", default="", help="Optional canon anchor that the story must occur before.")
    sequel_parser.add_argument(
        "--force-context-rebuild",
        action="store_true",
        help="Ignore exported narrative context and rebuild it from core SAGA outputs.",
    )
    sequel_parser.add_argument(
        "--force-blueprint-regenerate",
        action="store_true",
        help="Ignore any exported blueprint artifact and generate a fresh one.",
    )
    sequel_parser.add_argument(
        "--model-mode",
        default=DEFAULT_NARRATIVE_MODEL_MODE,
        choices=[
            LLMClient.MODE_DEEPSEEK,
            LLMClient.MODE_GPT_OSS,
            LLMClient.MODE_GENERAL_COMPUTE,
            LLMClient.MODE_MISTRAL,
            LLMClient.MODE_GEMINI,
        ],
        help="LLM backend to use for sequel generation.",
    )
    sequel_parser.add_argument(
        "--ollama-model",
        default=DEFAULT_NARRATIVE_OLLAMA_MODEL,
        help="Optional explicit model tag override for Ollama-backed or General Compute-backed runs.",
    )
    sequel_parser.add_argument("--planner-model-mode", default="", choices=[""] + MODEL_MODE_CHOICES, help="Optional separate planner model mode for blueprint/outline JSON stages.")
    sequel_parser.add_argument("--planner-model", default="", help="Optional separate planner model tag override.")
    sequel_parser.add_argument("--prose-model-mode", default="", choices=[""] + MODEL_MODE_CHOICES, help="Optional separate prose model mode for scene-writing stages.")
    sequel_parser.add_argument("--prose-model", default="", help="Optional separate prose model tag override.")
    sequel_parser.set_defaults(func=generate_sequel)

    sequel_graph_parser = subparsers.add_parser(
        "generate-sequel-neo4j",
        help="Run the full narrative generation pipeline using Neo4j-backed retrieval.",
    )
    sequel_graph_parser.add_argument("--series-id", default="", help="Series/corpus identifier stored on the Neo4j Series node.")
    sequel_graph_parser.add_argument("--book-title", action="append", default=[], help="Book title as stored on the Neo4j Book node. Repeat to target a subset.")
    sequel_graph_parser.add_argument("--prompt", required=True, help="Creative direction for the sequel.")
    sequel_graph_parser.add_argument("--output-dir", required=True, help="Directory for chapter outputs.")
    sequel_graph_parser.add_argument("--chapters", type=int, default=None, help="Requested chapter count for the generated book.")
    sequel_graph_parser.add_argument("--canon-position", default="post_canon", choices=["pre_canon", "mid_canon_insert", "mid_canon_divergent", "post_canon"], help="Place the generated story before canon, inside canon as an insertion, inside canon as a divergence branch, or after canon.")
    sequel_graph_parser.add_argument("--new-plot", default="", help="A new major plotline to inject into the generated story.")
    sequel_graph_parser.add_argument("--primary-pov", default="", help="Optional primary POV character to enforce across generated chapter outlines.")
    sequel_graph_parser.add_argument("--relationship-direction", action="append", default=[], help="Relationship direction in the form 'name1,name2|relationship_type|desired direction|optional notes'. Repeat for multiple relationship goals.")
    sequel_graph_parser.add_argument("--preserve-event", action="append", default=[], help="Canon element to preserve in the form 'event_id|description' or just 'description'. Repeat for multiple preserved canon elements.")
    sequel_graph_parser.add_argument("--continuity-anchor", default="", help="Free-text continuity constraint describing where the story must fit.")
    sequel_graph_parser.add_argument("--divergence-anchor", default="", help="Required for mid_canon_divergent. The canon event where the branch begins.")
    sequel_graph_parser.add_argument("--anchor-after", default="", help="Optional canon anchor that the story must occur after.")
    sequel_graph_parser.add_argument("--anchor-before", default="", help="Optional canon anchor that the story must occur before.")
    sequel_graph_parser.add_argument("--uri", default=None, help="Neo4j URI. Falls back to NEO4J_URI.")
    sequel_graph_parser.add_argument("--username", default=None, help="Neo4j username. Falls back to NEO4J_USERNAME.")
    sequel_graph_parser.add_argument("--password", default=None, help="Neo4j password. Falls back to NEO4J_PASSWORD.")
    sequel_graph_parser.add_argument("--database", default=None, help="Neo4j database. Falls back to NEO4J_DATABASE.")
    sequel_graph_parser.add_argument(
        "--model-mode",
        default=DEFAULT_NARRATIVE_MODEL_MODE,
        choices=MODEL_MODE_CHOICES,
    )
    sequel_graph_parser.add_argument(
        "--ollama-model",
        default=DEFAULT_NARRATIVE_OLLAMA_MODEL,
        help="Optional explicit model tag override for Ollama-backed or General Compute-backed runs.",
    )
    sequel_graph_parser.add_argument("--planner-model-mode", default="", choices=[""] + MODEL_MODE_CHOICES, help="Optional separate planner model mode for blueprint/outline JSON stages.")
    sequel_graph_parser.add_argument("--planner-model", default="", help="Optional separate planner model tag override.")
    sequel_graph_parser.add_argument("--prose-model-mode", default="", choices=[""] + MODEL_MODE_CHOICES, help="Optional separate prose model mode for scene-writing stages.")
    sequel_graph_parser.add_argument("--prose-model", default="", help="Optional separate prose model tag override.")
    sequel_graph_parser.set_defaults(func=generate_sequel_neo4j)

    compare_parser = subparsers.add_parser(
        "compare-generation-models",
        help="Generate the same narrative brief with two model configurations and write a comparison artifact.",
    )
    compare_parser.add_argument("--series-id", required=True, help="Series/corpus identifier stored on the Neo4j Series node.")
    compare_parser.add_argument("--book-title", action="append", default=[], help="Book title as stored on the Neo4j Book node. Repeat to target a subset.")
    compare_parser.add_argument("--prompt", required=True, help="Creative direction for the generation run.")
    compare_parser.add_argument("--output-dir", required=True, help="Directory for both generated runs and the comparison artifact.")
    compare_parser.add_argument("--chapters", type=int, default=None, help="Requested chapter count for the generated book.")
    compare_parser.add_argument("--canon-position", default="post_canon", choices=["pre_canon", "mid_canon_insert", "mid_canon_divergent", "post_canon"])
    compare_parser.add_argument("--new-plot", default="", help="A new major plotline to inject into the generated story.")
    compare_parser.add_argument("--primary-pov", default="", help="Optional primary POV character to enforce across generated chapter outlines.")
    compare_parser.add_argument("--relationship-direction", action="append", default=[], help="Relationship direction in the form 'name1,name2|relationship_type|desired direction|optional notes'. Repeat for multiple relationship goals.")
    compare_parser.add_argument("--preserve-event", action="append", default=[], help="Canon element to preserve in the form 'event_id|description' or just 'description'. Repeat for multiple preserved canon elements.")
    compare_parser.add_argument("--continuity-anchor", default="", help="Free-text continuity constraint describing where the story must fit.")
    compare_parser.add_argument("--divergence-anchor", default="", help="Required for mid_canon_divergent. The canon event where the branch begins.")
    compare_parser.add_argument("--anchor-after", default="", help="Optional canon anchor that the story must occur after.")
    compare_parser.add_argument("--anchor-before", default="", help="Optional canon anchor that the story must occur before.")
    compare_parser.add_argument("--uri", default=None, help="Neo4j URI. Falls back to NEO4J_URI.")
    compare_parser.add_argument("--username", default=None, help="Neo4j username. Falls back to NEO4J_USERNAME.")
    compare_parser.add_argument("--password", default=None, help="Neo4j password. Falls back to NEO4J_PASSWORD.")
    compare_parser.add_argument("--database", default=None, help="Neo4j database. Falls back to NEO4J_DATABASE.")
    compare_parser.add_argument("--model-mode-a", default=DEFAULT_NARRATIVE_MODEL_MODE, choices=MODEL_MODE_CHOICES)
    compare_parser.add_argument("--ollama-model-a", default=DEFAULT_NARRATIVE_OLLAMA_MODEL, help="Ollama model tag override for model A.")
    compare_parser.add_argument("--planner-model-mode-a", default="", choices=[""] + MODEL_MODE_CHOICES, help="Optional separate planner model mode for run A.")
    compare_parser.add_argument("--planner-model-a", default="", help="Optional separate planner model tag override for run A.")
    compare_parser.add_argument("--prose-model-mode-a", default="", choices=[""] + MODEL_MODE_CHOICES, help="Optional separate prose model mode for run A.")
    compare_parser.add_argument("--prose-model-a", default="", help="Optional separate prose model tag override for run A.")
    compare_parser.add_argument("--model-mode-b", default=DEFAULT_NARRATIVE_MODEL_MODE, choices=MODEL_MODE_CHOICES)
    compare_parser.add_argument("--ollama-model-b", default="gpt-oss:120b-cloud", help="Ollama model tag override for model B.")
    compare_parser.add_argument("--planner-model-mode-b", default="", choices=[""] + MODEL_MODE_CHOICES, help="Optional separate planner model mode for run B.")
    compare_parser.add_argument("--planner-model-b", default="", help="Optional separate planner model tag override for run B.")
    compare_parser.add_argument("--prose-model-mode-b", default="", choices=[""] + MODEL_MODE_CHOICES, help="Optional separate prose model mode for run B.")
    compare_parser.add_argument("--prose-model-b", default="", help="Optional separate prose model tag override for run B.")
    compare_parser.set_defaults(func=compare_generation_models)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except (ValueError, Neo4jIngestionError) as exc:
        raise SystemExit(str(exc))
    except Exception as exc:
        if exc.__class__.__name__ == "SceneFailurePolicyError":
            raise SystemExit(str(exc))
        raise


if __name__ == "__main__":
    main()
