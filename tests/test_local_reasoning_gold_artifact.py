import json
import re
from pathlib import Path


def test_tracked_extraction_gold_is_complete_reviewed_and_source_safe():
    root = Path(__file__).resolve().parents[1]
    path = root / "benchmarks/reasoning/local_extraction_gold_v1.json"
    raw = path.read_text(encoding="utf-8")
    gold = json.loads(raw)
    annotations = list(gold["annotations"])

    assert re.fullmatch(r"[0-9a-f]{64}", gold["corpus_fingerprint"])
    assert len(annotations) == 9
    assert {item["source_id"] for item in annotations} == {
        "the-cruel-prince", "a-court-of-thorns-and-roses", "caraval",
    }
    assert {item["family"] for item in annotations} == {
        "canon_events", "canon_entities", "canon_relationships",
    }
    assert all(item["review_status"] == "reviewed" and item["items"] for item in annotations)
    assert "source_text" not in raw and "evidence_quote" not in raw

    for annotation in annotations:
        for item in annotation["items"]:
            if annotation["family"] == "canon_events":
                spans = item["normalized_evidence_spans"]
                assert spans and all(len(span) == 2 and 0 <= span[0] < span[1] for span in spans)
            elif annotation["family"] == "canon_entities":
                assert item["aliases"] and item["entity_type"] in {
                    "location", "object", "creature", "organization", "artifact", "concept",
                }
            else:
                assert item["source_aliases"] and item["target_aliases"] and item["type_aliases"]
