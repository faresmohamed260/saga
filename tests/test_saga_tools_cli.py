import json
import threading
import time

import saga_tools
import services.encoder_persistence_service as encoder_persistence_service
from services.encoder_persistence_service import RateLimitGuardError
from saga_tools import (
    _book_checkpoint_path,
    _validate_contract,
    audit_corpus,
    build_parser,
    build_sequel_context,
    build_sequel_context_neo4j,
    compare_generation_models,
    encode_store,
    generate_blueprint,
    generate_blueprint_neo4j,
    inspect_corpus,
    rebuild_corpus,
    repair_corpus,
    probe_neo4j,
    register_corpus,
)

from tests.test_narrative_context_service import _sample_contract


def test_validate_contract_accepts_sample_contract():
    _validate_contract(_sample_contract())


def test_cli_parser_accepts_build_sequel_context_command(tmp_path):
    contract_path = tmp_path / "contract.json"
    out_path = tmp_path / "sequel_context.json"
    contract_path.write_text(json.dumps(_sample_contract()), encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(
        [
            "build-sequel-context",
            "--contract",
            str(contract_path),
            "--out",
            str(out_path),
        ]
    )
    build_sequel_context(args)

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["meta"]["book_title"] == "Harry Potter and the Order of the Phoenix"
    assert payload["story_ending"]["last_scene"]["summary"] == "Harry confides in Hermione at Grimmauld Place."


def test_cli_encode_store_defaults_to_full_chapters():
    parser = build_parser()
    args = parser.parse_args(
        [
            "encode-store",
            "--book",
            "example.epub",
        ]
    )
    assert args.target_scene_words == 0
    assert args.max_parallel_books == 2


def test_cli_parser_accepts_audit_repair_rebuild_and_compare_commands():
    parser = build_parser()
    audit_args = parser.parse_args(["audit-corpus", "--series-id", "acotar", "--ollama-model", "gemma4:31b-cloud"])
    assert audit_args.series_id == "acotar"
    assert audit_args.ollama_model == "gemma4:31b-cloud"
    assert parser.parse_args(["repair-corpus", "--series-id", "acotar", "--output-dir", "tmp", "--model-mode", "gpt_oss"]).output_dir == "tmp"
    assert parser.parse_args(["rebuild-corpus", "--series-id", "acotar", "--output-dir", "tmp", "--model-mode", "gpt_oss"]).output_dir == "tmp"
    assert parser.parse_args(["rebuild-corpus", "--series-id", "acotar", "--output-dir", "tmp", "--source-dir", "D:\\Books"]).source_dir == "D:\\Books"
    compare_args = parser.parse_args([
        "compare-generation-models",
        "--series-id",
        "acotar",
        "--prompt",
        "Compare models.",
        "--output-dir",
        "tmp",
    ])
    assert compare_args.series_id == "acotar"


def test_book_checkpoint_path_is_series_scoped():
    path = _book_checkpoint_path("harry-potter", 4, "Goblet of Fire.epub")
    assert "harry-potter" in str(path)
    assert str(path).endswith("04_Goblet of Fire.epub.checkpoint.json")


def test_cli_build_sequel_context_prefers_exported_artifact(tmp_path):
    contract = _sample_contract()
    exported = {
        "meta": {"book_title": "Cached Contract"},
        "story_ending": {"last_scene": {"summary": "Cached."}, "critical_path_tail": []},
        "character_states": [],
        "relationship_summary": [],
        "unresolved_threads": [],
        "causal_chains": [],
        "flexible_events": [],
        "character_trajectories": [],
        "stats": {"characters_retrieved": 0},
    }
    contract["outputs"]["sequel_artifacts"] = {"context": exported, "blueprint": {}}
    contract_path = tmp_path / "contract.json"
    out_path = tmp_path / "sequel_context.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(
        [
            "build-sequel-context",
            "--contract",
            str(contract_path),
            "--out",
            str(out_path),
        ]
    )
    build_sequel_context(args)

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload == exported


