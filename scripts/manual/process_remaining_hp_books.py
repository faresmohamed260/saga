from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.db_character_visual_baseline_agent import DatabaseCharacterVisualBaselineAgent
from analysis.db_noncharacter_scene_state_agent import DatabaseNonCharacterSceneStateAgent
from analysis.db_relationship_agent import DatabaseRelationshipAgent
from analysis.db_scene_enrichment_agent import DatabaseSceneEnrichmentAgent
from analysis.db_stable_character_state_agent import DatabaseStableCharacterStateAgent
from analysis.db_timeline_agent import DatabaseTimelineAgent
from analysis.db_world_state_consolidation_agent import DatabaseWorldStateConsolidationAgent
from redesign_lab.identity.series_identity_provider import (
    build_series_pipeline_identity,
    generate_book_identity_bundle,
)
from sql_store.persistence import SagaSQLiteStore
BOOK_DIR = Path(r"D:\Books\Harry_Potter_Series")
SERIES_ID = "hp1-full-e2e-20260615"
SERIES_TITLE = "Harry Potter Full Series DB Canon"
IDENTITY_ROOT = ROOT / "analysis_outputs" / "identity_series" / SERIES_ID
SERIES_IDENTITY_JSON = IDENTITY_ROOT / f"{SERIES_ID}_series_pipeline_identity.json"
ENCODE_OUT = ROOT / "analysis_outputs" / "encoder_validation" / "hp_books_2_7_encode_20260616.json"
STORE = SagaSQLiteStore()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
LOGGER = logging.getLogger("process_remaining_hp_books")


def list_books() -> list[dict[str, Any]]:
    rows = sorted(BOOK_DIR.glob("*.epub"))
    payload: list[dict[str, Any]] = []
    for idx, path in enumerate(rows, start=1):
        payload.append(
            {
                "path": str(path),
                "title": path.name,
                "book_index": idx,
            }
        )
    return payload


def existing_book1_summary() -> dict[str, Any]:
    output_dir = IDENTITY_ROOT / "book_01_book_01"
    pipeline_path = output_dir / "booknlp_small_pipeline_identity.json"
    if not pipeline_path.exists():
        raise FileNotFoundError(f"Existing Book 1 identity bundle missing: {pipeline_path}")
    payload = json.loads(pipeline_path.read_text(encoding="utf-8"))
    raw = json.loads((output_dir / "booknlp_small_identity_result.json").read_text(encoding="utf-8"))
    return {
        "book_index": 1,
        "book_slug": "book_01",
        "title": "1 Harry Potter & the Philosophers Stone.epub",
        "output_dir": str(output_dir),
        "booknlp_runtime_seconds": ((raw.get("diagnostics") or {}).get("runtime_seconds")),
        "pipeline_identity_path": str(pipeline_path),
        "character_count": len(payload.get("characters") or []),
        "alias_count": len(payload.get("alias_index") or {}),
        "reference_entity_count": len(payload.get("reference_entities") or []),
        "suppressed_cluster_count": len(payload.get("suppressed_clusters") or []),
        "narrator": payload.get("narrator") or {},
        "reused_seed": True,
    }


def build_full_series_identity(books: list[dict[str, Any]]) -> None:
    IDENTITY_ROOT.mkdir(parents=True, exist_ok=True)
    summaries = [existing_book1_summary()]
    for book in books:
        if int(book["book_index"]) == 1:
            continue
        LOGGER.info("Generating BookNLP-clean identity bundle | book=%s", book["title"])
        summary = generate_book_identity_bundle(
            book=book,
            book_index=int(book["book_index"]),
            output_root=IDENTITY_ROOT,
            reuse_book1_seed=False,
        )
        summaries.append(summary)
        LOGGER.info(
            "Identity bundle ready | book=%s chars=%s aliases=%s refs=%s",
            book["title"],
            summary["character_count"],
            summary["alias_count"],
            summary["reference_entity_count"],
        )
    payload = build_series_pipeline_identity(book_summaries=summaries, output_json=SERIES_IDENTITY_JSON)
    payload["series_id"] = SERIES_ID
    payload.setdefault("provider", "booknlp_clean")
    STORE.persist_identity_bundle(
        series_id=SERIES_ID,
        source_path=f"db://identity-series/{SERIES_ID}",
        series_payload=payload,
        book_summaries=summaries,
    )
    LOGGER.info(
        "Persisted full HP identity series | series=%s books=%s chars=%s aliases=%s",
        SERIES_ID,
        len(summaries),
        len(payload.get("characters") or []),
        len(payload.get("alias_index") or {}),
    )


def run_encode(books: list[dict[str, Any]]) -> None:
    remaining = [row for row in books if int(row["book_index"]) >= 2]
    command = [
        sys.executable,
        "-u",
        "saga_tools.py",
        "encode-store",
    ]
    for row in remaining:
        command.extend(["--book", row["path"]])
    command.extend(
        [
            "--series-id",
            SERIES_ID,
            "--series-title",
            SERIES_TITLE,
            "--book-index-base",
            "2",
            "--analysis-model",
            "gpt_oss",
            "--identity-model",
            "gpt_oss",
            "--analysis-provider-mode",
            "same_provider_rotating",
            "--identity-provider",
            "booknlp_clean",
            "--series-identity-json",
            str(SERIES_IDENTITY_JSON),
            "--scene-failure-policy",
            "fail_fast",
            "--max-failed-scenes-absolute",
            "3",
            "--max-failed-scene-ratio",
            "0.10",
            "--min-nonempty-scene-ratio",
            "0.80",
            "--max-parallel-books",
            "1",
            "--skip-ingest",
            "--out",
            str(ENCODE_OUT),
        ]
    )
    LOGGER.info("Starting encode-store for books 2-7")
    subprocess.run(command, cwd=ROOT, check=True)
    LOGGER.info("encode-store complete for books 2-7")


