"""Provider-neutral cooperative cancellation primitives for long-running runtimes."""

from __future__ import annotations

from collections.abc import Callable


CancellationChecker = Callable[[], bool]


class RuntimeCancelledError(RuntimeError):
    """Raised when a runtime reaches a safe cancellation boundary."""


def raise_if_cancelled(checker: CancellationChecker | None) -> None:
    if checker is not None and checker():
        raise RuntimeCancelledError("Execution cancellation was requested.")