def test_cli_generate_blueprint_prefers_exported_artifact_by_default(tmp_path, monkeypatch):
    contract = _sample_contract()
    exported_context = {
        "meta": {"book_title": "Cached Contract"},
        "story_ending": {"last_scene": {"summary": "Cached."}, "critical_path_tail": []},
        "character_states": [],
        "relationship_summary": [],
        "unresolved_threads": [],
        "causal_chains": [],
        "flexible_events": [],
        "character_trajectories": [],
        "stats": {"characters_retrieved": 0},
    }
    exported_blueprint = {
        "title": "Cached Blueprint",
        "premise": "Cached premise.",
        "structure_type": "linear",
        "canon_placement": "post_canon",
        "continuity_anchor": "",
        "divergence_anchor": "",
        "canon_elements_preserved": [],
        "new_plot_thread": "",
        "relationship_targets": [],
        "total_chapters": 10,
        "central_conflict": "Cached conflict",
        "primary_arcs": [],
        "acts": [
            {"label": "Part One", "chapter_range": "1-3", "narrative_goal": "Set up.", "ends_with": "Turn.", "dominant_arcs": []},
            {"label": "Part Two", "chapter_range": "4-7", "narrative_goal": "Escalate.", "ends_with": "Break.", "dominant_arcs": []},
            {"label": "Part Three", "chapter_range": "8-10", "narrative_goal": "Resolve.", "ends_with": "Finale.", "dominant_arcs": []},
        ],
        "world_threads_activated": [],
        "tone": "quiet",
    }
    contract["outputs"]["sequel_artifacts"] = {"context": exported_context, "blueprint": exported_blueprint}
    contract_path = tmp_path / "contract.json"
    out_path = tmp_path / "blueprint.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    class _DummyLLM:
        MODE_DEEPSEEK = "deepseek"
        MODE_GPT_OSS = "gpt_oss"
        MODE_MISTRAL = "mistral"
        MODE_GEMINI = "gemini"

        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class _DummyDecoder:
        def __init__(self, llm_client=None):
            self.llm_client = llm_client

        def build_or_load_blueprint(self, payload, **kwargs):
            assert kwargs["generation_controls"]["chapter_count"] == 12
            assert kwargs["generation_controls"]["canon_position"] == "mid_canon_insert"
            assert kwargs["generation_controls"]["new_plot"] == "Introduce a political succession crisis."
            assert kwargs["generation_controls"]["primary_pov_character"] == "Hermione Granger"
            assert kwargs["generation_controls"]["relationship_directions"][0]["characters"] == ["Harry Potter", "Hermione Granger"]
            assert kwargs["generation_controls"]["relationship_directions"][0]["relationship_type"] == "romance"
            assert kwargs["prefer_exported_context"] is True
            assert kwargs["prefer_exported_blueprint"] is True
            return exported_context, exported_blueprint

    monkeypatch.setattr(saga_tools, "LLMClient", _DummyLLM)
    monkeypatch.setattr(saga_tools, "NarrativeGenerationService", _DummyDecoder)

    parser = build_parser()
    args = parser.parse_args(
        [
            "generate-blueprint",
            "--contract",
            str(contract_path),
            "--prompt",
            "Use the cached blueprint.",
            "--chapters",
            "12",
            "--canon-position",
            "mid_canon_insert",
            "--new-plot",
            "Introduce a political succession crisis.",
            "--primary-pov",
            "Hermione Granger",
            "--relationship-direction",
            "Harry Potter,Hermione Granger|romance|grow closer under pressure|slow-burn trust",
            "--out",
            str(out_path),
        ]
    )
    generate_blueprint(args)

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload == exported_blueprint


