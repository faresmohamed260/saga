from __future__ import annotations

from pathlib import Path

import pytest

from packages.analysis_foundation import AnalysisFoundationRuntime, CanonicalIdentityBundle, SceneSegmentationAgent
from packages.analysis_foundation.contracts import ChapterArtifact, SceneArtifact
from packages.analysis_foundation.pipeline import (
    _build_narrator_reference,
    _epub_document_title,
    _is_epub_terminal_document,
    _select_character_display_name,
    _should_include_epub_document,
    _split_paragraphs,
)
from packages.analysis_foundation.contracts import CanonicalCharacter
from packages.analysis_foundation.narrative_grounding import (
    ground_scene_narration,
    narrative_grounding_summary,
    split_narration_and_dialogue,
)
from packages.analysis_foundation.store import AnalysisFoundationStore
from packages.identity_runtime.contracts import IdentityRuntimeResult
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client


class StubIdentityRuntime:
    def provider_name(self) -> str:
        return "modal_xcore_litbank"

    def analyze_chapters(self, *, chapters: list[dict], use_chunking: bool | None = None) -> IdentityRuntimeResult:
        del use_chunking
        assert chapters
        return IdentityRuntimeResult.model_validate(
            {
                "provider_name": "modal_xcore_litbank",
                "app_name": "saga-coref-runtime",
                "model_name": "xcore-litbank",
                "runtime_seconds": 1.23,
                "chunk_count": 1,
                "input_stats": {"chapter_count": len(chapters)},
                "clusters": [
                    {
                        "cluster_id": 1,
                        "display_name": "Fares",
                        "aliases": [],
                        "mentions": ["Fares", "He"],
                        "mention_count": 2,
                        "proper_mentions": ["Fares"],
                        "pronoun_mentions": ["He"],
                    },
                    {
                        "cluster_id": 2,
                        "display_name": "Kareem",
                        "aliases": [],
                        "mentions": ["Kareem", "Kareem"],
                        "mention_count": 2,
                        "proper_mentions": ["Kareem"],
                        "pronoun_mentions": [],
                    },
                ],
                "raw_payload": {},
            }
        )


def _persistence(tmp_path: Path):
    profile = PersistenceProfile(
        name="analysis-foundation-test",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite:///{tmp_path / 'analysis_foundation.sqlite3'}",
        local_storage_root_dir=str(tmp_path / "storage"),
        application_name="analysis-foundation-test",
    )
    client = create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(profile=profile))
    client.initialize()
    return client


def test_scene_segmentation_is_deterministic(tmp_path: Path):
    store = AnalysisFoundationStore(_persistence(tmp_path))
    chapter = store.upsert_chapter(
        ChapterArtifact(
            chapter_id="book-1-chapter-001",
            series_id="series-1",
            book_id="book-1",
            chapter_index=1,
            title="Chapter 1",
            content=(
                "Fares greeted Kareem in the hallway and asked about the project.\n\n"
                "Kareem answered calmly and pointed to the whiteboard where the deadline was written.\n\n"
                "The project leader nodded and told them to begin the review immediately.\n\n"
                "Hours later they returned with notes, corrections, and a clear plan for the next milestone."
            ),
            source_id="source-1",
            word_count=48,
        )
    )
    agent = SceneSegmentationAgent(store=store, target_words=16)
    first = agent.run(book_ids=[chapter.book_id])
    second = agent.run(book_ids=[chapter.book_id])
    assert first == second
    assert [row["scene_index"] for row in first["scenes"]] == [1]
    assert "Fares greeted Kareem" in first["scenes"][0]["summary"]


def test_split_paragraphs_accepts_single_newline_epub_style_blocks():
    text = "First paragraph line.\nSecond paragraph line.\nThird paragraph line.\nFourth paragraph line.\nFifth paragraph line."
    paragraphs = _split_paragraphs(text)

    assert len(paragraphs) == 5
    assert paragraphs[0] == "First paragraph line."
    assert paragraphs[-1] == "Fifth paragraph line."


