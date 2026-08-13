"""Compile qualification checkpoints into a versioned routing scorecard."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.reasoning.scorecard import build_scorecard
from benchmarks.reasoning.task_suite import TASK_SUITE_VERSION
from packages.reasoning_runtime import QualificationTrial


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoints", default="analysis_outputs/local_reasoning/qualification")
    parser.add_argument("--output", default="analysis_outputs/local_reasoning/scorecard.json")
    parser.add_argument("--scope", choices=("screening", "full"), default="full")
    args = parser.parse_args()

    trials = []
    for path in sorted(Path(args.checkpoints).resolve().glob("reasoning-trial-*.json")):
        trial = QualificationTrial.model_validate_json(path.read_text(encoding="utf-8"))
        if trial.run_variant.startswith(f"tasks-{TASK_SUITE_VERSION}-{args.scope}-"):
            trials.append(trial)
    scorecard = build_scorecard(
        trials, minimum_sources=3 if args.scope == "full" else 1,
        required_families=TASK_FAMILIES,
    )
    payload = {"task_suite_version": TASK_SUITE_VERSION, **scorecard}
    target = Path(args.output).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(target)
    print(json.dumps({"trial_count": len(trials), "routes": payload["routes"], "output": str(target)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
