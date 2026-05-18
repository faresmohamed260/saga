"""Searchable index for scenes and durable narrative artifacts."""

from typing import Dict, List, Optional

from sklearn.feature_extraction.text import TfidfVectorizer


class StoryIndexService:
    """
    Stores scene and downstream structured outputs in a searchable TF-IDF index.
    """

    def __init__(self, min_similarity: float = 0.05, max_results: int = 8):
        self.min_similarity = min_similarity
        self.max_results = max_results
        self.vectorizer = None
        self.matrix = None
        self.documents: List[Dict] = []

    def build(
        self,
        *,
        artifact_bundle: Optional[Dict] = None,
        scene_analyses: Optional[List[Dict]] = None,
        timeline: Optional[List[Dict]] = None,
        event_ledger: Optional[List[Dict]] = None,
        character_timelines: Optional[List[Dict]] = None,
        character_profiles: Optional[List[Dict]] = None,
        relationship_profiles: Optional[List[Dict]] = None,
        entity_profiles: Optional[List[Dict]] = None,
        canon_snapshots: Optional[List[Dict]] = None,
        entity_registry: Optional[List[Dict]] = None,
        canon_snapshot: Optional[List[Dict]] = None,
        state_result: Optional[Dict] = None,
        identity_result: Optional[Dict] = None,
        causal_graph_result: Optional[Dict] = None,
    ) -> Dict:
        artifact_bundle = artifact_bundle or {}
        raw_outputs = artifact_bundle.get("raw_outputs", {}) if isinstance(artifact_bundle, dict) else {}
        scene_analyses = scene_analyses if scene_analyses is not None else raw_outputs.get("resolved_scene_analyses")
        timeline = timeline if timeline is not None else raw_outputs.get("timeline")
        event_ledger = event_ledger if event_ledger is not None else artifact_bundle.get("event_ledger")
        character_timelines = character_timelines if character_timelines is not None else raw_outputs.get("character_timelines")
        character_profiles = character_profiles if character_profiles is not None else artifact_bundle.get("character_profiles")
        relationship_profiles = relationship_profiles if relationship_profiles is not None else artifact_bundle.get("relationship_profiles")
        entity_profiles = entity_profiles if entity_profiles is not None else artifact_bundle.get("entity_profiles")
        canon_snapshots = canon_snapshots if canon_snapshots is not None else artifact_bundle.get("canon_snapshots")
        entity_registry = entity_registry if entity_registry is not None else raw_outputs.get("entity_registry")
        state_result = state_result if state_result is not None else raw_outputs.get("state_result")
        identity_result = identity_result if identity_result is not None else raw_outputs.get("identity_result")
        causal_graph_result = causal_graph_result if causal_graph_result is not None else raw_outputs.get("causal_graph_result")

        documents = []
        documents.extend(self._scene_documents(scene_analyses or []))
        documents.extend(self._timeline_documents(timeline or []))
        documents.extend(self._event_ledger_documents(event_ledger or []))
        documents.extend(self._character_timeline_documents(character_timelines or []))
        documents.extend(self._character_profile_documents(character_profiles or []))
        documents.extend(self._relationship_profile_documents(relationship_profiles or []))
        documents.extend(self._entity_profile_documents(entity_profiles or []))
        documents.extend(self._canon_snapshot_documents(canon_snapshots or []))
        documents.extend(self._entity_registry_documents(entity_registry or []))
        documents.extend(self._canon_snapshot_documents(canon_snapshot or []))
        documents.extend(self._state_documents(state_result or {}))
        documents.extend(self._identity_documents(identity_result or {}))
        documents.extend(self._causal_documents(causal_graph_result or {}))

        self.documents = documents
        if not documents:
            self.vectorizer = None
            self.matrix = None
            return {"document_count": 0}

        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self.matrix = self.vectorizer.fit_transform([doc["search_text"] for doc in documents])
        return {"document_count": len(documents)}

    def query(self, query_text: str, min_similarity: Optional[float] = None, max_results: Optional[int] = None) -> List[Dict]:
        if not query_text or self.vectorizer is None or self.matrix is None or not self.documents:
            return []

        threshold = self.min_similarity if min_similarity is None else min_similarity
        limit = self.max_results if max_results is None else max_results

        query_vector = self.vectorizer.transform([query_text])
        scores = (self.matrix @ query_vector.T).toarray().ravel()
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)

        results = []
        for index, score in ranked:
            if score < threshold:
                continue

            doc = self.documents[index]
            results.append({
                "item_type": doc["item_type"],
                "score": float(score),
                "summary": doc["summary"],
                "text": doc["text"],
                "metadata": doc["metadata"],
            })
            if len(results) >= limit:
                break

        return results

    def _scene_documents(self, scene_analyses: List[Dict]) -> List[Dict]:
        documents = []
        for scene in scene_analyses:
            event_summaries = " ".join(event["description"] for event in scene.get("events", []))
            documents.append({
                "item_type": "scene",
                "summary": scene.get("scene_summary", ""),
                "text": scene.get("text", ""),
                "search_text": " ".join(filter(None, [
                    scene.get("scene_summary", ""),
                    event_summaries,
                    scene.get("text", ""),
                ])),
                "metadata": {
                    "book_index": scene.get("book_index"),
                    "chapter_index": scene.get("chapter_index"),
                    "scene_index": scene.get("scene_index"),
                },
            })
        return documents

    def _timeline_documents(self, timeline: List[Dict]) -> List[Dict]:
        return [
            {
                "item_type": "timeline_event",
                "summary": item.get("summary", ""),
                "text": item.get("summary", ""),
                "search_text": " ".join(filter(None, [
                    item.get("summary", ""),
                    " ".join(item.get("characters", [])),
                ])),
                "metadata": {
                    "time_index": item.get("time_index"),
                    "book_index": item.get("book_index"),
                    "chapter_index": item.get("chapter_index"),
                    "scene_index": item.get("scene_index"),
                    "event_id": item.get("event_id"),
                    "characters": item.get("characters", []),
                },
            }
            for item in timeline
        ]

    def _character_timeline_documents(self, character_timelines: List[Dict]) -> List[Dict]:
        documents = []
        for item in character_timelines:
            event_summaries = " ".join(event.get("summary", "") for event in item.get("events", []))
            documents.append({
                "item_type": "character_timeline",
                "summary": item.get("character", ""),
                "text": event_summaries,
                "search_text": f"{item.get('character', '')} {event_summaries}",
                "metadata": {
                    "character": item.get("character"),
                    "event_count": len(item.get("events", [])),
                },
            })
        return documents

    def _event_ledger_documents(self, event_ledger: List[Dict]) -> List[Dict]:
        return [
            {
                "item_type": "event_ledger",
                "summary": item.get("title", ""),
                "text": item.get("summary", ""),
                "search_text": " ".join(filter(None, [
                    item.get("title", ""),
                    item.get("summary", ""),
                    " ".join(item.get("participants", [])),
                    item.get("location", ""),
                    " ".join(item.get("tags", [])),
                ])),
                "metadata": {
                    "ledger_event_id": item.get("ledger_event_id"),
                    "time_index": item.get("time_index"),
                    "book_index": item.get("book_index"),
                    "chapter_index": item.get("chapter_index"),
                    "scene_index": item.get("scene_index"),
                    "participants": item.get("participants", []),
                    "tags": item.get("tags", []),
                },
            }
            for item in event_ledger
        ]

    def _character_profile_documents(self, character_profiles: List[Dict]) -> List[Dict]:
        documents = []
        for item in character_profiles:
            searchable_bits = [
                item.get("canonical_name", ""),
                " ".join(item.get("aliases", [])),
                item.get("core_description", ""),
                " ".join(item.get("traits", [])),
                " ".join(event.get("summary", "") for event in item.get("important_history", [])),
                " ".join(f"{key} {value}" for key, value in (item.get("state_at_latest") or {}).items()),
            ]
            documents.append({
                "item_type": "character_profile",
                "summary": item.get("canonical_name", ""),
                "text": item.get("core_description", ""),
                "search_text": " ".join(filter(None, searchable_bits)),
                "metadata": {
                    "character_id": item.get("character_id"),
                    "canonical_name": item.get("canonical_name"),
                    "aliases": item.get("aliases", []),
                    "event_count": item.get("event_count", 0),
                },
            })
        return documents

    def _relationship_profile_documents(self, relationship_profiles: List[Dict]) -> List[Dict]:
        documents = []
        for item in relationship_profiles:
            history = " ".join(item.get("shared_history", []))
            changes = " ".join(
                " ".join(
                    filter(
                        None,
                        [
                            row.get("relationship", ""),
                            row.get("change", ""),
                            row.get("evidence", ""),
                        ],
                    )
                )
                for row in item.get("change_log", [])
            )
            documents.append({
                "item_type": "relationship_profile",
                "summary": f"{item.get('source_character', '')} / {item.get('target_character', '')}",
                "text": history or changes,
                "search_text": " ".join(filter(None, [
                    item.get("relationship_id", ""),
                    item.get("source_character", ""),
                    item.get("target_character", ""),
                    item.get("relationship_type", ""),
                    item.get("baseline_dynamic", ""),
                    item.get("trust_level", ""),
                    item.get("conflict_level", ""),
                    item.get("romantic_signal", ""),
                    history,
                    changes,
                ])),
                "metadata": {
                    "relationship_id": item.get("relationship_id"),
                    "source_character": item.get("source_character"),
                    "target_character": item.get("target_character"),
                    "relationship_type": item.get("relationship_type"),
                },
            })
        return documents

    def _entity_profile_documents(self, entity_profiles: List[Dict]) -> List[Dict]:
        documents = []
        for item in entity_profiles:
            history = " ".join(change.get("evidence", "") for change in item.get("status_history", []))
            documents.append({
                "item_type": "entity_profile",
                "summary": f"{item.get('name', '')} ({item.get('entity_type', '')})",
                "text": item.get("description", ""),
                "search_text": " ".join(filter(None, [
                    item.get("entity_id", ""),
                    item.get("name", ""),
                    item.get("entity_type", ""),
                    item.get("description", ""),
                    " ".join(item.get("rules_or_constraints", [])),
                    " ".join(item.get("connected_characters", [])),
                    history,
                ])),
                "metadata": {
                    "entity_id": item.get("entity_id"),
                    "name": item.get("name"),
                    "entity_type": item.get("entity_type"),
                    "connected_characters": item.get("connected_characters", []),
                },
            })
        return documents

    def _entity_registry_documents(self, entity_registry: List[Dict]) -> List[Dict]:
        documents = []
        for item in entity_registry:
            descriptions = " ".join(
                description.get("description", "")
                for description in item.get("descriptions", [])
            )
            changes = " ".join(
                change.get("evidence", "")
                for change in item.get("state_changes", [])
            )
            documents.append({
                "item_type": "entity_registry",
                "summary": f"{item.get('name', '')} ({item.get('entity_type', '')})",
                "text": " ".join(filter(None, [descriptions, changes])),
                "search_text": " ".join(filter(None, [
                    item.get("name", ""),
                    item.get("entity_type", ""),
                    descriptions,
                    changes,
                ])),
                "metadata": {
                    "entity_name": item.get("name"),
                    "entity_type": item.get("entity_type"),
                    "mention_count": item.get("mention_count"),
                    "first_seen": item.get("first_seen"),
                },
            })
        return documents

    def _canon_snapshot_documents(self, canon_snapshot: List[Dict]) -> List[Dict]:
        documents = []
        for item in canon_snapshot:
            attributes = item.get("attributes", {})
            if not attributes and item.get("character_states") is not None:
                attributes = {
                    "character_states": len(item.get("character_states") or []),
                    "relationship_states": len(item.get("relationship_states") or []),
                    "entity_states": len(item.get("entity_states") or []),
                }
            attribute_text = " ".join(f"{key} {value}" for key, value in attributes.items())
            documents.append({
                "item_type": "canon_snapshot",
                "summary": f"{item.get('entity_name', '') or item.get('anchor_event_id', '')} snapshot",
                "text": attribute_text,
                "search_text": " ".join(filter(None, [
                    item.get("snapshot_id", ""),
                    item.get("entity_name", ""),
                    item.get("entity_type", ""),
                    item.get("anchor_event_id", ""),
                    attribute_text,
                ])),
                "metadata": {
                    "snapshot_id": item.get("snapshot_id"),
                    "anchor_event_id": item.get("anchor_event_id"),
                    "entity_name": item.get("entity_name"),
                    "entity_type": item.get("entity_type"),
                    "attributes": attributes,
                },
            })
        return documents

    def _state_documents(self, state_result: Dict) -> List[Dict]:
        documents = []
        for item in state_result.get("transitions", []):
            documents.append({
                "item_type": "state_transition",
                "summary": f"{item.get('entity_name', '')} {item.get('attribute', '')} -> {item.get('new_state', '')}",
                "text": item.get("evidence", ""),
                "search_text": " ".join(filter(None, [
                    item.get("entity_name", ""),
                    item.get("attribute", ""),
                    item.get("new_state", ""),
                    item.get("evidence", ""),
                ])),
                "metadata": {
                    "state_index": item.get("state_index"),
                    "book_index": item.get("book_index"),
                    "chapter_index": item.get("chapter_index"),
                    "scene_index": item.get("scene_index"),
                    "entity_name": item.get("entity_name"),
                    "entity_type": item.get("entity_type"),
                },
            })
        return documents

    def _identity_documents(self, identity_result: Dict) -> List[Dict]:
        documents = []
        for item in identity_result.get("decisions", []):
            documents.append({
                "item_type": "identity_decision",
                "summary": item.get("reasoning", ""),
                "text": item.get("reasoning", ""),
                "search_text": " ".join(filter(None, [
                    item.get("character", ""),
                    item.get("canonical_name", ""),
                    item.get("reasoning", ""),
                    " ".join(item.get("candidate_names", [])) if isinstance(item.get("candidate_names"), list) else "",
                ])),
                "metadata": {
                    "decision_type": item.get("decision_type"),
                    "character": item.get("character"),
                    "canonical_name": item.get("canonical_name"),
                    "same_character": item.get("same_character"),
                    "confidence": item.get("confidence"),
                    "resolved_at_time_index": item.get("resolved_at_time_index"),
                },
            })
        for canonical_name, aliases in (identity_result.get("alias_map") or {}).items():
            documents.append({
                "item_type": "alias_map",
                "summary": f"{canonical_name} aliases",
                "text": ", ".join(aliases),
                "search_text": " ".join([canonical_name] + list(aliases)),
                "metadata": {
                    "canonical_name": canonical_name,
                    "aliases": aliases,
                },
            })
        return documents

    def _causal_documents(self, causal_graph_result: Dict) -> List[Dict]:
        documents = []
        graph = (causal_graph_result or {}).get("graph", {})
        metrics = (causal_graph_result or {}).get("metrics", {})

        for item in graph.get("events", []):
            link_text = " ".join(
                [link.get("event_id", "") for link in item.get("caused_by", []) + item.get("causes", [])]
            )
            documents.append({
                "item_type": "causal_event",
                "summary": item.get("description", ""),
                "text": item.get("source_summary", ""),
                "search_text": " ".join(filter(None, [
                    item.get("id", ""),
                    item.get("description", ""),
                    item.get("source_summary", ""),
                    " ".join(item.get("characters", [])),
                    link_text,
                ])),
                "metadata": {
                    "graph_id": item.get("id"),
                    "time_index": item.get("time_index"),
                    "book_index": item.get("book_index"),
                    "chapter_index": item.get("chapter_index"),
                    "scene_index": item.get("scene_index"),
                    "characters": item.get("characters", []),
                },
            })

        if metrics:
            metric_text = " ".join(f"{key} {value}" for key, value in metrics.items())
            documents.append({
                "item_type": "causal_metrics",
                "summary": "causal graph metrics",
                "text": metric_text,
                "search_text": metric_text,
                "metadata": metrics,
            })

        return documents
