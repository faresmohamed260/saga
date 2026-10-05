from packages.narrative_compiler.adapters.static import StaticSemanticLexer
from packages.narrative_compiler.compiler import NarrativeCompilerV30
from packages.narrative_compiler.ir import EntityType, Mention, SourceSpan
from packages.narrative_compiler.linker import ExactSurfaceCharacterLinker
from packages.narrative_compiler.source import NormalizedSource


def source():
    text = "Rhys arrived. Rhys smiled."
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


def test_compiler_binds_linker_artifact_to_lexer_artifact():
    src = source()
    mentions = [
        Mention.create(
            source_fingerprint=src.source_fingerprint,
            source_unit_key="chapter:0",
            span=SourceSpan(0, 4),
            entity_type=EntityType.CHARACTER,
            text="Rhys",
        ),
        Mention.create(
            source_fingerprint=src.source_fingerprint,
            source_unit_key="chapter:0",
            span=SourceSpan(14, 18),
            entity_type=EntityType.CHARACTER,
            text="Rhys",
        ),
    ]
    compiler = NarrativeCompilerV30(
        lexer=StaticSemanticLexer(mentions),
        linker=ExactSurfaceCharacterLinker(),
    )
    first = compiler.compile_identity(src)
    second = compiler.compile_identity(src)
    assert first.lexer.run.artifact_fingerprint == second.lexer.run.artifact_fingerprint
    assert first.linker.run.artifact_fingerprint == second.linker.run.artifact_fingerprint
    assert first.lexer.run.artifact_fingerprint != first.linker.run.artifact_fingerprint


def test_linker_artifact_changes_when_upstream_lexer_artifact_changes():
    src = source()
    one = Mention.create(
        source_fingerprint=src.source_fingerprint,
        source_unit_key="chapter:0",
        span=SourceSpan(0, 4),
        entity_type=EntityType.CHARACTER,
        text="Rhys",
    )
    two = Mention.create(
        source_fingerprint=src.source_fingerprint,
        source_unit_key="chapter:0",
        span=SourceSpan(14, 18),
        entity_type=EntityType.CHARACTER,
        text="Rhys",
    )
    linker = ExactSurfaceCharacterLinker()
    a = NarrativeCompilerV30(lexer=StaticSemanticLexer([one]), linker=linker).compile_identity(src)
    b = NarrativeCompilerV30(lexer=StaticSemanticLexer([one, two]), linker=linker).compile_identity(src)
    assert a.lexer.run.artifact_fingerprint != b.lexer.run.artifact_fingerprint
    assert a.linker.run.artifact_fingerprint != b.linker.run.artifact_fingerprint
