"""Deterministic English character-pronoun mention provider for V3.0."""

from __future__ import annotations

import re
from typing import Mapping

from ..fingerprint import artifact_fingerprint, config_fingerprint
from ..ir import EntityType, Mention, ModelDescriptor, SourceSpan, StageRunDescriptor
from ..source import NormalizedSource
from ..stages import LexerResult


_TOKEN_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")

_STRICT = frozenset(
    {
        "i",
        "me",
        "my",
        "mine",
        "myself",
        "we",
        "us",
        "our",
        "ours",
        "ourselves",
        "you",
        "your",
        "yours",
        "yourself",
        "yourselves",
        "he",
        "him",
        "his",
        "himself",
        "she",
        "her",
        "hers",
        "herself",
    }
)

_PROFILES: Mapping[str, frozenset[str]] = {
    "strict": _STRICT,
    "plus_plural": _STRICT
    | frozenset({"they", "them", "their", "theirs", "themself", "themselves"}),
    "plus_neuter": _STRICT
    | frozenset(
        {
            "they",
            "them",
            "their",
            "theirs",
            "themself",
            "themselves",
            "it",
            "its",
            "itself",
        }
    ),
}


class EnglishCharacterPronounLexer:
    """Emit grounded character-pronoun candidates from a closed lexical class.

    This adapter only owns mention-span detection. It does not decide which
    character a pronoun refers to, and it deliberately exposes no probabilistic
    confidence score.
    """

    stage_name = "semantic-lexer-english-pronouns"
    stage_version = "v3.0.0"

    def __init__(self, *, profile: str = "plus_plural") -> None:
        try:
            self.pronouns = _PROFILES[profile]
        except KeyError as exc:
            raise ValueError(f"unsupported pronoun profile: {profile}") from exc
        self.profile = profile

    @property
    def descriptor(self) -> ModelDescriptor | None:
        return None

    def analyze(self, source: NormalizedSource) -> LexerResult:
        mentions: list[Mention] = []
        for section in source.sections:
            for match in _TOKEN_RE.finditer(section.normalized_text):
                token = match.group(0)
                if token.casefold() not in self.pronouns:
                    continue
                start = section.span.start_offset + match.start()
                end = section.span.start_offset + match.end()
                mentions.append(
                    Mention.create(
                        source_fingerprint=source.source_fingerprint,
                        source_unit_key=section.stable_key,
                        span=SourceSpan(start, end),
                        entity_type=EntityType.CHARACTER,
                        text=token,
                        attributes={
                            "lexer_label": "person pronoun lexical",
                            "mention_kind": "pronoun",
                            "mention_detector": "english-pronoun-lexicon",
                            "pronoun_profile": self.profile,
                        },
                    )
                )

        config = {"profile": self.profile, "pronouns": sorted(self.pronouns)}
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
            mentions=tuple(
                sorted(
                    mentions,
                    key=lambda item: (
                        item.evidence.span.start_offset,
                        item.evidence.span.end_offset,
                        item.mention_id,
                    ),
                )
            ),
        )
