"""Build narrative retrieval context directly from persisted Neo4j graph data."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any, Dict, List

from core.canon_normalization import CanonicalEntityNormalizer
from infrastructure.neo4j_ingestion_service import Neo4jIngestionService


class Neo4jNarrativeContextService(Neo4jIngestionService):
    """Query Neo4j for decoder-ready narrative context."""

    GENERIC_ALIAS_LABELS = {
        "father",
        "mother",
        "my father",
        "my mother",
        "my brother",
        "my sister",
        "the narrator",
        "narrator",
        "the male",
        "the female",
    }

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

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.normalizer = CanonicalEntityNormalizer()

    def build_from_graph(
        self,
        book_title: str | None = None,
        *,
        series_id: str | None = None,
        book_titles: List[str] | None = None,
        top_characters: int = 10,
        top_threads: int = 8,
        top_flexible_events: int = 5,
        top_character_trajectories: int = 6,
    ) -> Dict[str, Any]:
        requested_titles = [title for title in (book_titles or ([] if not book_title else [book_title])) if title]
        if not series_id and not requested_titles:
            raise ValueError("Provide at least one book title or a series_id for Neo4j retrieval.")

        driver = self._ensure_driver()
        self.probe_connection()
        session_kwargs = {"database": self.database} if self.database else {}
        try:
            with driver.session(**session_kwargs) as session:
                scope = self._require_scope(session, series_id=series_id, book_titles=requested_titles)
                alias_lookup = self._load_alias_lookup(
                    session,
                    series_id=series_id or (scope["matched_series_ids"][0] if len(scope["matched_series_ids"]) == 1 else ""),
                )
                story_ending = {
                    "last_scene": self._clean_last_scene(
                        self._last_scene(session, series_id=series_id, book_titles=requested_titles),
                        alias_lookup=alias_lookup,
                    ),
                    "critical_path_tail": self._critical_path_tail(session, series_id=series_id, book_titles=requested_titles),
                }
                raw_character_states = self._character_states(
                    session,
                    series_id=series_id,
                    book_titles=requested_titles,
                    top_characters=max(top_characters * 4, top_characters),
                )
                character_states = self._clean_character_states(
                    raw_character_states,
                    alias_lookup=alias_lookup,
                    top_characters=top_characters,
                    use_props_fallback=len(scope.get("matched_titles", [])) <= 1,
                    target_recent_book_index=max(scope.get("matched_book_indices", []) or [0]) or None,
                )
                relationship_summary = self._clean_relationship_summary(
                    self._relationship_summary(session, series_id=series_id, book_titles=requested_titles),
                    alias_lookup=alias_lookup,
                )
                unresolved_threads = self._unresolved_threads(
                    session,
                    series_id=series_id,
                    book_titles=requested_titles,
                    top_threads=top_threads,
                )
                causal_chains = self._causal_chains(session, series_id=series_id, book_titles=requested_titles)
                flexible_events = self._flexible_events(
                    session,
                    series_id=series_id,
                    book_titles=requested_titles,
                    top_flexible_events=top_flexible_events,
                )
                trajectories = self._clean_character_trajectories(
                    self._character_trajectories(
                        session,
                        series_id=series_id,
                        book_titles=requested_titles,
                        top_character_trajectories=top_character_trajectories,
                    ),
                    alias_lookup=alias_lookup,
                )
                retrieval_documents = self._retrieval_documents(
                    session,
                    series_id=series_id,
                    book_titles=requested_titles,
                    alias_lookup=alias_lookup,
                    trajectories=trajectories,
                    unresolved_threads=unresolved_threads,
                )
        except ValueError:
            raise
        except Exception as exc:  # pragma: no cover - live driver behavior
            self._raise_connection_error(exc)
            raise

        warnings = self._sanity_warnings(
            scope=scope,
            story_ending=story_ending,
            character_states=character_states,
            requested_titles=requested_titles,
        )
        if not character_states:
            raise ValueError("Neo4j retrieval returned no character state for the requested scope. The corpus may be empty or under-ingested.")

        return {
            "meta": {
                "retrieval_type": "sequel_setup_neo4j",
                "book_title": self._meta_book_title(scope=scope, requested_titles=requested_titles),
                "series_id": series_id or "",
                "book_titles": requested_titles,
                "matched_book_titles": scope["matched_titles"],
                "matched_series_ids": scope["matched_series_ids"],
                "database": self.database,
                "uri": self.uri,
                "retrieval_warnings": warnings,
            },
            "story_ending": story_ending,
            "character_states": character_states,
            "relationship_summary": relationship_summary,
            "unresolved_threads": unresolved_threads,
            "causal_chains": causal_chains,
            "flexible_events": flexible_events,
            "character_trajectories": trajectories,
            "retrieval_documents": retrieval_documents,
            "stats": {
                "critical_ending_events": len(story_ending["critical_path_tail"]),
                "characters_retrieved": len(character_states),
                "relationship_pairs": len(relationship_summary),
                "unresolved_threads": len(unresolved_threads),
                "causal_chains": len(causal_chains),
                "flexible_events": len(flexible_events),
                "retrieval_documents": len(retrieval_documents),
            },
        }

    def _meta_book_title(self, *, scope: Dict[str, Any], requested_titles: List[str]) -> str:
        if len(requested_titles) == 1:
            return requested_titles[0]
        matched = [title for title in scope.get("matched_titles", []) if title]
        if matched:
            return matched[-1]
        return ""

    def _book_filter(self, *, series_id: str | None, book_titles: List[str]) -> tuple[str, Dict[str, Any]]:
        clauses = []
        params: Dict[str, Any] = {"book_titles": book_titles}
        if series_id:
            clauses.append("b.series_id = $series_id")
            params["series_id"] = series_id
        if book_titles:
            clauses.append("b.title IN $book_titles")
        if not clauses:
            clauses.append("true")
        return " AND ".join(clauses), params

    def _require_scope(self, session, *, series_id: str | None, book_titles: List[str]) -> Dict[str, Any]:
        where, params = self._book_filter(series_id=series_id, book_titles=book_titles)
        rows = [
            row.data()
            for row in session.run(
                f"MATCH (b:Book) WHERE {where} RETURN b.title AS title, b.series_id AS series_id, b.book_index AS book_index ORDER BY b.book_index ASC",
                **params,
            )
        ]
        if not rows:
            scope = series_id or ", ".join(book_titles)
            raise ValueError(f"Requested retrieval scope '{scope}' was not found in Neo4j database '{self.database}'.")
        matched_series_ids = sorted({row.get("series_id", "") for row in rows if row.get("series_id")})
        if not series_id and len(matched_series_ids) > 1:
            raise ValueError(
                "Requested book titles span multiple persisted series. Provide --series-id to avoid mixed-series retrieval contamination."
            )
        return {
            "matched_titles": [row.get("title", "") for row in rows],
            "matched_series_ids": matched_series_ids,
            "matched_book_indices": [row.get("book_index") for row in rows if row.get("book_index") is not None],
        }

    def _sanity_warnings(
        self,
        *,
        scope: Dict[str, Any],
        story_ending: Dict[str, Any],
        character_states: List[Dict[str, Any]],
        requested_titles: List[str],
    ) -> List[str]:
        warnings: List[str] = []
        if requested_titles and len(scope.get("matched_titles", [])) < len(requested_titles):
            warnings.append("Some requested book titles were not found in the persisted corpus.")
        if len(scope.get("matched_titles", [])) == 1 and len(character_states) < 2:
            warnings.append("Very small retrieval scope: fewer than two characters were recovered.")
        if not (story_ending.get("critical_path_tail") or []):
            warnings.append("No critical-path events were recovered for this retrieval scope.")
        return warnings

    def _last_scene(self, session, *, series_id: str | None, book_titles: List[str]) -> Dict[str, Any]:
        where, params = self._book_filter(series_id=series_id, book_titles=book_titles)
        row = session.run(
            f"""
            MATCH (b:Book)-[:HAS_CHAPTER]->(:Chapter)-[:HAS_SCENE]->(sc:Scene)
            WHERE {where}
            OPTIONAL MATCH (sc)-[:LOCATED_IN]->(loc:Entity)
            OPTIONAL MATCH (sc)-[:FEATURES]->(ent:Entity)
            WITH sc, loc, collect(DISTINCT {{name: ent.name, entity_type: ent.entity_type}}) AS entities
            RETURN sc.summary AS summary,
                   sc.book_index AS book_index,
                   sc.chapter_index AS chapter_index,
                   sc.scene_index AS scene_index,
                   CASE WHEN loc IS NULL THEN {{}} ELSE {{name: loc.name, entity_type: loc.entity_type, description: coalesce(loc.description, '')}} END AS location,
                   entities AS entities_present
            ORDER BY sc.book_index DESC, sc.chapter_index DESC, sc.scene_index DESC
            LIMIT 1
            """,
            **params,
        ).single()
        return row.data() if row else {}

    def _critical_path_tail(self, session, *, series_id: str | None, book_titles: List[str]) -> List[Dict[str, Any]]:
        where, params = self._book_filter(series_id=series_id, book_titles=book_titles)
        rows = session.run(
            f"""
            MATCH (b:Book)-[:HAS_EVENT]->(e:Event)
            WHERE {where} AND e.is_critical = true
            RETURN e.id AS id,
                   e.description AS description,
                   e.chapter_index AS chapter,
                   e.criticality_score AS score,
                   e.why_critical AS why_critical,
                   e.critical_order AS order,
                   e.story_impact AS story_impact
            ORDER BY e.critical_order ASC, e.book_index ASC, e.chapter_index ASC
            """,
            **params,
        )
        return [row.data() for row in rows][-10:]

    def _character_states(
        self,
        session,
        *,
        series_id: str | None,
        book_titles: List[str],
        top_characters: int,
    ) -> List[Dict[str, Any]]:
        where, params = self._book_filter(series_id=series_id, book_titles=book_titles)
        rows = session.run(
            f"""
            MATCH (b:Book)-[he:HAS_ENTITY]->(e:Entity {{entity_type: 'character'}})
            WHERE {where}
            WITH e,
                 sum(coalesce(he.mention_count, 0)) AS total_mentions,
                 min(he.first_seen_ch) AS first_seen_chapter,
                 max(b.book_index) AS latest_book_index
            CALL (e) {{
                OPTIONAL MATCH (e)-[:HAS_ALIAS]->(a:Alias)
                RETURN collect(DISTINCT a.text) AS aliases
            }}
            CALL (e) {{
                OPTIONAL MATCH (e)-[:HAD_STATE_CHANGE]->(st:StateTransition)
                RETURN collect(DISTINCT {{
                    attribute: st.attribute,
                    previous_state: st.previous_state,
                    new_state: st.new_state,
                    change_type: st.change_type,
                    evidence: st.evidence,
                    chapter: st.chapter_index,
                    book_index: st.book_index
                }}) AS transitions
            }}
            RETURN e.name AS name,
                   total_mentions AS mention_count,
                   first_seen_chapter AS first_seen_chapter,
                   latest_book_index AS latest_book_index,
                   coalesce(e.descriptions, []) AS descriptions,
                   aliases AS aliases,
                   transitions AS state_transitions,
                   properties(e) AS props
            ORDER BY mention_count DESC, name ASC
            LIMIT $limit
            """,
            **{**params, "limit": top_characters},
        )
        return [row.data() for row in rows]

    def _relationship_summary(self, session, *, series_id: str | None, book_titles: List[str]) -> List[Dict[str, Any]]:
        where, params = self._book_filter(series_id=series_id, book_titles=book_titles)
        rows = session.run(
            f"""
            MATCH (b:Book)-[:HAS_ENTITY]->(a:Entity)-[r:HAS_RELATIONSHIP]->(c:Entity)
            WHERE {where}
            RETURN a.name AS entity_a,
                   c.name AS entity_b,
                   r.type AS relationship_type,
                   r.latest_change AS latest_change,
                   r.latest_evidence AS evidence,
                   r.last_seen_ch AS last_seen_chapter
            ORDER BY r.last_seen_ch DESC, entity_a ASC, entity_b ASC
            LIMIT 15
            """,
            **params,
        )
        return [row.data() for row in rows]

    def _unresolved_threads(
        self,
        session,
        *,
        series_id: str | None,
        book_titles: List[str],
        top_threads: int,
    ) -> List[Dict[str, Any]]:
        where, params = self._book_filter(series_id=series_id, book_titles=book_titles)
        divergence_rows = [
            row.data()
            for row in session.run(
                f"""
                MATCH (b:Book)-[:HAS_EVENT]->(e:Event)-[:IS_DIVERGENCE_POINT]->(d:DivergencePoint)
                WHERE {where}
                RETURN d.event_id AS event_id,
                       e.description AS event_description,
                       e.chapter_index AS chapter,
                       e.book_index AS book_index,
                       e.is_critical AS is_critical,
                       d.decision_made AS decision_made,
                       d.alternatives AS alternatives,
                       d.divergence_potential AS divergence_potential,
                       d.alternate_timeline AS alternate_timeline,
                       'historical_branch' AS thread_type
                ORDER BY e.book_index DESC, e.chapter_index DESC
                """,
                **params,
            )
        ]
        event_rows = [
            row.data()
            for row in session.run(
                f"""
                MATCH (b:Book)-[:HAS_EVENT]->(e:Event)
                WHERE {where}
                  AND (
                    coalesce(e.is_flexible, false) = true
                    OR coalesce(e.is_critical, false) = true
                    OR coalesce(e.story_impact, 0) >= 7
                  )
                RETURN e.id AS event_id,
                       e.description AS event_description,
                       e.chapter_index AS chapter,
                       e.book_index AS book_index,
                       e.is_critical AS is_critical,
                       '' AS decision_made,
                       [] AS alternatives,
                       coalesce(e.flexibility_score, e.story_impact, 0) AS divergence_potential,
                       '' AS alternate_timeline,
                       CASE
                           WHEN toLower(coalesce(e.description, '')) CONTAINS 'war'
                                OR toLower(coalesce(e.description, '')) CONTAINS 'court'
                                OR toLower(coalesce(e.description, '')) CONTAINS 'ministry'
                                OR toLower(coalesce(e.description, '')) CONTAINS 'queen'
                                OR toLower(coalesce(e.description, '')) CONTAINS 'politic'
                               THEN 'political_tension'
                           WHEN toLower(coalesce(e.description, '')) CONTAINS 'bond'
                                OR toLower(coalesce(e.description, '')) CONTAINS 'mate'
                                OR toLower(coalesce(e.description, '')) CONTAINS 'romance'
                               THEN 'relationship_tension'
                           WHEN toLower(coalesce(e.description, '')) CONTAINS 'prison'
                                OR toLower(coalesce(e.description, '')) CONTAINS 'dusk'
                                OR toLower(coalesce(e.description, '')) CONTAINS 'gate'
                                OR toLower(coalesce(e.description, '')) CONTAINS 'world'
                                OR toLower(coalesce(e.description, '')) CONTAINS 'koschei'
                                OR toLower(coalesce(e.description, '')) CONTAINS 'seer'
                               THEN 'magical_threat'
                           ELSE 'active_hook'
                       END AS thread_type
                ORDER BY e.book_index DESC, e.chapter_index DESC
                LIMIT $limit
                """,
                **{**params, "limit": max(top_threads * 3, top_threads)},
            )
        ]
        merged: Dict[str, Dict[str, Any]] = {}
        for row in event_rows + divergence_rows:
            event_id = str(row.get("event_id") or "").strip()
            if not event_id:
                continue
            score = self._thread_priority_score(row)
            existing = merged.get(event_id)
            if existing is None or score > existing["_score"]:
                merged[event_id] = {**row, "_score": score}
        ranked = sorted(merged.values(), key=lambda item: item.get("_score", 0), reverse=True)
        return [{key: value for key, value in item.items() if key != "_score"} for item in ranked[:top_threads]]

    def _thread_priority_score(self, row: Dict[str, Any]) -> int:
        thread_type = str(row.get("thread_type") or "")
        base = {
            "magical_threat": 40,
            "political_tension": 34,
            "relationship_tension": 30,
            "active_hook": 24,
            "historical_branch": 8,
        }.get(thread_type, 12)
        if row.get("is_critical"):
            base += 8
        base += int(row.get("divergence_potential") or 0)
        base += int(row.get("book_index") or 0) * 2
        base += int(row.get("chapter") or 0) // 5
        return base

    def _causal_chains(self, session, *, series_id: str | None, book_titles: List[str]) -> List[Dict[str, Any]]:
        where, params = self._book_filter(series_id=series_id, book_titles=book_titles)
        rows = session.run(
            f"""
            MATCH (b:Book)-[:HAS_EVENT]->(e:Event)-[:IN_CHAIN]->(cc:CausalChain)
            WHERE {where}
            WITH cc, e
            ORDER BY e.book_index ASC, e.time_index ASC
            WITH cc, collect({{
                event_id: e.id,
                description: e.description,
                chapter: e.chapter_index,
                time_index: e.time_index
            }}) AS events
            RETURN cc.chain_id AS chain_id,
                   cc.description AS description,
                   cc.chain_type AS chain_type,
                   cc.story_function AS story_function,
                   events AS events
            """,
            **params,
        )
        return [row.data() for row in rows]

    def _flexible_events(
        self,
        session,
        *,
        series_id: str | None,
        book_titles: List[str],
        top_flexible_events: int,
    ) -> List[Dict[str, Any]]:
        where, params = self._book_filter(series_id=series_id, book_titles=book_titles)
        rows = session.run(
            f"""
            MATCH (b:Book)-[:HAS_EVENT]->(e:Event)
            WHERE {where} AND e.is_flexible = true
            RETURN e.id AS event_id,
                   e.description AS description,
                   e.chapter_index AS chapter,
                   e.flexibility_score AS flexibility_score,
                   e.why_flexible AS why_flexible
            ORDER BY e.flexibility_score DESC, e.book_index DESC, e.chapter_index DESC
            LIMIT $limit
            """,
            **{**params, "limit": top_flexible_events},
        )
        return [row.data() for row in rows]

    def _character_trajectories(
        self,
        session,
        *,
        series_id: str | None,
        book_titles: List[str],
        top_character_trajectories: int,
    ) -> List[Dict[str, Any]]:
        where, params = self._book_filter(series_id=series_id, book_titles=book_titles)
        rows = session.run(
            f"""
            MATCH (b:Book)-[:HAS_ENTITY]->(c:Entity {{entity_type: 'character'}})-[:INVOLVED_IN]->(e:Event)
            WHERE {where}
            WITH c, e
            ORDER BY e.book_index DESC, e.time_index DESC
            WITH c, collect({{summary: e.description, time_index: e.time_index}})[..5] AS last_events
            RETURN c.name AS character, last_events
            ORDER BY size(last_events) DESC, character ASC
            LIMIT $limit
            """,
            **{**params, "limit": top_character_trajectories},
        )
        return [row.data() for row in rows]

    def _retrieval_documents(
        self,
        session,
        *,
        series_id: str | None,
        book_titles: List[str],
        alias_lookup: Dict[str, str],
        trajectories: List[Dict[str, Any]],
        unresolved_threads: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        documents: List[Dict[str, Any]] = []
        documents.extend(
            self._scene_retrieval_documents(
                session,
                series_id=series_id,
                book_titles=book_titles,
                alias_lookup=alias_lookup,
            )
        )
        documents.extend(
            self._event_retrieval_documents(
                session,
                series_id=series_id,
                book_titles=book_titles,
                alias_lookup=alias_lookup,
            )
        )
        documents.extend(self._trajectory_retrieval_documents(trajectories))
        documents.extend(self._thread_retrieval_documents(unresolved_threads))
        return documents

    def _scene_retrieval_documents(
        self,
        session,
        *,
        series_id: str | None,
        book_titles: List[str],
        alias_lookup: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        where, params = self._book_filter(series_id=series_id, book_titles=book_titles)
        rows = session.run(
            f"""
            MATCH (b:Book)-[:HAS_CHAPTER]->(:Chapter)-[:HAS_SCENE]->(sc:Scene)
            WHERE {where}
            OPTIONAL MATCH (sc)-[:FEATURES]->(ent:Entity)
            RETURN b.title AS book_title,
                   sc.book_index AS book_index,
                   sc.chapter_index AS chapter_index,
                   sc.scene_index AS scene_index,
                   sc.summary AS summary,
                   collect(DISTINCT ent.name) AS characters
            ORDER BY sc.book_index ASC, sc.chapter_index ASC, sc.scene_index ASC
            """,
            **params,
        )
        documents: List[Dict[str, Any]] = []
        for row in rows:
            data = row.data()
            characters = [
                self._canonicalize_name(name, alias_lookup=alias_lookup)
                for name in (data.get("characters") or [])
            ]
            characters = [name for name in characters if name]
            summary = str(data.get("summary") or "").strip()
            if not summary:
                continue
            doc_id = f"scene:{data.get('book_index')}:{data.get('chapter_index')}:{data.get('scene_index')}"
            documents.append({
                "document_id": doc_id,
                "source_type": "scene",
                "summary": summary,
                "text": " ".join(filter(None, [summary, " ".join(characters)])),
                "metadata": {
                    "series_id": series_id or "",
                    "book_title": data.get("book_title", ""),
                    "book_index": data.get("book_index"),
                    "chapter_index": data.get("chapter_index"),
                    "scene_index": data.get("scene_index"),
                    "characters": characters,
                },
            })
        return documents

    def _event_retrieval_documents(
        self,
        session,
        *,
        series_id: str | None,
        book_titles: List[str],
        alias_lookup: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        where, params = self._book_filter(series_id=series_id, book_titles=book_titles)
        rows = session.run(
            f"""
            MATCH (b:Book)-[:HAS_EVENT]->(e:Event)
            WHERE {where}
            OPTIONAL MATCH (c:Entity)-[:INVOLVED_IN]->(e)
            RETURN b.title AS book_title,
                   e.id AS event_id,
                   e.description AS description,
                   e.book_index AS book_index,
                   e.chapter_index AS chapter_index,
                   e.time_index AS time_index,
                   collect(DISTINCT c.name) AS characters
            ORDER BY e.book_index ASC, e.time_index ASC
            """,
            **params,
        )
        documents: List[Dict[str, Any]] = []
        for row in rows:
            data = row.data()
            description = str(data.get("description") or "").strip()
            if not description:
                continue
            characters = [
                self._canonicalize_name(name, alias_lookup=alias_lookup)
                for name in (data.get("characters") or [])
            ]
            characters = [name for name in characters if name]
            documents.append({
                "document_id": str(data.get("event_id") or f"event:{data.get('book_index')}:{data.get('time_index')}"),
                "source_type": "event",
                "summary": description,
                "text": " ".join(filter(None, [description, " ".join(characters)])),
                "metadata": {
                    "series_id": series_id or "",
                    "book_title": data.get("book_title", ""),
                    "book_index": data.get("book_index"),
                    "chapter_index": data.get("chapter_index"),
                    "time_index": data.get("time_index"),
                    "characters": characters,
                },
            })
        return documents

    def _trajectory_retrieval_documents(self, trajectories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        documents: List[Dict[str, Any]] = []
        for item in trajectories:
            character = str(item.get("character") or "").strip()
            last_events = [str(event.get("summary") or "").strip() for event in (item.get("last_events") or []) if str(event.get("summary") or "").strip()]
            if not character or not last_events:
                continue
            documents.append({
                "document_id": f"trajectory:{self._normalized_entity_key(character)}",
                "source_type": "trajectory",
                "summary": f"{character} trajectory",
                "text": " ".join([character] + last_events),
                "metadata": {
                    "series_id": "",
                    "book_title": "",
                    "book_index": None,
                    "chapter_index": None,
                    "characters": [character],
                },
            })
        return documents

    def _active_thread_retrieval_documents(self, unresolved_threads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        documents: List[Dict[str, Any]] = []
        for item in unresolved_threads:
            event_id = str(item.get("event_id") or "").strip()
            summary = str(item.get("event_description") or "").strip()
            if not event_id or not summary:
                continue
            documents.append({
                "document_id": f"active-thread:{event_id}",
                "source_type": "thread",
                "summary": summary,
                "text": " ".join(filter(None, [summary, str(item.get("thread_type") or "")])),
                "metadata": {
                    "series_id": "",
                    "thread_type": item.get("thread_type", ""),
                    "book_index": item.get("book_index"),
                    "chapter_index": item.get("chapter"),
                },
            })
        return documents

    def _thread_retrieval_documents(self, unresolved_threads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        documents: List[Dict[str, Any]] = []
        for item in unresolved_threads:
            description = str(item.get("event_description") or "").strip()
            if not description:
                continue
            documents.append({
                "document_id": f"thread:{item.get('event_id') or self._normalized_entity_key(description)}",
                "source_type": "thread",
                "summary": description,
                "text": " ".join(
                    filter(
                        None,
                        [
                            description,
                            str(item.get("decision_made") or "").strip(),
                            " ".join(item.get("alternatives") or []),
                        ],
                    )
                ),
                "metadata": {
                    "series_id": "",
                    "book_title": "",
                    "book_index": None,
                    "chapter_index": item.get("chapter"),
                    "characters": [],
                },
            })
        return documents

    def _load_alias_lookup(self, session, *, series_id: str) -> Dict[str, str]:
        if not series_id:
            return {}
        rows = [row.data() for row in session.run(
            """
            MATCH (e:Entity {series_id: $series_id})-[:HAS_ALIAS]->(a:Alias {series_id: $series_id})
            OPTIONAL MATCH (:Book {series_id: $series_id})-[he:HAS_ENTITY]->(e)
            WITH e, a, sum(coalesce(he.mention_count, 0)) AS mention_count
            RETURN e.name AS canonical_name, a.text AS alias_text, mention_count AS mention_count
            """,
            series_id=series_id,
        )]
        lookup: Dict[str, str] = {}
        choices: Dict[str, List[tuple[str, int]]] = defaultdict(list)
        for data in rows:
            canonical = self.normalizer.canonicalize_candidate_name(self._clean_name(data.get("canonical_name", "")))
            alias = self.normalizer.canonicalize_candidate_name(self._clean_name(data.get("alias_text", "")))
            if not canonical or not alias:
                continue
            mention_count = int(data.get("mention_count") or 0)
            choices[alias].append((canonical, mention_count))
            choices[self._normalized_entity_key(alias)].append((canonical, mention_count))
        for alias, canonicals in choices.items():
            lookup[alias] = max(canonicals, key=lambda item: (item[1],) + self._name_rank(item[0]))[0]
        return lookup

    def _clean_last_scene(self, scene: Dict[str, Any], *, alias_lookup: Dict[str, str]) -> Dict[str, Any]:
        if not scene:
            return {}
        cleaned = dict(scene)
        entities = []
        seen = set()
        for entity in scene.get("entities_present", []) or []:
            canonical_name = self._canonicalize_name((entity or {}).get("name", ""), alias_lookup=alias_lookup)
            if not canonical_name or canonical_name in seen:
                continue
            entities.append({
                "name": canonical_name,
                "entity_type": (entity or {}).get("entity_type", ""),
            })
            seen.add(canonical_name)
        cleaned["entities_present"] = entities
        location = cleaned.get("location") or {}
        if location.get("name"):
            location = dict(location)
            location["name"] = self._clean_name(location.get("name", ""))
            cleaned["location"] = location
        return cleaned

    def _clean_character_states(
        self,
        rows: List[Dict[str, Any]],
        *,
        alias_lookup: Dict[str, str],
        top_characters: int,
        use_props_fallback: bool,
        target_recent_book_index: Any,
    ) -> List[Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            raw_name = row.get("name", "")
            canonical_name = self._resolve_cluster_name(
                raw_name=raw_name,
                aliases=row.get("aliases") or [],
                alias_lookup=alias_lookup,
            )
            if not self._is_viable_character_name(canonical_name):
                continue
            props = row.get("props") or {}
            raw_type = str(props.get("entity_type") or row.get("entity_type") or "").strip().lower()
            inferred_type = self.normalizer.infer_entity_type(
                canonical_name,
                existing_type=raw_type,
                descriptions=[desc for desc in (row.get("descriptions") or []) if isinstance(desc, str)],
            )
            if inferred_type != "character":
                continue
            entry = merged.setdefault(
                canonical_name,
                {
                    "name": canonical_name,
                    "mention_count": 0,
                    "first_seen_chapter": row.get("first_seen_chapter"),
                    "latest_book_index": row.get("latest_book_index"),
                    "descriptions": [],
                    "aliases": [],
                    "state_transitions": [],
                    "_props": [],
                },
            )
            entry["mention_count"] += int(row.get("mention_count") or 0)
            first_seen = row.get("first_seen_chapter")
            if entry.get("first_seen_chapter") is None or (
                first_seen is not None and first_seen < entry.get("first_seen_chapter")
            ):
                entry["first_seen_chapter"] = first_seen
            latest_book_index = row.get("latest_book_index")
            if latest_book_index is not None and (
                entry.get("latest_book_index") is None or latest_book_index > entry.get("latest_book_index")
            ):
                entry["latest_book_index"] = latest_book_index
            entry["descriptions"] = self._merge_unique(
                entry.get("descriptions", []),
                [desc for desc in (row.get("descriptions") or []) if isinstance(desc, str) and desc.strip()],
            )[:4]
            aliases = [self._clean_name(alias) for alias in (row.get("aliases") or [])]
            if raw_name and self._clean_name(raw_name) != canonical_name:
                aliases.append(self._clean_name(raw_name))
            entry["aliases"] = self._merge_unique(entry.get("aliases", []), [alias for alias in aliases if alias and alias != canonical_name])
            entry["state_transitions"].extend(self._clean_transitions(row.get("state_transitions") or []))
            entry["_props"].append(row.get("props") or {})

        cleaned_rows: List[Dict[str, Any]] = []
        for entry in merged.values():
            raw_transitions = list(entry.get("state_transitions", []))
            entry["canon_state"] = self._derive_stable_canon_state(
                entry.get("_props", []),
                raw_transitions,
                descriptions=entry.get("descriptions", []),
                aliases=entry.get("aliases", []),
                latest_book_index=entry.get("latest_book_index"),
                use_props_fallback=use_props_fallback,
            )
            entry["aliases"] = self._sanitize_output_aliases(
                canonical_name=entry.get("name", ""),
                aliases=entry.get("aliases", []),
            )
            entry["state_transitions"] = self._transitions_for_output(
                raw_transitions,
                latest_book_index=entry.get("latest_book_index"),
                target_book_index=target_recent_book_index,
            )
            entry.pop("_props", None)
            cleaned_rows.append(entry)

        cleaned_rows.sort(key=lambda item: (-int(item.get("mention_count") or 0), item.get("name", "")))
        return cleaned_rows[:top_characters]

    def _clean_relationship_summary(
        self,
        rows: List[Dict[str, Any]],
        *,
        alias_lookup: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        cleaned: List[Dict[str, Any]] = []
        seen = set()
        for row in rows:
            entity_a = self._canonicalize_name(row.get("entity_a", ""), alias_lookup=alias_lookup)
            entity_b = self._canonicalize_name(row.get("entity_b", ""), alias_lookup=alias_lookup)
            if not entity_a or not entity_b or entity_a == entity_b:
                continue
            if self.normalizer.is_bad_alias_like_name(entity_a) or self.normalizer.is_bad_alias_like_name(entity_b):
                continue
            key = (entity_a, entity_b, row.get("relationship_type", ""))
            if key in seen:
                continue
            seen.add(key)
            cleaned.append({
                **row,
                "entity_a": entity_a,
                "entity_b": entity_b,
            })
        return cleaned[:15]

    def _clean_character_trajectories(
        self,
        rows: List[Dict[str, Any]],
        *,
        alias_lookup: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        cleaned: List[Dict[str, Any]] = []
        seen = set()
        for row in rows:
            character = self._canonicalize_name(row.get("character", ""), alias_lookup=alias_lookup)
            if not self._is_viable_character_name(character) or character in seen:
                continue
            seen.add(character)
            cleaned.append({
                "character": character,
                "last_events": row.get("last_events", []) or [],
            })
        return cleaned

    def _canonicalize_name(self, raw_name: str, *, alias_lookup: Dict[str, str]) -> str:
        cleaned = self._clean_name(raw_name)
        if not cleaned:
            return ""
        cleaned = self.normalizer.canonicalize_candidate_name(cleaned)
        if not cleaned:
            return ""
        resolved = alias_lookup.get(cleaned) or alias_lookup.get(self._normalized_entity_key(cleaned)) or cleaned
        return self._best_display_name([resolved, cleaned])

    def _resolve_cluster_name(self, *, raw_name: str, aliases: List[str], alias_lookup: Dict[str, str]) -> str:
        candidates = [self._clean_name(raw_name)] + [self._clean_name(alias) for alias in aliases]
        expanded = list(candidates)
        for candidate in list(candidates):
            if not candidate:
                continue
            mapped = alias_lookup.get(candidate) or alias_lookup.get(self._normalized_entity_key(candidate))
            if mapped:
                expanded.append(mapped)
        expanded = [
            canonical
            for candidate in expanded
            if candidate
            for canonical in [self.normalizer.canonicalize_candidate_name(candidate)]
            if canonical
        ]
        chosen = self._best_display_name(expanded)
        if self.normalizer.is_bad_alias_like_name(chosen):
            return ""
        return chosen

    def _clean_name(self, value: str) -> str:
        if not value:
            return ""
        cleaned = unicodedata.normalize("NFKC", str(value))
        cleaned = cleaned.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = self._repair_noisy_character_name(cleaned)
        return cleaned

    def _repair_noisy_character_name(self, value: str) -> str:
        match = re.match(r"^(Toward|Marked|Begged|Asked|Called|From|To|With|At)\s+([A-Z][A-Za-z'\\-]+(?:\s+[A-Z][A-Za-z'\\-]+){0,2})$", value)
        if match:
            return match.group(2).strip()
        return value

    def _normalized_entity_key(self, value: str) -> str:
        return self.normalizer.normalized_entity_key(value)

    def _best_display_name(self, names: List[str]) -> str:
        candidates: List[str] = []
        for name in names:
            cleaned = self._clean_name(name)
            if not cleaned:
                continue
            canonical = self.normalizer.canonicalize_candidate_name(cleaned)
            if canonical:
                candidates.append(canonical)
        if not candidates:
            return ""
        unique = []
        seen = set()
        for name in candidates:
            key = self._normalized_entity_key(name)
            if key in seen:
                continue
            unique.append(name)
            seen.add(key)
        return max(unique, key=self._name_rank)

    def _is_viable_character_name(self, name: str) -> bool:
        if not name:
            return False
        if self.normalizer.is_bad_alias_like_name(name):
            return False
        if not self.normalizer.looks_like_character_name(name):
            return False
        canonical = self.normalizer.canonicalize_candidate_name(name)
        return bool(canonical and self.normalizer.looks_like_character_name(canonical))

    def _name_rank(self, name: str) -> tuple[int, int, int, int]:
        cleaned = self._clean_name(name)
        tokens = cleaned.split()
        proper_tokens = 0
        for token in tokens:
            bare = token.replace("'", "").replace("-", "")
            if bare and bare[0].isupper() and bare[1:].isalpha():
                proper_tokens += 1
        suspicious = 1 if any(marker in cleaned for marker in [",", ";", ":"]) or cleaned.endswith("'s") else 0
        lowercase_penalty = 1 if any(token.islower() for token in tokens) else 0
        title_penalty = 1 if any(token.lower() in {"my", "the", "his", "her"} for token in tokens) else 0
        return (
            -suspicious,
            -lowercase_penalty - title_penalty,
            proper_tokens,
            len(tokens),
            len(cleaned),
        )

    def _clean_transitions(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cleaned_rows = []
        for row in rows:
            attribute = self._clean_name((row or {}).get("attribute", ""))
            if not attribute:
                continue
            cleaned_rows.append({
                "attribute": attribute,
                "previous_state": self._clean_name((row or {}).get("previous_state", "")),
                "new_state": self._clean_name((row or {}).get("new_state", "")),
                "change_type": self._clean_name((row or {}).get("change_type", "")),
                "evidence": self._clean_name((row or {}).get("evidence", "")),
                "chapter": (row or {}).get("chapter"),
                "book_index": (row or {}).get("book_index"),
            })
        return cleaned_rows

    def _dedupe_transitions(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        grouped: Dict[tuple[str, Any, str], Dict[str, Any]] = {}
        for row in rows:
            key = (row.get("attribute", ""), row.get("chapter"), row.get("new_state", ""))
            existing = grouped.get(key)
            if existing is None or len(row.get("evidence", "")) > len(existing.get("evidence", "")):
                grouped[key] = row
        cleaned = list(grouped.values())
        cleaned.sort(key=lambda item: ((item.get("chapter") or 0), item.get("attribute", "")))
        return cleaned[-12:]

    def _sanitize_output_aliases(self, *, canonical_name: str, aliases: List[str]) -> List[str]:
        canonical_tokens = [
            self._clean_name(token)
            for token in str(canonical_name or "").split()
            if self._clean_name(token)
        ]
        canonical_key = self._normalized_entity_key(canonical_name)
        cleaned_aliases: List[str] = []
        seen = set()
        for alias in aliases or []:
            cleaned = self._clean_name(alias)
            if not cleaned or self.normalizer.is_bad_alias_like_name(cleaned):
                continue
            if self.normalizer.looks_like_location_name(cleaned):
                continue
            normalized_alias = self.normalizer.canonicalize_candidate_name(cleaned)
            if not normalized_alias or not self.normalizer.looks_like_character_name(normalized_alias):
                continue
            if self._is_generic_alias_label(cleaned) or self._is_generic_alias_label(normalized_alias):
                continue
            normalized_key = self._normalized_entity_key(normalized_alias)
            if not normalized_key or normalized_key == canonical_key:
                continue
            resembles_canonical = any(
                SequenceMatcher(None, normalized_alias.lower(), token.lower()).ratio() >= 0.8
                for token in canonical_tokens
            ) or any(
                token.lower() in normalized_alias.lower() or normalized_alias.lower() in token.lower()
                for token in canonical_tokens
            )
            if not resembles_canonical:
                continue
            if len(normalized_alias.split()) == 1 and any(
                SequenceMatcher(None, normalized_alias.lower(), token.lower()).ratio() >= 0.8
                and normalized_alias.lower() != token.lower()
                and normalized_alias.lower() not in token.lower()
                and token.lower() not in normalized_alias.lower()
                for token in canonical_tokens
            ):
                continue
            if normalized_key in seen:
                continue
            cleaned_aliases.append(normalized_alias)
            seen.add(normalized_key)
        return cleaned_aliases[:5]

    def _is_generic_alias_label(self, value: str) -> bool:
        lowered = self._clean_name(value).lower()
        return lowered in self.GENERIC_ALIAS_LABELS

    def _transitions_for_output(self, rows: List[Dict[str, Any]], *, latest_book_index: Any, target_book_index: Any) -> List[Dict[str, Any]]:
        scope_latest_rows = [
            row for row in rows
            if target_book_index is not None and row.get("book_index") == target_book_index
        ]
        if scope_latest_rows:
            return self._dedupe_transitions(scope_latest_rows)[-6:]
        if target_book_index is not None:
            return []
        latest_rows = [
            row for row in rows
            if latest_book_index is not None and row.get("book_index") == latest_book_index
        ]
        scoped_rows = latest_rows if latest_rows else rows
        return self._dedupe_transitions(scoped_rows)[-6:]

    def _derive_stable_canon_state(
        self,
        props_rows: List[Dict[str, Any]],
        transitions: List[Dict[str, Any]],
        *,
        descriptions: List[str],
        aliases: List[str],
        latest_book_index: Any,
        use_props_fallback: bool,
    ) -> Dict[str, Any]:
        canon_state: Dict[str, Any] = {}
        latest_by_attr: Dict[str, Dict[str, Any]] = {}
        for row in transitions:
            attr = row.get("attribute", "")
            if latest_book_index is not None and row.get("book_index") != latest_book_index:
                continue
            if not self._keep_canon_attribute(attr, row.get("new_state")):
                continue
            latest_by_attr[attr] = row
        for attr, row in latest_by_attr.items():
            canon_state[attr] = row.get("new_state", "")
        if canon_state:
            return canon_state

        props_fallback = self._derive_canon_state_from_props(props_rows)
        if props_fallback and use_props_fallback:
            canon_state.update(props_fallback)

        if not canon_state and props_fallback:
            # Series-wide retrieval is noisier, but a blank canon packet is worse than a
            # conservative stable-facts fallback from explicitly stored canon_* props.
            canon_state.update(props_fallback)
        if canon_state:
            return canon_state

        alias_inferred = self._infer_canon_state_from_aliases(aliases or [])
        if alias_inferred:
            canon_state.update(alias_inferred)
        if canon_state:
            return canon_state

        inferred = self._infer_canon_state_from_descriptions(descriptions or [])
        canon_state.update(inferred)
        return canon_state

    def _derive_canon_state_from_props(self, props_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        canon_state: Dict[str, Any] = {}
        for props in props_rows:
            for key, value in (props or {}).items():
                if not key.startswith("canon_"):
                    continue
                attr = key[len("canon_"):]
                if self._keep_canon_attribute(attr, value):
                    canon_state[attr] = value
        return canon_state

    def _infer_canon_state_from_aliases(self, aliases: List[str]) -> Dict[str, str]:
        text = " ".join(str(item or "") for item in aliases if str(item or "").strip())
        if not text:
            return {}
        lowered = text.lower()
        canon_state: Dict[str, str] = {}
        if "high lord of spring" in lowered:
            canon_state["title"] = "High Lord"
            canon_state["court"] = "Spring Court"
        elif "high lady of the night court" in lowered:
            canon_state["title"] = "High Lady"
            canon_state["court"] = "Night Court"
        elif "high lord" in lowered and "night" in lowered:
            canon_state["title"] = "High Lord"
            canon_state["court"] = "Night Court"
        elif "lady" in lowered and "night" in lowered:
            canon_state["title"] = "Lady"
            canon_state["court"] = "Night Court"
        return canon_state

    def _infer_canon_state_from_descriptions(self, descriptions: List[str]) -> Dict[str, str]:
        text = " ".join(str(item or "") for item in descriptions if str(item or "").strip())
        if not text:
            return {}
        lowered = text.lower()
        canon_state: Dict[str, str] = {}
        title_match = re.search(r"\b(high lord|high lady|lord|lady|general|spymaster|queen|king|priestess)\b", lowered)
        if title_match:
            title = title_match.group(1)
            if title in {"high lord", "high lady", "lord", "lady", "queen", "king"}:
                canon_state["title"] = title.title()
            else:
                canon_state["role"] = title
        role_match = re.search(r"\b(spymaster|general|priestess|blacksmith|healer|warrior)\b", lowered)
        if role_match and "role" not in canon_state:
            canon_state["role"] = role_match.group(1)
        court_match = re.search(r"\b(night|day|dawn|spring|summer|autumn|winter|dusk)\s+court\b", lowered)
        if court_match:
            canon_state["court"] = f"{court_match.group(1).title()} Court"
        if "mate" in lowered:
            canon_state.setdefault("mate_status", "mated or mate-bonded")
        family_match = re.search(r"\b(sister|brother|mother|father|daughter|son)\b", lowered)
        if family_match:
            canon_state.setdefault("family_role", family_match.group(1))
        allegiance_match = re.search(r"\b(loyal to|allied with)\s+([A-Z][A-Za-z'\\-]+(?:\s+[A-Z][A-Za-z'\\-]+){0,2})", text)
        if allegiance_match:
            canon_state.setdefault("allegiance", allegiance_match.group(2))
        return canon_state

    def _keep_canon_attribute(self, attr: str, value: Any) -> bool:
        if attr not in self.STABLE_CANON_ATTRIBUTES:
            return False
        if not isinstance(value, str):
            return False
        cleaned = self._clean_name(value)
        if not cleaned:
            return False
        if len(cleaned) > 120:
            return False
        return True

    def _merge_unique(self, existing: List[str], new_rows: List[str]) -> List[str]:
        seen = {self._normalized_entity_key(item) for item in existing if item}
        merged = list(existing)
        for item in new_rows:
            normalized = self._normalized_entity_key(item)
            if not normalized or normalized in seen:
                continue
            merged.append(item)
            seen.add(normalized)
        return merged
