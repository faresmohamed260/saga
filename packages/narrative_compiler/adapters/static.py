"""Deterministic in-memory lexer used for contract tests and recorded fixtures."""

from __future__ import annotations

from typing import Sequence

from ..fingerprint import artifact_fingerprint, config_fingerprint
from ..ir import Mention, ModelDescriptor, StageRunDescriptor
from ..source import NormalizedSource
from ..stages import LexerResult


class StaticSemanticLexer:
    stage_name = "semantic-lexer-static"
    stage_version = "v3.0.0"

    def __init__(self, mentions: Sequence[Mention]) -> None:
        self._mentions = tuple(mentions)

    @property
    def descriptor(self) -> ModelDescriptor | None:
        return None

    def analyze(self, source: NormalizedSource) -> LexerResult:
        for mention in self._mentions:
            if mention.evidence.source_fingerprint != source.source_fingerprint:
                raise ValueError("static mention is bound to a different source fingerprint")
            span = mention.evidence.span
            if source.normalized_text[span.start_offset : span.end_offset] != mention.text:
                raise ValueError("static mention text does not match normalized source")
        config = {"fixture_mentions": [mention.mention_id for mention in self._mentions]}
        artifact = artifact_fingerprint(
            source_fingerprint=source.source_fingerprint,
            stage_name=self.stage_name,
            stage_version=self.stage_version,
            config=config,
        )
        return LexerResult(
            run=StageRunDescriptor(
                stage_name=self.stage_name,
                stage_version=self.stage_version,
                config_fingerprint=config_fingerprint(config),
                artifact_fingerprint=artifact,
            ),
            mentions=self._mentions,
        )
