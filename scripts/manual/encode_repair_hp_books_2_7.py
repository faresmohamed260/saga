from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.db_character_profile_agent import DatabaseCharacterProfileAgent
from analysis.db_character_visual_baseline_agent import DatabaseCharacterVisualBaselineAgent
from analysis.db_character_visual_scene_state_agent import DatabaseCharacterVisualSceneStateAgent
from analysis.db_noncharacter_scene_state_agent import DatabaseNonCharacterSceneStateAgent
from analysis.db_noncharacter_visual_dossier_agent import DatabaseNonCharacterVisualDossierAgent
from analysis.db_relationship_agent import DatabaseRelationshipAgent
from analysis.db_scene_enrichment_agent import DatabaseSceneEnrichmentAgent
from analysis.db_stable_character_state_agent import DatabaseStableCharacterStateAgent
from analysis.db_timeline_agent import DatabaseTimelineAgent
from analysis.db_world_state_consolidation_agent import DatabaseWorldStateConsolidationAgent
from sql_store.persistence import SagaSQLiteStore


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
LOGGER = logging.getLogger("encode_repair_hp_books")

SERIES_ID = "hp1-full-e2e-20260615"
SERIES_TITLE = "Harry Potter Full Series DB Canon"
SERIES_IDENTITY_JSON = ROOT / "analysis_outputs" / "identity_series" / SERIES_ID / f"{SERIES_ID}_series_pipeline_identity.json"
STORE = SagaSQLiteStore()

BOOKS = [
    (2, r"D:\Books\Harry_Potter_Series\2 Harry Potter & the Chamber of Secrets.epub"),
    (3, r"D:\Books\Harry_Potter_Series\3 Harry Potter & the Prisoner of Azkaban.epub"),
    (4, r"D:\Books\Harry_Potter_Series\4 Harry Potter and the Goblet of Fire.epub"),
    (5, r"D:\Books\Harry_Potter_Series\5 Harry Potter & The Order of the Phoenix.epub"),
    (6, r"D:\Books\Harry_Potter_Series\6 Harry Potter & The Half-Blood Prince.epub"),
    (7, r"D:\Books\Harry_Potter_Series\7 Harry Potter & the Deathly Hallows.epub"),
]


def encode_book(book_index: int, path: str) -> None:
    out = ROOT / "analysis_outputs" / "encoder_validation" / f"hp_book_{book_index:02d}_encode_20260616.json"
    command = [
        sys.executable,
        "-u",
        "saga_tools.py",
        "encode-store",
        "--book",
        path,
        "--series-id",
        SERIES_ID,
        "--series-title",
        SERIES_TITLE,
        "--book-index-base",
        str(book_index),
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
        str(out),
    ]
    LOGGER.info("Encode start | book_index=%s path=%s", book_index, path)
    subprocess.run(command, cwd=ROOT, check=True)
    LOGGER.info("Encode complete | book_index=%s", book_index)


def book_row(book_index: int) -> dict[str, str]:
    rows = STORE.get_series_books(SERIES_ID)
    for row in rows:
        if int(row.get("book_index") or 0) == int(book_index):
            return row
    raise RuntimeError(f"Book index {book_index} not found in series {SERIES_ID}")


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


def assert_healthy(counts: dict[str, int], *, book_index: int) -> None:
    if counts["scenes"] <= 0:
        raise RuntimeError(f"Book {book_index}: no scenes")
    required_equal = ["scene_titles", "scene_summaries", "scene_state_changes", "scene_world_rows"]
    for key in required_equal:
        if counts[key] != counts["scenes"]:
            raise RuntimeError(f"Book {book_index}: {key}={counts[key]} but scenes={counts['scenes']}")
    required_positive = [
        "events",
        "entities",
        "character_profiles",
        "character_visual_baselines",
        "creature_visual_baselines",
        "object_visual_baselines",
        "location_visual_baselines",
        "timeline_rows",
        "visual_prompts",
    ]
    for key in required_positive:
        if counts[key] <= 0:
            raise RuntimeError(f"Book {book_index}: {key} is empty")


def repair_book(book_index: int) -> None:
    row = book_row(book_index)
    book_id = str(row["book_id"])
    book_ref = f"db://book/{book_id}"
    LOGGER.info("Repair start | book_index=%s title=%s", book_index, row["title"])
    DatabaseSceneEnrichmentAgent().analyze_book(book_ref=book_ref)
    DatabaseCharacterProfileAgent().analyze_book(book_ref=book_ref)
    DatabaseRelationshipAgent().analyze_book(book_ref=book_ref)
    DatabaseTimelineAgent().analyze_book(book_ref=book_ref)
    DatabaseStableCharacterStateAgent().analyze_book(book_ref=book_ref)
    DatabaseCharacterVisualSceneStateAgent().analyze_book(book_ref=book_ref)
    DatabaseNonCharacterVisualDossierAgent().analyze_book(book_ref=book_ref)
    DatabaseNonCharacterSceneStateAgent().analyze_book(book_ref=book_ref)
    DatabaseWorldStateConsolidationAgent().analyze_book(book_ref=book_ref)
    sparse = sparse_character_names(book_id)
    if sparse:
        LOGGER.info("Web gap fill | book_index=%s sparse_characters=%s", book_index, len(sparse))
        DatabaseCharacterVisualBaselineAgent().backfill_web_reference_gaps(
            book_ref=book_ref,
            character_names=sparse,
        )
    counts = audit_counts(book_id)
    assert_healthy(counts, book_index=book_index)
    LOGGER.info("Repair complete | book_index=%s counts=%s", book_index, json.dumps(counts, ensure_ascii=False))


def main() -> None:
    for book_index, path in BOOKS:
        encode_book(book_index, path)
        repair_book(book_index)
    LOGGER.info("Books 2-7 encoded and repaired successfully.")


if __name__ == "__main__":
    main()
