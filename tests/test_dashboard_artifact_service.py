import json
from pathlib import Path

from services.dashboard_artifact_service import (
    build_contract_summary,
    discover_contract_files,
    discover_encode_runs,
    discover_report_files,
)


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_discover_encode_runs_collects_status_and_artifacts(tmp_path: Path):
    run_dir = tmp_path / "acotar" / "20260607T120000Z"
    contracts_dir = run_dir / "contracts"
    reports_dir = run_dir / "reports"
    _write_json(
        run_dir / "status.json",
        {
            "status": "completed",
            "started_at_utc": "2026-06-07T12:00:00+00:00",
            "updated_at_utc": "2026-06-07T12:10:00+00:00",
            "summary": {"total_requested": 2, "completed": 2, "failed": 0, "remaining": 0},
            "books": [{"title": "Book 1"}, {"title": "Book 2"}],
        },
    )
    _write_json(tmp_path / "acotar" / "latest_status.json", {"status": "completed"})
    _write_json(contracts_dir / "book.contract.json", {"ok": True})
    (reports_dir / "validation.md").parent.mkdir(parents=True, exist_ok=True)
    (reports_dir / "validation.md").write_text("# report", encoding="utf-8")

    runs = discover_encode_runs(tmp_path)

    assert len(runs) == 1
    assert runs[0]["series_id"] == "acotar"
    assert runs[0]["contract_count"] == 1
    assert runs[0]["report_count"] == 1
    assert runs[0]["completed_books"] == 2


def test_discover_contract_files_reads_series_and_run_ids(tmp_path: Path):
    contract_path = tmp_path / "acotar" / "20260607T120000Z" / "contracts" / "book.contract.json"
    _write_json(contract_path, {"contract_version": "1.0.0"})

    contracts = discover_contract_files(tmp_path)

    assert len(contracts) == 1
    assert contracts[0]["series_id"] == "acotar"
    assert contracts[0]["run_id"] == "20260607T120000Z"
    assert contracts[0]["name"] == "book.contract.json"


def test_discover_report_files_gathers_known_report_locations(tmp_path: Path):
    analysis_root = tmp_path / "analysis_outputs"
    (analysis_root / "encoder_validation").mkdir(parents=True, exist_ok=True)
    (analysis_root / "encoder_validation" / "summary.md").write_text("# summary", encoding="utf-8")
    (analysis_root / "encode_runs" / "acotar" / "20260607T120000Z" / "reports").mkdir(parents=True, exist_ok=True)
    (analysis_root / "encode_runs" / "acotar" / "20260607T120000Z" / "reports" / "detail.md").write_text(
        "# detail",
        encoding="utf-8",
    )

    reports = discover_report_files(analysis_root)

    names = {item["name"] for item in reports}
    assert "summary.md" in names
    assert "detail.md" in names


def test_build_contract_summary_extracts_major_counts():
    summary = build_contract_summary(
        {
            "generated_at_utc": "2026-06-07T12:00:00+00:00",
            "inputs": {
                "series": {"series_id": "acotar"},
                "books": [{"title": "Book 1"}],
            },
            "configuration": {
                "analysis_model": "gpt_oss",
                "identity_provider": "booknlp_clean",
                "scene_failure_policy": "fail_fast",
            },
            "outputs": {
                "chapters": [1, 2],
                "scene_analyses": [1, 2, 3],
                "timeline": [1],
                "event_ledger": [1, 2],
                "character_profiles": [1, 2, 3, 4],
            },
            "diagnostics": {"reference_entity_count": 9},
            "identity": {"alias_map": {"Rhys": "Rhysand", "Az": "Azriel"}},
        }
    )

    assert summary["series_id"] == "acotar"
    assert summary["book_title"] == "Book 1"
    assert summary["chapter_count"] == 2
    assert summary["scene_count"] == 3
    assert summary["event_ledger_count"] == 2
    assert summary["character_profile_count"] == 4
    assert summary["alias_count"] == 2