def test_analysis_foundation_persists_books_chapters_scenes_and_identity(tmp_path: Path):
    client = _persistence(tmp_path)
    source_path = tmp_path / "mini_story.txt"
    source_path.write_text(
        "Chapter 1\n\nFares greeted Kareem.\n\nHe smiled at Kareem.\n\n"
        "Chapter 2\n\nThe project leader nodded.\n\nKareem opened the notebook.",
        encoding="utf-8",
    )
    runtime = AnalysisFoundationRuntime(
        persistence=client,
        identity_runtime=StubIdentityRuntime(),
        allow_in_memory_checkpointer=True,
    )
    result = runtime.invoke(series_id="series-1", source_paths=[str(source_path)], thread_id="analysis-test")
    assert result.books and result.chapters and result.scenes
    assert result.identity_bundle is not None
    assert result.identity_bundle.provider_name == "modal_xcore_litbank"
    assert result.identity_bundle.alias_map["Fares"] == "char-fares"
    stored_identity = client.identity.get_identity_series("series-1")
    assert stored_identity is not None
    assert stored_identity["provider_name"] == "modal_xcore_litbank"
    persisted_chapters = client.library.list_records(record_type="chapter", book_id=result.books[0].book_id, limit=50)
    assert len(persisted_chapters) == 2
    persisted_scenes = client.library.list_scenes(book_id=result.books[0].book_id, limit=50)
    assert persisted_scenes


def test_analysis_foundation_returns_identity_bundle_contract(tmp_path: Path):
    client = _persistence(tmp_path)
    source_path = tmp_path / "fixture.txt"
    source_path.write_text("Fares greeted Kareem.\n\nHe smiled at Kareem.\n\nThe project leader nodded.", encoding="utf-8")
    runtime = AnalysisFoundationRuntime(
        persistence=client,
        identity_runtime=StubIdentityRuntime(),
        allow_in_memory_checkpointer=True,
    )
    result = runtime.invoke(series_id="series-2", source_paths=[str(source_path)], thread_id="identity-contract")
    bundle = CanonicalIdentityBundle.model_validate(result.identity_bundle.model_dump())
    assert bundle.characters[0].display_name == "Fares"
    assert bundle.narrator.perspective in {"first_person", "third_person"}
    assert result.run_metadata["stage_order"] == ["ingestion", "scene_segmentation", "identity", "narrative_grounding"]
    assert result.run_metadata["stage_timings_seconds"]["identity"] >= 0.0
    assert result.run_metadata["stage_timings_seconds"]["narrative_grounding"] >= 0.0


def test_analysis_foundation_persists_scene_narrative_grounding(tmp_path: Path):
    class FirstPersonIdentityRuntime:
        def provider_name(self) -> str:
            return "modal_xcore_litbank"

        def analyze_chapters(self, *, chapters: list[dict], use_chunking: bool | None = None) -> IdentityRuntimeResult:
            del chapters, use_chunking
            return IdentityRuntimeResult.model_validate(
                {
                    "provider_name": "modal_xcore_litbank",
                    "app_name": "saga-coref-runtime",
                    "model_name": "xcore-litbank",
                    "runtime_seconds": 1.0,
                    "chunk_count": 1,
                    "input_stats": {"chapter_count": 1},
                    "clusters": [
                        {
                            "cluster_id": 1,
                            "display_name": "Taryn",
                            "aliases": [],
                            "proper_mentions": ["Taryn"],
                            "pronoun_mentions": [],
                            "mention_count": 10,
                        },
                        {
                            "cluster_id": 2,
                            "display_name": "Jude",
                            "aliases": [],
                            "proper_mentions": ["Jude"],
                            "pronoun_mentions": [],
                            "mention_count": 8,
                        },
                        {
                            "cluster_id": 3,
                            "display_name": "Locke",
                            "aliases": [],
                            "proper_mentions": ["Locke"],
                            "pronoun_mentions": [],
                            "mention_count": 7,
                        },
                    ],
                    "raw_payload": {},
                }
            )

    client = _persistence(tmp_path)
    source_path = tmp_path / "first-person.txt"
    source_path.write_text(
        "Once upon a time, there was a girl named Taryn. I wrote back to Locke.\n\n"
        "You, Jude, would have known better, but I wanted to believe him.",
        encoding="utf-8",
    )
    runtime = AnalysisFoundationRuntime(
        persistence=client,
        identity_runtime=FirstPersonIdentityRuntime(),
        allow_in_memory_checkpointer=True,
    )
    result = runtime.invoke(series_id="series-grounding", source_paths=[str(source_path)], thread_id="grounding")

    assert result.scenes
    grounding = result.scenes[0].metadata["narrative_grounding"]
    assert grounding["narrator_character_id"] == "char-taryn"
    assert grounding["narrator_name"] == "Taryn"
    assert grounding["first_person_count"] >= 1
    assert "char-jude" in grounding["addressee_character_ids"]
    persisted_scene = client.library.list_scenes(book_id=result.books[0].book_id, limit=1)[0]
    assert persisted_scene["payload"]["narrative_grounding"]["narrator_character_id"] == "char-taryn"


