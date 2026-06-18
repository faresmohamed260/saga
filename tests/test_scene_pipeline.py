from saga.agents.scene_extractor import SceneExtractor
from saga.domain.entities.character_profile_service import CharacterProfileService
from saga.retrieval.story_index_service import StoryIndexService
from saga.domain.timeline.event_ledger_service import EventLedgerService
from saga.domain.timeline.timeline_service import TimelineService
from saga.domain.timeline.character_timeline_service import CharacterTimelineService


def build_sample_chapter():
    paragraphs = []
    for index in range(1, 25):
        paragraphs.append(
            f"Paragraph {index}. Feyre moves through the forest and thinks about the hunt. "
            f"She watches the snow and tracks the wolf through the trees for several moments. "
            f"The winter air cuts at her face while she studies every footprint in the brush."
        )

    return {
        "book_index": 1,
        "chapter_index": 1,
        "chapter_title": "Chapter 1",
        "content": "\n\n".join(paragraphs),
        "source_file": "sample.epub",
    }


def build_short_chapter(chapter_index: int, text: str):
    return {
        "book_index": 1,
        "chapter_index": chapter_index,
        "chapter_title": f"Chapter {chapter_index}",
        "content": text,
        "source_file": "sample.epub",
    }


def build_sample_scene_analyses():
    return [
        {
            "book_index": 1,
            "chapter_index": 1,
            "scene_index": 1,
            "length": 220,
            "text": "Feyre enters the forest and tracks a wolf.",
            "scene_summary": "Feyre hunts in the forest.",
            "events": [
                {
                    "event_id": "evt_1",
                    "description": "Feyre enters the forest to hunt.",
                    "characters": ["Feyre"],
                    "type": "movement",
                },
                {
                    "event_id": "evt_2",
                    "description": "Feyre tracks the wolf through the snow.",
                    "characters": ["Feyre", "Wolf"],
                    "type": "action",
                },
            ],
        },
        {
            "book_index": 1,
            "chapter_index": 2,
            "scene_index": 1,
            "length": 210,
            "text": "Feyre goes under the mountain to save Tamlin.",
            "scene_summary": "Feyre travels under the mountain to save Tamlin.",
            "events": [
                {
                    "event_id": "evt_1",
                    "description": "Feyre goes under the mountain to save Tamlin.",
                    "characters": ["Feyre", "Tamlin"],
                    "type": "movement",
                }
            ],
        },
    ]


def test_scene_size_presets():
    chapter = build_sample_chapter()

    chapter_mode = SceneExtractor.from_target_words(0).extract(chapter)
    medium_mode = SceneExtractor.from_target_words(300).extract(chapter)

    assert len(chapter_mode) == 1
    assert chapter_mode[0]["target_words"] == 0
    assert len(medium_mode) > 1
    assert all(item["target_words"] == 300 for item in medium_mode)


def test_chapter_mode_batches_short_adjacent_chapters():
    extractor = SceneExtractor.from_target_words(0)
    chapters = [
        build_short_chapter(1, "Feyre hunts in snow. " * 40),
        build_short_chapter(2, "Tamlin waits in silence. " * 35),
        build_short_chapter(3, "Lucien watches closely. " * 34),
    ]
    batched = extractor.extract_many(chapters, allow_cross_chapter=True)
    assert len(batched) == 1
    assert batched[0]["source_chapter_indices"] == [1, 2, 3]
    assert batched[0]["chapter_index"] == 1
    assert batched[0]["end_chapter_index"] == 3


def test_story_index_search():
    scene_analyses = build_sample_scene_analyses()
    timeline = TimelineService().build_from_scene_analyses(scene_analyses)
    character_timelines = CharacterTimelineService().build(timeline)
    event_ledger = EventLedgerService().build(scene_analyses, timeline, {})
    character_profiles = CharacterProfileService().build(
        character_timelines,
        entity_registry=[],
        state_result={"latest_state": []},
        identity_result={"alias_map": {"Feyre": ["Feyre"], "Tamlin": ["Tamlin"]}},
        scene_analyses=scene_analyses,
    )

    index = StoryIndexService()
    result = index.build(
        scene_analyses=scene_analyses,
        timeline=timeline,
        event_ledger=event_ledger,
        character_timelines=character_timelines,
        character_profiles=character_profiles,
    )

    assert result["document_count"] >= 4

    matches = index.query("Feyre was going under the mountain to save Tamlin", min_similarity=0.05, max_results=5)
    assert matches
    assert any("Tamlin" in item["summary"] or "Tamlin" in item["text"] for item in matches)


def test_event_ledger_and_character_profiles_build():
    scene_analyses = build_sample_scene_analyses()
    timeline = TimelineService().build_from_scene_analyses(scene_analyses)
    character_timelines = CharacterTimelineService().build(timeline)

    event_ledger = EventLedgerService().build(scene_analyses, timeline, {})
    character_profiles = CharacterProfileService().build(
        character_timelines,
        entity_registry=[],
        state_result={"latest_state": []},
        identity_result={"alias_map": {"Feyre": ["Feyre", "the huntress"], "Tamlin": ["Tamlin"]}},
        scene_analyses=scene_analyses,
    )

    assert event_ledger[0]["ledger_event_id"] == "canon_evt_1"
    assert any(item["canonical_name"] == "Feyre" for item in character_profiles)
