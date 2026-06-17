from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_BOOKNLP_PIPELINE_IDENTITY_JSON = Path(
    "analysis_outputs/identity_model_shootout/acotar_book1_fair_v2/booknlp_small_pipeline_identity.json"
)


def _normalize_key(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip().lower())
    return cleaned


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", _normalize_key(text))
    return slug.strip("_") or "entity"


def _quote_count(row: Dict[str, Any]) -> int:
    return int(row.get("quote_count", 0) or 0)


def _mention_count(row: Dict[str, Any]) -> int:
    return int(row.get("mention_count", 0) or 0)


def _first_seen(row: Dict[str, Any]) -> int:
    return int(row.get("first_seen", 0) or 0)


def _clean_aliases(aliases: List[str], display_name: str) -> List[str]:
    seen: set[str] = set()
    cleaned: List[str] = []
    for alias in [display_name, *(aliases or [])]:
        value = str(alias or "").strip()
        if not value:
            continue
        key = _normalize_key(value)
        if not key or key in seen:
            continue
        seen.add(key)
        cleaned.append(value)
    return cleaned


@dataclass
class BookNLPCleanIdentityProvider:
    input_json: Path
    _raw_cache: Optional[Dict[str, Any]] = field(default=None, init=False, repr=False)
    _pipeline_identity_cache: Optional[Dict[str, Any]] = field(default=None, init=False, repr=False)
    _identity_result_cache: Optional[Dict[str, Any]] = field(default=None, init=False, repr=False)

    @classmethod
    def from_path(cls, input_json: str | Path) -> "BookNLPCleanIdentityProvider":
        return cls(input_json=Path(input_json))

    def load_raw(self) -> Dict[str, Any]:
        if self._raw_cache is None:
            self._raw_cache = json.loads(self.input_json.read_text(encoding="utf-8"))
        return dict(self._raw_cache)

    def build_pipeline_identity(self) -> Dict[str, Any]:
        if self._pipeline_identity_cache is not None:
            return json.loads(json.dumps(self._pipeline_identity_cache))
        raw = self.load_raw()
        if isinstance(raw.get("pipeline_identity"), dict):
            payload = dict(raw["pipeline_identity"])
            payload.setdefault("provider", "booknlp_clean")
            payload.setdefault("source_file", str(self.input_json))
            self._pipeline_identity_cache = payload
            return json.loads(json.dumps(payload))
        if {"characters", "alias_index", "reference_entities", "narrator"}.issubset(raw.keys()):
            payload = dict(raw)
            payload.setdefault("provider", "booknlp_clean")
            payload.setdefault("source_file", str(self.input_json))
            payload.setdefault("suppressed_clusters", [])
            payload.setdefault("diagnostics", {})
            self._pipeline_identity_cache = payload
            return json.loads(json.dumps(payload))
        stable_rows = raw.get("stable_named_characters") or []
        ref_rows = raw.get("reference_entities") or []
        narrator_row = raw.get("narrator") or {}

        characters: List[Dict[str, Any]] = []
        alias_index: Dict[str, str] = {}
        for row in stable_rows:
            display_name = str(row.get("display_name") or "").strip()
            if not display_name:
                continue
            character_id = f"char_{_slugify(display_name)}"
            aliases = _clean_aliases(row.get("aliases") or [], display_name)
            payload = {
                "id": character_id,
                "display_name": display_name,
                "aliases": aliases,
                "mention_count": _mention_count(row),
                "quote_count": _quote_count(row),
                "first_seen": _first_seen(row),
                "source": str(raw.get("system") or "booknlp_small_clean"),
                "risk_flags": list(row.get("risk_flags") or []),
                "cluster_ids": list(row.get("cluster_ids") or []),
                "merged_from_clusters": list(row.get("merged_from_clusters") or []),
                "proper_mentions": list(row.get("proper_mentions") or []),
                "common_mentions": list(row.get("common_mentions") or []),
                "pronoun_mentions": list(row.get("pronoun_mentions") or []),
                "llm_review": row.get("llm_review") if isinstance(row.get("llm_review"), dict) else {},
            }
            characters.append(payload)
            for alias in aliases:
                alias_index[_normalize_key(alias)] = character_id

        reference_entities: List[Dict[str, Any]] = []
        for row in ref_rows:
            display_name = str(row.get("display_name") or "").strip()
            if not display_name:
                continue
            entity_id = f"ref_{_slugify(display_name)}"
            aliases = _clean_aliases(row.get("aliases") or [], display_name)
            reference_entities.append(
                {
                    "id": entity_id,
                    "display_name": display_name,
                    "aliases": aliases,
                    "category": str(row.get("category") or "reference_entity"),
                    "mention_count": _mention_count(row),
                    "quote_count": _quote_count(row),
                    "first_seen": _first_seen(row),
                    "risk_flags": list(row.get("risk_flags") or []),
                    "cluster_ids": list(row.get("cluster_ids") or []),
                    "merged_from_clusters": list(row.get("merged_from_clusters") or []),
                    "proper_mentions": list(row.get("proper_mentions") or []),
                    "common_mentions": list(row.get("common_mentions") or []),
                    "pronoun_mentions": list(row.get("pronoun_mentions") or []),
                    "llm_review": row.get("llm_review") if isinstance(row.get("llm_review"), dict) else {},
                }
            )

        narrator = {
            "id": "narrator_0",
            "display_name": str(narrator_row.get("display_name") or "[NARRATOR]"),
            "possible_name": narrator_row.get("possible_name"),
            "confidence": narrator_row.get("confidence"),
            "mention_count": _mention_count(narrator_row),
            "quote_count": _quote_count(narrator_row),
            "first_seen": _first_seen(narrator_row),
            "risk_flags": list(narrator_row.get("risk_flags") or []),
        }

        payload = {
            "provider": "booknlp_clean",
            "source_file": str(self.input_json),
            "characters": sorted(characters, key=lambda row: (-row["mention_count"], row["display_name"].lower())),
            "narrator": narrator,
            "reference_entities": sorted(reference_entities, key=lambda row: (-row["mention_count"], row["display_name"].lower())),
            "alias_index": alias_index,
            "suppressed_clusters": raw.get("suppressed_clusters") or [],
            "diagnostics": raw.get("diagnostics") or {},
        }
        self._pipeline_identity_cache = payload
        return json.loads(json.dumps(payload))

    def build_identity_result_compat(self) -> Dict[str, Any]:
        if self._identity_result_cache is not None:
            return json.loads(json.dumps(self._identity_result_cache))
        pipeline_identity = self.build_pipeline_identity()
        alias_map = {
            row["display_name"]: list(row["aliases"])
            for row in pipeline_identity["characters"]
        }
        rejected = [
            str(row.get("display_name") or "").strip()
            for row in pipeline_identity.get("suppressed_clusters") or []
            if str(row.get("display_name") or "").strip()
        ]
        payload = {
            "alias_map": alias_map,
            "rejected_non_characters": sorted(set(rejected), key=str.lower),
            "decisions": [],
            "alias_history": [],
            "identity_strategy": "booknlp_small_clean",
            "identity_provider": "booknlp_clean",
            "provider_locked": True,
            "provider_characters": pipeline_identity["characters"],
            "provider_alias_index": pipeline_identity["alias_index"],
            "unresolved_identity_candidates": [],
            "narrator": pipeline_identity["narrator"],
            "reference_entities": pipeline_identity["reference_entities"],
        }
        self._identity_result_cache = payload
        return json.loads(json.dumps(payload))

    def resolve_alias(self, alias: str) -> Optional[Dict[str, Any]]:
        pipeline_identity = self.build_pipeline_identity()
        alias_index = pipeline_identity["alias_index"]
        char_id = alias_index.get(_normalize_key(alias))
        if not char_id:
            return None
        for row in pipeline_identity["characters"]:
            if row["id"] == char_id:
                return row
        return None


