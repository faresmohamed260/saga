from __future__ import annotations

from pathlib import Path

from saga.storage.database import get_database_url
from saga.storage.models import Book
from saga.storage.persistence import SagaRelationalStore


def test_get_database_url_allows_swappable_explicit_database_url() -> None:
    url = get_database_url(database_url="postgresql://user:pass@example.com:5432/saga")
    assert url == "postgresql://user:pass@example.com:5432/saga"


def test_saga_relational_store_supports_default_sqlite_runtime(tmp_path: Path) -> None:
    store = SagaRelationalStore(database_path=tmp_path / "saga.sqlite")
    with store.session_factory() as session:
        session.add(Book(id="book-1", series_id="series-1", book_index=1, title="Test Book"))
        session.commit()

    with store.session_factory() as session:
        row = session.get(Book, "book-1")
        assert row is not None
        assert row.title == "Test Book"
