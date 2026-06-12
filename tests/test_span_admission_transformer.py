from __future__ import annotations

import json
from pathlib import Path

from transformers import AutoTokenizer

from redesign_lab.training.span_admission_transformer import (
    SpanAdmissionCollator,
    SpanAdmissionTorchDataset,
    create_label_map,
    load_dataset_splits,
    row_to_model_text,
    train_and_evaluate_transformer,
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
        "is_gold_person": label in {
            "CANDIDATE_PERSON_NAME",
            "HONORIFIC_PERSON_NAME",
            "DESCRIPTIVE_PERSON_REFERENCE",
            "RELATION_PERSON_REFERENCE",
            "GROUP_PERSON_REFERENCE",
            "PRONOUN_REFERENCE",
        },
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


def _make_dataset(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    train = [
        _example(doc_id="doc_train_1", split="train", span_text="Mr. Rochester", label="HONORIFIC_PERSON_NAME", sentence="Mr. Rochester arrived.", is_capitalized=True, is_multi_token=True, has_honorific=True),
        _example(doc_id="doc_train_1", split="train", span_text="Rochester", label="CANDIDATE_PERSON_NAME", sentence="Rochester arrived.", is_capitalized=True),
        _example(doc_id="doc_train_2", split="train", span_text="he", label="PRONOUN_REFERENCE", sentence="he replied.", is_pronoun=True),
        _example(doc_id="doc_train_2", split="train", span_text="the old man", label="DESCRIPTIVE_PERSON_REFERENCE", sentence="the old man replied.", is_multi_token=True),
        _example(doc_id="doc_train_3", split="train", span_text="his mother", label="RELATION_PERSON_REFERENCE", sentence="his mother waited.", is_multi_token=True),
        _example(doc_id="doc_train_3", split="train", span_text="the guests", label="GROUP_PERSON_REFERENCE", sentence="the guests waited.", is_multi_token=True),
        _example(doc_id="doc_train_4", split="train", span_text="York Road", label="LOCATION", sentence="York Road was wet.", is_capitalized=True, is_multi_token=True, locative_suffix=True),
        _example(doc_id="doc_train_4", split="train", span_text="the embassy", label="ORGANIZATION", sentence="the embassy closed.", is_multi_token=True),
        _example(doc_id="doc_train_5", split="train", span_text="Michaelmas", label="MALFORMED_OR_NOISE", sentence="Michaelmas term.", is_capitalized=True),
        _example(doc_id="doc_train_5", split="train", span_text="Avatar", label="NON_PERSON_MISC", sentence="Avatar glowed.", is_capitalized=True),
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


def _write_baseline_metrics(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "test": {
            "macro_f1": 0.1,
            "weighted_f1": 0.1,
            "grouped": {
                "person_reference_f1": 0.1,
                "non_person_f1": 0.1,
            },
            "per_label": {
                label: {"precision": 0.0, "recall": 0.0, "f1": 0.0}
                for label in [
                    "CANDIDATE_PERSON_NAME",
                    "HONORIFIC_PERSON_NAME",
                    "DESCRIPTIVE_PERSON_REFERENCE",
                    "RELATION_PERSON_REFERENCE",
                    "GROUP_PERSON_REFERENCE",
                    "PRONOUN_REFERENCE",
                    "LOCATION",
                    "ORGANIZATION",
                    "NON_PERSON_MISC",
                    "MALFORMED_OR_NOISE",
                ]
            },
        }
    }), encoding="utf-8")


def test_dataset_loading_and_label_map(tmp_path: Path):
    data_root = _make_dataset(tmp_path / "data")
    rows_by_split = load_dataset_splits(data_root)
    label_map = create_label_map(rows_by_split)
    assert set(rows_by_split) == {"train", "dev", "test"}
    assert "HONORIFIC_PERSON_NAME" in label_map
    assert "LOCATION" in label_map


def test_tokenization_and_collate(tmp_path: Path):
    data_root = _make_dataset(tmp_path / "data")
    rows_by_split = load_dataset_splits(data_root)
    label_map = create_label_map(rows_by_split)
    tokenizer = AutoTokenizer.from_pretrained("hf-internal-testing/tiny-random-distilbert")
    dataset = SpanAdmissionTorchDataset(rows_by_split["train"], tokenizer, label_map, max_length=64)
    collator = SpanAdmissionCollator(tokenizer)
    batch = collator([dataset[0], dataset[1]])
    assert "input_ids" in batch
    assert "attention_mask" in batch
    assert "labels" in batch
    assert batch["input_ids"].shape[0] == 2


def test_transformer_smoke_run_writes_outputs(tmp_path: Path):
    data_root = _make_dataset(tmp_path / "data")
    output_root = tmp_path / "reports"
    model_root = tmp_path / "model"
    baseline_path = tmp_path / "baseline" / "metrics.json"
    _write_baseline_metrics(baseline_path)
    metrics = train_and_evaluate_transformer(
        data_root=data_root,
        output_root=output_root,
        model_output_root=model_root,
        model_name="hf-internal-testing/tiny-random-distilbert",
        baseline_metrics_path=baseline_path,
        num_epochs=1,
        batch_size=2,
        learning_rate=5e-5,
        max_length=64,
        early_stopping_patience=1,
    )
    assert (output_root / "metrics.json").exists()
    assert (output_root / "classification_report.md").exists()
    assert (output_root / "confusion_matrix.csv").exists()
    assert (output_root / "per_label_errors.json").exists()
    assert (output_root / "top_false_positives.jsonl").exists()
    assert (output_root / "top_false_negatives.jsonl").exists()
    assert (output_root / "model_config.json").exists()
    assert (output_root / "label_map.json").exists()
    assert (output_root / "training_log.jsonl").exists()
    assert (model_root / "config.json").exists()
    assert metrics["model_name"] == "hf-internal-testing/tiny-random-distilbert"
    assert "delta_vs_baseline" in metrics

