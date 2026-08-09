from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any

from packages.observability_runtime.contracts import CostRate, UsageBudgetPolicy
from packages.observability_runtime.safety import sanitize
from packages.runtime_common import ProviderUsage, UsageAttribution, UsageReservation


class UsageGovernanceRuntime:
    """Provider-neutral accounting and budget enforcement over an append-only ledger."""

    def __init__(self, *, store, cost_rates: tuple[CostRate, ...] = (), reservation_ttl_seconds: int = 900,
                 observation_store=None, reconciliation_alert_ratio: float = 0.25) -> None:
        self.store = store
        self.cost_rates = tuple(cost_rates)
        self.reservation_ttl_seconds = max(30, int(reservation_ttl_seconds))
        self.observation_store = observation_store
        self.reconciliation_alert_ratio = max(0.0, float(reconciliation_alert_ratio))

    def configure_policy(self, policy: UsageBudgetPolicy) -> dict[str, Any]:
        return self.store.configure_policy(policy.model_dump())

    def reserve(self, attribution: UsageAttribution, projected: ProviderUsage) -> UsageReservation:
        reservation_id = f"usage-res-{uuid.uuid4().hex}"
        cost, status, pricing_version = self._price(attribution, projected)
        timestamp_ms = _now_ms()
        entry = self._entry(
            entry_id=_stable_id("reservation", reservation_id), reservation_id=reservation_id,
            entry_kind="reservation", timestamp_ms=timestamp_ms,
            expires_at_ms=timestamp_ms + self.reservation_ttl_seconds * 1000,
            attribution=attribution, usage=projected, cost_usd=cost,
            cost_status=status, pricing_version=pricing_version,
            evidence={"usage_source": projected.source},
        )
        decision = self.store.reserve(entry)
        reasons = [
            f"{policy['policy_id']} exceeded " + ", ".join(f"{item['metric']}={item['projected']:.6g}>{item['limit']:.6g}" for item in policy["exceeded"])
            for policy in decision.get("policies") or []
        ]
        if reasons:
            self._alert(
                name="usage.budget_denied" if not decision.get("authorized") else "usage.budget_warning",
                attribution=attribution, status="denied" if not decision.get("authorized") else "warning",
                payload={"reasons": reasons, "projected_cost_usd": cost},
            )
        return UsageReservation(
            reservation_id=reservation_id, attribution=attribution, projected=projected,
            projected_cost_usd=cost, cost_status=status, pricing_version=pricing_version,
            authorized=bool(decision.get("authorized")), reasons=reasons,
        )

    def settle(self, reservation: UsageReservation, actual: ProviderUsage, *, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
        cost, status, pricing_version = self._price(reservation.attribution, actual)
        timestamp_ms = _now_ms()
        release = self._entry(
            entry_id=_stable_id("release", reservation.reservation_id), reservation_id=reservation.reservation_id,
            entry_kind="reservation_release", timestamp_ms=timestamp_ms, attribution=reservation.attribution,
            usage=reservation.projected, cost_usd=-reservation.projected_cost_usd, sign=-1.0,
            cost_status=reservation.cost_status, pricing_version=reservation.pricing_version,
            evidence={"reason": "settled"},
        )
        charge = self._entry(
            entry_id=_stable_id("charge", reservation.reservation_id, actual.evidence_id), reservation_id=reservation.reservation_id,
            entry_kind="charge", timestamp_ms=timestamp_ms, attribution=reservation.attribution,
            usage=actual, cost_usd=cost, cost_status=status, pricing_version=pricing_version,
            evidence={"usage_source": actual.source, "provider_evidence": sanitize(evidence or {})},
        )
        result = self.store.settle(reservation_id=reservation.reservation_id, release_entry=release, charge_entry=charge)
        result["reconciliation"] = {
            "projected_cost_usd": reservation.projected_cost_usd,
            "actual_cost_usd": cost,
            "delta_cost_usd": cost - reservation.projected_cost_usd,
            "cost_status": status,
        }
        projected_cost = reservation.projected_cost_usd
        material_increase = max(projected_cost * self.reconciliation_alert_ratio, 1e-9)
        if cost > projected_cost + material_increase:
            self._alert(
                name="usage.reconciliation_anomaly", attribution=reservation.attribution, status="warning",
                payload=result["reconciliation"],
            )
        return result

    def release(self, reservation: UsageReservation, *, reason: str = "") -> dict[str, Any]:
        return self.store.release(self._entry(
            entry_id=_stable_id("release", reservation.reservation_id), reservation_id=reservation.reservation_id,
            entry_kind="reservation_release", timestamp_ms=_now_ms(), attribution=reservation.attribution,
            usage=reservation.projected, cost_usd=-reservation.projected_cost_usd, sign=-1.0,
            cost_status=reservation.cost_status, pricing_version=reservation.pricing_version,
            evidence={"reason": str(reason or "released")[:240]},
        ))

    def summary(self, *, run_id: str = "", provider: str = "", account_alias: str = "", since_ms: int = 0, limit: int = 100000) -> dict[str, Any]:
        rows = self.store.list(run_id=run_id, provider=provider, account_alias=account_alias, since_ms=since_ms, limit=limit)
        metrics = {key: 0.0 for key in ("request_count", "input_tokens", "output_tokens", "cached_input_tokens", "compute_seconds", "image_count", "audio_seconds", "cost_usd")}
        rows = _active_ledger_rows(rows, now_ms=_now_ms())
        for row in rows:
            for key in metrics:
                metrics[key] += float(row.get(key) or 0)
        charges = [row for row in rows if row.get("entry_kind") == "charge"]
        reconciled_charges = [
            row for row in charges
            if bool(dict(row.get("evidence") or {}).get("provider_evidence"))
        ]
        return {
            **metrics,
            "charge_count": len(charges),
            "priced_charge_count": sum(row.get("cost_status") in {"native", "estimated"} for row in charges),
            "unpriced_charge_count": sum(row.get("cost_status") == "unpriced" for row in charges),
            "reconciled_charge_count": len(reconciled_charges),
            "reconciliation_coverage": len(reconciled_charges) / len(charges) if charges else 0.0,
            "reconciled": bool(charges) and len(reconciled_charges) == len(charges),
            "providers": sorted({str(row.get("provider") or "") for row in charges if row.get("provider")}),
            "accounts": sorted({str(row.get("account_alias") or "") for row in charges if row.get("account_alias")}),
        }

    def breakdown(
        self,
        *,
        group_by: str,
        run_id: str = "",
        provider: str = "",
        account_alias: str = "",
        since_ms: int = 0,
        limit: int = 100000,
    ) -> list[dict[str, Any]]:
        allowed = {"release_id", "run_id", "series_id", "stage", "agent", "component", "provider", "account_alias", "model", "operation"}
        if group_by not in allowed:
            raise ValueError(f"Unsupported usage breakdown '{group_by}'.")
        rows = [
            row
            for row in self.store.list(
                run_id=run_id,
                provider=provider,
                account_alias=account_alias,
                since_ms=since_ms,
                limit=limit,
            )
            if row.get("entry_kind") == "charge"
        ]
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            groups.setdefault(str(row.get(group_by) or "unattributed"), []).append(row)
        result = []
        for label, group in sorted(groups.items()):
            result.append({
                group_by: label,
                "charge_count": len(group),
                "request_count": sum(float(row.get("request_count") or 0) for row in group),
                "input_tokens": sum(float(row.get("input_tokens") or 0) for row in group),
                "output_tokens": sum(float(row.get("output_tokens") or 0) for row in group),
                "compute_seconds": sum(float(row.get("compute_seconds") or 0) for row in group),
                "image_count": sum(float(row.get("image_count") or 0) for row in group),
                "audio_seconds": sum(float(row.get("audio_seconds") or 0) for row in group),
                "cost_usd": sum(float(row.get("cost_usd") or 0) for row in group),
                "unpriced_charge_count": sum(row.get("cost_status") == "unpriced" for row in group),
            })
        return result

    def _price(self, attribution: UsageAttribution, usage: ProviderUsage) -> tuple[float, str, str]:
        if usage.native_cost_usd is not None:
            return float(usage.native_cost_usd), "native", "provider-native"
        candidates = [
            item
            for item in self.cost_rates
            if item.provider == attribution.provider
            and (not item.account_alias or item.account_alias == attribution.account_alias)
            and (not item.model or item.model == attribution.model)
        ]
        rate = max(
            candidates,
            key=lambda item: (bool(item.account_alias), bool(item.model)),
            default=None,
        )
        if rate is None:
            return 0.0, "unpriced", ""
        cost = (
            max(0.0, usage.input_tokens - usage.cached_input_tokens) * rate.input_per_million / 1_000_000
            + usage.cached_input_tokens * rate.cached_input_per_million / 1_000_000
            + usage.output_tokens * rate.output_per_million / 1_000_000
            + usage.compute_seconds * rate.compute_per_second
            + usage.image_count * rate.image_each
            + usage.audio_seconds * rate.audio_per_second
            + usage.request_count * rate.request_each
        )
        return float(cost), "estimated", rate.pricing_version

    def _alert(self, *, name: str, attribution: UsageAttribution, status: str, payload: dict[str, Any]) -> None:
        if self.observation_store is None:
            return
        timestamp_ms = _now_ms()
        self.observation_store.append({
            "observation_id": _stable_id(name, attribution.model_dump(), payload), "kind": "alert", "timestamp_ms": timestamp_ms,
            "run_id": attribution.run_id, "series_id": attribution.series_id, "component": attribution.component,
            "stage": attribution.stage, "provider": attribution.provider, "name": name, "status": status,
            "dimensions": {"model": attribution.model},
            "payload": sanitize({**payload, "account_alias": attribution.account_alias}),
        })

    @staticmethod
    def _entry(*, entry_id: str, reservation_id: str, entry_kind: str, timestamp_ms: int, attribution: UsageAttribution,
               usage: ProviderUsage, cost_usd: float, cost_status: str, pricing_version: str, evidence: dict[str, Any], expires_at_ms: int = 0,
               sign: float = 1.0) -> dict[str, Any]:
        usage_values = usage.model_dump(exclude={"native_cost_usd", "source", "evidence_id"})
        usage_values = {key: float(value) * sign for key, value in usage_values.items()}
        return {
            "entry_id": entry_id, "reservation_id": reservation_id, "entry_kind": entry_kind,
            "timestamp_ms": timestamp_ms, "expires_at_ms": expires_at_ms,
            **attribution.model_dump(), **usage_values,
            "cost_usd": cost_usd, "cost_status": cost_status, "pricing_version": pricing_version,
            "evidence": sanitize(evidence),
        }
def _stable_id(*parts: Any) -> str:
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return f"usage-{hashlib.sha256(payload).hexdigest()[:32]}"


def _active_ledger_rows(rows: list[dict[str, Any]], *, now_ms: int) -> list[dict[str, Any]]:
    released = {
        str(row.get("reservation_id") or "")
        for row in rows
        if row.get("entry_kind") == "reservation_release"
    }
    return [
        row
        for row in rows
        if row.get("entry_kind") != "reservation"
        or not row.get("expires_at_ms")
        or int(row["expires_at_ms"]) >= now_ms
        or str(row.get("reservation_id") or "") in released
    ]


def _now_ms() -> int:
    return int(time.time() * 1000)
