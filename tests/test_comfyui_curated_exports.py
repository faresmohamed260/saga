from __future__ import annotations

from pathlib import Path

from query.comfyui_prompt_pack_service import ComfyUIPromptPackService
from saga_tools import _write_comfyui_curated_preview, _write_comfyui_text_exports
from tests.test_comfyui_prompt_pack_service import _visual_payload


def test_text_exports_and_preview_are_written(tmp_path: Path) -> None:
    service = ComfyUIPromptPackService()
    prompt_pack = service.build(visual_state=_visual_payload())
    curated = service.build_curated_test_pack(prompt_pack)
    export_dir = _write_comfyui_text_exports(tmp_path / "exports", curated)
    preview = _write_comfyui_curated_preview(tmp_path / "preview.md", curated)
    assert export_dir.exists()
    assert preview.exists()
    assert any(path.name.endswith("_positive.txt") for path in export_dir.iterdir())
    assert any(path.name.endswith("_negative.txt") for path in export_dir.iterdir())
