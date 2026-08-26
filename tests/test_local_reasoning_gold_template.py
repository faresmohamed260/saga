import json
import subprocess
import sys
from pathlib import Path


def test_gold_template_is_source_safe_and_covers_three_families(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    corpus = {
        "suite_id": "suite", "corpus_version": "1", "cases": [
            {"case_id": f"book-{book}-case-{case}", "source_id": f"book-{book}",
             "chapter_index": case + 1, "segment": "opening", "text": "Private passage text."}
            for book in range(3) for case in range(3)
        ],
    }
    corpus_path = tmp_path / "corpus.json"
    output_path = tmp_path / "gold.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    result = subprocess.run([
        sys.executable, str(root / "scripts/build_local_reasoning_gold_template.py"),
        "--corpus", str(corpus_path), "--output", str(output_path),
    ], cwd=root, capture_output=True, text=True, timeout=20)

    assert result.returncode == 0, result.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(payload["annotations"]) == 9
    assert "Private passage text" not in output_path.read_text(encoding="utf-8")
    assert {item["family"] for item in payload["annotations"]} == {
        "canon_events", "canon_entities", "canon_relationships",
    }
    assert payload["version"] == "1.1.0"
    assert "generic props" in payload["annotation_policy"]["canon_entities"]
