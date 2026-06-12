from entities.entity_registry_service import EntityRegistryService


def test_entity_registry_prefers_stable_trait_for_initial_physical_description():
    registry = EntityRegistryService().build(
        [
            {
                "book_index": 1,
                "chapter_index": 1,
                "scene_index": 1,
                "entities_present": [{"name": "Feyre", "entity_type": "character"}],
                "entity_descriptions": [
                    {
                        "entity_name": "Feyre",
                        "entity_type": "character",
                        "description": "slender young woman with pale hair and a worn hunter's bearing",
                        "description_type": "stable_trait",
                    },
                    {
                        "entity_name": "Feyre",
                        "entity_type": "character",
                        "description": "hands trembling from cold",
                        "description_type": "temporary_condition",
                    },
                ],
                "state_changes": [],
                "events": [],
                "relationship_changes": [],
            }
        ]
    )

    feyre = registry[0]
    assert feyre["initial_physical_description"]["status"] == "captured"
    assert "slender young woman" in feyre["initial_physical_description"]["description"]
    assert feyre["initial_physical_description"]["description_type"] == "stable_trait"
