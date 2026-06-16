from __future__ import annotations

import json
from pathlib import Path

from redesign_lab.identity.booknlp_identity_adapter import clean_booknlp_identity
from redesign_lab.identity.identity_provider import BookNLPCleanIdentityProvider, run_booknlp_identity_integration_smoke


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_clean_identity(tmp_path: Path) -> Path:
    raw = {
        "system": "booknlp_small",
        "stable_characters": [
            {
                "display_name": "[NARRATOR]",
                "aliases": [],
                "proper_mentions": [],
                "common_mentions": [],
                "pronoun_mentions": [{"text": "I", "count": 10}],
                "mention_count": 10,
                "quote_count": 2,
                "first_seen": 1,
                "risk_flags": ["narrator_cluster"],
                "cluster_id": 0,
            },
            {
                "display_name": "Tamlin",
                "aliases": ["Tamlin", "Lord Tamlin"],
                "proper_mentions": [{"text": "Tamlin", "count": 5}],
                "common_mentions": [],
                "pronoun_mentions": [{"text": "he", "count": 3}],
                "mention_count": 8,
                "quote_count": 1,
                "first_seen": 2,
                "risk_flags": [],
                "cluster_id": 1,
            },
            {
                "display_name": "Lucien",
                "aliases": ["Lucien"],
                "proper_mentions": [{"text": "Lucien", "count": 12}],
                "common_mentions": [],
                "pronoun_mentions": [{"text": "he", "count": 6}],
                "mention_count": 18,
                "quote_count": 2,
                "first_seen": 3,
                "risk_flags": [],
                "cluster_id": 2,
            },
            {
                "display_name": "the Suriel",
                "aliases": ["the Suriel", "Suriel"],
                "proper_mentions": [{"text": "Suriel", "count": 3}],
                "common_mentions": [{"text": "the Suriel", "count": 2}],
                "pronoun_mentions": [],
                "mention_count": 5,
                "quote_count": 0,
                "first_seen": 4,
                "risk_flags": [],
                "cluster_id": 3,
            },
            {
                "display_name": "Iâ€",
                "aliases": ["Iâ€"],
                "proper_mentions": [{"text": "Iâ€", "count": 2}],
                "common_mentions": [],
                "pronoun_mentions": [],
                "mention_count": 2,
                "quote_count": 0,
                "first_seen": 1,
                "risk_flags": ["encoding_noise"],
                "cluster_id": 4,
            },
        ],
    }
    input_path = tmp_path / "raw.json"
    output_path = tmp_path / "clean.json"
    report_path = tmp_path / "clean.md"
    _write_json(input_path, raw)
    clean_booknlp_identity(input_path, output_path, report_path)
    return output_path


def test_booknlp_identity_provider_builds_pipeline_schema(tmp_path: Path) -> None:
    clean_path = _build_clean_identity(tmp_path)
    provider = BookNLPCleanIdentityProvider.from_path(clean_path)

    payload = provider.build_pipeline_identity()

    assert payload["provider"] == "booknlp_clean"
    assert len(payload["characters"]) >= 2
    assert payload["narrator"]["display_name"] == "[NARRATOR]"
    assert any(row["display_name"] == "the Suriel" for row in payload["reference_entities"])
    assert payload["alias_index"]["tamlin"] == "char_tamlin"
    assert payload["alias_index"]["lord tamlin"] == "char_tamlin"
    assert provider.resolve_alias("Lucien")["display_name"] == "Lucien"


def test_booknlp_identity_provider_preserves_llm_review_metadata(tmp_path: Path) -> None:
    clean_path = _build_clean_identity(tmp_path)
    payload = json.loads(clean_path.read_text(encoding="utf-8"))
    tamlin_row = next(row for row in payload["stable_named_characters"] if row.get("display_name") == "Tamlin")
    tamlin_row["llm_review"] = {
        "recommended_bucket": "stable",
        "confidence": "high",
        "notes": ["Verified by review layer."],
    }
    clean_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    provider = BookNLPCleanIdentityProvider.from_path(clean_path)
    pipeline = provider.build_pipeline_identity()
    tamlin = next(row for row in pipeline["characters"] if row["display_name"] == "Tamlin")

    assert tamlin["llm_review"]["recommended_bucket"] == "stable"
    assert tamlin["proper_mentions"]


def test_booknlp_identity_smoke_writes_outputs(tmp_path: Path) -> None:
    clean_path = _build_clean_identity(tmp_path)
    contract_path = tmp_path / "contract.json"
    output_path = tmp_path / "smoke.json"
    report_path = tmp_path / "report.md"
    _write_json(
        contract_path,
        {
            "outputs": {
                "scene_analyses": [],
            }
        },
    )

    report = run_booknlp_identity_integration_smoke(
        input_json=clean_path,
        contract_json=contract_path,
        output_json=output_path,
        report_md=report_path,
    )

    assert report["loaded_character_count"] >= 2
    assert report["reference_entity_count"] >= 1
    assert report["alias_resolution"]["Tamlin"]["display_name"] == "Tamlin"
    assert report["narrator"]["display_name"] == "[NARRATOR]"
    assert output_path.exists()
    assert report_path.exists()
