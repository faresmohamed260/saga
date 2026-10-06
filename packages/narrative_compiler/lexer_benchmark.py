"""Direct semantic-lexer mention evaluation for V3.0.

This module scores the lexer on the job it actually owns: grounded character
mention detection. Identity clustering/merging is intentionally excluded.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Sequence

from .benchmark import GoldIdentityDocument
from .ir import EntityType, Mention


@dataclass(frozen=True, slots=True)
class LexerMentionCounts:
    document_count: int = 0
    gold_person_mentions: int = 0
    predicted_character_mentions: int = 0
    true_positive_mentions: int = 0
    proper_name_gold: int = 0
    proper_name_true_positive: int = 0
    nominal_gold: int = 0
    nominal_true_positive: int = 0
    pronoun_gold: int = 0
    pronoun_true_positive: int = 0


@dataclass(frozen=True, slots=True)
class LexerMentionMetrics:
    precision: float
    recall: float
    f1: float
    proper_name_recall: float
    nominal_recall: float
    pronoun_recall: float


@dataclass(frozen=True, slots=True)
class LexerMentionReport:
    counts: LexerMentionCounts
    metrics: LexerMentionMetrics


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return 0.0 if denominator == 0 else float(numerator) / float(denominator)


def metrics_from_counts(counts: LexerMentionCounts) -> LexerMentionMetrics:
    precision = _ratio(counts.true_positive_mentions, counts.predicted_character_mentions)
    recall = _ratio(counts.true_positive_mentions, counts.gold_person_mentions)
    f1 = 0.0 if precision + recall == 0 else 2.0 * precision * recall / (precision + recall)
    return LexerMentionMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        proper_name_recall=_ratio(counts.proper_name_true_positive, counts.proper_name_gold),
        nominal_recall=_ratio(counts.nominal_true_positive, counts.nominal_gold),
        pronoun_recall=_ratio(counts.pronoun_true_positive, counts.pronoun_gold),
    )


def evaluate_character_mentions(
    *,
    gold: GoldIdentityDocument,
    mentions: Sequence[Mention],
) -> LexerMentionReport:
    """Score exact source spans for person/character mentions.

    Duplicate predicted spans are intentionally collapsed before scoring so a
    provider cannot gain or lose credit solely by emitting the same character
    span more than once under equivalent labels.
    """

    gold_people = [row for row in gold.mentions if row.entity_type == "person"]
    gold_by_span = {(row.start_offset, row.end_offset): row for row in gold_people}
    predicted = [row for row in mentions if row.entity_type is EntityType.CHARACTER]
    predicted_spans = {(row.evidence.span.start_offset, row.evidence.span.end_offset) for row in predicted}
    true_spans = predicted_spans & set(gold_by_span)

    by_kind_gold = {"proper_name": 0, "nominal": 0, "pronoun": 0}
    by_kind_tp = {"proper_name": 0, "nominal": 0, "pronoun": 0}
    for row in gold_people:
        by_kind_gold[row.mention_kind] = by_kind_gold.get(row.mention_kind, 0) + 1
    for span in true_spans:
        kind = gold_by_span[span].mention_kind
        by_kind_tp[kind] = by_kind_tp.get(kind, 0) + 1

    counts = LexerMentionCounts(
        document_count=1,
        gold_person_mentions=len(gold_people),
        predicted_character_mentions=len(predicted_spans),
        true_positive_mentions=len(true_spans),
        proper_name_gold=by_kind_gold.get("proper_name", 0),
        proper_name_true_positive=by_kind_tp.get("proper_name", 0),
        nominal_gold=by_kind_gold.get("nominal", 0),
        nominal_true_positive=by_kind_tp.get("nominal", 0),
        pronoun_gold=by_kind_gold.get("pronoun", 0),
        pronoun_true_positive=by_kind_tp.get("pronoun", 0),
    )
    return LexerMentionReport(counts=counts, metrics=metrics_from_counts(counts))


def aggregate_character_mention_reports(reports: Sequence[LexerMentionReport]) -> LexerMentionReport:
    totals = {field.name: 0 for field in fields(LexerMentionCounts)}
    for report in reports:
        for field in fields(LexerMentionCounts):
            totals[field.name] += getattr(report.counts, field.name)
    counts = LexerMentionCounts(**totals)
    return LexerMentionReport(counts=counts, metrics=metrics_from_counts(counts))
