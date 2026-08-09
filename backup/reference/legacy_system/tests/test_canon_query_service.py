from saga.domain.query.canon_query_service import CanonQueryService
from saga.domain.query.dependency_query_service import DependencyQueryService
from saga.retrieval.story_index_service import StoryIndexService

from tests.test_core_artifact_bundle import build_sample_artifact_bundle


def test_canon_query_service_returns_event_and_snapshots():
    bundle = build_sample_artifact_bundle()
    service = CanonQueryService(bundle)

    event = service.get_event("canon_evt_2")
    before = service.snapshot_before("canon_evt_2")
    after = service.snapshot_after("canon_evt_2")

    assert event["source_event_id"] == "evt_2"
    assert before["anchor_event_id"] == "canon_evt_1"
    assert after["anchor_event_id"] == "canon_evt_2"


def test_canon_query_service_returns_character_and_relationship_state_at_event():
    bundle = build_sample_artifact_bundle()
    service = CanonQueryService(bundle)

    harry = service.get_character_profile_at("char_harry_potter", "canon_evt_2")
    relationship = service.get_relationship_state_at("Harry Potter", "Hermione Granger", "canon_evt_2")

    assert harry["state_at_event"]["trust"] == "more open with Hermione"
    assert relationship["relationship_id"].startswith("rel_")
    assert len(relationship["change_log"]) == 2
    assert relationship["partial"] is True


def test_dependency_query_service_finds_downstream_events():
    bundle = build_sample_artifact_bundle()
    service = DependencyQueryService(bundle)

    downstream = service.get_downstream_dependencies("canon_evt_1")

    assert len(downstream) == 1
    assert downstream[0]["ledger_event_id"] == "canon_evt_2"


def test_story_index_can_build_from_artifact_bundle():
    bundle = build_sample_artifact_bundle()
    index = StoryIndexService()

    result = index.build(artifact_bundle=bundle)
    matches = index.query("Harry and Hermione grow closer after the battle", min_similarity=0.01, max_results=10)

    assert result["document_count"] >= 8
    assert any(item["item_type"] == "relationship_profile" for item in matches)
