from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import packages.observability_runtime.usage as usage_module
from packages.observability_runtime import (
    CostRate,
    UsageBudgetPolicy,
    UsageGovernanceRuntime,
)
from packages.persistence_runtime import (
    PersistenceProfile,
    PersistenceRuntimeConfig,
    create_persistence_client,
)
from packages.runtime_common import ProviderUsage, UsageAttribution, UsageBudgetExceededError, reserve_usage, settle_usage, usage_scope


def _runtime(tmp_path: Path, *, rates: tuple[CostRate, ...] = ()):
    profile = PersistenceProfile(name="usage-test", mode="test_harness", database_url=f"sqlite:///{tmp_path / 'usage.sqlite3'}")
    client = create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(profile=profile))
    client.initialize()
    return client, UsageGovernanceRuntime(store=client.usage, cost_rates=rates)


def _attribution(run_id: str = "run-1", project_id: str = "project-1") -> UsageAttribution:
    return UsageAttribution(
        release_id="release-1", project_id=project_id, run_id=run_id, series_id="series-1", stage="canon_extraction",
        agent="entity-agent", component="reasoning_runtime", provider="general_compute",
        account_alias="account-01", model="model-a", operation="generate_json",
    )


def test_cost_rate_rejects_an_all_zero_pricing_table():
    with pytest.raises(ValueError, match="positive unit price"):
        CostRate(provider="provider", pricing_version="invalid-zero-rate")


def test_usage_reservation_settlement_is_append_only_idempotent_and_priced(tmp_path: Path):
    client, runtime = _runtime(tmp_path, rates=(CostRate(
        provider="general_compute", model="model-a", input_per_million=1.0,
        output_per_million=2.0, request_each=0.01, pricing_version="2026-08",
    ),))
    reservation = runtime.reserve(_attribution(), ProviderUsage(input_tokens=1000, output_tokens=500, source="declared"))
    assert reservation.authorized is True
    assert reservation.projected_cost_usd == pytest.approx(0.012)

    actual = ProviderUsage(input_tokens=900, output_tokens=400, evidence_id="native-request-1")
    first = runtime.settle(reservation, actual, evidence={"request_id": "native-request-1", "api_token": "never-store"})
    second = runtime.settle(reservation, actual, evidence={"request_id": "native-request-1", "api_token": "different"})
    rows = client.usage.list(run_id="run-1")
    assert len(rows) == 3
    assert first["charge"]["entry_id"] == second["charge"]["entry_id"]
    summary = runtime.summary(run_id="run-1")
    assert summary["request_count"] == pytest.approx(1.0)
    assert summary["input_tokens"] == pytest.approx(900)
    assert summary["output_tokens"] == pytest.approx(400)
    assert summary["cost_usd"] == pytest.approx(0.0117)
    assert summary["priced_charge_count"] == 1
    assert summary["reconciled"] is True
    assert summary["reconciliation_coverage"] == pytest.approx(1)
    assert "never-store" not in json.dumps(rows)
    assert "different" not in json.dumps(rows)


def test_hard_budget_is_atomic_and_per_run_policy_isolated(tmp_path: Path):
    _, runtime = _runtime(tmp_path)
    runtime.configure_policy(UsageBudgetPolicy(
        policy_id="per-run-requests", scope_type="run", limits={"request_count": 1}, hard_limit=True,
    ))

    def reserve_same_run(_):
        return runtime.reserve(_attribution("run-1"), ProviderUsage(request_count=1, source="declared"))

    with ThreadPoolExecutor(max_workers=2) as pool:
        decisions = list(pool.map(reserve_same_run, range(2)))
    assert sum(item.authorized for item in decisions) == 1
    assert any("per-run-requests" in reason for item in decisions for reason in item.reasons)
    assert runtime.reserve(_attribution("run-2"), ProviderUsage(request_count=1, source="declared")).authorized is True


def test_release_returns_reserved_capacity_and_unpriced_usage_stays_explicit(tmp_path: Path):
    _, runtime = _runtime(tmp_path)
    runtime.configure_policy(UsageBudgetPolicy(
        policy_id="global-images", scope_type="global", limits={"image_count": 1}, hard_limit=True,
    ))
    first = runtime.reserve(_attribution(), ProviderUsage(image_count=1, source="declared"))
    assert first.authorized is True
    assert runtime.reserve(_attribution("run-2"), ProviderUsage(image_count=1, source="declared")).authorized is False
    runtime.release(first, reason="provider request failed before billing")
    second = runtime.reserve(_attribution("run-2"), ProviderUsage(image_count=1, source="declared"))
    assert second.authorized is True
    runtime.settle(second, ProviderUsage(image_count=1, evidence_id="render-1"), evidence={"render_id": "render-1"})
    summary = runtime.summary()
    assert summary["image_count"] == pytest.approx(1)
    assert summary["unpriced_charge_count"] == 1


def test_native_cost_has_priority_over_rate_estimate(tmp_path: Path):
    _, runtime = _runtime(tmp_path, rates=(CostRate(provider="general_compute", request_each=9, pricing_version="fallback"),))
    reservation = runtime.reserve(_attribution(), ProviderUsage(request_count=1, source="declared"))
    result = runtime.settle(reservation, ProviderUsage(request_count=1, native_cost_usd=0.25, evidence_id="bill-1"))
    assert result["charge"]["cost_usd"] == pytest.approx(0.25)
    assert result["charge"]["cost_status"] == "native"
    assert result["charge"]["pricing_version"] == "provider-native"


