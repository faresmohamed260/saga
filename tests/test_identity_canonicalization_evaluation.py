from __future__ import annotations

import json
from pathlib import Path

from packages.identity_runtime import evaluate_identity_canonicalization, review_identity_clusters


FIXTURE = Path(__file__).parent / "fixtures" / "identity_canonicalization" / "once_upon_a_broken_heart.json"


def _dataset() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_real_book_identity_variants_merge_with_audit_provenance():
    dataset = _dataset()
    result = review_identity_clusters(
        raw_clusters=dataset["clusters"],
        chapters=dataset["chapters"],
        scenes=dataset["scenes"],
    )

    evangeline = next(item for item in result.reviewed_clusters if 1 in item.source_cluster_ids)
    assert evangeline.cluster.display_name == "Evangeline Fox"
    assert set(evangeline.source_cluster_ids) == {1, 2, 5, 7, 13, 28, 32}
    assert {"Evangeline", "Little Fox", "Miss Fox", "Princess Evangeline Fox"} <= set(evangeline.accepted_aliases)
    assert result.merge_count == 6
    assert any(item.canonical_display_name == "Evangeline Fox" for item in result.merge_evidence)


def test_real_book_contamination_traps_remain_separate():
    dataset = _dataset()
    result = review_identity_clusters(
        raw_clusters=dataset["clusters"],
        chapters=dataset["chapters"],
        scenes=dataset["scenes"],
    )
    groups = [set(item.source_cluster_ids) for item in result.reviewed_clusters if item.keep_cluster]

    for distinct_cluster_id in (4, 10, 12, 29, 65, 176):
        assert not any(1 in group and distinct_cluster_id in group for group in groups)


def test_real_book_pairwise_identity_quality_gate():
    metrics = evaluate_identity_canonicalization(_dataset())

    assert metrics.labeled_pair_count == 18
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1 == 1.0
    assert metrics.over_merge_rate == 0.0
    assert metrics.fragmentation_rate == 0.0
    assert metrics.contamination_rate == 0.0
