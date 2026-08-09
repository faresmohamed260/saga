from __future__ import annotations

import json
import uuid
from pathlib import Path


def load_workflow_json(workflow_path: str | Path) -> dict:
    return json.loads(Path(workflow_path).read_text(encoding="utf-8-sig"))


def warmup_prompt_identity(label: str, prompt_uuid: uuid.UUID) -> tuple[str, str]:
    prompt_id = str(prompt_uuid)
    return prompt_id, f"warmup-{label}-{prompt_id[:8]}"
