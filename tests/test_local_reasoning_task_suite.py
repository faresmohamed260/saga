from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from benchmarks.reasoning.task_suite import TASK_FAMILIES, build_tasks, evaluate_task


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
