from __future__ import annotations

import json
from pathlib import Path

import joblib

from redesign_lab.training.span_admission_baseline import (
    NON_PERSON_LABELS,
    PERSON_REFERENCE_LABELS,
    BaselineArtifacts,
    load_dataset_splits,
    rows_to_frame,
    train_and_evaluate_baseline,
)


def _example(
    *,
    doc_id: str,
    split: str,
    span_text: str,
    label: str,
    sentence: str,
    left_context: str = "",
    right_context: str = "",
    is_pronoun: bool = False,
    is_capitalized: bool = False,
    is_multi_token: bool = False,
    has_honorific: bool = False,
    in_quote: bool = False,
    has_possessive: bool = False,
    locative_suffix: bool = False,
) -> dict:
    return {
        "doc_id": doc_id,
        "split": split,
        "span_text": span_text,
        "label": label,
        "start_char": 0,
        "end_char": len(span_text),
        "sentence": sentence,
        "left_context": left_context,
        "right_context": right_context,
        "cluster_id": "",
        "mention_count_in_cluster": 1,
        "is_pronoun": is_pronoun,
        "is_gold_person": label in PERSON_REFERENCE_LABELS,
        "annotation_label": "",
        "hard_negative_source": "",
        "features": {
            "is_capitalized": is_capitalized,
            "is_multi_token": is_multi_token,
            "has_honorific": has_honorific,
            "in_quote": in_quote,
            "has_possessive": has_possessive,
            "locative_suffix": locative_suffix,
        },
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _make_clean_dataset(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    train = [
        _example(doc_id="doc_train_1", split="train", span_text="Mr. Rochester", label="HONORIFIC_PERSON_NAME", sentence="Mr. Rochester arrived.", is_capitalized=True, is_multi_token=True, has_honorific=True),
        _example(doc_id="doc_train_1", split="train", span_text="Rochester", label="CANDIDATE_PERSON_NAME", sentence="Rochester arrived.", is_capitalized=True),
        _example(doc_id="doc_train_2", split="train", span_text="he", label="PRONOUN_REFERENCE", sentence="he replied.", is_pronoun=True),
        _example(doc_id="doc_train_2", split="train", span_text="the old man", label="DESCRIPTIVE_PERSON_REFERENCE", sentence="the old man replied.", is_multi_token=True),
        _example(doc_id="doc_train_3", split="train", span_text="York Road", label="LOCATION", sentence="York Road was wet.", is_capitalized=True, is_multi_token=True, locative_suffix=True),
        _example(doc_id="doc_train_3", split="train", span_text="the embassy", label="ORGANIZATION", sentence="the embassy closed.", is_multi_token=True),
        _example(doc_id="doc_train_4", split="train", span_text="Michaelmas", label="MALFORMED_OR_NOISE", sentence="Michaelmas term.", is_capitalized=True),
        _example(doc_id="doc_train_4", split="train", span_text="Avatar", label="NON_PERSON_MISC", sentence="Avatar glowed.", is_capitalized=True),
    ]
    dev = [
        _example(doc_id="doc_dev_1", split="dev", span_text="Captain Nemo", label="HONORIFIC_PERSON_NAME", sentence="Captain Nemo waved.", is_capitalized=True, is_multi_token=True, has_honorific=True),
        _example(doc_id="doc_dev_1", split="dev", span_text="she", label="PRONOUN_REFERENCE", sentence="she waited.", is_pronoun=True),
        _example(doc_id="doc_dev_2", split="dev", span_text="Temple Bar", label="LOCATION", sentence="Temple Bar stood silent.", is_capitalized=True, is_multi_token=True),
        _example(doc_id="doc_dev_2", split="dev", span_text="the office", label="ORGANIZATION", sentence="the office closed.", is_multi_token=True),
    ]
    test = [
        _example(doc_id="doc_test_1", split="test", span_text="Miss Smith", label="HONORIFIC_PERSON_NAME", sentence="Miss Smith entered.", is_capitalized=True, is_multi_token=True, has_honorific=True),
        _example(doc_id="doc_test_1", split="test", span_text="their", label="PRONOUN_REFERENCE", sentence="their carriage stopped.", is_pronoun=True),
        _example(doc_id="doc_test_2", split="test", span_text="Holborn Hill", label="LOCATION", sentence="Holborn Hill was muddy.", is_capitalized=True, is_multi_token=True),
        _example(doc_id="doc_test_2", split="test", span_text="the corporation", label="ORGANIZATION", sentence="the corporation failed.", is_multi_token=True),
    ]
    _write_jsonl(root / "train.jsonl", train)
    _write_jsonl(root / "dev.jsonl", dev)
    _write_jsonl(root / "test.jsonl", test)
    return root


def test_load_jsonl_and_label_groups(tmp_path: Path):
    data_root = _make_clean_dataset(tmp_path / "data")
    splits = load_dataset_splits(data_root)
    assert set(splits) == {"train", "dev", "test"}
    assert "PRONOUN_REFERENCE" in PERSON_REFERENCE_LABELS
    assert "LOCATION" in NON_PERSON_LABELS


def test_baseline_trains_writes_reports_and_model_reloads(tmp_path: Path):
    data_root = _make_clean_dataset(tmp_path / "data")
    output_root = tmp_path / "reports"
    model_root = tmp_path / "models"
    metrics = train_and_evaluate_baseline(
        data_root=data_root,
        output_root=output_root,
        model_root=model_root,
    )
    assert (output_root / "metrics.json").exists()
    assert (output_root / "classification_report.md").exists()
    assert (output_root / "confusion_matrix.csv").exists()
    assert (output_root / "per_label_errors.json").exists()
    assert (output_root / "top_false_positives.jsonl").exists()
    assert (output_root / "top_false_negatives.jsonl").exists()
    assert (output_root / "model_config.json").exists()
    assert (model_root / "span_admission_baseline_v1.joblib").exists()
    assert "test" in metrics and "macro_f1" in metrics["test"]

    artifact = joblib.load(model_root / "span_admission_baseline_v1.joblib")
    assert isinstance(artifact, BaselineArtifacts)
    test_rows = load_dataset_splits(data_root)["test"]
    frame = rows_to_frame(test_rows)
    preds = artifact.pipeline.predict(frame)
    assert len(preds) == len(test_rows)

