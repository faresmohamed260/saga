"""Run bounded, resumable local-model qualification on the real-book corpus."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import psutil
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.reasoning.task_suite import TASK_FAMILIES, TASK_SUITE_VERSION, build_tasks, evaluate_task
from benchmarks.reasoning.gold_evaluation import build_gold_evaluator
from scripts.build_local_reasoning_corpus import corpus_fingerprint
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
    parser.add_argument(
        "--engine",
        choices=("ollama", "lm_studio"),
        required=True,
        help="Local inference engine to qualify; no engine is selected implicitly.",
    )
    parser.add_argument("--model", required=True, help="Exact model identifier for the selected local engine.")
    parser.add_argument("--corpus", default="analysis_outputs/local_reasoning/corpus_v1.json")
    parser.add_argument("--gold", help="Versioned local extraction gold annotations.")
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
    parser.add_argument(
        "--ollama-thinking", choices=("off", "on", "low", "medium", "high"),
        default="off",
    )
    parser.add_argument("--lm-studio-gpu-offload", default="0.5")
    parser.add_argument(
        "--lm-studio-reasoning-effort",
        choices=("none", "low", "medium", "high"),
        default="none",
    )
    parser.add_argument("--max-vram-gib", type=float, default=10.0)
    parser.add_argument("--max-host-ram-gib", type=float, default=112.0)
    parser.add_argument("--cpu-warning-percent", type=float, default=80.0)
    parser.add_argument("--min-available-ram-gib", type=float, default=16.0)
    return parser.parse_args()


def _validate_gold_corpus(*, corpus_path: Path, corpus: dict[str, Any], gold: dict[str, Any]) -> None:
    if str(gold.get("corpus_version") or "") != str(corpus.get("corpus_version") or ""):
        raise ValueError("Gold annotations do not match the corpus version.")
    if str(gold.get("corpus_fingerprint") or "") != corpus_fingerprint(corpus):
        raise ValueError("Gold annotations do not match the exact corpus artifact.")


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
    evaluator = evaluate_task
    gold_variant = ""
    if args.gold:
        gold = json.loads(Path(args.gold).resolve().read_text(encoding="utf-8"))
        try:
            _validate_gold_corpus(corpus_path=corpus_path, corpus=corpus, gold=gold)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        evaluator = build_gold_evaluator(gold)
        gold_variant = f"-gold{gold.get('version', 'unknown')}"
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
    engine_version = _local_engine_version(engine=args.engine, config=config)
    host_admission = _assess_host_resources(
        cpu_warning_percent=args.cpu_warning_percent,
        min_available_ram_bytes=int(args.min_available_ram_gib * 1024 ** 3),
    )
    if args.engine == "ollama":
        evicted_models = _unload_other_models(
            requested_model=args.model, generate_url=config.ollama_local_url,
        )
    else:
        evicted_models = _unload_other_lm_studio_models(requested_model=args.model)
    load_monitor = LocalResourceMonitor()
    load_monitor.start()
    try:
        if args.engine == "ollama":
            load_evidence = _prepare_local_model(
                model=args.model, url=config.ollama_local_url,
                keep_alive=args.keep_alive, timeout_seconds=args.load_timeout_seconds,
                context_tokens=args.context_tokens, gpu_layers=args.gpu_layers,
                threads=args.threads,
            )
        else:
            load_evidence = _prepare_lm_studio_model(
                model=args.model,
                timeout_seconds=args.load_timeout_seconds,
                context_tokens=args.context_tokens,
                gpu_offload=args.lm_studio_gpu_offload,
                ttl_seconds=_duration_seconds(args.keep_alive),
                models_url=_lm_studio_model_status_url(
                    config.lm_studio_chat_url, args.model,
                ),
            )
    finally:
        load_resource_metrics = load_monitor.stop()
    load_evidence["host_admission"] = host_admission
    load_evidence["resource_metrics"] = load_resource_metrics
    load_evidence["evicted_models"] = evicted_models
    load_evidence["engine"] = args.engine
    load_evidence["engine_version"] = engine_version
    _save_load_evidence(checkpoint_root, args.model, args.context_tokens, load_evidence)
    try:
        _assert_resource_limits(
            load_resource_metrics,
            max_peak_vram_bytes=int(args.max_vram_gib * 1024 ** 3),
            max_peak_host_ram_bytes=int(args.max_host_ram_gib * 1024 ** 3),
        )
    except RuntimeError:
        if args.engine == "ollama":
            _unload_model(model=args.model, generate_url=config.ollama_local_url)
        else:
            _unload_lm_studio_model(args.model)
        raise

    if args.engine == "ollama":
        ollama_thinking: bool | str = {
            "off": False, "on": True,
            "low": "low", "medium": "medium", "high": "high",
        }[args.ollama_thinking]
        profile = ReasoningProfile(
            name="qualification-local", mode="ollama_local", ollama_model=args.model,
            timeout_seconds=args.timeout_seconds, max_retries=1,
            allow_account_rotation=False, context_window_tokens=args.context_tokens,
            ollama_keep_alive=args.keep_alive,
            ollama_gpu_layers=args.gpu_layers, ollama_threads=args.threads,
            ollama_stream_metrics=True,
            ollama_thinking=ollama_thinking,
        )
        allocation_variant = (
            f"gpu{args.gpu_layers}-threads{args.threads}-stream1"
            f"-thinking{args.ollama_thinking}"
        )
    else:
        profile = ReasoningProfile(
            name="qualification-local", mode="lm_studio_local",
            lm_studio_model=args.model,
            timeout_seconds=args.timeout_seconds, max_retries=1,
            allow_account_rotation=False, context_window_tokens=args.context_tokens,
            lm_studio_stream_metrics=True,
            lm_studio_reasoning_effort=(
                "" if args.lm_studio_reasoning_effort == "none"
                else args.lm_studio_reasoning_effort
            ),
        )
        allocation_variant = (
            f"gpu{args.lm_studio_gpu_offload}-parallel1-stream1-lifecycle2"
            f"-reasoning{args.lm_studio_reasoning_effort}"
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
        client=client, tasks=tasks, repetitions=args.repetitions, evaluator=evaluator,
        run_variant=(f"tasks-{TASK_SUITE_VERSION}-{args.scope}-{args.engine}-{engine_version}"
                     f"-ctx{args.context_tokens}"
                     f"-{allocation_variant}{gold_variant}"),
    )
    wall_times = [trial.wall_seconds for trial in trials]
    summary = {
        "model": args.model,
        "engine": args.engine,
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


def _local_engine_version(*, engine: str, config: ReasoningRuntimeConfig) -> str:
    if engine == "ollama":
        base = config.ollama_local_url.split("/api/", 1)[0].rstrip("/")
        response = requests.get(f"{base}/api/version", timeout=10)
        response.raise_for_status()
        version = str(dict(response.json() or {}).get("version") or "").strip()
        if not version:
            raise RuntimeError("Ollama did not report an engine version.")
        return f"ollama-{version}"
    executable = shutil.which("lms")
    if not executable:
        raise RuntimeError("LM Studio CLI 'lms' is not installed.")
    result = subprocess.run(
        [executable, "runtime", "ls"],
        capture_output=True, text=True, timeout=15, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"LM Studio runtime query failed: {result.stderr.strip()}")
    lines = result.stdout.splitlines()
    header = lines[0] if lines else ""
    selected_start = header.find("SELECTED")
    format_start = header.find("MODEL FORMAT")
    for line in lines[1:]:
        selected = (
            line[selected_start:format_start].strip()
            if selected_start >= 0 and format_start > selected_start
            else ""
        )
        if "llama.cpp" in line and selected:
            match = re.search(r"@([0-9]+(?:\.[0-9]+)+)", line)
            if match:
                return f"lmstudio-llamacpp-{match.group(1)}"
    raise RuntimeError("LM Studio selected runtime version could not be determined.")


def _prepare_lm_studio_model(
    *, model: str, timeout_seconds: int, context_tokens: int,
    gpu_offload: str, ttl_seconds: int, models_url: str,
) -> dict[str, Any]:
    executable = shutil.which("lms")
    if not executable:
        raise RuntimeError("LM Studio CLI 'lms' is not installed.")
    started = time.perf_counter()
    if _lm_studio_model_loaded(model=model, models_url=models_url):
        return {
            "model": model,
            "wall_seconds": 0.0,
            "provider_load_seconds": 0.0,
            "keep_alive": f"{ttl_seconds}s",
            "gpu_offload": str(gpu_offload),
            "reused_loaded_instance": True,
            "created_at_ms": int(time.time() * 1000),
        }
    process = subprocess.Popen(
        [
            executable, "load", model,
            "--gpu", str(gpu_offload),
            "--context-length", str(context_tokens),
            "--parallel", "1",
            "--ttl", str(ttl_seconds),
            "--yes",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = started + timeout_seconds
    try:
        while time.perf_counter() < deadline:
            if _lm_studio_model_loaded(model=model, models_url=models_url):
                break
            if process.poll() not in {None, 0}:
                details = process.stderr.read().strip() if process.stderr is not None else ""
                suffix = f": {details}" if details else "."
                raise RuntimeError(
                    f"LM Studio model load failed with exit code {process.returncode}{suffix}"
                )
            time.sleep(0.5)
        else:
            raise TimeoutError(f"LM Studio model load exceeded {timeout_seconds} seconds.")
    finally:
        if process.poll() is None:
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
    return {
        "model": model,
        "wall_seconds": round(time.perf_counter() - started, 6),
        "provider_load_seconds": 0.0,
        "keep_alive": f"{ttl_seconds}s",
        "gpu_offload": str(gpu_offload),
        "created_at_ms": int(time.time() * 1000),
    }


def _lm_studio_model_status_url(chat_url: str, model: str) -> str:
    base = str(chat_url).split("/v1/", 1)[0].rstrip("/")
    return f"{base}/api/v0/models/{quote(str(model), safe='')}"


def _lm_studio_model_loaded(*, model: str, models_url: str) -> bool:
    response = requests.get(models_url, timeout=10)
    response.raise_for_status()
    payload = dict(response.json() or {})
    if "state" in payload:
        return str(payload.get("id") or "") == model and payload.get("state") == "loaded"
    for item in list(payload.get("models") or []):
        if str(item.get("key") or "") == model and list(item.get("loaded_instances") or []):
            return True
    return False


def _duration_seconds(value: str) -> int:
    normalized = str(value or "").strip().lower()
    multiplier = 1
    if normalized.endswith("m"):
        multiplier, normalized = 60, normalized[:-1]
    elif normalized.endswith("h"):
        multiplier, normalized = 3600, normalized[:-1]
    elif normalized.endswith("s"):
        normalized = normalized[:-1]
    try:
        return max(1, int(float(normalized) * multiplier))
    except ValueError as exc:
        raise ValueError(f"Unsupported keep-alive duration '{value}'.") from exc


def _lm_studio_processes() -> list[dict[str, Any]]:
    executable = shutil.which("lms")
    if not executable:
        raise RuntimeError("LM Studio CLI 'lms' is not installed.")
    result = subprocess.run(
        [executable, "ps", "--json"],
        capture_output=True, text=True, timeout=15, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"LM Studio process query failed: {result.stderr.strip()}")
    payload = json.loads(result.stdout or "[]")
    return [item for item in payload if isinstance(item, dict)]


def _unload_other_lm_studio_models(*, requested_model: str) -> list[str]:
    evicted = []
    for item in _lm_studio_processes():
        identifier = str(item.get("identifier") or item.get("modelKey") or item.get("model") or "").strip()
        model_key = str(item.get("modelKey") or item.get("model") or identifier).strip()
        if not identifier or model_key == requested_model:
            continue
        _unload_lm_studio_model(identifier)
        evicted.append(identifier)
    return evicted


def _unload_lm_studio_model(identifier: str) -> None:
    executable = shutil.which("lms")
    if not executable:
        raise RuntimeError("LM Studio CLI 'lms' is not installed.")
    result = subprocess.run(
        [executable, "unload", identifier],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"LM Studio model unload failed: {result.stderr.strip() or result.stdout.strip()}")


def _assess_host_resources(
    *, cpu_warning_percent: float, min_available_ram_bytes: int,
) -> dict[str, Any]:
    cpu_percent = float(psutil.cpu_percent(interval=1.0))
    available_ram = int(psutil.virtual_memory().available)
    if available_ram < min_available_ram_bytes:
        raise RuntimeError(
            f"available RAM {available_ram / 1024 ** 3:.1f} GiB is below "
            f"{min_available_ram_bytes / 1024 ** 3:.1f} GiB"
        )
    return {
        "baseline_cpu_percent": cpu_percent,
        "available_ram_bytes": available_ram,
        "cpu_warning": cpu_percent > cpu_warning_percent,
        "cpu_warning_percent": cpu_warning_percent,
    }


def _assert_resource_limits(
    metrics: dict[str, Any], *, max_peak_vram_bytes: int,
    max_peak_host_ram_bytes: int,
) -> None:
    failures = []
    peak_vram = int(metrics.get("peak_vram_used_bytes") or 0)
    peak_host_ram = int(metrics.get("peak_host_used_bytes") or 0)
    if peak_vram > max_peak_vram_bytes:
        failures.append(
            f"peak VRAM {peak_vram / 1024 ** 3:.1f} GiB exceeds "
            f"{max_peak_vram_bytes / 1024 ** 3:.1f} GiB"
        )
    if peak_host_ram > max_peak_host_ram_bytes:
        failures.append(
            f"peak host RAM {peak_host_ram / 1024 ** 3:.1f} GiB exceeds "
            f"{max_peak_host_ram_bytes / 1024 ** 3:.1f} GiB"
        )
    if failures:
        raise RuntimeError("Model preload resource limit exceeded: " + "; ".join(failures))


def _unload_model(*, model: str, generate_url: str) -> None:
    response = requests.post(
        generate_url,
        json={"model": model, "prompt": "", "stream": False, "keep_alive": 0},
        timeout=30,
    )
    response.raise_for_status()


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
    identity_payload = {
        "engine": payload.get("engine"),
        "engine_version": payload.get("engine_version"),
        "model": model,
        "context_tokens": context_tokens,
        "gpu_offload": payload.get("gpu_offload"),
    }
    identity = hashlib.sha256(
        json.dumps(identity_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    target = root / f"model-load-{identity}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(target)


if __name__ == "__main__":
    raise SystemExit(main())
