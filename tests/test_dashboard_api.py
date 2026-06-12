import base64
import json
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

import dashboard_api.app as dashboard_app
from dashboard_api.app import create_app


def _encode(display_path: str) -> str:
    return base64.urlsafe_b64encode(display_path.encode("utf-8")).decode("ascii").rstrip("=")


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _contract_record(path: Path, display_path: str) -> dict:
    return {
        "name": path.name,
        "path": path,
        "display_path": display_path,
        "category": "contract",
        "size_bytes": path.stat().st_size,
        "modified_at": datetime.fromtimestamp(path.stat().st_mtime),
    }


def _report_record(path: Path, display_path: str) -> dict:
    return {
        "name": path.name,
        "path": path,
        "display_path": display_path,
        "category": "report",
        "size_bytes": path.stat().st_size,
        "modified_at": datetime.fromtimestamp(path.stat().st_mtime),
    }


def test_dashboard_api_lists_runs_and_contracts():
    client = TestClient(create_app())

    runs_response = client.get("/api/runs")
    contracts_response = client.get("/api/contracts")
    reports_response = client.get("/api/reports")

    assert runs_response.status_code == 200
    assert "items" in runs_response.json()
    assert contracts_response.status_code == 200
    assert "items" in contracts_response.json()
    assert reports_response.status_code == 200
    assert "items" in reports_response.json()


def test_dashboard_api_reads_real_contract_when_available(tmp_path, monkeypatch):
    contract_path = tmp_path / "book.contract.json"
    display_path = "analysis_outputs/encode_runs/acotar/test/contracts/book.contract.json"
    _write_json(contract_path, {"inputs": {"books": [{"title": "Book 1"}]}, "outputs": {"scene_analyses": []}})
    monkeypatch.setattr(dashboard_app, "discover_contract_files", lambda: [_contract_record(contract_path, display_path)])
    monkeypatch.setattr(dashboard_app, "_safe_path_from_display", lambda _: contract_path)
    client = TestClient(create_app())
    contracts = client.get("/api/contracts").json()["items"]
    assert contracts

    contract_id = contracts[0]["id"]
    response = client.get(f"/api/contracts/{contract_id}")

    assert response.status_code == 200
    payload = response.json()
    assert "payload" in payload
    assert "summary" in payload