def test_dialogue_pronouns_do_not_change_third_person_narrative_evidence():
    text = (
        "PART I The Tale of Evangeline Fox. Evangeline crossed the empty chapel. "
        "“I came because my parents are dead, and I need you to help me,” she said."
    )
    narration, dialogue = split_narration_and_dialogue(text)

    assert "I came" not in narration
    assert "I came" in dialogue
    bundle = CanonicalIdentityBundle.model_validate(
        {
            "series_id": "series-third-person",
            "provider_name": "modal_xcore_litbank",
            "narrator": {"perspective": "third_person"},
        }
    )
    scene = SceneArtifact(
        scene_id="scene-dialogue",
        book_id="book-1",
        chapter_index=1,
        scene_index=1,
        text=text,
        summary="Evangeline asks for help.",
    )

    grounding = ground_scene_narration(scenes=[scene], identity_bundle=bundle)[0]

    assert grounding.perspective == "third_person"
    assert grounding.first_person_count == 0
    assert grounding.dialogue_first_person_count == 4
    assert grounding.raw_first_person_count == 4
    summary = narrative_grounding_summary(
        [scene.model_copy(update={"metadata": {"narrative_grounding": grounding.model_dump()}})]
    )
    assert summary["first_person_perspective_scene_count"] == 0
    assert summary["third_person_perspective_scene_count"] == 1
    assert summary["narration_first_person_evidence_scene_count"] == 0
    assert summary["dialogue_first_person_evidence_scene_count"] == 1


def test_perspective_inference_uses_narration_instead_of_quoted_dialogue():
    chapter = ChapterArtifact(
        chapter_id="chapter-1",
        series_id="series-1",
        book_id="book-1",
        chapter_index=1,
        title="One",
        source_id="source-1",
        content=(
            "Evangeline walked home while she considered what he had told her. "
            "“I need my book. I know you have it. Give it to me,” Luc said."
        ),
    )

    narrator = _build_narrator_reference(
        [chapter],
        [CanonicalCharacter(character_id="char-e", display_name="Evangeline", mention_count=3)],
    )

    assert narrator.perspective == "third_person"
    assert narrator.first_person_pronoun_count == 0
    assert narrator.third_person_pronoun_count >= 3


def test_perspective_inference_preserves_genuine_first_person_narration():
    chapter = ChapterArtifact(
        chapter_id="chapter-1",
        series_id="series-1",
        book_id="book-1",
        chapter_index=1,
        title="One",
        source_id="source-1",
        content="I walked home with my book because I knew it was mine.",
    )

    narrator = _build_narrator_reference([chapter], [])

    assert narrator.perspective == "first_person"
    assert narrator.first_person_pronoun_count == 4


