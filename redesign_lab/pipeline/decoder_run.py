"""Redesign-local decoder stage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from infrastructure.llm_client import LLMClient
from redesign_lab.pipeline.contracts import validate_contract
from services.narrative_generation_service import NarrativeGenerationService


class DecoderRunStage:
    """Run sequel generation from redesign-local retrieval context."""

    def __init__(
        self,
        *,
        blueprint_spec: Dict[str, Any],
        outline_spec: Dict[str, Any],
        prose_spec: Dict[str, Any],
    ) -> None:
        self.blueprint_spec = blueprint_spec
        self.outline_spec = outline_spec
        self.prose_spec = prose_spec

    def build_decoder_context(
        self,
        *,
        series_id: str,
        retrieval_context: Dict[str, Any],
        generation_controls: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload = {
            "series_id": series_id,
            "retrieval_context": retrieval_context,
            "generation_controls": generation_controls,
            "planner_candidate": self.blueprint_spec["candidate_id"],
            "outline_candidate": self.outline_spec["candidate_id"],
            "prose_candidate": self.prose_spec["candidate_id"],
        }
        return validate_contract("decoder_context", payload)

    def run(
        self,
        *,
        series_id: str,
        user_prompt: str,
        output_dir: str | Path,
        generation_controls: Dict[str, Any],
    ) -> Path:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        blueprint_llm = self._build_llm(self.blueprint_spec)
        outline_llm = self._build_llm(self.outline_spec)
        prose_llm = self._build_llm(self.prose_spec)

        helper_service = NarrativeGenerationService(
            planner_llm_client=outline_llm,
            prose_llm_client=prose_llm,
        )
        retrieval_context = helper_service.build_retrieval_context_from_neo4j(series_id=series_id)
        compiled = helper_service.compile_context(
            retrieval_context,
            user_prompt,
            generation_controls=generation_controls,
        )

        blueprint_service = NarrativeGenerationService(
            planner_llm_client=blueprint_llm,
            prose_llm_client=prose_llm,
            hybrid_retriever=helper_service.hybrid_retriever,
            target_chapters=int(compiled.get("generation_controls", {}).get("chapter_count") or helper_service.target_chapters),
        )
        outline_service = NarrativeGenerationService(
            planner_llm_client=outline_llm,
            prose_llm_client=prose_llm,
            hybrid_retriever=helper_service.hybrid_retriever,
            target_chapters=int(compiled.get("generation_controls", {}).get("chapter_count") or helper_service.target_chapters),
        )
        prose_service = NarrativeGenerationService(
            planner_llm_client=outline_llm,
            prose_llm_client=prose_llm,
            hybrid_retriever=helper_service.hybrid_retriever,
            target_chapters=int(compiled.get("generation_controls", {}).get("chapter_count") or helper_service.target_chapters),
        )

        blueprint = blueprint_service.generate_blueprint(compiled)
        controls = compiled.get("generation_controls") or {}
        if not outline_service._blueprint_matches_controls(blueprint, controls):
            raise ValueError("Redesign blueprint candidate did not satisfy generation controls.")
        blueprint["total_chapters"] = int(controls.get("chapter_count") or blueprint.get("total_chapters") or outline_service.target_chapters)
        (output_dir / "blueprint.json").write_text(json.dumps(blueprint, ensure_ascii=False, indent=2), encoding="utf-8")
        self._announce(f"[decoder] Blueprint generated with {blueprint.get('total_chapters')} chapters.")

        world_state = outline_service.initialise_world_state(compiled)
        previous_summaries: List[str] = []
        rolling_previous_ending = str((compiled.get("story_ending") or {}).get("last_scene_summary") or "").strip()
        scene_memory = prose_service._empty_scene_memory()
        progress: Dict[str, Any] = {
            "compiled_context": compiled,
            "completed_chapters": [],
            "blueprint_candidate": self.blueprint_spec["candidate_id"],
            "outline_candidate": self.outline_spec["candidate_id"],
            "prose_candidate": self.prose_spec["candidate_id"],
        }

        total_chapters = int(blueprint.get("total_chapters") or outline_service.target_chapters)
        for chapter_number in range(1, total_chapters + 1):
            self._progress("outline", chapter_number, total_chapters, f"chapter {chapter_number}")
            current_story_position = outline_service._current_story_position(
                compiled_context=compiled,
                previous_summaries=previous_summaries,
                rolling_previous_ending=rolling_previous_ending,
            )
            chapter_controls = outline_service._chapter_controls_for_generation(
                blueprint=blueprint,
                controls=controls,
                chapter_number=chapter_number,
            )
            chapter_context_packet = outline_service.hybrid_retriever.build_outline_context_packet(
                retrieval_context=retrieval_context,
                compiled_context=compiled,
                blueprint=blueprint,
                world_state=world_state,
                current_story_position=current_story_position,
                chapter_number=chapter_number,
                previous_summaries=previous_summaries,
                chapter_controls=chapter_controls,
            )
            outline = outline_service.generate_chapter_outline(
                blueprint=blueprint,
                compiled_context=compiled,
                world_state=world_state,
                previous_summaries=previous_summaries,
                chapter_number=chapter_number,
                current_story_position=current_story_position,
                chapter_context_packet=chapter_context_packet,
            )

            scenes = outline.get("scenes", []) or []
            scenes_prose: List[str] = []
            chapter_debug: Dict[str, Any] = {
                "chapter_number": chapter_number,
                "chapter_title": outline.get("chapter_title", f"Chapter {chapter_number}"),
                "outline_packet": chapter_context_packet,
                "scenes": [],
            }
            previous_scene_ending = rolling_previous_ending

            for scene_index, scene in enumerate(scenes, start=1):
                self._progress("prose", scene_index, len(scenes), f"chapter {chapter_number} scene {scene_index}")
                scene_context_packet = prose_service.hybrid_retriever.build_scene_context_packet(
                    retrieval_context=retrieval_context,
                    compiled_context=compiled,
                    scene_outline=scene,
                    chapter_outline=outline,
                    world_state=world_state,
                    scene_memory=scene_memory,
                    previous_scene_ending=previous_scene_ending,
                    chapter_controls=chapter_controls,
                )
                prose = prose_service.generate_scene_prose(
                    scene_outline=scene,
                    chapter_outline=outline,
                    world_state=world_state,
                    previous_scene_ending=previous_scene_ending,
                    book_title=str(compiled.get("book_title") or ""),
                    scene_memory=scene_memory,
                    generation_controls=controls,
                    scene_context_packet=scene_context_packet,
                )
                scenes_prose.append(prose)
                world_state = prose_service.update_world_state_from_scene(world_state, scene, prose)
                scene_memory = prose_service._update_scene_memory(scene_memory, scene, prose)
                previous_scene_ending = prose[-150:].strip() or str(scene.get("ends_on") or "").strip()
                chapter_debug["scenes"].append({
                    "scene_outline": scene,
                    "scene_context_packet": scene_context_packet,
                    "prose_word_count": len(prose.split()),
                })

            chapter_text = "\n\n".join(scenes_prose).strip()
            (output_dir / f"chapter_{chapter_number:02d}.txt").write_text(chapter_text, encoding="utf-8")
            world_state = outline_service.update_world_state(world_state, outline)
            previous_summaries.append(outline_service.chapter_summary_from_outline(outline))
            rolling_previous_ending = scenes_prose[-1][-150:].strip() if scenes_prose else str(outline.get("chapter_closes_on") or "").strip()
            progress["completed_chapters"].append(chapter_debug)
            (output_dir / "progress.json").write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")

        decoder_context = self.build_decoder_context(
            series_id=series_id,
            retrieval_context=retrieval_context,
            generation_controls=generation_controls,
        )
        (output_dir / "decoder_context.json").write_text(
            json.dumps(decoder_context, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output_dir

    def _build_llm(self, spec: Dict[str, Any]) -> LLMClient:
        return LLMClient(
            mode=spec["mode"],
            ollama_model_override=spec.get("model_override", ""),
        )

    def _progress(self, stage: str, index: int, total: int, label: str) -> None:
        filled = max(1, int((index / max(total, 1)) * 24))
        bar = "#" * filled + "-" * max(0, 24 - filled)
        self._announce(f"[decoder:{stage}] [{bar}] {index}/{total} {label}")

    def _announce(self, message: str) -> None:
        print(message, flush=True)
