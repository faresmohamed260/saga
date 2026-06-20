from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from token_pool import (
    DEFAULT_STATE_PATH,
    DEFAULT_TOKENS_PATH,
    DEFAULT_WARM_TTL_SECONDS,
    load_start_index,
    load_tokens,
    mark_render_success,
    rotate_from,
    rotate_prefer_warm,
    save_next_index,
    update_token_stat,
)


CREDIT_PATTERNS = (
    "credit",
    "credits",
    "quota",
    "budget",
    "billing",
    "payment",
    "insufficient",
    "limit exceeded",
    "exceeded your spending",
    "workspace budget",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Modal commands against a token pool with automatic failover."
    )
    parser.add_argument(
        "--tokens-file",
        type=Path,
        default=DEFAULT_TOKENS_PATH,
        help="JSON file containing the Modal token pool.",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=DEFAULT_STATE_PATH,
        help="Local state file storing which token to try first next time.",
    )
    parser.add_argument(
        "--retry-any-error",
        action="store_true",
        help="Retry on any non-zero exit code instead of only obvious billing/quota failures.",
    )
    parser.add_argument(
        "--prefer-warm",
        action="store_true",
        help="Try tokens with a recently successful render first.",
    )
    parser.add_argument(
        "--mark-render-success",
        action="store_true",
        help="Record the winning token as warm after a successful render-like command.",
    )
    parser.add_argument(
        "--warm-ttl-seconds",
        type=int,
        default=DEFAULT_WARM_TTL_SECONDS,
        help="How long a successful render keeps a token marked as warm.",
    )
    parser.add_argument(
        "--command-timeout-seconds",
        type=int,
        default=180,
        help="Maximum seconds to wait for the wrapped command before treating it as a failed token attempt.",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command to run. Example: modal run integrations/comfyui/modal_app.py --prompt \"test\"",
    )
    return parser


def is_credit_failure(stdout: str, stderr: str) -> bool:
    haystack = f"{stdout}\n{stderr}".lower()
    return any(pattern in haystack for pattern in CREDIT_PATTERNS)


def emit_text(stream, text: str) -> None:
    if not text:
        return
    encoding = getattr(stream, "encoding", None) or "utf-8"
    safe = text.encode(encoding, errors="backslashreplace").decode(encoding, errors="replace")
    stream.write(safe)
    stream.flush()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("Please provide a command to run after the pool_cli arguments.")

    tokens = load_tokens(args.tokens_file)
    start_index = load_start_index(args.state_file)
    ordered_tokens = (
        rotate_prefer_warm(tokens, start_index, state_path=args.state_file)
        if args.prefer_warm
        else rotate_from(tokens, start_index)
    )

    last_returncode = 1
    for index, token in ordered_tokens:
        env = os.environ.copy()
        env["MODAL_TOKEN_ID"] = token.token_id
        env["MODAL_TOKEN_SECRET"] = token.token_secret
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        print(f"[modal-pool] trying token '{token.name}'", file=sys.stderr)
        try:
            result = subprocess.run(
                command,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(1, int(args.command_timeout_seconds or 180)),
            )

            emit_text(sys.stdout, result.stdout)
            emit_text(sys.stderr, result.stderr)

            if result.returncode == 0:
                save_next_index(index + 1, args.state_file)
                update_token_stat(token.name, state_path=args.state_file, health_ok=True, last_error="")
                if args.mark_render_success:
                    mark_render_success(
                        token.name,
                        state_path=args.state_file,
                        warm_ttl_seconds=args.warm_ttl_seconds,
                    )
                print(f"[modal-pool] succeeded with token '{token.name}'", file=sys.stderr)
                return 0

            last_returncode = result.returncode
            tail_error = (result.stderr or result.stdout).strip().splitlines()
            update_token_stat(
                token.name,
                state_path=args.state_file,
                health_ok=False,
                last_error=tail_error[-1] if tail_error else f"returncode={result.returncode}",
            )
            should_retry = args.retry_any_error or is_credit_failure(result.stdout, result.stderr)
            if should_retry:
                print(
                    f"[modal-pool] token '{token.name}' failed with a retryable error, rotating...",
                    file=sys.stderr,
                )
                continue

            print(
                f"[modal-pool] token '{token.name}' failed with a non-retryable error, stopping.",
                file=sys.stderr,
            )
            return result.returncode
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            emit_text(sys.stdout, stdout)
            emit_text(sys.stderr, stderr)
            timeout_message = f"[modal-pool] token '{token.name}' timed out after {max(1, int(args.command_timeout_seconds or 180))}s"
            print(timeout_message, file=sys.stderr)
            update_token_stat(
                token.name,
                state_path=args.state_file,
                health_ok=False,
                last_error=timeout_message,
            )
            last_returncode = 124
            if args.retry_any_error:
                print(
                    f"[modal-pool] token '{token.name}' timed out, rotating...",
                    file=sys.stderr,
                )
                continue
            return last_returncode

    print("[modal-pool] all tokens failed.", file=sys.stderr)
    return last_returncode


if __name__ == "__main__":
    raise SystemExit(main())
