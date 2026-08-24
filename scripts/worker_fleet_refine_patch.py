from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Expected source fragment not found in {path}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


for gateway in (
    "integrations/comfyui/flux2_klein_gateway.py",
    "integrations/comfyui/ltx23_gateway.py",
):
    replace_once(
        gateway,
        '''    def _state():\n        try:\n            return worker_state.get("worker") or {"state": "sleeping", "worker_id": WORKER_ID, "ecosystem": ECOSYSTEM_ID}\n        except Exception:\n            return {"state": "unknown", "worker_id": WORKER_ID, "ecosystem": ECOSYSTEM_ID}\n''',
        '''    def _state():\n        try:\n            return worker_state.get("worker") or {"state": "sleeping", "worker_id": WORKER_ID, "ecosystem": ECOSYSTEM_ID}\n        except Exception:\n            return {"state": "unknown", "worker_id": WORKER_ID, "ecosystem": ECOSYSTEM_ID}\n\n    def _submit_state():\n        state = str(_state().get("state") or "").strip()\n        return "waking" if state in {"", "sleeping", "unknown"} else state\n''',
    )

replace_once(
    "integrations/comfyui/flux2_klein_gateway.py",
    '            current = _state()\n            return {"status": "queued", "call_id": call.object_id, "reference_count": len(images), "worker_state": current.get("state") or "waking", "worker_id": WORKER_ID, "ecosystem": ECOSYSTEM_ID}\n',
    '            return {"status": "queued", "call_id": call.object_id, "reference_count": len(images), "worker_state": _submit_state(), "worker_id": WORKER_ID, "ecosystem": ECOSYSTEM_ID}\n',
)

replace_once(
    "integrations/comfyui/ltx23_gateway.py",
    '                "worker_state": (_state().get("state") or "waking"),\n',
    '                "worker_state": _submit_state(),\n',
)

ltx_path = "integrations/comfyui/ltx23_app.py"
replace_once(
    ltx_path,
    '    @modal.method()\n    def generate(\n',
    '    def _generate_impl(\n',
)

wrapper = '''\n    @modal.method()\n    def generate(\n        self,\n        prompt: str,\n        negative_prompt: str = "",\n        seed: int = 42,\n        resolution: str = "480p",\n        duration_seconds: int = 5,\n        audio_enabled: bool = True,\n        aspect_ratio: str = "16:9",\n        frame_rate: int = DEFAULT_FPS,\n        source_image: bytes | None = None,\n    ) -> bytes:\n        try:\n            return self._generate_impl(\n                prompt=prompt,\n                negative_prompt=negative_prompt,\n                seed=seed,\n                resolution=resolution,\n                duration_seconds=duration_seconds,\n                audio_enabled=audio_enabled,\n                aspect_ratio=aspect_ratio,\n                frame_rate=frame_rate,\n                source_image=source_image,\n            )\n        except Exception:\n            _set_worker_state("failed")\n            raise\n\n'''
replace_once(
    ltx_path,
    '    @modal.exit()\n    def stop(self) -> None:\n',
    wrapper + '    @modal.exit()\n    def stop(self) -> None:\n',
)

print("Worker fleet refinement patch applied.")
