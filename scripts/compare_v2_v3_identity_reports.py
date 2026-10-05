"""Compare frozen V2 and V3 identity benchmark reports without changing metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


_V2_TO_V3 = {
    "canonicalPrecision": "canonical_precision",
    "canonicalRecall": "canonical_recall",
    "falseCanonicalRate": "false_canonical_rate",
    "incorrectMergeRate": "incorrect_merge_rate",
    "contaminatedCanonicalRate": "contaminated_canonical_rate",
    "fragmentationRate": "fragmentation_rate",
    "linkedMentionPrecision": "linked_mention_precision",
    "linkedMentionRecall": "linked_mention_recall",
    "unresolvedRelevantMentionRate": "unresolved_relevant_mention_rate",
    "quarantinedRelevantMentionRate": "quarantined_relevant_mention_rate",
    "nonPersonQuarantineRate": "non_person_quarantine_rate",
    "clusterPurity": "cluster_purity",
}


def _load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"report must be a JSON object: {path}")
    return value


def _metrics(report: Mapping[str, Any], *, label: str) -> Mapping[str, Any]:
    aggregate = report.get("aggregate")
    if not isinstance(aggregate, Mapping):
        raise ValueError(f"{label} report missing aggregate")
    metrics = aggregate.get("metrics")
    if not isinstance(metrics, Mapping):
        raise ValueError(f"{label} report missing aggregate.metrics")
    return metrics


def _document_count(dataset: Mapping[str, Any], *, label: str) -> int:
    if dataset.get("documentCount") is not None:
        return int(dataset["documentCount"])
    if dataset.get("completedDocumentCount") is not None:
        failed = int(dataset.get("failedDocumentCount", 0))
        if failed != 0:
            raise ValueError(f"{label} report contains {failed} failed documents; comparison would change the denominator")
        return int(dataset["completedDocumentCount"])
    raise ValueError(f"{label} dataset does not expose a comparable document count")


def _assert_comparable(v2: Mapping[str, Any], v3: Mapping[str, Any]) -> None:
    v2_dataset = v2.get("dataset")
    v3_dataset = v3.get("dataset")
    if not isinstance(v2_dataset, Mapping) or not isinstance(v3_dataset, Mapping):
        raise ValueError("both reports must identify their dataset")
    for field in ("repository", "commit", "annotationLayer"):
        if v2_dataset.get(field) != v3_dataset.get(field):
            raise ValueError(
                f"reports are not directly comparable: dataset {field} differs "
                f"({v2_dataset.get(field)!r} != {v3_dataset.get(field)!r})"
            )
    old_count = _document_count(v2_dataset, label="v2")
    new_count = _document_count(v3_dataset, label="v3")
    if old_count != new_count:
        raise ValueError(f"reports are not directly comparable: document count differs ({old_count} != {new_count})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v2", required=True, type=Path)
    parser.add_argument("--v3", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    v2 = _load(args.v2)
    v3 = _load(args.v3)
    _assert_comparable(v2, v3)
    v2_metrics = _metrics(v2, label="v2")
    v3_metrics = _metrics(v3, label="v3")
    rows = {}
    for v2_key, v3_key in _V2_TO_V3.items():
        if v2_key not in v2_metrics or v3_key not in v3_metrics:
            raise ValueError(f"missing comparison metric: {v2_key} / {v3_key}")
        old = float(v2_metrics[v2_key])
        new = float(v3_metrics[v3_key])
        rows[v3_key] = {"v2": old, "v3": new, "delta": new - old}

    output = {
        "schemaVersion": "saga-v2-v3-identity-comparison-v1",
        "dataset": v3.get("dataset"),
        "v2SchemaVersion": v2.get("schemaVersion"),
        "v3SchemaVersion": v3.get("schemaVersion"),
        "metrics": rows,
        "v3Resources": v3.get("resources"),
        "v3Model": v3.get("model"),
        "v3Environment": v3.get("environment"),
    }
    rendered = json.dumps(output, indent=2, sort_keys=True) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
