"""Typed V3.0 compiler orchestration.

The compiler is a static dataflow. It does not ask an agent/model which mandatory
stage to execute next; stage order and provenance dependencies are explicit.
"""

from __future__ import annotations

from dataclasses import dataclass

from .source import NormalizedSource
from .stages import GlobalCharacterLinker, LexerResult, LinkerResult, SemanticLexer


@dataclass(frozen=True, slots=True)
class IdentityCompilation:
    source_fingerprint: str
    lexer: LexerResult
    linker: LinkerResult

    def __post_init__(self) -> None:
        if self.lexer.run.artifact_fingerprint == self.linker.run.artifact_fingerprint:
            raise ValueError("compiler stages must have distinct artifact fingerprints")


class NarrativeCompilerV30:
    """First V3 compiler slice: source -> lexer -> character linker."""

    def __init__(self, *, lexer: SemanticLexer, linker: GlobalCharacterLinker) -> None:
        self.lexer = lexer
        self.linker = linker

    def compile_identity(self, source: NormalizedSource) -> IdentityCompilation:
        lexical = self.lexer.analyze(source)
        linked = self.linker.link(
            source=source,
            mentions=lexical.mentions,
            upstream_fingerprints=(lexical.run.artifact_fingerprint,),
        )
        return IdentityCompilation(
            source_fingerprint=source.source_fingerprint,
            lexer=lexical,
            linker=linked,
        )
