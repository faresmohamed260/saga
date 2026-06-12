import json
from pathlib import Path

from redesign_lab.benchmarks.common import choose_winner
from redesign_lab.pipeline.chapter_batching import ChapterBatcher
from redesign_lab.pipeline.comparison import generate_comparison_report
from redesign_lab.pipeline.contracts import validate_contract
from redesign_lab.pipeline.decoder_run import DecoderRunStage
from redesign_lab.pipeline.identity_consolidation import IdentityConsolidator
from redesign_lab.pipeline.identity_inventory import IdentityInventoryUpdater, empty_identity_inventory, inventory_to_identity_result
from redesign_lab.pipeline.incremental_identity_roster import IncrementalIdentityRoster


def _sample_chapters():
    return [
        {
            "book_index": 1,
            "chapter_index": 1,
            "chapter_title": "Chapter 1",
            "content": "Feyre hunts in snow. " * 60,
            "source_file": "sample.epub",
        },
        {
            "book_index": 1,
            "chapter_index": 2,
            "chapter_title": "Chapter 2",
            "content": "Tamlin waits in silence. " * 20,
            "source_file": "sample.epub",
        },
        {
            "book_index": 1,
            "chapter_index": 3,
            "chapter_title": "Chapter 3",
            "content": "Lucien watches closely. " * 20,
            "source_file": "sample.epub",
        },
    ]


def test_redesign_contract_validation_accepts_valid_batch():
    payload = {
        "batch_id": "acotar-batch-0001",
        "series_id": "acotar",
        "series_title": "A Court of Thorns and Roses",
        "book_index": 1,
        "chapter_indices": [1],
        "chapter_titles": ["Chapter 1"],
        "source_files": ["sample.epub"],
        "text": "Feyre hunts.",
        "word_count": 2,
        "stage": "chapter_batching",
    }
    assert validate_contract("chapter_batch", payload) == payload


def test_chapter_batcher_groups_short_adjacent_chapters_in_redesign_track():
    batches = ChapterBatcher(target_scene_words=0).build_batches(
        _sample_chapters(),
        series_id="acotar",
        series_title="A Court of Thorns and Roses",
    )
    assert len(batches) == 1
    assert batches[0]["chapter_indices"] == [1, 2, 3]


def test_chapter_batcher_supports_overflow_fallback_mode():
    chapters = [{
        "book_index": 1,
        "chapter_index": 1,
        "chapter_title": "Chapter 1",
        "content": ("Feyre studies the manor and thinks about the curse.\n\n" * 800).strip(),
        "source_file": "sample.epub",
    }]
    batches = ChapterBatcher(target_scene_words=250).build_batches(
        chapters,
        series_id="acotar",
        series_title="A Court of Thorns and Roses",
    )
    assert len(batches) >= 2
    assert all(batch["chapter_indices"] == [1] for batch in batches)


def test_identity_inventory_update_and_consolidation():
    updater = IdentityInventoryUpdater()
    inventory = empty_identity_inventory("acotar")
    extraction_one = {
        "batch_id": "acotar-batch-0001",
        "series_id": "acotar",
        "book_index": 1,
        "chapter_indices": [1],
        "scene_summary": "Feyre meets Tamlin.",
        "canonical_characters": [
            {"name": "Feyre", "role": "human", "names_used": ["Feyre"], "is_new_character": False},
            {"name": "Tamlin", "role": "High Lord", "names_used": ["Tamlin", "High Lord"], "is_new_character": False},
        ],
        "character_mentions": [
            {"mention_text": "the stranger", "mention_type": "descriptor", "canonical_name": "", "is_consequential_character": True}
        ],
        "alias_updates": [
            {"alias": "High Lord", "canonical_name": "Tamlin", "action": "map_alias", "reasoning": "Scene evidence"}
        ],
        "rejected_identity_candidates": ["doe"],
    }
    extraction_two = {
        "batch_id": "acotar-batch-0002",
        "series_id": "acotar",
        "book_index": 2,
        "chapter_indices": [2],
        "scene_summary": "Lucien warns Feyre.",
        "canonical_characters": [
            {"name": "Lucien", "role": "emissary", "names_used": ["Lucien"], "is_new_character": False},
            {"name": "Feyre", "role": "human", "names_used": ["girl"], "is_new_character": False},
        ],
        "character_mentions": [],
        "alias_updates": [],
        "rejected_identity_candidates": [],
    }
    inventory = updater.update(inventory, extraction_one)
    inventory = updater.update(inventory, extraction_two)
    identity_result = inventory_to_identity_result(inventory)
    assert "Tamlin" in identity_result["alias_map"]
    assert "High Lord" in identity_result["alias_map"]["Tamlin"]
    assert "Lucien" in inventory["canonical_characters"]
    consolidated = IdentityConsolidator(use_web_hints=False).consolidate(inventory)
    assert "Tamlin" in consolidated["canonical_characters"]
    assert "Lucien" in consolidated["canonical_characters"]
    assert "doe" in consolidated["rejected_non_characters"]