def test_cli_generate_blueprint_passes_divergent_controls(tmp_path, monkeypatch):
    contract = _sample_contract()
    contract_path = tmp_path / "contract.json"
    out_path = tmp_path / "blueprint.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    class _DummyLLM:
        MODE_DEEPSEEK = "deepseek"
        MODE_GPT_OSS = "gpt_oss"
        MODE_MISTRAL = "mistral"
        MODE_GEMINI = "gemini"

        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class _DummyDecoder:
        def __init__(self, llm_client=None):
            self.llm_client = llm_client

        def build_or_load_blueprint(self, payload, **kwargs):
            controls = kwargs["generation_controls"]
            assert controls["canon_position"] == "mid_canon_divergent"
            assert controls["divergence_anchor"] == "Harry confides in Hermione at Grimmauld Place."
            assert controls["canon_elements_to_preserve"] == [
                {"event_id": "t_1", "description": "Harry and Hermione regroup after the battle."}
            ]
            return {"meta": {"book_title": "Test"}}, {
                "title": "Branch Blueprint",
                "premise": "Premise",
                "structure_type": "linear",
                "canon_placement": "mid_canon_divergent",
                "continuity_anchor": "",
                "divergence_anchor": "Harry confides in Hermione at Grimmauld Place.",
                "canon_elements_preserved": ["Harry and Hermione regroup after the battle."],
                "new_plot_thread": "",
                "relationship_targets": [],
                "total_chapters": 14,
                "central_conflict": "Conflict",
                "primary_arcs": [],
                "acts": [
                    {"label": "Part One", "chapter_range": "1-4", "narrative_goal": "Set up.", "ends_with": "Turn.", "dominant_arcs": []},
                    {"label": "Part Two", "chapter_range": "5-9", "narrative_goal": "Escalate.", "ends_with": "Break.", "dominant_arcs": []},
                    {"label": "Part Three", "chapter_range": "10-14", "narrative_goal": "Resolve.", "ends_with": "Finale.", "dominant_arcs": []},
                ],
                "world_threads_activated": [],
                "tone": "dramatic",
            }

    monkeypatch.setattr(saga_tools, "LLMClient", _DummyLLM)
    monkeypatch.setattr(saga_tools, "NarrativeGenerationService", _DummyDecoder)

    parser = build_parser()
    args = parser.parse_args(
        [
            "generate-blueprint",
            "--contract",
            str(contract_path),
            "--prompt",
            "Rewrite from the confessional scene onward.",
            "--chapters",
            "14",
            "--canon-position",
            "mid_canon_divergent",
            "--divergence-anchor",
            "Harry confides in Hermione at Grimmauld Place.",
            "--preserve-event",
            "t_1|Harry and Hermione regroup after the battle.",
            "--out",
            str(out_path),
        ]
    )
    generate_blueprint(args)

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["canon_placement"] == "mid_canon_divergent"


def test_cli_probe_neo4j_uses_service_preflight(monkeypatch, capsys):
    class _DummyService:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def probe_connection(self):
            return {"status": "ok", "uri": self.kwargs["uri"], "database": self.kwargs["database"]}

        def close(self):
            return None

    monkeypatch.setattr(saga_tools, "Neo4jIngestionService", _DummyService)

    parser = build_parser()
    args = parser.parse_args(
        [
            "probe-neo4j",
            "--uri",
            "bolt://localhost:7687",
            "--username",
            "neo4j",
            "--password",
            "secret",
            "--database",
            "neo4j",
        ]
    )
    probe_neo4j(args)
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["neo4j_preflight"]["status"] == "ok"
    assert payload["neo4j_preflight"]["uri"] == "bolt://localhost:7687"


