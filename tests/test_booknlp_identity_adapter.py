from __future__ import annotations

import json
from pathlib import Path

from redesign_lab.identity.booknlp_identity_adapter import clean_booknlp_identity


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_booknlp_identity_cleanup_merges_and_suppresses(tmp_path: Path) -> None:
    noise = "\u00e2\u20ac"
    noise_join = "\u00e2\u20ac\u0152"
    raw = {
        "system": "booknlp_small",
        "stable_characters": [
            {
                "display_name": "[NARRATOR]",
                "aliases": [],
                "proper_mentions": [],
                "common_mentions": [],
                "pronoun_mentions": [{"text": "I", "count": 10}, {"text": "my", "count": 8}],
                "mention_count": 20,
                "quote_count": 3,
                "first_seen": 1,
                "risk_flags": ["narrator_cluster", "pov_cluster", "pronoun_only_cluster"],
                "cluster_id": 0,
            },
            {
                "display_name": "Tamlin",
                "aliases": ["Tamlin", "Lord Tamlin", f"Rhys?{noise_join} Tamlin"],
                "proper_mentions": [{"text": "Tamlin", "count": 5}, {"text": "Lord Tamlin", "count": 1}],
                "common_mentions": [],
                "pronoun_mentions": [{"text": "he", "count": 6}],
                "mention_count": 12,
                "quote_count": 4,
                "first_seen": 5,
                "risk_flags": [],
                "cluster_id": 1,
            },
            {
                "display_name": f"Tamlin{noise}",
                "aliases": [f"Tamlin{noise}"],
                "proper_mentions": [{"text": f"Tamlin{noise}", "count": 2}],
                "common_mentions": [],
                "pronoun_mentions": [],
                "mention_count": 2,
                "quote_count": 0,
                "first_seen": 6,
                "risk_flags": ["encoding_noise"],
                "cluster_id": 2,
            },
            {
                "display_name": "Lucien",
                "aliases": ["Lucien", f"you.{noise_join} Lucien", f"Lucien{noise}", "the Cauldron Lucien"],
                "proper_mentions": [{"text": "Lucien", "count": 4}, {"text": f"Lucien{noise}", "count": 1}],
                "common_mentions": [],
                "pronoun_mentions": [{"text": "he", "count": 3}],
                "mention_count": 8,
                "quote_count": 2,
                "first_seen": 8,
                "risk_flags": [],
                "cluster_id": 3,
            },
            {
                "display_name": "Amarantha",
                "aliases": ["Amarantha", f"Amarantha{noise}"],
                "proper_mentions": [{"text": "Amarantha", "count": 3}],
                "common_mentions": [],
                "pronoun_mentions": [{"text": "she", "count": 2}],
                "mention_count": 5,
                "quote_count": 1,
                "first_seen": 9,
                "risk_flags": [],
                "cluster_id": 4,
            },
            {
                "display_name": f"I{noise}",
                "aliases": [f"I{noise}", "I†™ d"],
                "proper_mentions": [{"text": f"I{noise}", "count": 3}],
                "common_mentions": [],
                "pronoun_mentions": [],
                "mention_count": 3,
                "quote_count": 0,
                "first_seen": 3,
                "risk_flags": ["encoding_noise"],
                "cluster_id": 5,
            },
            {
                "display_name": "my father",
                "aliases": ["my father", "My father"],
                "proper_mentions": [],
                "common_mentions": [{"text": "my father", "count": 7}],
                "pronoun_mentions": [{"text": "he", "count": 2}],
                "mention_count": 9,
                "quote_count": 0,
                "first_seen": 2,
                "risk_flags": [],
                "cluster_id": 6,
            },
            {
                "display_name": "the Suriel",
                "aliases": ["the Suriel", "Suriel"],
                "proper_mentions": [{"text": "Suriel", "count": 3}],
                "common_mentions": [{"text": "the Suriel", "count": 2}],
                "pronoun_mentions": [],
                "mention_count": 5,
                "quote_count": 0,
                "first_seen": 7,
                "risk_flags": [],
                "cluster_id": 7,
            },
            {
                "display_name": "The Attor",
                "aliases": ["The Attor", "the Attor"],
                "proper_mentions": [{"text": "The Attor", "count": 4}],
                "common_mentions": [{"text": "the Attor", "count": 2}],
                "pronoun_mentions": [],
                "mention_count": 6,
                "quote_count": 1,
                "first_seen": 7,
                "risk_flags": [],
                "cluster_id": 8,
            },
            {
                "display_name": "Alis",
                "aliases": ["Alis", "Hybern Alis"],
                "proper_mentions": [{"text": "Alis", "count": 6}],
                "common_mentions": [],
                "pronoun_mentions": [],
                "mention_count": 6,
                "quote_count": 1,
                "first_seen": 10,
                "risk_flags": [],
                "cluster_id": 9,
            },
            {
                "display_name": "Feyre",
                "aliases": ["Feyre", "Feyre darling"],
                "proper_mentions": [{"text": "Feyre", "count": 12}],
                "common_mentions": [],
                "pronoun_mentions": [],
                "mention_count": 12,
                "quote_count": 2,
                "first_seen": 4,
                "risk_flags": [],
                "cluster_id": 10,
            },
        ],
    }
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    report_path = tmp_path / "report.md"
    _write_json(input_path, raw)

    cleaned = clean_booknlp_identity(input_path, output_path, report_path)

    stable = {row["display_name"]: row for row in cleaned["stable_named_characters"]}
    refs = {row["display_name"]: row for row in cleaned["reference_entities"]}
    suppressed = {row["display_name"]: row for row in cleaned["suppressed_clusters"]}

    assert "Tamlin" in stable
    assert len(stable["Tamlin"]["merged_from_clusters"]) >= 2
    assert "Lucien" in stable
    assert "Amarantha" in stable
    assert "Alis" in stable
    assert "Lord Tamlin" in stable["Tamlin"]["aliases"]
    assert all("Rhys" not in alias or alias == "Rhys" for alias in stable["Tamlin"]["aliases"])
    assert all("you." not in alias for alias in stable["Lucien"]["aliases"])
    assert "the Cauldron Lucien" not in stable["Lucien"]["aliases"]
    assert "Hybern Alis" not in stable["Alis"]["aliases"]
    assert cleaned["narrator"]["display_name"] == "[NARRATOR]"
    assert cleaned["narrator"]["possible_name"] == "Feyre"
    assert any(name.startswith("I") for name in suppressed)
    assert "my father" in refs
    assert "the Suriel" in refs
    assert "The Attor" in refs
    assert "I" not in cleaned["alias_map"].get("Feyre", [])
    assert report_path.exists()
    assert output_path.exists()