def test_choose_winner_prefers_semantic_then_validity_then_low_failures_then_speed():
    winner = choose_winner([
        {"candidate_id": "a", "status": "ok", "semantic_score": 0.8, "validity_score": 1.0, "structural_failures": 2.0, "elapsed_seconds": 12.0, "estimated_cost": 1.0},
        {"candidate_id": "b", "status": "ok", "semantic_score": 0.8, "validity_score": 1.0, "structural_failures": 0.0, "elapsed_seconds": 20.0, "estimated_cost": 1.0},
        {"candidate_id": "c", "status": "ok", "semantic_score": 0.7, "validity_score": 1.0, "structural_failures": 0.0, "elapsed_seconds": 1.0, "estimated_cost": 0.0},
    ])
    assert winner["candidate_id"] == "b"


def test_incremental_identity_roster_snapshot_is_chapter_scoped():
    roster = IncrementalIdentityRoster(series_id="acotar", lookahead_chapters=2)
    roster.entries = [
        {
            "canonical_name": "Feyre",
            "aliases": ["the girl"],
            "role": "",
            "mention_count": 12,
            "confidence": 0.9,
            "first_seen": {"book_index": 1, "chapter_index": 1},
            "last_seen": {"book_index": 1, "chapter_index": 2},
            "sources": [],
        },
        {
            "canonical_name": "Rhysand",
            "aliases": ["Rhys"],
            "role": "",
            "mention_count": 6,
            "confidence": 0.88,
            "first_seen": {"book_index": 1, "chapter_index": 4},
            "last_seen": {"book_index": 1, "chapter_index": 4},
            "sources": [],
        },
    ]
    snapshot = roster.snapshot_for_batch(book_index=1, chapter_indices=[1])
    assert "Feyre" in snapshot["alias_map"]
    assert "Rhysand" not in snapshot["alias_map"]
    snapshot_later = roster.snapshot_for_batch(book_index=1, chapter_indices=[2])
    assert "Rhysand" in snapshot_later["alias_map"]


def test_incremental_identity_roster_feedback_can_upgrade_alias_to_full_name():
    roster = IncrementalIdentityRoster(series_id="acotar", lookahead_chapters=2)
    roster.entries = [
        {
            "canonical_name": "Rhys",
            "aliases": [],
            "role": "",
            "mention_count": 3,
            "confidence": 0.8,
            "first_seen": {"book_index": 1, "chapter_index": 3},
            "last_seen": {"book_index": 1, "chapter_index": 3},
            "sources": [],
        }
    ]
    roster.apply_extraction_feedback(
        batch={"book_index": 1, "chapter_indices": [6]},
        extraction={
            "batch_id": "b6",
            "canonical_characters": [
                {"name": "Rhysand", "role": "High Lord", "names_used": ["Rhys", "Rhysand"]},
            ],
            "alias_updates": [],
            "character_mentions": [],
        },
    )
    assert roster.entries[0]["canonical_name"] == "Rhysand"
    assert "Rhys" in roster.entries[0]["aliases"]


def test_decoder_context_accepts_outline_candidate():
    stage = DecoderRunStage(
        blueprint_spec={"candidate_id": "bp", "mode": "gpt_oss"},
        outline_spec={"candidate_id": "ol", "mode": "gpt_oss"},
        prose_spec={"candidate_id": "pr", "mode": "gpt_oss"},
    )
    payload = stage.build_decoder_context(
        series_id="acotar-redesign",
        retrieval_context={"meta": {}, "story_ending": {}, "character_states": [], "relationship_summary": [], "unresolved_threads": [], "retrieval_documents": []},
        generation_controls={},
    )
    assert payload["planner_candidate"] == "bp"
    assert payload["outline_candidate"] == "ol"
    assert payload["prose_candidate"] == "pr"


def test_generate_comparison_report_reads_baseline_and_redesign(tmp_path: Path):
    redesign_root = tmp_path / "redesign"
    baseline_root = tmp_path / "baseline"
    (redesign_root / "end_to_end").mkdir(parents=True)
    baseline_root.mkdir(parents=True)
    (redesign_root / "end_to_end" / "run_report.json").write_text(
        json.dumps({"stable_state_count": 3, "sequel_output_dir": "x", "elapsed_seconds": 12.4}),
        encoding="utf-8",
    )
    status_path = Path("analysis_outputs/encode_runs/acotar/latest_status.json")
    status_path.parent.mkdir(parents=True, exist_ok=True)
    original = status_path.read_text(encoding="utf-8") if status_path.exists() else None
    try:
        status_path.write_text(json.dumps({"status": "completed", "elapsed_seconds": 99.0}), encoding="utf-8")
        report = generate_comparison_report(
            baseline_root=baseline_root,
            redesign_root=redesign_root,
            output_path=tmp_path / "comparison.json",
        )
        assert report["comparison"]["encoder_reliability"] == "completed"
        assert report["comparison"]["stable_state_richness"] == 3
    finally:
        if original is None:
            status_path.unlink(missing_ok=True)
        else:
            status_path.write_text(original, encoding="utf-8")
