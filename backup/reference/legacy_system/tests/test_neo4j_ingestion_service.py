from saga.providers import neo4j_ingestion_service as neo4j_module
from saga.providers.neo4j_ingestion_service import (
    Neo4jAuthenticationError,
    Neo4jBookConflictError,
    Neo4jClientConfigurationError,
    Neo4jConnectionUnavailableError,
    Neo4jDriverMissingError,
    Neo4jIngestionService,
)


class _FakeDriver:
    def __init__(self, exc=None):
        self.exc = exc

    def verify_connectivity(self):
        if self.exc:
            raise self.exc

    def close(self):
        return None


class _PlanningSession:
    def __init__(self, by_title=None, by_index=None):
        self.by_title = by_title or {}
        self.by_index = by_index or {}

    def run(self, query, **params):
        compact = " ".join(query.split())
        if "MATCH (b:Book {series_id: $series_id, title: $book_title})" in compact:
            row = self.by_title.get(params["book_title"])
            return _SingleResult(row)
        if "MATCH (b:Book {series_id: $series_id, book_index: $book_index})" in compact:
            row = self.by_index.get(params["book_index"])
            return _SingleResult(row)
        if "MATCH (s:Series {series_id: $series_id})" in compact:
            return _SingleResult(None)
        raise AssertionError(f"Unexpected query: {compact}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None


class _SingleRow:
    def __init__(self, payload):
        self.payload = payload

    def data(self):
        return dict(self.payload)


class _SingleResult:
    def __init__(self, payload):
        self.payload = payload

    def single(self):
        if self.payload is None:
            return None
        return _SingleRow(self.payload)


class _PlanningDriver(_FakeDriver):
    def __init__(self, session):
        super().__init__()
        self._session = session

    def session(self, **kwargs):
        return self._session


def test_neo4j_probe_reports_missing_driver(monkeypatch):
    monkeypatch.setattr(neo4j_module, "GraphDatabase", None)
    service = Neo4jIngestionService()

    try:
        service.probe_connection()
    except Neo4jDriverMissingError as exc:
        assert "pip install -e .[graph]" in str(exc)
        assert "NEO4J_URI" in str(exc)
    else:
        raise AssertionError("Expected missing driver to raise Neo4jDriverMissingError.")


def test_neo4j_probe_classifies_unreachable_database(monkeypatch):
    class _FakeServiceUnavailable(Exception):
        pass

    monkeypatch.setattr(neo4j_module, "ServiceUnavailable", _FakeServiceUnavailable)
    service = Neo4jIngestionService(driver=_FakeDriver(exc=_FakeServiceUnavailable("down")))

    try:
        service.probe_connection()
    except Neo4jConnectionUnavailableError as exc:
        assert "unreachable" in str(exc).lower()
        assert "NEO4J_URI" in str(exc)
    else:
        raise AssertionError("Expected unreachable database to raise Neo4jConnectionUnavailableError.")


def test_neo4j_probe_classifies_auth_failure(monkeypatch):
    class _FakeAuthError(Exception):
        pass

    monkeypatch.setattr(neo4j_module, "AuthError", _FakeAuthError)
    service = Neo4jIngestionService(driver=_FakeDriver(exc=_FakeAuthError("bad auth")))

    try:
        service.probe_connection()
    except Neo4jAuthenticationError as exc:
        assert "authentication failed" in str(exc).lower()
        assert "NEO4J_PASSWORD" in str(exc)
    else:
        raise AssertionError("Expected auth failure to raise Neo4jAuthenticationError.")


def test_neo4j_probe_classifies_bad_configuration(monkeypatch):
    class _FakeConfigError(Exception):
        pass

    monkeypatch.setattr(neo4j_module, "ConfigurationError", _FakeConfigError)
    service = Neo4jIngestionService(driver=_FakeDriver(exc=_FakeConfigError("bad config")))

    try:
        service.probe_connection()
    except Neo4jClientConfigurationError as exc:
        assert "configuration is invalid" in str(exc).lower()
        assert "NEO4J_DATABASE" in str(exc)
    else:
        raise AssertionError("Expected bad configuration to raise Neo4jClientConfigurationError.")


def test_neo4j_plan_ingest_classifies_new_unchanged_and_stale():
    service = Neo4jIngestionService(
        driver=_PlanningDriver(
            _PlanningSession(
                by_title={
                    "Same Book": {
                        "title": "Same Book",
                        "book_index": 1,
                        "source_hash_sha256": "same",
                    },
                    "Changed Book": {
                        "title": "Changed Book",
                        "book_index": 2,
                        "source_hash_sha256": "old",
                    },
                },
                by_index={1: {"title": "Same Book"}, 2: {"title": "Changed Book"}},
            )
        )
    )

    plan = service.plan_ingest("harry-potter", [
        {"title": "Same Book", "path": "same.epub", "book_index": 1, "source_hash_sha256": "same"},
        {"title": "Changed Book", "path": "changed.epub", "book_index": 2, "source_hash_sha256": "new"},
        {"title": "New Book", "path": "new.epub", "book_index": 3, "source_hash_sha256": "fresh"},
    ])

    actions = {row["title"]: row["action"] for row in plan["books"]}
    assert actions == {"Same Book": "unchanged", "Changed Book": "stale", "New Book": "new"}


def test_neo4j_plan_ingest_detects_book_index_conflict():
    service = Neo4jIngestionService(
        driver=_PlanningDriver(
            _PlanningSession(
                by_index={6: {"title": "Existing Book"}},
            )
        )
    )

    plan = service.plan_ingest("harry-potter", [
        {"title": "New Book", "path": "new.epub", "book_index": 6, "source_hash_sha256": "fresh"},
    ])

    assert plan["books"][0]["action"] == "conflict"


def test_neo4j_service_loads_local_env_file(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join([
            "NEO4J_URI=neo4j://db.example:7687",
            "NEO4J_USERNAME=graph",
            "NEO4J_PASSWORD=secret",
            "NEO4J_DATABASE=story",
        ]),
        encoding="utf-8",
    )

    service = Neo4jIngestionService(env_path=env_path)

    assert service.uri == "neo4j://db.example:7687"
    assert service.username == "graph"
    assert service.password == "secret"
    assert service.database == "story"


def test_derive_book_entity_stats_accepts_canonical_character_dicts():
    service = Neo4jIngestionService(driver=_FakeDriver())

    stats = service._derive_book_entity_stats(
        resolved_scenes=[
            {
                "book_index": 1,
                "chapter_index": 2,
                "scene_index": 3,
                "entities_present": [{"name": "Hogwarts"}],
                "canonical_characters": [
                    {"name": "Harry Potter", "names_used": ["Harry"]},
                    {"name": "Ron"},
                ],
            }
        ]
    )

    assert stats["Harry Potter"][1]["mention_count"] == 1
    assert stats["Ron"][1]["first_seen_chapter"] == 2
    assert stats["Hogwarts"][1]["first_seen_scene"] == 3


def test_canonicalize_entity_registry_collapses_aliases_and_corrects_locations():
    service = Neo4jIngestionService(driver=_FakeDriver())

    repaired = service._canonicalize_entity_registry(
        [
            {"name": "Feyre Archeron", "entity_type": "character", "descriptions": [], "state_changes": []},
            {"name": "Feyr e", "entity_type": "character", "descriptions": [], "state_changes": []},
            {"name": "Rhysand's House", "entity_type": "character", "descriptions": [], "state_changes": []},
        ],
        alias_map={"Feyre Archeron": ["Feyre Archeron", "Feyr e"]},
    )

    by_name = {row["name"]: row for row in repaired}
    assert "Feyr e" not in by_name
    assert by_name["Feyre Archeron"]["entity_type"] == "character"
    assert by_name["Rhysand's House"]["entity_type"] == "location"
