#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
MANIFEST = ROOT / "config" / "modal-project-ownership.json"
EXPECTED_SAGA = [f"modal-{n:02d}" for n in range(3, 42)]
RENDERLAB = ["modal-01", "modal-02", *[f"modal-{n:02d}" for n in range(42, 48)]]
RETIRED_WORKFLOWS = [
    "deploy-flux2-klein-gateway.yml",
    "deploy-flux2-klein-modal01.yml",
    "modal-worker-maintenance.yml",
    "modal-worker-provision.yml",
    "qwen-fleet-routing-live.yml",
    "qwen-live-inference-smoke.yml",
    "test-flux2-klein-resolutions.yml",
    "worker-fleet-live-smoke.yml",
]

payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
assert payload.get("project") == "saga", "Modal manifest project must be saga"
assert payload.get("ownedAccountLabels") == EXPECTED_SAGA, "Saga must own exactly modal-03 through modal-41"
assert (payload.get("reservedForOtherProjects") or {}).get("renderlab") == RENDERLAB
assert not set(EXPECTED_SAGA).intersection(RENDERLAB), "Modal project allocations overlap"

fleet = (ROOT / "scripts" / "modal_worker_fleet.py").read_text(encoding="utf-8")
assert "assert_saga_owned_account(account.label)" in fleet, "Credential export must assert Saga ownership"
assert "OWNERSHIP_MANIFEST" in fleet, "Modal loader must use the checked-in ownership manifest"

for name in RETIRED_WORKFLOWS:
    assert not (WORKFLOWS / name).exists(), f"Retired cross-project Modal workflow remains active: {name}"

inventory = (WORKFLOWS / "modal-worker-inventory.yml").read_text(encoding="utf-8")
assert 'EXPECTED_MODAL_ACCOUNTS: "39"' in inventory, "Modal inventory must cover only the 39 Saga-owned accounts"
assert "Inventory every S.A.G.A.-owned Modal account" in inventory

for path in sorted(WORKFLOWS.glob("*.y*ml")):
    text = path.read_text(encoding="utf-8")
    for label in RENDERLAB:
        assert label not in text, f"Active Saga workflow {path.name} references RenderLab-owned account {label}"
    assert "config/modal-worker-registry.json" not in text, (
        f"Active Saga workflow {path.name} still consumes the historical RenderLab-owned worker registry"
    )

print("S.A.G.A. Modal project ownership boundary verified.")
