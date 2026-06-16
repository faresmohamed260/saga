from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
import uuid
import webbrowser
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from core.builders.relationship_profile_builder import RelationshipProfileBuilder
from infrastructure.codex_session_store import CodexSessionStore
from infrastructure.general_compute_account_rotator import GeneralComputeAccountRotator
from infrastructure.llm_client import LLMClient
from redesign_lab.identity.series_identity_provider import (
    build_series_pipeline_identity,
    generate_book_identity_bundle,
)
from services.comfyui_character_sheet_service import render_manifest_path_for_contract
from services.encoder_persistence_service import EncoderPersistenceService
from sql_store.persistence import SagaSQLiteStore
from sql_store.models import Book as SqlBook
from sql_store.models import CharacterProfile as SqlCharacterProfile
from sql_store.models import Entity as SqlEntity
from sql_store.models import Event as SqlEvent
from sql_store.models import GeneratedImage as SqlGeneratedImage
from sql_store.models import IdentityAlias as SqlIdentityAlias
from sql_store.models import IdentityBook as SqlIdentityBook
from sql_store.models import IdentityCharacter as SqlIdentityCharacter
from sql_store.models import IdentityNarrator as SqlIdentityNarrator
from sql_store.models import IdentityReferenceEntity as SqlIdentityReferenceEntity
from sql_store.models import IdentitySeries as SqlIdentitySeries
from sql_store.models import Scene as SqlScene
from sql_store.models import StableCharacterState as SqlStableCharacterState
from sql_store.models import TimelineRow as SqlTimelineRow
from sql_store.models import VisualPrompt as SqlVisualPrompt


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dashboard_app" / "dist"
OUTPUTS_DIR = ROOT / "analysis_outputs"
DASHBOARD_DIR = OUTPUTS_DIR / "dashboard"
UPLOADS_DIR = DASHBOARD_DIR / "uploads"
OLLAMA_ACCOUNTS_FILE = ROOT / "deploy" / "ollama" / "accounts.local.json"
CODEX_ACCOUNTS_FILE = ROOT / "deploy" / "openai" / "accounts.local.json"
GENERAL_COMPUTE_ACCOUNTS_FILE = ROOT / "deploy" / "general_compute" / "accounts.local.json"

DEFAULT_BOOKS = [
    r"D:\Books\Ebooks\Sarah J. Maas\A Court of Thorns and Roses\A Court of Thorns and Roses.epub",
    r"D:\Books\Ebooks\Sarah J. Maas\A Court of Mist and Fury\A Court of Mist and Fury.epub",
    r"D:\Books\Ebooks\Sarah J. Maas\A Court of Wings and Ruin\A Court of Wings and Ruin.epub",
    r"D:\Books\Ebooks\Sarah J. Maas\A Court of Frost and Starlight\A Court of Frost and Starlight.epub",
    r"D:\Books\Ebooks\Sarah J. Maas\A Court of Silver Flames\A Court of Silver Flames.epub",
]

PROMPT_FILES = [
    "analysis/scene_analyzer.py",
    "analysis/entity_world_state_analyzer.py",
    "analysis/visual_state_analyzer.py",
    "analysis/identity_analyzer.py",
    "analysis/event_extractor.py",
    "analysis/microtasks/scene_fallback_synthesizer.py",
    "analysis/microtasks/scene_semantic_reviewer.py",
    "analysis/microtasks/identity_semantic_reviewer.py",
    "services/narrative_generation_service.py",
    "services/epub_processor.py",
    "services/pdf_processor.py",
    "prompts/causal_graph_prompt.py",
]

HEAVY_CONTRACT_BYTES = 2 * 1024 * 1024
SCAN_CACHE_TTL_SECONDS = 10
CONTRACT_SUMMARY_CACHE: dict[str, dict[str, Any]] = {}
SCAN_CACHE: dict[str, Any] = {"created_at": 0.0, "payload": None}
SQLITE_STORE = SagaSQLiteStore()
CODEX_SESSION_STORE = CodexSessionStore()

PLACEHOLDER_ANALYSIS_VALUES = {
    "",
    "n/a",
    "none",
    "null",
    "unknown",
    "not_explicitly_stated_in_text",
}

SPECULATIVE_ANALYSIS_PATTERNS = (
    "not explicitly stated",
    "not explicitly described",
    "commonly depicted",
    "presumed",
    "unspecified",
)


class EncodeRequest(BaseModel):
    books: list[str] = Field(default_factory=list)
    series_id: str = "acotar-full-booknlp-clean-live"
    series_title: str = "ACOTAR Full BookNLP Clean Live"
    book_index_base: int = 1
    analysis_model: str = "gpt_oss"
    identity_model: str = "gpt_oss"
    analysis_provider_mode: str = "same_provider_rotating"
    identity_provider: str = "booknlp_clean"
    identity_strategy: str = "scene_inline"
    series_identity_json: str = r"analysis_outputs\identity_series\acotar\acotar_series_pipeline_identity.json"
    scene_failure_policy: str = "fail_fast"
    max_failed_scenes_absolute: int = 3
    max_failed_scene_ratio: float = 0.10
    min_nonempty_scene_ratio: float = 0.80
    max_parallel_books: int = 1
    max_chapters: int = 0
    skip_ingest: bool = False
    no_progress: bool = True
    out: str = ""
    generate_identity_bundles: bool = False
    generate_visuals: bool = False
    identity_output_root: str = ""
    export_contracts: bool = False
    quality_preset: str = "balanced"
    force_full_text_scenes: bool = True
    visual_strictness: str = "strict"


class ProviderAccount(BaseModel):
    label: str
    email: str = ""
    password: str = ""
    api_key: str = ""


class OllamaProviderConfig(BaseModel):
    active_index: int = 0
    accounts: list[ProviderAccount] = Field(default_factory=list)


class CodexProviderConfig(BaseModel):
    active_index: int = 0
    accounts: list[ProviderAccount] = Field(default_factory=list)


class GeneralComputeProviderConfig(BaseModel):
    active_index: int = 0
    accounts: list[ProviderAccount] = Field(default_factory=list)


def _is_placeholder_analysis_value(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    lowered = text.lower()
    if lowered in PLACEHOLDER_ANALYSIS_VALUES:
        return True
    return any(pattern in lowered for pattern in SPECULATIVE_ANALYSIS_PATTERNS)


def _clean_analysis_text(value: Any) -> str:
    text = str(value or "").strip()
    return "" if _is_placeholder_analysis_value(text) else text


def _clean_analysis_list(values: Any) -> list[Any]:
    if not isinstance(values, list):
        return []
    cleaned: list[Any] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, str):
            normalized = _clean_analysis_text(value)
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(normalized)
            continue
        if isinstance(value, dict):
            normalized = _clean_analysis_dict(value)
            if normalized:
                key = json.dumps(normalized, sort_keys=True, ensure_ascii=True)
                if key in seen:
                    continue
                seen.add(key)
                cleaned.append(normalized)
            continue
        if value in (None, "", [], {}):
            continue
        key = repr(value)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(value)
    return cleaned


