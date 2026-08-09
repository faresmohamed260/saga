from pathlib import Path

from packages.retrieval_runtime.client import RetrievalRuntimeClient
from packages.retrieval_runtime.factory import create_retrieval_client
from packages.retrieval_runtime.models import RetrievalProfile, RetrievalRuntimeConfig
from saga.services.retrieval_service import RetrievalService


def _stub_embedder(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for text in texts:
        lowered = str(text or "").lower()
        vectors.append(
            [
                float(lowered.count("harry") + lowered.count("letter")),
                float(lowered.count("owl") + lowered.count("feather")),
                float(lowered.count("hut") + lowered.count("rock")),
            ]
        )
    return vectors


def test_retrieval_runtime_indexes_and_queries_documents(tmp_path: Path) -> None:
    profile = RetrievalProfile(name="default", base_dir=str(tmp_path / "vector_indices"))
    client = create_retrieval_client(
        config=RetrievalRuntimeConfig(profile=profile),
        profile=profile,
        embedder=_stub_embedder,
    )
    payload = client.ensure_document_index(
        series_id="hp",
        scope_key="book-1",
        documents=[
            {
                "document_id": "scene-1",
                "source_type": "scene",
                "summary": "Harry receives a letter",
                "text": "Harry receives a parchment letter.",
                "metadata": {"characters": ["Harry Potter"]},
            },
            {
                "document_id": "scene-2",
                "source_type": "scene",
                "summary": "An owl lands near the hut",
                "text": "A brown owl lands beside the hut on the rock.",
                "metadata": {"characters": ["Owl"]},
            },
        ],
    )

    hits = client.query_documents(
        index_ref={
            "index_id": payload["index_id"],
            "series_id": payload["series_id"],
            "scope_key": payload["scope_key"],
            "fingerprint": payload["fingerprint"],
        },
        query_text="Which scene has the owl near the hut?",
        top_k=1,
        character_bias=["Owl"],
    )

    assert hits
    assert hits[0]["document_id"] == "scene-2"


def test_retrieval_service_wraps_book_and_document_retrieval(tmp_path: Path) -> None:
    class StubBookRetriever:
        def ensure_book_index(self, *, book_id: str, source_types=None):
            return {"book_id": book_id, "source_types": list(source_types or [])}

        def query_book(self, *, book_id: str, query_text: str, top_k: int = 8, **kwargs):
            return [{"book_id": book_id, "query_text": query_text, "score": 1.0, "source_type": "scene"}]

    profile = RetrievalProfile(name="default", base_dir=str(tmp_path / "vector_indices"))
    document_client = RetrievalRuntimeClient(
        profile=profile,
        config=RetrievalRuntimeConfig(profile=profile),
        embedder=_stub_embedder,
    )
    service = RetrievalService(book_retriever=StubBookRetriever(), document_retriever=document_client)

    book_hits = service.query_book(book_id="book-1", query_text="Harry")
    index_payload = service.ensure_document_index(
        series_id="hp",
        scope_key="book-1",
        documents=[
            {
                "document_id": "scene-1",
                "source_type": "scene",
                "summary": "Harry receives a letter",
                "text": "Harry receives a parchment letter.",
                "metadata": {"characters": ["Harry Potter"]},
            }
        ],
    )
    doc_hits = service.query_documents(
        index_ref={
            "index_id": index_payload["index_id"],
            "series_id": index_payload["series_id"],
            "scope_key": index_payload["scope_key"],
            "fingerprint": index_payload["fingerprint"],
        },
        query_text="letter",
    )

    assert book_hits[0]["book_id"] == "book-1"
    assert doc_hits[0]["document_id"] == "scene-1"
