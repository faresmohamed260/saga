from pathlib import Path

from saga.services.database_decoder_service import DatabaseDecoderService
from saga.storage.models import Book
from saga.storage.persistence import SagaSQLiteStore


class _FakeLLMClient:
    def __init__(self, *, mode: str, provider: str, model: str) -> None:
        self.mode = mode
        self._provider = provider
        self._model = model

    def provider_name(self) -> str:
        return self._provider

    def resolved_model_name(self) -> str:
        return self._model


class _FailingDecoder:
    def __init__(self) -> None:
        self.calls = 0
        self.llm = _FakeLLMClient(mode="gpt_oss", provider="ollama", model="gpt-oss:120b-cloud")
        self.planner_llm = self.llm
        self.prose_llm = self.llm

    def generate_sequel_from_contract(self, *args, **kwargs):
        self.calls += 1
        raise ValueError("Decoder blueprint generation failed schema validation: HTTP 429 rate_limited")


class _SuccessfulFallbackDecoder:
    def __init__(self) -> None:
        self.calls = 0
        self.llm = _FakeLLMClient(mode="gpt_oss", provider="ollama", model="gpt-oss:120b-cloud")
        self.planner_llm = _FakeLLMClient(mode="general_compute", provider="general_compute", model="deepseek-v3.1")
        self.prose_llm = self.llm

    def generate_sequel_from_contract(self, contract, *, user_prompt, output_dir, generation_controls, **kwargs):
        self.calls += 1
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        (out_path / "blueprint.json").write_text(
            (
                '{'
                '"title":"Recovered Story",'
                f'"canon_placement":"{generation_controls["canon_position"]}"'
                '}'
            ),
            encoding="utf-8",
        )
        (out_path / "progress.json").write_text('{"status":"completed"}', encoding="utf-8")
        prose = " ".join(["Hermione"] * 260)
        (out_path / "chapter_1.txt").write_text(
            f"Chapter 1\nRecovered Story\n\n{prose}",
            encoding="utf-8",
        )
        return out_path


def test_database_decoder_service_retries_with_fallback_on_rate_limit(monkeypatch, tmp_path):
    store = SagaSQLiteStore(tmp_path / "saga.sqlite")
    with store.session_factory() as session:
        book = Book(id="book-1", series_id="series-1", book_index=1, title="Test Book")
        session.add(book)
        session.commit()

    primary = _FailingDecoder()
    fallback = _SuccessfulFallbackDecoder()
    service = DatabaseDecoderService(sqlite_store=store, decoder=primary)

    monkeypatch.setattr(
        "saga.services.database_decoder_service.load_contract_like",
        lambda book_ref: {"inputs": {"series": {"series_id": "series-1"}}},
    )
    monkeypatch.setattr(service, "_fallback_decoder_for_rate_limit", lambda active_decoder: fallback)

    result = service.generate_and_store(
        book_ref="db://book/book-1",
        series_id="series-1",
        story_mode="mid_canon",
        user_prompt="Write a canon-aware library mystery.",
        chapter_count=1,
        primary_pov_character="Hermione Granger",
    )

    assert primary.calls == 1
    assert fallback.calls == 1
    assert result["chapter_count"] == 1
    assert result["verification"]["valid"] is True

    stored_story = store.get_generated_story(result["story_id"])
    assert stored_story is not None
    assert stored_story["metadata"]["series_id"] == "series-1"
    assert stored_story["metadata"]["planner_provider"] == "general_compute"
