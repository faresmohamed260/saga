from packages.retrieval_runtime.models import RetrievalProfile, RetrievalRuntimeConfig
from packages.retrieval_runtime.client import RetrievalRuntimeClient
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client


def test_retrieval_profile_rejects_invalid_values():
    try:
        RetrievalProfile(name="", mode="document_index")
    except ValueError as exc:
        assert "name is required" in str(exc)
    else:
        raise AssertionError("Expected invalid retrieval profile to be rejected.")

    try:
        RetrievalProfile(name="bad", mode="document_index", ollama_embed_url="localhost-only")
    except ValueError as exc:
        assert "ollama_embed_url" in str(exc)
    else:
        raise AssertionError("Expected invalid retrieval embed URL to be rejected.")


def test_retrieval_runtime_config_requires_profile():
    try:
        RetrievalRuntimeConfig(profile=None)  # type: ignore[arg-type]
    except ValueError as exc:
        assert "profile is required" in str(exc)
    else:
        raise AssertionError("Expected retrieval runtime config without profile to be rejected.")


def test_retrieval_tool_payload_uses_request_metadata(tmp_path):
    persistence_profile = PersistenceProfile(
        name="retrieval-test-persistence",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'retrieval-request-metadata.sqlite3'}",
    )
    persistence_client = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=persistence_profile),
        profile=persistence_profile,
    )
    client = RetrievalRuntimeClient(
        profile=RetrievalProfile(name="test-retrieval", mode="document_index"),
        config=RetrievalRuntimeConfig(profile=RetrievalProfile(name="test-retrieval", mode="document_index")),
        embedder=lambda texts: [[float(index + 1), 0.0, 0.0] for index, _ in enumerate(texts)],
        persistence_client=persistence_client,
    )

    tools = {tool.name: tool for tool in client.as_langgraph_tools()}
    indexed = tools["retrieval_ensure_document_index"].invoke(
        {
            "series_id": "series-1",
            "scope_key": "chapters",
            "documents": [
                {"document_id": "doc-1", "text": "Victor Frankenstein creates the creature.", "summary": "Victor creates the creature."}
            ],
        }
    )

    assert indexed["ok"] is True
    assert "request_metadata" in indexed["data"]
    assert indexed["data"]["request_metadata"]["operation"] == "ensure_document_index"


def test_retrieval_runtime_returns_typed_document_and_result_metadata(tmp_path):
    persistence_profile = PersistenceProfile(
        name="retrieval-typed-metadata",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'retrieval-typed-metadata.sqlite3'}",
    )
    persistence_client = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=persistence_profile),
        profile=persistence_profile,
    )
    client = RetrievalRuntimeClient(
        profile=RetrievalProfile(name="test-retrieval", mode="document_index"),
        config=RetrievalRuntimeConfig(profile=RetrievalProfile(name="test-retrieval", mode="document_index")),
        embedder=lambda texts: [[float(index + 1), 0.0, 0.0] for index, _ in enumerate(texts)],
        persistence_client=persistence_client,
    )

    indexed = client.ensure_document_index(
        series_id="series-1",
        scope_key="chapters",
        documents=[
            {
                "document_id": "doc-1",
                "text": "Victor Frankenstein creates the creature.",
                "summary": "Victor creates the creature.",
                "source_type": "scene",
                "metadata": {"characters": ["Victor Frankenstein", "Creature"], "chapter": 1},
            }
        ],
    )
    queried = client.query_documents(
        index_ref={
            "index_id": indexed["index_id"],
            "series_id": indexed["series_id"],
            "scope_key": indexed["scope_key"],
            "fingerprint": indexed["fingerprint"],
        },
        query_text="who creates the creature",
        top_k=1,
    )

    assert indexed["documents"][0]["metadata"]["characters"] == ["Victor Frankenstein", "Creature"]
    assert indexed["documents"][0]["metadata"]["attributes"]["chapter"] == 1
    assert queried[0]["metadata"]["characters"] == ["Victor Frankenstein", "Creature"]
    assert queried[0]["metadata"]["attributes"]["chapter"] == 1