def resolve_identity_provider_input(
    *,
    provider_mode: str,
    input_json: str | Path | None = None,
    book_inputs: Optional[List[Dict[str, Any]]] = None,
) -> Any:
    mode = str(provider_mode or "booknlp_clean").strip().lower()
    if mode != "booknlp_clean":
        raise ValueError(
            f"Unsupported identity provider: {provider_mode}. "
            "The legacy/custom resolver has been removed; only booknlp_clean is supported."
        )
    raw_input = str(input_json or "").strip()
    if raw_input.startswith("db://identity-series/"):
        from saga.identity.series_identity_provider import SeriesBookNLPCleanIdentityProvider
        from saga.storage.persistence import SagaSQLiteStore

        series_id = raw_input.split("db://identity-series/", 1)[-1].strip()
        payload = SagaSQLiteStore().get_identity_series_payload(series_id)
        if not isinstance(payload, dict):
            raise FileNotFoundError(
                f"BookNLP clean identity series '{series_id}' was not found in SQLite. "
                "Generate or index the identity bundle first."
            )
        return SeriesBookNLPCleanIdentityProvider.from_payload(payload)
    resolved_path = Path(raw_input) if raw_input else DEFAULT_BOOKNLP_PIPELINE_IDENTITY_JSON
    if not resolved_path.exists():
        raise FileNotFoundError(
            f"BookNLP clean identity file not found at {resolved_path}. "
            "Pass --identity-json with a valid path or generate the pipeline identity first."
        )
    raw = json.loads(resolved_path.read_text(encoding="utf-8"))
    if "book_identity_paths" in raw and "series_id" in raw:
        from saga.identity.series_identity_provider import SeriesBookNLPCleanIdentityProvider

        return SeriesBookNLPCleanIdentityProvider.from_path(resolved_path)
    return BookNLPCleanIdentityProvider.from_path(resolved_path)


