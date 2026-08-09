from __future__ import annotations

from packages.character_world_modeling.contracts import (
    CharacterProfileArtifact,
    CharacterWorldModelingResult,
    StableCharacterStateArtifact,
    WorldStateArtifact,
)
from packages.character_world_modeling.quality import evaluate_character_world_quality


def test_character_world_quality_metrics_detect_grounding_and_world_usefulness():
    result = CharacterWorldModelingResult(
        series_id="series-1",
        character_profiles=[
            CharacterProfileArtifact(
                profile_id="profile-taryn",
                series_id="series-1",
                character_id="char-taryn",
                canonical_name="Taryn",
                overview="Taryn sends a note to Locke.",
                first_seen_summary="Fairy tales have a moral.",
                latest_state_summary="Taryn sends a note to Locke.",
                important_event_ids=["event-1"],
                notable_relationships=["romantic with char-locke"],
            ),
            CharacterProfileArtifact(
                profile_id="profile-heather",
                series_id="series-1",
                character_id="char-heather",
                canonical_name="Heather",
                overview="Heather appears in the source, but current canon evidence has no primary grounded actions for this character.",
            ),
        ],
        stable_character_states=[
            StableCharacterStateArtifact(
                stable_state_id="state-taryn",
                series_id="series-1",
                character_id="char-taryn",
                canonical_name="Taryn",
                stable_attributes={"role": "mortal"},
                supporting_event_ids=[],
            )
        ],
        world_states=[
            WorldStateArtifact(
                world_state_id="world-folk",
                series_id="series-1",
                entity_id="entity-folk",
                canonical_name="Folk",
                entity_type="organization",
                description="The Folk are faeries.",
                current_state_summary="The Folk are present in Faerie.",
            ),
            WorldStateArtifact(
                world_state_id="world-the-folk",
                series_id="series-1",
                entity_id="entity-the-folk",
                canonical_name="the Folk",
                entity_type="organization",
                description="The Folk are faeries.",
            ),
            WorldStateArtifact(
                world_state_id="world-thing",
                series_id="series-1",
                entity_id="entity-thing",
                canonical_name="thing",
                entity_type="object",
            ),
        ],
    )

    metrics = evaluate_character_world_quality(result)

    assert metrics.profile_grounding_rate == 1.0
    assert metrics.unsupported_profile_claim_rate > 0.0
    assert metrics.stable_attribute_precision == 1.0
    assert metrics.relationship_support_rate == 1.0
    assert metrics.entity_deduplication_rate < 1.0
    assert metrics.useful_entity_rate < 1.0
    assert metrics.unsupported_world_fact_rate == 0.0
    assert metrics.details["duplicate_entity_names"] == ["folk"]


def test_character_world_quality_accepts_title_derived_stable_attributes():
    result = CharacterWorldModelingResult(
        series_id="series-1",
        stable_character_states=[
            StableCharacterStateArtifact(
                stable_state_id="state-rhyia",
                series_id="series-1",
                character_id="char-princess-rhyia",
                canonical_name="Princess Rhyia",
                stable_attributes={"role": "royal"},
                supporting_event_ids=[],
            ),
            StableCharacterStateArtifact(
                stable_state_id="state-bogdana",
                series_id="series-1",
                character_id="char-bogdana",
                canonical_name="Bogdana",
                stable_attributes={"role": "royal"},
                supporting_event_ids=[],
            ),
        ],
    )

    metrics = evaluate_character_world_quality(result)

    assert metrics.stable_attribute_precision == 0.5
    assert metrics.details["unsupported_stable_attributes"] == [
        {"character_id": "char-bogdana", "key": "role", "value": "royal"}
    ]


def test_character_world_quality_accepts_explicit_scene_support():
    result = CharacterWorldModelingResult(
        series_id="series-1",
        stable_character_states=[
            StableCharacterStateArtifact(
                stable_state_id="state-mikkel",
                series_id="series-1",
                character_id="char-mikkel",
                canonical_name="Mikkel",
                stable_attributes={"role": "Living Council member"},
                supporting_scene_ids=["scene-1"],
            )
        ],
        world_states=[
            WorldStateArtifact(
                world_state_id="world-guards",
                series_id="series-1",
                entity_id="entity-guards",
                canonical_name="Ghost's guards",
                entity_type="organization",
                active_conditions=["Present and preventing sneaking past them."],
                scene_ids=["scene-1"],
            )
        ],
    )

    metrics = evaluate_character_world_quality(result)

    assert metrics.stable_attribute_precision == 1.0
    assert metrics.unsupported_world_fact_rate == 0.0
