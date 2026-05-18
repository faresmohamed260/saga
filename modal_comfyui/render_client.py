from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parent
POOL_CLI = MODULE_DIR / "pool_cli.py"
APP_FILE = MODULE_DIR / "modal_app.py"
DEFAULT_OUTPUT_DIR = MODULE_DIR / "outputs"
MODAL_EXE = Path(sys.executable).with_name("modal.exe")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate an image through Modal + ComfyUI with token failover."
    )
    parser.add_argument("--prompt", required=True, help="Positive prompt text.")
    parser.add_argument(
        "--negative-prompt",
        default="blurry, low quality, distorted hands, artifacts",
        help="Negative prompt text.",
    )
    parser.add_argument("--seed", type=int, default=5, help="Sampling seed.")
    parser.add_argument("--steps", type=int, default=20, help="Sampler steps.")
    parser.add_argument("--cfg", type=float, default=8.0, help="CFG scale.")
    parser.add_argument("--width", type=int, default=512, help="Image width.")
    parser.add_argument("--height", type=int, default=512, help="Image height.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "render.png",
        help="Where to save the generated PNG.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        str(POOL_CLI),
        "--retry-any-error",
        "--prefer-warm",
        "--mark-render-success",
        "--",
        str(MODAL_EXE),
        "run",
        str(APP_FILE),
        "--prompt",
        args.prompt,
        "--negative-prompt",
        args.negative_prompt,
        "--seed",
        str(args.seed),
        "--steps",
        str(args.steps),
        "--cfg",
        str(args.cfg),
        "--width",
        str(args.width),
        "--height",
        str(args.height),
        "--output-path",
        str(args.output),
    ]
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