def get_series_books() -> list[dict[str, Any]]:
    return STORE.get_series_books(SERIES_ID)


def sparse_character_names(book_id: str) -> list[str]:
    from sqlalchemy import text

    with STORE.session_factory() as session:
        rows = session.execute(
            text(
                """
                SELECT canonical_name
                FROM entities
                WHERE book_id=:book_id
                  AND entity_type='character'
                  AND (
                    COALESCE(json_extract(first_appearance_profile,'$.status'),'') IN ('sparse','partial','minimal','')
                    OR COALESCE(json_extract(initial_physical_description,'$.status'),'') IN ('empty','partial','minimal','')
                  )
                ORDER BY canonical_name
                """
            ),
            {"book_id": book_id},
        ).fetchall()
    return [str(row[0]) for row in rows if str(row[0]).strip()]


def audit_counts(book_id: str) -> dict[str, int]:
    from sqlalchemy import text

    queries = {
        "scenes": "SELECT COUNT(*) FROM scenes WHERE book_id=:b",
        "scene_titles": "SELECT COUNT(*) FROM scenes WHERE book_id=:b AND COALESCE(json_extract(payload_json,'$.scene_title'),'')<>''",
        "scene_summaries": "SELECT COUNT(*) FROM scenes WHERE book_id=:b AND COALESCE(summary,'')<>''",
        "scene_state_changes": "SELECT COUNT(*) FROM scenes WHERE book_id=:b AND COALESCE(json_array_length(json_extract(payload_json,'$.state_changes')),0)>0",
        "scene_relationship_changes": "SELECT COUNT(*) FROM scenes WHERE book_id=:b AND COALESCE(json_array_length(json_extract(payload_json,'$.relationship_changes')),0)>0",
        "scene_world_rows": "SELECT COUNT(*) FROM scenes WHERE book_id=:b AND COALESCE(json_array_length(json_extract(payload_json,'$.entity_world_state.entities')),0)>0",
        "events": "SELECT COUNT(*) FROM events WHERE book_id=:b",
        "entities": "SELECT COUNT(*) FROM entities WHERE book_id=:b",
        "character_profiles": "SELECT COUNT(*) FROM character_profiles WHERE book_id=:b",
        "character_visual_baselines": "SELECT COUNT(*) FROM character_visual_baselines WHERE book_id=:b",
        "character_visual_scene_states": "SELECT COUNT(*) FROM character_visual_scene_states WHERE book_id=:b",
        "creature_visual_baselines": "SELECT COUNT(*) FROM creature_visual_baselines WHERE book_id=:b",
        "object_visual_baselines": "SELECT COUNT(*) FROM object_visual_baselines WHERE book_id=:b",
        "object_scene_states": "SELECT COUNT(*) FROM object_scene_states WHERE book_id=:b",
        "location_visual_baselines": "SELECT COUNT(*) FROM location_visual_baselines WHERE book_id=:b",
        "location_scene_states": "SELECT COUNT(*) FROM location_scene_states WHERE book_id=:b",
        "stable_character_states": "SELECT COUNT(*) FROM stable_character_states WHERE book_id=:b",
        "timeline_rows": "SELECT COUNT(*) FROM timeline_rows WHERE book_id=:b",
        "visual_prompts": "SELECT COUNT(*) FROM visual_prompts WHERE book_id=:b",
    }
    results: dict[str, int] = {}
    with STORE.session_factory() as session:
        for key, query in queries.items():
            results[key] = int(session.execute(text(query), {"b": book_id}).scalar_one())
    return results


def repair_book(book: dict[str, Any]) -> None:
    book_id = str(book["book_id"])
    book_ref = f"db://book/{book_id}"
    title = str(book["title"])
    LOGGER.info("Repair pipeline start | book=%s", title)
    DatabaseSceneEnrichmentAgent().analyze_book(book_ref=book_ref)
    DatabaseRelationshipAgent().analyze_book(book_ref=book_ref)
    DatabaseTimelineAgent().analyze_book(book_ref=book_ref)
    DatabaseStableCharacterStateAgent().analyze_book(book_ref=book_ref)
    DatabaseNonCharacterSceneStateAgent().analyze_book(book_ref=book_ref)
    DatabaseWorldStateConsolidationAgent().analyze_book(book_ref=book_ref)

    sparse = sparse_character_names(book_id)
    if sparse:
        LOGGER.info("Running character web gap fill | book=%s sparse=%s", title, len(sparse))
        DatabaseCharacterVisualBaselineAgent().backfill_web_reference_gaps(
            book_ref=book_ref,
            character_names=sparse,
        )
    counts = audit_counts(book_id)
    LOGGER.info("Repair pipeline complete | book=%s counts=%s", title, json.dumps(counts, ensure_ascii=False))


def main() -> None:
    books = list_books()
    if len(books) != 7:
        raise RuntimeError(f"Expected 7 Harry Potter EPUBs, found {len(books)}")
    build_full_series_identity(books)
    run_encode(books)
    for book in sorted(get_series_books(), key=lambda row: int(row.get("book_index") or 0)):
        if int(book.get("book_index") or 0) >= 2:
            repair_book(book)
    LOGGER.info("All remaining Harry Potter books processed and repaired.")


if __name__ == "__main__":
    main()
