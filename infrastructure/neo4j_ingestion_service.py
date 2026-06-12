"""Neo4j ingestion adapter for the SAGA export contract.

This service absorbs the exploratory Narraverse FastAPI prototype into a
reusable class that can be called directly from scripts, jobs, or future UI
entrypoints without forcing the main pipeline to depend on FastAPI.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from core.canon_normalization import CanonicalEntityContext, CanonicalEntityNormalizer
from core.stable_character_state import StableCharacterStateBuilder

try:
    from neo4j import GraphDatabase
    from neo4j.exceptions import AuthError, ConfigurationError, ServiceUnavailable
except ImportError:  # pragma: no cover - optional dependency
    GraphDatabase = None
    AuthError = None
    ConfigurationError = None
    ServiceUnavailable = None


class Neo4jIngestionError(RuntimeError):
    """Base operational error for Neo4j ingestion."""


class Neo4jDriverMissingError(Neo4jIngestionError):
    """Raised when the optional Neo4j driver dependency is unavailable."""


class Neo4jConnectionUnavailableError(Neo4jIngestionError):
    """Raised when the database cannot be reached."""


class Neo4jAuthenticationError(Neo4jIngestionError):
    """Raised when Neo4j authentication fails."""


class Neo4jClientConfigurationError(Neo4jIngestionError):
    """Raised when Neo4j connection settings are malformed."""


class Neo4jBookConflictError(Neo4jIngestionError):
    """Raised when an ingest would overwrite an existing persisted book version."""


class Neo4jIngestionService:
    """Persist a SAGA export contract into Neo4j."""

    STABLE_CANON_ATTRIBUTES = {
        "bond",
        "relationship_status",
        "role",
        "title",
        "court",
        "court_role",
        "political_role",
        "family_role",
        "mate_status",
        "allegiance",
        "loyalty",
        "residence",
        "power_status",
    }

    def __init__(
        self,
        *,
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
        database: str | None = None,
        env_path: str | Path | None = None,
        driver: Any | None = None,
    ) -> None:
        self.env_path = Path(env_path) if env_path else Path("deploy/neo4j/.env")
        local_env = self._load_local_env(self.env_path)
        self.uri = uri or os.getenv("NEO4J_URI") or local_env.get("NEO4J_URI") or "neo4j://localhost:7687"
        self.username = username or os.getenv("NEO4J_USERNAME") or local_env.get("NEO4J_USERNAME") or "neo4j"
        self.password = password or os.getenv("NEO4J_PASSWORD") or local_env.get("NEO4J_PASSWORD") or ""
        self.database = database or os.getenv("NEO4J_DATABASE") or local_env.get("NEO4J_DATABASE") or "neo4j"
        self.driver = driver
        self.normalizer = CanonicalEntityNormalizer()
        self.stable_state_builder = StableCharacterStateBuilder()

    def close(self) -> None:
        if self.driver is not None:
            self.driver.close()
            self.driver = None

    def ingest_contract_file(self, path: str | Path) -> Dict[str, Any]:
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return self.ingest_contract(payload)

    def probe_connection(self) -> Dict[str, Any]:
        driver = self._ensure_driver()
        try:
            driver.verify_connectivity()
        except Exception as exc:  # pragma: no cover - exercised via classification tests
            self._raise_connection_error(exc)
        return {
            "status": "ok",
            "uri": self.uri,
            "database": self.database,
        }

    def ingest_contract(self, payload: Dict[str, Any], *, replace_existing: bool = False) -> Dict[str, Any]:
        driver = self._ensure_driver()
        session_kwargs = {"database": self.database} if self.database else {}
        self.probe_connection()
        try:
            with driver.session(**session_kwargs) as session:
                return self._ingest(payload, session, replace_existing=replace_existing)
        except Exception as exc:  # pragma: no cover - depends on live driver behavior
            self._raise_connection_error(exc)
            raise

    def register_series(self, series_id: str, series_title: str) -> Dict[str, Any]:
        if not series_id.strip():
            raise ValueError("series_id is required to register a corpus.")
        driver = self._ensure_driver()
        session_kwargs = {"database": self.database} if self.database else {}
        self.probe_connection()
        with driver.session(**session_kwargs) as session:
            self._run(
                session,
                """
                MERGE (s:Series {series_id: $series_id})
                SET s.title = CASE WHEN $series_title <> '' THEN $series_title ELSE coalesce(s.title, $series_id) END,
                    s.updated_at = datetime($updated_at),
                    s.created_at = coalesce(s.created_at, datetime($updated_at))
                """,
                series_id=series_id,
                series_title=series_title.strip(),
                updated_at=self._now_utc(),
            )
        return {"status": "ok", "series_id": series_id, "series_title": series_title.strip()}

    def inspect_series(self, series_id: str) -> Dict[str, Any]:
        if not series_id.strip():
            raise ValueError("series_id is required to inspect a corpus.")
        driver = self._ensure_driver()
        session_kwargs = {"database": self.database} if self.database else {}
        self.probe_connection()
        with driver.session(**session_kwargs) as session:
            header = session.run(
                """
                MATCH (s:Series {series_id: $series_id})
                RETURN s.series_id AS series_id,
                       s.title AS title,
                       s.created_at AS created_at,
                       s.updated_at AS updated_at
                """,
                series_id=series_id,
            ).single()
            if not header:
                raise ValueError(f"Series '{series_id}' was not found in Neo4j database '{self.database}'.")
            labels = {
                row.data().get("label", "")
                for row in session.run("CALL db.labels() YIELD label RETURN label")
            }
            books = []
            if "Book" in labels:
                books = [
                    row.data()
                    for row in session.run(
                        """
                        MATCH (s:Series {series_id: $series_id})-[:HAS_BOOK]->(b:Book)
                        RETURN b.book_index AS book_index,
                               b.title AS title,
                               b.source_hash_sha256 AS source_hash_sha256,
                               b.source_size_bytes AS source_size_bytes,
                               b.source_mtime_utc AS source_mtime_utc,
                               b.ingested_at AS ingested_at,
                               b.encoder_version AS encoder_version,
                               b.analysis_model AS analysis_model,
                               b.identity_model AS identity_model,
                               b.analysis_mode AS analysis_mode
                        ORDER BY b.book_index ASC
                        """,
                        series_id=series_id,
                    )
                ]
        payload = header.data()
        payload["book_count"] = len(books)
        payload["books"] = books
        return payload

    def remove_book(self, series_id: str, book_title: str) -> Dict[str, Any]:
        if not series_id.strip() or not book_title.strip():
            raise ValueError("series_id and book_title are required to remove a persisted book.")
        driver = self._ensure_driver()
        session_kwargs = {"database": self.database} if self.database else {}
        self.probe_connection()
        with driver.session(**session_kwargs) as session:
            record = self.lookup_book(series_id, book_title, session=session)
            if not record:
                raise ValueError(
                    f"Book '{book_title}' was not found in series '{series_id}' in Neo4j database '{self.database}'."
                )
            book_index = record["book_index"]
            self._remove_book_in_session(session, series_id=series_id, book_title=book_title, book_index=book_index)
        return {"status": "ok", "series_id": series_id, "book_title": book_title, "book_index": book_index}

    def purge_series_residue(self, series_id: str) -> Dict[str, Any]:
        if not series_id.strip():
            raise ValueError("series_id is required to purge residual series data.")
        driver = self._ensure_driver()
        session_kwargs = {"database": self.database} if self.database else {}
        self.probe_connection()
        with driver.session(**session_kwargs) as session:
            self._run(
                session,
                """
                MATCH (n {series_id: $series_id})
                WHERE NOT n:Series
                DETACH DELETE n
                """,
                series_id=series_id,
            )
            self._run(
                session,
                """
                MATCH (s:Series {series_id: $series_id})
                SET s.updated_at = datetime($updated_at)
                """,
                series_id=series_id,
                updated_at=self._now_utc(),
            )
        return {"status": "ok", "series_id": series_id}

    def lookup_book(self, series_id: str, book_title: str, *, session=None) -> Dict[str, Any] | None:
        owns_session = False
        if session is None:
            driver = self._ensure_driver()
            session_kwargs = {"database": self.database} if self.database else {}
            self.probe_connection()
            session = driver.session(**session_kwargs)
            owns_session = True
        try:
            row = session.run(
                """
                MATCH (b:Book {series_id: $series_id, title: $book_title})
                RETURN b.title AS title,
                       b.book_index AS book_index,
                       b.source_hash_sha256 AS source_hash_sha256,
                       b.source_mtime_utc AS source_mtime_utc,
                       b.source_size_bytes AS source_size_bytes,
                       b.ingested_at AS ingested_at,
                       b.encoder_version AS encoder_version
                LIMIT 1
                """,
                series_id=series_id,
                book_title=book_title,
            ).single()
            return row.data() if row else None
        finally:
            if owns_session:
                session.close()

    def plan_ingest(self, series_id: str, books: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not series_id.strip():
            raise ValueError("series_id is required to plan a corpus ingest.")
        driver = self._ensure_driver()
        session_kwargs = {"database": self.database} if self.database else {}
        self.probe_connection()
        plan_books: List[Dict[str, Any]] = []
        with driver.session(**session_kwargs) as session:
            for book in books:
                title = (book.get("title") or Path(book["path"]).name).strip()
                existing = self.lookup_book(series_id, title, session=session)
                requested_index = int(book.get("book_index") or 0)
                index_row = session.run(
                    """
                    MATCH (b:Book {series_id: $series_id, book_index: $book_index})
                    RETURN b.title AS title
                    LIMIT 1
                    """,
                    series_id=series_id,
                    book_index=requested_index,
                ).single()
                index_title = (index_row.data().get("title") if index_row else "") or ""
                source_hash = book.get("source_hash_sha256", "")
                if index_title and index_title != title:
                    action = "conflict"
                    reason = f"book_index {requested_index} is already occupied by '{index_title}'."
                elif existing and existing.get("source_hash_sha256") == source_hash:
                    action = "unchanged"
                    reason = "same source hash already persisted"
                elif existing:
                    action = "stale"
                    reason = "book title already exists with a different source hash"
                else:
                    action = "new"
                    reason = "book title not found in persisted corpus"
                plan_books.append({
                    "title": title,
                    "book_index": requested_index,
                    "source_hash_sha256": source_hash,
                    "action": action,
                    "reason": reason,
                    "existing": existing or {},
                })
        return {
            "series_id": series_id,
            "books": plan_books,
            "summary": {
                "new": sum(1 for row in plan_books if row["action"] == "new"),
                "unchanged": sum(1 for row in plan_books if row["action"] == "unchanged"),
                "stale": sum(1 for row in plan_books if row["action"] == "stale"),
                "conflict": sum(1 for row in plan_books if row["action"] == "conflict"),
            },
        }

    def _remove_book_in_session(self, session, *, series_id: str, book_title: str, book_index: int) -> None:
        self._run(
            session,
            """
            MATCH (b:Book {series_id: $series_id, title: $book_title})
            OPTIONAL MATCH (b)-[:HAS_CHAPTER]->(ch:Chapter)
            OPTIONAL MATCH (ch)-[:HAS_SCENE]->(sc:Scene)
            OPTIONAL MATCH (b)-[:HAS_EVENT]->(ev:Event)
            OPTIONAL MATCH (b)-[:HAS_INGEST_RUN]->(ir:IngestRun)
            OPTIONAL MATCH (st:StateTransition {series_id: $series_id, book_index: $book_index})
            DETACH DELETE sc, ch, ev, ir, st, b
            """,
            series_id=series_id,
            book_title=book_title,
            book_index=book_index,
        )
        self._run(
            session,
            """
            MATCH (s:Series {series_id: $series_id})
            SET s.updated_at = datetime($updated_at)
            """,
            series_id=series_id,
            updated_at=self._now_utc(),
        )

    def _ensure_driver(self):
        if self.driver is not None:
            return self.driver
        if GraphDatabase is None:  # pragma: no cover - optional dependency
            raise Neo4jDriverMissingError(
                "Neo4j driver is not installed. Install the optional dependency with "
                "`pip install -e .[graph]`. Expected configuration env vars: "
                "NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE."
            )
        self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
        return self.driver

    def _config_hint(self) -> str:
        return (
            "Expected env vars: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE. "
            "Local fallback file: deploy/neo4j/.env."
        )

    def _load_local_env(self, path: Path) -> Dict[str, str]:
        if not path.exists():
            return {}
        values: Dict[str, str] = {}
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
        return values

    def _raise_connection_error(self, exc: Exception) -> None:
        if AuthError is not None and isinstance(exc, AuthError):
            raise Neo4jAuthenticationError(
                f"Neo4j authentication failed for {self.uri}. Check credentials and database access. "
                f"{self._config_hint()}"
            ) from exc
        if ConfigurationError is not None and isinstance(exc, ConfigurationError):
            raise Neo4jClientConfigurationError(
                f"Neo4j connection configuration is invalid for {self.uri}. "
                f"{self._config_hint()}"
            ) from exc
        if ServiceUnavailable is not None and isinstance(exc, ServiceUnavailable):
            raise Neo4jConnectionUnavailableError(
                f"Neo4j is unreachable at {self.uri}. Start the database or update the connection settings. "
                f"{self._config_hint()}"
            ) from exc
        raise Neo4jIngestionError(
            f"Neo4j operation failed for {self.uri}: {exc!r}. {self._config_hint()}"
        ) from exc

    def _run(self, session, query: str, **params) -> None:
        session.run(query, **params)

    def _series_meta(self, payload: Dict[str, Any]) -> Dict[str, str]:
        inputs_meta = payload.get("inputs", {}) or {}
        books_meta = inputs_meta.get("books", []) or [{}]
        primary_book = books_meta[0] if books_meta else {}
        series_meta = inputs_meta.get("series") or {}
        series_title = (
            (series_meta.get("series_title") or "").strip()
            or (primary_book.get("title") or "").strip()
            or Path(primary_book.get("path", "")).stem
            or "Standalone Series"
        )
        series_id = (series_meta.get("series_id") or "").strip() or self._slugify(series_title)
        return {"series_id": series_id, "series_title": series_title}

    def _book_entries(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        inputs_meta = payload.get("inputs", {}) or {}
        series_meta = inputs_meta.get("series") or {}
        base_index = int(series_meta.get("book_index_base") or 1)
        entries: List[Dict[str, Any]] = []
        for offset, book in enumerate((inputs_meta.get("books") or []), start=0):
            title = (book.get("title") or Path(book.get("path", "")).name or "").strip()
            if not title:
                continue
            entries.append({
                "book_index": int(book.get("book_index") or (base_index + offset)),
                "title": title,
                "path": book.get("path", ""),
                "type": book.get("type", ""),
                "source_hash_sha256": book.get("source_hash_sha256", ""),
                "source_size_bytes": book.get("source_size_bytes"),
                "source_mtime_utc": book.get("source_mtime_utc", ""),
            })
        if entries:
            return entries
        fallback_title = Path((inputs_meta.get("books") or [{}])[0].get("path", "")).stem or "Unknown Book"
        return [{"book_index": base_index, "title": fallback_title, "path": "", "type": ""}]

    def _book_map(self, payload: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
        return {int(book["book_index"]): book for book in self._book_entries(payload)}

    def _now_utc(self) -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()

    def _event_key(self, series_id: str, book_index: Any, raw_event_id: str) -> str:
        return f"{series_id}::b{book_index}::{raw_event_id}"

    def _ingest(self, payload: Dict[str, Any], session, *, replace_existing: bool = False) -> Dict[str, Any]:
        inputs_meta = payload.get("inputs", {}) or {}
        books_meta = self._book_entries(payload)
        book_map = self._book_map(payload)
        primary_book = books_meta[0] if books_meta else {}
        series_meta = self._series_meta(payload)
        series_id = series_meta["series_id"]
        series_title = series_meta["series_title"]
        book_title = primary_book.get("title") or "Unknown Book"
        generated_at = payload.get("generated_at_utc", "")
        contract_version = payload.get("contract_version", "")
        outputs = self._canonicalize_outputs_payload(payload.get("outputs", {}) or {})
        configuration = payload.get("configuration", {}) or {}
        ingest_started_at = self._now_utc()

        for book in books_meta:
            existing = self.lookup_book(series_id, book["title"], session=session)
            if existing and existing.get("source_hash_sha256") == book.get("source_hash_sha256"):
                continue
            if existing and not replace_existing:
                raise Neo4jBookConflictError(
                    f"Book '{book['title']}' already exists in series '{series_id}' with a different source hash. "
                    "Use the replace flow to intentionally re-encode or replace it."
                )
            if existing and replace_existing:
                self._remove_book_in_session(
                    session,
                    series_id=series_id,
                    book_title=book["title"],
                    book_index=int(existing.get("book_index") or book.get("book_index") or 0),
                )

        self._run(
            session,
            """
            MERGE (s:Series {series_id: $series_id})
            SET s.title = $series_title,
                s.updated_at = datetime($updated_at),
                s.created_at = coalesce(s.created_at, datetime($updated_at))
            """,
            series_id=series_id,
            series_title=series_title,
            updated_at=ingest_started_at,
        )
        run_id = f"{series_id}::{generated_at or ingest_started_at}"
        self._run(
            session,
            """
            MERGE (ir:IngestRun {series_id: $series_id, run_id: $run_id})
            SET ir.generated_at = $generated_at,
                ir.ingested_at = datetime($ingested_at),
                ir.contract_version = $contract_version,
                ir.encoder_version = $encoder_version,
                ir.analysis_model = $analysis_model,
                ir.identity_model = $identity_model,
                ir.analysis_mode = $analysis_mode,
                ir.target_scene_words = $target_scene_words
            WITH ir
            MATCH (s:Series {series_id: $series_id})
            MERGE (s)-[:HAS_INGEST_RUN]->(ir)
            """,
            series_id=series_id,
            run_id=run_id,
            generated_at=generated_at,
            ingested_at=ingest_started_at,
            contract_version=contract_version,
            encoder_version=configuration.get("encoder_version", ""),
            analysis_model=configuration.get("analysis_model", ""),
            identity_model=configuration.get("identity_model", ""),
            analysis_mode=configuration.get("analysis_mode", ""),
            target_scene_words=configuration.get("target_scene_words"),
        )
        for book in books_meta:
            self._run(
                session,
                """
                MERGE (b:Book {series_id: $series_id, book_index: $book_index})
                SET b.title = $title,
                    b.path = $path,
                    b.type = $book_type,
                    b.generated_at = $generated_at,
                    b.contract_version = $contract_version,
                    b.source_hash_sha256 = $source_hash_sha256,
                    b.source_size_bytes = $source_size_bytes,
                    b.source_mtime_utc = $source_mtime_utc,
                    b.ingested_at = datetime($ingested_at),
                    b.encoder_version = $encoder_version,
                    b.analysis_model = $analysis_model,
                    b.identity_model = $identity_model,
                    b.analysis_mode = $analysis_mode,
                    b.target_scene_words = $target_scene_words
                WITH b
                MATCH (s:Series {series_id: $series_id})
                MERGE (s)-[:HAS_BOOK]->(b)
                WITH b
                MATCH (ir:IngestRun {series_id: $series_id, run_id: $run_id})
                MERGE (b)-[:HAS_INGEST_RUN]->(ir)
                """,
                series_id=series_id,
                book_index=book["book_index"],
                title=book["title"],
                path=book.get("path", ""),
                book_type=book.get("type", ""),
                generated_at=generated_at,
                contract_version=contract_version,
                source_hash_sha256=book.get("source_hash_sha256", ""),
                source_size_bytes=book.get("source_size_bytes"),
                source_mtime_utc=book.get("source_mtime_utc", ""),
                ingested_at=ingest_started_at,
                encoder_version=configuration.get("encoder_version", ""),
                analysis_model=configuration.get("analysis_model", ""),
                identity_model=configuration.get("identity_model", ""),
                analysis_mode=configuration.get("analysis_mode", ""),
                target_scene_words=configuration.get("target_scene_words"),
                run_id=run_id,
            )

        chapters = outputs.get("chapters", []) or []
        for chapter in chapters:
            chapter_book = book_map.get(int(chapter.get("book_index") or 0), primary_book)
            self._run(
                session,
                """
                MATCH (b:Book {series_id: $series_id, book_index: $book_index})
                MERGE (c:Chapter {series_id: $series_id, book_index: $bi, chapter_index: $ci})
                SET c.title = $title
                MERGE (b)-[:HAS_CHAPTER]->(c)
                """,
                series_id=series_id,
                book_index=chapter_book.get("book_index"),
                bi=chapter.get("book_index"),
                ci=chapter.get("chapter_index"),
                title=chapter.get("chapter_title", ""),
            )

        alias_map = ((outputs.get("identity_result") or {}).get("alias_map") or {})
        entity_registry = self._canonicalize_entity_registry(outputs.get("entity_registry", []) or [], alias_map=alias_map)
        canonical_context = self.normalizer.build_context(entity_registry=entity_registry, alias_map=alias_map)
        per_book_entity_stats = self._derive_book_entity_stats(
            resolved_scenes=outputs.get("resolved_scene_analyses") or outputs.get("scene_analyses") or [],
            context=canonical_context,
        )
        stable_character_states = self._derive_stable_character_states(outputs, alias_map=alias_map)
        for entity in entity_registry:
            name = self._resolve_entity_name(entity.get("name"), context=canonical_context)
            if not name:
                continue
            first_seen = entity.get("first_seen", {}) or {}
            entity_type = self._resolve_entity_type(
                name,
                entity.get("entity_type", "unknown"),
                descriptions=[row.get("description", "") for row in (entity.get("descriptions") or []) if isinstance(row, dict)],
                context=canonical_context,
            )
            self._run(
                session,
                """
                MERGE (e:Entity {series_id: $series_id, name: $name})
                SET e.entity_type = $entity_type,
                    e.first_seen_book = $fs_book,
                    e.first_seen_ch = $fs_ch,
                    e.first_seen_scene = $fs_scene
                """,
                series_id=series_id,
                name=name,
                entity_type=entity_type,
                fs_book=first_seen.get("book_index"),
                fs_ch=first_seen.get("chapter_index"),
                fs_scene=first_seen.get("scene_index"),
            )
            for book_index, stats in sorted((per_book_entity_stats.get(name) or {}).items()):
                self._run(
                    session,
                    """
                    MATCH (b:Book {series_id: $series_id, book_index: $book_index})
                    MATCH (e:Entity {series_id: $series_id, name: $name})
                    MERGE (b)-[r:HAS_ENTITY]->(e)
                    SET r.mention_count = $mention_count,
                        r.first_seen_book = $first_seen_book,
                        r.first_seen_ch = $first_seen_ch,
                        r.first_seen_scene = $first_seen_scene
                    """,
                    series_id=series_id,
                    book_index=book_index,
                    name=name,
                    mention_count=stats.get("mention_count", 0),
                    first_seen_book=book_index,
                    first_seen_ch=stats.get("first_seen_chapter"),
                    first_seen_scene=stats.get("first_seen_scene"),
                )
            descriptions = [
                row.get("description", "")
                for row in entity.get("descriptions", []) or []
                if row.get("description")
            ]
            if descriptions:
                self._run(
                    session,
                    "MATCH (e:Entity {series_id: $series_id, name: $name}) SET e.descriptions = $descs",
                    series_id=series_id,
                    name=name,
                    descs=descriptions,
                )
            stable_attrs = stable_character_states.get(name, {}) if entity_type == "character" else {}
            if stable_attrs:
                set_clauses = []
                params = {"series_id": series_id, "name": name}
                for key, value in stable_attrs.items():
                    safe = self._safe_key(key)
                    set_clauses.append(f"e.canon_{safe} = $attr_{safe}")
                    params[f"attr_{safe}"] = value
                self._run(
                    session,
                    f"MATCH (e:Entity {{series_id: $series_id, name: $name}}) SET {', '.join(set_clauses)}",
                    **params,
                )
            for state_change in entity.get("state_changes", []) or []:
                self._upsert_state_transition(session, series_id, name, state_change)

        for canonical_name, aliases in alias_map.items():
            resolved_canonical = self._resolve_entity_name(canonical_name, context=canonical_context, expect_character=True)
            if not resolved_canonical:
                continue
            self._run(
                session,
                "MERGE (e:Entity {series_id: $series_id, name: $name}) SET e.entity_type = coalesce(e.entity_type, 'character')",
                series_id=series_id,
                name=resolved_canonical,
            )
            for alias in aliases or []:
                resolved_alias = self.normalizer.canonicalize_candidate_name(alias)
                if not resolved_alias or resolved_alias == resolved_canonical:
                    continue
                self._run(
                    session,
                    """
                    MATCH (e:Entity {series_id: $series_id, name: $canonical})
                    MERGE (a:Alias {series_id: $series_id, text: $alias})
                    MERGE (e)-[:HAS_ALIAS]->(a)
                    """,
                    series_id=series_id,
                    canonical=resolved_canonical,
                    alias=resolved_alias,
                )

        transitions = ((outputs.get("state_result") or {}).get("transitions") or [])
        for transition in transitions:
            entity_name = self._resolve_entity_name(transition.get("entity_name"), context=canonical_context, expect_character=True)
            if entity_name:
                self._upsert_state_transition(session, series_id, entity_name, transition)

        for snapshot in outputs.get("canon_snapshot", []) or []:
            entity_name = self._resolve_entity_name(snapshot.get("entity_name"), context=canonical_context, expect_character=True)
            if not entity_name:
                continue
            attributes = snapshot.get("attributes", {}) or {}
            safe_attributes = self._stable_canon_snapshot_attributes(attributes)
            set_clauses = []
            params = {"name": entity_name}
            for key, value in safe_attributes.items():
                safe = self._safe_key(key)
                set_clauses.append(f"e.canon_{safe} = $attr_{safe}")
                params[f"attr_{safe}"] = value
            if set_clauses:
                self._run(
                    session,
                    f"MATCH (e:Entity {{series_id: $series_id, name: $name}}) SET {', '.join(set_clauses)}",
                    series_id=series_id,
                    **params,
                )
            self._run(
                session,
                """
                MATCH (e:Entity {series_id: $series_id, name: $name})
                MATCH (b:Book {series_id: $series_id, book_index: $book_index})
                MERGE (cs:CanonSnapshot {series_id: $series_id, entity_name: $name, book_index: $book_index})
                SET cs.attributes_json = $attributes_json,
                    cs.stable_attributes_json = $stable_attributes_json,
                    cs.recorded_at = datetime($recorded_at)
                MERGE (e)-[:HAS_CANON_SNAPSHOT]->(cs)
                MERGE (b)-[:HAS_CANON_SNAPSHOT]->(cs)
                """,
                series_id=series_id,
                name=entity_name,
                book_index=primary_book.get("book_index"),
                attributes_json=json.dumps(attributes, ensure_ascii=False),
                stable_attributes_json=json.dumps(safe_attributes, ensure_ascii=False),
                recorded_at=ingest_started_at,
            )

        resolved_scenes = outputs.get("resolved_scene_analyses") or outputs.get("scene_analyses") or []
        for scene in resolved_scenes:
            self._upsert_scene(session, series_id, scene, context=canonical_context)

        graph = ((outputs.get("causal_graph_result") or {}).get("graph") or {})
        graph_events = graph.get("events", []) or []
        scoped_event_lookup = {
            event.get("id"): self._event_key(series_id, event.get("book_index"), event.get("id", ""))
            for event in graph_events
            if event.get("id")
        }
        for event in graph_events:
            self._upsert_causal_event(session, series_id, event, context=canonical_context)

        critical_path = graph.get("critical_path", []) or []
        for order, critical in enumerate(critical_path):
            event_id = scoped_event_lookup.get(critical.get("event_id", ""))
            if not event_id:
                continue
            self._run(
                session,
                """
                MERGE (e:Event {series_id: $series_id, id: $event_id})
                SET e.is_critical = true,
                    e.why_critical = $why,
                    e.criticality_score = $score,
                    e.critical_order = $order
                """,
                series_id=series_id,
                event_id=event_id,
                why=critical.get("why_critical", ""),
                score=critical.get("criticality_score"),
                order=order,
            )
            if order < len(critical_path) - 1:
                next_id = scoped_event_lookup.get(critical_path[order + 1].get("event_id", ""))
                if next_id:
                    self._run(
                        session,
                        """
                        MATCH (a:Event {series_id: $series_id, id: $current})
                        MERGE (b:Event {series_id: $series_id, id: $next})
                        MERGE (a)-[r:CRITICAL_NEXT]->(b)
                        SET r.sequence = $sequence
                        """,
                        series_id=series_id,
                        current=event_id,
                        next=next_id,
                        sequence=order,
                    )

        for chain in graph.get("causal_chains", []) or []:
            chain_id = chain.get("chain_id")
            if not chain_id:
                continue
            self._run(
                session,
                """
                MERGE (cc:CausalChain {series_id: $series_id, chain_id: $chain_id})
                SET cc.description = $description,
                    cc.chain_type = $chain_type,
                    cc.story_function = $story_function
                """,
                series_id=series_id,
                chain_id=chain_id,
                description=chain.get("description", ""),
                chain_type=chain.get("chain_type", ""),
                story_function=chain.get("story_function", ""),
            )
            for event_id in chain.get("event_sequence", []) or []:
                scoped_event_id = scoped_event_lookup.get(event_id)
                if scoped_event_id:
                    self._run(
                        session,
                        """
                        MERGE (e:Event {series_id: $series_id, id: $event_id})
                        WITH e
                        MATCH (cc:CausalChain {series_id: $series_id, chain_id: $chain_id})
                        MERGE (e)-[:IN_CHAIN]->(cc)
                        """,
                        series_id=series_id,
                        event_id=scoped_event_id,
                        chain_id=chain_id,
                    )

        for divergence in graph.get("divergence_points", []) or []:
            event_id = scoped_event_lookup.get(divergence.get("event_id", ""))
            if not event_id:
                continue
            self._run(
                session,
                """
                MERGE (d:DivergencePoint {series_id: $series_id, event_id: $event_id})
                SET d.decision_made = $decision,
                    d.divergence_potential = $potential,
                    d.alternate_timeline = $alternate_timeline,
                    d.alternatives = $alternatives
                WITH d
                MATCH (e:Event {series_id: $series_id, id: $event_id})
                MERGE (e)-[:IS_DIVERGENCE_POINT]->(d)
                """,
                series_id=series_id,
                event_id=event_id,
                decision=divergence.get("decision_made", ""),
                potential=divergence.get("divergence_potential"),
                alternate_timeline=divergence.get("alternate_timeline", ""),
                alternatives=divergence.get("alternatives", []) or [],
            )

        for flexible in graph.get("flexible_events", []) or []:
            event_id = scoped_event_lookup.get(flexible.get("event_id", ""))
            if event_id:
                self._run(
                    session,
                    """
                    MERGE (e:Event {series_id: $series_id, id: $event_id})
                    SET e.is_flexible = true,
                        e.flexibility_score = $score,
                        e.why_flexible = $why
                    """,
                    series_id=series_id,
                    event_id=event_id,
                    score=flexible.get("flexibility_score"),
                    why=flexible.get("why_flexible", ""),
                )

        for timeline_row in outputs.get("timeline", []) or []:
            raw_event_id = timeline_row.get("event_id")
            event_id = self._event_key(series_id, timeline_row.get("book_index"), raw_event_id) if raw_event_id else ""
            if not event_id:
                continue
            self._run(
                session,
                """
                MERGE (e:Event {series_id: $series_id, id: $event_id})
                SET e.time_index = coalesce(e.time_index, $time_index),
                    e.timeline_summary = $summary
                """,
                series_id=series_id,
                event_id=event_id,
                time_index=timeline_row.get("time_index"),
                summary=timeline_row.get("summary", ""),
            )
            for character_name in timeline_row.get("characters", []) or []:
                resolved_name = self._resolve_entity_name(character_name, context=canonical_context, expect_character=True)
                if resolved_name:
                    self._link_entity_to_event(session, series_id, resolved_name, event_id, "INVOLVED_IN")

        for row in outputs.get("character_timelines", []) or []:
            character_name = self._resolve_entity_name(row.get("character"), context=canonical_context, expect_character=True)
            if not character_name:
                continue
            self._run(
                session,
                "MERGE (c:Entity {series_id: $series_id, name: $name}) SET c.entity_type = coalesce(c.entity_type, 'character')",
                series_id=series_id,
                name=character_name,
            )
            for event in row.get("events", []) or []:
                raw_event_id = event.get("event_id")
                event_id = self._event_key(series_id, event.get("book_index") or row.get("book_index") or 0, raw_event_id) if raw_event_id else ""
                if not event_id:
                    continue
                self._run(
                    session,
                    """
                    MERGE (e:Event {series_id: $series_id, id: $event_id})
                    SET e.time_index = coalesce(e.time_index, $time_index)
                    """,
                    series_id=series_id,
                    event_id=event_id,
                    time_index=event.get("time_index"),
                )
                self._link_entity_to_event(session, series_id, character_name, event_id, "INVOLVED_IN")

        relationship_summary_edges = self._ingest_relationship_summary(session, series_id, resolved_scenes)

        return {
            "status": f"SAGA contract ingested into {self.database}",
            "ingested": {
                "book": book_title,
                "books": len(books_meta),
                "chapters": len(chapters),
                "entities": len(entity_registry),
                "aliases": sum(max(0, len(aliases) - 1) for aliases in alias_map.values()),
                "state_transitions": len(transitions),
                "scenes": len(resolved_scenes),
                "causal_events": len(graph_events),
                "critical_path_events": len(critical_path),
                "causal_chains": len(graph.get("causal_chains", []) or []),
                "divergence_points": len(graph.get("divergence_points", []) or []),
                "timeline_entries": len(outputs.get("timeline", []) or []),
                "character_timelines": len(outputs.get("character_timelines", []) or []),
                "relationship_summary_edges": relationship_summary_edges,
                "flexible_events": len(graph.get("flexible_events", []) or []),
            },
        }

    def _derive_book_entity_stats(
        self,
        *,
        resolved_scenes: Iterable[Dict[str, Any]],
        context: CanonicalEntityContext | None = None,
    ) -> Dict[str, Dict[int, Dict[str, Any]]]:
        stats: Dict[str, Dict[int, Dict[str, Any]]] = {}
        for scene in resolved_scenes:
            book_index = int(scene.get("book_index") or 0)
            chapter_index = scene.get("chapter_index")
            scene_index = scene.get("scene_index")
            names: set[str] = set()
            for row in scene.get("entities_present", []) or []:
                raw_name = row.get("name")
                if not raw_name:
                    continue
                resolved = self._resolve_entity_name(
                    raw_name,
                    context=context,
                    expect_character=self._resolve_entity_type(
                        str(raw_name),
                        row.get("entity_type", ""),
                        context=context,
                    ) == "character",
                )
                if resolved:
                    names.add(resolved)
            for item in scene.get("canonical_characters", []) or []:
                if isinstance(item, dict):
                    name = (item.get("name") or "").strip()
                else:
                    name = str(item or "").strip()
                resolved = self._resolve_entity_name(name, context=context, expect_character=True)
                if resolved:
                    names.add(resolved)
            for name in names:
                per_book = stats.setdefault(name, {}).setdefault(book_index, {
                    "mention_count": 0,
                    "first_seen_chapter": chapter_index,
                    "first_seen_scene": scene_index,
                })
                per_book["mention_count"] += 1
                if per_book.get("first_seen_chapter") is None or (
                    chapter_index is not None and chapter_index < per_book.get("first_seen_chapter", chapter_index)
                ):
                    per_book["first_seen_chapter"] = chapter_index
                    per_book["first_seen_scene"] = scene_index
        return stats

    def _upsert_state_transition(self, session, series_id: str, entity_name: str, row: Dict[str, Any]) -> None:
        self._run(
            session,
            """
            MATCH (e:Entity {series_id: $series_id, name: $name})
            MERGE (st:StateTransition {
                series_id: $series_id,
                entity_name: $name,
                attribute: $attribute,
                book_index: $book_index,
                chapter_index: $chapter_index,
                scene_index: $scene_index
            })
            SET st.previous_state = $previous_state,
                st.new_state = $new_state,
                st.change_type = $change_type,
                st.evidence = $evidence,
                st.state_index = $state_index,
                st.is_stable_canon = $is_stable_canon
            MERGE (e)-[:HAD_STATE_CHANGE]->(st)
            """,
            series_id=series_id,
            name=entity_name,
            attribute=row.get("attribute", ""),
            book_index=row.get("book_index"),
            chapter_index=row.get("chapter_index"),
            scene_index=row.get("scene_index"),
            previous_state=row.get("previous_state", ""),
            new_state=row.get("new_state", ""),
            change_type=row.get("change_type", ""),
            evidence=row.get("evidence", ""),
            state_index=row.get("state_index"),
            is_stable_canon=self._safe_key(row.get("attribute", "")) in self.STABLE_CANON_ATTRIBUTES,
        )

    def _upsert_scene(
        self,
        session,
        series_id: str,
        scene: Dict[str, Any],
        *,
        context: CanonicalEntityContext | None = None,
    ) -> None:
        bi = scene.get("book_index")
        ci = scene.get("chapter_index")
        si = scene.get("scene_index")
        self._run(
            session,
            """
            MERGE (sc:Scene {series_id: $series_id, book_index: $book_index, chapter_index: $chapter_index, scene_index: $scene_index})
            SET sc.summary = $summary,
                sc.length = $length,
                sc.analysis_duration_s = $duration
            WITH sc
            MATCH (ch:Chapter {series_id: $series_id, book_index: $book_index, chapter_index: $chapter_index})
            MERGE (ch)-[:HAS_SCENE]->(sc)
            """,
            series_id=series_id,
            book_index=bi,
            chapter_index=ci,
            scene_index=si,
            summary=scene.get("scene_summary", ""),
            length=scene.get("length", 0),
            duration=scene.get("analysis_duration_seconds", 0.0),
        )
        location = scene.get("location") or {}
        if location.get("name"):
            location_name = self._resolve_entity_name(location.get("name"), context=context)
            if location_name:
                location_type = self._resolve_entity_type(
                    location_name,
                    location.get("entity_type", "location"),
                    descriptions=[location.get("description", "")],
                    context=context,
                )
                self._run(
                    session,
                    """
                    MERGE (l:Entity {series_id: $series_id, name: $name})
                    SET l.entity_type = $entity_type,
                        l.description = $description
                    WITH l
                    MATCH (sc:Scene {series_id: $series_id, book_index: $book_index, chapter_index: $chapter_index, scene_index: $scene_index})
                    MERGE (sc)-[:LOCATED_IN]->(l)
                    """,
                    series_id=series_id,
                    name=location_name,
                    entity_type=location_type,
                    description=location.get("description", ""),
                    book_index=bi,
                    chapter_index=ci,
                    scene_index=si,
                )
        for entity in scene.get("entities_present", []) or []:
            entity_name = self._resolve_entity_name(entity.get("name"), context=context)
            if not entity_name:
                continue
            entity_type = self._resolve_entity_type(
                entity_name,
                entity.get("entity_type", "character"),
                context=context,
            )
            self._run(
                session,
                """
                MERGE (e:Entity {series_id: $series_id, name: $name})
                SET e.entity_type = coalesce(e.entity_type, $entity_type)
                WITH e
                MATCH (sc:Scene {series_id: $series_id, book_index: $book_index, chapter_index: $chapter_index, scene_index: $scene_index})
                MERGE (sc)-[:FEATURES]->(e)
                """,
                series_id=series_id,
                name=entity_name,
                entity_type=entity_type,
                book_index=bi,
                chapter_index=ci,
                scene_index=si,
            )
        for event in scene.get("events", []) or []:
            raw_event_id = event.get("event_id")
            event_id = self._event_key(series_id, bi, raw_event_id) if raw_event_id else ""
            if not event_id:
                continue
            self._run(
                session,
                """
                MERGE (e:Event {series_id: $series_id, id: $event_id})
                SET e.description = $description,
                    e.event_type = $event_type,
                    e.book_index = $book_index,
                    e.chapter_index = $chapter_index,
                    e.scene_index = $scene_index
                WITH e
                MATCH (sc:Scene {series_id: $series_id, book_index: $book_index, chapter_index: $chapter_index, scene_index: $scene_index})
                MERGE (sc)-[:HAS_EVENT]->(e)
                """,
                series_id=series_id,
                event_id=event_id,
                description=event.get("description", ""),
                event_type=event.get("type", ""),
                book_index=bi,
                chapter_index=ci,
                scene_index=si,
            )
            for character_name in event.get("characters", []) or []:
                resolved_name = self._resolve_entity_name(character_name, context=context, expect_character=True)
                if resolved_name:
                    self._link_entity_to_event(session, series_id, resolved_name, event_id, "INVOLVED_IN")
        for change in scene.get("relationship_changes", []) or []:
            src = self._resolve_entity_name(change.get("source_entity"), context=context, expect_character=True)
            tgt = self._resolve_entity_name(change.get("target_entity"), context=context, expect_character=True)
            if not src or not tgt:
                continue
            self._run(
                session,
                """
                MATCH (sc:Scene {series_id: $series_id, book_index: $book_index, chapter_index: $chapter_index, scene_index: $scene_index})
                MERGE (src:Entity {series_id: $series_id, name: $src})
                SET src.entity_type = coalesce(src.entity_type, 'character')
                MERGE (tgt:Entity {series_id: $series_id, name: $tgt})
                SET tgt.entity_type = coalesce(tgt.entity_type, 'character')
                MERGE (rc:RelationshipChange {
                    series_id: $series_id,
                    source_entity: $src,
                    target_entity: $tgt,
                    book_index: $book_index,
                    chapter_index: $chapter_index,
                    scene_index: $scene_index
                })
                SET rc.relationship = $relationship,
                    rc.change = $change,
                    rc.evidence = $evidence
                MERGE (sc)-[:HAS_RELATIONSHIP_CHANGE]->(rc)
                MERGE (rc)-[:CHANGE_SOURCE]->(src)
                MERGE (rc)-[:CHANGE_TARGET]->(tgt)
                """,
                series_id=series_id,
                book_index=bi,
                chapter_index=ci,
                scene_index=si,
                src=src,
                tgt=tgt,
                relationship=change.get("relationship", ""),
                change=change.get("change", ""),
                evidence=change.get("evidence", ""),
            )

    def _upsert_causal_event(
        self,
        session,
        series_id: str,
        event: Dict[str, Any],
        *,
        context: CanonicalEntityContext | None = None,
    ) -> None:
        raw_event_id = event.get("id")
        event_id = self._event_key(series_id, event.get("book_index"), raw_event_id) if raw_event_id else ""
        if not event_id:
            return
        self._run(
            session,
            """
            MATCH (b:Book {series_id: $series_id, book_index: $book_index})
            MERGE (e:Event {series_id: $series_id, id: $event_id})
            SET e.description = $description,
                e.event_type = $event_type,
                e.story_impact = $story_impact,
                e.reversibility = $reversibility,
                e.time_index = $time_index,
                e.book_index = $book_index,
                e.chapter_index = $chapter_index,
                e.scene_index = $scene_index,
                e.source_summary = $source_summary
            MERGE (b)-[:HAS_EVENT]->(e)
            """,
            series_id=series_id,
            event_id=event_id,
            description=event.get("description", ""),
            event_type=event.get("event_type", ""),
            story_impact=event.get("story_impact"),
            reversibility=event.get("reversibility"),
            time_index=event.get("time_index"),
            book_index=event.get("book_index"),
            chapter_index=event.get("chapter_index"),
            scene_index=event.get("scene_index"),
            source_summary=event.get("source_summary", ""),
        )
        for character_name in event.get("characters", []) or []:
            resolved_name = self._resolve_entity_name(character_name, context=context, expect_character=True)
            if resolved_name:
                self._link_entity_to_event(session, series_id, resolved_name, event_id, "INVOLVED_IN")
        for rel_key, rel_type in (
            ("causes", "CAUSES"),
            ("caused_by", "CAUSED_BY"),
            ("prevents", "PREVENTS"),
            ("required_for", "REQUIRED_FOR"),
        ):
            for linked in event.get(rel_key, []) or []:
                target_id = self._event_key(series_id, event.get("book_index"), linked.get("event_id", "")) if linked.get("event_id") else ""
                if target_id:
                    self._run(
                        session,
                        f"""
                        MATCH (a:Event {{series_id: $series_id, id: $from_id}})
                        MERGE (b:Event {{series_id: $series_id, id: $to_id}})
                        MERGE (a)-[r:{rel_type}]->(b)
                        SET r.explanation = $explanation
                        """,
                        series_id=series_id,
                        from_id=event_id,
                        to_id=target_id,
                        explanation=linked.get("explanation", "") or linked.get("why_required", ""),
                    )

    def _ingest_relationship_summary(self, session, series_id: str, scenes: Iterable[Dict[str, Any]]) -> int:
        count = 0
        sorted_scenes = sorted(
            scenes,
            key=lambda item: (
                item.get("book_index", 0),
                item.get("chapter_index", 0),
                item.get("scene_index", 0),
            ),
        )
        for scene in sorted_scenes:
            for change in scene.get("relationship_changes", []) or []:
                src = change.get("source_entity")
                tgt = change.get("target_entity")
                if not src or not tgt:
                    continue
                self._run(
                    session,
                    """
                    MERGE (a:Entity {series_id: $series_id, name: $src})
                    SET a.entity_type = coalesce(a.entity_type, 'character')
                    MERGE (b:Entity {series_id: $series_id, name: $tgt})
                    SET b.entity_type = coalesce(b.entity_type, 'character')
                    MERGE (a)-[r:HAS_RELATIONSHIP {pair: $pair}]->(b)
                    SET r.type = $rel_type,
                        r.latest_change = $change,
                        r.latest_evidence = $evidence,
                        r.last_seen_book = $book_index,
                        r.last_seen_ch = $chapter_index,
                        r.last_seen_scene = $scene_index
                    """,
                    series_id=series_id,
                    src=src,
                    tgt=tgt,
                    pair=f"{min(src, tgt)}|{max(src, tgt)}",
                    rel_type=self._relationship_type(change.get("relationship", "")),
                    change=change.get("change", ""),
                    evidence=change.get("evidence", ""),
                    book_index=scene.get("book_index"),
                    chapter_index=scene.get("chapter_index"),
                    scene_index=scene.get("scene_index"),
                )
                count += 1
        return count

    def _link_entity_to_event(self, session, series_id: str, entity_name: str, event_id: str, rel_type: str) -> None:
        self._run(
            session,
            f"""
            MERGE (c:Entity {{series_id: $series_id, name: $name}})
            SET c.entity_type = coalesce(c.entity_type, 'character')
            WITH c
            MATCH (e:Event {{series_id: $series_id, id: $event_id}})
            MERGE (c)-[:{rel_type}]->(e)
            """,
            series_id=series_id,
            name=entity_name,
            event_id=event_id,
        )

    def _canonicalize_entity_registry(
        self,
        entity_registry: List[Dict[str, Any]],
        *,
        alias_map: Dict[str, List[str]],
    ) -> List[Dict[str, Any]]:
        context = self.normalizer.build_context(entity_registry=entity_registry, alias_map=alias_map)
        merged: Dict[str, Dict[str, Any]] = {}
        for row in entity_registry:
            name = self._resolve_entity_name(row.get("name"), context=context)
            if not name:
                continue
            entity_type = self._resolve_entity_type(
                name,
                row.get("entity_type", ""),
                descriptions=[entry.get("description", "") for entry in (row.get("descriptions") or []) if isinstance(entry, dict)],
                context=context,
            )
            current = merged.setdefault(name, json.loads(json.dumps(row)))
            current["name"] = name
            current["entity_type"] = entity_type
            descriptions = list(current.get("descriptions") or [])
            for entry in row.get("descriptions") or []:
                if entry not in descriptions:
                    descriptions.append(entry)
            current["descriptions"] = descriptions
            state_changes = list(current.get("state_changes") or [])
            for entry in row.get("state_changes") or []:
                if entry not in state_changes:
                    state_changes.append(entry)
            current["state_changes"] = state_changes
        return sorted(merged.values(), key=lambda item: (int((item.get("first_seen") or {}).get("book_index") or 0), item.get("name", "")))

    def _canonicalize_outputs_payload(self, outputs: Dict[str, Any]) -> Dict[str, Any]:
        payload = json.loads(json.dumps(outputs or {}))
        identity_result = dict(payload.get("identity_result") or {})
        raw_alias_map = dict(identity_result.get("alias_map") or {})
        cleaned_alias_map: Dict[str, List[str]] = {}
        for canonical, aliases in raw_alias_map.items():
            canonical_name = self.normalizer.canonicalize_candidate_name(canonical)
            if not canonical_name:
                continue
            bucket = cleaned_alias_map.setdefault(canonical_name, [canonical_name])
            for alias in aliases or []:
                alias_name = self.normalizer.canonicalize_candidate_name(alias)
                if not alias_name or alias_name == canonical_name:
                    continue
                if alias_name not in bucket:
                    bucket.append(alias_name)
        identity_result["alias_map"] = cleaned_alias_map
        payload["identity_result"] = identity_result

        names = self.normalizer.collect_named_values(payload)
        for canonical, aliases in cleaned_alias_map.items():
            names.append(canonical)
            names.extend(aliases or [])
        merge_map, _ = self.normalizer.build_merge_map(names=names, alias_map=cleaned_alias_map)
        payload = self._remap_named_payload(payload, merge_map)
        payload["entity_registry"] = self._canonicalize_entity_registry(
            payload.get("entity_registry") or [],
            alias_map=((payload.get("identity_result") or {}).get("alias_map") or {}),
        )
        self._clean_character_scoped_payloads(payload)
        return payload

    def _remap_named_payload(self, payload: Any, merge_map: Dict[str, str]) -> Any:
        if isinstance(payload, list):
            return [self._remap_named_payload(item, merge_map) for item in payload]
        if isinstance(payload, dict):
            repaired: Dict[str, Any] = {}
            for key, value in payload.items():
                if key == "alias_map" and isinstance(value, dict):
                    repaired[key] = self._repair_alias_map(value, merge_map)
                    continue
                if key in {"name", "entity_name", "character", "source_entity", "target_entity", "entity_a", "entity_b"} and isinstance(value, str):
                    repaired[key] = merge_map.get(value, value)
                    continue
                if key in {"characters", "canonical_characters"} and isinstance(value, list):
                    repaired[key] = self._remap_name_list(value, merge_map)
                    continue
                repaired[key] = self._remap_named_payload(value, merge_map)
            return repaired
        return payload

    def _repair_alias_map(self, alias_map: Dict[str, List[str]], merge_map: Dict[str, str]) -> Dict[str, List[str]]:
        repaired: Dict[str, List[str]] = {}
        for canonical, aliases in (alias_map or {}).items():
            target = merge_map.get(canonical, canonical)
            target = self.normalizer.canonicalize_candidate_name(target)
            if not target:
                continue
            bucket = repaired.setdefault(target, [target])
            for alias in aliases or []:
                resolved_alias = merge_map.get(alias, alias)
                resolved_alias = self.normalizer.canonicalize_candidate_name(resolved_alias)
                if not resolved_alias or resolved_alias == target:
                    continue
                if resolved_alias not in bucket:
                    bucket.append(resolved_alias)
        return repaired

    def _remap_name_list(self, values: List[Any], merge_map: Dict[str, str]) -> List[Any]:
        repaired = []
        for item in values or []:
            if isinstance(item, str):
                remapped = merge_map.get(item, item)
                remapped = self.normalizer.canonicalize_candidate_name(remapped)
                if remapped and not self.normalizer.is_bad_alias_like_name(remapped):
                    repaired.append(remapped)
            elif isinstance(item, dict):
                remapped = dict(item)
                if "name" in remapped:
                    remapped_name = merge_map.get(str(remapped.get("name") or ""), str(remapped.get("name") or ""))
                    remapped_name = self.normalizer.canonicalize_candidate_name(remapped_name)
                    if remapped_name and not self.normalizer.is_bad_alias_like_name(remapped_name):
                        remapped["name"] = remapped_name
                        repaired.append(remapped)
                else:
                    repaired.append(remapped)
            else:
                repaired.append(item)
        return repaired

    def _clean_character_scoped_payloads(self, outputs: Dict[str, Any]) -> None:
        alias_map = ((outputs.get("identity_result") or {}).get("alias_map") or {})
        context = self.normalizer.build_context(
            entity_registry=outputs.get("entity_registry") or [],
            alias_map=alias_map,
        )
        allowed_characters = set(context.known_characters.values())

        def _clean_character_list(values: List[Any]) -> List[Any]:
            cleaned: List[Any] = []
            seen = set()
            for item in values or []:
                if isinstance(item, dict):
                    resolved = self.normalizer.resolve_name(item.get("name", ""), context=context, expect_character=True)
                    if not resolved or resolved not in allowed_characters or resolved in seen:
                        continue
                    remapped = dict(item)
                    remapped["name"] = resolved
                    cleaned.append(remapped)
                    seen.add(resolved)
                    continue
                resolved = self.normalizer.resolve_name(str(item or ""), context=context, expect_character=True)
                if not resolved or resolved not in allowed_characters or resolved in seen:
                    continue
                cleaned.append(resolved)
                seen.add(resolved)
            return cleaned

        for timeline_row in outputs.get("timeline", []) or []:
            timeline_row["characters"] = _clean_character_list(timeline_row.get("characters") or [])
        for row in outputs.get("character_timelines", []) or []:
            row["character"] = self.normalizer.resolve_name(row.get("character", ""), context=context, expect_character=True)
        outputs["character_timelines"] = [row for row in (outputs.get("character_timelines") or []) if row.get("character")]
        for row in outputs.get("stable_character_states", []) or []:
            row["entity_name"] = self.normalizer.resolve_name(row.get("entity_name", ""), context=context, expect_character=True)
        outputs["stable_character_states"] = [
            row for row in (outputs.get("stable_character_states") or []) if row.get("entity_name")
        ]
        for scene_bucket in ("resolved_scene_analyses", "scene_analyses"):
            for scene in outputs.get(scene_bucket, []) or []:
                scene["canonical_characters"] = _clean_character_list(scene.get("canonical_characters") or [])
                for event in scene.get("events", []) or []:
                    event["characters"] = _clean_character_list(event.get("characters") or [])
        for event in (((outputs.get("causal_graph_result") or {}).get("graph") or {}).get("events") or []):
            event["characters"] = _clean_character_list(event.get("characters") or [])

    def _resolve_entity_name(
        self,
        raw_name: Any,
        *,
        context: CanonicalEntityContext | None,
        expect_character: bool = False,
    ) -> str:
        if raw_name is None:
            return ""
        if context is None:
            cleaned = self.normalizer.canonicalize_candidate_name(str(raw_name))
            if not cleaned:
                return ""
            if expect_character and not self.normalizer.looks_like_character_name(cleaned):
                return ""
            return cleaned
        return self.normalizer.resolve_name(str(raw_name), context=context, expect_character=expect_character)

    def _resolve_entity_type(
        self,
        name: str,
        raw_type: str,
        *,
        descriptions: Optional[List[str]] = None,
        context: CanonicalEntityContext | None = None,
    ) -> str:
        existing = ""
        if context is not None:
            existing = context.entity_types.get(name, "")
        return self.normalizer.infer_entity_type(
            name,
            existing_type=existing or str(raw_type or ""),
            descriptions=descriptions,
        )

    def _relationship_type(self, value: str) -> str:
        cleaned = (value or "RELATED_TO").strip().upper()
        return cleaned.replace(" ", "_").replace("-", "_").replace("/", "_")

    def _stable_canon_snapshot_attributes(self, attributes: Dict[str, Any]) -> Dict[str, Any]:
        stable: Dict[str, Any] = {}
        for key, value in (attributes or {}).items():
            safe_key = self._safe_key(key)
            if safe_key not in self.STABLE_CANON_ATTRIBUTES:
                continue
            if isinstance(value, str) and value.strip():
                stable[key] = value.strip()
        return stable

    def _derive_stable_character_states(self, outputs: Dict[str, Any], *, alias_map: Dict[str, List[str]]) -> Dict[str, Dict[str, str]]:
        provided = outputs.get("stable_character_states") or []
        if provided:
            rows = provided
        else:
            rows = self.stable_state_builder.build(
                character_profiles=outputs.get("character_profiles") or [],
                identity_result=outputs.get("identity_result") or {"alias_map": alias_map},
                canon_snapshot=outputs.get("canon_snapshot") or [],
                state_result=outputs.get("state_result") or {},
            )
        by_name: Dict[str, Dict[str, str]] = {}
        for row in rows or []:
            entity_name = str(row.get("entity_name") or "").strip()
            resolved_name = self._resolve_alias_name(entity_name, alias_map)
            if not resolved_name:
                continue
            attrs = self._stable_canon_snapshot_attributes(row.get("attributes") or {})
            if attrs:
                existing = by_name.setdefault(resolved_name, {})
                existing.update(attrs)
        return by_name

    def _resolve_alias_name(self, name: str, alias_map: Dict[str, List[str]]) -> str:
        if not name:
            return ""
        lowered = name.lower()
        for canonical, aliases in (alias_map or {}).items():
            names = [canonical, *(aliases or [])]
            if lowered in {str(item or "").strip().lower() for item in names}:
                return canonical
        canonical = self.normalizer.canonicalize_candidate_name(name)
        return canonical or name

    def _safe_key(self, value: str) -> str:
        return str(value or "").strip().replace(" ", "_").replace("-", "_").replace("/", "_")

    def _slugify(self, value: str) -> str:
        cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value or "").strip())
        while "--" in cleaned:
            cleaned = cleaned.replace("--", "-")
        return cleaned.strip("-") or "standalone-series"
