from core.query.divergence_planning_service import DivergencePlanningService
from core.query.event_context_service import EventContextService

from tests.test_core_artifact_bundle import build_sample_artifact_bundle


def test_event_context_service_builds_grounded_context_packet():
    bundle = build_sample_artifact_bundle()
    service = EventContextService(bundle)

    context = service.build_event_context("canon_evt_2")

    assert context["event"]["ledger_event_id"] == "canon_evt_2"
    assert any(item["canonical_name"] == "Harry Potter" for item in context["participant_profiles"])
    assert any(item.get("entity_type") == "location" for item in context["related_entity_profiles"])


def test_divergence_planning_service_marks_downstream_dependencies():
    bundle = build_sample_artifact_bundle()
    service = DivergencePlanningService(bundle)

    workspace = service.plan_divergence(
        "canon_evt_1",
        "Harry and Hermione begin growing closer romantically after the battle.",
    )

    assert workspace["divergence_event_id"] == "canon_evt_1"
    assert "canon_evt_2" in workspace["invalidated_events"]
    assert workspace["unstable_downstream_facts"]
    assert workspace["unstable_downstream_facts"][0]["status"] == "invalidated"
    assert workspace["unstable_downstream_facts"][0]["depth"] == 1
    assert workspace["unstable_downstream_facts"][0]["stakes"]
    assert any("Harry Potter state at divergence" in item for item in workspace["required_continuity_constraints"])
    assert any("Locked precondition:" in item or "Divergence stake:" in item for item in workspace["required_continuity_constraints"])
    assert workspace["target_arcs"]
