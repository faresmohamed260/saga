from query.neo4j_narrative_context_service import Neo4jNarrativeContextService


class _FakeRow:
    def __init__(self, payload):
        self.payload = payload

    def data(self):
        return dict(self.payload)


class _FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def single(self):
        if not self.rows:
            return None
        return _FakeRow(self.rows[0])

    def __iter__(self):
        for row in self.rows:
            yield _FakeRow(row)


class _FakeSession:
    def run(self, query, **params):
        compact = " ".join(query.split())
        if "MATCH (b:Book) WHERE" in compact and "RETURN b.title AS title, b.series_id AS series_id" in compact:
            return _FakeResult([{"title": "A Court of Frost and Starlight.epub", "series_id": "harry-potter"}])
        if "MATCH (e:Entity {series_id: $series_id})-[:HAS_ALIAS]->(a:Alias {series_id: $series_id})" in compact:
            return _FakeResult([])
        if "ORDER BY sc.book_index DESC, sc.chapter_index DESC, sc.scene_index DESC LIMIT 1" in compact:
            return _FakeResult([{
                "summary": "Final scene",
                "book_index": 1,
                "chapter_index": 10,
                "scene_index": 2,
                "location": {"name": "Velaris", "entity_type": "location", "description": ""},
                "entities_present": [{"name": "Feyre", "entity_type": "character"}],
            }])
        if "AND e.is_critical = true" in compact:
            return _FakeResult([{"id": "evt_1", "description": "Critical event", "chapter": 10, "score": 9, "why_critical": "Important", "order": 1, "story_impact": 9}])
        if "MATCH (b:Book)-[he:HAS_ENTITY]->(e:Entity {entity_type: 'character'})" in compact:
            return _FakeResult([{
                "name": "Feyre",
                "mention_count": 26,
                "first_seen_chapter": 1,
                "descriptions": ["High Lady"],
                "aliases": ["Feyre Darling"],
                "state_transitions": [{"attribute": "grief", "new_state": "easing", "chapter": 10}],
                "props": {"canon_relationship_status": "married to Rhys"},
            }])
        if "MATCH (b:Book)-[:HAS_ENTITY]->(a:Entity)-[r:HAS_RELATIONSHIP]->(c:Entity)" in compact:
            return _FakeResult([{"entity_a": "Feyre", "entity_b": "Rhys", "relationship_type": "MATES", "latest_change": "Closer", "evidence": "Scene", "last_seen_chapter": 10}])
        if "MATCH (b:Book)-[:HAS_EVENT]->(e:Event)-[:IS_DIVERGENCE_POINT]->(d:DivergencePoint)" in compact:
            return _FakeResult([{"event_id": "evt_2", "event_description": "Decision", "chapter": 10, "book_index": 1, "is_critical": True, "decision_made": "Stay", "alternatives": ["Leave"], "divergence_potential": 8, "alternate_timeline": "Alt", "thread_type": "historical_branch"}])
        if "coalesce(e.is_flexible, false) = true" in compact:
            return _FakeResult([{"event_id": "evt_4", "event_description": "Koschei threat grows in the court.", "chapter": 10, "book_index": 1, "is_critical": True, "decision_made": "", "alternatives": [], "divergence_potential": 9, "alternate_timeline": "", "thread_type": "magical_threat"}])
        if "MATCH (b:Book)-[:HAS_EVENT]->(e:Event)-[:IN_CHAIN]->(cc:CausalChain)" in compact:
            return _FakeResult([{"chain_id": "chain_1", "description": "Arc", "chain_type": "LINEAR", "story_function": "growth", "events": [{"event_id": "evt_1", "description": "Critical event", "chapter": 10, "time_index": 5}]}])
        if "AND e.is_flexible = true" in compact:
            return _FakeResult([{"event_id": "evt_3", "description": "Flexible", "chapter": 9, "flexibility_score": 7, "why_flexible": "Branching"}])
        if "MATCH (b:Book)-[:HAS_ENTITY]->(c:Entity {entity_type: 'character'})-[:INVOLVED_IN]->(e:Event)" in compact:
            return _FakeResult([{"character": "Feyre", "last_events": [{"summary": "Recent event", "time_index": 5}]}])
        if "MATCH (b:Book)-[:HAS_CHAPTER]->(:Chapter)-[:HAS_SCENE]->(sc:Scene)" in compact and "collect(DISTINCT ent.name) AS characters" in compact:
            return _FakeResult([{
                "book_title": "A Court of Frost and Starlight.epub",
                "book_index": 1,
                "chapter_index": 10,
                "scene_index": 2,
                "summary": "Final scene",
                "characters": ["Feyre"],
            }])
        if "OPTIONAL MATCH (c:Entity)-[:INVOLVED_IN]->(e)" in compact:
            return _FakeResult([{
                "book_title": "A Court of Frost and Starlight.epub",
                "event_id": "evt_1",
                "description": "Critical event",
                "book_index": 1,
                "chapter_index": 10,
                "time_index": 5,
                "characters": ["Feyre"],
            }])
        raise AssertionError(f"Unexpected query: {compact}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None


class _FakeDriver:
    def verify_connectivity(self):
        return None

    def session(self, **kwargs):
        return _FakeSession()

    def close(self):
        return None


def test_neo4j_narrative_context_service_builds_decoder_schema_from_graph():
    service = Neo4jNarrativeContextService(driver=_FakeDriver())

    context = service.build_from_graph(
        series_id="harry-potter",
        book_titles=["A Court of Frost and Starlight.epub"],
    )

    assert context["meta"]["book_title"] == "A Court of Frost and Starlight.epub"
    assert context["meta"]["series_id"] == "harry-potter"
    assert context["meta"]["matched_book_titles"] == ["A Court of Frost and Starlight.epub"]
    assert context["story_ending"]["last_scene"]["summary"] == "Final scene"
    assert context["character_states"][0]["canon_state"]["relationship_status"] == "married to Rhys"
    assert context["relationship_summary"][0]["relationship_type"] == "MATES"
    assert context["unresolved_threads"][0]["event_id"] == "evt_4"
    assert any(item["event_id"] == "evt_2" for item in context["unresolved_threads"])
    assert context["causal_chains"][0]["chain_id"] == "chain_1"
    assert context["flexible_events"][0]["event_id"] == "evt_3"
    assert context["character_trajectories"][0]["character"] == "Feyre"


class _MixedSeriesSession(_FakeSession):
    def run(self, query, **params):
        compact = " ".join(query.split())
        if "MATCH (b:Book) WHERE" in compact and "RETURN b.title AS title, b.series_id AS series_id" in compact:
            return _FakeResult([
                {"title": "Book One", "series_id": "series-a"},
                {"title": "Book One", "series_id": "series-b"},
            ])
        return super().run(query, **params)


class _MixedSeriesDriver(_FakeDriver):
    def session(self, **kwargs):
        return _MixedSeriesSession()


def test_neo4j_narrative_context_service_rejects_mixed_series_scope_without_series_id():
    service = Neo4jNarrativeContextService(driver=_MixedSeriesDriver())

    try:
        service.build_from_graph(book_titles=["Book One"])
    except ValueError as exc:
        assert "mixed-series retrieval contamination" in str(exc)
    else:
        raise AssertionError("Expected mixed-series scope to raise a ValueError.")


class _DirtyAliasSession(_FakeSession):
    def run(self, query, **params):
        compact = " ".join(query.split())
        if "MATCH (b:Book) WHERE" in compact and "RETURN b.title AS title, b.series_id AS series_id" in compact:
            return _FakeResult([
                {"title": "A Court of Frost and Starlight.epub", "series_id": "acotar"},
                {"title": "A Court of Silver Flames.epub", "series_id": "acotar"},
            ])
        if "MATCH (e:Entity {series_id: $series_id})-[:HAS_ALIAS]->(a:Alias {series_id: $series_id})" in compact:
            return _FakeResult([
                {"canonical_name": "Feyre Archeron", "alias_text": "Feyr e"},
                {"canonical_name": "Feyre Archeron", "alias_text": "Feyre"},
            ])
        if "ORDER BY sc.book_index DESC, sc.chapter_index DESC, sc.scene_index DESC LIMIT 1" in compact:
            return _FakeResult([{
                "summary": "Final scene",
                "book_index": 5,
                "chapter_index": 80,
                "scene_index": 1,
                "location": {"name": "Velaris", "entity_type": "location", "description": ""},
                "entities_present": [
                    {"name": "Feyr e", "entity_type": "character"},
                    {"name": "Rhysand", "entity_type": "character"},
                ],
            }])
        if "MATCH (b:Book)-[he:HAS_ENTITY]->(e:Entity {entity_type: 'character'})" in compact:
            return _FakeResult([
                {
                    "name": "Feyre Archeron",
                    "mention_count": 26,
                    "first_seen_chapter": 1,
                    "descriptions": ["High Lady"],
                    "aliases": ["Feyre"],
                    "state_transitions": [{"attribute": "relationship_status", "new_state": "married to Rhysand", "chapter": 80}],
                    "props": {"canon_relationship_status": "married to Rhysand"},
                },
                {
                    "name": "Feyr e",
                    "mention_count": 3,
                    "first_seen_chapter": 1,
                    "descriptions": ["OCR variant"],
                    "aliases": ["Feyre"],
                    "state_transitions": [{"attribute": "status", "new_state": "dead", "chapter": 80}],
                    "props": {"canon_status": "dead"},
                },
                {
                    "name": "Rhysand's House",
                    "mention_count": 11,
                    "first_seen_chapter": 1,
                    "descriptions": ["Town house"],
                    "aliases": [],
                    "state_transitions": [],
                    "props": {"entity_type": "location"},
                },
                {
                    "name": "Rhysand For Solstice",
                    "mention_count": 42,
                    "first_seen_chapter": 1,
                    "descriptions": ["mate of Feyre"],
                    "aliases": ["Rhys"],
                    "state_transitions": [],
                    "props": {"entity_type": "character"},
                },
            ])
        return super().run(query, **params)


class _DirtyAliasDriver(_FakeDriver):
    def session(self, **kwargs):
        return _DirtyAliasSession()


def test_neo4j_narrative_context_service_cleans_alias_pollution_and_uses_latest_scope_title():
    service = Neo4jNarrativeContextService(driver=_DirtyAliasDriver())

    context = service.build_from_graph(series_id="acotar")

    assert context["meta"]["book_title"] == "A Court of Silver Flames.epub"
    assert context["story_ending"]["last_scene"]["entities_present"][0]["name"] == "Feyre Archeron"
    by_name = {item["name"]: item for item in context["character_states"]}
    assert by_name["Feyre Archeron"]["canon_state"] == {"relationship_status": "married to Rhysand"}
    assert all(item["name"] != "Rhysand's House" for item in context["character_states"])
    assert all(item["name"] != "Rhysand For Solstice" for item in context["character_states"])


def test_neo4j_narrative_context_service_prefers_clean_canonical_display_names():
    service = Neo4jNarrativeContextService(driver=_FakeDriver())

    assert service._best_display_name(["Azriel Siphons", "Azriel"]) == "Azriel"
    assert service._canonicalize_name("Feyre's", alias_lookup={}) == "Feyre"
    assert service._canonicalize_name("The War", alias_lookup={}) == ""


def test_neo4j_narrative_context_service_uses_canon_props_as_series_wide_fallback():
    service = Neo4jNarrativeContextService(driver=_FakeDriver())

    canon_state = service._derive_stable_canon_state(
        [{"canon_title": "High Lady of the Night Court", "canon_relationship_status": "married to Rhysand"}],
        [],
        descriptions=[],
        aliases=[],
        latest_book_index=5,
        use_props_fallback=False,
    )

    assert canon_state == {
        "title": "High Lady of the Night Court",
        "relationship_status": "married to Rhysand",
    }


def test_neo4j_narrative_context_service_infers_canon_state_from_alias_titles():
    service = Neo4jNarrativeContextService(driver=_FakeDriver())

    canon_state = service._derive_stable_canon_state(
        [{}],
        [],
        descriptions=[],
        aliases=["High Lord of Spring", "Tamlin"],
        latest_book_index=5,
        use_props_fallback=False,
    )

    assert canon_state == {
        "title": "High Lord",
        "court": "Spring Court",
    }


def test_neo4j_narrative_context_service_sanitizes_output_aliases_and_scopes_recent_transitions_to_latest_book():
    service = Neo4jNarrativeContextService(driver=_FakeDriver())

    cleaned = service._clean_character_states(
        [
            {
                "name": "Rhysand",
                "mention_count": 50,
                "first_seen_chapter": 1,
                "latest_book_index": 5,
                "descriptions": [],
                "aliases": ["Rhys", "Letting Rhys", "Rhysand's", "High Lord of the Night Court"],
                "state_transitions": [
                    {
                        "attribute": "status",
                        "previous_state": "alive",
                        "new_state": "dead",
                        "change_type": "physical_state",
                        "evidence": "Old battle death",
                        "chapter": 76,
                        "book_index": 3,
                    },
                    {
                        "attribute": "status",
                        "previous_state": "dead",
                        "new_state": "alive",
                        "change_type": "physical_state",
                        "evidence": "Old battle revival",
                        "chapter": 77,
                        "book_index": 3,
                    },
                    {
                        "attribute": "communication",
                        "previous_state": "",
                        "new_state": "plans war council with Feyre",
                        "change_type": "knowledge",
                        "evidence": "Latest-book council planning",
                        "chapter": 80,
                        "book_index": 5,
                    },
                ],
                "props": {"entity_type": "character"},
            }
        ],
        alias_lookup={},
        top_characters=10,
        use_props_fallback=True,
        target_recent_book_index=5,
    )

    assert cleaned[0]["aliases"] == ["Rhys"]
    assert cleaned[0]["state_transitions"] == [
        {
            "attribute": "communication",
            "previous_state": "",
            "new_state": "plans war council with Feyre",
            "change_type": "knowledge",
            "evidence": "Latest-book council planning",
            "chapter": 80,
            "book_index": 5,
        }
    ]


def test_neo4j_narrative_context_service_prefers_scope_latest_book_for_recent_changes():
    service = Neo4jNarrativeContextService(driver=_FakeDriver())

    cleaned = service._clean_character_states(
        [
            {
                "name": "Lucien Vanserra",
                "mention_count": 20,
                "first_seen_chapter": 1,
                "latest_book_index": 3,
                "descriptions": [],
                "aliases": ["Lucien"],
                "state_transitions": [
                    {
                        "attribute": "status",
                        "previous_state": "",
                        "new_state": "alive",
                        "change_type": "status",
                        "evidence": "Old-book status",
                        "chapter": 32,
                        "book_index": 1,
                    },
                    {
                        "attribute": "status",
                        "previous_state": "alive",
                        "new_state": "free to wander with conditions",
                        "change_type": "status",
                        "evidence": "Mid-series status",
                        "chapter": 16,
                        "book_index": 3,
                    },
                ],
                "props": {"entity_type": "character"},
            }
        ],
        alias_lookup={},
        top_characters=10,
        use_props_fallback=True,
        target_recent_book_index=5,
    )

    assert cleaned[0]["state_transitions"] == []


def test_neo4j_narrative_context_service_drops_generic_family_and_narrator_alias_labels():
    service = Neo4jNarrativeContextService(driver=_FakeDriver())

    aliases = service._sanitize_output_aliases(
        canonical_name="Feyre Archeron",
        aliases=["Father", "My Father", "The Narrator", "Feyre", "Feyre Cursebreaker"],
    )

    assert aliases == ["Feyre"]


def test_neo4j_narrative_context_service_drops_ocr_like_alias_variants_when_clean_short_name_exists():
    service = Neo4jNarrativeContextService(driver=_FakeDriver())

    aliases = service._sanitize_output_aliases(
        canonical_name="Feyre Archeron",
        aliases=["Feyre", "Feyri", "Feyr"],
    )

    assert aliases == ["Feyre", "Feyr"]
