"""Oracle-history identity retrieval/reranking benchmark for V3.0.

This benchmark deliberately isolates two pre-merge questions:

1. can candidate generation retrieve the already-established gold character?
2. when that candidate is available, can an optional scorer rank it highly?

Gold history is used only to maintain the prior entity clusters. The target
mention's gold ID is never exposed to candidate generation or scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Mapping, Sequence

from .benchmark import GoldIdentityDocument, GoldIdentityMention
from .fingerprint import stable_id
from .ir import AcceptanceState, Entity, EntityType, Mention, SourceSpan
from .source import NormalizedSource
from .stages import IdentityCandidateGenerator, IdentityScore, IdentityScorer, IdentityScoringContext


@dataclass(frozen=True, slots=True)
class IdentityRankingCounts:
    eligible_mentions: int = 0
    nonempty_candidate_sets: int = 0
    true_candidate_retrieved: int = 0
    candidate_hit_at_1: int = 0
    candidate_hit_at_3: int = 0
    candidate_hit_at_5: int = 0
    candidate_reciprocal_rank_sum: float = 0.0
    scorer_candidate_sets_scored: int = 0
    scored_candidate_pairs: int = 0
    scorer_true_candidate_available: int = 0
    scorer_hit_at_1: int = 0
    scorer_hit_at_3: int = 0
    scorer_hit_at_5: int = 0
    scorer_reciprocal_rank_sum: float = 0.0


@dataclass(frozen=True, slots=True)
class IdentityRankingMetrics:
    candidate_nonempty_rate: float
    candidate_retrieval_rate: float
    candidate_recall_at_1: float
    candidate_recall_at_3: float
    candidate_recall_at_5: float
    candidate_mrr: float
    scorer_execution_rate: float
    scorer_top1_end_to_end: float
    scorer_recall_at_3_end_to_end: float
    scorer_recall_at_5_end_to_end: float
    scorer_mrr_end_to_end: float
    scorer_top1_conditional: float
    scorer_mrr_conditional: float


@dataclass(frozen=True, slots=True)
class IdentityRankingBucketReport:
    counts: IdentityRankingCounts
    metrics: IdentityRankingMetrics


@dataclass(frozen=True, slots=True)
class IdentityRankingReport:
    overall: IdentityRankingBucketReport
    by_mention_kind: Mapping[str, IdentityRankingBucketReport]


@dataclass(slots=True)
class _Accumulator:
    eligible_mentions: int = 0
    nonempty_candidate_sets: int = 0
    true_candidate_retrieved: int = 0
    candidate_hit_at_1: int = 0
    candidate_hit_at_3: int = 0
    candidate_hit_at_5: int = 0
    candidate_reciprocal_rank_sum: float = 0.0
    scorer_candidate_sets_scored: int = 0
    scored_candidate_pairs: int = 0
    scorer_true_candidate_available: int = 0
    scorer_hit_at_1: int = 0
    scorer_hit_at_3: int = 0
    scorer_hit_at_5: int = 0
    scorer_reciprocal_rank_sum: float = 0.0

    def observe(
        self,
        *,
        candidate_rank: int | None,
        candidate_count: int,
        scorer_rank: int | None,
        scorer_ran: bool,
    ) -> None:
        self.eligible_mentions += 1
        if candidate_count:
            self.nonempty_candidate_sets += 1
        if candidate_rank is not None:
            self.true_candidate_retrieved += 1
            self.candidate_reciprocal_rank_sum += 1.0 / candidate_rank
            if candidate_rank <= 1:
                self.candidate_hit_at_1 += 1
            if candidate_rank <= 3:
                self.candidate_hit_at_3 += 1
            if candidate_rank <= 5:
                self.candidate_hit_at_5 += 1
        if scorer_ran:
            self.scorer_candidate_sets_scored += 1
            self.scored_candidate_pairs += candidate_count
        if scorer_rank is not None:
            self.scorer_true_candidate_available += 1
            self.scorer_reciprocal_rank_sum += 1.0 / scorer_rank
            if scorer_rank <= 1:
                self.scorer_hit_at_1 += 1
            if scorer_rank <= 3:
                self.scorer_hit_at_3 += 1
            if scorer_rank <= 5:
                self.scorer_hit_at_5 += 1

    def freeze(self) -> IdentityRankingCounts:
        return IdentityRankingCounts(**{field.name: getattr(self, field.name) for field in fields(IdentityRankingCounts)})


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return 0.0 if denominator == 0 else float(numerator) / float(denominator)


def ranking_metrics_from_counts(counts: IdentityRankingCounts) -> IdentityRankingMetrics:
    eligible = counts.eligible_mentions
    available = counts.scorer_true_candidate_available
    return IdentityRankingMetrics(
        candidate_nonempty_rate=_ratio(counts.nonempty_candidate_sets, eligible),
        candidate_retrieval_rate=_ratio(counts.true_candidate_retrieved, eligible),
        candidate_recall_at_1=_ratio(counts.candidate_hit_at_1, eligible),
        candidate_recall_at_3=_ratio(counts.candidate_hit_at_3, eligible),
        candidate_recall_at_5=_ratio(counts.candidate_hit_at_5, eligible),
        candidate_mrr=_ratio(counts.candidate_reciprocal_rank_sum, eligible),
        scorer_execution_rate=_ratio(counts.scorer_candidate_sets_scored, eligible),
        scorer_top1_end_to_end=_ratio(counts.scorer_hit_at_1, eligible),
        scorer_recall_at_3_end_to_end=_ratio(counts.scorer_hit_at_3, eligible),
        scorer_recall_at_5_end_to_end=_ratio(counts.scorer_hit_at_5, eligible),
        scorer_mrr_end_to_end=_ratio(counts.scorer_reciprocal_rank_sum, eligible),
        scorer_top1_conditional=_ratio(counts.scorer_hit_at_1, available),
        scorer_mrr_conditional=_ratio(counts.scorer_reciprocal_rank_sum, available),
    )


def _report(accumulator: _Accumulator) -> IdentityRankingBucketReport:
    counts = accumulator.freeze()
    return IdentityRankingBucketReport(counts=counts, metrics=ranking_metrics_from_counts(counts))


def _target_mention(*, source: NormalizedSource, gold: GoldIdentityMention) -> Mention:
    return Mention.create(
        source_fingerprint=source.source_fingerprint,
        source_unit_key=source.sections[0].stable_key,
        span=SourceSpan(gold.start_offset, gold.end_offset),
        entity_type=EntityType.CHARACTER,
        text=gold.surface_text,
        attributes={"mention_kind": gold.mention_kind},
    )


def _candidate_rank(candidate_ids: Sequence[str], true_entity_id: str) -> int | None:
    try:
        return list(candidate_ids).index(true_entity_id) + 1
    except ValueError:
        return None


def _append_gold_history(entity: Entity, mention: Mention, mention_kind: str) -> Entity:
    aliases = entity.aliases
    if mention_kind == "proper_name" and mention.text not in aliases:
        aliases = (*aliases, mention.text)
    return Entity(
        entity_id=entity.entity_id,
        entity_type=entity.entity_type,
        canonical_name=entity.canonical_name,
        mention_ids=(*entity.mention_ids, mention.mention_id),
        aliases=aliases,
        confidence=entity.confidence,
        acceptance=entity.acceptance,
    )


def _validate_scores(
    *,
    mention: Mention,
    candidate_entity_ids: Sequence[str],
    scores: Sequence[IdentityScore],
) -> None:
    expected = {(mention.mention_id, entity_id) for entity_id in candidate_entity_ids}
    observed = {(score.mention_id, score.candidate_entity_id) for score in scores}
    if len(scores) != len(candidate_entity_ids) or observed != expected:
        raise ValueError(
            "identity scorer must return exactly one score for every requested candidate"
        )


def _score_candidates(
    *,
    scorer: IdentityScorer,
    mention: Mention,
    candidates,
    existing_entities: Sequence[Entity],
    context: IdentityScoringContext,
) -> list[IdentityScore]:
    batch = getattr(scorer, "score_many", None)
    if callable(batch):
        scored = list(
            batch(
                mention=mention,
                candidates=candidates,
                existing_entities=existing_entities,
                context=context,
            )
        )
    else:
        scored = [
            scorer.score(
                mention=mention,
                candidate=candidate,
                existing_entities=existing_entities,
                context=context,
            )
            for candidate in candidates
        ]
    _validate_scores(
        mention=mention,
        candidate_entity_ids=[candidate.candidate_entity_id for candidate in candidates],
        scores=scored,
    )
    return scored


def evaluate_oracle_history_ranking(
    *,
    source: NormalizedSource,
    gold: GoldIdentityDocument,
    candidate_generator: IdentityCandidateGenerator,
    scorer: IdentityScorer | None = None,
) -> IdentityRankingReport:
    """Evaluate retrieval/reranking with oracle-correct history up to each target.

    A character becomes eligible only after its first proper-name seed has
    appeared. Pre-seed pronouns/nominals are not retroactively injected into the
    entity. After each eligible target is scored, gold history updates the entity
    so later cases measure ranking rather than cascading merge errors.
    """

    seeded_entities: dict[str, Entity] = {}
    prior_mentions: list[Mention] = []
    overall = _Accumulator()
    by_kind = {kind: _Accumulator() for kind in ("proper_name", "nominal", "pronoun")}

    person_mentions = sorted(
        (
            mention
            for mention in gold.mentions
            if mention.entity_type == "person" and mention.gold_character_id is not None
        ),
        key=lambda item: (item.start_offset, item.end_offset, item.mention_id),
    )

    for gold_mention in person_mentions:
        gold_id = gold_mention.gold_character_id
        assert gold_id is not None
        target = _target_mention(source=source, gold=gold_mention)
        entity = seeded_entities.get(gold_id)

        if entity is None:
            if gold_mention.mention_kind != "proper_name":
                continue
            entity = Entity(
                entity_id=stable_id(
                    "identity-ranking-gold-seed",
                    source.source_fingerprint,
                    gold_id,
                    prefix="ent",
                ),
                entity_type=EntityType.CHARACTER,
                canonical_name=target.text,
                mention_ids=(target.mention_id,),
                aliases=(target.text,),
                acceptance=AcceptanceState.CANDIDATE,
            )
            seeded_entities[gold_id] = entity
            prior_mentions.append(target)
            continue

        context = IdentityScoringContext(source=source, mentions=tuple(prior_mentions))
        existing = tuple(sorted(seeded_entities.values(), key=lambda item: item.entity_id))
        candidates = tuple(
            candidate_generator.generate(
                mention=target,
                existing_entities=existing,
                context=context,
            )
        )
        candidate_ids = [candidate.candidate_entity_id for candidate in candidates]
        candidate_rank = _candidate_rank(candidate_ids, entity.entity_id)

        scorer_rank: int | None = None
        scorer_ran = scorer is not None and bool(candidates)
        if scorer_ran and scorer is not None:
            scored = _score_candidates(
                scorer=scorer,
                mention=target,
                candidates=candidates,
                existing_entities=existing,
                context=context,
            )
            scored.sort(key=lambda item: (-item.score, item.candidate_entity_id))
            scorer_rank = _candidate_rank(
                [item.candidate_entity_id for item in scored],
                entity.entity_id,
            )

        kwargs = {
            "candidate_rank": candidate_rank,
            "candidate_count": len(candidates),
            "scorer_rank": scorer_rank,
            "scorer_ran": scorer_ran,
        }
        overall.observe(**kwargs)
        by_kind.setdefault(gold_mention.mention_kind, _Accumulator()).observe(**kwargs)

        seeded_entities[gold_id] = _append_gold_history(entity, target, gold_mention.mention_kind)
        prior_mentions.append(target)

    return IdentityRankingReport(
        overall=_report(overall),
        by_mention_kind={kind: _report(accumulator) for kind, accumulator in sorted(by_kind.items())},
    )


def aggregate_identity_ranking_reports(reports: Sequence[IdentityRankingReport]) -> IdentityRankingReport:
    overall = _Accumulator()
    by_kind: dict[str, _Accumulator] = {}

    def add_counts(accumulator: _Accumulator, counts: IdentityRankingCounts) -> None:
        for field in fields(IdentityRankingCounts):
            setattr(accumulator, field.name, getattr(accumulator, field.name) + getattr(counts, field.name))

    for report in reports:
        add_counts(overall, report.overall.counts)
        for kind, bucket in report.by_mention_kind.items():
            add_counts(by_kind.setdefault(kind, _Accumulator()), bucket.counts)

    return IdentityRankingReport(
        overall=_report(overall),
        by_mention_kind={kind: _report(accumulator) for kind, accumulator in sorted(by_kind.items())},
    )
