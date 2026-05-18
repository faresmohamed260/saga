from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from token_pool import DEFAULT_STATE_PATH, DEFAULT_TOKENS_PATH, is_token_warm, load_token_stats, load_tokens, update_token_stat


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cheap health check for Modal token pool entries.")
    parser.add_argument("--tokens-file", type=Path, default=DEFAULT_TOKENS_PATH)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="How many tokens to test. Use 0 or a negative number to test all tokens.",
    )
    parser.add_argument(
        "--modal-exe",
        type=Path,
        default=Path(sys.executable).with_name("modal.exe"),
        help="Path to the Modal executable.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    tokens = load_tokens(args.tokens_file)
    if args.limit > 0:
        tokens = tokens[: args.limit]

    results: list[dict[str, object]] = []

    for token in tokens:
        env = os.environ.copy()
        env["MODAL_TOKEN_ID"] = token.token_id
        env["MODAL_TOKEN_SECRET"] = token.token_secret
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(
            [str(args.modal_exe), "app", "list", "--json"],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        ok = result.returncode == 0
        tail_error = (result.stderr or result.stdout).strip().splitlines()
        update_token_stat(
            token.name,
            state_path=args.state_file,
            health_ok=ok,
            last_error="" if ok else (tail_error[-1] if tail_error else f"returncode={result.returncode}"),
        )
        stats = load_token_stats(args.state_file).get(token.name, {})
        results.append(
            {
                "name": token.name,
                "ok": ok,
                "warm": is_token_warm(token.name, state_path=args.state_file),
                "last_render_ok": stats.get("last_render_ok"),
                "message": "ok" if ok else (tail_error[-1] if tail_error else "unknown error"),
            }
        )

    print(json.dumps(results, indent=2))
    return 0 if all(item["ok"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
