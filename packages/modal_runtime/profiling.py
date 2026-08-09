from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModalTimingEvent:
    phase: str
    elapsed_seconds: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModalTimingCollector:
    events: list[ModalTimingEvent] = field(default_factory=list)

    def record(self, phase: str, elapsed_seconds: float, **metadata: Any) -> None:
        self.events.append(
            ModalTimingEvent(
                phase=str(phase or "").strip(),
                elapsed_seconds=max(0.0, float(elapsed_seconds or 0.0)),
                metadata={key: value for key, value in metadata.items() if value is not None},
            )
        )

    def summary(self) -> dict[str, dict[str, Any]]:
        by_phase: dict[str, dict[str, Any]] = {}
        for event in self.events:
            bucket = by_phase.setdefault(
                event.phase,
                {
                    "count": 0,
                    "total_seconds": 0.0,
                    "max_seconds": 0.0,
                    "last_metadata": {},
                },
            )
            bucket["count"] += 1
            bucket["total_seconds"] = round(float(bucket["total_seconds"]) + event.elapsed_seconds, 6)
            bucket["max_seconds"] = round(max(float(bucket["max_seconds"]), event.elapsed_seconds), 6)
            bucket["last_metadata"] = dict(event.metadata)
        return by_phase


_CURRENT_COLLECTOR: ContextVar[ModalTimingCollector | None] = ContextVar("modal_runtime_timing_collector", default=None)


def current_modal_timing_collector() -> ModalTimingCollector | None:
    return _CURRENT_COLLECTOR.get()


def record_modal_timing(phase: str, elapsed_seconds: float, **metadata: Any) -> None:
    collector = current_modal_timing_collector()
    if collector is not None:
        collector.record(phase, elapsed_seconds, **metadata)


@contextmanager
def modal_timing_phase(phase: str, **metadata: Any):
    started_at = time.perf_counter()
    try:
        yield
    finally:
        record_modal_timing(phase, time.perf_counter() - started_at, **metadata)


@contextmanager
def collect_modal_timings():
    collector = ModalTimingCollector()
    token = _CURRENT_COLLECTOR.set(collector)
    try:
        yield collector
    finally:
        _CURRENT_COLLECTOR.reset(token)
