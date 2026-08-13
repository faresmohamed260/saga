"""Run bounded, resumable local-model qualification on the real-book corpus."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import statistics
import sys
import threading
import time
from pathlib import Path
from typing import Any

import psutil
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.reasoning.task_suite import TASK_FAMILIES, TASK_SUITE_VERSION, build_tasks, evaluate_task
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
            "peak_host_cpu_percent": self._peak.get("host_cpu_percent", 0),
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
            "host_cpu_percent": int(round(psutil.cpu_percent(interval=None))),
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
    parser.add_argument("--load-timeout-seconds", type=int, default=180)
    parser.add_argument("--context-tokens", type=int, default=4096)
    parser.add_argument("--keep-alive", default="30m")
    parser.add_argument("--gpu-layers", type=int, default=32)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--max-vram-gib", type=float, default=10.0)
    parser.add_argument("--max-host-ram-gib", type=float, default=112.0)
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if not 1 <= args.timeout_seconds <= 300:
        raise SystemExit("--timeout-seconds must be between 1 and 300.")
    if not 1 <= args.load_timeout_seconds <= 300:
        raise SystemExit("--load-timeout-seconds must be between 1 and 300.")
    if args.repetitions < 1:
        raise SystemExit("--repetitions must be positive.")
    if args.gpu_layers < 0 or args.threads < 1:
        raise SystemExit("Resource allocation values are invalid.")

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

    checkpoint_root = Path(args.checkpoints).resolve()
    config = ReasoningRuntimeConfig()
    evicted_models = _unload_other_models(
        requested_model=args.model, generate_url=config.ollama_local_url,
    )
    load_evidence = _prepare_local_model(
        model=args.model, url=config.ollama_local_url,
        keep_alive=args.keep_alive, timeout_seconds=args.load_timeout_seconds,
        context_tokens=args.context_tokens, gpu_layers=args.gpu_layers,
        threads=args.threads,
    )
    load_evidence["evicted_models"] = evicted_models
    _save_load_evidence(checkpoint_root, args.model, args.context_tokens, load_evidence)

    profile = ReasoningProfile(
        name="qualification-local", mode="ollama_local", ollama_model=args.model,
        timeout_seconds=args.timeout_seconds, max_retries=1,
        allow_account_rotation=False, context_window_tokens=args.context_tokens,
        ollama_keep_alive=args.keep_alive,
        ollama_gpu_layers=args.gpu_layers, ollama_threads=args.threads,
    )
    config.profiles[profile.name] = profile
    client = create_reasoning_client(
        profile_name=profile.name,
        profile=profile,
        config=config,
    )
    runner = ReasoningQualificationRunner(
        checkpoint_store=JsonQualificationCheckpointStore(checkpoint_root),
        max_request_seconds=args.timeout_seconds,
        min_trials_before_elimination=(len(tasks) * args.repetitions + 1) if args.scope == "screening" else 3,
        resource_monitor_factory=LocalResourceMonitor,
        max_peak_vram_bytes=int(args.max_vram_gib * 1024 ** 3),
        max_peak_host_ram_bytes=int(args.max_host_ram_gib * 1024 ** 3),
    )
    trials = runner.run_model(
        suite_id=str(corpus["suite_id"]), corpus_version=str(corpus["corpus_version"]),
        client=client, tasks=tasks, repetitions=args.repetitions, evaluator=evaluate_task,
        run_variant=(f"tasks-{TASK_SUITE_VERSION}-{args.scope}-ollama-ctx{args.context_tokens}"
                     f"-gpu{args.gpu_layers}-threads{args.threads}"),
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
        "model_load_wall_seconds": load_evidence["wall_seconds"],
    }
    print(json.dumps(summary, indent=2))
    return 2 if summary["failed"] else 0


def _prepare_local_model(
    *, model: str, url: str, keep_alive: str, timeout_seconds: int,
    context_tokens: int, gpu_layers: int, threads: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    response = requests.post(
        url,
        json={
            "model": model, "prompt": "", "stream": False,
            "keep_alive": keep_alive, "options": {
                "num_ctx": context_tokens, "num_gpu": gpu_layers,
                "num_thread": threads,
            },
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    payload = dict(response.json() or {})
    return {
        "model": model,
        "wall_seconds": round(time.perf_counter() - started, 6),
        "provider_load_seconds": round(float(payload.get("load_duration") or 0) / 1_000_000_000, 6),
        "keep_alive": keep_alive,
        "created_at_ms": int(time.time() * 1000),
    }


def _unload_other_models(*, requested_model: str, generate_url: str) -> list[str]:
    ps_url = generate_url.rsplit("/", 1)[0] + "/ps"
    response = requests.get(ps_url, timeout=10)
    response.raise_for_status()
    evicted: list[str] = []
    for item in list(dict(response.json() or {}).get("models") or []):
        model = str(item.get("name") or item.get("model") or "").strip()
        if not model or model == requested_model:
            continue
        unload = requests.post(
            generate_url,
            json={"model": model, "prompt": "", "stream": False, "keep_alive": 0},
            timeout=30,
        )
        unload.raise_for_status()
        evicted.append(model)
    return evicted


def _save_load_evidence(root: Path, model: str, context_tokens: int, payload: dict[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    identity = hashlib.sha256(f"{model}:{context_tokens}".encode("utf-8")).hexdigest()[:16]
    target = root / f"model-load-{identity}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(target)


if __name__ == "__main__":
    raise SystemExit(main())
