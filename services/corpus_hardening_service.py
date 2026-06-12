"""Corpus audit, repair, and rebuild utilities for production hardening."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.canon_normalization import CanonicalEntityNormalizer
from core.pipeline_contract import (
    build_canon_snapshot,
    build_character_timelines,
    build_entity_registry,
    build_state_result,
    build_timeline,
    normalize_character_timelines,
)
from infrastructure.llm_client import LLMClient
from infrastructure.neo4j_ingestion_service import Neo4jIngestionService
from query.neo4j_narrative_context_service import Neo4jNarrativeContextService
from rag.hybrid_embedding_index_service import HybridEmbeddingIndexService
from services.encoder_persistence_service import EncoderPersistenceService
from services.web_entity_hint_service import WebEntityHintService


class CorpusHardeningService:
    """Audit, repair, and rebuild persisted corpus artifacts."""

    BAD_ENTITY_PREFIXES = {
        "toward",
        "begged",
        "asked",
        "told",
        "watched",
        "watching",
        "seeing",
        "saw",
        "heard",
        "hearing",
        "thinking",
        "thought",
        "looked",
        "looking",
        "turning",
        "turned",
        "facing",
        "faced",
        "following",
        "followed",
        "beside",
        "behind",
        "before",
        "after",
    }
    TITLE_PREFIXES = {
        "high lord",
        "high lady",
        "lord",
        "lady",
        "queen",
        "king",
        "prince",
        "princess",
        "sir",
        "madam",
        "mr",
        "mrs",
        "ms",
        "dr",
        "captain",
        "commander",
        "general",
    }
    KNOWN_CHARACTER_TYPES = {"character", "person", "fae", "high_fae", "human"}
    SUSPICIOUS_ENTITY_TYPES = {"location", "creature", "object", "unknown", ""}
    WEB_HINT_SEARCH = {
        "acotar": "https://acourtofthornsandroses.fandom.com/wiki/Special:ApiSandbox?uselang=en",
        "harry-potter": "https://harrypotter.fandom.com/wiki/Special:ApiSandbox?uselang=en",
    }
    SERIES_SOURCE_ROOTS = {
        "acotar": Path(r"D:\Books\Ebooks\Sarah J. Maas"),
        "harry-potter": Path(r"D:\Books\Harry_Potter_Series"),
    }

    def __init__(
        self,
        *,
        neo4j_service: Optional[Neo4jIngestionService] = None,
        llm_client: Optional[LLMClient] = None,
        wiki_hints_enabled: bool = False,
        vector_index_service: Optional[HybridEmbeddingIndexService] = None,
    ) -> None:
        self.neo4j = neo4j_service or Neo4jIngestionService()
        self.llm = llm_client
        self.wiki_hints_enabled = wiki_hints_enabled
        self.vector_index_service = vector_index_service or HybridEmbeddingIndexService()
        self.normalizer = CanonicalEntityNormalizer()
        self.web_entity_hint_service = WebEntityHintService()

    def discover_latest_contracts(self, series_id: str) -> List[Path]:
        root = Path("analysis_outputs") / "encode_runs" / series_id
        latest_by_index: Dict[int, Tuple[int, float, Path]] = {}
        for path in sorted(root.glob("**/contracts/*.json")):
            match = re.match(r"^(\d+)_", path.name)
            if not match:
                continue
            book_index = int(match.group(1))
            score = self._contract_quality_score(path)
            if score < 0:
                continue
            current = latest_by_index.get(book_index)
            if current is None or score > current[0] or (score == current[0] and path.stat().st_mtime > current[1]):
                latest_by_index[book_index] = (score, path.stat().st_mtime, path)
        return [latest_by_index[key][2] for key in sorted(latest_by_index)]

    def audit_corpus(
        self,
        *,
        series_id: str,
        contract_paths: Optional[List[str | Path]] = None,
    ) -> Dict[str, Any]:
        contract_reports = []
        for path in contract_paths or [str(item) for item in self.discover_latest_contracts(series_id)]:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            _, report = self.repair_contract(payload, dry_run=True)
            contract_reports.append({
                "contract_path": str(path),
                "book_title": self._contract_book_title(payload),
                "book_index": self._contract_book_index(payload),
                "repair_preview": report,
            })

        graph_report = self._audit_graph(series_id=series_id)
        return {
            "series_id": series_id,
            "audited_at_utc": self._now_utc(),
            "graph": graph_report,
            "contracts": contract_reports,
            "summary": {
                "contracts_audited": len(contract_reports),
                "duplicate_identity_candidates": graph_report["summary"]["duplicate_identity_candidates"],
                "malformed_entities": graph_report["summary"]["malformed_entities"],
                "entities_without_type": graph_report["summary"]["entities_without_type"],
            },
        }

    def repair_contracts(
        self,
        *,
        series_id: str,
        contract_paths: Optional[List[str | Path]] = None,
        output_dir: str | Path,
        dry_run: bool = False,
        progress_callback=None,
    ) -> Dict[str, Any]:
        target_dir = Path(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        for stale in target_dir.glob("*.contract.json"):
            stale.unlink()
        reports: List[Dict[str, Any]] = []
        repaired_paths: List[str] = []
        selected_paths = [str(path) for path in (contract_paths or [str(item) for item in self.discover_latest_contracts(series_id)])]
        if progress_callback:
            progress_callback("repair_contracts", {
                "current": 0,
                "total": len(selected_paths),
                "status": f"Repairing {len(selected_paths)} contract(s)",
                "done": len(selected_paths) == 0,
            })
        for index, path in enumerate(selected_paths, start=1):
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            repaired, report = self.repair_contract(payload, dry_run=dry_run)
            report["source_contract"] = str(path)
            if not dry_run:
                out_path = target_dir / Path(path).name
                out_path.write_text(json.dumps(repaired, ensure_ascii=False, indent=2), encoding="utf-8")
                repaired_paths.append(str(out_path))
                report["repaired_contract"] = str(out_path)
            reports.append(report)
            if progress_callback:
                progress_callback("repair_contracts", {
                    "current": index,
                    "total": len(selected_paths),
                    "label": Path(path).name,
                    "status": f"Repaired {Path(path).name}",
                    "done": index == len(selected_paths),
                })
        summary = self._summarise_reports(reports)
        artifact = {
            "series_id": series_id,
            "repaired_at_utc": self._now_utc(),
            "dry_run": dry_run,
            "contracts": reports,
            "summary": summary,
        }
        (target_dir / "repair_report.json").write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        return artifact

    def rebuild_corpus(
        self,
        *,
        series_id: str,
        contract_paths: Optional[List[str | Path]] = None,
        output_dir: str | Path,
        dry_run: bool = False,
        source_dir: str | Path | None = None,
        progress_callback=None,
    ) -> Dict[str, Any]:
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        repair_dir = output_root / "repaired_contracts"
        selected_contracts = [str(path) for path in (contract_paths or [str(item) for item in self.discover_latest_contracts(series_id)])]
        if progress_callback:
            progress_callback("stage", {"status": f"Preparing rebuild for '{series_id}'", "done": False})
        repair_report = self.repair_contracts(
            series_id=series_id,
            contract_paths=selected_contracts,
            output_dir=repair_dir,
            dry_run=dry_run,
            progress_callback=progress_callback,
        )
        if dry_run:
            return {
                "series_id": series_id,
                "status": "dry_run",
                "repair_report": repair_report,
            }

        existing = self.neo4j.inspect_series(series_id)
        removed = []
        existing_books = list(existing.get("books", []))
        if progress_callback:
            progress_callback("remove_books", {
                "current": 0,
                "total": len(existing_books),
                "status": f"Removing {len(existing_books)} existing book(s)",
                "done": len(existing_books) == 0,
            })
        for index, book in enumerate(existing_books, start=1):
            removed.append(self.neo4j.remove_book(series_id, book.get("title", "")))
            if progress_callback:
                progress_callback("remove_books", {
                    "current": index,
                    "total": len(existing_books),
                    "label": book.get("title", ""),
                    "status": f"Removed {book.get('title', '')}",
                    "done": index == len(existing_books),
                })
        if progress_callback:
            progress_callback("stage", {"status": "Purging residual series nodes", "done": False})
        purge_report = self.neo4j.purge_series_residue(series_id)

        ingested = []
        repair_sources: List[Dict[str, Any]] = []
        repaired_files = sorted(repair_dir.glob("*.contract.json"))
        recovered_files = self._recover_missing_contracts(
            series_id=series_id,
            repair_dir=repair_dir,
            repaired_files=repaired_files,
            source_dir=source_dir,
            progress_callback=progress_callback,
        ) if not dry_run else []
        repaired_files = sorted(repair_dir.glob("*.contract.json"))
        if progress_callback:
            progress_callback("ingest_contracts", {
                "current": 0,
                "total": len(repaired_files),
                "status": f"Ingesting {len(repaired_files)} repaired contract(s)",
                "done": len(repaired_files) == 0,
            })
        for index, path in enumerate(repaired_files, start=1):
            payload = json.loads(path.read_text(encoding="utf-8"))
            books = (((payload.get("inputs") or {}).get("books")) or [{}])
            first = books[0] if books else {}
            repair_sources.append({
                "book_index": int(first.get("book_index") or 0),
                "book_title": str(first.get("title") or Path(str(first.get("path") or "")).name or "").strip(),
                "source": "recovered_encode" if str(path) in recovered_files else "contract",
                "path": str(path),
            })
            ingested.append(self.neo4j.ingest_contract(payload, replace_existing=False))
            if progress_callback:
                progress_callback("ingest_contracts", {
                    "current": index,
                    "total": len(repaired_files),
                    "label": Path(path).name,
                    "status": f"Ingested {Path(path).name}",
                    "done": index == len(repaired_files),
                })
        if progress_callback:
            progress_callback("stage", {"status": "Consolidating graph", "done": False})
        consolidation_report = self.consolidate_graph(series_id=series_id)

        context_service = Neo4jNarrativeContextService(
            uri=self.neo4j.uri,
            username=self.neo4j.username,
            password=self.neo4j.password,
            database=self.neo4j.database,
        )
        try:
            if progress_callback:
                progress_callback("stage", {"status": "Refreshing retrieval context", "done": False})
            retrieval = context_service.build_from_graph(series_id=series_id)
        finally:
            context_service.close()

        if progress_callback:
            progress_callback("stage", {"status": "Rebuilding hybrid vector index", "done": False})
        index_payload = self.vector_index_service.ensure_index(
            series_id=series_id,
            scope_key="series-rebuild",
            documents=list(retrieval.get("retrieval_documents") or []),
        )
        if progress_callback:
            progress_callback("stage", {"status": "Running post-rebuild audit", "done": False})
        post_audit = self._audit_graph(series_id=series_id)
        result = {
            "series_id": series_id,
            "status": "ok",
            "rebuilt_at_utc": self._now_utc(),
            "removed_books": removed,
            "purge_report": purge_report,
            "repaired_contracts": [str(path) for path in repaired_files],
            "rebuild_sources": repair_sources,
            "ingested_contracts": ingested,
            "vector_index": {
                "series_id": index_payload.get("series_id"),
                "scope_key": index_payload.get("scope_key"),
                "fingerprint": index_payload.get("fingerprint"),
                "document_count": len(index_payload.get("documents") or []),
            },
            "consolidation_report": consolidation_report,
            "post_audit": post_audit,
            "repair_report": repair_report,
        }
        (output_root / "rebuild_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        if progress_callback:
            progress_callback("stage", {"status": f"Rebuild completed for '{series_id}'", "done": True})
        return result

    def _recover_missing_contracts(
        self,
        *,
        series_id: str,
        repair_dir: Path,
        repaired_files: List[Path],
        source_dir: str | Path | None,
        progress_callback=None,
    ) -> List[str]:
        source_books = self._source_books_for_series(series_id=series_id, source_dir=source_dir)
        if not source_books:
            return []
        present = set()
        for path in repaired_files:
            match = re.match(r"^(\d+)_", path.name)
            if match:
                present.add(int(match.group(1)))
        recovered: List[str] = []
        missing_books = [book for book in source_books if book["book_index"] not in present]
        if progress_callback:
            progress_callback("recover_books", {
                "current": 0,
                "total": len(missing_books),
                "status": f"Recovering {len(missing_books)} missing contract(s) from source",
                "done": len(missing_books) == 0,
            })
        for index, book in enumerate(missing_books, start=1):
            if book["book_index"] in present:
                continue
            contract = self._recover_contract_from_source(
                series_id=series_id,
                book_path=book["path"],
                book_title=book["title"],
                book_index=book["book_index"],
                progress_callback=progress_callback,
            )
            out_path = repair_dir / f"{book['book_index']:02d}_{book['title']}.contract.json"
            out_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
            recovered.append(str(out_path))
            if progress_callback:
                progress_callback("recover_books", {
                    "current": index,
                    "total": len(missing_books),
                    "label": book["title"],
                    "status": f"Recovered {book['title']}",
                    "done": index == len(missing_books),
                })
        return recovered

    def _source_books_for_series(self, *, series_id: str, source_dir: str | Path | None) -> List[Dict[str, Any]]:
        root = Path(source_dir) if source_dir else self.SERIES_SOURCE_ROOTS.get(series_id)
        if root is None or not root.exists():
            return []
        rows: List[Dict[str, Any]] = []
        for path in sorted(root.glob("*.epub")):
            match = re.match(r"^(\d+)\s+", path.name)
            if not match:
                continue
            rows.append({
                "book_index": int(match.group(1)),
                "title": path.name,
                "path": path,
            })
        return sorted(rows, key=lambda item: item["book_index"])

    def _recover_contract_from_source(
        self,
        *,
        series_id: str,
        book_path: Path,
        book_title: str,
        book_index: int,
        progress_callback=None,
    ) -> Dict[str, Any]:
        encoder = EncoderPersistenceService(
            analysis_model=LLMClient.MODE_GPT_OSS,
            identity_model=LLMClient.MODE_GPT_OSS,
            analysis_mode="structured",
            target_scene_words=0,
            series_id=series_id,
            series_title=book_title.rsplit(".", 1)[0],
            book_index_base=book_index,
        )
        def _relay(phase: str, payload: Dict[str, Any]) -> None:
            if progress_callback:
                progress_callback("recover_book_phase", {
                    "book_title": book_title,
                    "phase": phase,
                    **(payload or {}),
                })

        return encoder.encode_books([{"path": str(book_path), "title": book_title}], progress_callback=_relay)

    def _contract_quality_score(self, path: Path) -> int:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return -1
        score = 0
        contract_version = str(payload.get("contract_version") or "").strip().lower()
        if contract_version and contract_version != "test":
            score += 20
        outputs = payload.get("outputs") or {}
        score += min(50, len(outputs.get("chapters") or []))
        score += min(50, len(outputs.get("resolved_scene_analyses") or outputs.get("scene_analyses") or []))
        score += min(20, len(outputs.get("entity_registry") or []))
        first_book = (((payload.get("inputs") or {}).get("books")) or [{}])[0]
        title = str(first_book.get("title") or "").strip().lower()
        if title.startswith("book") and len(outputs.get("chapters") or []) <= 2:
            score -= 100
        return score

    def repair_contract(self, payload: Dict[str, Any], *, dry_run: bool = False) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        repaired = json.loads(json.dumps(payload))
        outputs = repaired.setdefault("outputs", {})
        entity_registry = list(outputs.get("entity_registry") or [])
        alias_map = dict(((outputs.get("identity_result") or {}).get("alias_map") or {}))
        hints = self._load_web_hints(repaired) if self.wiki_hints_enabled else {}
        series_id = str((((repaired.get("inputs") or {}).get("series") or {}).get("series_id")) or "").strip()
        book_title = self._contract_book_title(repaired)

        all_names = self.normalizer.collect_named_values(outputs)
        all_names.extend(str(item.get("name") or "").strip() for item in entity_registry)
        all_names.extend(str(key or "").strip() for key in alias_map)
        for aliases in alias_map.values():
            all_names.extend(str(alias or "").strip() for alias in aliases or [])

        merge_map, unresolved = self._build_merge_map(all_names, alias_map, hints=hints)
        llm_merge_map, llm_merge_decisions = self._resolve_unresolved_candidates_with_llm(
            unresolved,
            hints=hints,
            series_id=series_id,
            book_title=book_title,
        )
        merge_map.update(llm_merge_map)
        unresolved = self._filter_resolved_candidates(unresolved, llm_merge_map)
        type_corrections = self._entity_type_corrections(entity_registry, merge_map)

        outputs["entity_registry"] = self._repair_entity_registry(entity_registry, merge_map, type_corrections)
        identity_result = outputs.setdefault("identity_result", {})
        identity_result["alias_map"] = self._repair_alias_map(alias_map, merge_map)
        outputs["state_result"] = self._repair_state_result(outputs.get("state_result") or {}, merge_map)
        outputs["canon_snapshot"] = self._repair_canon_snapshot(outputs.get("canon_snapshot") or [], merge_map)
        outputs["timeline"] = self._repair_timeline(outputs.get("timeline") or [], merge_map)
        outputs["character_timelines"] = self._repair_character_timelines(outputs.get("character_timelines") or [], merge_map)
        outputs["stable_character_states"] = self._repair_stable_character_states(outputs.get("stable_character_states") or [], merge_map)
        outputs["resolved_scene_analyses"] = self._repair_scene_analyses(outputs.get("resolved_scene_analyses") or [], merge_map)
        if outputs.get("scene_analyses"):
            outputs["scene_analyses"] = self._repair_scene_analyses(outputs.get("scene_analyses") or [], merge_map)
        outputs["causal_graph_result"] = self._repair_causal_graph_result(outputs.get("causal_graph_result") or {}, merge_map)
        self._clean_character_scoped_payloads(outputs)
        resolved_scenes = outputs.get("resolved_scene_analyses") or []
        if resolved_scenes and all(
            scene.get("book_index") is not None and scene.get("chapter_index") is not None and scene.get("scene_index") is not None
            for scene in resolved_scenes
        ):
            outputs["entity_registry"] = build_entity_registry(resolved_scenes)
            outputs["state_result"] = build_state_result(resolved_scenes)
            outputs["timeline"] = build_timeline(resolved_scenes)
            outputs["character_timelines"] = normalize_character_timelines(
                build_character_timelines(outputs.get("timeline") or []),
                identity_result,
            )
            final_scene = resolved_scenes[-1]
            scene_ref = (
                int(final_scene.get("book_index") or self._contract_book_index(repaired)),
                int(final_scene.get("chapter_index") or 0),
                int(final_scene.get("scene_index") or 0),
            )
            outputs["canon_snapshot"] = build_canon_snapshot(outputs["state_result"], scene_ref=scene_ref)

        report = {
            "book_title": self._contract_book_title(repaired),
            "book_index": self._contract_book_index(repaired),
            "duplicate_identities_removed": sum(1 for source, target in merge_map.items() if source != target),
            "malformed_nodes_removed": sum(1 for entry in entity_registry if self._is_bad_alias_like_name(entry.get("name", ""))),
            "entity_type_corrections": type_corrections,
            "remaining_unresolved_merge_candidates": unresolved,
            "llm_merge_decisions": llm_merge_decisions,
            "heuristic_hints_used": sorted(hints.keys()),
        }
        if dry_run:
            return payload, report
        return repaired, report

    def _audit_graph(self, *, series_id: str) -> Dict[str, Any]:
        driver = self.neo4j._ensure_driver()
        self.neo4j.probe_connection()
        session_kwargs = {"database": self.neo4j.database} if self.neo4j.database else {}
        with driver.session(**session_kwargs) as session:
            entity_rows = [row.data() for row in session.run(
                """
                MATCH (e:Entity {series_id: $series_id})
                OPTIONAL MATCH (e)-[:HAS_ALIAS]->(a:Alias {series_id: $series_id})
                RETURN e.name AS name,
                       coalesce(e.entity_type, '') AS entity_type,
                       collect(DISTINCT a.text) AS aliases,
                       properties(e) AS props
                ORDER BY name ASC
                """,
                series_id=series_id,
            )]
            involved_rows = [row.data() for row in session.run(
                """
                MATCH (c:Entity {series_id: $series_id})-[:INVOLVED_IN]->(e:Event {series_id: $series_id})
                RETURN c.name AS name, count(DISTINCT e) AS involved_events
                ORDER BY involved_events DESC, name ASC
                LIMIT 20
                """,
                series_id=series_id,
            )]

        alias_names = defaultdict(set)
        normalized_counter = Counter()
        malformed = []
        wrong_types = []
        missing_type = []
        overlap_candidates = []
        for row in entity_rows:
            name = str(row.get("name") or "").strip()
            normalized_counter[self._normalized_entity_key(name)] += 1
            aliases = [str(item).strip() for item in (row.get("aliases") or []) if str(item).strip()]
            for alias in aliases:
                alias_names[self._normalized_entity_key(alias)].add(name)
            entity_type = str(row.get("entity_type") or "").strip().lower()
            if self._is_bad_alias_like_name(name):
                malformed.append(name)
            if not entity_type:
                missing_type.append(name)
            elif entity_type in self.SUSPICIOUS_ENTITY_TYPES and self._looks_like_character_name(name):
                wrong_types.append({"name": name, "entity_type": entity_type})

        for row in entity_rows:
            name = str(row.get("name") or "").strip()
            normalized = self._normalized_entity_key(name)
            alias_of = sorted(alias_names.get(normalized) or [])
            if alias_of and name not in alias_of:
                overlap_candidates.append({"name": name, "alias_of": alias_of})

        context_service = Neo4jNarrativeContextService(
            uri=self.neo4j.uri,
            username=self.neo4j.username,
            password=self.neo4j.password,
            database=self.neo4j.database,
        )
        try:
            retrieval = context_service.build_from_graph(series_id=series_id)
        finally:
            context_service.close()

        return {
            "series_id": series_id,
            "summary": {
                "entity_count": len(entity_rows),
                "duplicate_identity_candidates": len(overlap_candidates),
                "malformed_entities": len(malformed),
                "entities_without_type": len(missing_type),
                "wrong_entity_types": len(wrong_types),
            },
            "top_duplicate_candidates": overlap_candidates[:25],
            "malformed_entities": malformed[:50],
            "missing_type_entities": missing_type[:50],
            "wrong_type_entities": wrong_types[:50],
            "top_involved_characters": self._clean_involved_character_rows(involved_rows),
            "retrieval_preview": {
                "book_title": ((retrieval.get("meta") or {}).get("book_title") or ""),
                "top_characters": [
                    {
                        "name": item.get("name", ""),
                        "mention_count": item.get("mention_count", 0),
                        "canon_state": item.get("canon_state", {}),
                    }
                    for item in (retrieval.get("character_states") or [])[:10]
                ],
                "unresolved_threads": (retrieval.get("unresolved_threads") or [])[:8],
                "retrieval_warnings": ((retrieval.get("meta") or {}).get("retrieval_warnings") or []),
            },
        }

    def _clean_involved_character_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        aggregated: Dict[str, int] = defaultdict(int)
        for row in rows:
            canonical = self.normalizer.canonicalize_candidate_name(str(row.get("name") or "").strip())
            if not canonical or not self.normalizer.looks_like_character_name(canonical):
                continue
            aggregated[canonical] += int(row.get("involved_events") or 0)
        expanded: Dict[str, int] = defaultdict(int)
        candidate_names = list(aggregated.keys())
        for name, count in aggregated.items():
            target = self.normalizer.expand_short_character_name(name, candidate_names) or name
            expanded[target] += count
        cleaned = [
            {"name": name, "involved_events": count}
            for name, count in expanded.items()
        ]
        cleaned.sort(key=lambda item: (-int(item.get("involved_events") or 0), item.get("name", "")))
        return cleaned[:20]

    def _load_web_hints(self, payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        series_id = str((((payload.get("inputs") or {}).get("series") or {}).get("series_id")) or "").strip()
        if not series_id:
            return {}
        names = [
            str(item.get("name") or "").strip()
            for item in (payload.get("outputs", {}).get("entity_registry") or [])[:40]
            if str(item.get("name") or "").strip()
        ]
        return self.web_entity_hint_service.load_series_hints(series_id, names)

    def _build_merge_map(
        self,
        names: List[str],
        alias_map: Dict[str, List[str]],
        *,
        hints: Dict[str, Dict[str, Any]],
    ) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
        return self.normalizer.build_merge_map(names=names, alias_map=alias_map, hints=hints)

    def _resolve_unresolved_candidates_with_llm(
        self,
        unresolved: List[Dict[str, Any]],
        *,
        hints: Dict[str, Dict[str, Any]],
        series_id: str,
        book_title: str,
    ) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
        if not self.llm:
            return {}, []
        merge_overrides: Dict[str, str] = {}
        decisions: List[Dict[str, Any]] = []
        for candidate in unresolved[:25]:
            options = [str(item).strip() for item in (candidate.get("options") or []) if str(item).strip()]
            selected = str(candidate.get("selected") or "").strip()
            if len(options) < 2 or not selected:
                continue
            prompt = self._build_llm_merge_prompt(
                series_id=series_id,
                book_title=book_title,
                options=options,
                selected=selected,
                hints=hints,
            )
            result = self.llm.generate_json(prompt, strict=True, validator=lambda payload, opts=options: self._validate_llm_merge_decision(payload, opts))
            if not isinstance(result, dict) or "error" in result:
                continue
            canonical_name = str(result.get("canonical_name") or "").strip()
            merge_names = [str(item).strip() for item in (result.get("merge_names") or []) if str(item).strip()]
            keep_separate = [str(item).strip() for item in (result.get("keep_separate") or []) if str(item).strip()]
            if not canonical_name or canonical_name not in options:
                continue
            for name in merge_names:
                if name != canonical_name:
                    merge_overrides[name] = canonical_name
            decisions.append({
                "normalized_name": candidate.get("normalized_name", ""),
                "canonical_name": canonical_name,
                "merge_names": merge_names,
                "keep_separate": keep_separate,
                "selected_before_llm": selected,
                "rationale": str(result.get("rationale") or "").strip(),
            })
        return merge_overrides, decisions

    def _build_llm_merge_prompt(
        self,
        *,
        series_id: str,
        book_title: str,
        options: List[str],
        selected: str,
        hints: Dict[str, Dict[str, Any]],
    ) -> str:
        hint_lines = []
        for option in options:
            normalized = self._normalized_entity_key(option)
            if normalized in hints:
                hint_lines.append(f"- {option}: heuristic hint present")
        hints_block = "\n".join(hint_lines) if hint_lines else "- none"
        return (
            "You are validating ambiguous canon entity names extracted from a fantasy book analysis pipeline.\n"
            "Decide which names should merge into one canonical entity and which should remain separate.\n"
            "Be conservative: only merge OCR splits, title variants, shortened names, or obvious alias variants.\n"
            "Do not merge distinct characters, places, objects, or action fragments into a character unless it is clearly the same entity.\n\n"
            f"Series ID: {series_id or 'unknown'}\n"
            f"Book title: {book_title or 'unknown'}\n"
            f"Deterministic selected canonical name: {selected}\n"
            "Candidate options:\n"
            + "\n".join(f"- {item}" for item in options)
            + "\nHeuristic hints:\n"
            + hints_block
            + "\n\nReturn JSON only with this schema:\n"
            "{\n"
            '  "canonical_name": "one option from Candidate options",\n'
            '  "merge_names": ["subset of Candidate options that should resolve to canonical_name"],\n'
            '  "keep_separate": ["subset of Candidate options that should not merge"],\n'
            '  "rationale": "short explanation"\n'
            "}\n"
            "Every option must appear exactly once in either merge_names or keep_separate.\n"
            "canonical_name must be included in merge_names."
        )

    def _validate_llm_merge_decision(self, payload: Dict[str, Any], options: List[str]) -> bool:
        allowed = {str(item).strip() for item in options if str(item).strip()}
        canonical_name = str(payload.get("canonical_name") or "").strip()
        merge_names = [str(item).strip() for item in (payload.get("merge_names") or []) if str(item).strip()]
        keep_separate = [str(item).strip() for item in (payload.get("keep_separate") or []) if str(item).strip()]
        if canonical_name not in allowed:
            return False
        if canonical_name not in merge_names:
            return False
        covered = set(merge_names) | set(keep_separate)
        if covered != allowed:
            return False
        if set(merge_names) & set(keep_separate):
            return False
        return True

    def _filter_resolved_candidates(
        self,
        unresolved: List[Dict[str, Any]],
        llm_merge_map: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        if not llm_merge_map:
            return unresolved
        remaining: List[Dict[str, Any]] = []
        for candidate in unresolved:
            options = [str(item).strip() for item in (candidate.get("options") or []) if str(item).strip()]
            selected = str(candidate.get("selected") or "").strip()
            rewritten = [llm_merge_map.get(option, option) for option in options]
            unique_rewritten = sorted(set(rewritten))
            if len(unique_rewritten) <= 1:
                continue
            if selected and all(item == selected for item in rewritten):
                continue
            remaining.append(candidate)
        return remaining

    def _build_overlap_candidate_groups(self, entity_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        alias_names = defaultdict(set)
        for row in entity_rows:
            name = str(row.get("name") or "").strip()
            aliases = [str(item).strip() for item in (row.get("aliases") or []) if str(item).strip()]
            for alias in aliases:
                alias_names[self._normalized_entity_key(alias)].add(name)
        groups: Dict[Tuple[str, ...], Dict[str, Any]] = {}
        for row in entity_rows:
            name = str(row.get("name") or "").strip()
            if not name:
                continue
            alias_of = sorted(alias_names.get(self._normalized_entity_key(name)) or [])
            if not alias_of or name in alias_of:
                continue
            options = sorted(set([name] + alias_of))
            if len(options) < 2:
                continue
            key = tuple(options)
            groups[key] = {
                "normalized_name": self._normalized_entity_key(options[0]),
                "options": options,
                "selected": self.normalizer.choose_canonical_name(options),
            }
        return list(groups.values())

    def _canonical_name_for_options(self, options: List[str], *, hints: Dict[str, Dict[str, Any]]) -> str:
        return self.normalizer.choose_canonical_name(options, hints=hints)

    def _canonicalize_candidate_name(self, raw: str, *, hints: Dict[str, Dict[str, Any]]) -> str:
        return self.normalizer.canonicalize_candidate_name(raw, hints=hints)

    def _expand_short_character_name(self, name: str, candidates: List[str]) -> str:
        return self.normalizer.expand_short_character_name(name, candidates)

    def _repair_entity_registry(
        self,
        entity_registry: List[Dict[str, Any]],
        merge_map: Dict[str, str],
        type_corrections: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {}
        for row in entity_registry:
            source_name = str(row.get("name") or "").strip()
            if self._is_bad_alias_like_name(source_name):
                continue
            target_name = merge_map.get(source_name, source_name)
            if not target_name:
                continue
            current = merged.setdefault(target_name, json.loads(json.dumps(row)))
            current["name"] = target_name
            current["entity_type"] = type_corrections.get(target_name) or type_corrections.get(source_name) or row.get("entity_type", "unknown")
            current_descriptions = list(current.get("descriptions") or [])
            for description in row.get("descriptions") or []:
                if description not in current_descriptions:
                    current_descriptions.append(description)
            current["descriptions"] = current_descriptions
            current_changes = list(current.get("state_changes") or [])
            for change in row.get("state_changes") or []:
                if change not in current_changes:
                    current_changes.append(change)
            current["state_changes"] = current_changes
        return sorted(merged.values(), key=lambda item: (int(item.get("first_seen", {}).get("book_index") or 0), item.get("name", "")))

    def _repair_alias_map(self, alias_map: Dict[str, List[str]], merge_map: Dict[str, str]) -> Dict[str, List[str]]:
        repaired: Dict[str, set[str]] = defaultdict(set)
        for canonical, aliases in alias_map.items():
            target = merge_map.get(canonical, canonical)
            if not target:
                continue
            repaired[target].add(target)
            for alias in aliases or []:
                remapped = merge_map.get(alias, alias)
                if remapped:
                    repaired[target].add(remapped)
        return {key: sorted(values) for key, values in sorted(repaired.items())}

    def _repair_scene_analyses(self, scenes: List[Dict[str, Any]], merge_map: Dict[str, str]) -> List[Dict[str, Any]]:
        cleaned: List[Dict[str, Any]] = []
        for scene in scenes:
            repaired = dict(scene)
            repaired["canonical_characters"] = self._remap_name_list(scene.get("canonical_characters") or [], merge_map)
            repaired["entities_present"] = self._remap_name_list(scene.get("entities_present") or [], merge_map)
            repaired["entity_descriptions"] = self._remap_named_payload(scene.get("entity_descriptions") or [], merge_map)
            repaired["state_changes"] = self._remap_named_payload(scene.get("state_changes") or [], merge_map)
            repaired["relationship_changes"] = self._remap_named_payload(scene.get("relationship_changes") or [], merge_map)
            repaired["character_mentions"] = self._remap_named_payload(scene.get("character_mentions") or [], merge_map)
            repaired["events"] = self._remap_named_payload(scene.get("events") or [], merge_map)
            repaired["location"] = self._remap_named_payload(scene.get("location") or {}, merge_map)
            entities = []
            for entity in repaired.get("entities_present", []) or []:
                name = str(entity.get("name") or "").strip()
                if not name or self._is_bad_alias_like_name(name):
                    continue
                entities.append(entity)
            repaired["entities_present"] = entities
            cleaned.append(repaired)
        return cleaned

    def _repair_state_result(self, state_result: Dict[str, Any], merge_map: Dict[str, str]) -> Dict[str, Any]:
        repaired = dict(state_result or {})
        repaired["transitions"] = self._remap_named_payload(repaired.get("transitions") or [], merge_map)
        repaired["latest_state"] = self._remap_named_payload(repaired.get("latest_state") or [], merge_map)
        return repaired

    def _repair_canon_snapshot(self, canon_snapshot: List[Dict[str, Any]], merge_map: Dict[str, str]) -> List[Dict[str, Any]]:
        return self._remap_named_payload(canon_snapshot or [], merge_map)

    def _repair_timeline(self, timeline: List[Dict[str, Any]], merge_map: Dict[str, str]) -> List[Dict[str, Any]]:
        return self._remap_named_payload(timeline or [], merge_map)

    def _repair_character_timelines(self, character_timelines: List[Dict[str, Any]], merge_map: Dict[str, str]) -> List[Dict[str, Any]]:
        return self._remap_named_payload(character_timelines or [], merge_map)

    def _repair_causal_graph_result(self, causal_graph_result: Dict[str, Any], merge_map: Dict[str, str]) -> Dict[str, Any]:
        repaired = dict(causal_graph_result or {})
        graph = dict(repaired.get("graph") or {})
        if "events" in graph:
            graph["events"] = self._remap_named_payload(graph.get("events") or [], merge_map)
        if "critical_path" in graph:
            graph["critical_path"] = self._remap_named_payload(graph.get("critical_path") or [], merge_map)
        if "causal_chains" in graph:
            graph["causal_chains"] = self._remap_named_payload(graph.get("causal_chains") or [], merge_map)
        if "divergence_points" in graph:
            graph["divergence_points"] = self._remap_named_payload(graph.get("divergence_points") or [], merge_map)
        if "flexible_events" in graph:
            graph["flexible_events"] = self._remap_named_payload(graph.get("flexible_events") or [], merge_map)
        repaired["graph"] = graph
        return repaired

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

    def _remap_name_list(self, values: List[Any], merge_map: Dict[str, str]) -> List[Any]:
        repaired = []
        for item in values:
            if isinstance(item, str):
                remapped = merge_map.get(item, item)
                if remapped and not self._is_bad_alias_like_name(remapped):
                    repaired.append(remapped)
            elif isinstance(item, dict):
                remapped = dict(item)
                if "name" in remapped:
                    remapped_name = merge_map.get(str(remapped.get("name") or ""), str(remapped.get("name") or ""))
                    if remapped_name and not self._is_bad_alias_like_name(remapped_name):
                        remapped["name"] = remapped_name
                        repaired.append(remapped)
                else:
                    repaired.append(remapped)
            else:
                repaired.append(item)
        return repaired

    def _entity_type_corrections(self, entity_registry: List[Dict[str, Any]], merge_map: Dict[str, str]) -> Dict[str, str]:
        corrections: Dict[str, str] = {}
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in entity_registry:
            source_name = str(row.get("name") or "").strip()
            target = merge_map.get(source_name, source_name)
            if target:
                grouped[target].append(row)
        for target, rows in grouped.items():
            types = [str(row.get("entity_type") or "").strip().lower() for row in rows if str(row.get("entity_type") or "").strip()]
            descriptions = [
                entry.get("description", "")
                for row in rows
                for entry in (row.get("descriptions") or [])
                if isinstance(entry, dict)
            ]
            inferred = self.normalizer.infer_entity_type(
                target,
                existing_type=Counter(types).most_common(1)[0][0] if types else "",
                descriptions=descriptions,
            )
            if inferred:
                corrections[target] = inferred
        return corrections

    def _summarise_reports(self, reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "duplicate_identities_removed": sum(int(report.get("duplicate_identities_removed") or 0) for report in reports),
            "malformed_nodes_removed": sum(int(report.get("malformed_nodes_removed") or 0) for report in reports),
            "entity_type_corrections": sum(len(report.get("entity_type_corrections") or {}) for report in reports),
            "remaining_unresolved_merge_candidates": sum(len(report.get("remaining_unresolved_merge_candidates") or []) for report in reports),
            "llm_merge_decisions": sum(len(report.get("llm_merge_decisions") or []) for report in reports),
        }

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

    def _repair_stable_character_states(self, rows: List[Dict[str, Any]], merge_map: Dict[str, str]) -> List[Dict[str, Any]]:
        return self._remap_named_payload(rows or [], merge_map)

    def consolidate_graph(self, *, series_id: str) -> Dict[str, Any]:
        driver = self.neo4j._ensure_driver()
        self.neo4j.probe_connection()
        session_kwargs = {"database": self.neo4j.database} if self.neo4j.database else {}
        llm_merge_decisions: List[Dict[str, Any]] = []
        with driver.session(**session_kwargs) as session:
            entity_rows = [
                row.data()
                for row in session.run(
                    """
                    MATCH (e:Entity {series_id: $series_id})
                    OPTIONAL MATCH (e)-[:HAS_ALIAS]->(a:Alias {series_id: $series_id})
                    RETURN e.name AS name,
                           coalesce(e.entity_type, '') AS entity_type,
                           collect(DISTINCT a.text) AS aliases
                    ORDER BY name ASC
                    """,
                    series_id=series_id,
                )
            ]
            alias_map = {
                str(row.get("name") or "").strip(): [str(item).strip() for item in (row.get("aliases") or []) if str(item).strip()]
                for row in entity_rows
                if str(row.get("name") or "").strip()
            }
            merge_map, _ = self.normalizer.build_merge_map(
                names=[str(row.get("name") or "").strip() for row in entity_rows],
                alias_map=alias_map,
            )
            overlap_merge_map = self._overlap_merge_candidates(entity_rows)
            merge_map.update(overlap_merge_map)
            merged = 0
            corrected = 0
            removed = 0
            for row in entity_rows:
                name = str(row.get("name") or "").strip()
                if not name:
                    continue
                inferred = self.normalizer.infer_entity_type(name, existing_type=str(row.get("entity_type") or ""))
                if inferred and inferred != str(row.get("entity_type") or "").strip().lower():
                    self.neo4j._run(
                        session,
                        "MATCH (e:Entity {series_id: $series_id, name: $name}) SET e.entity_type = $entity_type",
                        series_id=series_id,
                        name=name,
                        entity_type=inferred,
                    )
                    corrected += 1
                if self.normalizer.is_bad_alias_like_name(name):
                    self.neo4j._run(
                        session,
                        "MATCH (e:Entity {series_id: $series_id, name: $name}) DETACH DELETE e",
                        series_id=series_id,
                        name=name,
                    )
                    removed += 1
                    continue
                target = merge_map.get(name, name)
                if target and target != name:
                    self._merge_graph_entity(session, series_id=series_id, source=name, target=target)
                    merged += 1
            residual_rows = [
                row.data()
                for row in session.run(
                    """
                    MATCH (e:Entity {series_id: $series_id})
                    OPTIONAL MATCH (e)-[:HAS_ALIAS]->(a:Alias {series_id: $series_id})
                    RETURN e.name AS name,
                           coalesce(e.entity_type, '') AS entity_type,
                           collect(DISTINCT a.text) AS aliases
                    ORDER BY name ASC
                    """,
                    series_id=series_id,
                )
            ]
            residual_alias_map = {
                str(row.get("name") or "").strip(): [str(item).strip() for item in (row.get("aliases") or []) if str(item).strip()]
                for row in residual_rows
                if str(row.get("name") or "").strip()
            }
            _, residual_unresolved = self.normalizer.build_merge_map(
                names=[str(row.get("name") or "").strip() for row in residual_rows],
                alias_map=residual_alias_map,
            )
            overlap_candidates = self._build_overlap_candidate_groups(residual_rows)
            llm_merge_map, llm_merge_decisions = self._resolve_unresolved_candidates_with_llm(
                residual_unresolved + overlap_candidates,
                hints={},
                series_id=series_id,
                book_title="",
            )
            for source, target in sorted(llm_merge_map.items()):
                if source and target and source != target:
                    self._merge_graph_entity(session, series_id=series_id, source=source, target=target)
                    merged += 1
            final_rows = [
                row.data()
                for row in session.run(
                    """
                    MATCH (e:Entity {series_id: $series_id})
                    RETURN e.name AS name,
                           coalesce(e.entity_type, '') AS entity_type
                    ORDER BY name ASC
                    """,
                    series_id=series_id,
                )
            ]
            for row in final_rows:
                name = str(row.get("name") or "").strip()
                if not name:
                    continue
                inferred = self.normalizer.infer_entity_type(name, existing_type=str(row.get("entity_type") or ""))
                if inferred and inferred != str(row.get("entity_type") or "").strip().lower():
                    self.neo4j._run(
                        session,
                        "MATCH (e:Entity {series_id: $series_id, name: $name}) SET e.entity_type = $entity_type",
                        series_id=series_id,
                        name=name,
                        entity_type=inferred,
                    )
                    corrected += 1
        return {
            "series_id": series_id,
            "merged_entities": merged,
            "malformed_entities_removed": removed,
            "entity_type_corrections": corrected,
            "llm_merge_decisions": llm_merge_decisions,
        }

    def _overlap_merge_candidates(self, entity_rows: List[Dict[str, Any]]) -> Dict[str, str]:
        alias_names: Dict[str, List[str]] = defaultdict(list)
        type_by_name: Dict[str, str] = {}
        for row in entity_rows:
            name = str(row.get("name") or "").strip()
            if not name:
                continue
            type_by_name[name] = str(row.get("entity_type") or "").strip().lower()
            for alias in [str(item).strip() for item in (row.get("aliases") or []) if str(item).strip()]:
                alias_names[self._normalized_entity_key(alias)].append(name)
        merge_map: Dict[str, str] = {}
        for row in entity_rows:
            name = str(row.get("name") or "").strip()
            if not name:
                continue
            targets = sorted(set(alias_names.get(self._normalized_entity_key(name)) or []))
            if not targets or name in targets:
                continue
            preferred = self._preferred_overlap_target(name, targets, type_by_name.get(name, ""))
            if preferred and preferred != name:
                merge_map[name] = preferred
        return merge_map

    def _preferred_overlap_target(self, name: str, targets: List[str], entity_type: str) -> str:
        if not targets:
            return ""
        if self.normalizer.is_bad_alias_like_name(name):
            return max(targets, key=lambda item: (len(item.split()), len(item)))
        if name.endswith("'s"):
            base = self.normalizer.canonicalize_candidate_name(name)
            for target in targets:
                if self._normalized_entity_key(target) == self._normalized_entity_key(base):
                    return target
        if not self.normalizer.looks_like_character_name(name) or entity_type not in {"character", ""}:
            return max(targets, key=lambda item: (len(item.split()), len(item)))
        expanded = self.normalizer.expand_short_character_name(name, targets)
        if expanded:
            return expanded
        return max(targets, key=lambda item: (len(item.split()), len(item)))

    def _merge_graph_entity(self, session, *, series_id: str, source: str, target: str) -> None:
        self.neo4j._run(
            session,
            """
            MERGE (target:Entity {series_id: $series_id, name: $target})
            MERGE (a:Alias {series_id: $series_id, text: $source})
            MERGE (target)-[:HAS_ALIAS]->(a)
            """,
            series_id=series_id,
            source=source,
            target=target,
        )
        rewrites = (
            """
            MATCH (b:Book {series_id: $series_id})-[r:HAS_ENTITY]->(source:Entity {series_id: $series_id, name: $source})
            MERGE (target:Entity {series_id: $series_id, name: $target})
            MERGE (b)-[r2:HAS_ENTITY]->(target)
            SET r2.mention_count = coalesce(r2.mention_count, 0) + coalesce(r.mention_count, 0)
            DELETE r
            """,
            """
            MATCH (sc:Scene {series_id: $series_id})-[r:FEATURES]->(source:Entity {series_id: $series_id, name: $source})
            MERGE (target:Entity {series_id: $series_id, name: $target})
            MERGE (sc)-[:FEATURES]->(target)
            DELETE r
            """,
            """
            MATCH (source:Entity {series_id: $series_id, name: $source})-[r:INVOLVED_IN]->(e:Event {series_id: $series_id})
            MERGE (target:Entity {series_id: $series_id, name: $target})
            MERGE (target)-[:INVOLVED_IN]->(e)
            DELETE r
            """,
            """
            MATCH (source:Entity {series_id: $series_id, name: $source})-[r:HAD_STATE_CHANGE]->(st:StateTransition {series_id: $series_id})
            MERGE (target:Entity {series_id: $series_id, name: $target})
            SET st.entity_name = $target
            MERGE (target)-[:HAD_STATE_CHANGE]->(st)
            DELETE r
            """,
            """
            MATCH (source:Entity {series_id: $series_id, name: $source})-[r:HAS_CANON_SNAPSHOT]->(cs:CanonSnapshot {series_id: $series_id})
            MERGE (target:Entity {series_id: $series_id, name: $target})
            SET cs.entity_name = $target
            MERGE (target)-[:HAS_CANON_SNAPSHOT]->(cs)
            DELETE r
            """,
            """
            MATCH (source:Entity {series_id: $series_id, name: $source})-[r:HAS_RELATIONSHIP]->(other:Entity {series_id: $series_id})
            MERGE (target:Entity {series_id: $series_id, name: $target})
            MERGE (target)-[r2:HAS_RELATIONSHIP {pair: coalesce(r.pair, $target + '|' + other.name)}]->(other)
            SET r2 += properties(r)
            DELETE r
            """,
            """
            MATCH (other:Entity {series_id: $series_id})-[r:HAS_RELATIONSHIP]->(source:Entity {series_id: $series_id, name: $source})
            MERGE (target:Entity {series_id: $series_id, name: $target})
            MERGE (other)-[r2:HAS_RELATIONSHIP {pair: coalesce(r.pair, other.name + '|' + $target)}]->(target)
            SET r2 += properties(r)
            DELETE r
            """,
            """
            MATCH (rc:RelationshipChange {series_id: $series_id, source_entity: $source})
            SET rc.source_entity = $target
            """,
            """
            MATCH (rc:RelationshipChange {series_id: $series_id, target_entity: $source})
            SET rc.target_entity = $target
            """,
            """
            MATCH (rc:RelationshipChange {series_id: $series_id})-[r:CHANGE_SOURCE]->(source:Entity {series_id: $series_id, name: $source})
            MERGE (target:Entity {series_id: $series_id, name: $target})
            MERGE (rc)-[:CHANGE_SOURCE]->(target)
            DELETE r
            """,
            """
            MATCH (rc:RelationshipChange {series_id: $series_id})-[r:CHANGE_TARGET]->(source:Entity {series_id: $series_id, name: $source})
            MERGE (target:Entity {series_id: $series_id, name: $target})
            MERGE (rc)-[:CHANGE_TARGET]->(target)
            DELETE r
            """,
            """
            MATCH (source:Entity {series_id: $series_id, name: $source})-[r:HAS_ALIAS]->(a:Alias {series_id: $series_id})
            MERGE (target:Entity {series_id: $series_id, name: $target})
            MERGE (target)-[:HAS_ALIAS]->(a)
            DELETE r
            """,
        )
        for query in rewrites:
            self.neo4j._run(session, query, series_id=series_id, source=source, target=target)
        self.neo4j._run(
            session,
            "MATCH (e:Entity {series_id: $series_id, name: $source}) DETACH DELETE e",
            series_id=series_id,
            source=source,
        )

    def _looks_like_character_name(self, value: str) -> bool:
        return self.normalizer.looks_like_character_name(value)

    def _is_bad_alias_like_name(self, value: str) -> bool:
        return self.normalizer.is_bad_alias_like_name(value)

    def _normalized_entity_key(self, value: str) -> str:
        return self.normalizer.normalized_entity_key(value)

    def _title_case_like(self, value: str) -> str:
        return self.normalizer.title_case_like(value)

    def _contract_book_title(self, payload: Dict[str, Any]) -> str:
        books = (((payload.get("inputs") or {}).get("books")) or [])
        first = books[0] if books else {}
        return str(first.get("title") or Path(str(first.get("path") or "")).name or "Unknown").strip()

    def _contract_book_index(self, payload: Dict[str, Any]) -> int:
        books = (((payload.get("inputs") or {}).get("books")) or [])
        first = books[0] if books else {}
        return int(first.get("book_index") or 0)

    def _now_utc(self) -> str:
        return datetime.now(timezone.utc).isoformat()
