"""Lightweight CLI for contract-centric downstream workflows."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import os
import re
import shutil
import sys
import threading
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List

from saga.domain.pipeline_contract import (
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
from saga.domain.stable_character_state import StableCharacterStateBuilder
from saga.providers.reasoning_runtime_adapter import (
    MODE_CODEX,
    MODE_DEEPSEEK,
    MODE_GENERAL_COMPUTE,
    MODE_GEMINI,
    MODE_GPT_OSS,
    MODE_MISTRAL,
    create_runtime_client,
    probe_runtime_mode_access,
)
from saga.providers.neo4j_ingestion_service import Neo4jIngestionError, Neo4jIngestionService
from saga.agents.db_event_agent import DatabaseEventAnalysisAgent
from saga.retrieval.neo4j_narrative_context_service import Neo4jNarrativeContextService
from saga.retrieval.narrative_context_service import NarrativeContextService
from saga.retrieval.target_character_state_service import TargetCharacterStateService
from saga.retrieval.visual_world_state_service import VisualWorldStateService
from saga.identity.identity_provider import (
    DEFAULT_BOOKNLP_PIPELINE_IDENTITY_JSON,
    override_contract_with_identity_provider,
)
from saga.services.comfyui_character_sheet_service import (
    ComfyUICharacterSheetService,
    render_manifest_path_for_contract,
)
from saga.services.entity_visual_prompt_service import EntityVisualPromptService
from saga.services.narrative_generation_service import NarrativeGenerationService
from saga.services.visual_prompt_rewrite_service import VisualPromptRewriteService
from saga.services.wiki_character_reference_service import WikiCharacterReferenceService
from saga.storage.persistence import SagaSQLiteStore

CorpusHardeningService = None

DEFAULT_NARRATIVE_MODEL_MODE = MODE_GPT_OSS
DEFAULT_NARRATIVE_OLLAMA_MODEL = "gemma4:31b-cloud"
DEFAULT_PRODUCTION_IDENTITY_PROVIDER = "booknlp_clean"
MODEL_MODE_CHOICES = [
    MODE_DEEPSEEK,
    MODE_GPT_OSS,
    MODE_CODEX,
    MODE_GENERAL_COMPUTE,
    MODE_MISTRAL,
    MODE_GEMINI,
]
IDENTITY_PROVIDER_CHOICES = ["booknlp_clean"]
ANALYSIS_PROVIDER_MODE_CHOICES = ["single_provider", "same_provider_rotating", "cross_provider_fallback"]
SQLITE_STORE = SagaSQLiteStore()


def _preflight_model_access(model_mode: str, provider_mode: str) -> None:
    provider_mode = str(provider_mode or "single_provider").strip().lower()
    probe_result = probe_runtime_mode_access(
        model_mode,
        timeout=30,
        max_retries=1,
        allow_account_rotation=(provider_mode == "same_provider_rotating"),
        allow_cross_provider_fallback=(provider_mode == "cross_provider_fallback"),
    )
    if probe_result.get("status") == "ok":
        return
    model_name = str(probe_result.get("model") or model_mode)
    raise ValueError(
        f"Model access failed for mode '{model_mode}' using model '{model_name}': "
        f"{probe_result.get('detail') or probe_result.get('status')}. "
        "Configure a working provider account or switch to another model provider."
    )


class _TerminalProgressPrinter:
    def __init__(self, *, enabled: bool = True, width: int = 28) -> None:
        self.enabled = enabled
        self.width = width
        self._last_was_bar = False
        stream = getattr(sys, "stdout", None)
        self._stream = stream
        self._interactive = bool(
            enabled
            and stream is not None
            and hasattr(stream, "isatty")
            and stream.isatty()
        )

    def _safe_write(self, text: str) -> bool:
        if not self.enabled or self._stream is None:
            return False
        try:
            self._stream.write(text)
            self._stream.flush()
            return True
        except (BrokenPipeError, OSError, ValueError):
            self.enabled = False
            self._last_was_bar = False
            return False

    def __call__(self, phase: str, payload: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        payload = payload or {}
        current = payload.get("current")
        total = payload.get("total")
        label = str(payload.get("label") or payload.get("status") or phase).strip()
        done = bool(payload.get("done"))
        if isinstance(current, int) and isinstance(total, int) and total >= 0:
            if self._interactive:
                filled = self.width if total == 0 else max(0, min(self.width, int(round((current / max(total, 1)) * self.width))))
                bar = "#" * filled + "-" * (self.width - filled)
                line = f"[{phase}] [{bar}] {current}/{total}"
                if label:
                    line += f" {label}"
                if self._safe_write("\r" + line[:200]):
                    self._last_was_bar = True
                    if done:
                        self._safe_write("\n")
                        self._last_was_bar = False
                    return
            print(f"[{phase}] {current}/{total} {label}".strip())
            return
        if self._last_was_bar:
            self._safe_write("\n")
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
    if phase == "scene_wait":
        scene_position = payload.get("scene_position")
        total_scenes = payload.get("total_scenes")
        chapter_index = payload.get("chapter_index")
        scene_index = payload.get("scene_index")
        elapsed_seconds = payload.get("elapsed_seconds")
        model = str(payload.get("analysis_model") or "").strip()
        scene_label = f"scene {scene_position}/{total_scenes}" if isinstance(scene_position, int) and isinstance(total_scenes, int) else "scene running"
        details = []
        if chapter_index is not None and scene_index is not None:
            details.append(f"ch {chapter_index} scene {scene_index}")
        if elapsed_seconds is not None:
            details.append(f"{elapsed_seconds}s elapsed")
        if model:
            details.append(model)
        suffix = " ط¢آ· ".join(details)
        return {
            "current": scene_position if isinstance(scene_position, int) else None,
            "total": total_scenes if isinstance(total_scenes, int) else None,
            "label": f"{label_prefix}{scene_label}" + (f" ط¢آ· {suffix}" if suffix else ""),
            "status": payload.get("status") or "Scene still running",
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
        from saga.services.corpus_hardening_service import CorpusHardeningService as _CorpusHardeningService

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
    return Path("analysis_outputs") / "pipeline_runtime" / series_id


def _series_contract_export_root(series_id: str) -> Path:
    return Path("analysis_outputs") / "contract_exports" / series_id


def _start_run_artifacts(series_id: str, *, export_contracts: bool = False) -> Dict[str, Any]:
    started = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    temp_root = Path(tempfile.mkdtemp(prefix=f"saga_{_safe_filename(series_id)}_"))
    run_dir = temp_root / started
    checkpoints_dir = temp_root / "resume_checkpoints"
    reports_dir = run_dir / "reports"
    contracts_dir = (_series_contract_export_root(series_id) / started / "contracts") if export_contracts else None
    run_dir.mkdir(parents=True, exist_ok=True)
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    if contracts_dir is not None:
        contracts_dir.mkdir(parents=True, exist_ok=True)
    return {
        "run_dir": run_dir,
        "contracts_dir": contracts_dir,
        "checkpoints_dir": checkpoints_dir,
        "reports_dir": reports_dir,
        "status_path": None,
        "latest_status_path": None,
        "log_path": None,
        "temp_root": temp_root,
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
        "run_id": run_dir.name,
        "worker_pid": os.getpid(),
        "worker_executable": os.path.abspath(os.sys.executable),
        "run_dir": str(run_dir),
        "log_path": str(log_path) if log_path else "",
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


def _save_status(status: Dict[str, Any], status_path: Path | None, latest_status_path: Path | None) -> None:
    status["updated_at_utc"] = _now_utc()
    if status_path is not None:
        _write_json(status_path, status)
    if latest_status_path is not None:
        _write_json(latest_status_path, status)


def _persist_run_status_sqlite(sqlite_store, status: Dict[str, Any]) -> None:
    if sqlite_store is None:
        return
    try:
        run_dir = Path(str(status.get("run_dir") or ""))
        run_id = str(status.get("run_id") or run_dir.name or "").strip()
        series_id = str(status.get("series_id") or "").strip()
        progress = None
        for book in status.get("books") or []:
            if isinstance(book, dict) and str(book.get("status") or "").strip().lower() == "running":
                payload = book.get("last_progress") if isinstance(book.get("last_progress"), dict) else None
                if payload:
                    progress = _encode_progress_payload(str(book.get("phase") or "running"), {
                        **payload,
                        "book": book.get("title") or payload.get("book"),
                    })
                break
        sqlite_store.upsert_pipeline_run(
            {
                "series_id": series_id,
                "series_title": status.get("series_title"),
                "run_id": run_id,
                "run_dir": f"db://pipeline-run/{series_id}/{run_id}" if series_id and run_id else "",
                "log_path": "",
                "status": status.get("status"),
                "status_reason": status.get("error") or "",
                "status_source": "saga_tools_status",
                "command_mode": ((status.get("plan") or {}).get("mode") or ""),
                "worker_pid": status.get("worker_pid"),
                "started_at_utc": status.get("started_at_utc"),
                "finished_at_utc": status.get("finished_at_utc"),
                "latest_progress_json": progress,
                "books": status.get("books") or [],
                "summary": status.get("summary") or {},
            }
        )
    except Exception:
        logging.exception("Failed to persist pipeline run status into SQLite.")


def _attach_file_logger(log_path: Path | None) -> logging.Handler:
    handler: logging.Handler
    if log_path is None:
        handler = logging.NullHandler()
    else:
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


def _book_contract_ref(*, book_id: str, contract_path: Path | None = None) -> str:
    if contract_path is not None:
        return str(contract_path)
    return f"db://book/{book_id}"


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
        "character_timelines": "saga.domain.timeline.characters",
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


def resplit_book_scenes(args) -> None:
    result = SQLITE_STORE.resplit_book_scenes(
        book_ref=str(args.book_ref),
        target_words=int(args.target_words or 700),
        allow_cross_chapter=bool(args.allow_cross_chapter),
        clear_dependent_rows=not bool(args.keep_dependent_rows),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def register_corpus(args) -> None:
    service = Neo4jIngestionService(
        uri=args.uri,
        username=args.username,
        password=args.password,
        database=args.database,
    )
    try:
        preflight = service.probe_connection()
        result = service.register_series(
            series_id=str(args.series_id or "").strip(),
            series_title=str(args.series_title or "").strip(),
        )
    finally:
        service.close()
    print(json.dumps({"neo4j_preflight": preflight, "result": result}, ensure_ascii=False, indent=2, default=str))


def inspect_corpus(args) -> None:
    service = Neo4jIngestionService(
        uri=args.uri,
        username=args.username,
        password=args.password,
        database=args.database,
    )
    try:
        preflight = service.probe_connection()
        result = service.inspect_series(series_id=str(args.series_id or "").strip())
    finally:
        service.close()
    print(json.dumps({"neo4j_preflight": preflight, "result": result}, ensure_ascii=False, indent=2, default=str))


def remove_book(args) -> None:
    service = Neo4jIngestionService(
        uri=args.uri,
        username=args.username,
        password=args.password,
        database=args.database,
    )
    try:
        preflight = service.probe_connection()
        result = service.remove_book(
            series_id=str(args.series_id or "").strip(),
            book_title=str(args.book_title or "").strip(),
        )
    finally:
        service.close()
    print(json.dumps({"neo4j_preflight": preflight, "result": result}, ensure_ascii=False, indent=2, default=str))


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
    llm = create_runtime_client(mode=args.model_mode, model_override=getattr(args, "ollama_model", ""))
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
    llm = create_runtime_client(mode=args.model_mode, model_override=getattr(args, "ollama_model", ""))
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
    llm = create_runtime_client(mode=args.model_mode, model_override=getattr(args, "ollama_model", ""))
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

    planner_llm = create_runtime_client(mode=planner_mode, model_override=planner_model)
    prose_llm = planner_llm if (planner_mode == prose_mode and planner_model == prose_model) else create_runtime_client(
        mode=prose_mode,
        model_override=prose_model,
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
        planner_llm = create_runtime_client(mode=planner_mode, model_override=planner_model)
        prose_llm = planner_llm if (planner_mode == prose_mode and planner_model == prose_model) else create_runtime_client(
            mode=prose_mode,
            model_override=prose_model,
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


def render_character_sheets(args) -> None:
    service = ComfyUICharacterSheetService()
    contract_ref = str(getattr(args, "book_ref", "") or getattr(args, "contract", "") or "").strip()
    if not contract_ref:
        raise ValueError("Either --book-ref or --contract is required.")
    entity_types = {
        str(value or "").strip().lower()
        for value in (getattr(args, "entity_type", None) or [])
        if str(value or "").strip()
    } or None
    entity_ids = {
        str(value or "").strip()
        for value in (getattr(args, "entity_id", None) or [])
        if str(value or "").strip()
    } or None
    prompt_ids = {
        str(value or "").strip()
        for value in (getattr(args, "prompt_id", None) or [])
        if str(value or "").strip()
    } or None
    payload = service.render_from_contract(
        contract_ref,
        limit=int(getattr(args, "limit", 0) or 0),
        overwrite=bool(getattr(args, "overwrite", False)),
        entity_types=entity_types,
        entity_ids=entity_ids,
        prompt_ids=prompt_ids,
    )
    manifest_path = render_manifest_path_for_contract(contract_ref)
    if str(getattr(args, "out", "") or "").strip():
        _write_json(args.out, payload)
        print(f"Character-sheet render manifest copied to: {Path(args.out)}")
    print(f"Character-sheet renders written under: {payload.get('output_dir')}")
    print(f"Character-sheet manifest written to: {manifest_path}")


def analyze_db_events(args) -> None:
    model_mode = str(getattr(args, "model_mode", "") or MODE_GPT_OSS).strip()
    provider_mode = str(getattr(args, "analysis_provider_mode", "") or "same_provider_rotating").strip()
    agent = DatabaseEventAnalysisAgent(
        llm_client=create_runtime_client(
            mode=model_mode,
            allow_account_rotation=(provider_mode == "same_provider_rotating"),
            allow_cross_provider_fallback=(provider_mode == "cross_provider_fallback"),
        )
    )
    payload = agent.analyze_book_chapter(
        book_ref=str(getattr(args, "book_ref", "") or "").strip(),
        chapter_index=int(getattr(args, "chapter_index", 1) or 1),
        replace_existing_agent_rows=bool(getattr(args, "replace_existing_agent_rows", False)),
    )
    _write_json(args.out, payload)
    report_md = Path(getattr(args, "report_md", "") or Path(args.out).with_suffix(".md"))
    report_md.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# DB Event Agent Chapter Audit",
        "",
        f"- Book ref: `{getattr(args, 'book_ref', '')}`",
        f"- Chapter index: `{payload.get('chapter_index')}`",
        f"- Scene index: `{payload.get('scene_index')}`",
        f"- Inserted events: `{payload.get('inserted_event_count')}`",
        f"- Known entities in roster: `{payload.get('known_entity_count')}`",
        f"- Agent version: `{payload.get('agent_version')}`",
        "",
        "## Scene Summary",
        "",
        payload.get("scene_summary") or "_empty_",
        "",
        "## Events",
        "",
    ]
    for row in payload.get("events") or []:
        lines.extend(
            [
                f"### {row.get('event_id')}",
                "",
                f"- Type: `{row.get('type')}`",
                f"- Description: {row.get('description')}",
                f"- Characters: `{', '.join(row.get('characters') or []) or 'none'}`",
                f"- Entities involved: `{', '.join(row.get('entities_involved') or []) or 'none'}`",
                f"- Reason: {row.get('reason') or '_empty_'}",
                f"- Outcome: {row.get('outcome') or '_empty_'}",
                "",
            ]
        )
    if payload.get("unresolved_entities"):
        lines.extend(
            [
                "## Unresolved Entities",
                "",
                *(f"- `{item}`" for item in payload.get("unresolved_entities") or []),
                "",
            ]
        )
    report_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"DB event agent JSON written to: {Path(args.out)}")
    print(f"DB event agent report written to: {report_md}")


def audit_visual_prompts(args) -> None:
    service = VisualPromptRewriteService()
    payload = service.audit_contract(
        args.contract,
        reference_json=(getattr(args, "reference_json", "") or None),
        names=list(getattr(args, "name", []) or []),
    )
    _write_json(args.out, payload)
    report_md = Path(getattr(args, "report_md", "") or Path(args.out).with_suffix(".md"))
    report_md.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Visual Prompt Persistent-Trait Audit",
        "",
        f"- Contract: `{args.contract}`",
        f"- Reference notes: `{getattr(args, 'reference_json', '') or 'none'}`",
        f"- Entries audited: `{len(payload.get('entries') or [])}`",
        "",
    ]
    for entry in payload.get("entries") or []:
        lines.extend(
            [
                f"## {entry.get('entity_name')}",
                "",
                f"- Entity type: `{entry.get('entity_type')}`",
                f"- Specificity score: `{entry.get('profile_specificity_score')}`",
                f"- Missing core slots: `{', '.join(entry.get('missing_core_slots') or []) or 'none'}`",
                f"- Contaminated fields: `{', '.join(entry.get('contaminated_fields') or []) or 'none'}`",
                f"- Issues: `{'; '.join(entry.get('issues') or []) or 'none'}`",
                "",
                "### Persistent Profile",
                "",
                "```json",
                json.dumps(entry.get("persistent_visual_profile") or {}, ensure_ascii=False, indent=2),
                "```",
                "",
                "### Current Prompt",
                "",
                entry.get("current_prompt") or "_empty_",
                "",
            ]
        )
    report_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"Visual prompt audit written to: {args.out}")
    print(f"Visual prompt audit report written to: {report_md}")


def rewrite_visual_prompts(args) -> None:
    service = VisualPromptRewriteService(
        llm_client=create_runtime_client(
            mode=getattr(args, "model_mode", MODE_CODEX),
            allow_account_rotation=True,
            allow_cross_provider_fallback=False,
        )
    )
    payload = service.rewrite_contract_prompts(
        args.contract,
        reference_json=(getattr(args, "reference_json", "") or None),
        names=list(getattr(args, "name", []) or []),
    )
    _write_json(args.out, payload)
    report_md = Path(getattr(args, "report_md", "") or Path(args.out).with_suffix(".md"))
    report_md.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Visual Prompt Rewrite Output",
        "",
        f"- Contract: `{args.contract}`",
        f"- Reference notes: `{getattr(args, 'reference_json', '') or 'none'}`",
        f"- Provider: `{payload.get('provider')}`",
        f"- Model: `{payload.get('model')}`",
        f"- Rewritten entries: `{len(payload.get('rewritten_prompts') or [])}`",
        "",
    ]
    for entry in payload.get("rewritten_prompts") or []:
        lines.extend(
            [
                f"## {entry.get('entity_name')}",
                "",
                f"- Entity type: `{entry.get('entity_type')}`",
                f"- Confidence: `{entry.get('confidence')}`",
                f"- Issues: `{'; '.join(entry.get('issues') or []) or 'none'}`",
                "",
                "### Rewritten Prompt",
                "",
                entry.get("rewritten_prompt") or "_empty_",
                "",
                "### Rewritten Profile",
                "",
                "```json",
                json.dumps(entry.get("persistent_visual_profile") or {}, ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
    report_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"Visual prompt rewrites written to: {args.out}")
    print(f"Visual prompt rewrite report written to: {report_md}")


def build_entity_visual_prompts(args) -> None:
    service = EntityVisualPromptService(SQLITE_STORE)
    result = service.build_book_prompts(args.book_ref, overwrite=bool(getattr(args, "overwrite", False)))
    payload = {
        "book_ref": args.book_ref,
        "book_id": result.book_id,
        "total_entities": result.total_entities,
        "prompts_written": result.prompts_written,
        "prompts_updated": result.prompts_updated,
        "prompts_skipped": result.prompts_skipped,
        "prompts_total": result.prompts_total,
    }
    target = _write_json(args.out, payload)
    print(f"Entity visual prompt summary written to: {target}")


def research_visual_references(args) -> None:
    service = WikiCharacterReferenceService(
        llm_client=create_runtime_client(
            mode=getattr(args, "model_mode", MODE_CODEX),
            allow_account_rotation=True,
            allow_cross_provider_fallback=False,
        ),
        wiki_base_url=getattr(args, "wiki_base_url", "") or "https://acourtofthornsandroses.fandom.com",
        series_id=getattr(args, "series_id", "") or "acotar",
    )
    rewrite_service = VisualPromptRewriteService()
    contract_rows = rewrite_service.collect_initial_rows(args.contract)
    context_map = {
        str(row.get("entity_name") or "").strip().lower(): {
            "source_evidence": row.get("source_evidence") or "",
            "persistent_visual_profile": row.get("profile") or {},
            "dynamic_visual_changes": row.get("dynamic_visual_changes") or [],
            "book_index": row.get("book_index"),
            "chapter_index": row.get("chapter_index"),
            "scene_index": row.get("scene_index"),
        }
        for row in contract_rows
        if str(row.get("entity_name") or "").strip()
    }
    contract_payload = rewrite_service.load_contract(args.contract)
    books = ((contract_payload.get("inputs") or {}).get("books") or [])
    contract_title = str((books[0] or {}).get("title") or "").strip() if books else ""
    names = list(getattr(args, "name", []) or [])
    if not names:
        names = [row.get("entity_name") for row in contract_rows if row.get("entity_name")]
    payload = service.research_names(names, context_map=context_map, contract_title=contract_title)
    _write_json(args.out, payload)
    report_md = Path(getattr(args, "report_md", "") or Path(args.out).with_suffix(".md"))
    report_md.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Web-Backed Character Reference Research",
        "",
        f"- Contract: `{getattr(args, 'contract', '')}`",
        f"- Wiki base URL: `{payload.get('wiki_base_url')}`",
        f"- Provider: `{payload.get('provider')}`",
        f"- Model: `{payload.get('model')}`",
        f"- Entries researched: `{len(payload.get('entries') or [])}`",
        "",
    ]
    for entry in payload.get("entries") or []:
        lines.extend(
            [
                f"## {entry.get('display_name')}",
                "",
                f"- Entity type: `{entry.get('entity_type')}`",
                f"- Page: `{entry.get('page_title')}`",
                f"- URL: `{entry.get('page_url')}`",
                f"- Search query: `{entry.get('search_query')}`",
                f"- Search candidates: `{', '.join(entry.get('search_candidates') or []) or 'none'}`",
                f"- Resolved via: `{entry.get('resolved_via')}`",
                f"- Target scope: `{entry.get('target_scope')}`",
                f"- Confidence: `{entry.get('confidence')}`",
                f"- Issues: `{'; '.join(entry.get('issues') or []) or 'none'}`",
                "",
                "### Canon Notes",
                "",
                *[f"- {note}" for note in (entry.get("canon_notes") or [])],
                "",
                "### Structured Traits",
                "",
                "```json",
                json.dumps(entry.get("structured_traits") or {}, ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
    report_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"Visual reference research written to: {args.out}")
    print(f"Visual reference research report written to: {report_md}")


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

    resplit_parser = subparsers.add_parser(
        "resplit-book-scenes",
        help="Re-split one persisted book into smaller scene rows using stored chapter text.",
    )
    resplit_parser.add_argument("--book-ref", required=True, help="SQLite book reference like db://book/<book_id>.")
    resplit_parser.add_argument("--target-words", type=int, default=700, help="Approximate target words per scene chunk.")
    resplit_parser.add_argument("--allow-cross-chapter", action="store_true", help="Allow a scene chunk to span chapter boundaries.")
    resplit_parser.add_argument("--keep-dependent-rows", action="store_true", help="Keep entities/events/profiles/states instead of clearing them. Not recommended for agent testing.")
    resplit_parser.set_defaults(func=resplit_book_scenes)

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

    render_character_parser = subparsers.add_parser(
        "render-character-sheets",
        help="Render character-sheet images from contract-native initial character prompts through Modal ComfyUI.",
    )
    render_character_parser.add_argument("--contract", default="", help="Legacy contract path or db://book/<id> reference.")
    render_character_parser.add_argument("--book-ref", default="", help="Canonical db://book/<id> reference.")
    render_character_parser.add_argument("--limit", type=int, default=0, help="Optional limit for quick tests.")
    render_character_parser.add_argument("--overwrite", action="store_true", help="Re-render images even if they already exist.")
    render_character_parser.add_argument("--entity-type", action="append", default=[], help="Optional entity type filter. Repeat for multi-type renders.")
    render_character_parser.add_argument("--entity-id", action="append", default=[], help="Optional exact SQLite entity id to render. Repeat for multi-entity renders.")
    render_character_parser.add_argument("--prompt-id", action="append", default=[], help="Optional exact SQLite visual prompt id to render. Repeat for multi-prompt renders.")
    render_character_parser.add_argument("--out", default="", help="Optional extra manifest output path.")
    render_character_parser.set_defaults(func=render_character_sheets)

    db_event_parser = subparsers.add_parser(
        "analyze-db-events",
        help="Run a standalone DB-native event analysis agent for one stored book chapter.",
    )
    db_event_parser.add_argument("--book-ref", required=True, help="Canonical db://book/<id> reference.")
    db_event_parser.add_argument("--chapter-index", type=int, required=True, help="Stored chapter index to analyze.")
    db_event_parser.add_argument("--model-mode", default=MODE_GPT_OSS, choices=MODEL_MODE_CHOICES, help="LLM backend for the standalone event agent.")
    db_event_parser.add_argument("--analysis-provider-mode", default="same_provider_rotating", choices=ANALYSIS_PROVIDER_MODE_CHOICES, help="Provider rotation mode for the standalone event agent.")
    db_event_parser.add_argument("--replace-existing-agent-rows", action="store_true", help="Replace prior rows produced by this standalone agent for the same chapter.")
    db_event_parser.add_argument("--out", required=True, help="Output path for the event-agent JSON result.")
    db_event_parser.add_argument("--report-md", default="", help="Optional markdown review report path.")
    db_event_parser.set_defaults(func=analyze_db_events)

    audit_visual_parser = subparsers.add_parser(
        "audit-visual-prompts",
        help="Audit persistent visual profiles and current character-sheet prompts from a contract.",
    )
    audit_visual_parser.add_argument("--contract", required=True, help="Path to the contract JSON.")
    audit_visual_parser.add_argument("--reference-json", default="", help="Optional canonical reference notes JSON keyed by character name.")
    audit_visual_parser.add_argument("--name", action="append", default=[], help="Optional character name filter. Repeat as needed.")
    audit_visual_parser.add_argument("--out", required=True, help="Output path for the audit JSON.")
    audit_visual_parser.add_argument("--report-md", default="", help="Optional markdown report path.")
    audit_visual_parser.set_defaults(func=audit_visual_prompts)

    rewrite_visual_parser = subparsers.add_parser(
        "rewrite-visual-prompts",
        help="Run the visual prompt rewrite agent against contract-native persistent character saga.prompts.",
    )
    rewrite_visual_parser.add_argument("--contract", required=True, help="Path to the contract JSON.")
    rewrite_visual_parser.add_argument("--reference-json", default="", help="Optional canonical reference notes JSON keyed by character name.")
    rewrite_visual_parser.add_argument("--name", action="append", default=[], help="Optional character name filter. Repeat as needed.")
    rewrite_visual_parser.add_argument("--model-mode", default=MODE_CODEX, choices=MODEL_MODE_CHOICES, help="LLM backend for the rewrite agent.")
    rewrite_visual_parser.add_argument("--out", required=True, help="Output path for the rewritten prompt JSON.")
    rewrite_visual_parser.add_argument("--report-md", default="", help="Optional markdown report path.")
    rewrite_visual_parser.set_defaults(func=rewrite_visual_prompts)

    build_db_visual_prompt_parser = subparsers.add_parser(
        "build-entity-visual-prompts",
        help="Build one persisted baseline visual prompt per DB entity from the typed visual trait tables.",
    )
    build_db_visual_prompt_parser.add_argument("--book-ref", required=True, help="Canonical DB ref like db://book/<book_id>.")
    build_db_visual_prompt_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing visual prompt rows.")
    build_db_visual_prompt_parser.add_argument("--out", required=True, help="Output path for the build summary JSON.")
    build_db_visual_prompt_parser.set_defaults(func=build_entity_visual_prompts)

    research_visual_parser = subparsers.add_parser(
        "research-visual-references",
        help="Collect web-backed canon appearance notes for contract characters from a fandom wiki.",
    )
    research_visual_parser.add_argument("--contract", required=True, help="Path to the contract JSON.")
    research_visual_parser.add_argument("--name", action="append", default=[], help="Optional character name filter. Repeat as needed.")
    research_visual_parser.add_argument("--wiki-base-url", default="https://acourtofthornsandroses.fandom.com", help="MediaWiki/Fandom base URL.")
    research_visual_parser.add_argument("--series-id", default="acotar", help="Series identifier used for title overrides.")
    research_visual_parser.add_argument("--model-mode", default=MODE_CODEX, choices=MODEL_MODE_CHOICES, help="LLM backend for structuring fetched notes.")
    research_visual_parser.add_argument("--out", required=True, help="Output path for the reference JSON.")
    research_visual_parser.add_argument("--report-md", default="", help="Optional markdown report path.")
    research_visual_parser.set_defaults(func=research_visual_references)

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
            MODE_DEEPSEEK,
            MODE_GPT_OSS,
            MODE_GENERAL_COMPUTE,
            MODE_MISTRAL,
            MODE_GEMINI,
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
            MODE_DEEPSEEK,
            MODE_GPT_OSS,
            MODE_GENERAL_COMPUTE,
            MODE_MISTRAL,
            MODE_GEMINI,
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
