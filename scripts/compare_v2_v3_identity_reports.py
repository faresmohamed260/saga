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


def _v2_metrics(report: Mapping[str, Any]) -> Mapping[str, Any]:
    aggregate = report.get("aggregate")
    if not isinstance(aggregate, Mapping):
        raise ValueError("v2 report missing aggregate")
    metrics = aggregate.get("metrics")
    if not isinstance(metrics, Mapping):
        raise ValueError("v2 report missing aggregate.metrics")
    return metrics


def _v3_metrics(report: Mapping[str, Any]) -> Mapping[str, Any]:
    aggregate = report.get("aggregate")
    if not isinstance(aggregate, Mapping):
        raise ValueError("v3 report missing aggregate")
    metrics = aggregate.get("metrics")
    if not isinstance(metrics, Mapping):
        raise ValueError("v3 report missing aggregate.metrics")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v2", required=True, type=Path)
    parser.add_argument("--v3", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    v2 = _load(args.v2)
    v3 = _load(args.v3)
    v2_metrics = _v2_metrics(v2)
    v3_metrics = _v3_metrics(v3)
    rows = {}
    for v2_key, v3_key in _V2_TO_V3.items():
        old = float(v2_metrics.get(v2_key, 0.0))
        new = float(v3_metrics.get(v3_key, 0.0))
        rows[v3_key] = {"v2": old, "v3": new, "delta": new - old}

    output = {
        "schemaVersion": "saga-v2-v3-identity-comparison-v1",
        "v2SchemaVersion": v2.get("schemaVersion"),
        "v3SchemaVersion": v3.get("schemaVersion"),
        "metrics": rows,
        "v3Resources": v3.get("resources"),
        "v3Model": v3.get("model"),
    }
    rendered = json.dumps(output, indent=2, sort_keys=True) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
