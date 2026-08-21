from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    from integrations.comfyui.modal_app import CACHE_DIR, COMFY_DIR, app, cache_volume, image
except ImportError:  # pragma: no cover
    from modal_app import CACHE_DIR, COMFY_DIR, app, cache_volume, image


# Intentionally fixed: callers cannot request arbitrary filesystem paths.
INSPECTION_ROOTS: dict[str, tuple[Path, int, int]] = {
    "comfy_models": (Path(COMFY_DIR) / "models", 4, 1200),
    "comfy_custom_nodes": (Path(COMFY_DIR) / "custom_nodes", 3, 600),
    "cache_weights": (Path(CACHE_DIR) / "weights", 3, 400),
    "cache_workflows": (Path(CACHE_DIR) / "workflows", 3, 400),
    # Shallow listing exposes Hugging Face cache repository directories without
    # recursively dumping every cached blob.
    "cache_root": (Path(CACHE_DIR), 2, 800),
}

_DENIED_BASENAMES = {
    ".env",
    "credentials",
    "credentials.json",
    "secrets",
    "secrets.json",
    "token",
    "tokens",
    "auth",
}
_DENIED_SUFFIXES = {".key", ".pem", ".p12", ".pfx"}


def _is_sensitive_name(name: str) -> bool:
    lowered = name.lower()
    if lowered in _DENIED_BASENAMES or lowered.startswith(".env."):
        return True
    return any(lowered.endswith(suffix) for suffix in _DENIED_SUFFIXES)


def _entry_metadata(path: Path, root: Path) -> dict[str, Any]:
    stat_result = path.lstat()
    is_symlink = path.is_symlink()
    if is_symlink:
        kind = "symlink"
    elif path.is_dir():
        kind = "directory"
    elif path.is_file():
        kind = "file"
    else:
        kind = "other"
    return {
        "path": path.relative_to(root).as_posix(),
        "name": path.name,
        "kind": kind,
        "size_bytes": int(stat_result.st_size) if kind == "file" else None,
        "is_symlink": is_symlink,
        "modified_at_ns": int(stat_result.st_mtime_ns),
    }


def _list_root(root: Path, *, max_depth: int, max_entries: int) -> dict[str, Any]:
    result: dict[str, Any] = {
        "root": str(root),
        "exists": root.exists(),
        "max_depth": max_depth,
        "max_entries": max_entries,
        "entries": [],
        "truncated": False,
        "redacted_entries": 0,
        "errors": [],
    }
    if not root.exists():
        return result

    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack and len(result["entries"]) < max_entries:
        current, depth = stack.pop()
        if depth >= max_depth:
            continue
        try:
            children = sorted(current.iterdir(), key=lambda item: item.name.lower(), reverse=True)
        except (OSError, PermissionError) as exc:
            result["errors"].append({"path": str(current), "error": type(exc).__name__})
            continue

        for child in children:
            if len(result["entries"]) >= max_entries:
                result["truncated"] = True
                break
            if _is_sensitive_name(child.name):
                result["redacted_entries"] += 1
                continue
            try:
                metadata = _entry_metadata(child, root)
            except (OSError, PermissionError) as exc:
                result["errors"].append({"path": str(child), "error": type(exc).__name__})
                continue
            result["entries"].append(metadata)
            # Never follow symlinks. This keeps inspection bounded to the selected
            # directory tree and prevents traversal into unrelated paths.
            if metadata["kind"] == "directory" and not metadata["is_symlink"]:
                stack.append((child, depth + 1))

    if stack:
        result["truncated"] = True
    result["entry_count"] = len(result["entries"])
    return result


@app.function(
    image=image,
    timeout=300,
    volumes={CACHE_DIR: cache_volume},
)
def inspect_runtime_directories() -> dict[str, Any]:
    """Return metadata-only listings for a fixed allowlist of ComfyUI/cache directories.

    This function is deliberately read-only: it never opens file contents, writes files,
    follows symlinks, accepts caller-provided paths, or returns environment variables.
    """
    return {
        "read_only": True,
        "pid": os.getpid(),
        "roots": {
            label: _list_root(path, max_depth=max_depth, max_entries=max_entries)
            for label, (path, max_depth, max_entries) in INSPECTION_ROOTS.items()
        },
    }
