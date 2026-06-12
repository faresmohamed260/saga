import logging

from services.encoder_persistence_service import EncoderPersistenceService


def test_encoder_defaults_to_full_chapter_processing():
    service = EncoderPersistenceService()
    assert service.target_scene_words == 0
    assert service.identity_provider == "booknlp_clean"


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


def test_encoder_identity_resolution_uses_booknlp_provider(monkeypatch, tmp_path):
    service = EncoderPersistenceService(identity_model="gpt_oss", identity_json_path=str(tmp_path / "identity.json"))
    book_path = tmp_path / "book.epub"
    book_path.write_text("stub", encoding="utf-8")

    class StubProvider:
        last_books = None

        def build_identity_result_compat(self, book_inputs=None):
            StubProvider.last_books = list(book_inputs or [])
            return {
                "alias_map": {"Feyre": ["Feyre"]},
                "rejected_non_characters": [],
                "decisions": [],
                "alias_history": [],
                "identity_strategy": "booknlp_small_clean",
                "identity_provider": "booknlp_clean",
            }

    monkeypatch.setattr("services.encoder_persistence_service.resolve_identity_provider_input", lambda **kwargs: StubProvider())

    result = service._run_identity_resolution([{"path": str(book_path), "title": "Book"}])

    assert StubProvider.last_books[0]["title"] == "Book"
    assert result["identity_provider"] == "booknlp_clean"
    assert result["alias_map"]["Feyre"] == ["Feyre"]
