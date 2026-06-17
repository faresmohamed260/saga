from saga.domain.query.rewrite_context_service import RewriteContextService

from tests.test_core_artifact_bundle import build_sample_artifact_bundle


def test_rewrite_context_service_collects_generation_packet():
    bundle = build_sample_artifact_bundle()
    service = RewriteContextService(bundle)

    context = service.build_rewrite_context(
        divergence_event_id="canon_evt_1",
        divergence_statement="Harry and Hermione begin growing closer romantically after the battle.",
        anchor_event_id="canon_evt_2",
        involved_characters=["Harry Potter", "Hermione Granger"],
    )

    assert context["divergence_workspace"]["invalidated_events"]
    assert context["anchor_event_context"]["event"]["ledger_event_id"] == "canon_evt_2"
    assert context["relevant_arcs"]
    assert context["continuity_constraints"]
