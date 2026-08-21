from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

INPUT_PATH = Path(os.environ.get("SAGA_MODAL_INSPECTION_OUTPUT") or "modal-roster-inspection.json")
OUTPUT_PATH = Path(os.environ.get("SAGA_MODAL_INSPECTION_SUMMARY") or "modal-roster-inspection-summary.md")

MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".onnx"}


def _model_entries(account: dict[str, Any]) -> list[dict[str, Any]]:
    volume = account.get("volume") or {}
    entries = volume.get("entries") or []
    rows: list[dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict):
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
    accounts = [row for row in (report.get("accounts") or []) if isinstance(row, dict)]
    lines = ["# Latest Modal ComfyUI roster inspection", ""]
    lines.append(f"Accounts inspected: **{report.get('account_count', 0)}**")
    lines.append("")

    inventory: dict[str, dict[str, Any]] = {}
    accounts_by_model: dict[str, set[str]] = defaultdict(set)
    for account in accounts:
        label = str(account.get("label") or "unknown")
        for model in _model_entries(account):
            name = str(model.get("name") or "unknown")
            key = name.lower()
            inventory.setdefault(key, {"name": name, "max_size": 0, "paths": set()})
            inventory[key]["max_size"] = max(int(inventory[key]["max_size"]), int(model.get("size_bytes") or 0))
            inventory[key]["paths"].add(str(model.get("path") or ""))
            accounts_by_model[key].add(label)

    lines.append("## Aggregated model inventory")
    lines.append("")
    if inventory:
        lines.append("| Model file | Accounts | Max reported size |")
        lines.append("|---|---:|---:|")
        for key in sorted(inventory, key=lambda item: inventory[item]["name"].lower()):
            item = inventory[key]
            lines.append(
                f"| `{item['name']}` | {len(accounts_by_model[key])} | {_format_size(item['max_size'])} |"
            )
    else:
        lines.append("_No model-weight files were found in the persistent Modal cache volumes._")
    lines.append("")

    for account in accounts:
        label = str(account.get("label") or "unknown")
        app_name = str(account.get("app_name") or "")
        models = _model_entries(account)
        lines.append(f"## {label}")
        if app_name:
            lines.append(f"App: `{app_name}`")
        volume = account.get("volume") or {}
        if volume.get("volume_name"):
            lines.append(f"Volume: `{volume.get('volume_name')}`")
        lines.append(f"Model files found: **{len(models)}**")
        if models:
            names = sorted({str(item.get("name") or "unknown") for item in models}, key=str.lower)
            lines.append("Models: " + ", ".join(f"`{name}`" for name in names[:40]))
            if len(names) > 40:
                lines.append(f"...and {len(names) - 40} more unique model filenames.")
        lines.append("")

        errors = account.get("errors") or []
        if errors:
            lines.append("### Errors")
            for error in errors[:8]:
                lines.append(f"- `{str(error)[:700]}`")
            if len(errors) > 8:
                lines.append(f"- ...and {len(errors) - 8} more errors")
            lines.append("")

    OUTPUT_PATH.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    print(OUTPUT_PATH.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
