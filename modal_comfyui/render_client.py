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
    parser.add_argument("--prompt", default="", help="Positive prompt text.")
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=None,
        help="Optional JSON manifest for batch renders.",
    )
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
        "--workflow-mode",
        default="default",
        choices=["default", "character_sheet"],
        help="Workflow mode to execute inside Modal ComfyUI.",
    )
    parser.add_argument(
        "--pose-image-path",
        type=Path,
        default=None,
        help="Optional pose image path for character-sheet workflows.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "render.png",
        help="Where to save the generated PNG.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional output directory for batch renders.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=None,
        help="Optional JSON report path for batch renders.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.prompt and not args.manifest_path:
        raise SystemExit("Either --prompt or --manifest-path is required.")
    if args.manifest_path:
        (args.output_dir or DEFAULT_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
        if args.report_path:
            args.report_path.parent.mkdir(parents=True, exist_ok=True)
    else:
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
        "--workflow-mode",
        args.workflow_mode,
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
    ]
    if args.pose_image_path:
        command.extend(["--pose-image-path", str(args.pose_image_path)])
    if args.manifest_path:
        command.extend(["--manifest-path", str(args.manifest_path)])
        command.extend(["--output-dir", str(args.output_dir or DEFAULT_OUTPUT_DIR)])
        if args.report_path:
            command.extend(["--report-path", str(args.report_path)])
    else:
        command.extend(["--prompt", args.prompt, "--output-path", str(args.output)])
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
