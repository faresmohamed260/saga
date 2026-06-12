from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core.builders.relationship_profile_builder import RelationshipProfileBuilder


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dashboard_app" / "dist"
OUTPUTS_DIR = ROOT / "analysis_outputs"
DASHBOARD_DIR = OUTPUTS_DIR / "dashboard"
JOBS_DIR = DASHBOARD_DIR / "jobs"
UPLOADS_DIR = DASHBOARD_DIR / "uploads"
OLLAMA_ACCOUNTS_FILE = ROOT / "deploy" / "ollama" / "accounts.local.json"
CODEX_ACCOUNTS_FILE = ROOT / "deploy" / "openai" / "accounts.local.json"

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
    no_progress: bool = False
    out: str = r"analysis_outputs\encoder_validation\acotar_full_booknlp_clean_live.json"


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


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


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
    title = metadata.get("book_title") or path.name.replace(".contract.json", "")
    summary = {
        "path": rel(path),
        "name": title,
        "mtime": stat.st_mtime,
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
        "run_status": metadata.get("run_status") or payload.get("run_status") or "unknown",
        "identity_provider": metadata.get("identity_provider") or payload.get("identity_provider") or "n/a",
        "scenes": len(scenes),
        "successful_scenes": quality.get("successful_scenes"),
        "failed_scenes": quality.get("failed_scenes"),
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
    active_books = []
    if isinstance(status_payload, dict):
        active_books = status_payload.get("books") or []
    active_scene_total = 0
    if active_books:
        for book in active_books:
            if not isinstance(book, dict):
                continue
            active_scene_total += int(book.get("scenes_processed") or book.get("total_scenes") or 0)
    failed_books = sum(1 for row in contracts if str(row.get("run_status")).lower() in {"failed", "partial", "paused"})
    status_value = "failed" if failed_books else (run_status or ("completed" if contracts else "unknown"))
    books_count = len(contracts) if contracts else len(active_books)
    contracts_count = len(contracts)
    total_scenes = sum(int(row.get("scenes") or 0) for row in contracts if isinstance(row.get("scenes"), int))
    if not total_scenes and active_scene_total:
        total_scenes = active_scene_total
    return {
        "path": rel(run_dir),
        "series_id": run_dir.parent.name,
        "run_id": run_dir.name,
        "mtime": run_dir.stat().st_mtime,
        "status": status_value,
        "books": books_count,
        "contracts": contracts_count,
        "failed_books": failed_books,
        "total_scenes": total_scenes,
        "book_rows": contracts if contracts else active_books,
        "status_payload_count": len(statuses),
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
    contract_paths = sorted(OUTPUTS_DIR.rglob("*.contract.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    contracts = [contract_summary(path) for path in contract_paths[:200]]
    run_dirs = []
    runs_root = OUTPUTS_DIR / "encode_runs"
    if runs_root.exists():
        for series_dir in runs_root.iterdir():
            if not series_dir.is_dir():
                continue
            for run_dir in series_dir.iterdir():
                if is_real_run_dir(run_dir):
                    run_dirs.append(run_dir)
    runs = [run_summary(path) for path in sorted(run_dirs, key=lambda p: p.stat().st_mtime, reverse=True)[:100]]
    reports = [
        {
            "path": rel(path),
            "name": path.name,
            "mtime": path.stat().st_mtime,
            "category": rel(path.parent),
        }
        for path in sorted(OUTPUTS_DIR.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:200]
    ]
    visual_states = [
        {
            "path": rel(path),
            "name": path.name,
            "mtime": path.stat().st_mtime,
            "type": "visual_state" if "visual" in path.name.lower() else "json",
        }
        for path in sorted((OUTPUTS_DIR / "visual_state").rglob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:100]
    ] if (OUTPUTS_DIR / "visual_state").exists() else []
    identities = [
        {
            "path": rel(path),
            "name": path.name,
            "mtime": path.stat().st_mtime,
        }
        for path in sorted((OUTPUTS_DIR / "identity_series").rglob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:200]
    ] if (OUTPUTS_DIR / "identity_series").exists() else []
    payload = {
        "contracts": contracts,
        "runs": runs,
        "reports": reports,
        "visual_states": visual_states,
        "identities": identities,
        "counts": {
            "contracts": len(contract_paths),
            "runs": len(run_dirs),
            "reports": len(reports),
            "visual_states": len(visual_states),
            "identities": len(identities),
            "total_scenes": sum(int(row.get("scenes") or 0) for row in contracts if isinstance(row.get("scenes"), int)),
        },
    }
    SCAN_CACHE["created_at"] = now
    SCAN_CACHE["payload"] = payload
    return payload


def read_ollama_accounts(mask: bool = True) -> dict[str, Any]:
    data = load_json(OLLAMA_ACCOUNTS_FILE)
    if not isinstance(data, dict):
        data = {"active_index": 0, "accounts": []}
    accounts = []
    for index, item in enumerate(data.get("accounts") or []):
        account = {
            "index": index,
            "label": str(item.get("label") or f"account-{index + 1}"),
            "email": str(item.get("email") or ""),
            "has_password": bool(item.get("password")),
            "has_api_key": bool(item.get("api_key")),
            "password": mask_secret(item.get("password") or "") if mask else str(item.get("password") or ""),
            "api_key": mask_secret(item.get("api_key") or "") if mask else str(item.get("api_key") or ""),
            "active": index == int(data.get("active_index", 0) or 0),
        }
        accounts.append(account)
    return {"active_index": int(data.get("active_index", 0) or 0), "accounts": accounts}


def merge_and_save_ollama_accounts(config: OllamaProviderConfig) -> dict[str, Any]:
    existing_raw = load_json(OLLAMA_ACCOUNTS_FILE) or {"active_index": 0, "accounts": []}
    existing_by_label = {str(item.get("label") or ""): item for item in existing_raw.get("accounts") or []}
    accounts: list[dict[str, Any]] = []
    for account in config.accounts:
        previous = existing_by_label.get(account.label, {})
        item = {"label": account.label.strip() or f"account-{len(accounts) + 1}"}
        if account.email:
            item["email"] = account.email
        elif previous.get("email"):
            item["email"] = previous.get("email")
        if account.password:
            item["password"] = account.password
        elif previous.get("password"):
            item["password"] = previous.get("password")
        if account.api_key:
            item["api_key"] = account.api_key
        elif previous.get("api_key"):
            item["api_key"] = previous.get("api_key")
        if item.get("api_key") or (item.get("email") and item.get("password")):
            accounts.append(item)
    payload = {"active_index": max(0, min(config.active_index, max(len(accounts) - 1, 0))), "accounts": accounts}
    write_json(OLLAMA_ACCOUNTS_FILE, payload)
    return read_ollama_accounts(mask=True)


def read_codex_accounts(mask: bool = True) -> dict[str, Any]:
    data = load_json(CODEX_ACCOUNTS_FILE)
    if not isinstance(data, dict):
        data = {"active_index": 0, "accounts": []}
    accounts = []
    for index, item in enumerate(data.get("accounts") or []):
        account = {
            "index": index,
            "label": str(item.get("label") or f"account-{index + 1}"),
            "has_api_key": bool(item.get("api_key")),
            "api_key": mask_secret(item.get("api_key") or "") if mask else str(item.get("api_key") or ""),
            "active": index == int(data.get("active_index", 0) or 0),
        }
        accounts.append(account)
    return {"active_index": int(data.get("active_index", 0) or 0), "accounts": accounts}


def merge_and_save_codex_accounts(config: CodexProviderConfig) -> dict[str, Any]:
    existing_raw = load_json(CODEX_ACCOUNTS_FILE) or {"active_index": 0, "accounts": []}
    existing_by_label = {str(item.get("label") or ""): item for item in existing_raw.get("accounts") or []}
    accounts: list[dict[str, Any]] = []
    for account in config.accounts:
        previous = existing_by_label.get(account.label, {})
        item = {"label": account.label.strip() or f"account-{len(accounts) + 1}"}
        if account.api_key:
            item["api_key"] = account.api_key
        elif previous.get("api_key"):
            item["api_key"] = previous.get("api_key")
        if item.get("api_key"):
            accounts.append(item)
    payload = {"active_index": max(0, min(config.active_index, max(len(accounts) - 1, 0))), "accounts": accounts}
    write_json(CODEX_ACCOUNTS_FILE, payload)
    return read_codex_accounts(mask=True)


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


def reduce_contract_row(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {"description": str(row)}
    allowed_keys = [
        "id",
        "scene_id",
        "event_id",
        "character_id",
        "entity_id",
        "chapter_index",
        "scene_index",
        "scene_summary",
        "summary",
        "name",
        "display_name",
        "canonical_name",
        "event",
        "description",
        "relationship_type",
        "state",
        "evidence",
        "notes",
        "location",
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


def contract_view(path: Path, *, limit: int = 200) -> dict[str, Any]:
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
    visual_prompt_sets = outputs.get("visual_prompt_sets") or {}
    visual_sections: dict[str, list[Any]] = {}
    if isinstance(visual_prompt_sets, dict):
        for key in ["initial_characters", "character_changes", "objects_creatures", "locations", "scene_compositions"]:
            visual_sections[key] = visual_prompt_sets.get(key) or []
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
            "visual_prompt_diagnostics": visual_prompt_sets.get("diagnostics") if isinstance(visual_prompt_sets, dict) else {},
        },
        "counts": {
            **{key: len(values) for key, values in sections.items()},
            **{f"visual_{key}": len(values) for key, values in visual_sections.items()},
        },
        "truncated_at": limit,
    }


def job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def log_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.log"


def load_job(job_id: str) -> dict[str, Any]:
    payload = load_json(job_path(job_id))
    if not isinstance(payload, dict):
        raise HTTPException(status_code=404, detail="Job not found")
    log = log_path(job_id)
    payload["log_tail"] = log.read_text(encoding="utf-8", errors="replace").splitlines()[-120:] if log.exists() else []
    return payload


def save_job(payload: dict[str, Any]) -> None:
    write_json(job_path(payload["id"]), payload)


def list_jobs() -> list[dict[str, Any]]:
    ensure_dirs()
    rows = []
    for path in sorted(JOBS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        data = load_json(path)
        if isinstance(data, dict):
            rows.append(load_job(data.get("id") or path.stem))
    return rows[:50]


def build_encode_command(request: EncodeRequest) -> list[str]:
    books = [book for book in request.books if str(book).strip()]
    if not books:
        raise HTTPException(status_code=400, detail="At least one book path is required.")
    command = [sys.executable, "saga_tools.py", "encode-store"]
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
            "--identity-strategy",
            request.identity_strategy,
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
            "--out",
            request.out,
        ]
    )
    if request.max_chapters and request.max_chapters > 0:
        command.extend(["--max-chapters", str(request.max_chapters)])
    if request.series_identity_json:
        command.extend(["--series-identity-json", request.series_identity_json])
    if request.skip_ingest:
        command.append("--skip-ingest")
    if request.no_progress:
        command.append("--no-progress")
    return command


def run_job(job_id: str, command: list[str]) -> None:
    payload = load_job(job_id)
    payload.update({"status": "running", "started_at": utc_now(), "pid": None})
    save_job(payload)
    with log_path(job_id).open("a", encoding="utf-8", errors="replace") as log:
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
            for line in process.stdout:
                log.write(line)
                log.flush()
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
            log.write(f"\nRuntime failed: {exc!r}\n")
            payload = load_job(job_id)
            payload.update({"status": "failed", "return_code": -1, "finished_at": utc_now(), "error": repr(exc)})
            save_job(payload)


app = FastAPI(title="S.A.G.A. Local Web Runtime")


@app.on_event("startup")
def on_startup() -> None:
    ensure_dirs()


@app.get("/runtime/state")
def runtime_state() -> dict[str, Any]:
    return {
        "workspace": {"root": str(ROOT), "outputs": rel(OUTPUTS_DIR), "uploads": rel(UPLOADS_DIR)},
        "defaults": {
            "books": DEFAULT_BOOKS,
            "series_identity_json": r"analysis_outputs\identity_series\acotar\acotar_series_pipeline_identity.json",
            "models": ["gpt_oss", "deepseek", "codex", "general_compute", "mistral", "gemini"],
            "provider_modes": ["single_provider", "same_provider_rotating", "cross_provider_fallback"],
        },
        "artifacts": scan_artifacts(),
        "jobs": list_jobs(),
        "providers": {
            "ollama": read_ollama_accounts(mask=True),
            "codex": read_codex_accounts(mask=True),
        },
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
    target = (ROOT / path).resolve()
    if not str(target).lower().startswith(str(ROOT).lower()):
        raise HTTPException(status_code=400, detail="Contract path must stay inside the project.")
    if not target.exists() or not target.name.endswith(".contract.json"):
        raise HTTPException(status_code=404, detail="Contract not found.")
    return contract_view(target, limit=max(20, min(limit, 500)))


@app.post("/runtime/upload-book")
async def upload_book(file: UploadFile = File(...)) -> dict[str, Any]:
    ensure_dirs()
    safe_name = Path(file.filename or "book.epub").name
    target = UPLOADS_DIR / f"{datetime.now().strftime('%Y%m%dT%H%M%S')}_{safe_name}"
    with target.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    return {"path": str(target), "relative_path": rel(target), "name": safe_name}


@app.post("/runtime/start-encode")
def start_encode(request: EncodeRequest) -> dict[str, Any]:
    ensure_dirs()
    command = build_encode_command(request)
    job_id = f"encode_{datetime.now().strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    payload = {
        "id": job_id,
        "type": "encode-store",
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


@app.get("/runtime/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    return load_job(job_id)


@app.post("/runtime/providers/ollama")
def save_ollama_provider(config: OllamaProviderConfig) -> dict[str, Any]:
    return {"ollama": merge_and_save_ollama_accounts(config)}


@app.post("/runtime/providers/codex")
def save_codex_provider(config: CodexProviderConfig) -> dict[str, Any]:
    return {"codex": merge_and_save_codex_accounts(config)}


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
