from __future__ import annotations

import json
from pathlib import Path

from redesign_lab.training.build_litbank_span_admission_dataset import (
    assign_document_splits,
    build_dataset,
    detect_negative_label,
    detect_person_positive_label,
    load_litbank_span_documents,
)


def _write_doc(root: Path, name: str, text: str, ann: str) -> None:
    (root / f"{name}.txt").write_text(text, encoding="utf-8")
    (root / f"{name}.ann").write_text(ann, encoding="utf-8")


def _make_fixture_dataset(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _write_doc(
        root,
        "doc_a",
        "Mr. Rochester greeted her father.\n\nThe guests waited.\n\nThe old man bowed.\n\nYork Road was wet.\n\nHe smiled.",
        "\n".join(
            [
                "T1\tPROP_PER 0 13\tMr. Rochester",
                "T2\tNOM_PER 22 32\ther father",
                "T3\tNOM_PER 38 48\tThe guests",
                "T4\tNOM_PER 58 69\tThe old man",
                "T5\tLOC 77 86\tYork Road",
                "T6\tPRON_PER 96 98\tHe",
            ]
        ),
    )
    _write_doc(
        root,
        "doc_b",
        "Miss Smith opened the door.\n\nThe doctor hesitated.\n\n??? cracked.",
        "\n".join(
            [
                "T1\tPROP_PER 0 10\tMiss Smith",
                "T2\tOBJ 22 30\tthe door",
                "T3\tOBJ 52 55\t???",
            ]
        ),
    )
    _write_doc(
        root,
        "doc_c",
        "Kareem spoke to Fares.\n\nThe servants listened.",
        "\n".join(
            [
                "T1\tPROP_PER 0 6\tKareem",
                "T2\tPROP_PER 16 21\tFares",
                "T3\tNOM_PER 24 36\tThe servants",
            ]
        ),
    )
    return root


def test_document_level_split_keeps_docs_together():
    splits = assign_document_splits(["a", "b", "c", "d", "e"], seed=7)
    assert set(splits) == {"a", "b", "c", "d", "e"}
    assert set(splits.values()) <= {"train", "dev", "test"}


def test_honorific_label_detection():
    from redesign_lab.training.build_litbank_span_admission_dataset import SpanMention

    mention = SpanMention("T1", "Miss Smith", 0, 10, "PROP_PER", True)
    assert detect_person_positive_label(mention) == "HONORIFIC_PERSON_NAME"


def test_descriptive_reference_label_detection():
    from redesign_lab.training.build_litbank_span_admission_dataset import SpanMention

    mention = SpanMention("T1", "the old man", 0, 11, "NOM_PER", True)
    assert detect_person_positive_label(mention) == "DESCRIPTIVE_PERSON_REFERENCE"


def test_relation_reference_label_detection():
    from redesign_lab.training.build_litbank_span_admission_dataset import SpanMention

    mention = SpanMention("T1", "her father", 0, 10, "NOM_PER", True)
    assert detect_person_positive_label(mention) == "RELATION_PERSON_REFERENCE"


def test_pronoun_label_detection():
    from redesign_lab.training.build_litbank_span_admission_dataset import SpanMention

    mention = SpanMention("T1", "He", 0, 2, "PRON_PER", True)
    assert detect_person_positive_label(mention) == "PRONOUN_REFERENCE"


def test_location_negative_detection():
    assert detect_negative_label("York Road", "LOC") == "LOCATION"


def test_malformed_noise_negative_detection():
    assert detect_negative_label("???", "OBJ") == "MALFORMED_OR_NOISE"


def test_jsonl_output_schema_validity(tmp_path: Path):
    data_root = _make_fixture_dataset(tmp_path / "data")
    output_root = tmp_path / "out"
    summary = build_dataset(
        data_root=data_root,
        output_root=output_root,
        split_seed=11,
        use_model_negatives=False,
    )
    assert (output_root / "train.jsonl").exists()
    assert (output_root / "dev.jsonl").exists()
    assert (output_root / "test.jsonl").exists()
    assert (output_root / "dataset_summary.json").exists()
    assert (output_root / "label_distribution.md").exists()
    rows = []
    for split in ("train", "dev", "test"):
        for line in (output_root / f"{split}.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    assert rows
    required = {
        "doc_id", "split", "span_text", "label", "start_char", "end_char", "sentence",
        "left_context", "right_context", "cluster_id", "mention_count_in_cluster",
        "is_pronoun", "is_gold_person", "features",
    }
    assert required <= set(rows[0])
    assert {"is_capitalized", "is_multi_token", "has_honorific", "in_quote", "has_possessive", "locative_suffix"} <= set(rows[0]["features"])
    assert summary["document_count"] == 3
    docs = load_litbank_span_documents(data_root)
    split_map = assign_document_splits([doc.doc_id for doc in docs], seed=11)
    for doc_id, split in split_map.items():
        seen_splits = {row["split"] for row in rows if row["doc_id"] == doc_id}
        assert seen_splits == {split}
