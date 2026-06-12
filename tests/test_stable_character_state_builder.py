from core.stable_character_state import StableCharacterStateBuilder


def test_stable_character_state_builder_promotes_profile_state_and_inferred_role():
    builder = StableCharacterStateBuilder()

    rows = builder.build(
        character_profiles=[
            {
                "canonical_name": "Azriel",
                "aliases": ["Az", "Azriel"],
                "core_description": "shadowsinger, wings of black armor",
                "traits": ["monitoring visits, strategist"],
                "state_at_latest": {
                    "physical_state": "wing bleeding",
                    "emotional_state": "aloof",
                },
                "relationship_refs": [],
                "important_history": [
                    {"summary": "Azriel presents maps and intelligence about Illyrian clan unrest."}
                ],
            }
        ],
        identity_result={"alias_map": {"Azriel": ["Azriel", "Az"]}},
        canon_snapshot=[],
        state_result={},
    )

    assert rows == [{"entity_name": "Azriel", "attributes": {"role": "shadowsinger"}}]


def test_stable_character_state_builder_uses_alias_title_and_relationship_inference():
    builder = StableCharacterStateBuilder()

    rows = builder.build(
        character_profiles=[
            {
                "canonical_name": "Elain Archeron",
                "aliases": ["Elain"],
                "core_description": "",
                "traits": [],
                "state_at_latest": {},
                "relationship_refs": [
                    {
                        "target_entity": "Lord Graysen",
                        "relationship": "former betrothed",
                        "change": "engagement ended",
                        "evidence": "Elain and Graysen discuss forced marriage before it is broken",
                    }
                ],
                "important_history": [],
            },
            {
                "canonical_name": "Tamlin",
                "aliases": ["Tamlin", "High Lord of Spring"],
                "core_description": "",
                "traits": [],
                "state_at_latest": {},
                "relationship_refs": [],
                "important_history": [],
            },
        ],
        identity_result={
            "alias_map": {
                "Elain Archeron": ["Elain Archeron", "Elain"],
                "Tamlin": ["Tamlin", "High Lord of Spring"],
            }
        },
        canon_snapshot=[],
        state_result={},
    )

    by_name = {row["entity_name"]: row["attributes"] for row in rows}
    assert by_name["Elain Archeron"]["relationship_status"] == "former betrothed to Lord Graysen"
    assert by_name["Tamlin"] == {"title": "High Lord", "court": "Spring Court"}