def test_cli_encode_store_uses_encoder_and_ingestion(monkeypatch, tmp_path, capsys):
    sample_contract = _sample_contract()
    book_path = tmp_path / "book.epub"
    book_path.write_bytes(b"dummy book")

    class _DummyEncoder:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.series_id = kwargs["series_id"]
            self.series_title = kwargs["series_title"]
            assert kwargs["series_id"] == "harry-potter"
            assert kwargs["series_title"] == "Harry Potter"
            assert kwargs["book_index_base"] == 6

        def _prepare_book_inputs(self, books):
            return [{
                **books[0],
                "book_index": 6,
                "source_hash_sha256": "abc123",
                "source_size_bytes": 10,
                "source_mtime_utc": "2026-01-01T00:00:00+00:00",
            }]

        def _series_context(self, prepared_books):
            return self.series_id, self.series_title

        def encode_and_persist(self, books, neo4j_service=None, progress_callback=None, checkpoint_path=None):
            assert books[0]["path"].endswith("book.epub")
            assert checkpoint_path is not None
            return {
                "contract": sample_contract,
                "ingest_result": {"status": "ok"},
            }

    class _DummyNeo4j:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def register_series(self, series_id, series_title):
            return {"status": "ok", "series_id": series_id, "series_title": series_title}

        def plan_ingest(self, series_id, books):
            return {"series_id": series_id, "books": [{"title": books[0]["title"], "action": "new"}], "summary": {"new": 1, "unchanged": 0, "stale": 0, "conflict": 0}}

        def close(self):
            return None

    monkeypatch.setattr(encoder_persistence_service, "EncoderPersistenceService", _DummyEncoder)
    monkeypatch.setattr(saga_tools, "Neo4jIngestionService", _DummyNeo4j)
    monkeypatch.setattr(
        saga_tools.LLMClient,
        "probe_ollama_mode_access",
        classmethod(lambda cls, mode, model_name: {"status": "ok", "mode": mode, "model": model_name}),
    )

    parser = build_parser()
    out_path = tmp_path / "contract.json"
    args = parser.parse_args(
        [
            "encode-store",
            "--book",
            str(book_path),
            "--series-id",
            "harry-potter",
            "--series-title",
            "Harry Potter",
            "--book-index-base",
            "6",
            "--out",
            str(out_path),
        ]
    )
    encode_store(args)
    output = capsys.readouterr().out
    json_start = output.index("{")
    payload = json.loads(output[json_start:])
    assert payload["encoded"]["books"] == 1
    assert payload["ingest"][0]["status"] == "ok"
    assert payload["plan"]["summary"]["new"] == 1
    assert out_path.exists()
    status_payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert status_payload["status"] == "completed"
    assert payload["status_file"].endswith("status.json")
    assert payload["log_file"].endswith("encode.log")
    assert "Run status written to:" in output


def test_cli_encode_store_skips_unchanged_books(monkeypatch, tmp_path, capsys):
    book_path = tmp_path / "book.epub"
    book_path.write_bytes(b"dummy book")

    class _DummyEncoder:
        def __init__(self, **kwargs):
            self.series_id = kwargs["series_id"]
            self.series_title = kwargs["series_title"]

        def _prepare_book_inputs(self, books):
            return [{
                **books[0],
                "book_index": 1,
                "source_hash_sha256": "same-hash",
                "source_size_bytes": 10,
                "source_mtime_utc": "2026-01-01T00:00:00+00:00",
            }]

        def _series_context(self, prepared_books):
            return self.series_id, self.series_title

        def encode_and_persist(self, books, neo4j_service=None, progress_callback=None):
            raise AssertionError("encode_and_persist should not be called for unchanged books")

    class _DummyNeo4j:
        def __init__(self, **kwargs):
            pass

        def register_series(self, series_id, series_title):
            return {"status": "ok"}

        def plan_ingest(self, series_id, books):
            return {"series_id": series_id, "books": [{"title": books[0]["title"], "action": "unchanged"}], "summary": {"new": 0, "unchanged": 1, "stale": 0, "conflict": 0}}

        def close(self):
            return None

    monkeypatch.setattr(encoder_persistence_service, "EncoderPersistenceService", _DummyEncoder)
    monkeypatch.setattr(saga_tools, "Neo4jIngestionService", _DummyNeo4j)
    monkeypatch.setattr(
        saga_tools.LLMClient,
        "probe_ollama_mode_access",
        classmethod(lambda cls, mode, model_name: {"status": "ok", "mode": mode, "model": model_name}),
    )
    parser = build_parser()
    args = parser.parse_args(["encode-store", "--book", str(book_path), "--series-id", "harry-potter"])
    encode_store(args)
    payload = json.loads(capsys.readouterr().out)
    assert payload["ingest"]["status"] == "skipped"
    assert payload["status_file"].endswith("status.json")


