from __future__ import annotations

from saga.agents.identity_seed_sanitizer import sanitize_identity_seed
from saga.domain.canon_normalization import CanonicalEntityNormalizer


def test_identity_seed_sanitizer_drops_low_support_malformed_rows() -> None:
    cleaned, alias_map, diagnostics = sanitize_identity_seed(
        character_rows=[
            {
                "id": "char_harry",
                "display_name": "Harry",
                "aliases": ["Harry", "Harry Potter"],
                "mention_count": 40,
                "risk_flags": [],
            },
            {
                "id": "char_noise",
                "display_name": "ANYTHING Harry",
                "aliases": ["ANYTHING Harry"],
                "mention_count": 5,
                "risk_flags": [],
            },
            {
                "id": "char_repeat",
                "display_name": "Harry Harry",
                "aliases": ["Harry Harry"],
                "mention_count": 7,
                "risk_flags": [],
            },
        ],
        non_character_entities=[],
        normalizer=CanonicalEntityNormalizer(),
    )

    names = [row["display_name"] for row in cleaned]
    assert "Harry Potter" in names
    assert "ANYTHING Harry" not in names
    assert "Harry Harry" not in names
    assert alias_map["Harry Potter"] == ["Harry Potter", "Harry"]
    assert len(diagnostics["suppressed_rows"]) >= 1


def test_identity_seed_sanitizer_drops_low_support_split_short_form() -> None:
    cleaned, _alias_map, _diagnostics = sanitize_identity_seed(
        character_rows=[
            {
                "id": "char_vernon",
                "display_name": "Vernon Dursley",
                "aliases": ["Vernon Dursley"],
                "mention_count": 30,
                "risk_flags": [],
            },
            {
                "id": "char_short",
                "display_name": "Dursley",
                "aliases": ["Dursley"],
                "mention_count": 3,
                "risk_flags": ["possible_split_cluster"],
            },
        ],
        non_character_entities=[],
        normalizer=CanonicalEntityNormalizer(),
    )

    names = [row["display_name"] for row in cleaned]
    assert "Vernon Dursley" in names
    assert "Dursley" not in names
