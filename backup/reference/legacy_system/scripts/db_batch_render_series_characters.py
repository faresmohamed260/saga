from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from saga.services.comfyui_character_sheet_service import ComfyUICharacterSheetService
from saga.storage.persistence import SagaSQLiteStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render DB-native character images for every book in a series.")
    parser.add_argument("--series-id", required=True, help="Series identifier stored in SQLite.")
    parser.add_argument("--limit-per-book", type=int, default=0, help="Optional render cap per book.")
    parser.add_argument("--overwrite", action="store_true", help="Force re-render even if an image already exists.")
    parser.add_argument("--out", default="analysis_outputs/dashboard/series_character_render_report.json", help="JSON report path.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    sqlite_store = SagaSQLiteStore()
    service = ComfyUICharacterSheetService()
    started_at = time.time()
    books = sqlite_store.get_series_books(args.series_id)
    report_rows: list[dict[str, object]] = []
    for book in sorted(books, key=lambda row: int(row.get("book_index") or 0)):
        book_ref = f"db://book/{book.get('book_id')}"
        book_started = time.time()
        manifest = service.render_from_contract(
            book_ref,
            limit=int(args.limit_per_book or 0),
            overwrite=bool(args.overwrite),
            entity_types={"character"},
        )
        renders = manifest.get("renders") or []
        report_rows.append(
            {
                "book_ref": book_ref,
                "book_index": book.get("book_index"),
                "book_title": book.get("title"),
                "render_count": len(renders),
                "rendered_count": sum(1 for row in renders if str(row.get("status") or "").strip().lower() == "rendered"),
                "skipped_existing_count": sum(1 for row in renders if str(row.get("status") or "").strip().lower() == "skipped_existing"),
                "failed_count": sum(1 for row in renders if str(row.get("status") or "").strip().lower() == "failed"),
                "elapsed_seconds": round(time.time() - book_started, 2),
            }
        )
    payload = {
        "series_id": args.series_id,
        "book_count": len(report_rows),
        "elapsed_seconds": round(time.time() - started_at, 2),
        "books": report_rows,
    }
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
