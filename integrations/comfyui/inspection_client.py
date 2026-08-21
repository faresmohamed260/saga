from __future__ import annotations

import json
from typing import Any

try:
    from integrations.comfyui.token_pool import ModalToken
    from integrations.comfyui.workspace_client import PYTHON_EXE, _run
except ImportError:  # pragma: no cover
    from token_pool import ModalToken
    from workspace_client import PYTHON_EXE, _run


def invoke_directory_inspection(
    token: ModalToken,
    app_name: str,
    *,
    timeout: int = 600,
    hf_token: str = "",
) -> dict[str, Any]:
    script = f'''
import json
import modal
fn = modal.Function.from_name({app_name!r}, "inspect_runtime_directories")
print(json.dumps(fn.remote(), ensure_ascii=False))
'''
    result = _run([str(PYTHON_EXE), "-c", script], token=token, timeout=timeout, hf_token=hf_token)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "modal directory inspection failed")
    try:
        return json.loads((result.stdout or "").strip())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse directory inspection payload: {(result.stdout or '').strip()}") from exc
