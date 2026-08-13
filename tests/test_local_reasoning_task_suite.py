from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from benchmarks.reasoning.task_suite import TASK_FAMILIES, build_tasks, evaluate_task
from scripts.qualify_local_reasoning import _prepare_local_model


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
    assert "Exact local Ollama model tag" in result.stdout


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
    )

    assert captured["json"]["options"] == {"num_ctx": 4096}
    assert evidence["provider_load_seconds"] == 1.0
