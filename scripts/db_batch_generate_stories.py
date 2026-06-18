from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from saga.services.database_decoder_service import DatabaseDecoderService


DEFAULT_STORIES = [
    {
        "story_mode": "pre_canon",
        "chapter_count": 20,
        "primary_pov_character": "Lily Evans",
        "continuity_anchor": "before Harry Potter book 1 and before Hogwarts letters are sent",
        "divergence_anchor": "",
        "user_prompt": (
            "Write a long complete pre-canon Harry Potter novel in 20 chapters about Lily Evans and "
            "Severus Snape from childhood through the worsening strain on their friendship before Hogwarts, "
            "with grounded magic, class tension, and emotional continuity."
        ),
    },
    {
        "story_mode": "mid_canon",
        "chapter_count": 20,
        "primary_pov_character": "Hermione Granger",
        "continuity_anchor": "during Harry Potter book 1 before the climax",
        "divergence_anchor": "",
        "user_prompt": (
            "Write a long complete mid-canon Harry Potter novel in 20 chapters about Hermione Granger "
            "discovering a hidden library clue at Hogwarts during first year, while preserving canon outcomes."
        ),
    },
    {
        "story_mode": "post_canon",
        "chapter_count": 20,
        "primary_pov_character": "Ginny Weasley",
        "continuity_anchor": "after the end of Harry Potter and the Deathly Hallows",
        "divergence_anchor": "",
        "user_prompt": (
            "Write a long complete post-canon Harry Potter novel in 20 chapters about Ginny Weasley balancing "
            "public life, family strain, and a new magical threat tied to old war scars."
        ),
    },
    {
        "story_mode": "alternate_universe",
        "chapter_count": 20,
        "primary_pov_character": "Neville Longbottom",
        "continuity_anchor": "during Harry Potter book 5 inside Hogwarts",
        "divergence_anchor": "Umbridge remains in power at Hogwarts much longer than canon",
        "user_prompt": (
            "Write a long complete alternate-universe Harry Potter novel in 20 chapters where Dolores Umbridge "
            "keeps control of Hogwarts far longer than canon and Neville Longbottom builds a covert resistance network."
        ),
    },
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate long-form DB-native decoder stories in sequence.")
    parser.add_argument("--book-ref", required=True, help="Canonical DB ref like db://book/<book_id>.")
    parser.add_argument("--out", default="analysis_outputs/dashboard/generated_story_batch_report.json", help="JSON report path.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    service = DatabaseDecoderService()
    report_rows: list[dict[str, object]] = []
    started_at = time.time()
    for spec in DEFAULT_STORIES:
        row = dict(spec)
        row["started_at_epoch"] = time.time()
        print(
            f"STORY_BATCH_PROGRESS|starting|{spec['story_mode']}|chapters={spec['chapter_count']}|pov={spec['primary_pov_character']}",
            flush=True,
        )
        try:
            result = service.generate_and_store(book_ref=args.book_ref, **spec)
            row["result"] = result
            row["status"] = "success"
            print(
                f"STORY_BATCH_PROGRESS|completed|{spec['story_mode']}|story_id={result.get('story_id')}|chapters={result.get('chapter_count')}",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            row["status"] = "failed"
            row["error"] = repr(exc)
            print(f"STORY_BATCH_PROGRESS|failed|{spec['story_mode']}|error={repr(exc)}", flush=True)
            report_rows.append(row)
            break
        row["elapsed_seconds"] = round(time.time() - row["started_at_epoch"], 2)
        report_rows.append(row)
    payload = {
        "book_ref": args.book_ref,
        "elapsed_seconds": round(time.time() - started_at, 2),
        "stories": report_rows,
    }
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