def override_contract_with_identity_provider(
    contract: Dict[str, Any],
    *,
    provider_mode: str,
    input_json: str | Path | None = None,
) -> Dict[str, Any]:
    mode = str(provider_mode or "booknlp_clean").strip().lower()
    if mode != "booknlp_clean":
        raise ValueError(
            f"Unsupported identity provider: {provider_mode}. "
            "The legacy/custom resolver has been removed; only booknlp_clean is supported."
        )

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

    contract_books = list((((contract.get("inputs") or {}).get("books") or [])))
    provider = resolve_identity_provider_input(
        provider_mode=mode,
        input_json=input_json,
        book_inputs=contract_books or None,
    )
    patched = dict(contract)
    outputs = dict((patched.get("outputs") or {}))
    if hasattr(provider, "build_identity_result_compat"):
        try:
            identity_result = provider.build_identity_result_compat(book_inputs=contract_books or None)
            pipeline_identity = provider.build_pipeline_identity(book_inputs=contract_books or None)
        except TypeError:
            identity_result = provider.build_identity_result_compat()
            pipeline_identity = provider.build_pipeline_identity()
    else:
        identity_result = provider.build_identity_result_compat()
        pipeline_identity = provider.build_pipeline_identity()
    outputs["identity_result"] = identity_result
    outputs["pipeline_identity"] = pipeline_identity

    scene_analyses = outputs.get("scene_analyses") or []
    resolved_scene_analyses = rebuild_resolved_scene_analyses(scene_analyses, identity_result)
    entity_registry = build_entity_registry(resolved_scene_analyses)
    state_result = build_state_result(resolved_scene_analyses)
    timeline = build_timeline(resolved_scene_analyses)
    causal_graph_result = outputs.get("causal_graph_result") or {"graph": {"events": [], "critical_path": [], "flexible_events": [], "causal_chains": [], "divergence_points": []}, "metrics": {}}
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
    latest_scene = resolved_scene_analyses[-1] if resolved_scene_analyses else {}
    canon_snapshot = build_canon_snapshot(
        state_result,
        (
            latest_scene.get("book_index", 1),
            latest_scene.get("chapter_index", 1),
            latest_scene.get("scene_index", 1),
        ),
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
        "timeline": timeline,
        "event_ledger": event_ledger,
        "character_timelines": character_timelines,
        "character_profiles": character_profiles,
        "canon_snapshot": canon_snapshot,
        "stable_character_states": stable_character_states,
        "story_index_summary": story_index_summary,
    })
    patched["outputs"] = outputs
    return patched


