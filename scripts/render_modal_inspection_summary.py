from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

INPUT_PATH = Path(os.environ.get("SAGA_MODAL_INSPECTION_OUTPUT") or "modal-roster-inspection.json")
OUTPUT_PATH = Path(os.environ.get("SAGA_MODAL_INSPECTION_SUMMARY") or "modal-roster-inspection-summary.md")

MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf"}


def _model_entries(account: dict[str, Any]) -> list[dict[str, Any]]:
    directories = account.get("directories") or {}
    roots = directories.get("roots") or {}
    comfy_models = roots.get("comfy_models") or {}
    entries = comfy_models.get("entries") or []
    rows: list[dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        if item.get("kind") not in {"file", "symlink"}:
            continue
        name = str(item.get("name") or "")
        if Path(name).suffix.lower() not in MODEL_EXTENSIONS:
            continue
        rows.append(item)
    return sorted(rows, key=lambda row: str(row.get("path") or "").lower())


def _format_size(value: Any) -> str:
    try:
        size = int(value)
    except (TypeError, ValueError):
        return ""
    units = ["B", "KB", "MB", "GB", "TB"]
    number = float(size)
    for unit in units:
        if number < 1024 or unit == units[-1]:
            return f"{number:.1f} {unit}" if unit != "B" else f"{int(number)} B"
        number /= 1024
    return ""


def main() -> int:
    report = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    lines = ["# Latest Modal ComfyUI roster inspection", ""]
    lines.append(f"Accounts inspected: **{report.get('account_count', 0)}**")
    lines.append("")

    for account in report.get("accounts") or []:
        label = str(account.get("label") or "unknown")
        app_name = str(account.get("app_name") or "")
        lines.append(f"## {label}")
        if app_name:
            lines.append(f"App: `{app_name}`")
        lines.append("")

        models = _model_entries(account)
        lines.append(f"Model files found: **{len(models)}**")
        lines.append("")
        if models:
            lines.append("| Path | Type | Size |")
            lines.append("|---|---|---:|")
            for model in models:
                path = str(model.get("path") or "").replace("|", "\\|")
                kind = str(model.get("kind") or "")
                size = _format_size(model.get("size_bytes"))
                lines.append(f"| `{path}` | {kind} | {size} |")
        else:
            lines.append("_No model-weight files were returned by the live directory inspection._")
        lines.append("")

        errors = account.get("errors") or []
        if errors:
            lines.append("### Errors")
            for error in errors:
                lines.append(f"- `{str(error)[:1000]}`")
            lines.append("")

        directories = account.get("directories") or {}
        roots = directories.get("roots") or {}
        for root_name in ("comfy_models", "cache_weights", "cache_workflows", "comfy_custom_nodes"):
            root = roots.get(root_name) or {}
            if root:
                lines.append(
                    f"- `{root_name}`: {root.get('entry_count', 0)} entries"
                    f"{' (truncated)' if root.get('truncated') else ''}"
                )
        lines.append("")

    OUTPUT_PATH.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    print(OUTPUT_PATH.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
