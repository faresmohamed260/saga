from packages.narrative_compiler.adapters.gliner2 import GLiNER25SemanticLexer
from packages.narrative_compiler.adapters.v2 import adapt_v2_identity_result
from packages.narrative_compiler.candidates import LexicalIdentityCandidateGenerator
from packages.narrative_compiler.ir import AcceptanceState, Entity, EntityType, Mention, SourceSpan
from packages.narrative_compiler.source import NormalizedSource
from packages.narrative_compiler.stages import IdentityScoringContext


def normalized_source():
    text = "Rhys arrived. Feyre watched Rhys."
    return NormalizedSource.from_v2_payload(
        {
            "normalizationVersion": "test-v1",
            "configFingerprint": "cfg",
            "normalizedSha256": "a" * 64,
            "outputFingerprint": "b" * 64,
            "normalizedText": text,
            "sections": [
                {
                    "stable_key": "chapter:0",
                    "ordinal": 0,
                    "section_kind": "chapter",
                    "title": None,
                    "source_locator": "chapter-1",
                    "start_offset": 0,
                    "end_offset": len(text),
                    "normalized_text": text,
                }
            ],
        }
    )


def test_v2_adapter_preserves_linked_and_unresolved_states():
    source = normalized_source()
    payload = {
        "resolverVersion": "v2-test",
        "resolverConfigFingerprint": "resolver-cfg",
        "provider": {"name": "fixture", "model": None, "revision": "1"},
        "normalizedInputFingerprint": source.source_fingerprint,
        "outputFingerprint": "v2-output",
        "characters": [
            {
                "characterKey": "rhys",
                "canonicalName": "Rhys",
                "admissionTier": "canonical_seed",
                "evidenceCount": 2,
                "aliases": [{"surfaceForm": "Rhys", "normalizedForm": "rhys", "evidenceCount": 2}],
            }
        ],
        "mentions": [
            {
                "evidenceId": "m1",
                "characterKey": "rhys",
                "surfaceText": "Rhys",
                "startOffset": 0,
                "endOffset": 4,
                "structuralLocator": "chapter-1",
                "mentionKind": "proper_name",
                "resolutionState": "linked",
                "evidenceTier": "canonical_seed",
                "decisionReason": "fixture",
            },
            {
                "evidenceId": "m2",
                "characterKey": None,
                "surfaceText": "Feyre",
                "startOffset": 14,
                "endOffset": 19,
                "structuralLocator": "chapter-1",
                "mentionKind": "proper_name",
                "resolutionState": "unresolved",
                "evidenceTier": "attachment",
                "decisionReason": "fixture",
            },
        ],
    }
    projection = adapt_v2_identity_result(source=source, payload=payload)
    assert len(projection.entities) == 1
    assert projection.entities[0].canonical_name == "Rhys"
    assert projection.entities[0].acceptance is AcceptanceState.ACCEPTED
    assert len(projection.unresolved_mention_ids) == 1
    assert projection.v2_output_fingerprint == "v2-output"


def test_lexical_candidate_generator_ranks_exact_alias_first():
    source = normalized_source()
    mention = Mention.create(
        source_fingerprint=source.source_fingerprint,
        source_unit_key="chapter:0",
        span=SourceSpan(0, 4),
        entity_type=EntityType.CHARACTER,
        text="Rhys",
    )
    exact = Entity(
        entity_id="ent-rhys",
        entity_type=EntityType.CHARACTER,
        canonical_name="Rhysand",
        aliases=("Rhys", "Rhysand"),
        mention_ids=("prior-1",),
    )
    other = Entity(
        entity_id="ent-feyre",
        entity_type=EntityType.CHARACTER,
        canonical_name="Feyre Archeron",
        aliases=("Feyre",),
        mention_ids=("prior-2",),
    )
    candidates = LexicalIdentityCandidateGenerator(top_k=2).generate(
        mention=mention,
        existing_entities=[other, exact],
        context=IdentityScoringContext(source=source, mentions=()),
    )
    assert candidates[0].candidate_entity_id == "ent-rhys"
    assert candidates[0].features["exact_surface"] == 1.0


class FakeGLiNER:
    def extract_entities_long(self, text, labels, **kwargs):
        assert kwargs["include_spans"] is True
        assert kwargs["include_confidence"] is True
        return {
            "entities": {
                "person": [
                    {"text": "Rhys", "start": 0, "end": 4, "confidence": 0.91},
                    {"text": "Rhys", "start": 28, "end": 32, "confidence": 0.88},
                ],
                "location": [],
            }
        }


def test_gliner_adapter_is_testable_without_importing_heavy_dependency():
    source = normalized_source()
    lexer = GLiNER25SemanticLexer(revision="fixture-revision", model=FakeGLiNER())
    result = lexer.analyze(source)
    assert [mention.text for mention in result.mentions] == ["Rhys", "Rhys"]
    assert all(mention.entity_type is EntityType.CHARACTER for mention in result.mentions)
    assert result.run.model.model_id == "fastino/gliner2.5-base-v1"
    assert result.run.model.revision == "fixture-revision"
