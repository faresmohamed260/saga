"""CLI entrypoint for direct LLM-provider smoke tests."""

from __future__ import annotations

import argparse
import json

from saga.providers.llm_provider_smoke import run_llm_provider_smoke


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a direct LLM provider smoke test.")
    parser.add_argument("provider_name", choices=["ollama", "general_compute"])
    parser.add_argument("--model", required=True, help="Provider model name to probe.")
    parser.add_argument("--prompt", default='Return exactly this JSON object: {"ok": true}')
    parser.add_argument("--output-root", default="", help="Optional output root for smoke artifacts.")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    args = parser.parse_args()

    payload = run_llm_provider_smoke(
        args.provider_name,
        model_name=args.model,
        prompt=args.prompt,
        output_root=args.output_root or None,
        timeout_seconds=max(10, int(args.timeout_seconds)),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
