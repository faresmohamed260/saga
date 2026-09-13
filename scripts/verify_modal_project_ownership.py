#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
payload = json.loads((ROOT / "config/modal-project-ownership.json").read_text(encoding="utf-8"))
expected = [f"modal-{n:02d}" for n in range(3, 42)]
renderlab = ["modal-01", "modal-02", *[f"modal-{n:02d}" for n in range(42, 48)]]
assert payload.get("project") == "saga"
assert payload.get("ownedAccountLabels") == expected
assert (payload.get("reservedForOtherProjects") or {}).get("renderlab") == renderlab
assert not set(expected).intersection(renderlab)
fleet = (ROOT / "scripts/modal_worker_fleet.py").read_text(encoding="utf-8")
assert "assert_saga_owned_account(account.label)" in fleet
assert "OWNERSHIP_MANIFEST" in fleet
print("S.A.G.A. Modal project ownership boundary verified.")
