"""Heavy-model qualification utilities kept outside normal CI dependencies."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass
import hashlib
import os
from pathlib import Path
import threading
import time
from typing import Any


@dataclass(frozen=True, slots=True)
class ModelArtifactDigest:
    model_id: str
    revision: str
    snapshot_path: str
    aggregate_sha256: str
    file_count: int
    total_bytes: int


@dataclass(frozen=True, slots=True)
class ResourceUsage:
    wall_seconds: float
    peak_rss_bytes: int | None
    peak_process_tree_rss_bytes: int | None
    cuda_peak_allocated_bytes: int | None
    cuda_peak_reserved_bytes: int | None


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def digest_snapshot(*, model_id: str, revision: str, snapshot_path: str | Path) -> ModelArtifactDigest:
    root = Path(snapshot_path).resolve()
    if not root.is_dir():
        raise ValueError(f"model snapshot directory does not exist: {root}")

    rows: list[tuple[str, str, int]] = []
    for path in sorted((path for path in root.rglob("*") if path.is_file()), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        sha256, size = _sha256_file(path)
        rows.append((relative, sha256, size))

    if not rows:
        raise ValueError(f"model snapshot contains no files: {root}")

    aggregate = hashlib.sha256()
    for relative, sha256, size in rows:
        aggregate.update(relative.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(sha256.encode("ascii"))
        aggregate.update(b"\0")
        aggregate.update(str(size).encode("ascii"))
        aggregate.update(b"\n")

    return ModelArtifactDigest(
        model_id=model_id,
        revision=revision,
        snapshot_path=str(root),
        aggregate_sha256=aggregate.hexdigest(),
        file_count=len(rows),
        total_bytes=sum(size for _, _, size in rows),
    )


def download_and_digest_model(
    *,
    model_id: str,
    revision: str,
    cache_dir: str | Path | None = None,
    local_files_only: bool = False,
) -> ModelArtifactDigest:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:  # pragma: no cover - dedicated qualification path
        raise RuntimeError("qualification requires huggingface_hub from the pinned model environment") from exc

    snapshot = snapshot_download(
        repo_id=model_id,
        revision=revision,
        cache_dir=None if cache_dir is None else str(cache_dir),
        local_files_only=local_files_only,
    )
    return digest_snapshot(model_id=model_id, revision=revision, snapshot_path=snapshot)


class ResourceMonitor(AbstractContextManager["ResourceMonitor"]):
    """Sample process-tree RSS and framework CUDA peak memory during a run."""

    def __init__(self, *, sample_interval_seconds: float = 0.05) -> None:
        if sample_interval_seconds <= 0:
            raise ValueError("sample_interval_seconds must be > 0")
        self.sample_interval_seconds = sample_interval_seconds
        self._started = 0.0
        self._stopped = 0.0
        self._peak_rss: int | None = None
        self._peak_tree_rss: int | None = None
        self._cuda_peak_allocated: int | None = None
        self._cuda_peak_reserved: int | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._process: Any | None = None
        self._torch: Any | None = None

    def _sample(self) -> None:
        if self._process is None:
            return
        try:
            own = int(self._process.memory_info().rss)
            total = own
            for child in self._process.children(recursive=True):
                try:
                    total += int(child.memory_info().rss)
                except Exception:
                    continue
            self._peak_rss = own if self._peak_rss is None else max(self._peak_rss, own)
            self._peak_tree_rss = total if self._peak_tree_rss is None else max(self._peak_tree_rss, total)
        except Exception:
            return

    def _poll(self) -> None:
        while not self._stop.wait(self.sample_interval_seconds):
            self._sample()

    def __enter__(self) -> "ResourceMonitor":
        self._started = time.perf_counter()
        try:
            import psutil

            self._process = psutil.Process(os.getpid())
            self._sample()
            self._thread = threading.Thread(target=self._poll, name="saga-v3-resource-monitor", daemon=True)
            self._thread.start()
        except ImportError:
            self._process = None

        try:
            import torch

            self._torch = torch
            if torch.cuda.is_available():
                torch.cuda.synchronize()
                torch.cuda.reset_peak_memory_stats()
        except ImportError:
            self._torch = None
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._stopped = time.perf_counter()
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self.sample_interval_seconds * 4))
        self._sample()
        if self._torch is not None and self._torch.cuda.is_available():
            self._torch.cuda.synchronize()
            self._cuda_peak_allocated = int(self._torch.cuda.max_memory_allocated())
            self._cuda_peak_reserved = int(self._torch.cuda.max_memory_reserved())
        return None

    @property
    def usage(self) -> ResourceUsage:
        if self._stopped <= self._started:
            raise RuntimeError("resource monitor has not completed")
        return ResourceUsage(
            wall_seconds=self._stopped - self._started,
            peak_rss_bytes=self._peak_rss,
            peak_process_tree_rss_bytes=self._peak_tree_rss,
            cuda_peak_allocated_bytes=self._cuda_peak_allocated,
            cuda_peak_reserved_bytes=self._cuda_peak_reserved,
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self.usage)
