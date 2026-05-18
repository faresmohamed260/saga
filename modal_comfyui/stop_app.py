from __future__ import annotations

import argparse

import modal


def main() -> None:
    parser = argparse.ArgumentParser(description="Stop a deployed Modal ComfyUI app.")
    parser.add_argument("--app-name", default="graduation-comfyui", help="Modal app name to stop.")
    args = parser.parse_args()
    modal.App.stop(args.app_name)
    print(f"Stopped app: {args.app_name}")


if __name__ == "__main__":
    main()
