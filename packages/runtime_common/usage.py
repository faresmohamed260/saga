from __future__ import annotations

import contextlib
import contextvars
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


class UsageBudgetExceededError(RuntimeError):
    pass


@contextlib.contextmanager
def usage_scope(*, governor: UsageGovernor | None = None, **attribution: Any) -> Iterator[UsageAttribution]:
    current = _USAGE_ATTRIBUTION.get() or UsageAttribution()
    merged = current.model_dump()
    merged.update({key: value for key, value in attribution.items() if value not in (None, "")})
    resolved = UsageAttribution.model_validate(merged)
    attribution_token = _USAGE_ATTRIBUTION.set(resolved)
    governor_token = _USAGE_GOVERNOR.set(governor) if governor is not None else None
    try:
        yield resolved
    finally:
        _USAGE_ATTRIBUTION.reset(attribution_token)
        if governor_token is not None:
            _USAGE_GOVERNOR.reset(governor_token)


def current_usage_attribution(**overrides: Any) -> UsageAttribution:
    values = (_USAGE_ATTRIBUTION.get() or UsageAttribution()).model_dump()
    values.update({key: value for key, value in overrides.items() if value not in (None, "")})
    return UsageAttribution.model_validate(values)


def reserve_usage(*, projected: ProviderUsage, **attribution: Any) -> UsageReservation | None:
    governor = _USAGE_GOVERNOR.get()
    if governor is None:
        return None
    try:
        reservation = governor.reserve(current_usage_attribution(**attribution), projected)
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
