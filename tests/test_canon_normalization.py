from core.canon_normalization import CanonicalEntityNormalizer


def test_expand_short_character_name_leading_substring_match():
    normalizer = CanonicalEntityNormalizer()

    assert normalizer.expand_short_character_name("Mor", ["Morrigan", "Feyre"]) == "Morrigan"
    assert normalizer.expand_short_character_name("Rhys", ["Rhysand", "Feyre", "Nesta"]) == "Rhysand"
    assert normalizer.expand_short_character_name("Tam", ["Tamlin", "Tara"]) == "Tamlin"
    assert normalizer.expand_short_character_name("Nes", ["Nesta Archeron"]) == "Nesta Archeron"
    assert normalizer.expand_short_character_name("Mo", ["Morrigan"]) == ""
    assert normalizer.expand_short_character_name("Mor", ["Morrigan", "Mordecai"]) == ""
    assert normalizer.expand_short_character_name("Feyre", ["Feyre Archeron"]) == "Feyre Archeron"


def test_canonicalize_candidate_name_strips_i_artifacts():
    normalizer = CanonicalEntityNormalizer()

    assert normalizer.canonicalize_candidate_name("I. Nesta") == "Nesta"
    assert normalizer.canonicalize_candidate_name("I. Rhys") == "Rhys"
    assert normalizer.canonicalize_candidate_name("I. Get") == ""
    assert normalizer.canonicalize_candidate_name("I Feyre") == "Feyre"
    assert normalizer.canonicalize_candidate_name("J. Smith") == "J. Smith"


def test_looks_like_character_name_rejects_structural_non_names():
    normalizer = CanonicalEntityNormalizer()

    assert normalizer.looks_like_character_name("Their Highnesses") is False
    assert normalizer.looks_like_character_name("Your Grace") is False
    assert normalizer.looks_like_character_name("Level Five") is False
    assert normalizer.looks_like_character_name("Chapter Three") is False
    assert normalizer.looks_like_character_name("Feyre Archeron") is True
    assert normalizer.looks_like_character_name("Rhysand") is True
    assert normalizer.looks_like_character_name("Nesta Archeron") is True
    assert normalizer.looks_like_character_name("High Lord") is False


def test_normalized_entity_key_strips_titles_and_is_idempotent():
    normalizer = CanonicalEntityNormalizer()

    assert normalizer.normalized_entity_key("Mrs. Laurent") == normalizer.normalized_entity_key("Laurent")
    assert normalizer.normalized_entity_key("Professor Snape") == normalizer.normalized_entity_key("Snape")
    assert normalizer.normalized_entity_key("Feyre Archeron") != normalizer.normalized_entity_key("Feyre")
    assert normalizer.normalized_entity_key("Mrs. Laurent") == normalizer.normalized_entity_key("Mrs. Laurent")
