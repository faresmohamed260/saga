from packages.narrative_compiler.benchmark import GoldIdentityDocument, GoldIdentityMention
from packages.narrative_compiler.ir import EntityType, Mention, SourceSpan
from packages.narrative_compiler.lexer_benchmark import (
    aggregate_character_mention_reports,
    evaluate_character_mentions,
)
from packages.narrative_compiler.source import NormalizedSource


def source_for(text: str) -> NormalizedSource:
    return NormalizedSource.from_v2_payload(
        {
            "normalizationVersion": "test-v1",
            "configFingerprint": "cfg",
            "normalizedSha256": "a" * 64,
            "outputFingerprint": "b" * 64,
            "normalizedText": text,
            "sections": [
                {
                    "stable_key": "doc:0",
                    "ordinal": 0,
                    "section_kind": "document",
                    "title": None,
                    "source_locator": "doc",
                    "start_offset": 0,
                    "end_offset": len(text),
                    "normalized_text": text,
                }
            ],
        }
    )


def gold_for(text: str) -> GoldIdentityDocument:
    return GoldIdentityDocument(
        document_id="fixture",
        text=text,
        mentions=(
            GoldIdentityMention(
                mention_id="g0",
                surface_text="Alice",
                start_offset=0,
                end_offset=5,
                mention_kind="proper_name",
                entity_type="person",
                gold_character_id="alice",
            ),
            GoldIdentityMention(
                mention_id="g1",
                surface_text="the doctor",
                start_offset=10,
                end_offset=20,
                mention_kind="nominal",
                entity_type="person",
                gold_character_id="alice",
            ),
            GoldIdentityMention(
                mention_id="g2",
                surface_text="she",
                start_offset=22,
                end_offset=25,
                mention_kind="pronoun",
                entity_type="person",
                gold_character_id="alice",
            ),
        ),
    )


def mention(source: NormalizedSource, start: int, end: int, entity_type: EntityType) -> Mention:
    return Mention.create(
        source_fingerprint=source.source_fingerprint,
        source_unit_key="doc:0",
        span=SourceSpan(start, end),
        entity_type=entity_type,
        text=source.normalized_text[start:end],
    )


def test_character_mention_metrics_score_exact_spans_by_kind():
    text = "Alice met the doctor; she waved."
    source = source_for(text)
    report = evaluate_character_mentions(
        gold=gold_for(text),
        mentions=(
            mention(source, 0, 5, EntityType.CHARACTER),
            mention(source, 10, 20, EntityType.CHARACTER),
            mention(source, 27, 32, EntityType.CHARACTER),
        ),
    )

    assert report.counts.gold_person_mentions == 3
    assert report.counts.predicted_character_mentions == 3
    assert report.counts.true_positive_mentions == 2
    assert report.metrics.precision == 2 / 3
    assert report.metrics.recall == 2 / 3
    assert report.metrics.proper_name_recall == 1.0
    assert report.metrics.nominal_recall == 1.0
    assert report.metrics.pronoun_recall == 0.0


def test_duplicate_character_spans_are_collapsed_and_noncharacters_ignored():
    text = "Alice met the doctor; she waved."
    source = source_for(text)
    alice = mention(source, 0, 5, EntityType.CHARACTER)
    report = evaluate_character_mentions(
        gold=gold_for(text),
        mentions=(
            alice,
            alice,
            mention(source, 10, 20, EntityType.LOCATION),
        ),
    )

    assert report.counts.predicted_character_mentions == 1
    assert report.counts.true_positive_mentions == 1
    assert report.metrics.precision == 1.0
    assert report.metrics.recall == 1 / 3


def test_character_mention_reports_aggregate_from_counts():
    text = "Alice met the doctor; she waved."
    source = source_for(text)
    first = evaluate_character_mentions(
        gold=gold_for(text),
        mentions=(mention(source, 0, 5, EntityType.CHARACTER),),
    )
    second = evaluate_character_mentions(
        gold=gold_for(text),
        mentions=(
            mention(source, 10, 20, EntityType.CHARACTER),
            mention(source, 22, 25, EntityType.CHARACTER),
        ),
    )

    aggregate = aggregate_character_mention_reports((first, second))
    assert aggregate.counts.document_count == 2
    assert aggregate.counts.gold_person_mentions == 6
    assert aggregate.counts.true_positive_mentions == 3
    assert aggregate.metrics.precision == 1.0
    assert aggregate.metrics.recall == 0.5
    assert aggregate.metrics.proper_name_recall == 0.5
    assert aggregate.metrics.nominal_recall == 0.5
    assert aggregate.metrics.pronoun_recall == 0.5