def test_pricing_prefers_account_and_model_specific_rate(tmp_path: Path):
    _, runtime = _runtime(tmp_path, rates=(
        CostRate(provider="general_compute", request_each=1, pricing_version="generic"),
        CostRate(provider="general_compute", model="model-a", request_each=2, pricing_version="model"),
        CostRate(
            provider="general_compute", account_alias="account-01", model="model-a",
            request_each=3, pricing_version="account-model",
        ),
    ))
    reservation = runtime.reserve(_attribution(), ProviderUsage(request_count=1, source="declared"))
    assert reservation.projected_cost_usd == pytest.approx(3)
    assert reservation.pricing_version == "account-model"


def test_reconciliation_alerts_only_when_actual_cost_exceeds_reservation(tmp_path: Path):
    class ObservationStore:
        def __init__(self):
            self.rows = []

        def append(self, row):
            self.rows.append(row)

    client, _ = _runtime(tmp_path, rates=(CostRate(
        provider="general_compute", request_each=1, pricing_version="test-rate",
    ),))
    observations = ObservationStore()
    runtime = UsageGovernanceRuntime(
        store=client.usage,
        cost_rates=(CostRate(provider="general_compute", request_each=1, pricing_version="test-rate"),),
        observation_store=observations,
    )

    lower = runtime.reserve(_attribution("lower"), ProviderUsage(request_count=2, source="declared"))
    runtime.settle(lower, ProviderUsage(request_count=1, evidence_id="lower-actual"))
    assert observations.rows == []

    higher = runtime.reserve(_attribution("higher"), ProviderUsage(request_count=1, source="declared"))
    runtime.settle(higher, ProviderUsage(request_count=2, evidence_id="higher-actual"))
    assert [row["name"] for row in observations.rows] == ["usage.reconciliation_anomaly"]
    assert "account_alias" not in observations.rows[0]["dimensions"]


def test_settlement_after_reservation_expiry_does_not_understate_usage(tmp_path: Path, monkeypatch):
    _, runtime = _runtime(tmp_path)
    runtime.configure_policy(UsageBudgetPolicy(
        policy_id="slow-call-budget", scope_type="global", limits={"request_count": 1}, hard_limit=True,
    ))
    monkeypatch.setattr(usage_module, "_now_ms", lambda: 1_000)
    reservation = runtime.reserve(_attribution(), ProviderUsage(request_count=1, source="declared"))

    monkeypatch.setattr(usage_module, "_now_ms", lambda: 100_000)
    runtime.settle(reservation, ProviderUsage(request_count=1, evidence_id="slow-provider-call"))

    summary = runtime.summary(run_id="run-1")
    assert summary["request_count"] == pytest.approx(1)
    assert summary["charge_count"] == 1
    assert runtime.reserve(_attribution("next-run"), ProviderUsage(request_count=1)).authorized is False


def test_project_budget_and_breakdown_are_isolated(tmp_path: Path):
    _, runtime = _runtime(tmp_path)
    runtime.configure_policy(UsageBudgetPolicy(
        policy_id="per-project-requests", scope_type="project", limits={"request_count": 1}, hard_limit=True,
    ))

    first = runtime.reserve(_attribution("run-a", "project-a"), ProviderUsage(request_count=1))
    runtime.settle(first, ProviderUsage(request_count=1, source="provider", evidence_id="native-a"))
    assert runtime.reserve(_attribution("run-b", "project-a"), ProviderUsage(request_count=1)).authorized is False

    second = runtime.reserve(_attribution("run-c", "project-b"), ProviderUsage(request_count=1))
    runtime.settle(second, ProviderUsage(request_count=1, source="measured", evidence_id="measured-b"))
    assert runtime.summary(project_id="project-a")["provider_confirmed_coverage"] == pytest.approx(1.0)
    assert runtime.summary(project_id="project-b")["measured_charge_count"] == 1
    assert {row["project_id"] for row in runtime.breakdown(group_by="project_id")} == {"project-a", "project-b"}


def test_usage_telemetry_storage_errors_fail_open_but_budget_denials_do_not():
    class BrokenGovernor:
        def reserve(self, attribution, projected):
            raise ConnectionError("ledger unavailable")

        def settle(self, reservation, actual, *, evidence=None):
            raise ConnectionError("ledger unavailable")

        def release(self, reservation, *, reason=""):
            raise ConnectionError("ledger unavailable")

    with usage_scope(governor=BrokenGovernor(), project_id="project-a"):
        with pytest.warns(RuntimeWarning, match="failed open"):
            reservation = reserve_usage(projected=ProviderUsage(request_count=1), provider="test")
        assert reservation is None
        assert settle_usage(None, ProviderUsage(request_count=1)) == {}

    class DenyingGovernor:
        def reserve(self, attribution, projected):
            from packages.runtime_common import UsageReservation
            return UsageReservation(
                reservation_id="denied", attribution=attribution, projected=projected,
                authorized=False, reasons=["hard budget reached"],
            )

    with usage_scope(governor=DenyingGovernor(), project_id="project-a"):
        with pytest.raises(UsageBudgetExceededError, match="hard budget reached"):
            reserve_usage(projected=ProviderUsage(request_count=1), provider="test")
