from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

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
        self.decoder = decoder or NarrativeGenerationService()

    def generate_and_store(
        self,
        *,
        book_ref: str,
        story_mode: str,
        user_prompt: str,
        chapter_count: int = 1,
        primary_pov_character: str = "",
        continuity_anchor: str = "",
        divergence_anchor: str = "",
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
            out_dir = self.decoder.generate_sequel_from_contract(
                contract,
                user_prompt=user_prompt,
                output_dir=temp_dir,
                generation_controls=controls,
                prefer_exported_context=True,
                prefer_exported_blueprint=False,
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
            llm_provider=self.decoder.llm.provider_name(),
            llm_model=self.decoder.llm.resolved_model_name(),
            status="success" if verification.get("valid") else "needs_review",
            output_text=full_text,
            blueprint=blueprint,
            progress=progress,
            verification=verification,
            metadata={
                "book_ref": book_ref,
                "story_mode": story_mode,
                "generation_controls": controls,
            },
            chapters=chapters,
        )
        return {
            **stored,
            "verification": verification,
            "chapter_count": len(chapters),
            "output_characters": len(full_text),
        }

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