def test_cli_encode_store_blocks_remaining_books_after_rate_limit(monkeypatch, tmp_path, capsys):
    first_book = tmp_path / "book1.epub"
    second_book = tmp_path / "book2.epub"
    first_book.write_bytes(b"book one")
    second_book.write_bytes(b"book two")

    class _DummyEncoder:
        def __init__(self, **kwargs):
            self.series_id = kwargs["series_id"]
            self.series_title = kwargs["series_title"]
            self.book_index_base = kwargs["book_index_base"]

        def _prepare_book_inputs(self, books):
            prepared = []
            for index, book in enumerate(books, start=self.book_index_base):
                prepared.append({
                    **book,
                    "book_index": index,
                    "source_hash_sha256": f"hash-{index}",
                    "source_size_bytes": 10,
                    "source_mtime_utc": "2026-01-01T00:00:00+00:00",
                })
            return prepared

        def _series_context(self, prepared_books):
            return self.series_id, self.series_title

        def encode_and_persist(self, books, neo4j_service=None, progress_callback=None, checkpoint_path=None):
            raise RateLimitGuardError("Rate limit exhausted while processing book 1.")

    class _DummyNeo4j:
        def __init__(self, **kwargs):
            pass

        def register_series(self, series_id, series_title):
            return {"status": "ok"}

        def plan_ingest(self, series_id, books):
            return {
                "series_id": series_id,
                "books": [
                    {"title": books[0]["title"], "action": "new"},
                    {"title": books[1]["title"], "action": "new"},
                ],
                "summary": {"new": 2, "unchanged": 0, "stale": 0, "conflict": 0},
            }

        def close(self):
            return None

    monkeypatch.setattr(encoder_persistence_service, "EncoderPersistenceService", _DummyEncoder)
    monkeypatch.setattr(saga_tools, "Neo4jIngestionService", _DummyNeo4j)
    monkeypatch.setattr(
        saga_tools.LLMClient,
        "probe_ollama_mode_access",
        classmethod(lambda cls, mode, model_name: {"status": "ok", "mode": mode, "model": model_name}),
    )

    parser = build_parser()
    out_path = tmp_path / "status.json"
    args = parser.parse_args([
        "encode-store",
        "--book",
        str(first_book),
        "--book",
        str(second_book),
        "--series-id",
        "harry-potter",
        "--series-title",
        "Harry Potter",
        "--out",
        str(out_path),
    ])
    encode_store(args)

    output = capsys.readouterr().out
    json_start = output.index("{")
    payload = json.loads(output[json_start:])
    assert payload["run_status"] == "blocked_rate_limit"


def test_cli_encode_store_can_run_books_in_parallel(monkeypatch, tmp_path, capsys):
    first_book = tmp_path / "book1.epub"
    second_book = tmp_path / "book2.epub"
    first_book.write_bytes(b"book one")
    second_book.write_bytes(b"book two")

    sample_contract = _sample_contract()
    started = {"count": 0, "overlap": False}
    lock = threading.Lock()
    release_event = threading.Event()

    class _DummyEncoder:
        def __init__(self, **kwargs):
            self.series_id = kwargs["series_id"]
            self.series_title = kwargs["series_title"]
            self.book_index_base = kwargs["book_index_base"]

        def _prepare_book_inputs(self, books):
            prepared = []
            for index, book in enumerate(books, start=self.book_index_base):
                prepared.append({
                    **book,
                    "book_index": index,
                    "source_hash_sha256": f"hash-{index}",
                    "source_size_bytes": 10,
                    "source_mtime_utc": "2026-01-01T00:00:00+00:00",
                })
            return prepared

        def _series_context(self, prepared_books):
            return self.series_id, self.series_title

        def encode_and_persist(self, books, neo4j_service=None, progress_callback=None, checkpoint_path=None):
            with lock:
                started["count"] += 1
                if started["count"] >= 2:
                    started["overlap"] = True
            if progress_callback:
                progress_callback("scene", {"scene_position": 1, "total_scenes": 1})
            release_event.wait(timeout=2)
            contract = json.loads(json.dumps(sample_contract))
            contract["inputs"]["books"][0]["title"] = books[0]["title"]
            return {
                "contract": contract,
                "ingest_result": {"status": "ok", "book": books[0]["title"]},
            }

    class _DummyNeo4j:
        def __init__(self, **kwargs):
            pass

        def register_series(self, series_id, series_title):
            return {"status": "ok"}

        def plan_ingest(self, series_id, books):
            return {
                "series_id": series_id,
                "books": [
                    {"title": books[0]["title"], "action": "new"},
                    {"title": books[1]["title"], "action": "new"},
                ],
                "summary": {"new": 2, "unchanged": 0, "stale": 0, "conflict": 0},
            }

        def close(self):
            return None

        def ingest_contract(self, payload, replace_existing=False):
            return {"status": "ok"}

    monkeypatch.setattr(encoder_persistence_service, "EncoderPersistenceService", _DummyEncoder)
    monkeypatch.setattr(saga_tools, "Neo4jIngestionService", _DummyNeo4j)
    monkeypatch.setattr(
        saga_tools.LLMClient,
        "probe_ollama_mode_access",
        classmethod(lambda cls, mode, model_name, api_key=None: {"status": "ok", "mode": mode, "model": model_name}),
    )

    def _release():
        time.sleep(0.2)
        release_event.set()

    releaser = threading.Thread(target=_release, daemon=True)
    releaser.start()

    parser = build_parser()
    args = parser.parse_args([
        "encode-store",
        "--book",
        str(first_book),
        "--book",
        str(second_book),
        "--series-id",
        "harry-potter",
        "--series-title",
        "Harry Potter",
        "--max-parallel-books",
        "2",
    ])
    encode_store(args)

    payload = json.loads(capsys.readouterr().out)
    assert payload["encoded"]["books"] == 2
    assert started["overlap"] is True


