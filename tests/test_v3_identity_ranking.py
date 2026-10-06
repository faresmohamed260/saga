import hashlib

from packages.narrative_compiler.benchmark import GoldIdentityDocument, GoldIdentityMention
from packages.narrative_compiler.candidates import (
    HybridIdentityCandidateGenerator,
    LexicalIdentityCandidateGenerator,
)
from packages.narrative_compiler.ir import Entity, EntityType, Mention, SourceSpan
from packages.narrative_compiler.ranking import evaluate_oracle_history_ranking
from packages.narrative_compiler.source import NormalizedSource
from packages.narrative_compiler.stages import IdentityCandidate, IdentityScore, IdentityScoringContext


def source_for(text: str) -> NormalizedSource:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return NormalizedSource.from_v2_payload(
        {
            "normalizationVersion": "test-v1",
            "configFingerprint": "cfg",
            "normalizedSha256": digest,
            "outputFingerprint": digest,
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


def gold_for(text: str, rows):
    return GoldIdentityDocument(
        document_id="fixture",
        text=text,
        mentions=tuple(
            GoldIdentityMention(
                mention_id=f"g{index}",
                surface_text=surface,
                start_offset=start,
                end_offset=end,
                mention_kind=kind,
                entity_type="person",
                gold_character_id=gold_id,
            )
            for index, (surface, start, end, kind, gold_id) in enumerate(rows)
        ),
    )


def test_lexical_ranking_excludes_zero_overlap_pronouns():
    text = "Alice met Bob. She waved to Alice."
    gold = gold_for(
        text,
        [
            ("Alice", 0, 5, "proper_name", "alice"),
            ("Bob", 10, 13, "proper_name", "bob"),
            ("She", 15, 18, "pronoun", "alice"),
            ("Alice", 28, 33, "proper_name", "alice"),
        ],
    )
    report = evaluate_oracle_history_ranking(
        source=source_for(text),
        gold=gold,
        candidate_generator=LexicalIdentityCandidateGenerator(top_k=8),
    )
    assert report.overall.counts.eligible_mentions == 2
    assert report.overall.counts.true_candidate_retrieved == 1
    assert report.by_mention_kind["pronoun"].metrics.candidate_retrieval_rate == 0.0
    assert report.by_mention_kind["proper_name"].metrics.candidate_recall_at_1 == 1.0


def test_hybrid_ranking_adds_recent_candidate_for_pronoun():
    text = "Alice met Bob. She waved."
    gold = gold_for(
        text,
        [
            ("Alice", 0, 5, "proper_name", "alice"),
            ("Bob", 10, 13, "proper_name", "bob"),
            ("She", 15, 18, "pronoun", "alice"),
        ],
    )
    report = evaluate_oracle_history_ranking(
        source=source_for(text),
        gold=gold,
        candidate_generator=HybridIdentityCandidateGenerator(top_k=4, lexical_k=2, recent_k=2),
    )
    assert report.overall.counts.eligible_mentions == 1
    assert report.overall.counts.true_candidate_retrieved == 1
    assert report.overall.metrics.candidate_retrieval_rate == 1.0


class PreferAliceScorer:
    descriptor = None

    def score(self, *, mention, candidate, existing_entities, context):
        del mention, context
        entity = next(item for item in existing_entities if item.entity_id == candidate.candidate_entity_id)
        return IdentityScore(
            mention_id=candidate.mention_id,
            candidate_entity_id=candidate.candidate_entity_id,
            score=1.0 if entity.canonical_name == "Alice" else 0.0,
        )


def test_scorer_metrics_are_separate_from_candidate_retrieval():
    text = "Alice met Bob. She waved."
    gold = gold_for(
        text,
        [
            ("Alice", 0, 5, "proper_name", "alice"),
            ("Bob", 10, 13, "proper_name", "bob"),
            ("She", 15, 18, "pronoun", "alice"),
        ],
    )
    report = evaluate_oracle_history_ranking(
        source=source_for(text),
        gold=gold,
        candidate_generator=HybridIdentityCandidateGenerator(top_k=4, lexical_k=2, recent_k=2),
        scorer=PreferAliceScorer(),
    )
    assert report.overall.metrics.candidate_retrieval_rate == 1.0
    assert report.overall.metrics.scorer_top1_end_to_end == 1.0
    assert report.overall.metrics.scorer_mrr_conditional == 1.0


def test_identity_scoring_context_rejects_cross_source_mentions():
    left = source_for("Alice")
    right = source_for("Bob")
    mention = Mention.create(
        source_fingerprint=right.source_fingerprint,
        source_unit_key="doc:0",
        span=SourceSpan(0, 3),
        entity_type=EntityType.CHARACTER,
        text="Bob",
    )
    try:
        IdentityScoringContext(source=left, mentions=(mention,))
    except ValueError as exc:
        assert "different source" in str(exc)
    else:
        raise AssertionError("expected cross-source context rejection")


def test_hybrid_candidate_features_are_finite():
    source = source_for("Alice met Bob. She")
    alice = Mention.create(
        source_fingerprint=source.source_fingerprint,
        source_unit_key="doc:0",
        span=SourceSpan(0, 5),
        entity_type=EntityType.CHARACTER,
        text="Alice",
    )
    target = Mention.create(
        source_fingerprint=source.source_fingerprint,
        source_unit_key="doc:0",
        span=SourceSpan(15, 18),
        entity_type=EntityType.CHARACTER,
        text="She",
    )
    entity = Entity(
        entity_id="ent-alice",
        entity_type=EntityType.CHARACTER,
        canonical_name="Alice",
        mention_ids=(alice.mention_id,),
        aliases=("Alice",),
    )
    candidates = HybridIdentityCandidateGenerator(top_k=2, lexical_k=1, recent_k=1).generate(
        mention=target,
        existing_entities=(entity,),
        context=IdentityScoringContext(source=source, mentions=(alice,)),
    )
    assert candidates[0].candidate_entity_id == "ent-alice"
    assert candidates[0].features["recent_rank"] == 1.0
