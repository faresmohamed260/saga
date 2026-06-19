from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Callable

from saga.providers.llm_client import LLMClient
from saga.services.narrative_generation_service import NarrativeGenerationService
from saga.services.sqlite_contract_adapter import load_contract_like
from saga.storage.persistence import SagaSQLiteStore


class DatabaseDecoderService:
    """Generate bounded decoder outputs from DB-backed books and persist them back into SQLite."""

    def __init__(
        self,
        *,
        sqlite_store: SagaSQLiteStore | None = None,
        decoder: NarrativeGenerationService | None = None,
    ) -> None:
        self.sqlite_store = sqlite_store or SagaSQLiteStore()
        self.decoder = decoder

    def generate_and_store(
        self,
        *,
        book_ref: str,
        series_id: str = "",
        story_mode: str,
        provider: str = "",
        user_prompt: str,
        chapter_count: int = 1,
        primary_pov_character: str = "",
        continuity_anchor: str = "",
        divergence_anchor: str = "",
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        contract = load_contract_like(book_ref)
        book_id = str(book_ref).split("db://book/", 1)[-1].strip()
        controls = self._controls_for_mode(
            story_mode=story_mode,
            chapter_count=chapter_count,
            primary_pov_character=primary_pov_character,
            continuity_anchor=continuity_anchor,
            divergence_anchor=divergence_anchor,
        )

        with tempfile.TemporaryDirectory(prefix="saga_decoder_") as temp_dir:
            requested_provider = self._normalize_provider(provider)
            active_decoder = self.decoder or self._build_decoder(provider=requested_provider)
            try:
                out_dir = self._generate_with_decoder(
                    decoder=active_decoder,
                    contract=contract,
                    user_prompt=user_prompt,
                    output_dir=temp_dir,
                    generation_controls=controls,
                    progress_callback=progress_callback,
                )
            except Exception as exc:
                if not self._is_rate_limit_error(exc) or requested_provider:
                    raise
                fallback_decoder = self._fallback_decoder_for_rate_limit(active_decoder)
                if fallback_decoder is None:
                    raise
                active_decoder = fallback_decoder
                out_dir = self._generate_with_decoder(
                    decoder=active_decoder,
                    contract=contract,
                    user_prompt=user_prompt,
                    output_dir=temp_dir,
                    generation_controls=controls,
                    progress_callback=progress_callback,
                )
            out_path = Path(out_dir)
            blueprint = self._load_json(out_path / "blueprint.json")
            progress = self._load_json(out_path / "progress.json")
            chapters = self._load_chapters(out_path)

        full_text = "\n\n".join(chapter["prose_text"] for chapter in chapters if str(chapter.get("prose_text") or "").strip())
        verification = self._verify_output(
            user_prompt=user_prompt,
            story_mode=story_mode,
            canon_position=str(controls.get("canon_position") or ""),
            blueprint=blueprint,
            chapters=chapters,
            full_text=full_text,
        )
        stored = self.sqlite_store.store_generated_story(
            book_id=book_id,
            story_mode=story_mode,
            title=str((blueprint or {}).get("title") or f"{story_mode} story").strip(),
            user_prompt=user_prompt,
            canon_position=str(controls.get("canon_position") or ""),
            primary_pov_character=str(controls.get("primary_pov_character") or ""),
            llm_provider=active_decoder.llm.provider_name(),
            llm_model=active_decoder.llm.resolved_model_name(),
            status="success" if verification.get("valid") else "needs_review",
            output_text=full_text,
            blueprint=blueprint,
            progress=progress,
            verification=verification,
            metadata={
                "book_ref": book_ref,
                "series_id": series_id or str((contract.get("inputs") or {}).get("series", {}).get("series_id") or ""),
                "story_mode": story_mode,
                "selected_provider": requested_provider or self._provider_key_for_decoder(active_decoder),
                "generation_controls": controls,
                "planner_provider": active_decoder.planner_llm.provider_name(),
                "planner_model": active_decoder.planner_llm.resolved_model_name(),
                "prose_provider": active_decoder.prose_llm.provider_name(),
                "prose_model": active_decoder.prose_llm.resolved_model_name(),
            },
            chapters=chapters,
        )
        return {
            **stored,
            "verification": verification,
            "chapter_count": len(chapters),
            "output_characters": len(full_text),
        }

    def _build_decoder(self, *, provider: str = "") -> NarrativeGenerationService:
        provider_key = self._normalize_provider(provider)
        if provider_key == "general_compute":
            primary_llm = LLMClient(mode=LLMClient.MODE_GENERAL_COMPUTE, allow_cross_provider_fallback=False)
            return NarrativeGenerationService(
                llm_client=primary_llm,
                planner_llm_client=primary_llm,
                prose_llm_client=primary_llm,
            )
        if provider_key == "codex":
            primary_llm = LLMClient(mode=LLMClient.MODE_CODEX, allow_cross_provider_fallback=False)
            return NarrativeGenerationService(
                llm_client=primary_llm,
                planner_llm_client=primary_llm,
                prose_llm_client=primary_llm,
            )

        primary_llm = LLMClient(mode=LLMClient.MODE_GPT_OSS, allow_cross_provider_fallback=False)
        planner_llm = primary_llm
        if not provider_key and self._provider_ready("general_compute"):
            planner_llm = LLMClient(mode=LLMClient.MODE_GENERAL_COMPUTE)
        return NarrativeGenerationService(
            llm_client=primary_llm,
            planner_llm_client=planner_llm,
            prose_llm_client=primary_llm,
        )

    def _provider_ready(self, provider_name: str) -> bool:
        try:
            statuses = self.sqlite_store.get_provider_statuses(provider_name)
        except Exception:
            return False
        for row in statuses:
            if str(row.get("probe_status") or "").strip().lower() == "ok":
                return True
        return False

    def _fallback_decoder_for_rate_limit(self, active_decoder: NarrativeGenerationService) -> NarrativeGenerationService | None:
        planner_mode = str(getattr(active_decoder.planner_llm, "mode", "") or "").strip().lower()
        if planner_mode != LLMClient.MODE_GENERAL_COMPUTE and self._provider_ready("general_compute"):
            return self._build_decoder()
        return None

    def _normalize_provider(self, provider: str) -> str:
        value = str(provider or "").strip().lower()
        if value in {"ollama", "general_compute", "codex"}:
            return value
        return ""

    def _provider_key_for_decoder(self, decoder: NarrativeGenerationService) -> str:
        planner_mode = str(getattr(decoder.planner_llm, "mode", "") or "").strip().lower()
        llm_mode = str(getattr(decoder.llm, "mode", "") or "").strip().lower()
        if planner_mode == LLMClient.MODE_GENERAL_COMPUTE and llm_mode == LLMClient.MODE_GENERAL_COMPUTE:
            return "general_compute"
        if llm_mode == LLMClient.MODE_CODEX:
            return "codex"
        return "ollama"

    def _generate_with_decoder(
        self,
        *,
        decoder: NarrativeGenerationService,
        contract: dict[str, Any],
        user_prompt: str,
        output_dir: str,
        generation_controls: dict[str, Any],
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> Path:
        return decoder.generate_sequel_from_contract(
            contract,
            user_prompt=user_prompt,
            output_dir=output_dir,
            generation_controls=generation_controls,
            prefer_exported_context=True,
            prefer_exported_blueprint=False,
            progress_callback=progress_callback,
        )

    def _is_rate_limit_error(self, exc: Exception) -> bool:
        message = str(exc or "").lower()
        return any(token in message for token in ("429", "rate_limited", "rate limit", "quota", "balance"))

    def _controls_for_mode(
        self,
        *,
        story_mode: str,
        chapter_count: int,
        primary_pov_character: str,
        continuity_anchor: str,
        divergence_anchor: str,
    ) -> dict[str, Any]:
        mode = str(story_mode or "").strip().lower()
        mapping = {
            "pre_canon": "pre_canon",
            "mid_canon": "mid_canon_insert",
            "post_canon": "post_canon",
            "alternate_universe": "mid_canon_divergent",
        }
        canon_position = mapping.get(mode, "post_canon")
        controls: dict[str, Any] = {
            "chapter_count": max(1, int(chapter_count)),
            "canon_position": canon_position,
        }
        if primary_pov_character:
            controls["primary_pov_character"] = primary_pov_character
        if continuity_anchor:
            controls["continuity_anchor"] = continuity_anchor
        if canon_position == "mid_canon_divergent":
            controls["divergence_anchor"] = divergence_anchor or "diverges at a critical canon decision point"
        return controls

    def _load_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_chapters(self, output_dir: Path) -> list[dict[str, Any]]:
        chapters: list[dict[str, Any]] = []
        for path in sorted(output_dir.glob("chapter_*.txt")):
            raw = path.read_text(encoding="utf-8")
            lines = raw.splitlines()
            title = lines[1].strip() if len(lines) >= 2 else path.stem
            prose = "\n".join(lines[3:]).strip() if len(lines) >= 4 else raw.strip()
            number = 0
            try:
                number = int(path.stem.split("_")[-1])
            except Exception:
                number = len(chapters) + 1
            chapters.append(
                {
                    "chapter_number": number,
                    "chapter_title": title,
                    "prose_text": prose,
                    "metadata": {"source_path": str(path)},
                }
            )
        return chapters

    def _verify_output(
        self,
        *,
        user_prompt: str,
        story_mode: str,
        canon_position: str,
        blueprint: dict[str, Any],
        chapters: list[dict[str, Any]],
        full_text: str,
    ) -> dict[str, Any]:
        issues: list[str] = []
        if not str((blueprint or {}).get("title") or "").strip():
            issues.append("missing_blueprint_title")
        if not chapters:
            issues.append("no_chapters_generated")
        if len(full_text.split()) < 250:
            issues.append("story_too_short")
        if canon_position and str((blueprint or {}).get("canon_placement") or "").strip() != canon_position:
            issues.append("canon_position_mismatch")
        return {
            "valid": not issues,
            "issues": issues,
            "story_mode": story_mode,
            "prompt_excerpt": user_prompt[:220],
            "chapter_count": len(chapters),
            "word_count": len(full_text.split()),
        }