def test_cli_register_and_inspect_corpus(monkeypatch, capsys):
    class _DummyNeo4j:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def register_series(self, series_id, series_title):
            return {"status": "ok", "series_id": series_id, "series_title": series_title}

        def inspect_series(self, series_id):
            return {"series_id": series_id, "title": "Harry Potter", "book_count": 7, "books": []}

        def close(self):
            return None

    monkeypatch.setattr(saga_tools, "Neo4jIngestionService", _DummyNeo4j)
    parser = build_parser()
    reg_args = parser.parse_args(["register-corpus", "--series-id", "harry-potter", "--series-title", "Harry Potter"])
    register_corpus(reg_args)
    reg_payload = json.loads(capsys.readouterr().out)
    assert reg_payload["series_id"] == "harry-potter"

    inspect_args = parser.parse_args(["inspect-corpus", "--series-id", "harry-potter"])
    inspect_corpus(inspect_args)
    inspect_payload = json.loads(capsys.readouterr().out)
    assert inspect_payload["book_count"] == 7


def test_cli_build_sequel_context_neo4j(monkeypatch, tmp_path):
    exported = {
        "meta": {"book_title": "Persisted Book"},
        "story_ending": {"last_scene": {"summary": "Cached."}, "critical_path_tail": []},
        "character_states": [],
        "relationship_summary": [],
        "unresolved_threads": [],
        "causal_chains": [],
        "flexible_events": [],
        "character_trajectories": [],
        "stats": {"characters_retrieved": 0},
    }

    class _DummyGraphService:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def build_from_graph(self, **kwargs):
            assert kwargs["series_id"] == "harry-potter"
            assert kwargs["book_titles"] == ["Persisted Book"]
            return exported

        def close(self):
            return None

    monkeypatch.setattr(saga_tools, "Neo4jNarrativeContextService", _DummyGraphService)
    out_path = tmp_path / "context.json"
    parser = build_parser()
    args = parser.parse_args(
        [
            "build-sequel-context-neo4j",
            "--series-id",
            "harry-potter",
            "--book-title",
            "Persisted Book",
            "--out",
            str(out_path),
        ]
    )
    build_sequel_context_neo4j(args)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload == exported


