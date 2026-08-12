from __future__ import annotations

import contextlib
import contextvars
import threading
import warnings
from collections.abc import Iterator
from typing import Any

from packages.runtime_common.contracts import (
    ProviderUsage,
    UsageAttribution,
    UsageGovernor,
    UsageReservation,
)

_USAGE_GOVERNOR: contextvars.ContextVar[UsageGovernor | None] = contextvars.ContextVar("runtime_usage_governor", default=None)
_USAGE_ATTRIBUTION: contextvars.ContextVar[UsageAttribution | None] = contextvars.ContextVar(
    "runtime_usage_attribution", default=None
)
_REQUEST_BUDGET: contextvars.ContextVar["ProviderRequestBudget | None"] = contextvars.ContextVar(
    "runtime_provider_request_budget", default=None
)


class UsageBudgetExceededError(RuntimeError):
    pass


class ProviderRequestBudget:
    """Thread-safe request counter shared by copied stage contexts."""

    def __init__(self, limits: dict[str, int], initial_counts: dict[str, int] | None = None) -> None:
        self.limits = {
            str(key).strip().lower(): max(0, int(value))
            for key, value in limits.items()
            if str(key).strip()
        }
        self.counts: dict[str, int] = {
            str(key).strip().lower(): max(0, int(value))
            for key, value in dict(initial_counts or {}).items()
            if str(key).strip()
        }
        self._lock = threading.Lock()

    def consume(self, provider: str) -> None:
        key = str(provider or "unknown").strip().lower()
        limit = self.limits.get(key, self.limits.get("*"))
        with self._lock:
            used = self.counts.get(key, 0)
            if limit is None:
                raise UsageBudgetExceededError(
                    f"Provider request budget is not configured for '{key}'."
                )
            if used >= limit:
                raise UsageBudgetExceededError(
                    f"Provider request budget exceeded for '{key}': {used}/{limit}."
                )
            self.counts[key] = used + 1


@contextlib.contextmanager
def usage_scope(
    *, governor: UsageGovernor | None = None, request_limits: dict[str, int] | None = None,
    initial_request_counts: dict[str, int] | None = None,
    **attribution: Any,
) -> Iterator[UsageAttribution]:
    current = _USAGE_ATTRIBUTION.get() or UsageAttribution()
    merged = current.model_dump()
    merged.update({key: value for key, value in attribution.items() if value not in (None, "")})
    resolved = UsageAttribution.model_validate(merged)
    attribution_token = _USAGE_ATTRIBUTION.set(resolved)
    governor_token = _USAGE_GOVERNOR.set(governor) if governor is not None else None
    budget_token = _REQUEST_BUDGET.set(
        ProviderRequestBudget(request_limits, initial_counts=initial_request_counts)
    ) if request_limits else None
    try:
        yield resolved
    finally:
        _USAGE_ATTRIBUTION.reset(attribution_token)
        if governor_token is not None:
            _USAGE_GOVERNOR.reset(governor_token)
        if budget_token is not None:
            _REQUEST_BUDGET.reset(budget_token)


def current_usage_attribution(**overrides: Any) -> UsageAttribution:
    values = (_USAGE_ATTRIBUTION.get() or UsageAttribution()).model_dump()
    values.update({key: value for key, value in overrides.items() if value not in (None, "")})
    return UsageAttribution.model_validate(values)


def reserve_usage(*, projected: ProviderUsage, **attribution: Any) -> UsageReservation | None:
    resolved_attribution = current_usage_attribution(**attribution)
    budget = _REQUEST_BUDGET.get()
    if budget is not None:
        budget.consume(resolved_attribution.provider)
    governor = _USAGE_GOVERNOR.get()
    if governor is None:
        return None
    try:
        reservation = governor.reserve(resolved_attribution, projected)
    except Exception as exc:  # Accounting availability must not become provider availability.
        warnings.warn(f"Usage reservation telemetry failed open: {type(exc).__name__}", RuntimeWarning, stacklevel=2)
        return None
    if not reservation.authorized:
        raise UsageBudgetExceededError("; ".join(reservation.reasons) or "Provider usage budget exceeded.")
    return reservation


def settle_usage(reservation: UsageReservation | None, actual: ProviderUsage, *, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    governor = _USAGE_GOVERNOR.get()
    if governor is None or reservation is None:
        return {}
    try:
        return governor.settle(reservation, actual, evidence=evidence)
    except Exception as exc:
        warnings.warn(f"Usage settlement telemetry failed open: {type(exc).__name__}", RuntimeWarning, stacklevel=2)
        return {}


def release_usage(reservation: UsageReservation | None, *, reason: str = "") -> dict[str, Any]:
    governor = _USAGE_GOVERNOR.get()
    if governor is None or reservation is None:
        return {}
    try:
        return governor.release(reservation, reason=reason)
    except Exception as exc:
        warnings.warn(f"Usage release telemetry failed open: {type(exc).__name__}", RuntimeWarning, stacklevel=2)
        return {}