def test_addressee_grounding_requires_scene_local_identity_evidence():
    bundle = CanonicalIdentityBundle.model_validate(
        {
            "series_id": "series-addressee",
            "provider_name": "modal_xcore_litbank",
            "characters": [
                {"character_id": "char-jacks", "display_name": "Jacks"},
                {"character_id": "char-evangeline", "display_name": "Evangeline"},
            ],
            "narrator": {"perspective": "third_person"},
        }
    )
    scenes = [
        SceneArtifact(
            scene_id="scene-unknown",
            book_id="book-1",
            chapter_index=1,
            scene_index=1,
            text='“You should leave. You cannot stay here,” she said.',
            summary="An unnamed speaker issues a warning.",
        ),
        SceneArtifact(
            scene_id="scene-inferable",
            book_id="book-1",
            chapter_index=1,
            scene_index=2,
            text='“You need to leave now,” Evangeline whispered to Jacks.',
            summary="Evangeline warns Jacks.",
        ),
        SceneArtifact(
            scene_id="scene-speaker",
            book_id="book-1",
            chapter_index=1,
            scene_index=3,
            text='“Why are you nervous?” asked Evangeline.',
            summary="Evangeline asks an unnamed listener.",
        ),
    ]

    groundings = ground_scene_narration(scenes=scenes, identity_bundle=bundle)

    assert groundings[0].addressee_character_ids == []
    assert groundings[1].addressee_character_ids == ["char-jacks"]
    assert [item.kind for item in groundings[1].evidence_spans] == ["named_speech_recipient"]
    assert groundings[2].addressee_character_ids == []


def test_addressee_grounding_does_not_promote_identity_aliases_without_display_name_evidence():
    bundle = CanonicalIdentityBundle.model_validate(
        {
            "series_id": "series-alias",
            "provider_name": "modal_xcore_litbank",
            "characters": [
                {
                    "character_id": "char-knightlinger",
                    "display_name": "Mr. Knightlinger",
                    "aliases": ["Coward"],
                }
            ],
            "narrator": {"perspective": "third_person"},
        }
    )
    scene = SceneArtifact(
        scene_id="scene-alias",
        book_id="book-1",
        chapter_index=1,
        scene_index=1,
        text='“Coward,” she coughed.',
        summary="A generic insult is spoken.",
    )

    grounding = ground_scene_narration(scenes=[scene], identity_bundle=bundle)[0]

    assert grounding.addressee_character_ids == []


def test_epub_document_filters_frontmatter_and_titles_content():
    assert _should_include_epub_document(item_id="chapter001", file_name="chapter001.xhtml", text="A " * 100)
    assert not _should_include_epub_document(item_id="copyright", file_name="copyright.xhtml", text="copyright text")
    assert not _should_include_epub_document(item_id="cover", file_name="cover.xhtml", text="cover image", toc_title="Cover")
    assert _should_include_epub_document(item_id="chapter001", file_name="chapter001.xhtml", text="word " * 120, toc_title="Begin Reading")
    assert not _should_include_epub_document(item_id="x_f1", file_name="part0001.xhtml", text="hello world", toc_title="Title Page")
    assert _should_include_epub_document(
        item_id="x_f7",
        file_name="part0007.xhtml",
        text="word " * 120,
        toc_title="I. The King of Elfhame Visits the Mortal World",
    )
    assert not _should_include_epub_document(item_id="x_f6", file_name="part0006.xhtml", text="word " * 120, content_started=False)
    assert not _should_include_epub_document(
        item_id="appendix001",
        file_name="appendix001.xhtml",
        text="Continue reading for a sneak peek of the next book.",
        content_started=True,
    )
    assert _epub_document_title(
        item_id="chapter012",
        file_name="chapter012.xhtml",
        text="",
        ordinal=12,
    ) == "Chapter 12"
    assert _epub_document_title(
        item_id="appendix001",
        file_name="appendix001.xhtml",
        text="",
        ordinal=2,
    ) == "Appendix"
    assert _is_epub_terminal_document(
        item_id="appendix001",
        file_name="appendix001.xhtml",
        text="Continue reading for a sneak peek of the next book.",
        toc_title='A Sneak Peek of "The Wicked King"',
    )


def test_character_display_name_prefers_clean_mentions():
    raw = {
        "display_name": "a girl named Taryn",
        "proper_mentions": ["Taryn"],
        "aliases": ["my twin sister"],
    }
    assert _select_character_display_name(raw) == "Taryn"


