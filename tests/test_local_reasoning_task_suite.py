from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from benchmarks.reasoning.task_suite import TASK_FAMILIES, build_tasks, evaluate_task
from scripts.qualify_local_reasoning import (
    _assess_host_resources,
    _assert_resource_limits,
    _duration_seconds,
    _prepare_lm_studio_model,
    _prepare_local_model,
    _unload_other_models,
    _validate_gold_corpus,
)


def _corpus():
    cases = []
    for index in range(9):
        text = f"Mara entered Hall {index}. She carried the silver key. Rowan greeted Mara at the gate. " * 20
        cases.append({
            "case_id": f"case-{index}", "source_id": f"book-{index % 3}",
            "chapter_index": index + 1, "segment": "opening", "text": text,
        })
    return {"cases": cases}


def test_task_suite_covers_every_required_family_once():
    tasks = build_tasks(_corpus(), scope="screening")
    assert [task.metadata["family"] for task in tasks] == list(TASK_FAMILIES)
    assert len({task.task_id for task in tasks}) == 9
    assert all(task.max_tokens <= 900 for task in tasks)


def test_evidence_evaluator_rejects_invented_quotes_and_accepts_verbatim_quotes():
    task = build_tasks(_corpus(), scope="screening")[0]
    accepted = evaluate_task(task, {"payload": {"events": [
        {"title": "Arrival", "summary": "Mara arrived.", "event_type": "arrival", "evidence_quote": "Mara entered Hall 0."},
        {"title": "Greeting", "summary": "Rowan greeted her.", "event_type": "meeting", "evidence_quote": "Rowan greeted Mara at the gate."},
    ]}})
    rejected = evaluate_task(task, {"payload": {"events": [
        {"title": "Flight", "summary": "Mara flew away.", "event_type": "travel", "evidence_quote": "Mara boarded a spacecraft."},
        {"title": "Greeting", "summary": "Rowan greeted her.", "event_type": "meeting", "evidence_quote": "Rowan greeted Mara at the gate."},
    ]}})
    assert accepted.accepted is True
    assert rejected.accepted is False
    assert rejected.metrics["evidence_precision"] == 0.5


def test_evidence_evaluator_normalizes_typographic_punctuation_only():
    task = build_tasks(_corpus(), scope="screening")[0]
    task.metadata["source_text"] = "\u201cMara entered Hall 0.\u201d She carried the silver key."
    result = evaluate_task(task, {"payload": {"events": [
        {"evidence_quote": '"Mara entered Hall 0."'},
        {"evidence_quote": "She carried the silver key."},
    ]}})
    assert result.accepted is True
    assert result.metrics["evidence_precision"] == 1.0


def test_tool_and_metadata_evaluators_require_exact_arguments():
    tasks = build_tasks(_corpus(), scope="screening")
    metadata_task = next(task for task in tasks if task.metadata["family"] == "structured_json")
    tool_task = next(task for task in tasks if task.metadata["family"] == "tool_use")

    assert evaluate_task(metadata_task, {"payload": dict(metadata_task.metadata["expected"])}).accepted
    expected = dict(tool_task.metadata["expected_arguments"])
    assert evaluate_task(tool_task, {"payload": {"tool_calls": [{"tool": "fetch_passage", "arguments": expected}]}}).accepted
    assert not evaluate_task(tool_task, {"payload": {"tool_calls": [{"tool": "fetch_passage", "arguments": {}}]}}).accepted


def test_full_suite_covers_every_family_across_three_books():
    tasks = build_tasks(_corpus(), scope="full")
    assert len(tasks) == len(TASK_FAMILIES) * 3
    for family in TASK_FAMILIES:
        family_tasks = [task for task in tasks if task.metadata["family"] == family]
        assert len({task.metadata["case_id"].split(":")[0] for task in family_tasks}) == 3


def test_qualification_cli_is_directly_executable():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "qualify_local_reasoning.py"), "--help"],
        cwd=root, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "Exact model identifier" in result.stdout


def test_gold_corpus_validation_requires_exact_versioned_artifact(tmp_path):
    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text('{"corpus_version":"1"}', encoding="utf-8")
    corpus = {"corpus_version": "1"}
    matching_gold = {
        "corpus_version": "1",
        "corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
    }

    _validate_gold_corpus(corpus_path=corpus_path, corpus=corpus, gold=matching_gold)

    with pytest.raises(ValueError, match="exact corpus artifact"):
        _validate_gold_corpus(
            corpus_path=corpus_path,
            corpus=corpus,
            gold={**matching_gold, "corpus_sha256": "stale"},
        )


