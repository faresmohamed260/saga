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
        self.batch_size = None

    def predict(self, rows, *, batch_size):
        self.rows = rows
        self.batch_size = batch_size
        return [0.75 for _ in rows]


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
        batch_size=8,
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
    assert fake.batch_size == 8
    query, passage = fake.rows[0]
    assert "Mention: She" in query
    assert "Candidate character: Alice" in passage
    assert "Known contexts:" in passage
    assert "Alice entered" in passage
    assert "Alice smiled" in passage


def test_ettin_scores_candidate_set_in_one_model_call():
    text = "Alice met Bob. She waved."
    source = source_for(text)
    alice_mention = Mention.create(
        source_fingerprint=source.source_fingerprint,
        source_unit_key="doc:0",
        span=SourceSpan(0, 5),
        entity_type=EntityType.CHARACTER,
        text="Alice",
    )
    bob_mention = Mention.create(
        source_fingerprint=source.source_fingerprint,
        source_unit_key="doc:0",
        span=SourceSpan(10, 13),
        entity_type=EntityType.CHARACTER,
        text="Bob",
    )
    target = Mention.create(
        source_fingerprint=source.source_fingerprint,
        source_unit_key="doc:0",
        span=SourceSpan(15, 18),
        entity_type=EntityType.CHARACTER,
        text="She",
    )
    alice = Entity(
        entity_id="ent-alice",
        entity_type=EntityType.CHARACTER,
        canonical_name="Alice",
        mention_ids=(alice_mention.mention_id,),
        aliases=("Alice",),
    )
    bob = Entity(
        entity_id="ent-bob",
        entity_type=EntityType.CHARACTER,
        canonical_name="Bob",
        mention_ids=(bob_mention.mention_id,),
        aliases=("Bob",),
    )
    candidates = (
        IdentityCandidate(target.mention_id, alice.entity_id, {"recent_rank": 2.0}),
        IdentityCandidate(target.mention_id, bob.entity_id, {"recent_rank": 1.0}),
    )
    fake = FakeCrossEncoder()
    scorer = EttinRerankerIdentityScorer(revision="fixture", batch_size=4, model=fake)
    scores = scorer.score_many(
        mention=target,
        candidates=candidates,
        existing_entities=(alice, bob),
        context=IdentityScoringContext(source=source, mentions=(alice_mention, bob_mention)),
    )
    assert len(scores) == 2
    assert len(fake.rows) == 2
    assert fake.batch_size == 4
