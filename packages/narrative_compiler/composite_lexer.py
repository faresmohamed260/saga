"""Model-independent composition for grounded V3 semantic-lexer passes."""

from __future__ import annotations

import json
from typing import Iterable, Sequence

from .fingerprint import artifact_fingerprint, config_fingerprint
from .ir import Mention, ModelDescriptor, StageRunDescriptor
from .source import NormalizedSource
from .stages import LexerResult, SemanticLexer


class CompositeSemanticLexer:
    """Union multiple grounded lexer passes with deterministic provenance.

    Each child lexer remains responsible for its own model/configuration and
    source grounding. The composite only combines already-grounded mentions.

    Duplicate mentions are identified by canonical V3 ``mention_id``. That ID is
    bound to source fingerprint, source unit, span and entity type, so the
    composite never performs fuzzy span merging. For an exact duplicate, the
    highest-confidence observation is the primary record while provenance from
    every child observation is retained in immutable string attributes.
    """

    stage_name = "semantic-lexer-composite"
    stage_version = "v3.0.0"

    def __init__(self, lexers: Sequence[SemanticLexer]) -> None:
        if not lexers:
            raise ValueError("CompositeSemanticLexer requires at least one child lexer")
        self._lexers = tuple(lexers)

    @property
    def descriptor(self) -> ModelDescriptor | None:
        # A composite may contain zero, one, or many models. Child run
        # descriptors retain exact model provenance; claiming one model here
        # would be misleading.
        return None

    def analyze(self, source: NormalizedSource) -> LexerResult:
        child_results = [lexer.analyze(source) for lexer in self._lexers]
        child_results.sort(
            key=lambda result: (
                result.run.stage_name,
                result.run.stage_version,
                result.run.artifact_fingerprint,
            )
        )

        grouped: dict[str, list[tuple[StageRunDescriptor, Mention]]] = {}
        for result in child_results:
            for mention in result.mentions:
                self._validate_grounding(source=source, mention=mention)
                grouped.setdefault(mention.mention_id, []).append((result.run, mention))

        mentions = tuple(
            sorted(
                (self._merge_duplicate(rows) for rows in grouped.values()),
                key=lambda mention: (
                    mention.evidence.span.start_offset,
                    mention.evidence.span.end_offset,
                    mention.entity_type.value,
                    mention.mention_id,
                ),
            )
        )
        config = {
            "deduplication": "canonical-mention-id/max-confidence-primary",
            "child_stages": sorted(
                f"{result.run.stage_name}@{result.run.stage_version}"
                for result in child_results
            ),
        }
        upstream = [result.run.artifact_fingerprint for result in child_results]
        artifact = artifact_fingerprint(
            source_fingerprint=source.source_fingerprint,
            stage_name=self.stage_name,
            stage_version=self.stage_version,
            config=config,
            upstream_fingerprints=upstream,
        )
        return LexerResult(
            run=StageRunDescriptor(
                stage_name=self.stage_name,
                stage_version=self.stage_version,
                config_fingerprint=config_fingerprint(config),
                artifact_fingerprint=artifact,
            ),
            mentions=mentions,
        )

    @staticmethod
    def _validate_grounding(*, source: NormalizedSource, mention: Mention) -> None:
        if mention.evidence.source_fingerprint != source.source_fingerprint:
            raise ValueError("composite child mention belongs to a different source")
        section = next(
            (item for item in source.sections if item.stable_key == mention.evidence.source_unit_key),
            None,
        )
        if section is None:
            raise ValueError("composite child mention references an unknown source unit")
        span = mention.evidence.span
        if span.start_offset < section.span.start_offset or span.end_offset > section.span.end_offset:
            raise ValueError("composite child mention falls outside its source unit")
        if source.normalized_text[span.start_offset : span.end_offset] != mention.text:
            raise ValueError("composite child mention text does not match normalized source")

    @classmethod
    def _merge_duplicate(
        cls,
        rows: Iterable[tuple[StageRunDescriptor, Mention]],
    ) -> Mention:
        ordered = sorted(
            rows,
            key=lambda row: (
                -(row[1].confidence if row[1].confidence is not None else -1.0),
                row[0].stage_name,
                row[0].stage_version,
                row[0].artifact_fingerprint,
            ),
        )
        if not ordered:
            raise ValueError("cannot merge an empty mention group")

        primary_run, primary = ordered[0]
        del primary_run
        for _, mention in ordered[1:]:
            if (
                mention.entity_type != primary.entity_type
                or mention.text != primary.text
                or mention.evidence != primary.evidence
                or mention.acceptance != primary.acceptance
            ):
                raise ValueError("duplicate mention ID resolved to conflicting grounded mention data")

        confidences = [mention.confidence for _, mention in ordered if mention.confidence is not None]
        confidence = max(confidences) if confidences else None

        provenance = []
        lexer_labels: set[str] = set()
        for run, mention in ordered:
            label = mention.attributes.get("lexer_label")
            if label:
                lexer_labels.add(label)
            provenance.append(
                {
                    "stage": run.stage_name,
                    "stage_version": run.stage_version,
                    "artifact_fingerprint": run.artifact_fingerprint,
                    "model": cls._model_record(run.model),
                    "confidence": mention.confidence,
                    "attributes": dict(mention.attributes),
                }
            )

        attributes = dict(primary.attributes)
        attributes["composite_provenance"] = json.dumps(
            provenance,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        attributes["composite_sources"] = "|".join(
            sorted({run.stage_name for run, _ in ordered})
        )
        if lexer_labels:
            attributes["lexer_labels"] = "|".join(sorted(lexer_labels))

        return Mention(
            mention_id=primary.mention_id,
            entity_type=primary.entity_type,
            text=primary.text,
            evidence=primary.evidence,
            confidence=confidence,
            acceptance=primary.acceptance,
            attributes=attributes,
        )

    @staticmethod
    def _model_record(model: ModelDescriptor | None) -> dict[str, str | None] | None:
        if model is None:
            return None
        return {
            "model_id": model.model_id,
            "revision": model.revision,
            "adapter": model.adapter,
            "license_id": model.license_id,
        }