def test_model_preload_uses_the_qualified_context_window(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"load_duration": 1_000_000_000}

    def post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr("scripts.qualify_local_reasoning.requests.post", post)
    evidence = _prepare_local_model(
        model="qwen2.5:14b", url="http://localhost:11434/api/generate",
        keep_alive="30m", timeout_seconds=180, context_tokens=4096,
        gpu_layers=32, threads=8,
    )

    assert captured["json"]["options"] == {
        "num_ctx": 4096, "num_gpu": 32, "num_thread": 8,
    }
    assert evidence["provider_load_seconds"] == 1.0


def test_lm_studio_preload_uses_bounded_explicit_placement(monkeypatch):
    captured = {}
    monkeypatch.setattr("scripts.qualify_local_reasoning.shutil.which", lambda name: "lms")
    states = iter([False, True])
    monkeypatch.setattr(
        "scripts.qualify_local_reasoning._lm_studio_model_loaded",
        lambda **kwargs: next(states),
    )

    class Process:
        returncode = None

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = 0

        def wait(self, timeout):
            return 0

    def popen(command, **kwargs):
        captured.update(command=command, kwargs=kwargs)
        return Process()

    monkeypatch.setattr("scripts.qualify_local_reasoning.subprocess.Popen", popen)
    monkeypatch.setattr("scripts.qualify_local_reasoning.time.sleep", lambda seconds: None)

    evidence = _prepare_lm_studio_model(
        model="openai/gpt-oss-20b",
        timeout_seconds=120,
        context_tokens=4096,
        gpu_offload="0.5",
        ttl_seconds=300,
        models_url="http://localhost:1234/api/v1/models",
    )

    assert captured["command"] == [
        "lms", "load", "openai/gpt-oss-20b",
        "--gpu", "0.5", "--context-length", "4096",
        "--parallel", "1", "--ttl", "300", "--yes",
    ]
    assert captured["kwargs"]["stdout"] is subprocess.DEVNULL
    assert evidence["gpu_offload"] == "0.5"


def test_keep_alive_duration_is_normalized_for_lm_studio_ttl():
    assert _duration_seconds("5m") == 300
    assert _duration_seconds("1h") == 3600
    assert _duration_seconds("30s") == 30


def test_model_switch_evicts_only_other_resident_models(monkeypatch):
    calls = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    monkeypatch.setattr(
        "scripts.qualify_local_reasoning.requests.get",
        lambda *args, **kwargs: Response({"models": [
            {"name": "qwen2.5:14b"}, {"name": "mistral:7b-instruct"},
        ]}),
    )
    monkeypatch.setattr(
        "scripts.qualify_local_reasoning.requests.post",
        lambda *args, **kwargs: calls.append(kwargs["json"]) or Response({}),
    )

    evicted = _unload_other_models(
        requested_model="mistral:7b-instruct",
        generate_url="http://localhost:11434/api/generate",
    )

    assert evicted == ["qwen2.5:14b"]
    assert calls == [{"model": "qwen2.5:14b", "prompt": "", "stream": False, "keep_alive": 0}]


def test_host_admission_records_busy_cpu_without_rejecting_gpu_inference(monkeypatch):
    monkeypatch.setattr("scripts.qualify_local_reasoning.psutil.cpu_percent", lambda interval: 75.0)
    monkeypatch.setattr(
        "scripts.qualify_local_reasoning.psutil.virtual_memory",
        lambda: type("Memory", (), {"available": 64 * 1024 ** 3})(),
    )

    assessment = _assess_host_resources(
        cpu_warning_percent=50.0,
        min_available_ram_bytes=16 * 1024 ** 3,
    )

    assert assessment["cpu_warning"] is True
    assert assessment["baseline_cpu_percent"] == 75.0


def test_host_admission_still_rejects_insufficient_ram(monkeypatch):
    monkeypatch.setattr("scripts.qualify_local_reasoning.psutil.cpu_percent", lambda interval: 10.0)
    monkeypatch.setattr(
        "scripts.qualify_local_reasoning.psutil.virtual_memory",
        lambda: type("Memory", (), {"available": 8 * 1024 ** 3})(),
    )

    with pytest.raises(RuntimeError, match="available RAM"):
        _assess_host_resources(
            cpu_warning_percent=80.0,
            min_available_ram_bytes=16 * 1024 ** 3,
        )


def test_model_preload_rejects_vram_overflow():
    with pytest.raises(RuntimeError, match="peak VRAM"):
        _assert_resource_limits(
            {
                "peak_vram_used_bytes": 11 * 1024 ** 3,
                "peak_host_used_bytes": 64 * 1024 ** 3,
            },
            max_peak_vram_bytes=10 * 1024 ** 3,
            max_peak_host_ram_bytes=112 * 1024 ** 3,
        )
