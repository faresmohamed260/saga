from packages.retrieval_runtime import RetrievalProfile, RetrievalRuntimeConfig, create_retrieval_client
from saga.retrieval.hybrid_narrative_retriever import HybridNarrativeRetriever


def _fake_embedder(texts):
    vectors = []
    for text in texts:
        lowered = str(text).lower()
        vectors.append([
            float(lowered.count("elain")),
            float(lowered.count("azriel")),
            float(lowered.count("lucien")),
            float(lowered.count("koschei")),
            float(lowered.count("politic")),
        ])
    return vectors


def _retrieval_context():
    return {
        "meta": {
            "series_id": "acotar",
            "book_title": "A Court of Silver Flames.epub",
            "matched_book_titles": ["A Court of Silver Flames.epub"],
        },
        "character_states": [
            {
                "name": "Elain Archeron",
                "descriptions": ["quiet, observant, emotionally withdrawn"],
                "canon_state": {"role": "Archeron sister"},
                "state_transitions": [{"attribute": "power_status", "new_state": "visions intensifying"}],
                "aliases": ["Elain"],
            },
            {
                "name": "Azriel",
                "descriptions": ["shadow-singer, emotionally repressed"],
                "canon_state": {"role": "spymaster"},
                "state_transitions": [{"attribute": "self_worth", "new_state": "wavering"}],
                "aliases": [],
            },
            {
                "name": "Lucien",
                "descriptions": ["loyal but lonely"],
                "canon_state": {"role": "court emissary"},
                "state_transitions": [{"attribute": "mate_status", "new_state": "rejected bond"}],
                "aliases": [],
            },
        ],
        "relationship_summary": [
            {"entity_a": "Elain Archeron", "entity_b": "Azriel", "relationship_type": "romance", "latest_change": "forbidden tension"},
            {"entity_a": "Elain Archeron", "entity_b": "Lucien", "relationship_type": "bond", "latest_change": "bond strain"},
            {"entity_a": "Lucien", "entity_b": "Helion", "relationship_type": "family", "latest_change": "political leverage"},
        ],
        "unresolved_threads": [
            {"event_id": "thread-1", "event_description": "Koschei seeks a gate through Elain's visions.", "decision_made": "", "alternatives": [], "divergence_potential": 9},
            {"event_id": "thread-2", "event_description": "Autumn Court instability threatens Lucien's political position.", "decision_made": "", "alternatives": [], "divergence_potential": 7},
        ],
        "causal_chains": [
            {"chain_id": "chain-1", "description": "Koschei manipulates dreams to widen political instability.", "story_function": "escalation", "events": [{"description": "Elain sees a burning lake."}]},
        ],
        "retrieval_documents": [
            {
                "document_id": "scene:1",
                "source_type": "scene",
                "summary": "Elain quietly endures another prophetic vision in the garden.",
                "text": "Elain vision garden Koschei",
                "metadata": {"series_id": "acotar", "book_title": "A Court of Silver Flames.epub", "book_index": 5, "chapter_index": 80, "scene_index": 1, "characters": ["Elain Archeron"]},
            },
            {
                "document_id": "event:1",
                "source_type": "event",
                "summary": "Azriel investigates strange activity near the human border.",
                "text": "Azriel investigates human border political threat",
                "metadata": {"series_id": "acotar", "book_title": "A Court of Silver Flames.epub", "book_index": 5, "chapter_index": 80, "time_index": 3, "characters": ["Azriel"]},
            },
            {
                "document_id": "trajectory:lucien",
                "source_type": "trajectory",
                "summary": "Lucien trajectory",
                "text": "Lucien lonely political day court autumn court",
                "metadata": {"series_id": "acotar", "book_title": "A Court of Silver Flames.epub", "characters": ["Lucien"]},
            },
        ],
    }


def _index_service(tmp_path):
    profile = RetrievalProfile(
        name="test_runtime",
        mode="document_index",
        base_dir=str(tmp_path),
        embedding_model="test-embedder",
        ollama_embed_url="http://localhost:11434/api/embed",
        batch_size=24,
    )
    return create_retrieval_client(
        config=RetrievalRuntimeConfig(profile=profile),
        profile=profile,
        embedder=_fake_embedder,
    )


