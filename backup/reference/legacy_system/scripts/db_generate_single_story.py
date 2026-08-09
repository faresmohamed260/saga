from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.reasoning_runtime.client import ReasoningRuntimeClient
from saga.providers.reasoning_runtime_adapter import create_runtime_client
from saga.services.database_decoder_service import DatabaseDecoderService
from saga.services.narrative_generation_service import NarrativeGenerationService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate one DB-backed story with an explicit LLM mode.")
    parser.add_argument("--spec-path", default="", help="Optional JSON spec file with story arguments.")
    parser.add_argument("--book-ref", default="")
    parser.add_argument("--story-mode", default="")
    parser.add_argument("--chapter-count", type=int, default=20)
    parser.add_argument("--primary-pov-character", default="")
    parser.add_argument("--continuity-anchor", default="")
    parser.add_argument("--divergence-anchor", default="")
    parser.add_argument("--user-prompt", default="")
    parser.add_argument("--llm-mode", default=ReasoningRuntimeClient.MODE_CODEX)
    parser.add_argument("--out", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.spec_path:
        spec_path = Path(args.spec_path)
        spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
        for key, value in spec.items():
            attr = key.replace("-", "_")
            if hasattr(args, attr):
                setattr(args, attr, value)
    if not args.book_ref or not args.story_mode or not args.user_prompt:
        raise SystemExit("--book-ref, --story-mode, and --user-prompt are required (directly or via --spec-path).")
    llm = create_runtime_client(mode=args.llm_mode)
    decoder = NarrativeGenerationService(
        llm_client=llm,
        planner_llm_client=llm,
        prose_llm_client=llm,
    )
    service = DatabaseDecoderService(decoder=decoder)
    started = time.time()
    print(
        f"STORY_JOB_PROGRESS|starting|mode={args.story_mode}|chapters={args.chapter_count}|provider={llm.provider_name()}|model={llm.resolved_model_name()}",
        flush=True,
    )
    result = service.generate_and_store(
        book_ref=args.book_ref,
        story_mode=args.story_mode,
        user_prompt=args.user_prompt,
        chapter_count=args.chapter_count,
        primary_pov_character=args.primary_pov_character,
        continuity_anchor=args.continuity_anchor,
        divergence_anchor=args.divergence_anchor,
    )
    payload = {
        "story_mode": args.story_mode,
        "elapsed_seconds": round(time.time() - started, 2),
        "provider": llm.provider_name(),
        "model": llm.resolved_model_name(),
        "result": result,
    }
    if args.out:
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"STORY_JOB_PROGRESS|completed|mode={args.story_mode}|story_id={result.get('story_id')}|chapters={result.get('chapter_count')}|elapsed={payload['elapsed_seconds']}",
        flush=True,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
