from __future__ import annotations

import argparse
import contextlib
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
from scripts.manual.encode_repair_hp_books_2_7 import SERIES_ID, SERIES_TITLE, SERIES_IDENTITY_JSON, STORE, sparse_character_names, audit_counts


def book_row(book_index: int) -> dict[str, str]:
    rows = STORE.get_series_books(SERIES_ID)
    for row in rows:
        if int(row.get("book_index") or 0) == int(book_index):
            return row
    raise RuntimeError(f"Book index {book_index} not found in series {SERIES_ID}")


def encode_book(book_index: int, path: str, log_file: Path) -> None:
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
    with log_file.open("a", encoding="utf-8") as fh:
        fh.write(f"\n=== ENCODE BOOK {book_index} START ===\n")
        fh.flush()
        subprocess.run(command, cwd=ROOT, check=True, stdout=fh, stderr=fh)
        fh.write(f"\n=== ENCODE BOOK {book_index} END ===\n")


def repair_book(book_index: int, log_file: Path) -> dict[str, int]:
    row = book_row(book_index)
    book_id = str(row["book_id"])
    book_ref = f"db://book/{book_id}"
    with log_file.open("a", encoding="utf-8") as fh, contextlib.redirect_stdout(fh), contextlib.redirect_stderr(fh):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s", force=True)
        print(f"\n=== REPAIR BOOK {book_index} START ===")
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
        print(f"SPARSE_CHARACTERS={len(sparse)}")
        if sparse:
            DatabaseCharacterVisualBaselineAgent().backfill_web_reference_gaps(book_ref=book_ref, character_names=sparse)
        final_counts = audit_counts(book_id)
        print(json.dumps(final_counts, indent=2))
        print(f"=== REPAIR BOOK {book_index} END ===")
    return audit_counts(book_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book-index", type=int, required=True)
    parser.add_argument("--book-path", required=True)
    parser.add_argument("--log-file", required=True)
    args = parser.parse_args()

    log_file = Path(args.log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    encode_book(args.book_index, args.book_path, log_file)
    counts = repair_book(args.book_index, log_file)
    row = book_row(args.book_index)
    print(json.dumps({"book_id": row["book_id"], "title": row["title"], "counts": counts, "log": str(log_file)}, indent=2))


if __name__ == "__main__":
    main()