def test_cli_generate_blueprint_neo4j(monkeypatch, tmp_path):
    retrieval = {
        "meta": {"book_title": "Persisted Book"},
        "story_ending": {"last_scene": {"summary": "Ending."}, "critical_path_tail": []},
        "character_states": [],
        "relationship_summary": [],
        "unresolved_threads": [],
        "causal_chains": [],
        "flexible_events": [],
        "character_trajectories": [],
        "stats": {},
    }
    blueprint = {
        "title": "Graph Blueprint",
        "premise": "Premise",
        "structure_type": "linear",
        "canon_placement": "pre_canon",
        "continuity_anchor": "before the selected canon scope",
        "divergence_anchor": "",
        "canon_elements_preserved": [],
        "new_plot_thread": "A hidden court conspiracy surfaces.",
        "relationship_targets": [],
        "total_chapters": 10,
        "central_conflict": "Conflict",
        "primary_arcs": [],
        "acts": [
            {"label": "Part One", "chapter_range": "1-3", "narrative_goal": "Set up.", "ends_with": "Turn.", "dominant_arcs": []},
            {"label": "Part Two", "chapter_range": "4-7", "narrative_goal": "Escalate.", "ends_with": "Break.", "dominant_arcs": []},
            {"label": "Part Three", "chapter_range": "8-10", "narrative_goal": "Resolve.", "ends_with": "Finale.", "dominant_arcs": []},
        ],
        "world_threads_activated": [],
        "tone": "hopeful",
    }

    class _DummyLLM:
        MODE_DEEPSEEK = "deepseek"
        MODE_GPT_OSS = "gpt_oss"
        MODE_MISTRAL = "mistral"
        MODE_GEMINI = "gemini"

        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class _DummyDecoder:
        def __init__(self, llm_client=None):
            self.llm_client = llm_client

        def build_retrieval_context_from_neo4j(self, **kwargs):
            assert kwargs["series_id"] == "harry-potter"
            assert kwargs["book_titles"] == ["Persisted Book"]
            return retrieval

        def generate_blueprint(self, compiled):
            return blueprint

        @property
        def controls(self):
            return self._controls

        @controls.setter
        def controls(self, value):
            self._controls = value

        def compile_context(self, retrieval_json, user_prompt, generation_controls=None):
            assert retrieval_json == retrieval
            self.controls = generation_controls
            assert generation_controls["canon_position"] == "pre_canon"
            assert generation_controls["chapter_count"] == 10
            assert generation_controls["new_plot"] == "A hidden court conspiracy surfaces."
            return {"book_title": "Persisted Book", "user_prompt": user_prompt, "generation_controls": generation_controls}

    monkeypatch.setattr(saga_tools, "LLMClient", _DummyLLM)
    monkeypatch.setattr(saga_tools, "NarrativeGenerationService", _DummyDecoder)
    out_path = tmp_path / "blueprint.json"
    parser = build_parser()
    args = parser.parse_args(
        [
            "generate-blueprint-neo4j",
            "--series-id",
            "harry-potter",
            "--book-title",
            "Persisted Book",
            "--prompt",
            "Continue from the graph state.",
            "--chapters",
            "10",
            "--canon-position",
            "pre_canon",
            "--new-plot",
            "A hidden court conspiracy surfaces.",
            "--out",
            str(out_path),
        ]
    )
    generate_blueprint_neo4j(args)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload == blueprint


def test_cli_generate_sequel_neo4j_passes_ollama_model_override(monkeypatch, tmp_path):
    captured = {}

    class _DummyLLM:
        MODE_DEEPSEEK = "deepseek"
        MODE_GPT_OSS = "gpt_oss"
        MODE_MISTRAL = "mistral"
        MODE_GEMINI = "gemini"

        def __init__(self, **kwargs):
            captured.update(kwargs)

    class _DummyDecoder:
        def __init__(self, llm_client=None):
            self.llm_client = llm_client

        def generate_sequel_from_neo4j(self, **kwargs):
            target = tmp_path / "out"
            target.mkdir(parents=True, exist_ok=True)
            return target

    monkeypatch.setattr(saga_tools, "LLMClient", _DummyLLM)
    monkeypatch.setattr(saga_tools, "NarrativeGenerationService", _DummyDecoder)

    parser = build_parser()
    args = parser.parse_args(
        [
            "generate-sequel-neo4j",
            "--series-id",
            "acotar",
            "--prompt",
            "Continue from stored canon.",
            "--output-dir",
            str(tmp_path / "out"),
            "--model-mode",
            "gpt_oss",
            "--ollama-model",
            "gemma4:31b-cloud",
        ]
    )

    saga_tools.generate_sequel_neo4j(args)

    assert captured["mode"] == "gpt_oss"
    assert captured["ollama_model_override"] == "gemma4:31b-cloud"