def _clean_analysis_dict(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            nested = _clean_analysis_dict(value)
            if nested:
                cleaned[key] = nested
            continue
        if isinstance(value, list):
            nested = _clean_analysis_list(value)
            if nested:
                cleaned[key] = nested
            continue
        if isinstance(value, str):
            normalized = _clean_analysis_text(value)
            if normalized:
                cleaned[key] = normalized
            continue
        if value in (None, "", [], {}):
            continue
        cleaned[key] = value
    return cleaned


def _summarize_analysis_fields(payload: dict[str, Any], keys: list[str], *, limit: int = 8) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for key in keys:
        value = _clean_analysis_text(payload.get(key))
        if not value:
            continue
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        parts.append(value)
        if len(parts) >= limit:
            break
    return ", ".join(parts)


class CharacterRenderRequest(BaseModel):
    contract_path: str
    limit: int = 0
    overwrite: bool = False



def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs() -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def is_db_book_ref(value: str) -> bool:
    return str(value or "").startswith("db://book/")


def parse_db_book_ref(value: str) -> str:
    if not is_db_book_ref(value):
        return ""
    return str(value).split("db://book/", 1)[-1].strip()


def slugify(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", str(text or "").strip().lower())
    return value.strip("-") or "series"


def normalize_books(books: list[str], book_index_base: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for offset, book_path in enumerate(books):
        clean = str(book_path or "").strip()
        if not clean:
            continue
        path = Path(clean)
        rows.append(
            {
                "path": clean,
                "title": path.name,
                "book_index": int(book_index_base) + offset,
            }
        )
    return rows


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _safe_db(default: Any, operation: str, func_call) -> Any:
    try:
        return func_call()
    except (OperationalError, SQLAlchemyError) as exc:
        print(f"[dashboard_runtime] database operation failed: {operation}: {exc}", file=sys.stderr)
        return default
    except Exception as exc:
        print(f"[dashboard_runtime] unexpected operation failure: {operation}: {exc}", file=sys.stderr)
        return default


def tail_lines(path: Path, limit: int = 80) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    except Exception:
        return []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def derive_scene_quality(scene_rows: list[Any], quality: dict[str, Any] | None = None) -> dict[str, int]:
    base = quality or {}
    successful = base.get("successful_scenes")
    failed = base.get("failed_scenes")
    total = base.get("total_scenes")
    if isinstance(successful, int) and isinstance(failed, int):
        return {
            "successful_scenes": successful,
            "failed_scenes": failed,
            "total_scenes": int(total) if isinstance(total, int) else successful + failed,
        }

    success_count = 0
    failed_count = 0
    for row in scene_rows or []:
        if not isinstance(row, dict):
            continue
        final_status = str(row.get("final_status") or "").strip().lower()
        error_flag = bool(row.get("error") or row.get("last_error"))
        error_category = str(row.get("error_category") or "").strip().lower()
        if final_status in {"failed", "error"} or error_flag or error_category:
            failed_count += 1
        else:
            success_count += 1
    return {
        "successful_scenes": success_count,
        "failed_scenes": failed_count,
        "total_scenes": len(scene_rows or []),
    }


def mask_secret(value: str) -> dict[str, Any]:
    value = str(value or "")
    if not value:
        return {"configured": False, "preview": ""}
    return {"configured": True, "preview": f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "configured"}


def contract_summary(path: Path, *, parse_heavy: bool = False) -> dict[str, Any]:
    stat = path.stat()
    cache_key = str(path.resolve())
    cached = CONTRACT_SUMMARY_CACHE.get(cache_key)
    if cached and cached.get("mtime_ns") == stat.st_mtime_ns and cached.get("size") == stat.st_size:
        return dict(cached["summary"])
    if stat.st_size > HEAVY_CONTRACT_BYTES and not parse_heavy:
        return {
            "path": rel(path),
            "name": path.name.replace(".contract.json", ""),
            "mtime": stat.st_mtime,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "run_status": "load on select",
            "identity_provider": "load on select",
            "scenes": "load",
            "successful_scenes": None,
            "failed_scenes": None,
            "entity_registry": "load",
            "timeline": "load",
            "event_ledger": "load",
            "character_profiles": "load",
            "stable_character_states": "load",
            "story_index_docs": "load",
            "load_deferred": True,
        }
    payload = load_json(path) or {}
    outputs = payload.get("outputs") or {}
    metadata = payload.get("metadata") or {}
    quality = metadata.get("scene_analysis_quality") or payload.get("scene_analysis_quality") or {}
    scenes = outputs.get("resolved_scene_analyses") or outputs.get("scene_analyses") or []
    derived_quality = derive_scene_quality(scenes, quality if isinstance(quality, dict) else {})
    title = metadata.get("book_title") or path.name.replace(".contract.json", "")
    summary = {
        "path": rel(path),
        "name": title,
        "mtime": stat.st_mtime,
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
        "run_status": metadata.get("run_status") or payload.get("run_status") or "unknown",
        "identity_provider": metadata.get("identity_provider") or payload.get("identity_provider") or "n/a",
        "scenes": len(scenes),
        "successful_scenes": derived_quality.get("successful_scenes"),
        "failed_scenes": derived_quality.get("failed_scenes"),
        "entity_registry": len(outputs.get("entity_registry") or []),
        "timeline": len(outputs.get("timeline") or []),
        "event_ledger": len(outputs.get("event_ledger") or []),
        "character_profiles": len(outputs.get("character_profiles") or []),
        "stable_character_states": len(outputs.get("stable_character_states") or []),
        "story_index_docs": len(((outputs.get("story_index") or {}).get("documents") or [])),
    }
    CONTRACT_SUMMARY_CACHE[cache_key] = {
        "mtime_ns": stat.st_mtime_ns,
        "size": stat.st_size,
        "summary": summary,
    }
    return summary


def _db_contract_summaries(limit: int = 200) -> list[dict[str, Any]]:
    def _query() -> list[dict[str, Any]]:
        with SQLITE_STORE.session_factory() as session:
            books = session.execute(select(SqlBook).order_by(SqlBook.updated_at.desc())).scalars().all()
            rows: list[dict[str, Any]] = []
            for book in books[:limit]:
                scene_count = session.execute(select(func.count()).select_from(SqlScene).where(SqlScene.book_id == book.id)).scalar_one()
                event_count = session.execute(select(func.count()).select_from(SqlEvent).where(SqlEvent.book_id == book.id)).scalar_one()
                entity_count = session.execute(select(func.count()).select_from(SqlEntity).where(SqlEntity.book_id == book.id)).scalar_one()
                profile_count = session.execute(select(func.count()).select_from(SqlCharacterProfile).where(SqlCharacterProfile.book_id == book.id)).scalar_one()
                stable_count = session.execute(select(func.count()).select_from(SqlStableCharacterState).where(SqlStableCharacterState.book_id == book.id)).scalar_one()
                timeline_count = session.execute(select(func.count()).select_from(SqlTimelineRow).where(SqlTimelineRow.book_id == book.id)).scalar_one()
                quality = book.scene_analysis_quality if isinstance(book.scene_analysis_quality, dict) else {}
                rows.append({
                    "path": f"db://book/{book.id}",
                    "name": book.title.replace(".contract.json", ""),
                    "mtime": book.updated_at.timestamp() if getattr(book, "updated_at", None) else 0,
                    "size_mb": 0.0,
                    "run_status": book.run_status or "unknown",
                    "identity_provider": book.identity_provider or "n/a",
                    "scenes": int(scene_count or 0),
                    "successful_scenes": quality.get("successful_scenes"),
                    "failed_scenes": quality.get("failed_scenes"),
                    "entity_registry": int(entity_count or 0),
                    "timeline": int(timeline_count or 0),
                    "event_ledger": int(event_count or 0),
                    "character_profiles": int(profile_count or 0),
                    "stable_character_states": int(stable_count or 0),
                    "story_index_docs": 0,
                    "load_deferred": False,
                })
            return rows

    return _safe_db([], "_db_contract_summaries", _query)


def run_summary(run_dir: Path) -> dict[str, Any]:
    contracts_dir = run_dir / "contracts"
    contracts = [contract_summary(path) for path in contracts_dir.glob("*.contract.json")] if contracts_dir.exists() else []
    status_payload = load_json(run_dir / "status.json")
    latest_status_payload = load_json(run_dir.parent / "latest_status.json")
    statuses = [item for item in [status_payload, latest_status_payload] if isinstance(item, dict)]
    run_status = ""
    if isinstance(status_payload, dict):
        run_status = str(status_payload.get("status") or "").strip().lower()
    if not run_status and isinstance(latest_status_payload, dict):
        run_status = str(latest_status_payload.get("status") or "").strip().lower()
    status_reason = ""
    status_source = "run_status"
    latest_worker_pid = (status_payload or {}).get("worker_pid") if isinstance(status_payload, dict) else None
    latest_update_age = _status_update_age_seconds(status_payload if isinstance(status_payload, dict) else latest_status_payload)
    worker_stale = (
        isinstance(status_payload, dict)
        and run_status == "running"
        and latest_worker_pid not in (None, "", 0, "0")
        and not _pid_is_running(latest_worker_pid)
        and latest_update_age is not None
        and latest_update_age > 30
    )
    latest_run_dir = ""
    if isinstance(latest_status_payload, dict):
        latest_run_dir = str(latest_status_payload.get("run_dir") or "").strip().replace("\\", "/").lower()
    this_run_dir = str(rel(run_dir)).replace("\\", "/").lower()
    active_books = []
    if isinstance(status_payload, dict):
        active_books = status_payload.get("books") or []
    if not contracts and active_books:
        contracts = [
            {
                "path": str(book.get("contract_path") or ""),
                "name": str(book.get("title") or ""),
                "mtime": run_dir.stat().st_mtime,
                "size_mb": 0.0,
                "run_status": str(book.get("status") or "unknown"),
                "identity_provider": str(book.get("identity_provider") or "n/a"),
                "scenes": int(book.get("total_scenes") or book.get("scenes_processed") or 0),
                "successful_scenes": int(book.get("successful_scenes") or 0) if book.get("successful_scenes") is not None else None,
                "failed_scenes": int(book.get("failed_scenes") or 0) if book.get("failed_scenes") is not None else None,
                "entity_registry": int(book.get("entity_registry") or 0) if book.get("entity_registry") is not None else 0,
                "timeline": int(book.get("timeline") or 0) if book.get("timeline") is not None else 0,
                "event_ledger": int(book.get("event_ledger") or 0) if book.get("event_ledger") is not None else 0,
                "character_profiles": int(book.get("character_profiles") or 0) if book.get("character_profiles") is not None else 0,
                "stable_character_states": int(book.get("stable_character_states") or 0) if book.get("stable_character_states") is not None else 0,
                "story_index_docs": int(book.get("story_index_docs") or 0) if book.get("story_index_docs") is not None else 0,
            }
            for book in active_books if isinstance(book, dict)
        ]
    active_book = next(
        (
            book for book in active_books
            if isinstance(book, dict) and str(book.get("status") or "").strip().lower() == "running"
        ),
        None,
    )
    active_scene_total = 0
    if active_books:
        for book in active_books:
            if not isinstance(book, dict):
                continue
            active_scene_total += int(book.get("scenes_processed") or book.get("total_scenes") or 0)
    failed_books = sum(1 for row in contracts if str(row.get("run_status")).lower() in {"failed", "partial", "paused"})
    status_value = "failed" if failed_books else (run_status or ("completed" if contracts else "unknown"))
    if worker_stale:
        status_value = "failed"
        status_reason = _humanize_status_reason("stale_encode_worker_process")
        status_source = "stale_worker_guard"
    elif status_value == "failed" and not status_reason:
        status_reason = _humanize_status_reason(
            str((status_payload or {}).get("error") or (latest_status_payload or {}).get("error") or "").strip()
        )
    if status_value == "running" and latest_run_dir and latest_run_dir != this_run_dir:
        status_value = "superseded"
        status_reason = "a newer run for this series is now the latest active status"
        status_source = "latest_status_pointer"
    if worker_stale and active_books:
        for book in active_books:
            if not isinstance(book, dict):
                continue
            if str(book.get("status") or "").strip().lower() == "running":
                book["status"] = "failed"
                book["error"] = status_reason
        for row in contracts:
            if not isinstance(row, dict):
                continue
            if str(row.get("run_status") or "").strip().lower() == "running":
                row["run_status"] = "failed"
    books_count = len(contracts) if contracts else len(active_books)
    contracts_count = len(contracts)
    total_scenes = sum(int(row.get("scenes") or 0) for row in contracts if isinstance(row.get("scenes"), int))
    if not total_scenes and active_scene_total:
        total_scenes = active_scene_total
    progress = None
    if active_book:
        scenes_processed = int(active_book.get("scenes_processed") or 0)
        total_book_scenes = int(active_book.get("total_scenes") or 0)
        phase = str(active_book.get("phase") or "running")
        label = str((active_book.get("last_progress") or {}).get("status") or f"{active_book.get('title') or 'Book'} · {phase}")
        progress = {
            "stage": "encode",
            "current": scenes_processed,
            "total": total_book_scenes,
            "label": label,
            "status": status_value or "running",
            "details": {
                "book_title": active_book.get("title") or "",
                "book_phase": phase,
                "checkpoint_path": active_book.get("checkpoint_path") or "",
                "status_reason": status_reason,
                "status_source": status_source,
                "status_update_age_seconds": latest_update_age,
            },
        }
    log_tail = tail_lines(run_dir / "encode.log", limit=120) if status_value == "running" else []
    return {
        "path": rel(run_dir),
        "series_id": run_dir.parent.name,
        "run_id": run_dir.name,
        "mtime": run_dir.stat().st_mtime,
        "status": status_value,
        "status_reason": status_reason,
        "status_source": status_source,
        "books": books_count,
        "contracts": contracts_count,
        "failed_books": failed_books,
        "total_scenes": total_scenes,
        "book_rows": contracts if contracts else active_books,
        "status_payload_count": len(statuses),
        "worker_pid": latest_worker_pid,
        "status_update_age_seconds": latest_update_age,
        "progress": progress,
        "log_tail": log_tail,
        "command": ((status_payload or {}).get("plan") or {}).get("mode") if isinstance(status_payload, dict) else "",
    }


def is_real_run_dir(path: Path) -> bool:
    return (
        path.is_dir()
        and len(path.name) >= 4
        and path.name[:4].isdigit()
        and (path / "status.json").exists()
    )


def scan_artifacts() -> dict[str, Any]:
    now = time.monotonic()
    cached_payload = SCAN_CACHE.get("payload")
    if cached_payload and (now - float(SCAN_CACHE.get("created_at") or 0.0)) < SCAN_CACHE_TTL_SECONDS:
        return cached_payload
    OUTPUTS_DIR.mkdir(exist_ok=True)
    contracts = _db_contract_summaries(limit=200)
    runs = _safe_db([], "get_pipeline_runs", lambda: SQLITE_STORE.get_pipeline_runs(limit=100))
    runs = [row for row in runs if not str(row.get("path") or "").startswith("db://job/")]
    if not runs:
        job_runs = []
        for job in list_jobs():
            if str(job.get("type") or "").strip().lower() != "encode-pipeline":
                continue
            job_runs.append(_job_to_run_summary(job))
        runs = job_runs[:100]
    reports: list[dict[str, Any]] = []
    visual_states: list[dict[str, Any]] = []
    identities: list[dict[str, Any]] = []
    identity_db = _safe_db([], "db_identity_summaries", db_identity_summaries)
    db_counts = database_summary()
    payload = {
        "contracts": contracts,
        "runs": runs,
        "reports": reports,
        "visual_states": visual_states,
        "identities": identities,
        "identity_db": identity_db,
        "database": db_counts,
        "counts": {
            "contracts": len(contracts),
            "runs": len(runs),
            "reports": len(reports),
            "visual_states": int(db_counts.get("generated_images") or 0),
            "identities": len(identities),
            "identity_db": len(identity_db),
            "total_scenes": sum(int(row.get("scenes") or 0) for row in contracts if isinstance(row.get("scenes"), int)),
        },
    }
    SCAN_CACHE["created_at"] = now
    SCAN_CACHE["payload"] = payload
    return payload


def database_summary() -> dict[str, Any]:
    from sqlalchemy import func, select
    from sql_store.models import Book, Entity, GeneratedImage, IdentityCharacter, IdentitySeries, Scene, VisualPrompt

    def _query() -> dict[str, Any]:
        with SQLITE_STORE.session_factory() as session:
            return {
                "books": session.execute(select(func.count()).select_from(Book)).scalar_one(),
                "scenes": session.execute(select(func.count()).select_from(Scene)).scalar_one(),
                "entities": session.execute(select(func.count()).select_from(Entity)).scalar_one(),
                "visual_prompts": session.execute(select(func.count()).select_from(VisualPrompt)).scalar_one(),
                "generated_images": session.execute(select(func.count()).select_from(GeneratedImage)).scalar_one(),
                "identity_series": session.execute(select(func.count()).select_from(IdentitySeries)).scalar_one(),
                "identity_characters": session.execute(select(func.count()).select_from(IdentityCharacter)).scalar_one(),
            }

    return _safe_db(
        {
            "books": 0,
            "scenes": 0,
            "entities": 0,
            "visual_prompts": 0,
            "generated_images": 0,
            "identity_series": 0,
            "identity_characters": 0,
        },
        "database_summary",
        _query,
    )


def _provider_file(provider_name: str) -> Path:
    mapping = {
        "ollama": OLLAMA_ACCOUNTS_FILE,
        "codex": CODEX_ACCOUNTS_FILE,
        "general_compute": GENERAL_COMPUTE_ACCOUNTS_FILE,
    }
    return mapping[str(provider_name).strip().lower()]


def _masked_provider_payload(payload: dict[str, Any]) -> dict[str, Any]:
    masked = {"active_index": int(payload.get("active_index", 0) or 0), "accounts": []}
    for index, item in enumerate(payload.get("accounts") or []):
        if not isinstance(item, dict):
            continue
        masked["accounts"].append(
            {
                "index": int(item.get("index", index) or index),
                "label": str(item.get("label") or f"account-{index + 1}"),
                "email": str(item.get("email") or ""),
                "auth_mode": str(item.get("auth_mode") or ""),
                "account_id": str(item.get("account_id") or ""),
                "has_password": bool(item.get("password")),
                "has_api_key": bool(item.get("api_key")),
                "password": mask_secret(item.get("password") or ""),
                "api_key": mask_secret(item.get("api_key") or ""),
                "active": bool(item.get("active")),
            }
        )
    return masked


def _read_provider_config(provider_name: str, *, mask: bool = True) -> dict[str, Any]:
    provider_key = str(provider_name).strip().lower()
    stored = SQLITE_STORE.get_provider_config(provider_key)
    if not isinstance(stored, dict):
        stored = {"provider_name": provider_key, "active_index": 0, "accounts": []}
    return _masked_provider_payload(stored) if mask else stored


def _seed_provider_configs_from_local_files() -> None:
    for provider_key in ("ollama", "general_compute", "codex"):
        existing = SQLITE_STORE.get_provider_config(provider_key)
        if isinstance(existing, dict) and (existing.get("accounts") or []):
            continue
        raw = load_json(_provider_file(provider_key))
        if not isinstance(raw, dict):
            continue
        payload = {"provider_name": provider_key, "active_index": int(raw.get("active_index", 0) or 0), "accounts": []}
        for index, item in enumerate(raw.get("accounts") or []):
            if not isinstance(item, dict):
                continue
            payload["accounts"].append(
                {
                    "index": index,
                    "label": str(item.get("label") or f"account-{index + 1}"),
                    "email": str(item.get("email") or ""),
                    "auth_mode": str(item.get("auth_mode") or ""),
                    "account_id": str(item.get("account_id") or ""),
                    "password": str(item.get("password") or ""),
                    "api_key": str(item.get("api_key") or ""),
                    "active": index == int(raw.get("active_index", 0) or 0),
                }
            )
        SQLITE_STORE.upsert_provider_config(provider_key, payload)


def _persist_provider_file(provider_name: str, payload: dict[str, Any]) -> None:
    return


def _merge_provider_payload(provider_name: str, incoming_accounts: list[ProviderAccount], active_index: int) -> dict[str, Any]:
    existing = _read_provider_config(provider_name, mask=False) or {"active_index": 0, "accounts": []}
    existing_by_label = {str(item.get("label") or ""): item for item in existing.get("accounts") or []}
    accounts: list[dict[str, Any]] = []
    for index, account in enumerate(incoming_accounts):
        label = account.label.strip() or f"account-{index + 1}"
        previous = existing_by_label.get(label, {})
        merged = {
            "index": index,
            "label": label,
            "email": account.email or str(previous.get("email") or ""),
            "password": account.password or str(previous.get("password") or ""),
            "api_key": account.api_key or str(previous.get("api_key") or ""),
            "auth_mode": str(previous.get("auth_mode") or ""),
            "account_id": str(previous.get("account_id") or ""),
            "metadata": dict(previous.get("metadata") or {}) if isinstance(previous.get("metadata"), dict) else {},
        }
        if provider_name == "codex" and not merged["api_key"] and CODEX_SESSION_STORE.active_session():
            merged["auth_mode"] = CODEX_SESSION_STORE.active_session().auth_mode or "codex_session"
            merged["account_id"] = CODEX_SESSION_STORE.active_session().account_id or ""
        if merged.get("api_key") or merged.get("password") or merged.get("auth_mode"):
            accounts.append(merged)
    bounded_index = max(0, min(int(active_index or 0), max(len(accounts) - 1, 0)))
    for idx, row in enumerate(accounts):
        row["active"] = idx == bounded_index
    return {"provider_name": provider_name, "active_index": bounded_index, "accounts": accounts}


def _save_provider_config(provider_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    SQLITE_STORE.upsert_provider_config(provider_name, payload)
    return _read_provider_config(provider_name, mask=True)


def read_ollama_accounts(mask: bool = True) -> dict[str, Any]:
    return _read_provider_config("ollama", mask=mask)


def merge_and_save_ollama_accounts(config: OllamaProviderConfig) -> dict[str, Any]:
    payload = _merge_provider_payload("ollama", config.accounts, config.active_index)
    return _save_provider_config("ollama", payload)


def read_codex_accounts(mask: bool = True) -> dict[str, Any]:
    payload = _read_provider_config("codex", mask=mask)
    if not payload.get("accounts") and mask:
        session = CODEX_SESSION_STORE.active_session()
        if session:
            payload["accounts"] = [{
                "index": 0,
                "label": "codex-session",
                "email": "",
                "auth_mode": session.auth_mode or "codex_session",
                "account_id": session.account_id or "",
                "has_password": False,
                "has_api_key": False,
                "password": "",
                "api_key": "",
                "active": True,
            }]
    return payload


def merge_and_save_codex_accounts(config: CodexProviderConfig) -> dict[str, Any]:
    payload = _merge_provider_payload("codex", config.accounts, config.active_index)
    return _save_provider_config("codex", payload)


def read_general_compute_accounts(mask: bool = True) -> dict[str, Any]:
    return _read_provider_config("general_compute", mask=mask)


def merge_and_save_general_compute_accounts(config: GeneralComputeProviderConfig) -> dict[str, Any]:
    payload = _merge_provider_payload("general_compute", config.accounts, config.active_index)
    return _save_provider_config("general_compute", payload)


def read_prompts() -> list[dict[str, Any]]:
    prompts = []
    for relative in PROMPT_FILES:
        path = ROOT / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        prompt_hits = [
            line.strip()
            for line in text.splitlines()
            if "prompt" in line.lower() or "you are" in line.lower() or "return only valid json" in line.lower()
        ][:30]
        prompts.append(
            {
                "path": relative,
                "name": path.name,
                "line_count": len(text.splitlines()),
                "prompt_hits": prompt_hits,
                "content": text,
            }
        )
    return prompts


def db_identity_summaries(limit: int = 50) -> list[dict[str, Any]]:
    with SQLITE_STORE.session_factory() as session:
        rows = session.execute(select(SqlIdentitySeries).order_by(SqlIdentitySeries.updated_at.desc())).scalars().all()
        summaries: list[dict[str, Any]] = []
        for row in rows[:limit]:
            book_count = session.execute(select(func.count()).select_from(SqlIdentityBook).where(SqlIdentityBook.identity_series_id == row.id)).scalar_one()
            summaries.append(
                {
                    "series_id": row.series_id,
                    "provider": row.provider or "booknlp_clean",
                    "source_path": row.source_path or "",
                    "character_count": int(row.character_count or 0),
                    "alias_count": int(row.alias_count or 0),
                    "reference_entity_count": int(row.reference_entity_count or 0),
                    "narrator_count": int(row.narrator_count or 0),
                    "book_count": int(book_count or 0),
                    "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else "",
                    "diagnostics": row.metadata_json or {},
                }
            )
        return summaries


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_probe_ollama_account(account: dict[str, Any]) -> dict[str, Any]:
    api_key = str(account.get("api_key") or "").strip() or None
    model_name = LLMClient(mode=LLMClient.MODE_GPT_OSS).resolved_model_name()
    try:
        probe = LLMClient.probe_ollama_mode_access(LLMClient.MODE_GPT_OSS, model_name, api_key=api_key)
    except Exception as exc:
        probe = {"status": "error", "detail": repr(exc)}
    quota_source = "provider_api_unavailable" if api_key else "local_runtime"
    return {
        "provider_name": "ollama",
        "label": str(account.get("label") or ""),
        "probe_status": str(probe.get("status") or "unknown"),
        "transport": "ollama_cloud" if api_key else "ollama_local",
        "resolved_model": str(probe.get("model") or model_name),
        "quota_source": quota_source,
        "credits_remaining": "unknown",
        "detail": str(probe.get("detail") or ("Live model probe succeeded." if probe.get("status") == "ok" else "")).strip(),
        "last_checked_at_utc": _utc_now_iso(),
        "payload": probe,
    }


def _safe_probe_general_compute_account(account: dict[str, Any]) -> dict[str, Any]:
    rotator = GeneralComputeAccountRotator()
    raw = load_json(GENERAL_COMPUTE_ACCOUNTS_FILE)
    raw_accounts = list((raw or {}).get("accounts") or []) if isinstance(raw, dict) else []
    raw_match = next((row for row in raw_accounts if str(row.get("label") or "") == str(account.get("label") or "")), {})
    api_key = str(account.get("api_key") or "").strip() or None
    model_name = LLMClient(mode=LLMClient.MODE_GENERAL_COMPUTE).resolved_model_name()
    try:
        probe = LLMClient.probe_general_compute_model_access(model_name, api_key=api_key)
    except Exception as exc:
        probe = {"status": "error", "detail": repr(exc)}
    limits = rotator._limits(raw_match) if isinstance(raw_match, dict) else {}
    usage = rotator._usage(raw_match) if isinstance(raw_match, dict) else {}
    return {
        "provider_name": "general_compute",
        "label": str(account.get("label") or ""),
        "probe_status": str(probe.get("status") or "unknown"),
        "transport": "general_compute_api",
        "resolved_model": str(probe.get("model") or model_name),
        "quota_source": "local_budget_tracking",
        "remaining_requests_minute": max(0, int(limits.get("requests_per_minute", 0)) - int(usage.get("minute_requests", 0))),
        "remaining_input_tokens_minute": max(0, int(limits.get("input_tokens_per_minute", 0)) - int(usage.get("minute_input_tokens", 0))),
        "remaining_output_tokens_minute": max(0, int(limits.get("output_tokens_per_minute", 0)) - int(usage.get("minute_output_tokens", 0))),
        "remaining_requests_day": max(0, int(limits.get("requests_per_day", 0)) - int(usage.get("day_requests", 0))),
        "remaining_tokens_day": max(0, int(limits.get("tokens_per_day", 0)) - int(usage.get("day_tokens", 0))),
        "credits_remaining": "unknown",
        "detail": str(probe.get("detail") or ("Live model probe succeeded." if probe.get("status") == "ok" else "")).strip(),
        "last_checked_at_utc": _utc_now_iso(),
        "payload": {**probe, "usage": usage, "limits": limits},
    }


def _safe_probe_codex_account(account: dict[str, Any]) -> dict[str, Any]:
    api_key = str(account.get("api_key") or "").strip() or None
    model_name = LLMClient(mode=LLMClient.MODE_CODEX).resolved_model_name()
    try:
        probe = LLMClient.probe_codex_model_access(model_name, api_key=api_key)
    except Exception as exc:
        probe = {"status": "error", "detail": repr(exc)}
    transport = str(probe.get("transport") or ("codex_session" if str(account.get("auth_mode") or "").strip() else "openai_api"))
    return {
        "provider_name": "codex",
        "label": str(account.get("label") or ""),
        "probe_status": str(probe.get("status") or "unknown"),
        "transport": transport,
        "resolved_model": str(probe.get("model") or model_name),
        "quota_source": "provider_api_unavailable",
        "credits_remaining": "unknown",
        "detail": str(probe.get("detail") or ("Live model probe succeeded." if probe.get("status") == "ok" else "")).strip(),
        "last_checked_at_utc": _utc_now_iso(),
        "payload": probe,
    }


def refresh_provider_statuses() -> dict[str, Any]:
    provider_payloads = {
        "ollama": _read_provider_config("ollama", mask=False),
        "general_compute": _read_provider_config("general_compute", mask=False),
        "codex": _read_provider_config("codex", mask=False),
    }
    results: dict[str, Any] = {}
    for provider_name, payload in provider_payloads.items():
        accounts = list(payload.get("accounts") or [])
        if provider_name == "codex" and not accounts and CODEX_SESSION_STORE.active_session():
            session = CODEX_SESSION_STORE.active_session()
            accounts = [{
                "label": "codex-session",
                "auth_mode": session.auth_mode or "codex_session",
                "account_id": session.account_id or "",
                "active": True,
            }]
        rows = []
        for account in accounts:
            if provider_name == "ollama":
                status = _safe_probe_ollama_account(account)
            elif provider_name == "general_compute":
                status = _safe_probe_general_compute_account(account)
            else:
                status = _safe_probe_codex_account(account)
            SQLITE_STORE.upsert_provider_status(provider_name, status["label"], status)
            rows.append(status)
        results[provider_name] = {
            "active_index": int(payload.get("active_index", 0) or 0),
            "accounts": _masked_provider_payload(payload).get("accounts", []) if accounts else [],
            "statuses": SQLITE_STORE.get_provider_statuses(provider_name),
            "refreshed_at_utc": _utc_now_iso(),
        }
    return results


def reduce_contract_row(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {"description": str(row)}
    allowed_keys = [
        "id",
        "title",
        "scene_id",
        "event_id",
        "character_id",
        "entity_id",
        "entity_name",
        "chapter_index",
        "scene_index",
        "scene_summary",
        "summary",
        "name",
        "display_name",
        "canonical_name",
        "event",
        "description",
        "type",
        "event_type",
        "relationship_type",
        "state",
        "evidence",
        "notes",
        "location",
        "event_location",
        "characters",
        "entities_present",
        "events",
        "state_changes",
        "relationship_changes",
        "visual_analysis",
        "persistent_visual_profile",
        "dynamic_visual_changes",
        "persistent_visual_prompt",
        "aliases",
        "roles",
        "affiliations",
        "entity_type",
        "first_seen",
        "mention_count",
        "descriptions",
        "state_changes",
        "event_links",
        "initial_physical_description",
        "visual_change_log",
        "entity_context",
        "analysis_quality_flags",
        "core_description",
        "traits",
        "personality",
        "goals",
        "fears",
        "loyalties",
        "abilities",
        "constraints",
        "important_history",
        "relationship_id",
        "source_character",
        "target_character",
        "relationship_type",
        "baseline_dynamic",
        "trust_level",
        "conflict_level",
        "romantic_signal",
        "shared_history",
        "change_log",
        "participants",
        "entities_involved",
        "reason",
        "outcome",
        "text",
        "positive_prompt",
        "image_edit_prompt",
        "prompt_type",
        "beat_title",
        "visual_bucket",
        "visual_bucket_label",
        "source_evidence",
        "confidence",
        "details",
        "generated_image_path",
        "render_status",
        "negative_prompt",
        "baseline_prompt",
        "baseline_prompt_type",
        "baseline_source_evidence",
        "baseline_confidence",
        "baseline_details",
        "change_prompts",
        "scene_prompts",
        "entity_world_state",
        "typed_attributes",
        "narrative_roles",
        "first_appearance_profile",
        "latest_world_state",
        "visual_profile",
        "world_state_profile",
        "relationship_refs",
        "state_history",
        "state_at_latest",
        "tool_runtime",
        "provider",
        "model",
        "resolved_model",
        "provider_account_alias",
        "rotation_used",
        "rotation_attempt_count",
        "fallback_used",
        "analysis_duration_seconds",
        "book_index",
        "final_status",
    ]
    reduced: dict[str, Any] = {}
    for key in allowed_keys:
        value = row.get(key)
        if value in (None, "", [], {}):
            continue
        reduced[key] = value
    return reduced


def _merge_character_sheet_renders(
    contract_path: Path,
    visual_sections: dict[str, list[Any]],
) -> dict[str, Any]:
    manifest_path = render_manifest_path_for_contract(contract_path)
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        return {}
    rows = (manifest.get("render_report") or {}).get("renders") or manifest.get("renders") or []
    render_map: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = str(row.get("entity_name") or "").strip().lower()
        if not key:
            continue
        render_map[key] = row
    enriched = []
    for row in visual_sections.get("initial_characters", []):
        if not isinstance(row, dict):
            enriched.append(row)
            continue
        match = render_map.get(str(row.get("entity_name") or "").strip().lower())
        if match:
            merged = dict(row)
            merged["generated_image_path"] = match.get("relative_output_path") or match.get("output_path") or ""
            merged["render_status"] = match.get("status") or "rendered"
            merged["negative_prompt"] = match.get("negative_prompt") or ""
            if match.get("positive_prompt"):
                merged["positive_prompt"] = match.get("positive_prompt")
            enriched.append(merged)
        else:
            enriched.append(row)
    visual_sections["initial_characters"] = enriched
    return {
        "manifest_path": rel(manifest_path),
        "render_count": len(rows),
        "rendered_count": sum(1 for row in rows if Path(str((row or {}).get("output_path") or "")).exists()),
    }


def _render_map_for_contract(contract_path: Path) -> dict[str, dict[str, Any]]:
    manifest_path = render_manifest_path_for_contract(contract_path)
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        return {}
    rows = (manifest.get("render_report") or {}).get("renders") or manifest.get("renders") or []
    render_map: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = str(row.get("entity_name") or "").strip().lower()
        if not key:
            continue
        render_map[key] = row
    return render_map


def _build_visual_inventory(
    *,
    entity_registry: list[dict[str, Any]],
    visual_sections: dict[str, list[Any]],
    render_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    baseline_map: dict[tuple[str, str], dict[str, Any]] = {}
    change_map: dict[tuple[str, str], list[dict[str, Any]]] = {}
    scene_map: dict[str, list[dict[str, Any]]] = {}

    for bucket in ["initial_characters", "objects_creatures", "locations"]:
        for row in visual_sections.get(bucket, []):
            if not isinstance(row, dict):
                continue
            name = str(row.get("entity_name") or "").strip()
            entity_type = str(row.get("entity_type") or "").strip().lower()
            if not name or not entity_type:
                continue
            baseline_map[(name.lower(), entity_type)] = row

    for row in visual_sections.get("character_changes", []):
        if not isinstance(row, dict):
            continue
        name = str(row.get("entity_name") or "").strip()
        entity_type = str(row.get("entity_type") or "character").strip().lower() or "character"
        if not name:
            continue
        change_map.setdefault((name.lower(), entity_type), []).append(row)

    for row in visual_sections.get("scene_compositions", []):
        if not isinstance(row, dict):
            continue
        entity_names = [
            str(item).strip()
            for item in (row.get("details") or {}).get("entities", row.get("entities") or [])
            if str(item).strip()
        ]
        for name in entity_names:
            scene_map.setdefault(name.lower(), []).append(row)

    inventory: list[dict[str, Any]] = []
    for entity in entity_registry:
        if not isinstance(entity, dict):
            continue
        name = str(entity.get("name") or "").strip()
        entity_type = str(entity.get("entity_type") or "").strip().lower()
        if not name or entity_type not in {"character", "location", "object", "creature"}:
            continue
        key = (name.lower(), entity_type)
        baseline = baseline_map.get(key) or {}
        changes = change_map.get(key, [])
        render = render_map.get(name.lower()) or {}
        inventory.append(
            {
                "name": name,
                "entity_type": entity_type,
                "mention_count": entity.get("mention_count"),
                "first_seen": entity.get("first_seen") or {},
                "entity_context": entity.get("entity_context") or "",
                "initial_physical_description": entity.get("initial_physical_description") or {},
                "first_appearance_profile": entity.get("first_appearance_profile") or {},
                "typed_attributes": entity.get("typed_attributes") or {},
                "analysis_quality_flags": entity.get("analysis_quality_flags") or [],
                "baseline_prompt": str(baseline.get("positive_prompt") or "").strip(),
                "baseline_prompt_type": str(baseline.get("prompt_type") or "").strip(),
                "baseline_source_evidence": str(baseline.get("source_evidence") or "").strip(),
                "baseline_confidence": str(baseline.get("confidence") or "").strip(),
                "baseline_details": baseline.get("details") or {},
                "change_prompts": [
                    {
                        "prompt": str(row.get("image_edit_prompt") or row.get("positive_prompt") or "").strip(),
                        "prompt_type": str(row.get("prompt_type") or "").strip(),
                        "source_evidence": str(row.get("source_evidence") or "").strip(),
                        "confidence": str(row.get("confidence") or "").strip(),
                        "book_index": row.get("book_index"),
                        "chapter_index": row.get("chapter_index"),
                        "scene_index": row.get("scene_index"),
                    }
                    for row in changes
                    if str(row.get("image_edit_prompt") or row.get("positive_prompt") or "").strip()
                ][:8],
                "scene_prompts": [
                    {
                        "beat_title": str(row.get("entity_name") or row.get("details", {}).get("beat_title") or "").strip(),
                        "prompt": str(row.get("positive_prompt") or "").strip(),
                        "source_evidence": str(row.get("source_evidence") or "").strip(),
                        "confidence": str(row.get("confidence") or "").strip(),
                        "book_index": row.get("book_index"),
                        "chapter_index": row.get("chapter_index"),
                        "scene_index": row.get("scene_index"),
                    }
                    for row in scene_map.get(name.lower(), [])
                    if str(row.get("positive_prompt") or "").strip()
                ][:6],
                "generated_image_path": str(render.get("relative_output_path") or render.get("output_path") or "").strip(),
                "negative_prompt": str(render.get("negative_prompt") or "").strip(),
                "render_status": str(render.get("status") or "").strip(),
            }
        )
    return inventory


def _db_book_by_contract_path(path: Path | str) -> SqlBook | None:
    raw = str(path)
    book_id = parse_db_book_ref(raw)
    with SQLITE_STORE.session_factory() as session:
        if book_id:
            return session.get(SqlBook, book_id)
        if raw.startswith("db://book/"):
            return None
        normalized = str(Path(raw).resolve())
        books = session.execute(select(SqlBook)).scalars().all()
        for book in books:
            source_path = str(book.source_path or "").strip()
            contract_path = str(book.contract_path or "").strip()
            candidates = [item for item in [contract_path, source_path] if item]
            for candidate in candidates:
                try:
                    if str(Path(candidate).resolve()) == normalized:
                        return book
                except OSError:
                    if candidate == normalized:
                        return book
    return None


def _db_contract_view(path: Path | str, *, limit: int = 200) -> dict[str, Any] | None:
    book_row = _db_book_by_contract_path(path)
    if book_row is None:
        return None
    with SQLITE_STORE.session_factory() as session:
        book = session.get(SqlBook, book_row.id)
        if book is None:
            return None
        scenes = session.execute(select(SqlScene).where(SqlScene.book_id == book.id).order_by(SqlScene.chapter_index.asc(), SqlScene.scene_index.asc())).scalars().all()
        events = session.execute(select(SqlEvent).where(SqlEvent.book_id == book.id).order_by(SqlEvent.chapter_index.asc(), SqlEvent.scene_index.asc())).scalars().all()
        entities = session.execute(select(SqlEntity).where(SqlEntity.book_id == book.id).order_by(SqlEntity.entity_type.asc(), SqlEntity.canonical_name.asc())).scalars().all()
        profiles = session.execute(select(SqlCharacterProfile).where(SqlCharacterProfile.book_id == book.id)).scalars().all()
        states = session.execute(select(SqlStableCharacterState).where(SqlStableCharacterState.book_id == book.id)).scalars().all()
        timeline = session.execute(select(SqlTimelineRow).where(SqlTimelineRow.book_id == book.id).order_by(SqlTimelineRow.row_index.asc())).scalars().all()
        prompts = session.execute(select(SqlVisualPrompt).where(SqlVisualPrompt.book_id == book.id)).scalars().all()
        images = session.execute(select(SqlGeneratedImage).where(SqlGeneratedImage.book_id == book.id)).scalars().all()

        prompt_map = {}
        for row in prompts:
            key = (str(row.entity_name or "").lower(), str(row.entity_type or "").lower())
            prompt_map.setdefault(key, row)
        image_map = {}
        for row in images:
            key = (str(row.entity_name or "").lower(), str(row.entity_type or "").lower())
            image_map.setdefault(key, row)

        entity_rows = []
        visual_inventory = []
        for entity in entities:
            key = (str(entity.canonical_name or "").lower(), str(entity.entity_type or "").lower())
            prompt = prompt_map.get(key)
            image = image_map.get(key)
            initial_physical_description = _clean_analysis_dict(entity.initial_physical_description or {})
            first_appearance_profile = _clean_analysis_dict(entity.first_appearance_profile or {})
            latest_world_state = _clean_analysis_dict(entity.latest_world_state or {})
            descriptions = _clean_analysis_list(entity.descriptions or [])
            state_changes = _clean_analysis_list(entity.state_changes or [])
            event_links = _clean_analysis_list(entity.event_links or [])
            narrative_roles = _clean_analysis_list(entity.narrative_roles or [])
            visual_change_log = _clean_analysis_list(entity.visual_change_log or [])
            analysis_quality_flags = _clean_analysis_list(entity.analysis_quality_flags or [])
            scene_visual_states = _clean_analysis_list(((entity.metadata_json or {}).get("scene_visual_states") or []))

            if initial_physical_description and "description" not in initial_physical_description:
                baseline_fields = initial_physical_description.get("baseline_visual_fields") or {}
                description = _summarize_analysis_fields(
                    baseline_fields,
                    [
                        "gender_presentation",
                        "species_or_race",
                        "apparent_age_group",
                        "height_impression",
                        "build",
                        "skin_tone_or_complexion",
                        "hair_color",
                        "hair_length_or_style",
                        "eye_color",
                        "facial_features",
                        "distinguishing_marks",
                        "location_class",
                        "indoor_outdoor",
                        "environment_type",
                        "region_or_domain",
                        "architecture_or_terrain_style",
                        "object_class",
                        "function",
                        "primary_material",
                        "species_kind",
                        "size_class",
                        "body_plan",
                        "head_features",
                    ],
                )
                if description:
                    initial_physical_description["description"] = description

            if first_appearance_profile and "baseline_description" not in first_appearance_profile:
                persistent_traits = first_appearance_profile.get("persistent_traits") or {}
                baseline_description = _summarize_analysis_fields(
                    persistent_traits,
                    [
                        "gender_presentation",
                        "species_or_race",
                        "apparent_age_group",
                        "height_impression",
                        "build",
                        "skin_tone_or_complexion",
                        "hair_color",
                        "hair_length_or_style",
                        "eye_color",
                        "facial_features",
                        "distinguishing_marks",
                        "default_clothing_style",
                        "default_accessories",
                        "default_footwear",
                        "signature_items",
                        "location_class",
                        "environment_type",
                        "architecture_or_terrain_style",
                        "object_class",
                        "function",
                        "primary_material",
                        "species_kind",
                        "size_class",
                        "body_plan",
                        "head_features",
                    ],
                )
                if baseline_description:
                    first_appearance_profile["baseline_description"] = baseline_description

            first_seen = {
                "book_index": entity.first_seen_book_index,
                "chapter_index": entity.first_seen_chapter_index,
                "scene_index": entity.first_seen_scene_index,
            }
            entity_row = {
                "name": entity.canonical_name,
                "entity_type": entity.entity_type,
                "mention_count": entity.mention_count,
                "first_seen": first_seen,
                "entity_context": _clean_analysis_text(entity.entity_context),
                "initial_physical_description": initial_physical_description,
                "first_appearance_profile": first_appearance_profile,
                "typed_attributes": _clean_analysis_dict(entity.typed_attributes or {}),
                "persistent_traits": (first_appearance_profile.get("persistent_traits") or latest_world_state.get("persistent_traits") or {}),
                "descriptions": descriptions,
                "state_changes": state_changes,
                "event_links": event_links,
                "narrative_roles": narrative_roles,
                "latest_world_state": latest_world_state,
                "visual_change_log": visual_change_log,
                "scene_visual_states": scene_visual_states,
                "analysis_quality_flags": analysis_quality_flags,
                "baseline_visual_prompt": entity.baseline_visual_prompt or "",
                "generated_image_path": entity.generated_image_path or "",
            }
            entity_rows.append(entity_row)
            visual_inventory.append({
                **entity_row,
                "baseline_prompt": entity.baseline_visual_prompt or str(getattr(prompt, "positive_prompt", "") or ""),
                "baseline_prompt_type": str(getattr(prompt, "prompt_type", "") or ""),
                "baseline_source_evidence": str(getattr(prompt, "source_evidence", "") or ""),
                "baseline_confidence": str(getattr(prompt, "confidence", "") or ""),
                "baseline_details": getattr(prompt, "details_json", None) or {},
                "change_prompts": [],
                "scene_prompts": [],
                "generated_image_path": entity.generated_image_path or str(getattr(image, "output_path", "") or ""),
                "negative_prompt": str(getattr(prompt, "negative_prompt", "") or ""),
                "render_status": str(getattr(image, "render_status", "") or ""),
            })

        scene_rows = [(scene.payload_json or {
            "book_index": scene.book_index,
            "chapter_index": scene.chapter_index,
            "scene_index": scene.scene_index,
            "scene_summary": scene.summary,
            "text": scene.text,
            "location": {"name": scene.location_name, "description": scene.location_description},
            "final_status": scene.final_status,
            "error_category": scene.error_category,
            "last_error": scene.last_error,
            "provider": scene.provider,
            "model": scene.model,
            "provider_account_alias": scene.provider_account_alias,
            "rotation_used": scene.rotation_used,
            "rotation_attempt_count": scene.rotation_attempt_count,
            "analysis_duration_seconds": scene.analysis_duration_seconds,
        }) for scene in scenes]

        event_rows = [event.payload_json or {
            "event_id": event.event_id_external,
            "event_type": event.event_type,
            "description": event.description,
            "reason": event.reason,
            "outcome": event.outcome,
            "entities_involved": event.entities_involved or [],
            "chapter_index": event.chapter_index,
            "scene_index": event.scene_index,
        } for event in events]
        timeline_rows = [row.payload_json or {} for row in timeline]
        profile_rows = [row.payload_json or {"character_name": row.character_name} for row in profiles]
        state_rows = [row.payload_json or {"character_name": row.character_name} for row in states]
        relationship_profiles = RelationshipProfileBuilder().build(scene_analyses=scene_rows)
        quality = book.scene_analysis_quality if isinstance(book.scene_analysis_quality, dict) else {}
        successful_scenes = quality.get("successful_scenes")
        failed_scenes = quality.get("failed_scenes")
        if successful_scenes is None and failed_scenes is None and scene_rows:
            successful_scenes = len(scene_rows)
            failed_scenes = 0
        summary = {
            "path": str(path) if is_db_book_ref(str(path)) else rel(Path(path)),
            "name": book.title.replace(".contract.json", ""),
            "mtime": book.updated_at.timestamp() if getattr(book, "updated_at", None) else 0,
            "size_mb": round((Path(path).stat().st_size / (1024 * 1024)), 2) if not is_db_book_ref(str(path)) and Path(path).exists() else 0.0,
            "run_status": book.run_status or "unknown",
            "identity_provider": book.identity_provider or "n/a",
            "scenes": len(scene_rows),
            "successful_scenes": successful_scenes,
            "failed_scenes": failed_scenes,
            "entity_registry": len(entity_rows),
            "timeline": len(timeline_rows),
            "event_ledger": len(event_rows),
            "character_profiles": len(profile_rows),
            "stable_character_states": len(state_rows),
            "story_index_docs": 0,
        }
        return {
            "path": str(path) if is_db_book_ref(str(path)) else rel(Path(path)),
            "summary": summary,
            "metadata": (book.metadata_json or {}).get("metadata") or {},
            "outputs": {
                "resolved_scene_analyses": [reduce_contract_row(row) for row in scene_rows[:limit]],
                "event_ledger": [reduce_contract_row(row) for row in event_rows[:limit]],
                "entity_registry": [reduce_contract_row(row) for row in entity_rows[: max(limit, 500)]],
                "timeline": [reduce_contract_row(row) for row in timeline_rows[:limit]],
                "character_profiles": [reduce_contract_row(row) for row in profile_rows[:limit]],
                "stable_character_states": [reduce_contract_row(row) for row in state_rows[:limit]],
                "relationship_profiles": [reduce_contract_row(row) for row in relationship_profiles[:limit]],
                "scene_world_state": [
                    reduce_contract_row({
                        "scene_id": f"b{row.get('book_index', '?')}_c{row.get('chapter_index', '?')}_s{row.get('scene_index', '?')}",
                        "book_index": row.get("book_index"),
                        "chapter_index": row.get("chapter_index"),
                        "scene_index": row.get("scene_index"),
                        "scene_summary": row.get("scene_summary") or "",
                        "location": row.get("location") or {},
                        "visual_analysis": row.get("visual_analysis") or {},
                        "entity_world_state": row.get("entity_world_state") or {},
                        "state_changes": row.get("state_changes") or [],
                        "relationship_changes": row.get("relationship_changes") or [],
                        "text": row.get("text") or "",
                    })
                    for row in scene_rows[:limit]
                ],
                "visual_prompt_sets": {
                    "initial_characters": [reduce_contract_row({
                        "entity_name": item["name"],
                        "entity_type": item["entity_type"],
                        "positive_prompt": item["baseline_prompt"],
                        "generated_image_path": item["generated_image_path"],
                        "prompt_type": item["baseline_prompt_type"],
                        "source_evidence": item["baseline_source_evidence"],
                        "confidence": item["baseline_confidence"],
                    }) for item in visual_inventory if item["entity_type"] == "character"][: max(limit, 500)],
                    "objects_creatures": [reduce_contract_row({
                        "entity_name": item["name"],
                        "entity_type": item["entity_type"],
                        "positive_prompt": item["baseline_prompt"],
                        "generated_image_path": item["generated_image_path"],
                        "prompt_type": item["baseline_prompt_type"],
                        "source_evidence": item["baseline_source_evidence"],
                        "confidence": item["baseline_confidence"],
                    }) for item in visual_inventory if item["entity_type"] in {"object", "creature"}][: max(limit, 500)],
                    "locations": [reduce_contract_row({
                        "entity_name": item["name"],
                        "entity_type": item["entity_type"],
                        "positive_prompt": item["baseline_prompt"],
                        "generated_image_path": item["generated_image_path"],
                        "prompt_type": item["baseline_prompt_type"],
                        "source_evidence": item["baseline_source_evidence"],
                        "confidence": item["baseline_confidence"],
                    }) for item in visual_inventory if item["entity_type"] == "location"][: max(limit, 500)],
                    "character_changes": [],
                    "scene_compositions": [],
                },
                "visual_inventory": [reduce_contract_row(row) for row in visual_inventory[: max(limit, 500)]],
                "visual_prompt_diagnostics": {},
            },
            "counts": {
                "resolved_scene_analyses": len(scene_rows),
                "event_ledger": len(event_rows),
                "entity_registry": len(entity_rows),
                "timeline": len(timeline_rows),
                "character_profiles": len(profile_rows),
                "stable_character_states": len(state_rows),
                "relationship_profiles": len(relationship_profiles),
                "scene_world_state": len(scene_rows),
                "visual_initial_characters": len([row for row in visual_inventory if row["entity_type"] == "character"]),
                "visual_objects_creatures": len([row for row in visual_inventory if row["entity_type"] in {"object", "creature"}]),
                "visual_locations": len([row for row in visual_inventory if row["entity_type"] == "location"]),
                "visual_character_changes": 0,
                "visual_scene_compositions": 0,
                "visual_inventory": len(visual_inventory),
            },
            "render_summary": {
                "manifest_path": rel(render_manifest_path_for_contract(path)) if render_manifest_path_for_contract(path).exists() else "",
                "render_count": len(images),
                "rendered_count": len([row for row in images if str(row.output_path or "").strip()]),
            },
            "truncated_at": limit,
        }


def contract_view(path: Path, *, limit: int = 200) -> dict[str, Any]:
    db_view = _db_contract_view(path, limit=limit)
    if db_view:
        return db_view
    payload = load_json(path) or {}
    outputs = payload.get("outputs") or {}
    scene_rows = outputs.get("resolved_scene_analyses") or outputs.get("scene_analyses") or []
    relationship_profiles = outputs.get("relationship_profiles") or RelationshipProfileBuilder().build(scene_analyses=scene_rows)
    sections = {
        "resolved_scene_analyses": scene_rows,
        "event_ledger": outputs.get("event_ledger") or [],
        "entity_registry": outputs.get("entity_registry") or [],
        "timeline": outputs.get("timeline") or [],
        "character_profiles": outputs.get("character_profiles") or [],
        "stable_character_states": outputs.get("stable_character_states") or [],
        "relationship_profiles": relationship_profiles,
        "scene_world_state": [
            {
                "scene_id": f"b{scene.get('book_index', '?')}_c{scene.get('chapter_index', '?')}_s{scene.get('scene_index', '?')}",
                "book_index": scene.get("book_index"),
                "chapter_index": scene.get("chapter_index"),
                "scene_index": scene.get("scene_index"),
                "scene_summary": scene.get("scene_summary") or "",
                "location": scene.get("location") or {},
                "visual_analysis": scene.get("visual_analysis") or {},
                "entity_world_state": scene.get("entity_world_state") or {},
                "state_changes": scene.get("state_changes") or [],
                "relationship_changes": scene.get("relationship_changes") or [],
                "text": scene.get("text") or "",
            }
            for scene in scene_rows
        ],
    }
    visual_prompt_sets = EncoderPersistenceService()._build_visual_prompt_sets(scene_rows) if scene_rows else (outputs.get("visual_prompt_sets") or {})
    visual_sections: dict[str, list[Any]] = {}
    if isinstance(visual_prompt_sets, dict):
        for key in ["initial_characters", "character_changes", "objects_creatures", "locations", "scene_compositions"]:
            visual_sections[key] = visual_prompt_sets.get(key) or []
    render_summary = _merge_character_sheet_renders(path, visual_sections)
    render_map = _render_map_for_contract(path)
    visual_inventory = _build_visual_inventory(
        entity_registry=sections["entity_registry"],
        visual_sections=visual_sections,
        render_map=render_map,
    )
    return {
        "path": rel(path),
        "summary": contract_summary(path, parse_heavy=True),
        "metadata": payload.get("metadata") or {},
        "outputs": {
            key: [reduce_contract_row(row) for row in values[:limit]]
            for key, values in sections.items()
        } | {
            "visual_prompt_sets": {
                key: [reduce_contract_row(row) for row in values[:limit]]
                for key, values in visual_sections.items()
            },
            "visual_inventory": [reduce_contract_row(row) for row in visual_inventory[: max(limit, 500)]],
            "visual_prompt_diagnostics": visual_prompt_sets.get("diagnostics") if isinstance(visual_prompt_sets, dict) else {},
        },
        "counts": {
            **{key: len(values) for key, values in sections.items()},
            **{f"visual_{key}": len(values) for key, values in visual_sections.items()},
            "visual_inventory": len(visual_inventory),
        },
        "render_summary": render_summary,
        "truncated_at": limit,
    }


class DashboardJobLogHandle:
    def __init__(self, job_id: str) -> None:
        self.job_id = str(job_id)

    def write(self, text: str) -> None:
        SQLITE_STORE.append_dashboard_job_log(self.job_id, text)

    def flush(self) -> None:
        return


def load_job(job_id: str) -> dict[str, Any]:
    payload = SQLITE_STORE.get_dashboard_job(job_id)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=404, detail="Job not found")
    payload["log_tail"] = SQLITE_STORE.get_dashboard_job_log_tail(job_id, limit=120)
    return _normalize_job_payload(payload, persist=True)


def save_job(payload: dict[str, Any]) -> None:
    normalized = {**payload, "log_path": ""}
    SQLITE_STORE.upsert_dashboard_job(normalized)
    _sync_pipeline_run_from_job_payload(normalized)


def list_jobs() -> list[dict[str, Any]]:
    ensure_dirs()
    rows = []
    db_rows = _safe_db([], "get_dashboard_jobs", lambda: SQLITE_STORE.get_dashboard_jobs(limit=100))
    for data in db_rows:
        try:
            rows.append(load_job(data.get("id") or ""))
        except HTTPException:
            continue
    return rows[:50]


def _sync_pipeline_run_from_job_payload(payload: dict[str, Any]) -> None:
    return


def _pid_is_running(pid: Any) -> bool:
    try:
        numeric = int(pid)
    except (TypeError, ValueError):
        return False
    if numeric <= 0:
        return False
    try:
        os.kill(numeric, 0)
        return True
    except OSError:
        return False
    except Exception:
        return False


def _status_update_age_seconds(status_payload: dict[str, Any] | None) -> float | None:
    if not isinstance(status_payload, dict):
        return None
    updated_at = str(status_payload.get("updated_at_utc") or "").strip()
    if not updated_at:
        return None
    try:
        updated_dt = datetime.fromisoformat(updated_at)
    except ValueError:
        return None
    return max(0.0, (datetime.now(timezone.utc) - updated_dt).total_seconds())


def _humanize_status_reason(code: str, *, fallback: str = "") -> str:
    value = str(code or "").strip()
    mapping = {
        "stale_encode_worker_process": "The encoder worker stopped unexpectedly and did not write a terminal status.",
        "stale_dashboard_job_process": "The dashboard wrapper process stopped after the underlying run had already ended.",
        "blocked_rate_limit": "The run was blocked by provider rate limits before it could complete.",
    }
    return mapping.get(value, fallback or value)


def _is_stale_status_reason(value: str) -> bool:
    text = str(value or "").strip().lower()
    return text in {
        _humanize_status_reason("stale_encode_worker_process").lower(),
        _humanize_status_reason("stale_dashboard_job_process").lower(),
    }


def _humanize_job_failure(payload: dict[str, Any]) -> str:
    error_text = str(payload.get("error") or "").strip()
    return_code = payload.get("return_code")
    if error_text:
        if "encode-store failed with exit code" in error_text.lower():
            return error_text.replace("RuntimeError(", "").replace(")", "").replace("'", "")
        return _humanize_status_reason(error_text, fallback=error_text)
    if return_code not in (None, "", 0, "0"):
        return f"Subprocess failed with exit code {return_code}."
    return ""


def _job_to_run_summary(payload: dict[str, Any]) -> dict[str, Any]:
    request = payload.get("request") if isinstance(payload.get("request"), dict) else {}
    books = request.get("books") if isinstance(request.get("books"), list) else []
    progress = payload.get("progress") if isinstance(payload.get("progress"), dict) else {}
    details = progress.get("details") if isinstance(progress.get("details"), dict) else {}
    status = str(payload.get("status") or "unknown").strip().lower() or "unknown"
    status_reason = str(payload.get("status_reason") or "").strip()
    if (not status_reason or _is_stale_status_reason(status_reason)) and status in {"failed", "blocked_rate_limit"}:
        status_reason = _humanize_job_failure(payload)
    book_title = ""
    if books:
        book_title = re.sub(r"^\d{8}T\d{6}_", "", Path(str(books[0])).name)
    elif details.get("book_title"):
        book_title = str(details.get("book_title") or "")
    scene_count = int(details.get("total_scenes") or details.get("scenes_processed") or 0)
    return {
        "path": f"db://job/{payload.get('id')}",
        "series_id": str(request.get("series_id") or payload.get("id") or "job"),
        "run_id": str(payload.get("id") or ""),
        "mtime": 0,
        "status": status,
        "status_reason": status_reason,
        "status_source": "dashboard_job",
        "books": len(books) or 1,
        "contracts": 0,
        "failed_books": 1 if status in {"failed", "partial", "paused"} else 0,
        "total_scenes": scene_count,
        "book_rows": [
            {
                "path": f"db://job/{payload.get('id')}/book/1",
                "name": book_title or "Book",
                "run_status": status,
                "scenes": scene_count,
                "identity_provider": str(request.get("identity_provider") or "n/a"),
            }
        ],
        "status_payload_count": 0,
        "worker_pid": payload.get("pid"),
        "status_update_age_seconds": None,
        "progress": progress if progress else None,
        "log_tail": payload.get("log_tail") or [],
        "command": str(payload.get("command") or ""),
    }


def _normalize_job_payload(payload: dict[str, Any], *, persist: bool = False) -> dict[str, Any]:
    def _current_status() -> str:
        return str(payload.get("status") or "").strip().lower()

    pid = payload.get("pid")
    request = payload.get("request") if isinstance(payload.get("request"), dict) else {}
    series_id = str(request.get("series_id") or "").strip()
    latest_run = _safe_db(
        None,
        "get_latest_pipeline_run",
        lambda: SQLITE_STORE.get_latest_pipeline_run(series_id=series_id),
    ) if series_id else None
    latest_worker_pid = (latest_run or {}).get("worker_pid") if isinstance(latest_run, dict) else None
    latest_run_status = str((latest_run or {}).get("status") or "").strip().lower()
    latest_update_age = None
    if isinstance(latest_run, dict):
        try:
            latest_update_age = max(0.0, time.time() - float(latest_run.get("mtime") or 0.0))
        except Exception:
            latest_update_age = None
    if isinstance(latest_run, dict):
        if latest_run_status in {"running", "blocked_rate_limit", "failed", "completed"}:
            progress = latest_run.get("progress") if isinstance(latest_run.get("progress"), dict) else None
            if progress:
                progress.setdefault("details", {})
                progress["details"]["status_updated_at_utc"] = str(latest_run.get("finished_at") or latest_run.get("started_at") or "")
                progress["details"]["status_update_age_seconds"] = latest_update_age
                payload["progress"] = progress
            if _current_status() in {"queued", "running", "failed"} and latest_run_status == "running":
                payload["status"] = "running"
                payload.pop("error", None)
                payload.pop("status_reason", None)
            elif _current_status() == "running" and latest_run_status in {"failed", "completed", "blocked_rate_limit"}:
                payload["status"] = latest_run_status
                if latest_run_status == "blocked_rate_limit":
                    payload["status_reason"] = _humanize_status_reason("blocked_rate_limit")
    if (
        _current_status() == "running"
        and isinstance(latest_run, dict)
        and latest_run_status == "running"
        and latest_worker_pid not in (None, "", 0, "0")
        and not _pid_is_running(latest_worker_pid)
        and latest_update_age is not None
        and latest_update_age > 30
    ):
        payload["status"] = "failed"
        payload["error"] = payload.get("error") or "stale_encode_worker_process"
        payload["status_reason"] = _humanize_status_reason("stale_encode_worker_process")
        progress = payload.get("progress") or {}
        if isinstance(progress, dict):
            progress["status"] = "failed"
            progress["label"] = progress.get("label") or "encoder worker stopped unexpectedly"
            progress.setdefault("details", {})
            progress["details"]["stale_worker_pid"] = latest_worker_pid
            progress["details"]["status_update_age_seconds"] = latest_update_age
            payload["progress"] = progress
        if persist:
            save_job(payload)
    if _current_status() == "running" and pid not in (None, "", 0, "0") and not _pid_is_running(pid):
        if latest_run_status != "running":
            payload["status"] = "failed"
            payload["error"] = payload.get("error") or "stale_dashboard_job_process"
            payload["status_reason"] = _humanize_status_reason("stale_dashboard_job_process")
            progress = payload.get("progress") or {}
            if isinstance(progress, dict):
                progress["status"] = "failed"
                progress["label"] = progress.get("label") or "stale job cleaned up"
                progress.setdefault("details", {})
                progress["details"]["stale_pid"] = pid
                payload["progress"] = progress
            if persist:
                save_job(payload)
    if _current_status() in {"failed", "blocked_rate_limit"}:
        derived_reason = _humanize_job_failure(payload)
        if derived_reason and (not payload.get("status_reason") or _is_stale_status_reason(str(payload.get("status_reason") or ""))):
            payload["status_reason"] = derived_reason
            progress = payload.get("progress") or {}
            if isinstance(progress, dict):
                progress.setdefault("details", {})
                progress["details"]["status_reason"] = derived_reason
                if str(progress.get("status") or "").strip().lower() != "failed":
                    progress["status"] = "failed"
                payload["progress"] = progress
            if persist:
                save_job(payload)
    if not payload.get("status_reason") and payload.get("error"):
        payload["status_reason"] = _humanize_status_reason(str(payload.get("error") or ""))
    return payload


def build_encode_command(request: EncodeRequest) -> list[str]:
    books = [book for book in request.books if str(book).strip()]
    if not books:
        raise HTTPException(status_code=400, detail="At least one book path is required.")
    command = [sys.executable, "-u", "saga_tools.py", "encode-store"]
    for book in books:
        command.extend(["--book", book])
    command.extend(
        [
            "--series-id",
            request.series_id,
            "--series-title",
            request.series_title,
            "--book-index-base",
            str(request.book_index_base),
            "--analysis-model",
            request.analysis_model,
            "--identity-model",
            request.identity_model,
            "--analysis-provider-mode",
            request.analysis_provider_mode,
            "--identity-provider",
            request.identity_provider,
            "--scene-failure-policy",
            request.scene_failure_policy,
            "--max-failed-scenes-absolute",
            str(request.max_failed_scenes_absolute),
            "--max-failed-scene-ratio",
            str(request.max_failed_scene_ratio),
            "--min-nonempty-scene-ratio",
            str(request.min_nonempty_scene_ratio),
            "--max-parallel-books",
            str(request.max_parallel_books),
        ]
    )
    if str(request.out or "").strip():
        command.extend(["--out", request.out])
    if request.export_contracts:
        command.append("--export-contracts")
    if request.max_chapters and request.max_chapters > 0:
        command.extend(["--max-chapters", str(request.max_chapters)])
    if request.series_identity_json:
        command.extend(["--series-identity-json", request.series_identity_json])
    if request.skip_ingest:
        command.append("--skip-ingest")
    if request.no_progress:
        command.append("--no-progress")
    return command


def encode_latest_status_path(series_id: str) -> Path:
    return OUTPUTS_DIR / "pipeline_runtime" / series_id / "latest_status.json"


def _job_progress_payload(
    *,
    stage: str,
    current: int | None = None,
    total: int | None = None,
    label: str = "",
    status: str = "",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "stage": stage,
        "label": label,
        "status": status or stage,
        "details": details or {},
    }
    if current is not None:
        payload["current"] = int(current)
    if total is not None:
        payload["total"] = int(total)
    return payload


def update_job_progress(job_id: str, **progress: Any) -> None:
    payload = load_job(job_id)
    payload["progress"] = _job_progress_payload(**progress)
    save_job(payload)


def append_job_log(log_handle, text: str) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    raw = str(text or "")
    if not raw:
        return
    chunks = raw.splitlines(keepends=True)
    if not chunks:
        return
    for chunk in chunks:
        if not chunk.strip():
            log_handle.write(chunk)
            continue
        stripped = chunk.rstrip("\r\n")
        newline = chunk[len(stripped):]
        if re.match(r"^\d{4}-\d{2}-\d{2}", stripped):
            log_handle.write(chunk)
        else:
            log_handle.write(f"{timestamp} | {stripped}{newline}")
    log_handle.flush()


def _format_log_fields(fields: dict[str, Any]) -> str:
    ordered = []
    for key, value in fields.items():
        if value in (None, ""):
            continue
        text = str(value).replace("\n", "\\n")
        if any(ch.isspace() for ch in text) or "|" in text or "=" in text:
            text = json.dumps(text, ensure_ascii=False)
        ordered.append(f"{key}={text}")
    return " ".join(ordered)


def append_stage_log(log_handle, stage: str, message: str, **fields: Any) -> None:
    payload = {
        "level": "INFO",
        "stage": stage,
        "event": message,
        **fields,
    }
    append_job_log(log_handle, _format_log_fields(payload) + "\n")


def append_progress_log(log_handle, stage: str, payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        return
    fields = {
        "status": payload.get("status"),
        "scene_position": payload.get("scene_position"),
        "total_scenes": payload.get("total_scenes"),
        "book_index": payload.get("book_index"),
        "chapter_index": payload.get("chapter_index"),
        "scene_index": payload.get("scene_index"),
        "elapsed_seconds": payload.get("elapsed_seconds"),
        "analysis_model": payload.get("analysis_model"),
        "identity_model": payload.get("identity_model"),
        "provider_mode": payload.get("provider_mode"),
    }
    append_stage_log(log_handle, stage, "progress update", **fields)


def derive_encode_progress(status_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(status_payload, dict):
        return None
    books = status_payload.get("books") or []
    summary = status_payload.get("summary") or {}
    total_books = len(books) or int(summary.get("total_requested") or 0)
    active_book = next((row for row in books if str(row.get("status") or "").lower() == "running"), None)
    if active_book:
        scenes_processed = int(active_book.get("scenes_processed") or 0)
        total_scenes = int(active_book.get("total_scenes") or 0)
        phase = str(active_book.get("phase") or "running")
        phase_labels = {
            "chapters": "loading chapters",
            "identity": "loading BookNLP identity",
            "scene": "analyzing scenes",
            "scene_wait": "scene still running",
            "artifacts": "building downstream artifacts",
            "causal_graph": "building causal graph",
            "scene_failure_policy": "book failed policy checks",
        }
        progress_status = str((active_book.get("last_progress") or {}).get("status") or "").strip()
        label = f"{active_book.get('title') or 'Book'} · {phase_labels.get(phase, phase)}"
        if total_scenes > 0:
            label += f" · scene {scenes_processed}/{total_scenes}"
        if progress_status and phase == "scene_wait":
            label = f"{active_book.get('title') or 'Book'} · {progress_status}"
        details = {
            "book_title": active_book.get("title") or "",
            "book_phase": phase,
            "completed_books": int(summary.get("completed") or 0),
            "failed_books": int(summary.get("failed") or 0),
            "total_books": total_books,
            "checkpoint_path": active_book.get("checkpoint_path") or "",
            "book_elapsed_seconds": active_book.get("elapsed_seconds"),
            "elapsed_seconds": (active_book.get("last_progress") or {}).get("elapsed_seconds"),
            "analysis_model": (active_book.get("last_progress") or {}).get("analysis_model"),
            "identity_model": (active_book.get("last_progress") or {}).get("identity_model"),
        }
        return _job_progress_payload(
            stage="encode",
            current=scenes_processed,
            total=total_scenes if total_scenes > 0 else total_books,
            label=label,
            status=str(status_payload.get("status") or "running"),
            details=details,
        )
    completed_books = int(summary.get("completed") or 0) + int(summary.get("failed") or 0) + int(summary.get("skipped") or 0)
    label = f"books complete {completed_books}/{total_books}" if total_books else str(status_payload.get("status") or "running")
    return _job_progress_payload(
        stage="encode",
        current=completed_books if total_books else None,
        total=total_books if total_books else None,
        label=label,
        status=str(status_payload.get("status") or "running"),
        details={
            "completed_books": int(summary.get("completed") or 0),
            "failed_books": int(summary.get("failed") or 0),
            "skipped_books": int(summary.get("skipped") or 0),
            "total_books": total_books,
        },
    )


def poll_encode_status(job_id: str, series_id: str, stop_event: threading.Event, log_handle=None) -> None:
    last_progress_signature = ""
    last_status_signature = ""
    while not stop_event.is_set():
        try:
            latest_run = _safe_db(
                None,
                "get_latest_pipeline_run",
                lambda: SQLITE_STORE.get_latest_pipeline_run(series_id=series_id),
            )
            if isinstance(latest_run, dict):
                progress = latest_run.get("progress") if isinstance(latest_run.get("progress"), dict) else None
                status_signature = json.dumps(
                    {
                        "status": latest_run.get("status"),
                        "status_reason": latest_run.get("status_reason"),
                        "mtime": latest_run.get("mtime"),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )
                payload = load_job(job_id)
                if progress:
                    payload["progress"] = progress
                if status_signature != last_status_signature:
                    last_status_signature = status_signature
                    payload["status"] = str(latest_run.get("status") or payload.get("status") or "running")
                    if latest_run.get("status_reason"):
                        payload["status_reason"] = str(latest_run.get("status_reason") or "")
                    save_job(payload)
                if progress and log_handle is not None:
                    signature = json.dumps(progress, ensure_ascii=False, sort_keys=True, default=str)
                    if signature != last_progress_signature:
                        last_progress_signature = signature
                        append_progress_log(log_handle, str(progress.get("stage") or "encode"), progress)
        except Exception:
            pass
        stop_event.wait(1.0)


def build_character_render_command(request: CharacterRenderRequest) -> list[str]:
    command = [sys.executable, "-u", "saga_tools.py", "render-character-sheets", "--book-ref", request.contract_path]
    if request.limit and request.limit > 0:
        command.extend(["--limit", str(request.limit)])
    if request.overwrite:
        command.append("--overwrite")
    return command


def resolve_identity_output_root(request: EncodeRequest) -> Path:
    configured = str(request.identity_output_root or "").strip()
    if configured:
        return (ROOT / configured).resolve() if not Path(configured).is_absolute() else Path(configured)
    return OUTPUTS_DIR / "identity_series" / slugify(request.series_id)


def resolve_series_identity_output_path(request: EncodeRequest, identity_root: Path) -> Path:
    return identity_root / f"{slugify(request.series_id)}_series_pipeline_identity.json"


def cleanup_identity_bundle_files(identity_root: Path, log_handle=None) -> None:
    try:
        if identity_root.exists():
            shutil.rmtree(identity_root, ignore_errors=True)
            if log_handle is not None:
                append_stage_log(log_handle, "identity_bundle", "removed temporary identity bundle files", output_root=identity_root)
    except Exception as exc:
        if log_handle is not None:
            append_stage_log(log_handle, "identity_bundle", "failed to remove temporary identity bundle files", error=repr(exc), output_root=identity_root)


def cleanup_legacy_series_artifacts(series_id: str, log_handle=None) -> None:
    targets = [
        OUTPUTS_DIR / "pipeline_runtime" / str(series_id),
        OUTPUTS_DIR / "contract_exports" / str(series_id),
    ]
    for target in targets:
        try:
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
                if log_handle is not None:
                    append_stage_log(log_handle, "cleanup", "removed legacy series artifact directory", path=target)
        except Exception as exc:
            if log_handle is not None:
                append_stage_log(log_handle, "cleanup", "failed to remove legacy series artifact directory", path=target, error=repr(exc))


def generate_identity_bundles_for_request(job_id: str, request: EncodeRequest, log_handle) -> Path:
    books = normalize_books(request.books, request.book_index_base)
    if not books:
        raise HTTPException(status_code=400, detail="At least one book path is required.")
    identity_root = resolve_identity_output_root(request)
    identity_root.mkdir(parents=True, exist_ok=True)
    append_stage_log(log_handle, "identity_bundle", "starting identity bundle generation", output_root=identity_root)
    summaries: list[dict[str, Any]] = []
    total = (len(books) * 3) + 1
    step = 0
    for idx, book in enumerate(books, start=1):
        title = book.get("title") or Path(book["path"]).name
        step += 1
        update_job_progress(
            job_id,
            stage="identity_bundle",
            current=step,
            total=total,
            label=f"{title} · preparing identity bundle",
            status="running",
            details={
                "book_index": book.get("book_index"),
                "output_root": str(identity_root),
                "substage": "prepare_book",
                "book_title": title,
                "book_position": idx,
                "book_total": len(books),
            },
        )
        append_stage_log(log_handle, "identity_bundle", "generating book identity bundle", book_title=title, book_position=f"{idx}/{len(books)}")
        step += 1
        update_job_progress(
            job_id,
            stage="identity_bundle",
            current=step,
            total=total,
            label=f"{title} · running BookNLP and cleanup adapter",
            status="running",
            details={
                "book_index": book.get("book_index"),
                "output_root": str(identity_root),
                "substage": "generate_bundle",
                "book_title": title,
                "book_position": idx,
                "book_total": len(books),
            },
        )
        summary = generate_book_identity_bundle(
            book=book,
            book_index=int(book["book_index"]),
            output_root=identity_root,
            reuse_book1_seed=False,
        )
        summaries.append(summary)
        step += 1
        update_job_progress(
            job_id,
            stage="identity_bundle",
            current=step,
            total=total,
            label=f"{title} · bundle ready",
            status="running",
            details={
                "book_index": book.get("book_index"),
                "output_root": str(identity_root),
                "substage": "book_complete",
                "book_title": title,
                "book_position": idx,
                "book_total": len(books),
                "character_count": summary.get("character_count", 0),
                "alias_count": summary.get("alias_count", 0),
                "reference_entity_count": summary.get("reference_entity_count", 0),
            },
        )
        append_stage_log(
            log_handle,
            "identity_bundle",
            "book identity bundle ready",
            book_title=title,
            characters=summary.get("character_count", 0),
            aliases=summary.get("alias_count", 0),
            references=summary.get("reference_entity_count", 0),
            pipeline=summary.get("pipeline_identity_path"),
        )
    series_identity_path = resolve_series_identity_output_path(request, identity_root)
    step += 1
    append_stage_log(log_handle, "identity_bundle", "building series identity map", output_path=series_identity_path)
    update_job_progress(
        job_id,
        stage="identity_bundle",
        current=step,
        total=total,
        label="building series identity map",
        status="running",
        details={
            "substage": "series_merge",
            "output_root": str(identity_root),
            "book_total": len(books),
        },
    )
    payload = build_series_pipeline_identity(book_summaries=summaries, output_json=series_identity_path)
    payload["series_id"] = request.series_id
    payload.setdefault("provider", "booknlp_clean")
    SQLITE_STORE.persist_identity_bundle(
        series_id=request.series_id,
        source_path=f"db://identity-series/{request.series_id}",
        series_payload=payload,
        book_summaries=summaries,
    )
    update_job_progress(
        job_id,
        stage="identity_bundle",
        current=step,
        total=total,
        label="series identity ready",
        status="completed",
        details={
            "series_identity_json": f"db://identity-series/{request.series_id}",
            "character_count": len(payload.get("characters") or []),
            "book_count": len(summaries),
            "substage": "complete",
        },
    )
    append_stage_log(
        log_handle,
        "identity_bundle",
        "series identity ready",
        characters=len(payload.get("characters") or []),
        books=len(summaries),
        db_ref=f"db://identity-series/{request.series_id}",
    )
    return series_identity_path


def format_duration_seconds(seconds: float | int | None) -> str:
    if seconds is None:
        return "0s"
    total = max(0, int(round(float(seconds))))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def generate_identity_bundles_for_request_v2(job_id: str, request: EncodeRequest, log_handle) -> Path:
    books = normalize_books(request.books, request.book_index_base)
    if not books:
        raise HTTPException(status_code=400, detail="At least one book path is required.")
    identity_root = resolve_identity_output_root(request)
    identity_root.mkdir(parents=True, exist_ok=True)
    append_stage_log(log_handle, "identity_bundle", "starting identity bundle generation", output_root=identity_root)
    summaries: list[dict[str, Any]] = []
    total = (len(books) * 8) + 1
    stage_order = {
        "extract_chapters_start": 2,
        "extract_chapters_complete": 3,
        "write_booknlp_input_start": 4,
        "write_booknlp_input_complete": 4,
        "booknlp_process_start": 5,
        "booknlp_process_heartbeat": 5,
        "booknlp_process_complete": 6,
        "adapt_raw_identity_start": 6,
        "adapt_raw_identity_complete": 6,
        "cleanup_identity_start": 7,
        "cleanup_identity_complete": 7,
        "build_pipeline_identity_start": 8,
        "build_pipeline_identity_complete": 8,
        "reuse_existing_bundle": 8,
        "reuse_seed_bundle": 8,
    }
    stage_labels = {
        "extract_chapters_start": "extracting chapter text",
        "extract_chapters_complete": "chapter text ready",
        "write_booknlp_input_start": "writing BookNLP input",
        "write_booknlp_input_complete": "BookNLP input ready",
        "booknlp_process_start": "running BookNLP small",
        "booknlp_process_heartbeat": "BookNLP small running",
        "booknlp_process_complete": "BookNLP small complete",
        "adapt_raw_identity_start": "adapting raw BookNLP output",
        "adapt_raw_identity_complete": "raw identity adapted",
        "cleanup_identity_start": "cleaning identity bundle",
        "cleanup_identity_complete": "identity cleanup complete",
        "build_pipeline_identity_start": "building pipeline identity",
        "build_pipeline_identity_complete": "pipeline identity ready",
        "reuse_existing_bundle": "reusing existing identity bundle",
        "reuse_seed_bundle": "reusing seeded identity bundle",
    }
    step = 0
    for idx, book in enumerate(books, start=1):
        title = book.get("title") or Path(book["path"]).name
        step = ((idx - 1) * 8) + 1
        update_job_progress(
            job_id,
            stage="identity_bundle",
            current=step,
            total=total,
            label=f"{title} · preparing identity bundle",
            status="running",
            details={
                "book_index": book.get("book_index"),
                "output_root": str(identity_root),
                "substage": "prepare_book",
                "book_title": title,
                "book_position": idx,
                "book_total": len(books),
            },
        )
        append_stage_log(log_handle, "identity_bundle", "generating book identity bundle", book_title=title, book_position=f"{idx}/{len(books)}")

        def _bundle_progress_callback(bundle_stage: str, bundle_payload: dict[str, Any]) -> None:
            relative_step = stage_order.get(bundle_stage, 2)
            current_value = ((idx - 1) * 8) + relative_step
            elapsed = bundle_payload.get("elapsed_seconds")
            label = stage_labels.get(bundle_stage, bundle_stage.replace("_", " "))
            if bundle_stage == "booknlp_process_heartbeat" and elapsed is not None:
                label = f"{label} ({format_duration_seconds(elapsed)} elapsed)"
            update_job_progress(
                job_id,
                stage="identity_bundle",
                current=current_value,
                total=total,
                label=f"{title} · {label}",
                status="running",
                details={
                    "book_index": book.get("book_index"),
                    "output_root": str(identity_root),
                    "substage": bundle_stage,
                    "book_title": title,
                    "book_position": idx,
                    "book_total": len(books),
                    "elapsed_seconds": elapsed,
                    "character_count": bundle_payload.get("character_count"),
                    "alias_count": bundle_payload.get("alias_count"),
                    "reference_entity_count": bundle_payload.get("reference_entity_count"),
                },
            )
            append_stage_log(
                log_handle,
                "identity_bundle",
                "bundle substage",
                book_title=title,
                book_position=f"{idx}/{len(books)}",
                substage=bundle_stage,
                elapsed_seconds=elapsed,
            )

        summary = generate_book_identity_bundle(
            book=book,
            book_index=int(book["book_index"]),
            output_root=identity_root,
            reuse_book1_seed=False,
            progress_callback=_bundle_progress_callback,
        )
        summaries.append(summary)
        step = idx * 8
        update_job_progress(
            job_id,
            stage="identity_bundle",
            current=step,
            total=total,
            label=f"{title} · bundle ready",
            status="running",
            details={
                "book_index": book.get("book_index"),
                "output_root": str(identity_root),
                "substage": "book_complete",
                "book_title": title,
                "book_position": idx,
                "book_total": len(books),
                "character_count": summary.get("character_count", 0),
                "alias_count": summary.get("alias_count", 0),
                "reference_entity_count": summary.get("reference_entity_count", 0),
            },
        )
        append_stage_log(
            log_handle,
            "identity_bundle",
            "book identity bundle ready",
            book_title=title,
            characters=summary.get("character_count", 0),
            aliases=summary.get("alias_count", 0),
            references=summary.get("reference_entity_count", 0),
            pipeline=summary.get("pipeline_identity_path"),
        )
    step += 1
    series_identity_path = resolve_series_identity_output_path(request, identity_root)
    append_stage_log(log_handle, "identity_bundle", "building series identity map", output_path=series_identity_path)
    update_job_progress(
        job_id,
        stage="identity_bundle",
        current=step,
        total=total,
        label="building series identity map",
        status="running",
        details={
            "substage": "series_merge",
            "output_root": str(identity_root),
            "book_total": len(books),
        },
    )
    payload = build_series_pipeline_identity(book_summaries=summaries, output_json=series_identity_path)
    payload["series_id"] = request.series_id
    payload.setdefault("provider", "booknlp_clean")
    SQLITE_STORE.persist_identity_bundle(
        series_id=request.series_id,
        source_path=f"db://identity-series/{request.series_id}",
        series_payload=payload,
        book_summaries=summaries,
    )
    update_job_progress(
        job_id,
        stage="identity_bundle",
        current=step,
        total=total,
        label="series identity ready",
        status="completed",
        details={
            "series_identity_json": f"db://identity-series/{request.series_id}",
            "character_count": len(payload.get("characters") or []),
            "book_count": len(summaries),
            "substage": "complete",
        },
    )
    append_stage_log(
        log_handle,
        "identity_bundle",
        "series identity ready",
        characters=len(payload.get("characters") or []),
        books=len(summaries),
        db_ref=f"db://identity-series/{request.series_id}",
    )
    return series_identity_path


def run_subprocess_job(
    job_id: str,
    command: list[str],
    log_handle,
    *,
    progress_pattern: re.Pattern[str] | None = None,
    progress_transform=None,
    status_monitor=None,
) -> int:
    stop_event = threading.Event()
    monitor_thread = None
    started_at = time.perf_counter()
    try:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        payload = load_job(job_id)
        payload["pid"] = process.pid
        save_job(payload)
        append_stage_log(log_handle, "subprocess", "started", pid=process.pid, command=subprocess.list2cmdline(command))
        if callable(status_monitor):
            monitor_thread = threading.Thread(target=status_monitor, args=(stop_event,), daemon=True)
            monitor_thread.start()
        assert process.stdout is not None
        for line in process.stdout:
            append_job_log(log_handle, line)
            if progress_pattern:
                match = progress_pattern.search(line.strip())
                if match:
                    payload = load_job(job_id)
                    payload["progress"] = progress_transform(match, payload.get("progress") or {}) if callable(progress_transform) else {
                        "current": int(match.group("current")),
                        "total": int(match.group("total")),
                        "label": match.group("label"),
                        "status": match.group("status"),
                    }
                    save_job(payload)
        code = process.wait()
        append_stage_log(log_handle, "subprocess", "finished", exit_code=code, elapsed_seconds=round(time.perf_counter() - started_at, 2))
        return code
    finally:
        stop_event.set()
        if monitor_thread:
            monitor_thread.join(timeout=2.0)


def render_visuals_for_run(job_id: str, contract_paths: list[str], log_handle) -> None:
    total = len(contract_paths)
    progress_pattern = re.compile(r"RENDER_PROGRESS\|(?P<current>\d+)\|(?P<total>\d+)\|(?P<label>.*?)\|(?P<status>[a-z_]+)")
    for index, contract_path in enumerate(contract_paths, start=1):
        contract_name = Path(contract_path).name
        update_job_progress(
            job_id,
            stage="visual_render",
            current=index - 1,
            total=total,
            label=f"queueing {contract_name}",
            status="running",
            details={"contract_path": contract_path},
        )
        append_job_log(log_handle, f"\n# Visual render {index}/{total}: {contract_path}\n")
        command = build_character_render_command(CharacterRenderRequest(contract_path=contract_path, overwrite=True))

        def _transform(match, existing):
            entity_name = str(match.group("label") or "").strip()
            render_status = str(match.group("status") or "").strip()
            return _job_progress_payload(
                stage="visual_render",
                current=int(match.group("current")),
                total=int(match.group("total")),
                label=f"{contract_name} · {entity_name} · {render_status.replace('_', ' ')}",
                status=render_status,
                details={
                    "contract_path": contract_path,
                    "contract_name": contract_name,
                    "contract_index": index,
                    "contract_total": total,
                    "current_entity": entity_name,
                    "render_status": render_status,
                    "render_current": int(match.group("current")),
                    "render_total": int(match.group("total")),
                },
            )

        code = run_subprocess_job(job_id, command, log_handle, progress_pattern=progress_pattern, progress_transform=_transform)
        if code != 0:
            raise RuntimeError(f"Character-sheet render failed for {contract_name} with exit code {code}.")
    update_job_progress(job_id, stage="visual_render", current=total, total=total, label="visual renders complete", status="completed")


def run_encode_pipeline_job(job_id: str, request: EncodeRequest) -> None:
    payload = load_job(job_id)
    payload.update({"status": "running", "started_at": utc_now(), "pid": None})
    save_job(payload)
    code: int | None = None
    log = DashboardJobLogHandle(job_id)
    append_stage_log(log, "pipeline", "dashboard encode pipeline started", created_at=payload.get("created_at"), job_id=job_id)
    try:
        effective_request = request.model_copy(deep=True)
        cleanup_legacy_series_artifacts(effective_request.series_id, log)
        if effective_request.generate_identity_bundles:
            series_identity_path = generate_identity_bundles_for_request_v2(job_id, effective_request, log)
            effective_request.series_identity_json = f"db://identity-series/{effective_request.series_id}"
            append_stage_log(
                log,
                "identity_bundle",
                "identity bundle registered in sqlite",
                series_id=effective_request.series_id,
                db_ref=effective_request.series_identity_json,
                export_json=rel(series_identity_path),
            )
        command = build_encode_command(effective_request)
        append_stage_log(
            log,
            "pipeline",
            "launching encode-store",
            series_id=effective_request.series_id,
            books=len(normalize_books(effective_request.books, effective_request.book_index_base)),
            analysis_model=effective_request.analysis_model,
            identity_model=effective_request.identity_model,
            provider_mode=effective_request.analysis_provider_mode,
            identity_provider=effective_request.identity_provider,
            identity_ref=effective_request.series_identity_json,
            generate_visuals=effective_request.generate_visuals,
            skip_ingest=effective_request.skip_ingest,
        )
        append_job_log(log, "$ " + subprocess.list2cmdline(command) + "\n\n")
        update_job_progress(
            job_id,
            stage="encode",
            current=0,
            total=len(normalize_books(effective_request.books, effective_request.book_index_base)),
            label="starting encoder",
            status="running",
            details={"series_identity_json": effective_request.series_identity_json},
        )
        code = run_subprocess_job(
            job_id,
            command,
            log,
            status_monitor=lambda stop_event: poll_encode_status(job_id, effective_request.series_id, stop_event, log),
        )
        if code != 0:
            payload = load_job(job_id)
            payload.update({"return_code": code})
            save_job(payload)
            append_stage_log(log, "pipeline", "encode-store exited with failure", exit_code=code, series_id=effective_request.series_id)
            raise RuntimeError(f"encode-store failed with exit code {code}.")
        requested_indices = {
            int(row.get("book_index"))
            for row in normalize_books(effective_request.books, effective_request.book_index_base)
            if row.get("book_index") is not None
        }
        series_books = _safe_db([], "get_series_books", lambda: SQLITE_STORE.get_series_books(effective_request.series_id))
        series_books = [
            row for row in series_books
            if not requested_indices or int(row.get("book_index") or 0) in requested_indices
        ]
        book_refs = [
            f"db://book/{row.get('book_id')}"
            for row in series_books
            if str(row.get("book_id") or "").strip()
        ]
        if effective_request.generate_visuals and book_refs:
            append_stage_log(log, "pipeline", "starting visual render stage", books=len(book_refs))
            render_visuals_for_run(job_id, book_refs, log)
        payload = load_job(job_id)
        payload.update(
            {
                "status": "completed",
                "return_code": 0,
                "finished_at": utc_now(),
                "artifacts": {
                    "series_identity_json": effective_request.series_identity_json,
                    "book_refs": book_refs,
                    "visual_manifest_paths": [rel(render_manifest_path_for_contract(path)) for path in book_refs],
                },
            }
        )
        save_job(payload)
        append_stage_log(log, "pipeline", "pipeline completed", book_count=len(book_refs))
    except Exception as exc:
        append_stage_log(log, "pipeline", "pipeline failed", error=repr(exc))
        append_job_log(log, traceback.format_exc() + "\n")
        payload = load_job(job_id)
        terminal_code = code if code not in (None, "", 0, "0") else payload.get("return_code")
        payload.update(
            {
                "status": "failed",
                "return_code": terminal_code if terminal_code not in (None, "", 0, "0") else -1,
                "finished_at": utc_now(),
                "error": repr(exc),
            }
        )
        save_job(payload)
    finally:
        cleanup_legacy_series_artifacts(request.series_id, log)


def run_job(job_id: str, command: list[str]) -> None:
    payload = load_job(job_id)
    payload.update({"status": "running", "started_at": utc_now(), "pid": None})
    save_job(payload)
    log = DashboardJobLogHandle(job_id)
    append_stage_log(log, "runtime", "generic job started", job_id=job_id, command=subprocess.list2cmdline(command))
    log.write("$ " + subprocess.list2cmdline(command) + "\n\n")
    try:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        payload["pid"] = process.pid
        save_job(payload)
        assert process.stdout is not None
        progress_pattern = re.compile(r"RENDER_PROGRESS\|(?P<current>\d+)\|(?P<total>\d+)\|(?P<label>.*?)\|(?P<status>[a-z_]+)")
        for line in process.stdout:
            log.write(line)
            log.flush()
            match = progress_pattern.search(line.strip())
            if match:
                payload = load_job(job_id)
                payload["progress"] = {
                    "current": int(match.group("current")),
                    "total": int(match.group("total")),
                    "label": match.group("label"),
                    "status": match.group("status"),
                }
                save_job(payload)
        code = process.wait()
        payload = load_job(job_id)
        payload.update(
            {
                "status": "completed" if code == 0 else "failed",
                "return_code": code,
                "finished_at": utc_now(),
            }
        )
        save_job(payload)
    except Exception as exc:
        append_stage_log(log, "runtime", "generic job failed", error=repr(exc))
        log.write(traceback.format_exc() + "\n")
        payload = load_job(job_id)
        payload.update({"status": "failed", "return_code": -1, "finished_at": utc_now(), "error": repr(exc)})
        save_job(payload)


app = FastAPI(title="S.A.G.A. Local Web Runtime")


@app.on_event("startup")
def on_startup() -> None:
    ensure_dirs()
    _seed_provider_configs_from_local_files()


@app.get("/runtime/state")
def runtime_state() -> dict[str, Any]:
    provider_statuses = {
        "ollama": SQLITE_STORE.get_provider_statuses("ollama"),
        "general_compute": SQLITE_STORE.get_provider_statuses("general_compute"),
        "codex": SQLITE_STORE.get_provider_statuses("codex"),
    }
    uploads = _safe_db([], "get_uploaded_sources", lambda: SQLITE_STORE.get_uploaded_sources(limit=100))
    return {
        "workspace": {"root": str(ROOT), "outputs": rel(OUTPUTS_DIR), "uploads": rel(UPLOADS_DIR)},
        "defaults": {
            "books": DEFAULT_BOOKS,
            "series_identity_json": r"db://identity-series/acotar-full-booknlp-clean-live",
            "models": [
                {"value": "gpt_oss", "label": "gpt_oss (Ollama)"},
                {"value": "general_compute", "label": "deepseek_v3 (GC)"},
                {"value": "codex", "label": "codex"},
                {"value": "mistral", "label": "mistral"},
                {"value": "gemini", "label": "gemini"},
            ],
            "provider_modes": ["single_provider", "same_provider_rotating", "cross_provider_fallback"],
            "quality_presets": ["fast_debug", "balanced", "high_quality", "max_quality"],
            "visual_strictness_modes": ["relaxed", "strict", "very_strict"],
        },
        "artifacts": scan_artifacts(),
        "jobs": list_jobs(),
        "providers": {
            "ollama": read_ollama_accounts(mask=True),
            "general_compute": read_general_compute_accounts(mask=True),
            "codex": read_codex_accounts(mask=True),
        },
        "provider_statuses": provider_statuses,
        "uploads": uploads,
        "prompts": read_prompts(),
        "loaded_at": utc_now(),
    }


@app.get("/runtime/artifact")
def runtime_artifact(path: str) -> dict[str, Any]:
    target = (ROOT / path).resolve()
    if not str(target).lower().startswith(str(ROOT).lower()):
        raise HTTPException(status_code=400, detail="Artifact path must stay inside the project.")
    if not target.exists():
        raise HTTPException(status_code=404, detail="Artifact not found.")
    if target.suffix.lower() == ".json":
        return {"path": rel(target), "type": "json", "content": load_json(target)}
    return {"path": rel(target), "type": "text", "content": target.read_text(encoding="utf-8", errors="replace")}


@app.get("/runtime/contract-view")
def runtime_contract_view(path: str, limit: int = 200) -> dict[str, Any]:
    payload = _db_contract_view(path, limit=max(20, min(limit, 500)))
    if payload is None:
        raise HTTPException(status_code=404, detail="Book record not found in SQLite.")
    return payload


@app.get("/runtime/export-book-json")
def runtime_export_book_json(path: str, limit: int = 1000):
    payload = runtime_contract_view(path=path, limit=limit)
    safe_name = str(payload.get("summary", {}).get("name") or "book").replace("/", "_").replace("\\", "_")
    body = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.json"'},
    )


@app.post("/runtime/upload-book")
async def upload_book(file: UploadFile = File(...)) -> dict[str, Any]:
    ensure_dirs()
    safe_name = Path(file.filename or "book.epub").name
    target = UPLOADS_DIR / f"{datetime.now().strftime('%Y%m%dT%H%M%S')}_{safe_name}"
    digest = hashlib.sha256()
    total_bytes = 0
    with target.open("wb") as handle:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
            digest.update(chunk)
            total_bytes += len(chunk)
    stored = _safe_db(
        None,
        "register_uploaded_source",
        lambda: SQLITE_STORE.register_uploaded_source(
            original_name=safe_name,
            stored_path=str(target),
            size_bytes=total_bytes,
            mime_type=str(file.content_type or "").strip() or None,
            sha256=digest.hexdigest(),
            source_kind="book_upload",
            metadata={
                "relative_path": rel(target),
                "uploaded_at": utc_now(),
            },
        ),
    ) or {}
    return {
        "id": stored.get("id") or "",
        "path": str(target),
        "relative_path": rel(target),
        "name": safe_name,
        "size_bytes": total_bytes,
        "mime_type": str(file.content_type or "").strip(),
        "sha256": digest.hexdigest(),
    }


@app.post("/runtime/start-encode")
def start_encode(request: EncodeRequest) -> dict[str, Any]:
    ensure_dirs()
    job_id = f"encode_{datetime.now().strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    stages = []
    if request.generate_identity_bundles:
        stages.append("identity_bundle")
    stages.append("encode")
    if request.generate_visuals:
        stages.append("visual_render")
    payload = {
        "id": job_id,
        "type": "encode-pipeline",
        "status": "queued",
        "created_at": utc_now(),
        "command": " -> ".join(stages),
        "request": request.model_dump(),
    }
    save_job(payload)
    thread = threading.Thread(target=run_encode_pipeline_job, args=(job_id, request), daemon=True)
    thread.start()
    return load_job(job_id)


@app.post("/runtime/start-character-render")
def start_character_render(request: CharacterRenderRequest) -> dict[str, Any]:
    ensure_dirs()
    command = build_character_render_command(request)
    job_id = f"render_{datetime.now().strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    payload = {
        "id": job_id,
        "type": "render-character-sheets",
        "status": "queued",
        "created_at": utc_now(),
        "command": subprocess.list2cmdline(command),
        "request": request.model_dump(),
    }
    save_job(payload)
    thread = threading.Thread(target=run_job, args=(job_id, command), daemon=True)
    thread.start()
    return load_job(job_id)


@app.get("/runtime/jobs")
def get_jobs() -> dict[str, Any]:
    return {"jobs": list_jobs()}


@app.get("/api/runs")
def api_runs() -> list[dict[str, Any]]:
    return scan_artifacts().get("runs") or []


@app.get("/runtime/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    return load_job(job_id)


@app.post("/runtime/providers/ollama")
def save_ollama_provider(config: OllamaProviderConfig) -> dict[str, Any]:
    return {"ollama": merge_and_save_ollama_accounts(config)}


@app.post("/runtime/providers/general-compute")
def save_general_compute_provider(config: GeneralComputeProviderConfig) -> dict[str, Any]:
    return {"general_compute": merge_and_save_general_compute_accounts(config)}


@app.post("/runtime/providers/codex")
def save_codex_provider(config: CodexProviderConfig) -> dict[str, Any]:
    return {"codex": merge_and_save_codex_accounts(config)}


@app.get("/runtime/providers/status")
def get_provider_statuses(refresh: bool = False) -> dict[str, Any]:
    if refresh:
        return {"providers": refresh_provider_statuses(), "refreshed_at": utc_now()}
    return {
        "providers": {
            "ollama": {
                "config": read_ollama_accounts(mask=True),
                "statuses": SQLITE_STORE.get_provider_statuses("ollama"),
            },
            "general_compute": {
                "config": read_general_compute_accounts(mask=True),
                "statuses": SQLITE_STORE.get_provider_statuses("general_compute"),
            },
            "codex": {
                "config": read_codex_accounts(mask=True),
                "statuses": SQLITE_STORE.get_provider_statuses("codex"),
            },
        },
        "refreshed_at": utc_now(),
    }


@app.get("/runtime/file")
def runtime_file(path: str):
    target = (ROOT / path).resolve()
    if not str(target).lower().startswith(str(ROOT).lower()):
        raise HTTPException(status_code=400, detail="File path must stay inside the project.")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    media_type = None
    lower_name = target.name.lower()
    if lower_name.endswith(".json"):
        media_type = "application/json"
    elif lower_name.endswith(".md"):
        media_type = "text/markdown; charset=utf-8"
    return FileResponse(target, filename=target.name, media_type=media_type)


if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")


@app.get("/{full_path:path}")
def serve_dashboard(full_path: str = ""):
    target = DIST_DIR / full_path
    if full_path and target.exists() and target.is_file():
        return FileResponse(target)
    index = DIST_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"status": "dashboard build missing", "hint": "Run npm run build in dashboard_app first."}


def main() -> None:
    ensure_dirs()
    host = os.environ.get("SAGA_DASHBOARD_HOST", "127.0.0.1")
    port = int(os.environ.get("SAGA_DASHBOARD_PORT", "8675"))
    log_level = os.environ.get("SAGA_DASHBOARD_LOG_LEVEL", "info")
    url = f"http://{host}:{port}"
    if os.environ.get("SAGA_DASHBOARD_NO_BROWSER") != "1":
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=port, log_level=log_level)


if __name__ == "__main__":
    main()
