from packages.narrative_compiler.adapters.ettin import EttinRerankerIdentityScorer
from packages.narrative_compiler.ir import Entity, EntityType, Mention, SourceSpan
from packages.narrative_compiler.source import NormalizedSource
from packages.narrative_compiler.stages import IdentityCandidate, IdentityScoringContext


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


class FakeCrossEncoder:
    def __init__(self):
        self.rows = None

    def predict(self, rows):
        self.rows = rows
        return [0.75]


def test_ettin_passage_includes_representative_prior_contexts():
    text = "Alice entered the hall. Bob waited. Later Alice smiled. She waved."
    source = source_for(text)
    first = Mention.create(
        source_fingerprint=source.source_fingerprint,
        source_unit_key="doc:0",
        span=SourceSpan(0, 5),
        entity_type=EntityType.CHARACTER,
        text="Alice",
    )
    second = Mention.create(
        source_fingerprint=source.source_fingerprint,
        source_unit_key="doc:0",
        span=SourceSpan(42, 47),
        entity_type=EntityType.CHARACTER,
        text="Alice",
    )
    target = Mention.create(
        source_fingerprint=source.source_fingerprint,
        source_unit_key="doc:0",
        span=SourceSpan(55, 58),
        entity_type=EntityType.CHARACTER,
        text="She",
    )
    entity = Entity(
        entity_id="ent-alice",
        entity_type=EntityType.CHARACTER,
        canonical_name="Alice",
        mention_ids=(first.mention_id, second.mention_id),
        aliases=("Alice",),
    )
    fake = FakeCrossEncoder()
    scorer = EttinRerankerIdentityScorer(
        revision="fixture",
        context_chars=32,
        entity_contexts=2,
        model=fake,
    )
    result = scorer.score(
        mention=target,
        candidate=IdentityCandidate(
            mention_id=target.mention_id,
            candidate_entity_id=entity.entity_id,
            features={"recent_rank": 1.0},
        ),
        existing_entities=(entity,),
        context=IdentityScoringContext(source=source, mentions=(first, second)),
    )
    assert result.score == 0.75
    query, passage = fake.rows[0]
    assert "Mention: She" in query
    assert "Candidate character: Alice" in passage
    assert "Known contexts:" in passage
    assert "Alice entered" in passage
    assert "Alice smiled" in passage
