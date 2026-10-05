"""Identity benchmark contract shared by V2 and V3 challengers.

The primary metrics intentionally mirror the frozen TypeScript identity
benchmark semantics so the reboot cannot manufacture an improvement by changing
its ruler. Pairwise metrics remain available as a secondary diagnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Mapping, Sequence

from .ir import AcceptanceState, Entity, EntityType, Mention


@dataclass(frozen=True, slots=True)
class GoldIdentityMention:
    mention_id: str
    surface_text: str
    start_offset: int
    end_offset: int
    mention_kind: str
    entity_type: str
    gold_character_id: str | None


@dataclass(frozen=True, slots=True)
class GoldIdentityDocument:
    document_id: str
    text: str
    mentions: tuple[GoldIdentityMention, ...]


@dataclass(frozen=True, slots=True)
class IdentityBenchmarkCounts:
    document_count: int = 0
    gold_seed_eligible_character_count: int = 0
    predicted_canonical_count: int = 0
    pure_canonical_count: int = 0
    false_canonical_count: int = 0
    incorrect_merge_count: int = 0
    contaminated_canonical_count: int = 0
    represented_gold_character_count: int = 0
    fragmentation_excess_count: int = 0
    relevant_gold_mention_count: int = 0
    predicted_mention_count: int = 0
    correct_linked_mention_count: int = 0
    linked_mention_count: int = 0
    unresolved_relevant_mention_count: int = 0
    quarantined_relevant_mention_count: int = 0
    non_person_predicted_mention_count: int = 0
    non_person_linked_mention_count: int = 0
    non_person_quarantined_mention_count: int = 0
    linked_person_mention_count: int = 0
    dominant_cluster_linked_person_mention_count: int = 0


@dataclass(frozen=True, slots=True)
class IdentityBenchmarkMetrics:
    canonical_precision: float
    canonical_recall: float
    false_canonical_rate: float
    incorrect_merge_rate: float
    contaminated_canonical_rate: float
    fragmentation_rate: float
    linked_mention_precision: float
    linked_mention_recall: float
    unresolved_relevant_mention_rate: float
    quarantined_relevant_mention_rate: float
    non_person_quarantine_rate: float
    cluster_purity: float


@dataclass(frozen=True, slots=True)
class IdentityBenchmarkReport:
    counts: IdentityBenchmarkCounts
    metrics: IdentityBenchmarkMetrics


def _ratio(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def metrics_from_counts(counts: IdentityBenchmarkCounts) -> IdentityBenchmarkMetrics:
    return IdentityBenchmarkMetrics(
        canonical_precision=_ratio(counts.pure_canonical_count, counts.predicted_canonical_count),
        canonical_recall=_ratio(
            counts.represented_gold_character_count,
            counts.gold_seed_eligible_character_count,
        ),
        false_canonical_rate=_ratio(counts.false_canonical_count, counts.predicted_canonical_count),
        incorrect_merge_rate=_ratio(counts.incorrect_merge_count, counts.predicted_canonical_count),
        contaminated_canonical_rate=_ratio(
            counts.contaminated_canonical_count,
            counts.predicted_canonical_count,
        ),
        fragmentation_rate=_ratio(
            counts.fragmentation_excess_count,
            counts.gold_seed_eligible_character_count,
        ),
        linked_mention_precision=_ratio(counts.correct_linked_mention_count, counts.linked_mention_count),
        linked_mention_recall=_ratio(
            counts.correct_linked_mention_count,
            counts.relevant_gold_mention_count,
        ),
        unresolved_relevant_mention_rate=_ratio(
            counts.unresolved_relevant_mention_count,
            counts.relevant_gold_mention_count,
        ),
        quarantined_relevant_mention_rate=_ratio(
            counts.quarantined_relevant_mention_count,
            counts.relevant_gold_mention_count,
        ),
        non_person_quarantine_rate=_ratio(
            counts.non_person_quarantined_mention_count,
            counts.non_person_predicted_mention_count,
        ),
        cluster_purity=_ratio(
            counts.dominant_cluster_linked_person_mention_count,
            counts.linked_person_mention_count,
        ),
    )


def _gold_span_index(gold: GoldIdentityDocument) -> dict[tuple[int, int], list[GoldIdentityMention]]:
    index: dict[tuple[int, int], list[GoldIdentityMention]] = {}
    for mention in gold.mentions:
        index.setdefault((mention.start_offset, mention.end_offset), []).append(mention)
    return index


def _align_gold_mention(
    mention: Mention,
    index: Mapping[tuple[int, int], Sequence[GoldIdentityMention]],
) -> GoldIdentityMention | None:
    candidates = list(index.get((mention.evidence.span.start_offset, mention.evidence.span.end_offset), ()))
    exact_surface = [candidate for candidate in candidates if candidate.surface_text == mention.text]
    if len(exact_surface) == 1:
        return exact_surface[0]
    if len(candidates) == 1:
        return candidates[0]
    return None


def evaluate_identity_benchmark(
    *,
    gold: GoldIdentityDocument,
    mentions: Sequence[Mention],
    entities: Sequence[Entity],
    unresolved_mention_ids: Sequence[str] = (),
    quarantined_mention_ids: Sequence[str] = (),
) -> IdentityBenchmarkReport:
    """Evaluate a V2 projection or V3 candidate clusters with v2-compatible semantics.

    Candidate entities are scored as predicted canonicals for challenger quality
    measurement. `UNRESOLVED` and `REJECTED` entities are never counted as
    canonicals. This does not promote candidate entities into product canon.
    """

    mention_by_id = {mention.mention_id: mention for mention in mentions}
    if len(mention_by_id) != len(mentions):
        raise ValueError("predicted mention IDs must be unique")

    active_entities = [
        entity
        for entity in entities
        if entity.entity_type is EntityType.CHARACTER
        and entity.acceptance in {AcceptanceState.CANDIDATE, AcceptanceState.ACCEPTED}
    ]
    entity_by_mention: dict[str, Entity] = {}
    for entity in active_entities:
        for mention_id in entity.mention_ids:
            if mention_id not in mention_by_id:
                raise ValueError(f"entity references unknown mention: {mention_id}")
            if mention_id in entity_by_mention:
                raise ValueError(f"mention belongs to multiple predicted canonicals: {mention_id}")
            entity_by_mention[mention_id] = entity

    gold_span_index = _gold_span_index(gold)
    aligned = {mention.mention_id: _align_gold_mention(mention, gold_span_index) for mention in mentions}

    seed_eligible = {
        mention.gold_character_id
        for mention in gold.mentions
        if mention.entity_type == "person"
        and mention.gold_character_id is not None
        and mention.mention_kind == "proper_name"
    }

    assessments: dict[str, dict[str, object]] = {}
    for entity in active_entities:
        gold_character_ids: set[str] = set()
        per_gold: dict[str, int] = {}
        contaminating = 0
        linked_person = 0
        for mention_id in entity.mention_ids:
            gold_mention = aligned.get(mention_id)
            if gold_mention is not None and gold_mention.entity_type == "person" and gold_mention.gold_character_id:
                gold_character_ids.add(gold_mention.gold_character_id)
                linked_person += 1
                per_gold[gold_mention.gold_character_id] = per_gold.get(gold_mention.gold_character_id, 0) + 1
            else:
                contaminating += 1
        dominant = max(per_gold.values(), default=0)
        pure_gold_id = next(iter(gold_character_ids)) if len(gold_character_ids) == 1 and contaminating == 0 else None
        assessments[entity.entity_id] = {
            "gold_ids": gold_character_ids,
            "contaminating": contaminating,
            "linked_person": linked_person,
            "dominant": dominant,
            "pure_gold_id": pure_gold_id,
        }

    pure = [assessment for assessment in assessments.values() if assessment["pure_gold_id"] is not None]
    represented = {
        str(assessment["pure_gold_id"])
        for assessment in pure
        if assessment["pure_gold_id"] in seed_eligible
    }

    fragmentation_excess = 0
    for gold_id in seed_eligible:
        predicted_keys = {
            entity_id
            for entity_id, assessment in assessments.items()
            if gold_id in assessment["gold_ids"]
        }
        fragmentation_excess += max(0, len(predicted_keys) - 1)

    relevant_gold_mentions = [
        mention
        for mention in gold.mentions
        if mention.entity_type == "person"
        and mention.gold_character_id is not None
        and mention.gold_character_id in seed_eligible
    ]
    relevant_gold_ids = {mention.mention_id for mention in relevant_gold_mentions}
    unresolved = set(unresolved_mention_ids)
    quarantined = set(quarantined_mention_ids)

    linked_mention_count = 0
    correct_linked = 0
    unresolved_relevant = 0
    quarantined_relevant = 0
    non_person_predicted = 0
    non_person_linked = 0
    non_person_quarantined = 0

    for mention in mentions:
        gold_mention = aligned.get(mention.mention_id)
        linked_entity = entity_by_mention.get(mention.mention_id)
        if linked_entity is not None:
            linked_mention_count += 1

        is_quarantined = mention.mention_id in quarantined or mention.acceptance is AcceptanceState.REJECTED
        is_unresolved = mention.mention_id in unresolved or mention.acceptance is AcceptanceState.UNRESOLVED

        if gold_mention is not None and gold_mention.entity_type == "non_person":
            non_person_predicted += 1
            if linked_entity is not None:
                non_person_linked += 1
            if is_quarantined:
                non_person_quarantined += 1

        if gold_mention is not None and gold_mention.mention_id in relevant_gold_ids:
            if is_unresolved:
                unresolved_relevant += 1
            if is_quarantined:
                quarantined_relevant += 1
            if linked_entity is not None and gold_mention.gold_character_id:
                assessment = assessments[linked_entity.entity_id]
                if assessment["pure_gold_id"] == gold_mention.gold_character_id:
                    correct_linked += 1

    counts = IdentityBenchmarkCounts(
        document_count=1,
        gold_seed_eligible_character_count=len(seed_eligible),
        predicted_canonical_count=len(active_entities),
        pure_canonical_count=len(pure),
        false_canonical_count=sum(1 for item in assessments.values() if len(item["gold_ids"]) == 0),
        incorrect_merge_count=sum(1 for item in assessments.values() if len(item["gold_ids"]) > 1),
        contaminated_canonical_count=sum(1 for item in assessments.values() if int(item["contaminating"]) > 0),
        represented_gold_character_count=len(represented),
        fragmentation_excess_count=fragmentation_excess,
        relevant_gold_mention_count=len(relevant_gold_mentions),
        predicted_mention_count=len(mentions),
        correct_linked_mention_count=correct_linked,
        linked_mention_count=linked_mention_count,
        unresolved_relevant_mention_count=unresolved_relevant,
        quarantined_relevant_mention_count=quarantined_relevant,
        non_person_predicted_mention_count=non_person_predicted,
        non_person_linked_mention_count=non_person_linked,
        non_person_quarantined_mention_count=non_person_quarantined,
        linked_person_mention_count=sum(int(item["linked_person"]) for item in assessments.values()),
        dominant_cluster_linked_person_mention_count=sum(int(item["dominant"]) for item in assessments.values()),
    )
    return IdentityBenchmarkReport(counts=counts, metrics=metrics_from_counts(counts))


def aggregate_identity_benchmarks(reports: Sequence[IdentityBenchmarkReport]) -> IdentityBenchmarkReport:
    values = {
        field.name: sum(getattr(report.counts, field.name) for report in reports)
        for field in fields(IdentityBenchmarkCounts)
    }
    counts = IdentityBenchmarkCounts(**values)
    return IdentityBenchmarkReport(counts=counts, metrics=metrics_from_counts(counts))


# Secondary pairwise diagnostic retained for local experiments.
@dataclass(frozen=True, slots=True)
class PairwiseIdentityMetrics:
    evaluated_mentions: int
    predicted_linked_mentions: int
    mention_attachment_precision: float
    mention_attachment_recall: float
    incorrect_merge_rate: float
    fragmentation_rate: float
    unresolved_rate: float


def _pairs(cluster: Sequence[str]) -> set[tuple[str, str]]:
    ordered = sorted(set(cluster))
    return {(ordered[i], ordered[j]) for i in range(len(ordered)) for j in range(i + 1, len(ordered))}


def score_identity_clusters(
    *,
    gold_entity_by_mention: Mapping[str, str],
    predicted_entities: Sequence[Entity],
    unresolved_mention_ids: Sequence[str] = (),
) -> PairwiseIdentityMetrics:
    gold_mentions = set(gold_entity_by_mention)
    predicted_pairs: set[tuple[str, str]] = set()
    predicted_mentions: set[str] = set()
    for entity in predicted_entities:
        if entity.acceptance in {AcceptanceState.UNRESOLVED, AcceptanceState.REJECTED}:
            continue
        in_scope = [mention_id for mention_id in entity.mention_ids if mention_id in gold_mentions]
        predicted_mentions.update(in_scope)
        predicted_pairs.update(_pairs(in_scope))

    gold_clusters: dict[str, list[str]] = {}
    for mention_id, gold_id in gold_entity_by_mention.items():
        gold_clusters.setdefault(gold_id, []).append(mention_id)
    gold_pairs = set().union(*(_pairs(cluster) for cluster in gold_clusters.values())) if gold_clusters else set()

    correct_pairs = predicted_pairs & gold_pairs
    wrong_pairs = predicted_pairs - gold_pairs
    missed_pairs = gold_pairs - predicted_pairs

    precision = len(correct_pairs) / len(predicted_pairs) if predicted_pairs else 1.0
    recall = len(correct_pairs) / len(gold_pairs) if gold_pairs else 1.0
    incorrect_merge = len(wrong_pairs) / len(predicted_pairs) if predicted_pairs else 0.0
    fragmentation = len(missed_pairs) / len(gold_pairs) if gold_pairs else 0.0
    unresolved = len(set(unresolved_mention_ids) & gold_mentions) / len(gold_mentions) if gold_mentions else 0.0

    return PairwiseIdentityMetrics(
        evaluated_mentions=len(gold_mentions),
        predicted_linked_mentions=len(predicted_mentions),
        mention_attachment_precision=precision,
        mention_attachment_recall=recall,
        incorrect_merge_rate=incorrect_merge,
        fragmentation_rate=fragmentation,
        unresolved_rate=unresolved,
    )
