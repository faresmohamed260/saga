from __future__ import annotations

import json
from pathlib import Path

from redesign_lab.training.prepare_span_admission_v2 import (
    audit_transformer_errors,
    compare_transformer_runs,
    prepare_clean_v2_dataset,
)
from redesign_lab.training.span_admission_transformer import train_and_evaluate_transformer


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _example(
    *,
    doc_id: str,
    split: str,
    span_text: str,
    label: str,
    sentence: str,
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
        "left_context": "",
        "right_context": "",
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


def _make_clean_v1(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    train = [
        _example(doc_id="doc_train_1", split="train", span_text="himself", label="MALFORMED_OR_NOISE", sentence="he blamed himself .", is_pronoun=True),
        _example(doc_id="doc_train_1", split="train", span_text="York Road", label="LOCATION", sentence="York Road was wet.", is_capitalized=True, is_multi_token=True, locative_suffix=True),
        _example(doc_id="doc_train_2", split="train", span_text="Lincoln", label="ORGANIZATION", sentence="Lincoln stood nearby.", is_capitalized=True),
        _example(doc_id="doc_train_2", split="train", span_text="Rochester", label="CANDIDATE_PERSON_NAME", sentence="Rochester arrived.", is_capitalized=True),
        _example(doc_id="doc_train_3", split="train", span_text="the parlour", label="LOCATION", sentence="he entered the parlour .", is_multi_token=True),
    ]
    dev = [
        _example(doc_id="doc_dev_1", split="dev", span_text="herself", label="MALFORMED_OR_NOISE", sentence="she saw herself .", is_pronoun=True),
    ]
    test = [
        _example(doc_id="doc_test_1", split="test", span_text="themselves", label="MALFORMED_OR_NOISE", sentence="they praised themselves .", is_pronoun=True),
    ]
    _write_jsonl(root / "train.jsonl", train)
    _write_jsonl(root / "dev.jsonl", dev)
    _write_jsonl(root / "test.jsonl", test)
    return root


def _make_transformer_v1_report(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    metrics = {
        "labels": [
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
        ],
        "test": {
            "macro_f1": 0.5,
            "weighted_f1": 0.7,
            "grouped": {
                "person_reference_f1": 0.8,
                "non_person_f1": 0.4,
            },
            "per_label": {
                label: {"precision": 0.5, "recall": 0.5, "f1": 0.5}
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
            "confusion_matrix": [
                [1,0,0,0,0,0,0,1,0,0],
                [0,1,0,0,0,0,0,0,0,0],
                [0,0,1,0,0,0,0,1,0,0],
                [0,0,0,1,0,0,0,0,0,0],
                [0,0,0,0,1,0,0,0,0,0],
                [0,0,0,0,0,1,0,0,0,2],
                [0,0,1,0,0,0,1,1,0,0],
                [1,0,0,0,0,0,0,1,0,0],
                [0,0,0,0,0,0,0,0,0,0],
                [0,0,0,0,0,0,0,0,0,1],
            ],
        },
    }
    (root / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    false_rows = [
        {"doc_id": "d1", "span_text": "himself", "sentence": "he blamed himself .", "true_label": "PRONOUN_REFERENCE", "predicted_label": "MALFORMED_OR_NOISE", "confidence": 0.9},
        {"doc_id": "d1", "span_text": "York Road", "sentence": "York Road was wet.", "true_label": "LOCATION", "predicted_label": "DESCRIPTIVE_PERSON_REFERENCE", "confidence": 0.8},
        {"doc_id": "d1", "span_text": "Lincoln", "sentence": "Lincoln stood nearby.", "true_label": "ORGANIZATION", "predicted_label": "CANDIDATE_PERSON_NAME", "confidence": 0.8},
    ]
    _write_jsonl(root / "top_false_negatives.jsonl", false_rows)
    _write_jsonl(root / "top_false_positives.jsonl", false_rows)
    return root


def test_reflexive_pronouns_are_relabeled_and_schema_preserved(tmp_path: Path):
    clean_v1 = _make_clean_v1(tmp_path / "clean_v1")
    audit_root = _make_transformer_v1_report(tmp_path / "report_v1")
    output_root = tmp_path / "clean_v2"
    report = prepare_clean_v2_dataset(input_root=clean_v1, output_root=output_root, audit_root=audit_root)
    train_rows = [json.loads(line) for line in (output_root / "train.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    dev_rows = [json.loads(line) for line in (output_root / "dev.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    test_rows = [json.loads(line) for line in (output_root / "test.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(row["span_text"] == "himself" and row["label"] == "PRONOUN_REFERENCE" for row in train_rows)
    assert any(row["span_text"] == "herself" and row["label"] == "PRONOUN_REFERENCE" for row in dev_rows)
    assert any(row["span_text"] == "themselves" and row["label"] == "PRONOUN_REFERENCE" for row in test_rows)
    assert (output_root / "label_variant_full.json").exists()
    assert (output_root / "label_variant_grouped_non_person.json").exists()
    assert report["augmentation_stats"]["hard_negative_ambiguity_added"] >= 1


def test_audit_and_compare_outputs_are_written(tmp_path: Path):
    report_v1 = _make_transformer_v1_report(tmp_path / "report_v1")
    audit_out = tmp_path / "audit"
    audit_report = audit_transformer_errors(report_root=report_v1, output_root=audit_out)
    assert (audit_out / "error_audit.json").exists()
    assert (audit_out / "error_audit.md").exists()
    assert "PRONOUN_REFERENCE__TO__MALFORMED_OR_NOISE" in audit_report["pair_examples"]

    metrics_v2 = json.loads((report_v1 / "metrics.json").read_text(encoding="utf-8"))
    metrics_v2["test"]["macro_f1"] = 0.6
    metrics_v2["test"]["weighted_f1"] = 0.75
    metrics_v2["test"]["grouped"]["person_reference_f1"] = 0.82
    metrics_v2["test"]["grouped"]["non_person_f1"] = 0.5
    (tmp_path / "report_v2").mkdir(parents=True, exist_ok=True)
    (tmp_path / "report_v2" / "metrics.json").write_text(json.dumps(metrics_v2), encoding="utf-8")
    comparison = compare_transformer_runs(
        v1_metrics_path=report_v1 / "metrics.json",
        v2_metrics_path=tmp_path / "report_v2" / "metrics.json",
        output_root=tmp_path / "comparison",
    )
    assert (tmp_path / "comparison" / "comparison_report.json").exists()
    assert comparison["macro_f1_delta"] == 0.09999999999999998


def test_v2_dataset_smoke_trains_transformer(tmp_path: Path):
    clean_v1 = _make_clean_v1(tmp_path / "clean_v1")
    audit_root = _make_transformer_v1_report(tmp_path / "report_v1")
    clean_v2 = tmp_path / "clean_v2"
    prepare_clean_v2_dataset(input_root=clean_v1, output_root=clean_v2, audit_root=audit_root)
    metrics = train_and_evaluate_transformer(
        data_root=clean_v2,
        output_root=tmp_path / "transformer_report",
        model_output_root=tmp_path / "transformer_model",
        model_name="hf-internal-testing/tiny-random-distilbert",
        baseline_metrics_path=audit_root / "metrics.json",
        num_epochs=1,
        batch_size=2,
        learning_rate=5e-5,
        max_length=64,
        early_stopping_patience=1,
    )
    assert (tmp_path / "transformer_report" / "metrics.json").exists()
    assert metrics["model_name"] == "hf-internal-testing/tiny-random-distilbert"