def test_analysis_foundation_identity_review_filters_contaminated_aliases(tmp_path: Path):
    class ContaminatedIdentityRuntime:
        def provider_name(self) -> str:
            return "modal_xcore_litbank"

        def analyze_chapters(self, *, chapters: list[dict], use_chunking: bool | None = None) -> IdentityRuntimeResult:
            del chapters, use_chunking
            return IdentityRuntimeResult.model_validate(
                {
                    "provider_name": "modal_xcore_litbank",
                    "app_name": "saga-coref-runtime",
                    "model_name": "xcore-litbank",
                    "runtime_seconds": 2.34,
                    "chunk_count": 1,
                    "input_stats": {"chapter_count": 1},
                    "clusters": [
                        {
                            "cluster_id": 1,
                            "display_name": "Locke",
                            "aliases": ["the prince", "Madoc"],
                            "mentions": ["Locke", "the prince"],
                            "mention_count": 12,
                            "proper_mentions": ["Locke", "Madoc"],
                            "pronoun_mentions": ["he"],
                        },
                        {
                            "cluster_id": 2,
                            "display_name": "Prince Cardan",
                            "aliases": ["Locke", "the prince", "Cardan"],
                            "mentions": ["Prince Cardan", "Locke"],
                            "mention_count": 10,
                            "proper_mentions": ["Prince Cardan", "Locke", "Cardan"],
                            "pronoun_mentions": ["he"],
                        },
                        {
                            "cluster_id": 3,
                            "display_name": "my sister",
                            "aliases": [],
                            "mentions": ["my sister"],
                            "mention_count": 6,
                            "proper_mentions": [],
                            "pronoun_mentions": ["she", "her"],
                        },
                    ],
                    "raw_payload": {},
                }
            )

    client = _persistence(tmp_path)
    source_path = tmp_path / "contaminated.txt"
    source_path.write_text(
        "Chapter 1\n\nLocke confronted Prince Cardan in the hall.\n\n"
        "Cardan mocked Jude while her sister watched.\n",
        encoding="utf-8",
    )
    runtime = AnalysisFoundationRuntime(
        persistence=client,
        identity_runtime=ContaminatedIdentityRuntime(),
        allow_in_memory_checkpointer=True,
    )
    result = runtime.invoke(series_id="series-cleaned", source_paths=[str(source_path)], thread_id="identity-clean")
    assert result.identity_bundle is not None
    bundle = result.identity_bundle

    assert "my sister" not in [item.display_name for item in bundle.characters]
    prince = next(item for item in bundle.characters if item.display_name == "Prince Cardan")
    assert "Cardan" in prince.aliases
    assert "Locke" not in prince.aliases
    assert "the prince" not in prince.aliases
    assert bundle.source_stats["identity_dropped_cluster_count"] >= 1
    assert bundle.source_stats["identity_rejected_alias_count"] >= 2
    assert "cross_character_alias_rejected" in {
        item["code"] for item in list((bundle.metadata.get("identity_review") or {}).get("diagnostics") or [])
    }


def _has_real_xcore_env() -> bool:
    try:
        from packages.modal_runtime import load_modal_account_secrets

        return bool(load_modal_account_secrets("modal_xcore_litbank"))
    except Exception:
        return False


@pytest.mark.skipif(not _has_real_xcore_env(), reason="real Modal xcore provider is not configured")
def test_real_analysis_foundation_end_to_end_on_modal_xcore(tmp_path: Path):
    fixture = Path("backup/reference/legacy_system/tests/fixtures/litbank_mini/doc1.txt")
    client = _persistence(tmp_path)
    runtime = AnalysisFoundationRuntime(
        persistence=client,
        allow_in_memory_checkpointer=True,
    )
    result = runtime.invoke(series_id="series-real", source_paths=[str(fixture)], thread_id="real-analysis-foundation")
    assert result.identity_bundle is not None
    assert result.identity_bundle.provider_name == "modal_xcore_litbank"
    assert result.identity_bundle.characters
