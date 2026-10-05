from packages.narrative_compiler.benchmark import (
    GoldIdentityDocument,
    GoldIdentityMention,
    evaluate_identity_benchmark,
)
from packages.narrative_compiler.ir import AcceptanceState, Entity, EntityType, Mention, SourceSpan


SOURCE = "Rhys saw Feyre and he smiled."
FINGERPRINT = "source"
UNIT = "doc"


def predicted(text, start, *, acceptance=AcceptanceState.CANDIDATE):
    return Mention.create(
        source_fingerprint=FINGERPRINT,
        source_unit_key=UNIT,
        span=SourceSpan(start, start + len(text)),
        entity_type=EntityType.CHARACTER,
        text=text,
        acceptance=acceptance,
    )


def gold_document():
    return GoldIdentityDocument(
        document_id="fixture",
        text=SOURCE,
        mentions=(
            GoldIdentityMention("g1", "Rhys", 0, 4, "proper_name", "person", "rhys"),
            GoldIdentityMention("g2", "Feyre", 9, 14, "proper_name", "person", "feyre"),
            GoldIdentityMention("g3", "he", 19, 21, "pronoun", "person", "rhys"),
        ),
    )


def test_v3_identity_metrics_match_v2_style_semantics_for_pure_clusters():
    rhys = predicted("Rhys", 0)
    feyre = predicted("Feyre", 9)
    he = predicted("he", 19, acceptance=AcceptanceState.UNRESOLVED)
    entities = [
        Entity("e-rhys", EntityType.CHARACTER, "Rhys", (rhys.mention_id,), acceptance=AcceptanceState.CANDIDATE),
        Entity("e-feyre", EntityType.CHARACTER, "Feyre", (feyre.mention_id,), acceptance=AcceptanceState.CANDIDATE),
        Entity.unresolved_singleton(he),
    ]
    report = evaluate_identity_benchmark(
        gold=gold_document(),
        mentions=[rhys, feyre, he],
        entities=entities,
        unresolved_mention_ids=[he.mention_id],
    )
    assert report.metrics.canonical_precision == 1.0
    assert report.metrics.canonical_recall == 1.0
    assert report.metrics.incorrect_merge_rate == 0.0
    assert report.metrics.fragmentation_rate == 0.0
    assert report.metrics.linked_mention_precision == 1.0
    assert report.metrics.linked_mention_recall == 2 / 3
    assert report.metrics.unresolved_relevant_mention_rate == 1 / 3
    assert report.metrics.cluster_purity == 1.0


def test_incorrect_merge_is_visible_in_canonical_metrics():
    rhys = predicted("Rhys", 0)
    feyre = predicted("Feyre", 9)
    merged = Entity(
        "e-merged",
        EntityType.CHARACTER,
        "Rhys",
        (rhys.mention_id, feyre.mention_id),
        acceptance=AcceptanceState.CANDIDATE,
    )
    report = evaluate_identity_benchmark(
        gold=gold_document(),
        mentions=[rhys, feyre],
        entities=[merged],
    )
    assert report.metrics.canonical_precision == 0.0
    assert report.metrics.incorrect_merge_rate == 1.0
    assert report.metrics.linked_mention_precision == 0.0
