"""Lightweight CLI for contract-centric downstream workflows."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import os
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List

from infrastructure.llm_client import LLMClient
from infrastructure.neo4j_ingestion_service import Neo4jIngestionError, Neo4jIngestionService
from query.neo4j_narrative_context_service import Neo4jNarrativeContextService
from query.narrative_context_service import NarrativeContextService
from services.corpus_hardening_service import CorpusHardeningService
from services.narrative_generation_service import NarrativeGenerationService

DEFAULT_NARRATIVE_MODEL_MODE = LLMClient.MODE_GPT_OSS
DEFAULT_NARRATIVE_OLLAMA_MODEL = "gemma4:31b-cloud"


def _load_json(path: str | Path) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str | Path, payload: Dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
    return target


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
    helper = CorpusHardeningService(
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
    from services.encoder_persistence_service import EncoderPersistenceService, RateLimitGuardError

    preflight_models = [
        (args.analysis_model, args.analysis_model),
        (args.identity_model, args.identity_model),
    ]
    checked = set()
    for mode_name, model_mode in preflight_models:
        if model_mode in checked:
            continue
        checked.add(model_mode)
        if model_mode in {LLMClient.MODE_DEEPSEEK, LLMClient.MODE_GPT_OSS}:
            probe_client = LLMClient(mode=model_mode, max_retries=1, base_delay=0.0, timeout=30)
            model_name = probe_client._ollama_model_for_mode()
            probe_result = LLMClient.probe_ollama_mode_access(model_mode, model_name)
            if probe_result.get("status") != "ok":
                raise ValueError(
                    f"Ollama model access failed for mode '{model_mode}' using model '{model_name}': "
                    f"{probe_result.get('detail') or probe_result.get('status')}. "
                    "Choose a working model or upgrade the Ollama subscription for that cloud model."
                )

    encoder = EncoderPersistenceService(
        analysis_model=args.analysis_model,
        identity_model=args.identity_model,
        analysis_mode=args.analysis_mode,
        target_scene_words=args.target_scene_words,
        series_id=args.series_id,
        series_title=args.series_title,
        book_index_base=args.book_index_base,
    )
    neo4j = Neo4jIngestionService(
        uri=args.uri,
        username=args.username,
        password=args.password,
        database=args.database,
    )
    try:
        prepared_books = encoder._prepare_book_inputs(_book_inputs_from_args(args.book))
        effective_series_id, effective_series_title = encoder._series_context(prepared_books)
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
                analysis_mode=args.analysis_mode,
                target_scene_words=args.target_scene_words,
                series_id=effective_series_id,
                series_title=effective_series_title,
                book_index_base=book["book_index"],
            )
            book_neo4j = Neo4jIngestionService(
                uri=args.uri,
                username=args.username,
                password=args.password,
                database=args.database,
            )
            try:
                result = book_encoder.encode_and_persist(
                    [book],
                    neo4j_service=book_neo4j,
                    progress_callback=_progress_callback,
                    checkpoint_path=checkpoint_path,
                )
            finally:
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
    service = CorpusHardeningService(
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
    service = CorpusHardeningService(
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
    service = CorpusHardeningService(
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
        report = service.rebuild_corpus(
            series_id=args.series_id,
            contract_paths=_contract_paths_from_args_or_discovery(args),
            output_dir=args.output_dir,
            dry_run=args.dry_run,
            source_dir=args.source_dir,
        )
    finally:
        service.neo4j.close()
    print(json.dumps(report, ensure_ascii=True, indent=2, default=str))


def compare_generation_models(args) -> None:
    output_root = Path(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    controls = _generation_controls_from_args(args)
    runs = []
    for label, model_mode, ollama_model in [
        ("model_a", args.model_mode_a, args.ollama_model_a),
        ("model_b", args.model_mode_b, args.ollama_model_b),
    ]:
        llm = LLMClient(mode=model_mode, ollama_model_override=ollama_model)
        decoder = NarrativeGenerationService(llm_client=llm)
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
    payload = _load_json(args.contract)
    _validate_contract(payload)
    service = NarrativeContextService()
    context = service.build_from_contract(payload, prefer_exported=not args.force_rebuild)
    target = service.write_context(context, args.out)
    print(f"Narrative context written to: {target}")


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
    payload = _load_json(args.contract)
    _validate_contract(payload)
    llm = LLMClient(mode=args.model_mode, ollama_model_override=getattr(args, "ollama_model", ""))
    decoder = NarrativeGenerationService(llm_client=llm)
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
    llm = LLMClient(mode=args.model_mode, ollama_model_override=getattr(args, "ollama_model", ""))
    decoder = NarrativeGenerationService(llm_client=llm)
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
    payload = _load_json(args.contract)
    _validate_contract(payload)
    llm = LLMClient(mode=args.model_mode, ollama_model_override=getattr(args, "ollama_model", ""))
    decoder = NarrativeGenerationService(llm_client=llm)
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
    llm = LLMClient(mode=args.model_mode, ollama_model_override=getattr(args, "ollama_model", ""))
    decoder = NarrativeGenerationService(llm_client=llm)
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
    encode_parser.add_argument("--analysis-model", default=LLMClient.MODE_GPT_OSS, choices=[LLMClient.MODE_DEEPSEEK, LLMClient.MODE_GPT_OSS, LLMClient.MODE_MISTRAL, LLMClient.MODE_GEMINI])
    encode_parser.add_argument("--identity-model", default=LLMClient.MODE_GPT_OSS, choices=[LLMClient.MODE_DEEPSEEK, LLMClient.MODE_GPT_OSS, LLMClient.MODE_MISTRAL, LLMClient.MODE_GEMINI])
    encode_parser.add_argument("--analysis-mode", default="structured", choices=["structured", "tool", "compare"])
    encode_parser.add_argument("--target-scene-words", type=int, default=0)
    encode_parser.add_argument("--max-parallel-books", type=int, default=2, help="Maximum number of books to encode in parallel for this batch.")
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
    reencode_parser.add_argument("--analysis-model", default=LLMClient.MODE_GPT_OSS, choices=[LLMClient.MODE_DEEPSEEK, LLMClient.MODE_GPT_OSS, LLMClient.MODE_MISTRAL, LLMClient.MODE_GEMINI])
    reencode_parser.add_argument("--identity-model", default=LLMClient.MODE_GPT_OSS, choices=[LLMClient.MODE_DEEPSEEK, LLMClient.MODE_GPT_OSS, LLMClient.MODE_MISTRAL, LLMClient.MODE_GEMINI])
    reencode_parser.add_argument("--analysis-mode", default="structured", choices=["structured", "tool", "compare"])
    reencode_parser.add_argument("--target-scene-words", type=int, default=0)
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
        choices=[LLMClient.MODE_DEEPSEEK, LLMClient.MODE_GPT_OSS, LLMClient.MODE_MISTRAL, LLMClient.MODE_GEMINI],
        help="LLM backend to use for residual ambiguity verification during audit previews.",
    )
    audit_parser.add_argument(
        "--ollama-model",
        default=DEFAULT_NARRATIVE_OLLAMA_MODEL,
        help="Optional explicit Ollama model tag override for cloud/local Ollama-backed audit verification.",
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
        choices=[LLMClient.MODE_DEEPSEEK, LLMClient.MODE_GPT_OSS, LLMClient.MODE_MISTRAL, LLMClient.MODE_GEMINI],
        help="LLM backend to use for residual ambiguity verification during repair.",
    )
    repair_parser.add_argument(
        "--ollama-model",
        default=DEFAULT_NARRATIVE_OLLAMA_MODEL,
        help="Optional explicit Ollama model tag override for cloud/local Ollama-backed repair verification.",
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
    rebuild_parser.add_argument("--uri", default=None, help="Neo4j URI. Falls back to NEO4J_URI.")
    rebuild_parser.add_argument("--username", default=None, help="Neo4j username. Falls back to NEO4J_USERNAME.")
    rebuild_parser.add_argument("--password", default=None, help="Neo4j password. Falls back to NEO4J_PASSWORD.")
    rebuild_parser.add_argument("--database", default=None, help="Neo4j database. Falls back to NEO4J_DATABASE.")
    rebuild_parser.add_argument(
        "--model-mode",
        default=DEFAULT_NARRATIVE_MODEL_MODE,
        choices=[LLMClient.MODE_DEEPSEEK, LLMClient.MODE_GPT_OSS, LLMClient.MODE_MISTRAL, LLMClient.MODE_GEMINI],
        help="LLM backend to use for residual ambiguity verification during rebuild.",
    )
    rebuild_parser.add_argument(
        "--ollama-model",
        default=DEFAULT_NARRATIVE_OLLAMA_MODEL,
        help="Optional explicit Ollama model tag override for cloud/local Ollama-backed rebuild verification.",
    )
    rebuild_parser.set_defaults(func=rebuild_corpus)

    context_parser = subparsers.add_parser(
        "build-sequel-context",
        help="Build the Narraverse-style sequel retrieval context from a SAGA contract.",
    )
    context_parser.add_argument("--contract", required=True, help="Path to the contract JSON.")
    context_parser.add_argument("--out", required=True, help="Output path for the narrative context JSON.")
    context_parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Ignore any exported narrative context in the contract and rebuild from core SAGA outputs.",
    )
    context_parser.set_defaults(func=build_sequel_context)

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
            LLMClient.MODE_MISTRAL,
            LLMClient.MODE_GEMINI,
        ],
        help="LLM backend to use for blueprint generation.",
    )
    blueprint_parser.add_argument(
        "--ollama-model",
        default=DEFAULT_NARRATIVE_OLLAMA_MODEL,
        help="Optional explicit Ollama model tag override for cloud/local Ollama-backed runs.",
    )
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
        choices=[LLMClient.MODE_DEEPSEEK, LLMClient.MODE_GPT_OSS, LLMClient.MODE_MISTRAL, LLMClient.MODE_GEMINI],
    )
    blueprint_graph_parser.add_argument(
        "--ollama-model",
        default=DEFAULT_NARRATIVE_OLLAMA_MODEL,
        help="Optional explicit Ollama model tag override for cloud/local Ollama-backed runs.",
    )
    blueprint_graph_parser.set_defaults(func=generate_blueprint_neo4j)

    sequel_parser = subparsers.add_parser(
        "generate-sequel",
        help="Run the full narrative generation pipeline from a SAGA contract.",
    )
    sequel_parser.add_argument("--contract", required=True, help="Path to the contract JSON.")
    sequel_parser.add_argument("--prompt", required=True, help="Creative direction for the sequel.")
    sequel_parser.add_argument("--output-dir", required=True, help="Directory for chapter outputs.")
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
            LLMClient.MODE_MISTRAL,
            LLMClient.MODE_GEMINI,
        ],
        help="LLM backend to use for sequel generation.",
    )
    sequel_parser.add_argument(
        "--ollama-model",
        default=DEFAULT_NARRATIVE_OLLAMA_MODEL,
        help="Optional explicit Ollama model tag override for cloud/local Ollama-backed runs.",
    )
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
        choices=[LLMClient.MODE_DEEPSEEK, LLMClient.MODE_GPT_OSS, LLMClient.MODE_MISTRAL, LLMClient.MODE_GEMINI],
    )
    sequel_graph_parser.add_argument(
        "--ollama-model",
        default=DEFAULT_NARRATIVE_OLLAMA_MODEL,
        help="Optional explicit Ollama model tag override for cloud/local Ollama-backed runs.",
    )
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
    compare_parser.add_argument("--model-mode-a", default=DEFAULT_NARRATIVE_MODEL_MODE, choices=[LLMClient.MODE_DEEPSEEK, LLMClient.MODE_GPT_OSS, LLMClient.MODE_MISTRAL, LLMClient.MODE_GEMINI])
    compare_parser.add_argument("--ollama-model-a", default=DEFAULT_NARRATIVE_OLLAMA_MODEL, help="Ollama model tag override for model A.")
    compare_parser.add_argument("--model-mode-b", default=DEFAULT_NARRATIVE_MODEL_MODE, choices=[LLMClient.MODE_DEEPSEEK, LLMClient.MODE_GPT_OSS, LLMClient.MODE_MISTRAL, LLMClient.MODE_GEMINI])
    compare_parser.add_argument("--ollama-model-b", default="gpt-oss:120b-cloud", help="Ollama model tag override for model B.")
    compare_parser.set_defaults(func=compare_generation_models)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except (ValueError, Neo4jIngestionError) as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