def test_dashboard_api_reads_real_report_when_available(tmp_path, monkeypatch):
    report_path = tmp_path / "summary.md"
    display_path = "analysis_outputs/encoder_validation/summary.md"
    report_path.write_text("# summary", encoding="utf-8")
    monkeypatch.setattr(dashboard_app, "discover_report_files", lambda: [_report_record(report_path, display_path)])
    monkeypatch.setattr(dashboard_app, "_safe_path_from_display", lambda _: report_path)
    client = TestClient(create_app())
    reports = client.get("/api/reports").json()["items"]
    assert reports

    report_id = reports[0]["id"]
    response = client.get(f"/api/reports/{report_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["content_type"] in {"json", "text"}


def test_dashboard_api_export_json_returns_serialized_content():
    client = TestClient(create_app())
    response = client.post("/api/export/json", json={"payload": {"ok": True}, "file_name": "demo.json"})

    assert response.status_code == 200
    assert response.json()["file_name"] == "demo.json"
    assert '"ok": true' in response.json()["content"]


def test_dashboard_api_validate_contract_route_returns_payload(tmp_path, monkeypatch):
    contract_path = tmp_path / "book.contract.json"
    display_path = "analysis_outputs/encode_runs/acotar/test/contracts/book.contract.json"
    _write_json(
        contract_path,
        {
            "inputs": {"books": [{"title": "Book 1"}]},
            "outputs": {
                "scene_analyses": [
                    {
                        "book_index": 1,
                        "chapter_index": 1,
                        "scene_index": 1,
                        "scene_summary": "A test scene.",
                        "events": [{"event_id": "evt_1", "description": "A test event.", "characters": ["Feyre"]}],
                        "canonical_characters": [{"name": "Feyre"}],
                    }
                ],
                "identity_result": {"alias_map": {}, "stable_named_characters": [], "reference_entities": []},
            },
        },
    )
    monkeypatch.setattr(dashboard_app, "discover_contract_files", lambda: [_contract_record(contract_path, display_path)])
    monkeypatch.setattr(dashboard_app, "_safe_path_from_display", lambda _: contract_path)
    client = TestClient(create_app())
    contracts = client.get("/api/contracts").json()["items"]
    assert contracts

    response = client.post("/api/validate-contract", json={"contract_id": contracts[0]["id"]})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "artifact_snapshot" in payload["payload"]


def test_dashboard_api_build_visual_world_state_route_invokes_service(tmp_path, monkeypatch):
    contract_path = tmp_path / "book.contract.json"
    display_path = "analysis_outputs/encode_runs/acotar/test/contracts/book.contract.json"
    _write_json(contract_path, {"inputs": {"books": [{"title": "Book 1"}]}, "outputs": {"scene_analyses": []}})
    monkeypatch.setattr(dashboard_app, "discover_contract_files", lambda: [_contract_record(contract_path, display_path)])
    monkeypatch.setattr(dashboard_app, "_safe_path_from_display", lambda _: contract_path)
    client = TestClient(create_app())
    contracts = client.get("/api/contracts").json()["items"]
    assert contracts

    captured = {}

    class StubService:
        def build_visual_world_state(self, **kwargs):
            captured.update(kwargs)
            return {"target_point": kwargs["target_point"], "character_visual_states": [], "entity_visual_states": [], "location_visual_states": [], "diagnostics": {}}

    monkeypatch.setattr(dashboard_app, "VisualWorldStateService", lambda: StubService())
    monkeypatch.setattr(dashboard_app, "_write_visual_world_state_report", lambda path, payload: path)

    response = client.post(
        "/api/build-visual-world-state",
        json={
            "contract_ids": [contracts[0]["id"]],
            "target_point": {"mode": "post_book", "after_book_index": 1, "include_future_facts": False},
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert captured["target_point"]["mode"] == "post_book"
    assert len(captured["contract_paths"]) == 1


def test_dashboard_api_neo4j_delete_confirm_requires_exact_text():
    client = TestClient(create_app())
    response = client.post(
        "/api/neo4j/delete/confirm",
        json={
            "delete_type": "series",
            "series_id": "acotar",
            "confirm_text": "wrong",
        },
    )

    assert response.status_code == 400
    assert "Confirmation text mismatch" in response.json()["detail"]


def test_dashboard_api_neo4j_status_route_can_use_stub_service(monkeypatch):
    client = TestClient(create_app())

    class StubService:
        uri = "neo4j://localhost:7687"
        database = "neo4j"

        def probe_connection(self):
            return {"status": "ok", "uri": self.uri, "database": self.database}

    monkeypatch.setattr(dashboard_app, "_neo4j_service", lambda: StubService())
    response = client.get("/api/neo4j/status")

    assert response.status_code == 200
    assert response.json()["connected"] is True
    assert response.json()["status"] == "ok"


def test_dashboard_api_neo4j_delete_dry_run_route_can_use_stub_service(monkeypatch):
    client = TestClient(create_app())

    class StubService:
        def probe_connection(self):
            return {"status": "ok"}

    monkeypatch.setattr(dashboard_app, "_neo4j_service", lambda: StubService())
    monkeypatch.setattr(
        dashboard_app,
        "_neo4j_delete_dry_run",
        lambda service, payload: {
            "implemented": True,
            "connected": True,
            "status": "ok",
            "delete_type": payload.delete_type,
            "series_id": payload.series_id,
            "confirmation_required": payload.series_id,
            "dry_run": True,
            "would_delete": {"Series": 1},
            "local_contracts_affected": False,
        },
    )
    response = client.post("/api/neo4j/delete/dry-run", json={"delete_type": "series", "series_id": "acotar"})

    assert response.status_code == 200
    assert response.json()["dry_run"] is True
    assert response.json()["would_delete"]["Series"] == 1


def test_dashboard_api_rejects_escape_paths():
    client = TestClient(create_app())
    invalid = _encode("../outside.json")

    response = client.get(f"/api/contracts/{invalid}")

    assert response.status_code == 400
