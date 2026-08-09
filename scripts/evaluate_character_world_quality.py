"""Evaluate character/world modeling quality from a runtime report JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.character_world_modeling.contracts import CharacterWorldModelingResult
from packages.character_world_modeling.quality import evaluate_character_world_quality


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate CWM profile/world quality metrics from a report or result JSON.")
    parser.add_argument("input_json", help="Path to a CWM runtime report JSON or raw CharacterWorldModelingResult JSON.")
    parser.add_argument("--output-json", default="", help="Optional output path for metrics JSON.")
    args = parser.parse_args()

    payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    result_payload = payload.get("result") if isinstance(payload, dict) and "result" in payload else payload
    result = CharacterWorldModelingResult.model_validate(result_payload)
    metrics = evaluate_character_world_quality(result)
    output = {"series_id": result.series_id, "metrics": metrics.model_dump()}
    text = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output_json:
        Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_json).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
