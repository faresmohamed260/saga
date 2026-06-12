from __future__ import annotations

import json
from pathlib import Path

from redesign_lab.training.build_litbank_span_admission_dataset import build_dataset
from redesign_lab.training.clean_span_admission_dataset import clean_dataset


def _write_doc(root: Path, name: str, text: str, ann: str) -> None:
    (root / f"{name}.txt").write_text(text, encoding="utf-8")
    (root / f"{name}.ann").write_text(ann, encoding="utf-8")


def _make_fixture_dataset(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _write_doc(
        root,
        "doc_train_a",
        "Mr. Rochester greeted her father. The guests waited. The old man bowed. York Road was wet. He smiled.",
        "\n".join(
            [
                "T1\tPROP_PER 0 13\tMr. Rochester",
                "T2\tNOM_PER 22 32\ther father",
                "T3\tNOM_PER 34 44\tThe guests",
                "T4\tNOM_PER 53 64\tThe old man",
                "T5\tLOC 71 80\tYork Road",
                "T6\tPRON_PER 90 92\tHe",
            ]
        ),
    )
    _write_doc(
        root,
        "doc_train_b",
        "He thanked Miss Smith. She waved to Captain Nemo. The doctor frowned.",
        "\n".join(
            [
                "T1\tPRON_PER 0 2\tHe",
                "T2\tPROP_PER 12 22\tMiss Smith",
                "T3\tPRON_PER 24 27\tShe",
                "T4\tPROP_PER 37 49\tCaptain Nemo",
            ]
        ),
    )
    _write_doc(
        root,
        "doc_dev",
        "Avatar glowed. The masked figure lingered. Their mother arrived.",
        "\n".join(
            [
                "T1\tEVENT 0 6\tAvatar",
                "T2\tNOM_PER 15 32\tThe masked figure",
                "T3\tNOM_PER 43 55\tTheir mother",
            ]
        ),
    )
    return root


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_clean_dataset_preserves_raw_and_writes_outputs(tmp_path: Path):
    data_root = _make_fixture_dataset(tmp_path / "data")
    raw_root = tmp_path / "raw"
    clean_root = tmp_path / "clean"

    build_dataset(
        data_root=data_root,
        output_root=raw_root,
        split_seed=11,
        use_model_negatives=False,
    )
    original_train = (raw_root / "train.jsonl").read_text(encoding="utf-8")

    summary = clean_dataset(input_root=raw_root, output_root=clean_root)

    assert (raw_root / "train.jsonl").read_text(encoding="utf-8") == original_train
    assert (clean_root / "train.jsonl").exists()
    assert (clean_root / "dev.jsonl").exists()
    assert (clean_root / "test.jsonl").exists()
    assert (clean_root / "cleaning_report.json").exists()
    assert (clean_root / "cleaning_report.md").exists()
    assert (clean_root / "label_distribution.md").exists()
    assert (clean_root / "samples_by_label_raw.md").exists()
    assert (clean_root / "samples_by_label_clean.md").exists()
    assert (clean_root / "removed_examples.jsonl").exists()
    assert (clean_root / "downsampled_examples_stats.json").exists()
    assert summary["raw_example_count"] >= summary["cleaned_example_count"]


def test_cleaned_dataset_schema_and_split_boundaries(tmp_path: Path):
    data_root = _make_fixture_dataset(tmp_path / "data")
    raw_root = tmp_path / "raw"
    clean_root = tmp_path / "clean"
    build_dataset(
        data_root=data_root,
        output_root=raw_root,
        split_seed=11,
        use_model_negatives=False,
    )
    clean_dataset(input_root=raw_root, output_root=clean_root)

    rows = []
    for split in ("train", "dev", "test"):
        rows.extend(_load_jsonl(clean_root / f"{split}.jsonl"))
    assert rows
    required = {
        "doc_id", "split", "span_text", "label", "start_char", "end_char", "sentence",
        "left_context", "right_context", "cluster_id", "mention_count_in_cluster",
        "is_pronoun", "is_gold_person", "features",
    }
    assert required <= set(rows[0])

    doc_to_splits: dict[str, set[str]] = {}
    for row in rows:
        doc_to_splits.setdefault(row["doc_id"], set()).add(row["split"])
    assert all(len(splits) == 1 for splits in doc_to_splits.values())


def test_train_downsample_and_dev_test_preserved(tmp_path: Path):
    data_root = _make_fixture_dataset(tmp_path / "data")
    raw_root = tmp_path / "raw"
    clean_root = tmp_path / "clean"
    build_dataset(
        data_root=data_root,
        output_root=raw_root,
        split_seed=11,
        use_model_negatives=False,
    )

    raw_train = _load_jsonl(raw_root / "train.jsonl")
    raw_dev = _load_jsonl(raw_root / "dev.jsonl")
    raw_test = _load_jsonl(raw_root / "test.jsonl")

    report = clean_dataset(input_root=raw_root, output_root=clean_root)
    clean_train = _load_jsonl(clean_root / "train.jsonl")
    clean_dev = _load_jsonl(clean_root / "dev.jsonl")
    clean_test = _load_jsonl(clean_root / "test.jsonl")

    assert len(clean_train) <= len(raw_train)
    assert len(clean_dev) == len(raw_dev)
    assert len(clean_test) == len(raw_test)
    assert report["pronoun_downsampling"]["kept_pronoun_count"] <= report["pronoun_downsampling"]["raw_pronoun_count"]


def test_object_event_abstract_is_folded(tmp_path: Path):
    data_root = _make_fixture_dataset(tmp_path / "data")
    raw_root = tmp_path / "raw"
    clean_root = tmp_path / "clean"
    build_dataset(
        data_root=data_root,
        output_root=raw_root,
        split_seed=11,
        use_model_negatives=False,
    )
    # Inject a raw OBJECT_EVENT_ABSTRACT example to verify folding without changing the converter.
    extra = {
        "doc_id": "doc_train_a",
        "split": "train",
        "span_text": "Avatar",
        "label": "OBJECT_EVENT_ABSTRACT",
        "start_char": 0,
        "end_char": 6,
        "sentence": "Avatar glowed.",
        "left_context": "",
        "right_context": "",
        "cluster_id": "",
        "mention_count_in_cluster": 0,
        "is_pronoun": False,
        "is_gold_person": False,
        "annotation_label": "EVENT",
        "hard_negative_source": "test_injected",
        "features": {
            "is_capitalized": True,
            "is_multi_token": False,
            "has_honorific": False,
            "in_quote": False,
            "has_possessive": False,
            "locative_suffix": False,
        },
    }
    with (raw_root / "train.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(extra) + "\n")

    clean_dataset(input_root=raw_root, output_root=clean_root)
    clean_train = _load_jsonl(clean_root / "train.jsonl")
    assert any(row["label"] == "NON_PERSON_MISC" and row["span_text"] == "Avatar" for row in clean_train)


def test_extreme_malformed_long_spans_removed(tmp_path: Path):
    data_root = _make_fixture_dataset(tmp_path / "data")
    raw_root = tmp_path / "raw"
    clean_root = tmp_path / "clean"
    build_dataset(
        data_root=data_root,
        output_root=raw_root,
        split_seed=11,
        use_model_negatives=False,
    )
    extra = {
        "doc_id": "doc_train_a",
        "split": "train",
        "span_text": "this malformed span is absurdly long and should definitely be removed from the cleaned dataset because it is not a useful training unit",
        "label": "MALFORMED_OR_NOISE",
        "start_char": 0,
        "end_char": 120,
        "sentence": "this malformed span is absurdly long and should definitely be removed from the cleaned dataset because it is not a useful training unit",
        "left_context": "",
        "right_context": "",
        "cluster_id": "",
        "mention_count_in_cluster": 0,
        "is_pronoun": False,
        "is_gold_person": False,
        "annotation_label": "OBJ",
        "hard_negative_source": "test_injected",
        "features": {
            "is_capitalized": False,
            "is_multi_token": True,
            "has_honorific": False,
            "in_quote": False,
            "has_possessive": False,
            "locative_suffix": False,
        },
    }
    with (raw_root / "train.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(extra) + "\n")

    clean_dataset(input_root=raw_root, output_root=clean_root)
    removed = _load_jsonl(clean_root / "removed_examples.jsonl")
    assert any(row["removal_reason"] == "span_token_limit_exceeded" for row in removed)
