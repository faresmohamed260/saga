import hashlib
import json

from packages.narrative_compiler.composite_lexer import CompositeSemanticLexer
from packages.narrative_compiler.ir import EntityType, Mention, SourceSpan, StageRunDescriptor
from packages.narrative_compiler.source import NormalizedSource
from packages.narrative_compiler.stages import LexerResult


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


def mention_for(
    source: NormalizedSource,
    start: int,
    end: int,
    *,
    entity_type: EntityType = EntityType.CHARACTER,
    confidence: float | None = None,
    label: str | None = None,
) -> Mention:
    attributes = {} if label is None else {"lexer_label": label}
    return Mention.create(
        source_fingerprint=source.source_fingerprint,
        source_unit_key="doc:0",
        span=SourceSpan(start, end),
        entity_type=entity_type,
        text=source.normalized_text[start:end],
        confidence=confidence,
        attributes=attributes,
    )


class FixtureLexer:
    descriptor = None

    def __init__(self, stage: str, artifact: str, mentions):
        self.stage = stage
        self.artifact = artifact
        self.mentions = tuple(mentions)

    def analyze(self, source):
        del source
        return LexerResult(
            run=StageRunDescriptor(
                stage_name=self.stage,
                stage_version="fixture-v1",
                config_fingerprint=f"cfg-{self.stage}",
                artifact_fingerprint=self.artifact,
            ),
            mentions=self.mentions,
        )


def test_composite_deduplicates_exact_mentions_and_preserves_provenance():
    source = source_for("Alice waved.")
    low = mention_for(source, 0, 5, confidence=0.6, label="person")
    high = mention_for(source, 0, 5, confidence=0.9, label="character name")

    result = CompositeSemanticLexer(
        (
            FixtureLexer("lexer-low", "artifact-low", (low,)),
            FixtureLexer("lexer-high", "artifact-high", (high,)),
        )
    ).analyze(source)

    assert len(result.mentions) == 1
    merged = result.mentions[0]
    assert merged.mention_id == high.mention_id == low.mention_id
    assert merged.confidence == 0.9
    assert merged.attributes["lexer_label"] == "character name"
    assert merged.attributes["lexer_labels"] == "character name|person"
    assert merged.attributes["composite_sources"] == "lexer-high|lexer-low"
    provenance = json.loads(merged.attributes["composite_provenance"])
    assert {row["artifact_fingerprint"] for row in provenance} == {"artifact-high", "artifact-low"}


def test_composite_is_order_invariant():
    source = source_for("Alice waved.")
    first = FixtureLexer(
        "lexer-a",
        "artifact-a",
        (mention_for(source, 0, 5, confidence=0.7, label="character name"),),
    )
    second = FixtureLexer(
        "lexer-b",
        "artifact-b",
        (mention_for(source, 0, 5, confidence=0.7, label="person"),),
    )

    left = CompositeSemanticLexer((first, second)).analyze(source)
    right = CompositeSemanticLexer((second, first)).analyze(source)

    assert left.run.artifact_fingerprint == right.run.artifact_fingerprint
    assert left.run.config_fingerprint == right.run.config_fingerprint
    assert left.mentions == right.mentions


def test_composite_keeps_same_span_when_entity_types_differ():
    source = source_for("Paris shines.")
    character = mention_for(source, 0, 5, entity_type=EntityType.CHARACTER, confidence=0.6)
    location = mention_for(source, 0, 5, entity_type=EntityType.LOCATION, confidence=0.9)

    result = CompositeSemanticLexer(
        (
            FixtureLexer("character-lexer", "artifact-character", (character,)),
            FixtureLexer("location-lexer", "artifact-location", (location,)),
        )
    ).analyze(source)

    assert [mention.entity_type for mention in result.mentions] == [
        EntityType.CHARACTER,
        EntityType.LOCATION,
    ]


def test_composite_rejects_child_mentions_from_another_source():
    source = source_for("Alice")
    other = source_for("Bob")
    foreign = mention_for(other, 0, 3)

    try:
        CompositeSemanticLexer((FixtureLexer("foreign", "artifact-foreign", (foreign,)),)).analyze(source)
    except ValueError as exc:
        assert "different source" in str(exc)
    else:
        raise AssertionError("expected cross-source mention rejection")


def test_composite_artifact_is_bound_to_child_artifacts():
    source = source_for("Alice")
    mention = mention_for(source, 0, 5)

    left = CompositeSemanticLexer((FixtureLexer("child", "artifact-a", (mention,)),)).analyze(source)
    right = CompositeSemanticLexer((FixtureLexer("child", "artifact-b", (mention,)),)).analyze(source)

    assert left.run.artifact_fingerprint != right.run.artifact_fingerprint
