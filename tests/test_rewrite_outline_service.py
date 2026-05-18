from core.query.rewrite_outline_service import RewriteOutlineService

from tests.test_core_artifact_bundle import build_sample_artifact_bundle


def test_rewrite_outline_service_builds_grounded_beats():
    bundle = build_sample_artifact_bundle()
    service = RewriteOutlineService(bundle)

    outline = service.build_outline(
        divergence_event_id="canon_evt_1",
        divergence_statement="Harry and Hermione begin growing closer romantically after the battle.",
        anchor_event_id="canon_evt_2",
        involved_characters=["Harry Potter", "Hermione Granger"],
        max_beats=4,
    )

    beats = outline["beats"]
    assert len(beats) >= 2
    assert beats[0]["beat_id"] == "beat_1"
    assert "Immediately after" in beats[0]["summary"]
    assert beats[0]["based_on_locked_facts"] == ["canon_evt_2"]
    assert beats[0]["relationship_movement"] == "relationship deepening"
    assert beats[0]["continuity_notes"]
    assert any("canon_evt_2" in beat["based_on_locked_facts"] for beat in beats[1:])
