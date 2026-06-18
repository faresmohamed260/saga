from __future__ import annotations

import json
from pathlib import Path

from saga.identity.identity_provider import resolve_identity_provider_input
from saga.identity.series_identity_provider import build_series_pipeline_identity


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _book_pipeline_identity(path: Path, *, display_name: str, aliases: list[str], book_slug: str) -> Path:
    payload = {
        "provider": "booknlp_clean",
        "characters": [
            {
                "id": f"char_{book_slug}_{display_name.lower()}",
                "display_name": display_name,
                "aliases": aliases,
                "mention_count": 10,
                "quote_count": 2,
                "first_seen": 1,
                "source": "booknlp_small_clean",
                "risk_flags": [],
                "cluster_ids": [1],
            }
        ],
        "narrator": {
            "id": "narrator_0",
            "display_name": "[NARRATOR]",
            "possible_name": None,
            "confidence": "hypothesis",
            "mention_count": 10,
            "quote_count": 1,
            "first_seen": 1,
            "risk_flags": [],
        },
        "reference_entities": [],
        "alias_index": {alias.lower(): f"char_{book_slug}_{display_name.lower()}" for alias in aliases},
        "suppressed_clusters": [],
        "diagnostics": {},
    }
    _write_json(path, payload)
    return path


def test_build_series_pipeline_identity_merges_obvious_short_name_variants(tmp_path: Path) -> None:
    book1_dir = tmp_path / "book_01_acotar"
    book2_dir = tmp_path / "book_02_acomaf"
    book1_dir.mkdir()
    book2_dir.mkdir()
    _book_pipeline_identity(book1_dir / "booknlp_small_pipeline_identity.json", display_name="Rhys", aliases=["Rhys"], book_slug="acotar")
    _book_pipeline_identity(book2_dir / "booknlp_small_pipeline_identity.json", display_name="Rhysand", aliases=["Rhysand", "Rhys"], book_slug="acomaf")

    payload = build_series_pipeline_identity(
        book_summaries=[
            {"book_index": 1, "book_slug": "acotar", "output_dir": str(book1_dir)},
            {"book_index": 2, "book_slug": "acomaf", "output_dir": str(book2_dir)},
        ],
        output_json=tmp_path / "series.json",
    )

    assert len(payload["characters"]) == 1
    assert payload["characters"][0]["display_name"] == "Rhysand"
    assert payload["alias_index"]["rhys"] == payload["characters"][0]["id"]


def test_resolve_identity_provider_input_uses_series_mapping_for_selected_book(tmp_path: Path) -> None:
    book1_dir = tmp_path / "book_01_acotar"
    book5_dir = tmp_path / "book_05_acosf"
    book1_dir.mkdir()
    book5_dir.mkdir()
    path1 = _book_pipeline_identity(book1_dir / "booknlp_small_pipeline_identity.json", display_name="Feyre", aliases=["Feyre"], book_slug="acotar")
    path5 = _book_pipeline_identity(book5_dir / "booknlp_small_pipeline_identity.json", display_name="Nesta", aliases=["Nesta"], book_slug="acosf")
    series_path = tmp_path / "series_identity.json"
    _write_json(
        series_path,
        {
            "series_id": "acotar",
            "characters": [],
            "alias_index": {},
            "book_identity_paths": {
                "acotar": str(path1),
                "acosf": str(path5),
            },
            "reference_entities": [],
            "narrators": [],
            "diagnostics": {},
        },
    )

    provider = resolve_identity_provider_input(
        provider_mode="booknlp_clean",
        input_json=series_path,
        book_inputs=[{"path": r"D:\Books\Ebooks\Sarah J. Maas\A Court of Silver Flames\A Court of Silver Flames.epub", "title": "A Court of Silver Flames.epub", "book_index": 5}],
    )
    payload = provider.build_pipeline_identity(book_inputs=[{"path": r"D:\Books\Ebooks\Sarah J. Maas\A Court of Silver Flames\A Court of Silver Flames.epub", "title": "A Court of Silver Flames.epub", "book_index": 5}])

    assert len(payload["characters"]) == 1
    assert payload["characters"][0]["display_name"] == "Nesta"
