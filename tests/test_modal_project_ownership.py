from __future__ import annotations
import json
from pathlib import Path
import pytest
from scripts import modal_worker_fleet

def fake_roster(labels: list[str]) -> str:
    return json.dumps({"accounts": [{"label": label, "token_id": f"fake-{label}", "token_secret": f"secret-{label}"} for label in labels]})

def test_manifest_assigns_exact_saga_accounts() -> None:
    payload = json.loads(Path("config/modal-project-ownership.json").read_text(encoding="utf-8"))
    assert payload["ownedAccountLabels"] == [f"modal-{n:02d}" for n in range(3, 42)]
    assert payload["reservedForOtherProjects"]["renderlab"] == ["modal-01", "modal-02", *[f"modal-{n:02d}" for n in range(42, 48)]]

def test_omnibus_roster_is_filtered_to_saga_accounts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAGA_MODAL_TOKENS_JSON", fake_roster([f"modal-{n:02d}" for n in range(1, 48)]))
    assert [account.label for account in modal_worker_fleet.load_accounts()] == [f"modal-{n:02d}" for n in range(3, 42)]

@pytest.mark.parametrize("label", ["modal-01", "modal-02", "modal-42", "modal-47"])
def test_credential_export_rejects_renderlab_accounts(label: str) -> None:
    with pytest.raises(SystemExit, match="not owned by S.A.G.A."):
        modal_worker_fleet.env_for(modal_worker_fleet.Account(label, "fake-id", "fake-secret"))

def test_missing_owned_account_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAGA_MODAL_TOKENS_JSON", fake_roster([f"modal-{n:02d}" for n in range(1, 48) if n != 17]))
    with pytest.raises(SystemExit, match="modal-17"):
        modal_worker_fleet.load_accounts()
