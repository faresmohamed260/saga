"""Create a secret-safe immutable release-candidate bundle."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from packages.deployment_runtime.candidate import create_release_candidate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--runtime-digest", required=True)
    parser.add_argument("--dashboard-digest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    git_sha = _git(root, "rev-parse", "HEAD")
    if _git(root, "status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("Release candidates require a clean worktree.")
    candidate = create_release_candidate(
        version=args.version,
        git_sha=git_sha,
        runtime_digest=args.runtime_digest,
        dashboard_digest=args.dashboard_digest,
        configuration={"schema_revision": "from-runtime-contract"},
    )
    target = Path(args.output).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(candidate.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"release_id": candidate.manifest.release_id, "candidate_sha256": candidate.candidate_sha256}))
    return 0


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