def run_booknlp_identity_integration_smoke(
    *,
    input_json: str | Path,
    contract_json: str | Path,
    output_json: str | Path,
    report_md: str | Path,
) -> Dict[str, Any]:
    from saga.domain.pipeline_contract import normalize_character_timelines
    from saga.domain.stable_character_state import StableCharacterStateBuilder

    provider = BookNLPCleanIdentityProvider.from_path(input_json)
    pipeline_identity = provider.build_pipeline_identity()
    identity_result = provider.build_identity_result_compat()

    contract_payload = json.loads(Path(contract_json).read_text(encoding="utf-8"))
    outputs = contract_payload.get("outputs", {})
    normalized_timelines = normalize_character_timelines(outputs.get("character_timelines") or [], identity_result)
    stable_states = StableCharacterStateBuilder().build(
        character_profiles=[],
        identity_result=identity_result,
        canon_snapshot=outputs.get("canon_snapshot") or [],
        state_result=outputs.get("state_result") or {},
    )

    lookup_names = ["Tamlin", "Lucien", "Feyre", "Rhysand"]
    alias_resolution = {
        name: provider.resolve_alias(name)
        for name in lookup_names
    }
    smoke = {
        "provider": "booknlp_clean",
        "input_json": str(input_json),
        "contract_json": str(contract_json),
        "loaded_character_count": len(pipeline_identity["characters"]),
        "alias_index_count": len(pipeline_identity["alias_index"]),
        "reference_entity_count": len(pipeline_identity["reference_entities"]),
        "narrator": pipeline_identity["narrator"],
        "normalized_timeline_count": len(normalized_timelines),
        "stable_state_count": len(stable_states),
        "alias_resolution": alias_resolution,
        "reference_entity_samples": pipeline_identity["reference_entities"][:10],
        "downstream_errors": [],
    }

    Path(output_json).write_text(json.dumps({
        "pipeline_identity": pipeline_identity,
        "identity_result_compat": identity_result,
        "smoke": smoke,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    report_lines = [
        "# Identity Layer Integration Report",
        "",
        "## Final Identity Layer",
        "",
        "- Provider: `booknlp_clean`",
        "- Source system: `BookNLP small + cleanup adapter`",
        "",
        "## Why This Won",
        "",
        "- Best practical runtime/quality tradeoff from the fair v2 shootout.",
        "- Main ACOTAR cast is recovered in the cleaned stable tier.",
        "- Quote counts are available from BookNLP.",
        "- Cleanup burden is narrow and manageable.",
        "",
        "## Pipeline Schema",
        "",
        "```json",
        json.dumps({
            "characters": pipeline_identity["characters"][:2],
            "narrator": pipeline_identity["narrator"],
            "reference_entities": pipeline_identity["reference_entities"][:2],
            "alias_index": {key: pipeline_identity["alias_index"][key] for key in list(pipeline_identity["alias_index"])[:4]},
        }, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Smoke Test",
        "",
        f"- Loaded identity JSON: `yes`",
        f"- Characters loaded: `{smoke['loaded_character_count']}`",
        f"- Aliases indexed: `{smoke['alias_index_count']}`",
        f"- Reference entities loaded: `{smoke['reference_entity_count']}`",
        f"- Narrator separate: `{'yes' if pipeline_identity['narrator'].get('display_name') == '[NARRATOR]' else 'no'}`",
        f"- Character timelines normalized downstream: `{smoke['normalized_timeline_count']}`",
        f"- Stable state packets built downstream: `{smoke['stable_state_count']}`",
        f"- Downstream errors: `{'none' if not smoke['downstream_errors'] else '; '.join(smoke['downstream_errors'])}`",
        "",
        "## Alias Resolution Checks",
        "",
    ]
    for name in lookup_names:
        resolved = alias_resolution.get(name)
        if resolved:
            report_lines.append(f"- `{name}` -> `{resolved['display_name']}` (`{resolved['id']}`)")
        else:
            report_lines.append(f"- `{name}` -> `unresolved`")
    report_lines.extend([
        "",
        "## Narrator Handling",
        "",
        f"- Display name: `{pipeline_identity['narrator'].get('display_name')}`",
        f"- Possible name: `{pipeline_identity['narrator'].get('possible_name')}`",
        f"- Mention count: `{pipeline_identity['narrator'].get('mention_count')}`",
        f"- Quote count: `{pipeline_identity['narrator'].get('quote_count')}`",
        "",
        "## Known Limitations",
        "",
        "- Some stable display names are still short canonical forms like `Isaac`, `Clare`, and `Tomas` even though fuller aliases are preserved.",
        "- Narrator remains separate and is not automatically merged into `Feyre`.",
        "- Reference entities are available for analysis, but not all should be treated as main memory characters.",
        "",
        "## Next Story-Generation Step",
        "",
        "- Use `characters` as the primary character-memory roster.",
        "- Use `alias_index` for mention resolution into character IDs.",
        "- Use `reference_entities` as secondary world/entity context.",
        "- Keep `[NARRATOR]` separate as POV context.",
    ])
    Path(report_md).write_text("\n".join(report_lines), encoding="utf-8")
    return smoke
