from core.trait_taxonomy import (
    ENTITY_TYPES,
    DYNAMIC_TRAITS,
    PERSISTENT_TRAITS,
    TYPED_ATTRIBUTE_KEYS,
    group_traits_for_entity,
    typed_attribute_rows,
    validate_trait_taxonomy,
)


def test_trait_taxonomy_is_structurally_valid():
    assert validate_trait_taxonomy() == []


def test_all_entity_types_have_persistent_and_dynamic_traits():
    for entity_type in ENTITY_TYPES:
        assert entity_type in PERSISTENT_TRAITS
        assert entity_type in DYNAMIC_TRAITS
        assert entity_type in TYPED_ATTRIBUTE_KEYS
        assert group_traits_for_entity(entity_type, scope="persistent")
        assert group_traits_for_entity(entity_type, scope="dynamic")


def test_typed_attribute_rows_cover_all_current_pipeline_keys():
    rows = typed_attribute_rows()
    seen = {(row["entity_type"], row["typed_attribute_key"]) for row in rows}
    expected = {
        (entity_type, key)
        for entity_type, keys in TYPED_ATTRIBUTE_KEYS.items()
        for key in keys
    }
    assert seen == expected