def test_hybrid_embedding_index_service_persists_and_queries_scoped_results(tmp_path):
    service = _index_service(tmp_path)
    docs = _retrieval_context()["retrieval_documents"]

    payload = service.ensure_document_index(series_id="acotar", scope_key="acosf", documents=docs)
    again = service.ensure_document_index(series_id="acotar", scope_key="acosf", documents=docs)
    results = service.query_documents(
        index_ref={
            "index_id": again["index_id"],
            "series_id": again["series_id"],
            "scope_key": again["scope_key"],
            "fingerprint": again["fingerprint"],
        },
        query_text="Elain experiences a violent vision from Koschei.",
        top_k=2,
        allowed_types={"scene", "event"},
        character_bias=["Elain Archeron"],
    )

    assert payload["fingerprint"] == again["fingerprint"]
    assert results[0]["document_id"] == "scene:1"


def test_hybrid_retriever_builds_monologue_scene_packet_with_narrow_focus(tmp_path):
    retriever = HybridNarrativeRetriever(index_service=_index_service(tmp_path))
    retrieval = _retrieval_context()

    packet = retriever.build_scene_context_packet(
        retrieval_context=retrieval,
        compiled_context={"generation_controls": {"canon_elements_to_preserve": [{"description": "Koschei remains imprisoned but influential"}]}},
        scene_outline={
            "scene_number": 1,
            "summary": "Elain reflects alone on a brutal vision of Koschei.",
            "characters_present": ["Elain Archeron"],
            "purpose": "Internal monologue about the threat.",
            "ends_on": "She realizes the vision is a warning.",
        },
        chapter_outline={"chapter_number": 1, "pov_character": "Elain Archeron"},
        world_state={"characters": [], "relationships": [], "active_threads": [], "events_so_far": []},
        scene_memory={"scene_count_completed": 0},
        previous_scene_ending="The garden fell silent.",
        chapter_controls={"assigned_plot_beats": ["Elain begins experiencing increasingly violent prophetic visions connected to Koschei."]},
    )

    assert packet["query_summary"]["scene_type"] == "internal_monologue"
    assert packet["pov_character_packet"]["name"] == "Elain Archeron"
    assert packet["retrieved_memories"][0]["document_id"] == "scene:1"
    assert packet["canon_guardrails"]
    assert packet["scene_participants"][0]["name"] == "Elain Archeron"


def test_hybrid_retriever_builds_outline_packet_with_relationship_and_thread_context(tmp_path):
    retriever = HybridNarrativeRetriever(index_service=_index_service(tmp_path))
    retrieval = _retrieval_context()

    packet = retriever.build_outline_context_packet(
        retrieval_context=retrieval,
        compiled_context={
            "story_ending": {"last_scene_summary": "Nesta and Cassian return from the Prison."},
            "generation_controls": {
                "primary_pov_character": "Elain Archeron",
                "canon_elements_to_preserve": [{"description": "Feyre and Rhys are married with Nyx"}],
            },
        },
        blueprint={
            "central_conflict": "Koschei exploits political instability.",
            "new_plot_thread": "A gate begins to wake.",
            "relationship_targets": [{"characters": ["Elain Archeron", "Azriel"]}],
        },
        world_state={"characters": [{"name": "Elain Archeron"}, {"name": "Azriel"}], "relationships": [], "active_threads": [], "events_so_far": []},
        current_story_position={"latest_generated_ending": "Elain hides the vision from everyone."},
        chapter_number=2,
        previous_summaries=["Chapter 1: Elain keeps the first vision secret."],
        chapter_controls={
            "primary_pov_character": "Elain Archeron",
            "assigned_plot_beats": ["Azriel investigates Koschei-related threats while growing closer to Elain."],
            "relationship_focus": [{"characters": ["Elain Archeron", "Azriel"], "relationship_type": "romance"}],
        },
    )

    assert packet["pov_character_packet"]["name"] == "Elain Archeron"
    assert packet["active_relationship_packet"]
    assert packet["relevant_unresolved_threads"]
    assert packet["retrieved_memories"]
