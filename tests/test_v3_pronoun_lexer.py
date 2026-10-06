import hashlib

import pytest

from packages.narrative_compiler.adapters.pronouns import EnglishCharacterPronounLexer
from packages.narrative_compiler.source import NormalizedSource


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


def test_plus_plural_emits_grounded_personal_pronouns_without_neuter_it():
    source = source_for("She told them, 'I saw it with your brother.'")
    result = EnglishCharacterPronounLexer(profile="plus_plural").analyze(source)

    assert [(m.text, m.evidence.span.start_offset, m.evidence.span.end_offset) for m in result.mentions] == [
        ("She", 0, 3),
        ("them", 9, 13),
        ("I", 16, 17),
        ("your", 30, 34),
    ]
    assert all(m.confidence is None for m in result.mentions)
    assert all(m.attributes["mention_kind"] == "pronoun" for m in result.mentions)
    assert all(m.attributes["pronoun_profile"] == "plus_plural" for m in result.mentions)


def test_plus_neuter_adds_it_family():
    source = source_for("It guarded its cub itself.")
    strict = EnglishCharacterPronounLexer(profile="plus_plural").analyze(source)
    neuter = EnglishCharacterPronounLexer(profile="plus_neuter").analyze(source)

    assert strict.mentions == ()
    assert [m.text for m in neuter.mentions] == ["It", "its", "itself"]


def test_strict_excludes_ambiguous_plural_they_family():
    source = source_for("They told her that their work was ours.")
    result = EnglishCharacterPronounLexer(profile="strict").analyze(source)

    assert [m.text for m in result.mentions] == ["her", "ours"]


def test_profile_changes_artifact_identity():
    source = source_for("She saw them.")
    strict = EnglishCharacterPronounLexer(profile="strict").analyze(source)
    plural = EnglishCharacterPronounLexer(profile="plus_plural").analyze(source)

    assert strict.run.artifact_fingerprint != plural.run.artifact_fingerprint
    assert strict.run.config_fingerprint != plural.run.config_fingerprint


def test_invalid_profile_is_rejected():
    with pytest.raises(ValueError, match="unsupported pronoun profile"):
        EnglishCharacterPronounLexer(profile="unknown")
