"""Run bounded, resumable local-model qualification on the real-book corpus."""

from __future__ import annotations

import argparse
import ctypes
import json
import statistics
import sys
import threading
from pathlib import Path
from typing import Any

import psutil

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.reasoning.task_suite import TASK_FAMILIES, build_tasks, evaluate_task
from packages.reasoning_runtime import (
    JsonQualificationCheckpointStore,
    ReasoningProfile,
    ReasoningQualificationRunner,
    ReasoningRuntimeConfig,
    create_reasoning_client,
)


class LocalResourceMonitor:
    """Sample host and NVIDIA usage without coupling it to inference providers."""

    def __init__(self, interval_seconds: float = 0.5) -> None:
        self.interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._baseline: dict[str, int] = {}
        self._peak: dict[str, int] = {}
        self._nvml = NvmlMemoryReader()

    def start(self) -> None:
        self._sample()
        self._baseline = dict(self._peak)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
        self._sample()
        metrics = {
            "baseline_host_used_bytes": self._baseline.get("host_used_bytes", 0),
            "peak_host_used_bytes": self._peak.get("host_used_bytes", 0),
            "baseline_vram_used_bytes": self._baseline.get("vram_used_bytes", 0),
            "peak_vram_used_bytes": self._peak.get("vram_used_bytes", 0),
        }
        self._nvml.close()
        return metrics

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self._sample()

    def _sample(self) -> None:
        values = {
            "host_used_bytes": int(psutil.virtual_memory().used),
            "vram_used_bytes": self._nvml.used_bytes(),
        }
        for key, value in values.items():
            self._peak[key] = max(self._peak.get(key, 0), value)


class NvmlMemoryReader:
    class Memory(ctypes.Structure):
        _fields_ = [
            ("total", ctypes.c_ulonglong),
            ("free", ctypes.c_ulonglong),
            ("used", ctypes.c_ulonglong),
        ]

    def __init__(self) -> None:
        self._library: Any | None = None
        self._handle = ctypes.c_void_p()
        loader = getattr(ctypes, "WinDLL", ctypes.CDLL)
        for library_name in ("nvml.dll", "libnvidia-ml.so.1"):
            try:
                library = loader(library_name)
                library.nvmlInit_v2.restype = ctypes.c_int
                library.nvmlDeviceGetHandleByIndex_v2.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)]
                library.nvmlDeviceGetHandleByIndex_v2.restype = ctypes.c_int
                library.nvmlDeviceGetMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(self.Memory)]
                library.nvmlDeviceGetMemoryInfo.restype = ctypes.c_int
                if library.nvmlInit_v2() == 0 and library.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(self._handle)) == 0:
                    self._library = library
                    break
            except (AttributeError, OSError):
                continue

    def used_bytes(self) -> int:
        if self._library is None:
            return 0
        memory = self.Memory()
        return int(memory.used) if self._library.nvmlDeviceGetMemoryInfo(self._handle, ctypes.byref(memory)) == 0 else 0

    def close(self) -> None:
        if self._library is not None:
            self._library.nvmlShutdown()
            self._library = None


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Exact local Ollama model tag.")
    parser.add_argument("--corpus", default="analysis_outputs/local_reasoning/corpus_v1.json")
    parser.add_argument("--checkpoints", default="analysis_outputs/local_reasoning/qualification")
    parser.add_argument("--scope", choices=("screening", "full"), default="screening")
    parser.add_argument("--task-family", action="append", choices=TASK_FAMILIES)
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--context-tokens", type=int, default=4096)
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if not 1 <= args.timeout_seconds <= 300:
        raise SystemExit("--timeout-seconds must be between 1 and 300.")
    if args.repetitions < 1:
        raise SystemExit("--repetitions must be positive.")

    corpus_path = Path(args.corpus).resolve()
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    tasks = build_tasks(corpus, scope=args.scope)
    if args.task_family:
        selected = set(args.task_family)
        tasks = [task for task in tasks if task.metadata.get("family") in selected]
    if args.case_id:
        selected_cases = set(args.case_id)
        tasks = [task for task in tasks if task.metadata.get("case_id") in selected_cases]
    if not tasks:
        raise SystemExit("No qualification tasks matched the requested filters.")

    profile = ReasoningProfile(
        name="qualification-local", mode="ollama_local", ollama_model=args.model,
        timeout_seconds=args.timeout_seconds, max_retries=1,
        allow_account_rotation=False, context_window_tokens=args.context_tokens,
    )
    client = create_reasoning_client(
        profile_name=profile.name,
        profile=profile,
        config=ReasoningRuntimeConfig(profiles={profile.name: profile}),
    )
    checkpoint_root = Path(args.checkpoints).resolve()
    runner = ReasoningQualificationRunner(
        checkpoint_store=JsonQualificationCheckpointStore(checkpoint_root),
        max_request_seconds=args.timeout_seconds,
        resource_monitor_factory=LocalResourceMonitor,
    )
    trials = runner.run_model(
        suite_id=str(corpus["suite_id"]), corpus_version=str(corpus["corpus_version"]),
        client=client, tasks=tasks, repetitions=args.repetitions, evaluator=evaluate_task,
        run_variant=f"ollama-ctx{args.context_tokens}",
    )
    wall_times = [trial.wall_seconds for trial in trials]
    summary = {
        "model": args.model,
        "scope": args.scope,
        "selected_tasks": len(tasks),
        "completed_trials": len(trials),
        "accepted": sum(trial.status == "accepted" for trial in trials),
        "rejected": sum(trial.status == "rejected" for trial in trials),
        "failed": sum(trial.status == "failed" for trial in trials),
        "median_wall_seconds": round(statistics.median(wall_times), 3) if wall_times else None,
        "checkpoint_root": str(checkpoint_root),
    }
    print(json.dumps(summary, indent=2))
    return 2 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