def test_booknlp_identity_cleanup_output_schema(tmp_path: Path) -> None:
    raw = {
        "system": "booknlp_small",
        "stable_characters": [],
    }
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    report_path = tmp_path / "report.md"
    _write_json(input_path, raw)

    cleaned = clean_booknlp_identity(input_path, output_path, report_path)

    assert set(cleaned.keys()) == {
        "system",
        "source_system",
        "stable_named_characters",
        "narrator",
        "reference_entities",
        "suppressed_clusters",
        "alias_map",
        "diagnostics",
    }
    assert isinstance(cleaned["stable_named_characters"], list)
    assert isinstance(cleaned["reference_entities"], list)
    assert isinstance(cleaned["suppressed_clusters"], list)
    assert isinstance(cleaned["diagnostics"], dict)


def test_booknlp_identity_cleanup_merges_short_variant_into_full_name(tmp_path: Path) -> None:
    raw = {
        "system": "booknlp_small",
        "stable_characters": [
            {
                "display_name": "Rhysand",
                "aliases": ["Rhysand"],
                "proper_mentions": [{"text": "Rhysand", "count": 10}],
                "common_mentions": [],
                "pronoun_mentions": [{"text": "he", "count": 5}],
                "mention_count": 20,
                "quote_count": 1,
                "first_seen": 10,
                "risk_flags": [],
                "cluster_id": 1,
            },
            {
                "display_name": "Rhys",
                "aliases": ["Rhys"],
                "proper_mentions": [{"text": "Rhys", "count": 5}],
                "common_mentions": [],
                "pronoun_mentions": [{"text": "he", "count": 1}],
                "mention_count": 5,
                "quote_count": 0,
                "first_seen": 12,
                "risk_flags": ["possible_split_short_name"],
                "cluster_id": 2,
            },
        ],
    }
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    report_path = tmp_path / "report.md"
    _write_json(input_path, raw)

    cleaned = clean_booknlp_identity(input_path, output_path, report_path)
    stable = {row["display_name"]: row for row in cleaned["stable_named_characters"]}

    assert "Rhysand" in stable
    assert "Rhys" not in stable
    assert "Rhys" in stable["Rhysand"]["merged_from_clusters"]
    assert "merged_short_variant" in stable["Rhysand"]["risk_flags"]
