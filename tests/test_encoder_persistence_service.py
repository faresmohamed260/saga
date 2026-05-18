import logging

from services.encoder_persistence_service import EncoderPersistenceService


def test_encoder_defaults_to_full_chapter_processing():
    service = EncoderPersistenceService()
    assert service.target_scene_words == 0


def test_encoder_fallback_from_full_chapter_uses_large_chunks_first():
    service = EncoderPersistenceService()
    assert service._next_smaller_scene_target(0) == 2400
    assert service._next_smaller_scene_target(2400) == 1800
    assert service._next_smaller_scene_target(900) == 700
    assert service._next_smaller_scene_target(250) is None


def test_checkpoint_write_failure_does_not_raise(monkeypatch, tmp_path, caplog):
    service = EncoderPersistenceService()

    def _boom(*args, **kwargs):
        raise OSError(22, "Invalid argument")

    monkeypatch.setattr("services.encoder_persistence_service.os.replace", _boom)
    checkpoint_path = tmp_path / "checkpoint.json"

    with caplog.at_level(logging.ERROR):
        service._save_checkpoint(
            checkpoint_path,
            {"title": "Book", "book_index": 4, "source_hash_sha256": "hash"},
            "harry-potter",
            "Harry Potter",
            [],
            {"alias_map": {}, "rejected_non_characters": [], "decisions": [], "alias_history": []},
            [],
            [],
            phase="scene",
            total_scenes=37,
            causal_graph_result=service._empty_causal_graph_result(),
        )

    assert any("Checkpoint write failed" in record.getMessage() for record in caplog.records)
