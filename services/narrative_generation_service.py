"""Production-shaped narrative generation service adapted from the Narraverse prototype."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from infrastructure.llm_client import LLMClient
from query.hybrid_narrative_retriever import HybridNarrativeRetriever
from query.neo4j_narrative_context_service import Neo4jNarrativeContextService
from query.narrative_context_service import NarrativeContextService


BLUEPRINT_SYSTEM = """
You are a master story architect. You will be given a compiled story bible
from an existing book and a user's creative direction. Your job is to design
the blueprint for a full canon-aware novel.

RULES:
- Do NOT impose a rigid 3-act structure. Infer the right structure from the
  source material's own narrative shape and the characters' open arcs.
- Respect all critical canon events - these are ground truth.
- The sequel must honor the requested canon placement mode.
- If canon_placement is `mid_canon_insert`, preserve downstream canon continuity.
- If canon_placement is `mid_canon_divergent`, treat canon before the divergence
  anchor as fixed and canon after it as reference material only, not binding law.
- Weight the user's creative direction when deciding which unresolved threads
  to activate as the central conflict.
- Output ONLY valid JSON.

OUTPUT SCHEMA:
{
  "title": "proposed sequel title",
  "premise": "2-3 sentence summary of what this book is about",
  "structure_type": "e.g. linear, episodic, dual-timeline, etc.",
  "canon_placement": "pre_canon | mid_canon_insert | mid_canon_divergent | post_canon",
  "continuity_anchor": "how the story fits around existing canon constraints",
  "divergence_anchor": "required for mid_canon_divergent, empty otherwise",
  "canon_elements_preserved": [
    "canon events or facts the branch must keep intact"
  ],
  "new_plot_thread": "the newly introduced major plotline, or empty string if none",
  "relationship_targets": [
    {
      "characters": ["name a", "name b"],
      "relationship_type": "friendship | romance | rivalry | alliance | family | mentorship | enemy | other",
      "desired_direction": "what should happen to this relationship",
      "payoff": "the intended emotional or plot payoff"
    }
  ],
  "total_chapters": 25,
  "central_conflict": "the main conflict driving the story",
  "primary_arcs": [
    {
      "arc_name": "e.g. Nesta's Redemption",
      "character": "character name",
      "starts_at": "where this arc begins emotionally/situationally",
      "ends_at": "where it resolves",
      "key_turning_point": "the single event that changes everything for this arc"
    }
  ],
  "acts": [
    {
      "label": "e.g. Part One",
      "chapter_range": "1-7",
      "narrative_goal": "what this section must accomplish",
      "ends_with": "the event or revelation that closes this section",
      "dominant_arcs": ["arc names active here"]
    }
  ],
  "world_threads_activated": ["list of unresolved threads being used"],
  "tone": "the emotional register of this book"
}
"""

OUTLINE_SYSTEM = """
You are a narrative planner. Given a book blueprint, the current world state,
and previous chapter summaries, produce a detailed outline for the next chapter.

RULES:
- Stay consistent with the current world state.
- Advance at least one primary arc meaningfully.
- Honor the generation controls exactly, especially the requested POV and canon placement.
- Each chapter must end on a beat that pulls the reader forward.
- Output ONLY valid JSON.

OUTPUT SCHEMA:
{
  "chapter_number": 1,
  "chapter_title": "string",
  "pov_character": "whose perspective",
  "location": "where this takes place",
  "scenes": [
    {
      "scene_number": 1,
      "summary": "what happens in 2-3 sentences",
      "characters_present": ["names"],
      "purpose": "what narrative work this scene does",
      "ends_on": "the beat or image this scene closes on"
    }
  ],
  "arc_progress": {
    "arc_name": "what changes in this arc this chapter"
  },
  "world_state_changes": [
    "concise description of any state/relationship change that occurs"
  ],
  "chapter_closes_on": "the final beat of the chapter"
}
"""

PROSE_SYSTEM = """
You are a fiction writer continuing a novel. You will be given a scene outline,
the characters involved, the current world state, and the previous scene's
closing lines. Write the full prose for this scene.

RULES:
- Match the tone and style of the source book.
- Stay true to each character's voice and established personality.
- Stay in a single limited POV centered on the requested POV character.
- Unless the prompt explicitly requests first-person narration, default to close third-person.
- Do NOT introduce new major characters or contradict canon facts.
- Do NOT reassign court allegiances, family roles, political offices, or institutional setting facts unless the outline or canon facts explicitly support the change.
- Do NOT summarise - write scene prose in full.
- End the scene on the beat described in the outline.
- Length: 600-1200 words per scene.
- Output ONLY the prose, no titles, no commentary.
"""


class NarrativeGenerationService:
    """Four-stage canon-aware narrative generator backed by the shared LLM client."""

    DEFAULT_NARRATIVE_MODEL_MODE = LLMClient.MODE_GPT_OSS
    DEFAULT_NARRATIVE_OLLAMA_MODEL = "gemma4:31b-cloud"

    REQUIRED_BLUEPRINT_KEYS = {
        "title",
        "premise",
        "structure_type",
        "canon_placement",
        "continuity_anchor",
        "divergence_anchor",
        "canon_elements_preserved",
        "new_plot_thread",
        "relationship_targets",
        "total_chapters",
        "central_conflict",
        "primary_arcs",
        "acts",
        "world_threads_activated",
        "tone",
    }
    REQUIRED_PRIMARY_ARC_KEYS = {
        "arc_name",
        "character",
        "starts_at",
        "ends_at",
        "key_turning_point",
    }
    REQUIRED_ACT_KEYS = {
        "label",
        "chapter_range",
        "narrative_goal",
        "ends_with",
        "dominant_arcs",
    }
    REQUIRED_OUTLINE_KEYS = {
        "chapter_number",
        "chapter_title",
        "pov_character",
        "location",
        "scenes",
        "arc_progress",
        "world_state_changes",
        "chapter_closes_on",
    }
    REQUIRED_SCENE_KEYS = {
        "scene_number",
        "summary",
        "characters_present",
        "purpose",
        "ends_on",
    }
    REQUIRED_RELATIONSHIP_TARGET_KEYS = {
        "characters",
        "relationship_type",
        "desired_direction",
        "payoff",
    }
    ALLOWED_CANON_PLACEMENTS = {
        "pre_canon",
        "mid_canon_insert",
        "mid_canon_divergent",
        "post_canon",
    }
    CANON_PLACEMENT_ALIASES = {
        "mid_canon": "mid_canon_insert",
    }
    ALLOWED_RELATIONSHIP_TYPES = {
        "friendship",
        "romance",
        "rivalry",
        "alliance",
        "family",
        "mentorship",
        "enemy",
        "other",
    }

    def __init__(
        self,
        *,
        llm_client: Optional[LLMClient] = None,
        hybrid_retriever: Optional[HybridNarrativeRetriever] = None,
        target_chapters: int = 25,
        scene_pause_seconds: float = 0.0,
        chapter_pause_seconds: float = 0.0,
    ) -> None:
        self.llm = llm_client or LLMClient(
            mode=self.DEFAULT_NARRATIVE_MODEL_MODE,
            ollama_model_override=self.DEFAULT_NARRATIVE_OLLAMA_MODEL,
        )
        self.target_chapters = max(1, int(target_chapters))
        self.scene_pause_seconds = max(0.0, float(scene_pause_seconds))
        self.chapter_pause_seconds = max(0.0, float(chapter_pause_seconds))
        self.context_service = NarrativeContextService()
        self.neo4j_context_service = Neo4jNarrativeContextService()
        self.hybrid_retriever = hybrid_retriever or HybridNarrativeRetriever()
        self._last_validation_error = ""

    def load_exported_context(self, contract: Dict[str, Any]) -> Dict[str, Any] | None:
        return self.context_service.load_exported_context(contract)

    def load_exported_blueprint(self, contract: Dict[str, Any]) -> Dict[str, Any] | None:
        outputs = (contract.get("outputs") or {})
        artifacts = outputs.get("sequel_artifacts")
        if not artifacts:
            return None
        if not isinstance(artifacts, dict):
            raise ValueError(
                "Contract outputs.sequel_artifacts is malformed. Expected an object containing "
                "`context` and `blueprint`."
            )
        if "blueprint" not in artifacts or not artifacts.get("blueprint"):
            return None
        blueprint = artifacts.get("blueprint")
        if not isinstance(blueprint, dict):
            raise ValueError("Contract outputs.sequel_artifacts.blueprint is malformed. Expected a JSON object.")
        validation_error = self._blueprint_validation_error(blueprint)
        if validation_error:
            raise ValueError(
                "Contract outputs.sequel_artifacts.blueprint is malformed. Validation error: "
                + validation_error
            )
        return blueprint

    def build_retrieval_context(
        self,
        contract: Dict[str, Any],
        *,
        prefer_exported_context: bool = True,
    ) -> Dict[str, Any]:
        return self.context_service.build_from_contract(
            contract,
            prefer_exported=prefer_exported_context,
        )

    def build_retrieval_context_from_neo4j(
        self,
        *,
        book_title: str | None = None,
        series_id: str | None = None,
        book_titles: List[str] | None = None,
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
        database: str | None = None,
    ) -> Dict[str, Any]:
        use_existing = all(value is None for value in (uri, username, password, database))
        service = self.neo4j_context_service if use_existing else Neo4jNarrativeContextService(
            uri=uri,
            username=username,
            password=password,
            database=database,
        )
        try:
            return service.build_from_graph(
                book_title=book_title,
                series_id=series_id,
                book_titles=book_titles,
            )
        finally:
            if not use_existing:
                service.close()

    def build_or_load_blueprint(
        self,
        contract: Dict[str, Any],
        *,
        user_prompt: str,
        generation_controls: Optional[Dict[str, Any]] = None,
        prefer_exported_context: bool = True,
        prefer_exported_blueprint: bool = True,
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        retrieval_context = self.build_retrieval_context(
            contract,
            prefer_exported_context=prefer_exported_context,
        )
        normalized_controls = self.normalize_generation_controls(
            user_prompt=user_prompt,
            generation_controls=generation_controls,
        )
        if prefer_exported_blueprint:
            try:
                exported_blueprint = self.load_exported_blueprint(contract)
            except ValueError:
                exported_blueprint = None
            if exported_blueprint and self._blueprint_matches_controls(exported_blueprint, normalized_controls):
                return retrieval_context, exported_blueprint
        compiled = self.compile_context(
            retrieval_context,
            user_prompt,
            generation_controls=normalized_controls,
        )
        blueprint = self.generate_blueprint(compiled)
        return retrieval_context, blueprint

    def compile_context(
        self,
        retrieval_json: Dict[str, Any],
        user_prompt: str,
        generation_controls: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        meta = retrieval_json.get("meta", {}) or {}
        ending = retrieval_json.get("story_ending", {}) or {}
        character_states = retrieval_json.get("character_states", []) or []
        relationships = retrieval_json.get("relationship_summary", []) or []
        unresolved_threads = retrieval_json.get("unresolved_threads", []) or []
        causal_chains = retrieval_json.get("causal_chains", []) or []
        flexible_events = retrieval_json.get("flexible_events", []) or []
        trajectories = retrieval_json.get("character_trajectories", []) or []
        controls = self.normalize_generation_controls(
            user_prompt=user_prompt,
            generation_controls=generation_controls,
        )

        characters = []
        for item in character_states[:10]:
            transitions = item.get("state_transitions", []) or []
            characters.append({
                "name": item.get("name", ""),
                "descriptions": self._sanitize_character_descriptions(item.get("descriptions", []) or []),
                "canon_state": item.get("canon_state", {}) or {},
                "recent_changes": transitions[-3:],
                "aliases": item.get("aliases", []) or [],
            })

        relationship_rows = [
            {
                "between": f"{item.get('entity_a', '')} <-> {item.get('entity_b', '')}".strip(),
                "type": item.get("relationship_type"),
                "latest": item.get("latest_change"),
                "evidence": item.get("evidence"),
            }
            for item in relationships[:15]
        ]

        thread_rows = [
            {
                "event": item.get("event_description"),
                "decision": item.get("decision_made"),
                "alternatives": item.get("alternatives"),
                "potential": item.get("divergence_potential"),
            }
            for item in sorted(
                unresolved_threads,
                key=lambda row: row.get("divergence_potential", 0),
                reverse=True,
            )[:8]
        ]

        chain_rows = [
            {
                "id": item.get("chain_id"),
                "description": item.get("description"),
                "type": item.get("chain_type"),
                "function": item.get("story_function"),
                "event_count": len(item.get("events", []) or []),
            }
            for item in causal_chains
        ]

        last_scene = ending.get("last_scene", {}) or {}
        critical_tail = ending.get("critical_path_tail", []) or []
        story_ending = {
            "last_scene_summary": last_scene.get("summary", ""),
            "entities_present": [
                entity.get("name", "")
                for entity in last_scene.get("entities_present", []) or []
                if entity.get("name")
            ],
            "location": ((last_scene.get("location") or {}).get("name")),
            "critical_events": [item.get("description") for item in critical_tail[-5:] if item.get("description")],
        }

        flexible_rows = [
            {
                "description": item.get("description"),
                "score": item.get("flexibility_score"),
            }
            for item in flexible_events[:5]
        ]

        return {
            "book_title": meta.get("book_title", "Unknown"),
            "user_prompt": user_prompt,
            "generation_controls": controls,
            "story_ending": story_ending,
            "characters": characters,
            "relationships": relationship_rows,
            "unresolved_threads": thread_rows,
            "causal_chains": chain_rows,
            "flexible_events": flexible_rows,
            "character_trajectories": [
                {
                    "character": item.get("character", ""),
                    "last_events": [event.get("summary", "") for event in item.get("last_events", []) or []],
                }
                for item in trajectories
            ],
            "style_requirements": controls.get("style_requirements", []),
            "consistency_requirements": controls.get("consistency_requirements", []),
        }

    def generate_blueprint(self, compiled_context: Dict[str, Any]) -> Dict[str, Any]:
        controls = compiled_context.get("generation_controls") or {}
        prompt = (
            f"{BLUEPRINT_SYSTEM}\n\n"
            f"STORY BIBLE:\n{json.dumps(compiled_context, ensure_ascii=False, indent=2)}\n\n"
            f'USER DIRECTION: "{compiled_context.get("user_prompt", "")}"\n\n'
            f"GENERATION CONTROLS:\n{json.dumps(compiled_context.get('generation_controls', {}), ensure_ascii=False, indent=2)}\n\n"
            "Design the narrative blueprint now. Output only valid JSON."
        )
        return self._generate_guarded_json(
            prompt,
            validator=self._blueprint_validator(controls),
            stage_name="blueprint",
            local_repair=lambda raw_output: self._repair_blueprint_to_controls(raw_output, controls),
        )

    def generate_chapter_outline(
        self,
        *,
        blueprint: Dict[str, Any],
        compiled_context: Dict[str, Any],
        world_state: Dict[str, Any],
        previous_summaries: List[str],
        chapter_number: int,
        current_story_position: Optional[Dict[str, Any]] = None,
        chapter_context_packet: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        current_act = self._current_act(blueprint, chapter_number)
        recent_summaries = previous_summaries[-3:] if previous_summaries else []
        current_story_position = current_story_position or self._current_story_position(
            compiled_context=compiled_context,
            previous_summaries=previous_summaries,
            rolling_previous_ending=compiled_context.get("story_ending", {}).get("last_scene_summary", ""),
        )
        chapter_controls = self._chapter_controls_for_generation(
            blueprint=blueprint,
            controls=compiled_context.get("generation_controls") or {},
            chapter_number=chapter_number,
        )
        chapter_context_packet = chapter_context_packet or {
            "source_ending_baseline": compiled_context.get("story_ending", {}) or {},
            "current_story_position": current_story_position,
            "recent_summaries": recent_summaries,
            "query_summary": {"chapter_number": chapter_number, "pov_character": chapter_controls.get("primary_pov_character", "")},
        }
        outline_calibration = self._outline_calibration_packet(compiled_context, chapter_controls)
        prompt = (
            f"{OUTLINE_SYSTEM}\n\n"
            f"BLUEPRINT:\n{json.dumps(blueprint, ensure_ascii=False, indent=2)}\n\n"
            f"FOCUSED CHAPTER CONTEXT PACKET:\n{json.dumps(chapter_context_packet, ensure_ascii=False, indent=2)}\n\n"
            f"CURRENT WORLD STATE SUMMARY:\n{json.dumps({'active_threads': world_state.get('active_threads', []), 'recent_events': (world_state.get('events_so_far', []) or [])[-8:]}, ensure_ascii=False, indent=2)}\n\n"
            f"CURRENT ACT CONTEXT:\n{json.dumps(current_act, ensure_ascii=False, indent=2)}\n\n"
            f"GENERATION CONTROLS:\n{json.dumps(compiled_context.get('generation_controls', {}), ensure_ascii=False, indent=2)}\n\n"
            f"CHAPTER-SPECIFIC DIRECTIVES:\n{json.dumps(chapter_controls, ensure_ascii=False, indent=2)}\n\n"
            f"OUTLINE CALIBRATION PACKET:\n{json.dumps(outline_calibration, ensure_ascii=False, indent=2)}\n\n"
            f"Now generate the outline for CHAPTER {chapter_number}. Output only valid JSON."
        )
        return self._generate_guarded_json(
            prompt,
            validator=self._chapter_outline_validator(
                chapter_number,
                controls=compiled_context.get("generation_controls") or {},
            ),
            stage_name=f"chapter_outline_{chapter_number}",
        )

    def generate_scene_prose(
        self,
        *,
        scene_outline: Dict[str, Any],
        chapter_outline: Dict[str, Any],
        world_state: Dict[str, Any],
        previous_scene_ending: str,
        book_title: str,
        scene_memory: Optional[Dict[str, Any]] = None,
        generation_controls: Optional[Dict[str, Any]] = None,
        scene_context_packet: Optional[Dict[str, Any]] = None,
    ) -> str:
        present_names = scene_outline.get("characters_present", []) or []
        relevant_characters = [
            item for item in world_state.get("characters", []) or []
            if item.get("name") in present_names
        ]
        relevant_relationships = [
            item for item in world_state.get("relationships", []) or []
            if any(name and name in (item.get("between") or "") for name in present_names)
        ]
        scene_memory = scene_memory or self._empty_scene_memory()
        controls = generation_controls or {}
        narrative_voice = self._preferred_narrative_voice(book_title, controls)
        chapter_controls = self._chapter_controls_for_generation(
            blueprint={"total_chapters": controls.get("chapter_count") or self.target_chapters, "relationship_targets": []},
            controls=controls,
            chapter_number=int(chapter_outline.get("chapter_number") or 1),
        )
        scene_context_packet = scene_context_packet or {
            "pov_character_packet": next((item for item in relevant_characters if item.get("name") == chapter_outline.get("pov_character")), {}),
            "scene_participants": relevant_characters,
            "participant_relationships": relevant_relationships,
            "chapter_local_memory": {
                "previous_scene_ending": previous_scene_ending,
                "scene_memory": scene_memory,
            },
            "canon_guardrails": controls.get("canon_elements_to_preserve", []),
            "required_plot_beats": chapter_controls.get("assigned_plot_beats", []),
            "relationship_focus": chapter_controls.get("relationship_focus", []),
        }
        prose_calibration = self._prose_calibration_packet(
            controls=controls,
            chapter_controls=chapter_controls,
            scene_outline=scene_outline,
            scene_context_packet=scene_context_packet,
        )
        user_prompt = (
            f"SOURCE BOOK: {book_title}\n"
            f"CHAPTER: {chapter_outline.get('chapter_number')} - {chapter_outline.get('chapter_title')}\n"
            f"POV CHARACTER: {chapter_outline.get('pov_character')}\n"
            f"NARRATIVE VOICE: {narrative_voice}\n"
            f"LOCATION: {scene_outline.get('location', chapter_outline.get('location', 'unknown'))}\n\n"
            f"SCENE OUTLINE:\n{json.dumps(scene_outline, ensure_ascii=False, indent=2)}\n\n"
            f"FOCUSED SCENE CONTEXT PACKET:\n{json.dumps(scene_context_packet, ensure_ascii=False, indent=2)}\n\n"
            f"CHAPTER-SPECIFIC DIRECTIVES:\n{json.dumps(chapter_controls, ensure_ascii=False, indent=2)}\n\n"
            f"PROSE CALIBRATION PACKET:\n{json.dumps(prose_calibration, ensure_ascii=False, indent=2)}\n\n"
            f"CHAPTER MEMORY SO FAR:\n{json.dumps(scene_memory, ensure_ascii=False, indent=2)}\n\n"
            f"PREVIOUS SCENE ENDED WITH:\n\"\"\"{previous_scene_ending}\"\"\"\n\n"
            "Write the full prose for this scene now."
        )
        return self._generate_guarded_prose(
            user_prompt,
            validator=self._scene_prose_validator(
                chapter_outline=chapter_outline,
                scene_outline=scene_outline,
                controls=controls,
                narrative_voice=narrative_voice,
                scene_context_packet=scene_context_packet,
            ),
            stage_name=f"scene_prose_{chapter_outline.get('chapter_number')}_{scene_outline.get('scene_number')}",
        )

    def generate_sequel_from_contract(
        self,
        contract: Dict[str, Any],
        *,
        user_prompt: str,
        output_dir: str | Path = "output/sequel",
        generation_controls: Optional[Dict[str, Any]] = None,
        prefer_exported_context: bool = True,
        prefer_exported_blueprint: bool = True,
    ) -> Path:
        retrieval_context = self.build_retrieval_context(
            contract,
            prefer_exported_context=prefer_exported_context,
        )
        blueprint = None
        if prefer_exported_blueprint:
            try:
                candidate = self.load_exported_blueprint(contract)
            except ValueError:
                candidate = None
            controls = self.normalize_generation_controls(
                user_prompt=user_prompt,
                generation_controls=generation_controls,
            )
            if candidate and self._blueprint_matches_controls(candidate, controls):
                blueprint = candidate
        return self.generate_sequel(
            retrieval_context,
            user_prompt=user_prompt,
            output_dir=output_dir,
            blueprint=blueprint,
            generation_controls=generation_controls,
        )

    def generate_sequel_from_neo4j(
        self,
        *,
        book_title: str | None = None,
        series_id: str | None = None,
        book_titles: List[str] | None = None,
        user_prompt: str,
        output_dir: str | Path = "output/sequel",
        generation_controls: Optional[Dict[str, Any]] = None,
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
        database: str | None = None,
    ) -> Path:
        retrieval_context = self.build_retrieval_context_from_neo4j(
            book_title=book_title,
            series_id=series_id,
            book_titles=book_titles,
            uri=uri,
            username=username,
            password=password,
            database=database,
        )
        return self.generate_sequel(
            retrieval_context,
            user_prompt=user_prompt,
            output_dir=output_dir,
            generation_controls=generation_controls,
        )

    def generate_sequel(
        self,
        retrieval_context: Dict[str, Any] | str | Path,
        *,
        user_prompt: str,
        output_dir: str | Path = "output/sequel",
        blueprint: Optional[Dict[str, Any]] = None,
        generation_controls: Optional[Dict[str, Any]] = None,
    ) -> Path:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        retrieval_json = self._load_retrieval_context(retrieval_context)
        controls = self.normalize_generation_controls(
            user_prompt=user_prompt,
            generation_controls=generation_controls,
        )
        compiled = self.compile_context(
            retrieval_json,
            user_prompt,
            generation_controls=controls,
        )
        blueprint = blueprint or self.generate_blueprint(compiled)
        if not self._blueprint_matches_controls(blueprint, controls):
            raise ValueError("Provided blueprint does not satisfy the requested generation controls.")
        blueprint["total_chapters"] = int(controls["chapter_count"])

        with (out_path / "blueprint.json").open("w", encoding="utf-8") as handle:
            json.dump(blueprint, handle, ensure_ascii=False, indent=2)

        world_state = self.initialise_world_state(compiled)
        previous_summaries: List[str] = []
        total_chapters = int(blueprint.get("total_chapters") or self.target_chapters)
        rolling_previous_ending = compiled.get("story_ending", {}).get("last_scene_summary", "")
        retrieval_debug: List[Dict[str, Any]] = []

        for chapter_number in range(1, total_chapters + 1):
            current_story_position = self._current_story_position(
                compiled_context=compiled,
                previous_summaries=previous_summaries,
                rolling_previous_ending=rolling_previous_ending,
            )
            chapter_controls = self._chapter_controls_for_generation(
                blueprint=blueprint,
                controls=controls,
                chapter_number=chapter_number,
            )
            chapter_context_packet = self.hybrid_retriever.build_outline_context_packet(
                retrieval_context=retrieval_json,
                compiled_context=compiled,
                blueprint=blueprint,
                world_state=world_state,
                current_story_position=current_story_position,
                chapter_number=chapter_number,
                previous_summaries=previous_summaries,
                chapter_controls=chapter_controls,
            )
            outline = self.generate_chapter_outline(
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
            last_ending = rolling_previous_ending
            scene_memory = self._empty_scene_memory()
            chapter_debug = {
                "chapter_number": chapter_number,
                "outline_packet": self._retrieval_debug_snapshot(chapter_context_packet),
                "scene_packets": [],
            }
            for scene in scenes:
                scene_context_packet = self.hybrid_retriever.build_scene_context_packet(
                    retrieval_context=retrieval_json,
                    compiled_context=compiled,
                    scene_outline=scene,
                    chapter_outline=outline,
                    world_state=world_state,
                    scene_memory=scene_memory,
                    previous_scene_ending=last_ending,
                    chapter_controls=chapter_controls,
                )
                prose = self.generate_scene_prose(
                    scene_outline=scene,
                    chapter_outline=outline,
                    world_state=world_state,
                    previous_scene_ending=last_ending,
                    book_title=compiled.get("book_title", "Unknown"),
                    scene_memory=scene_memory,
                    generation_controls=controls,
                    scene_context_packet=scene_context_packet,
                )
                scenes_prose.append(prose)
                last_ending = prose[-150:].strip()
                scene_memory = self._update_scene_memory(scene_memory, scene, prose)
                world_state = self.update_world_state_from_scene(world_state, scene, prose)
                chapter_debug["scene_packets"].append(self._retrieval_debug_snapshot(scene_context_packet))
                if self.scene_pause_seconds:
                    time.sleep(self.scene_pause_seconds)
            self._save_chapter(
                out_path,
                chapter_number=chapter_number,
                chapter_title=outline.get("chapter_title", f"Chapter {chapter_number}"),
                scenes_prose=scenes_prose,
            )
            if scenes_prose:
                rolling_previous_ending = scenes_prose[-1][-150:].strip() or outline.get("chapter_closes_on", "") or last_ending
            else:
                rolling_previous_ending = outline.get("chapter_closes_on", "") or last_ending
            world_state = self.update_world_state(world_state, outline)
            previous_summaries.append(self.chapter_summary_from_outline(outline))
            retrieval_debug.append(chapter_debug)
            self._save_progress(
                out_path,
                {
                    "blueprint": blueprint,
                    "compiled_context": compiled,
                    "generation_controls": controls,
                    "world_state": world_state,
                    "previous_summaries": previous_summaries,
                    "rolling_previous_ending": rolling_previous_ending,
                    "retrieval_debug": retrieval_debug,
                    "last_completed_chapter": chapter_number,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            if self.chapter_pause_seconds:
                time.sleep(self.chapter_pause_seconds)

        return out_path

    def initialise_world_state(self, compiled_context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "characters": list(compiled_context.get("characters", []) or []),
            "relationships": list(compiled_context.get("relationships", []) or []),
            "active_threads": list(compiled_context.get("unresolved_threads", []) or []),
            "source_story_ending": dict(compiled_context.get("story_ending", {}) or {}),
            "events_so_far": [],
        }

    def update_world_state(self, world_state: Dict[str, Any], chapter_outline: Dict[str, Any]) -> Dict[str, Any]:
        changes = chapter_outline.get("world_state_changes", []) or []
        if changes:
            world_state["events_so_far"].extend(changes)
        if len(world_state["events_so_far"]) > 50:
            world_state["events_so_far"] = world_state["events_so_far"][-50:]
        return world_state

    def update_world_state_from_scene(self, world_state: Dict[str, Any], scene_outline: Dict[str, Any], prose: str) -> Dict[str, Any]:
        summary = (scene_outline.get("summary") or "").strip()
        ending = (scene_outline.get("ends_on") or "").strip()
        label = f"Scene {scene_outline.get('scene_number')}: {summary}".strip()
        if ending:
            label = f"{label} [Ends on: {ending}]"
        if label:
            world_state["events_so_far"].append(label)
        if len(world_state["events_so_far"]) > 50:
            world_state["events_so_far"] = world_state["events_so_far"][-50:]
        return world_state

    def chapter_summary_from_outline(self, outline: Dict[str, Any]) -> str:
        scenes = outline.get("scenes", []) or []
        scene_text = " ".join(scene.get("summary", "") for scene in scenes)
        return (
            f"Chapter {outline.get('chapter_number')} - {outline.get('chapter_title')}: "
            f"{scene_text} [Closes on: {outline.get('chapter_closes_on', '')}]"
        )

    def _current_story_position(
        self,
        *,
        compiled_context: Dict[str, Any],
        previous_summaries: List[str],
        rolling_previous_ending: str,
    ) -> Dict[str, Any]:
        story_ending = dict(compiled_context.get("story_ending", {}) or {})
        return {
            "source_book_ending": story_ending,
            "latest_generated_ending": str(rolling_previous_ending or "").strip(),
            "latest_chapter_summary": str(previous_summaries[-1] if previous_summaries else "").strip(),
            "chapters_completed": len(previous_summaries),
        }

    def _retrieval_debug_snapshot(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        if not packet:
            return {}
        return {
            "query_summary": packet.get("query_summary", {}),
            "retrieved_document_ids": [item.get("document_id", "") for item in (packet.get("retrieved_memories") or [])],
            "retrieved_sources": [item.get("source_type", "") for item in (packet.get("retrieved_memories") or [])],
            "top_character_packets": [
                item.get("name", "")
                for item in [
                    packet.get("pov_character_packet", {}),
                    *(packet.get("scene_participants") or []),
                ]
                if item.get("name")
            ][:6],
            "canon_facts_passed": packet.get("canon_guardrails") or packet.get("canon_facts_for_this_chapter") or [],
        }

    def _empty_scene_memory(self) -> Dict[str, Any]:
        return {
            "scene_count_completed": 0,
            "chapter_so_far_summary": "",
            "prior_scene_summaries": [],
            "recent_scene_endings": [],
            "recent_prose_tail": [],
            "characters_seen_so_far": [],
        }

    def _update_scene_memory(self, scene_memory: Dict[str, Any], scene_outline: Dict[str, Any], prose: str) -> Dict[str, Any]:
        updated = {
            "scene_count_completed": int(scene_memory.get("scene_count_completed") or 0),
            "chapter_so_far_summary": str(scene_memory.get("chapter_so_far_summary") or ""),
            "prior_scene_summaries": list(scene_memory.get("prior_scene_summaries") or []),
            "recent_scene_endings": list(scene_memory.get("recent_scene_endings") or []),
            "recent_prose_tail": list(scene_memory.get("recent_prose_tail") or []),
            "characters_seen_so_far": list(scene_memory.get("characters_seen_so_far") or []),
        }
        summary = (scene_outline.get("summary") or "").strip()
        ending = (scene_outline.get("ends_on") or "").strip()
        updated["scene_count_completed"] += 1
        if summary:
            updated["prior_scene_summaries"].append({
                "scene_number": scene_outline.get("scene_number"),
                "summary": summary,
            })
        updated["prior_scene_summaries"] = updated["prior_scene_summaries"][-4:]
        if ending:
            updated["recent_scene_endings"].append({
                "scene_number": scene_outline.get("scene_number"),
                "ending": ending,
            })
        updated["recent_scene_endings"] = updated["recent_scene_endings"][-3:]
        prose_tail = (prose or "").strip()[-450:]
        if prose_tail:
            updated["recent_prose_tail"].append({
                "scene_number": scene_outline.get("scene_number"),
                "tail": prose_tail,
            })
        updated["recent_prose_tail"] = updated["recent_prose_tail"][-2:]
        seen = {str(name).strip() for name in updated["characters_seen_so_far"] if str(name).strip()}
        for name in scene_outline.get("characters_present", []) or []:
            cleaned = str(name).strip()
            if cleaned and cleaned not in seen:
                updated["characters_seen_so_far"].append(cleaned)
                seen.add(cleaned)
        updated["characters_seen_so_far"] = updated["characters_seen_so_far"][-12:]
        summary_lines = [item.get("summary", "") for item in updated["prior_scene_summaries"] if item.get("summary")]
        updated["chapter_so_far_summary"] = " ".join(summary_lines).strip()
        return updated

    def check_consistency(self, prose: str, chapter_outline: Dict[str, Any], world_state: Dict[str, Any]) -> List[str]:
        warnings = []
        pov = chapter_outline.get("pov_character", "")
        if pov and pov.lower() not in (prose or "").lower():
            warnings.append(f"POV character '{pov}' not found in prose")
        return warnings

    def _load_retrieval_context(self, retrieval_context: Dict[str, Any] | str | Path) -> Dict[str, Any]:
        if isinstance(retrieval_context, dict):
            return retrieval_context
        with Path(retrieval_context).open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _current_act(self, blueprint: Dict[str, Any], chapter_number: int) -> Dict[str, Any]:
        for act in blueprint.get("acts", []) or []:
            chapter_range = str(act.get("chapter_range", "")).replace(" ", "")
            parts = chapter_range.split("-")
            if len(parts) != 2:
                continue
            try:
                if int(parts[0]) <= chapter_number <= int(parts[1]):
                    return act
            except ValueError:
                continue
        return {}

    def _save_chapter(
        self,
        output_dir: Path,
        *,
        chapter_number: int,
        chapter_title: str,
        scenes_prose: List[str],
    ) -> Path:
        target = output_dir / f"chapter_{chapter_number:02d}.txt"
        with target.open("w", encoding="utf-8") as handle:
            handle.write(f"CHAPTER {chapter_number}\n{chapter_title}\n\n")
            handle.write("\n\n---\n\n".join(scenes_prose))
        return target

    def _save_progress(self, output_dir: Path, payload: Dict[str, Any]) -> None:
        with (output_dir / "progress.json").open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)

    def parse_json_response(self, raw: str) -> Dict[str, Any] | List[Any]:
        cleaned = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
        return json.loads(cleaned)

    def normalize_generation_controls(
        self,
        *,
        user_prompt: str,
        generation_controls: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        raw = generation_controls or {}
        if not isinstance(raw, dict):
            raise ValueError("generation_controls must be a JSON object when provided.")

        canon_position = str(raw.get("canon_position") or "post_canon").strip().lower().replace("-", "_")
        canon_position = self.CANON_PLACEMENT_ALIASES.get(canon_position, canon_position)
        if canon_position not in self.ALLOWED_CANON_PLACEMENTS:
            raise ValueError(
                "canon_position must be one of: " + ", ".join(sorted(self.ALLOWED_CANON_PLACEMENTS))
            )

        chapter_count = int(raw.get("chapter_count") or self.target_chapters)
        if chapter_count < 1:
            raise ValueError("chapter_count must be a positive integer.")

        new_plot = str(raw.get("new_plot") or "").strip()
        continuity_anchor = str(raw.get("continuity_anchor") or "").strip()
        divergence_anchor = str(raw.get("divergence_anchor") or "").strip()
        anchor_after = str(raw.get("anchor_after") or "").strip()
        anchor_before = str(raw.get("anchor_before") or "").strip()
        primary_pov_character = str(raw.get("primary_pov_character") or "").strip() or self._infer_primary_pov_character(user_prompt)
        relationship_directions = self._normalize_relationship_directions(
            raw.get("relationship_directions") or self._infer_relationship_directions(user_prompt)
        )
        canon_elements_to_preserve = self._normalize_canon_elements_to_preserve(
            raw.get("canon_elements_to_preserve") or self._infer_canon_elements_to_preserve(user_prompt)
        )
        required_plot_beats = self._normalize_required_plot_beats(
            raw.get("required_plot_beats") or self._infer_required_plot_beats(user_prompt)
        )
        style_requirements = self._normalize_prompt_constraints(
            raw.get("style_requirements") or self._infer_style_requirements(user_prompt)
        )
        consistency_requirements = self._normalize_prompt_constraints(
            raw.get("consistency_requirements") or self._infer_consistency_requirements(user_prompt)
        )

        inferred_anchor = continuity_anchor
        if anchor_after or anchor_before:
            parts = []
            if anchor_after:
                parts.append(f"after {anchor_after}")
            if anchor_before:
                parts.append(f"before {anchor_before}")
            anchor_text = " and ".join(parts)
            inferred_anchor = f"{inferred_anchor}. {anchor_text}".strip(". ").strip()
        if canon_position == "mid_canon_divergent" and not divergence_anchor:
            raise ValueError("divergence_anchor is required for mid_canon_divergent generation.")

        return {
            "chapter_count": chapter_count,
            "canon_position": canon_position,
            "new_plot": new_plot,
            "primary_pov_character": primary_pov_character,
            "relationship_directions": relationship_directions,
            "canon_elements_to_preserve": canon_elements_to_preserve,
            "required_plot_beats": required_plot_beats,
            "style_requirements": style_requirements,
            "consistency_requirements": consistency_requirements,
            "continuity_anchor": inferred_anchor,
            "divergence_anchor": divergence_anchor,
            "anchor_after": anchor_after,
            "anchor_before": anchor_before,
            "user_prompt": str(user_prompt or "").strip(),
        }

    def _generate_guarded_json(
        self,
        prompt: str,
        *,
        validator,
        stage_name: str,
        max_attempts: int = 3,
        local_repair=None,
    ) -> Dict[str, Any]:
        attempt_prompt = prompt
        last_error = "unknown_error"
        for attempt in range(1, max_attempts + 1):
            result = self.llm.generate_json(attempt_prompt, strict=True, validator=validator)
            if isinstance(result, dict) and "error" not in result:
                return result
            validation_error = self._extract_validation_error(result, validator)
            last_error = validation_error
            raw_output = result.get("raw_output") if isinstance(result, dict) else None
            if local_repair and raw_output is not None:
                repaired = local_repair(raw_output)
                if repaired is not None and validator(repaired):
                    return repaired
            if attempt >= max_attempts:
                break
            attempt_prompt = self._build_repair_prompt(
                base_prompt=prompt,
                stage_name=stage_name,
                validation_error=validation_error,
                raw_output=raw_output,
            )
        raise ValueError(f"Decoder {stage_name} generation failed schema validation: {last_error}")

    def _generate_guarded_prose(
        self,
        prompt: str,
        *,
        validator,
        stage_name: str,
        max_attempts: int = 3,
    ) -> str:
        attempt_prompt = prompt
        last_error = "unknown_error"
        for attempt in range(1, max_attempts + 1):
            prose = self.llm.generate_text(
                attempt_prompt,
                system_prompt=PROSE_SYSTEM,
                temperature=0.85,
                max_tokens=3000,
            )
            prose = self._normalize_scene_prose_output(prose)
            if validator(prose):
                return prose
            last_error = self._last_validation_error or "validation_failed"
            if attempt >= max_attempts:
                break
            attempt_prompt = self._build_prose_repair_prompt(
                base_prompt=prompt,
                stage_name=stage_name,
                validation_error=last_error,
                raw_output=prose,
            )
        raise ValueError(f"Decoder {stage_name} generation failed prose validation: {last_error}")

    def _build_repair_prompt(
        self,
        *,
        base_prompt: str,
        stage_name: str,
        validation_error: str,
        raw_output: Any,
    ) -> str:
        raw_text = json.dumps(raw_output, ensure_ascii=False, indent=2) if raw_output is not None else "<no structured output>"
        return (
            f"{base_prompt}\n\n"
            f"SCHEMA REPAIR MODE ({stage_name}):\n"
            f"The previous response was structurally invalid.\n"
            f"Validation error: {validation_error}\n"
            f"Previous invalid output:\n{raw_text}\n\n"
            "Return a corrected response that matches the required schema exactly. "
            "Do not omit required keys. Do not add commentary. Output only valid JSON."
        )

    def _build_prose_repair_prompt(
        self,
        *,
        base_prompt: str,
        stage_name: str,
        validation_error: str,
        raw_output: str,
    ) -> str:
        return (
            f"{base_prompt}\n\n"
            f"PROSE REPAIR MODE ({stage_name}):\n"
            f"The previous prose draft violated the narrative constraints.\n"
            f"Validation error: {validation_error}\n"
            f"Previous invalid prose:\n\"\"\"\n{raw_output}\n\"\"\"\n\n"
            "Rewrite the same scene so it obeys the requested POV, canon facts, and outline constraints exactly. "
            "Output only the corrected scene prose."
        )

    def _extract_validation_error(self, result: Dict[str, Any], validator) -> str:
        if not isinstance(result, dict):
            return "response_not_object"
        if result.get("error") == "validation_failed":
            raw_output = result.get("raw_output")
            validator(raw_output)
            return self._last_validation_error or "validation_failed"
        error = result.get("last_error") or result.get("error") or "unknown_error"
        return str(error)

    def _validate_blueprint_response(self, response: Dict[str, Any]) -> bool:
        error = self._blueprint_validation_error(response)
        self._last_validation_error = error
        return error == ""

    def _validate_blueprint_response_with_controls(
        self,
        response: Dict[str, Any],
        *,
        controls: Optional[Dict[str, Any]] = None,
    ) -> bool:
        error = self._blueprint_validation_error(response, controls=controls)
        self._last_validation_error = error
        return error == ""

    def _blueprint_validator(self, controls: Optional[Dict[str, Any]] = None):
        def _validator(response: Dict[str, Any]) -> bool:
            return self._validate_blueprint_response_with_controls(response, controls=controls)

        return _validator

    def _validate_scene_prose_response(
        self,
        prose: str,
        *,
        chapter_outline: Dict[str, Any],
        scene_outline: Dict[str, Any],
        controls: Optional[Dict[str, Any]] = None,
        narrative_voice: str = "third_person_limited",
        scene_context_packet: Optional[Dict[str, Any]] = None,
    ) -> bool:
        error = self._scene_prose_validation_error(
            prose,
            chapter_outline=chapter_outline,
            scene_outline=scene_outline,
            controls=controls,
            narrative_voice=narrative_voice,
            scene_context_packet=scene_context_packet,
        )
        self._last_validation_error = error
        return error == ""

    def _scene_prose_validator(
        self,
        *,
        chapter_outline: Dict[str, Any],
        scene_outline: Dict[str, Any],
        controls: Optional[Dict[str, Any]] = None,
        narrative_voice: str = "third_person_limited",
        scene_context_packet: Optional[Dict[str, Any]] = None,
    ):
        def _validator(prose: str) -> bool:
            return self._validate_scene_prose_response(
                prose,
                chapter_outline=chapter_outline,
                scene_outline=scene_outline,
                controls=controls,
                narrative_voice=narrative_voice,
                scene_context_packet=scene_context_packet,
            )

        return _validator

    def _validate_chapter_outline_response(
        self,
        response: Dict[str, Any],
        *,
        chapter_number: int,
        controls: Optional[Dict[str, Any]] = None,
    ) -> bool:
        error = self._chapter_outline_validation_error(response, chapter_number=chapter_number, controls=controls)
        self._last_validation_error = error
        return error == ""

    def _chapter_outline_validator(self, chapter_number: int, controls: Optional[Dict[str, Any]] = None):
        def _validator(response: Dict[str, Any]) -> bool:
            return self._validate_chapter_outline_response(response, chapter_number=chapter_number, controls=controls)

        return _validator

    def _normalize_relationship_directions(self, rows: Any) -> List[Dict[str, Any]]:
        if not isinstance(rows, list):
            raise ValueError("relationship_directions must be a list.")
        normalized = []
        for index, item in enumerate(rows):
            if not isinstance(item, dict):
                raise ValueError(f"relationship_directions[{index}] must be an object.")
            characters = item.get("characters") or []
            if not isinstance(characters, list) or len([name for name in characters if str(name).strip()]) < 2:
                raise ValueError(f"relationship_directions[{index}].characters must contain at least two names.")
            cleaned_characters = [str(name).strip() for name in characters if str(name).strip()]
            relationship_type = str(item.get("relationship_type") or item.get("type") or "other").strip().lower()
            if relationship_type not in self.ALLOWED_RELATIONSHIP_TYPES:
                raise ValueError(
                    f"relationship_directions[{index}].relationship_type must be one of: "
                    + ", ".join(sorted(self.ALLOWED_RELATIONSHIP_TYPES))
                )
            desired_direction = str(item.get("desired_direction") or "").strip()
            if not desired_direction:
                raise ValueError(f"relationship_directions[{index}].desired_direction is required.")
            notes = str(item.get("notes") or "").strip()
            normalized.append({
                "characters": cleaned_characters,
                "relationship_type": relationship_type,
                "desired_direction": desired_direction,
                "notes": notes,
            })
        return normalized

    def _sanitize_character_descriptions(self, rows: List[Any]) -> List[str]:
        cleaned_rows: List[str] = []
        for item in rows:
            text = re.sub(r"[^A-Za-z0-9 ,.'’-]+", "", str(item or "")).strip()
            if not text:
                continue
            lowered = text.lower()
            if any(
                token in lowered
                for token in (
                    "ring",
                    "robe",
                    "jacket",
                    "pants",
                    "belt",
                    "knife",
                    "shirt",
                    "coat",
                    "gown",
                    "silk",
                )
            ):
                continue
            cleaned_rows.append(text)
        deduped: List[str] = []
        seen = set()
        for text in cleaned_rows:
            key = text.lower()
            if key in seen:
                continue
            deduped.append(text)
            seen.add(key)
        return deduped[:2]

    def _chapter_controls_for_generation(
        self,
        *,
        blueprint: Dict[str, Any],
        controls: Dict[str, Any],
        chapter_number: int,
    ) -> Dict[str, Any]:
        total_chapters = int(blueprint.get("total_chapters") or controls.get("chapter_count") or self.target_chapters)
        required_beats = list(controls.get("required_plot_beats") or [])
        assigned_beats: List[str] = []
        if required_beats and total_chapters > 0:
            beat_count = len(required_beats)
            previous_cut = 0 if chapter_number <= 1 else (((chapter_number - 1) * beat_count) + total_chapters - 1) // total_chapters
            current_cut = max(1, ((chapter_number * beat_count) + total_chapters - 1) // total_chapters)
            assigned_beats = required_beats[previous_cut:current_cut]
        relationship_targets = list((controls.get("relationship_directions") or []))
        relationship_focus: List[Dict[str, Any]] = []
        for item in relationship_targets:
            chars = list(item.get("characters") or [])
            if len(chars) < 2:
                continue
            lowered = " ".join(assigned_beats).lower()
            if lowered and any(char.lower() in lowered for char in chars):
                relationship_focus.append(item)
                continue
            if chapter_number <= max(3, total_chapters // 3) and item.get("relationship_type") == "romance":
                relationship_focus.append(item)
            elif chapter_number >= max(1, total_chapters - 2):
                relationship_focus.append(item)
        return {
            "assigned_plot_beats": assigned_beats[:2],
            "relationship_focus": relationship_focus[:3],
            "canon_focus": list(controls.get("canon_elements_to_preserve") or [])[:4],
            "style_focus": list(controls.get("style_requirements") or [])[:4],
            "consistency_focus": list(controls.get("consistency_requirements") or [])[:4],
        }

    def _outline_calibration_packet(self, compiled_context: Dict[str, Any], chapter_controls: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "style_requirements": list(compiled_context.get("style_requirements") or [])[:5],
            "consistency_requirements": list(compiled_context.get("consistency_requirements") or [])[:5],
            "chapter_focus": {
                "assigned_plot_beats": chapter_controls.get("assigned_plot_beats") or [],
                "relationship_focus": chapter_controls.get("relationship_focus") or [],
            },
            "planner_bias": [
                "Prefer emotionally precise scene turns over generic epic escalation.",
                "Keep court politics and institutional roles specific to the canon setting.",
                "Do not over-pack every chapter with cosmic reveals unless the assigned beat requires it.",
            ],
        }

    def _prose_calibration_packet(
        self,
        *,
        controls: Dict[str, Any],
        chapter_controls: Dict[str, Any],
        scene_outline: Dict[str, Any],
        scene_context_packet: Dict[str, Any],
    ) -> Dict[str, Any]:
        present_names = list(scene_outline.get("characters_present") or [])
        return {
            "style_requirements": list(controls.get("style_requirements") or [])[:6],
            "consistency_requirements": list(controls.get("consistency_requirements") or [])[:6],
            "relationship_focus": chapter_controls.get("relationship_focus") or [],
            "required_plot_beats": chapter_controls.get("assigned_plot_beats") or [],
            "present_characters": present_names,
            "pov_character": (scene_context_packet.get("pov_character_packet") or {}).get("name", ""),
            "avoid": [
                "Do not overuse ornamental clothing or jewelry description unless the scene beat makes it important.",
                "Do not drift into generic cosmic exposition when the scene is intimate or political.",
                "Prefer ACOTAR-style emotional subtext, close observation, and court-specific tension over abstract grandeur.",
                "Keep non-dialogue narration in close third-person unless explicitly instructed otherwise.",
            ],
        }

    def _normalize_canon_elements_to_preserve(self, rows: Any) -> List[Dict[str, Any]]:
        if not isinstance(rows, list):
            raise ValueError("canon_elements_to_preserve must be a list.")
        normalized = []
        for index, item in enumerate(rows):
            if isinstance(item, str):
                description = item.strip()
                if description:
                    normalized.append({"event_id": "", "description": description})
                continue
            if not isinstance(item, dict):
                raise ValueError(f"canon_elements_to_preserve[{index}] must be a string or object.")
            description = str(item.get("description") or "").strip()
            event_id = str(item.get("event_id") or "").strip()
            if not description and not event_id:
                raise ValueError(f"canon_elements_to_preserve[{index}] must include a description or event_id.")
            normalized.append({
                "event_id": event_id,
                "description": description,
            })
        return normalized

    def _normalize_required_plot_beats(self, rows: Any) -> List[str]:
        if not isinstance(rows, list):
            raise ValueError("required_plot_beats must be a list.")
        normalized: List[str] = []
        seen = set()
        for item in rows:
            cleaned = str(item or "").strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            normalized.append(cleaned)
            seen.add(key)
        return normalized

    def _normalize_prompt_constraints(self, rows: Any) -> List[str]:
        if not isinstance(rows, list):
            raise ValueError("prompt constraint collections must be lists.")
        cleaned_rows: List[str] = []
        seen = set()
        for item in rows:
            cleaned = str(item or "").strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            cleaned_rows.append(cleaned)
            seen.add(key)
        return cleaned_rows

    def _infer_primary_pov_character(self, user_prompt: str) -> str:
        if not user_prompt:
            return ""
        for line in user_prompt.splitlines():
            cleaned = line.strip(" -*\t")
            match = re.match(r"(?i)(.+?)\s+as the primary pov character$", cleaned)
            if match:
                return match.group(1).strip()
        return ""

    def _infer_canon_elements_to_preserve(self, user_prompt: str) -> List[Dict[str, Any]]:
        lines = self._extract_prompt_section_lines(user_prompt, "Required canon continuity")
        return [{"event_id": "", "description": line} for line in lines]

    def _infer_required_plot_beats(self, user_prompt: str) -> List[str]:
        return self._extract_prompt_section_lines(user_prompt, "Expected plot progression")

    def _infer_style_requirements(self, user_prompt: str) -> List[str]:
        return self._extract_prompt_section_lines(user_prompt, "Tone and style requirements")

    def _infer_consistency_requirements(self, user_prompt: str) -> List[str]:
        return self._extract_prompt_section_lines(user_prompt, "Important consistency requirements")

    def _infer_relationship_directions(self, user_prompt: str) -> List[Dict[str, Any]]:
        inferred: List[Dict[str, Any]] = []
        for line in self._extract_prompt_section_lines(user_prompt, "Core relationship expectations"):
            cleaned = line.strip()
            match = re.match(
                r"^([A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+){0,2})\s+and\s+([A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+){0,2})\s+(.+)$",
                cleaned,
            )
            if match:
                left = match.group(1).strip()
                right = match.group(2).strip()
                remainder = match.group(3).strip()
                relationship_type = "romance" if any(token in remainder.lower() for token in ["romantic", "romance", "love"]) else "alliance"
                inferred.append({
                    "characters": [left, right],
                    "relationship_type": relationship_type,
                    "desired_direction": remainder,
                    "notes": cleaned,
                })
                continue
            lower = cleaned.lower()
            if "lucien" in lower and "bond" in lower and "elain" not in lower:
                inferred.append({
                    "characters": ["Elain Archeron", "Lucien"],
                    "relationship_type": "romance",
                    "desired_direction": cleaned,
                    "notes": cleaned,
                })
        return inferred

    def _extract_prompt_section_lines(self, user_prompt: str, header: str) -> List[str]:
        if not user_prompt:
            return []
        lines = user_prompt.splitlines()
        collected: List[str] = []
        in_section = False
        target = header.strip().lower()
        for raw_line in lines:
            stripped = raw_line.strip()
            header_candidate = stripped.rstrip(":").lower()
            if header_candidate == target:
                in_section = True
                continue
            if in_section and stripped.endswith(":") and not re.match(r"^\d+\.", stripped):
                break
            if not in_section:
                continue
            bullet = stripped.lstrip("*- ").strip()
            bullet = re.sub(r"^\d+\.\s*", "", bullet).strip()
            if bullet:
                collected.append(bullet)
        return collected

    def _blueprint_matches_controls(self, blueprint: Dict[str, Any], controls: Dict[str, Any]) -> bool:
        return self._blueprint_validation_error(blueprint, controls=controls) == ""

    def _parse_act_ranges(self, acts: List[Dict[str, Any]]) -> List[tuple[int, int]]:
        ranges: List[tuple[int, int]] = []
        for act in acts:
            chapter_range = str((act or {}).get("chapter_range", "")).replace(" ", "")
            parts = chapter_range.split("-")
            if len(parts) != 2:
                return []
            try:
                ranges.append((int(parts[0]), int(parts[1])))
            except ValueError:
                return []
        return ranges

    def _normalize_match_text(self, value: Any) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()

    def _texts_loosely_match(self, left: Any, right: Any) -> bool:
        a = self._normalize_match_text(left)
        b = self._normalize_match_text(right)
        if not a or not b:
            return False
        if a == b or a in b or b in a:
            return True
        a_tokens = {token for token in a.split() if len(token) > 2}
        b_tokens = {token for token in b.split() if len(token) > 2}
        if not a_tokens or not b_tokens:
            return False
        overlap = len(a_tokens & b_tokens)
        threshold = max(2, min(len(a_tokens), len(b_tokens)) // 2)
        return overlap >= threshold

    def _relationship_character_sets_match(self, requested_names: List[str], target_names: List[str]) -> bool:
        normalized_targets = [
            self._normalize_match_text(name).replace(" ", "")
            for name in target_names
            if self._normalize_match_text(name)
        ]
        if not normalized_targets:
            return False
        for requested in requested_names:
            normalized_requested = self._normalize_match_text(requested).replace(" ", "")
            if not normalized_requested:
                continue
            if not any(
                normalized_requested == target
                or normalized_requested in target
                or target in normalized_requested
                for target in normalized_targets
            ):
                return False
        return True

    def _blueprint_validation_error(self, response: Any, controls: Optional[Dict[str, Any]] = None) -> str:
        if not isinstance(response, dict):
            return "blueprint_not_object"
        missing = sorted(self.REQUIRED_BLUEPRINT_KEYS - set(response.keys()))
        if missing:
            return "missing_blueprint_keys:" + ",".join(missing)
        if not isinstance(response.get("title"), str) or not response.get("title", "").strip():
            return "invalid_title"
        if not isinstance(response.get("premise"), str) or not response.get("premise", "").strip():
            return "invalid_premise"
        if not isinstance(response.get("structure_type"), str) or not response.get("structure_type", "").strip():
            return "invalid_structure_type"
        if response.get("canon_placement") not in self.ALLOWED_CANON_PLACEMENTS:
            return "invalid_canon_placement"
        if not isinstance(response.get("continuity_anchor"), str):
            return "invalid_continuity_anchor"
        if not isinstance(response.get("divergence_anchor"), str):
            return "invalid_divergence_anchor"
        if not isinstance(response.get("canon_elements_preserved"), list):
            return "invalid_canon_elements_preserved"
        if not isinstance(response.get("new_plot_thread"), str):
            return "invalid_new_plot_thread"
        if not isinstance(response.get("central_conflict"), str) or not response.get("central_conflict", "").strip():
            return "invalid_central_conflict"
        if not isinstance(response.get("tone"), str) or not response.get("tone", "").strip():
            return "invalid_tone"
        if not isinstance(response.get("total_chapters"), int) or response.get("total_chapters", 0) < 1:
            return "invalid_total_chapters"
        if not isinstance(response.get("primary_arcs"), list):
            return "primary_arcs_not_list"
        if not isinstance(response.get("acts"), list):
            return "acts_not_list"
        if not isinstance(response.get("world_threads_activated"), list):
            return "world_threads_not_list"
        if not isinstance(response.get("relationship_targets"), list):
            return "relationship_targets_not_list"
        for index, arc in enumerate(response.get("primary_arcs") or []):
            if not isinstance(arc, dict):
                return f"primary_arc_{index}_not_object"
            missing_arc = sorted(self.REQUIRED_PRIMARY_ARC_KEYS - set(arc.keys()))
            if missing_arc:
                return f"primary_arc_{index}_missing:" + ",".join(missing_arc)
            for key in self.REQUIRED_PRIMARY_ARC_KEYS:
                if not isinstance(arc.get(key), str) or not arc.get(key, "").strip():
                    return f"primary_arc_{index}_invalid_{key}"
        for index, act in enumerate(response.get("acts") or []):
            if not isinstance(act, dict):
                return f"act_{index}_not_object"
            missing_act = sorted(self.REQUIRED_ACT_KEYS - set(act.keys()))
            if missing_act:
                return f"act_{index}_missing:" + ",".join(missing_act)
            for key in ("label", "chapter_range", "narrative_goal", "ends_with"):
                if not isinstance(act.get(key), str) or not act.get(key, "").strip():
                    return f"act_{index}_invalid_{key}"
            if not isinstance(act.get("dominant_arcs"), list):
                return f"act_{index}_dominant_arcs_not_list"
        chapter_ranges = self._parse_act_ranges(response.get("acts") or [])
        if not chapter_ranges:
            return "invalid_act_ranges"
        expected_start = 1
        for index, (start, end) in enumerate(chapter_ranges):
            if end < start:
                return f"act_{index}_range_reversed"
            if start != expected_start:
                return f"act_{index}_range_gap_or_overlap"
            expected_start = end + 1
        if chapter_ranges[-1][1] != int(response.get("total_chapters") or 0):
            return "act_ranges_do_not_match_total_chapters"
        for index, relationship_target in enumerate(response.get("relationship_targets") or []):
            if not isinstance(relationship_target, dict):
                return f"relationship_target_{index}_not_object"
            missing_target = sorted(self.REQUIRED_RELATIONSHIP_TARGET_KEYS - set(relationship_target.keys()))
            if missing_target:
                return f"relationship_target_{index}_missing:" + ",".join(missing_target)
            characters = relationship_target.get("characters")
            if not isinstance(characters, list) or len([name for name in characters if str(name).strip()]) < 2:
                return f"relationship_target_{index}_invalid_characters"
            if relationship_target.get("relationship_type") not in self.ALLOWED_RELATIONSHIP_TYPES:
                return f"relationship_target_{index}_invalid_relationship_type"
            for key in ("desired_direction", "payoff"):
                if not isinstance(relationship_target.get(key), str) or not relationship_target.get(key, "").strip():
                    return f"relationship_target_{index}_invalid_{key}"
        active_controls = controls or {}
        if active_controls:
            if response.get("total_chapters") != active_controls.get("chapter_count"):
                return "chapter_count_control_mismatch"
            if response.get("canon_placement") != active_controls.get("canon_position"):
                return "canon_position_control_mismatch"
            if active_controls.get("canon_position") == "mid_canon_divergent":
                if not response.get("divergence_anchor", "").strip():
                    return "divergence_anchor_missing"
            if active_controls.get("new_plot") and not response.get("new_plot_thread", "").strip():
                return "new_plot_control_missing"
            primary_pov = str(active_controls.get("primary_pov_character") or "").strip()
            if primary_pov:
                blueprint_text = json.dumps(response, ensure_ascii=False).lower()
                if primary_pov.lower() not in blueprint_text:
                    return "primary_pov_control_missing"
            requested_relationships = active_controls.get("relationship_directions") or []
            if requested_relationships:
                blueprint_targets = response.get("relationship_targets") or []
                for requested in requested_relationships:
                    requested_names = [str(name).strip() for name in requested.get("characters", []) if str(name).strip()]
                    matched = False
                    for target in blueprint_targets:
                        target_names = [str(name).strip() for name in (target.get("characters") or []) if str(name).strip()]
                        if (
                            self._relationship_character_sets_match(requested_names, target_names)
                            and str(target.get("relationship_type") or "").strip().lower() == requested.get("relationship_type")
                        ):
                            matched = True
                            break
                    if not matched:
                        return "relationship_control_missing"
            requested_preserved = active_controls.get("canon_elements_to_preserve") or []
            if requested_preserved:
                blueprint_preserved = response.get("canon_elements_preserved") or []
                for requested in requested_preserved:
                    requested_key = str(requested.get("description") or requested.get("event_id") or "").strip()
                    if requested_key and not any(
                        self._texts_loosely_match(
                            requested_key,
                            item if isinstance(item, str) else ((item or {}).get("description") or (item or {}).get("event_id") or ""),
                        )
                        for item in blueprint_preserved
                    ):
                        return "canon_elements_preserved_control_missing"
        return ""

    def _chapter_outline_validation_error(
        self,
        response: Any,
        *,
        chapter_number: int,
        controls: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not isinstance(response, dict):
            return "outline_not_object"
        missing = sorted(self.REQUIRED_OUTLINE_KEYS - set(response.keys()))
        if missing:
            return "missing_outline_keys:" + ",".join(missing)
        if response.get("chapter_number") != chapter_number:
            return f"chapter_number_mismatch:{response.get('chapter_number')}!={chapter_number}"
        for key in ("chapter_title", "pov_character", "location", "chapter_closes_on"):
            if not isinstance(response.get(key), str) or not response.get(key, "").strip():
                return f"invalid_{key}"
        if not isinstance(response.get("scenes"), list) or not response.get("scenes"):
            return "scenes_not_nonempty_list"
        if not isinstance(response.get("arc_progress"), dict):
            return "arc_progress_not_object"
        if not isinstance(response.get("world_state_changes"), list):
            return "world_state_changes_not_list"
        for index, scene in enumerate(response.get("scenes") or []):
            if not isinstance(scene, dict):
                return f"scene_{index}_not_object"
            missing_scene = sorted(self.REQUIRED_SCENE_KEYS - set(scene.keys()))
            if missing_scene:
                return f"scene_{index}_missing:" + ",".join(missing_scene)
            if scene.get("scene_number") != index + 1:
                return f"scene_{index}_number_mismatch"
            for key in ("summary", "purpose", "ends_on"):
                if not isinstance(scene.get(key), str) or not scene.get(key, "").strip():
                    return f"scene_{index}_invalid_{key}"
            if not isinstance(scene.get("characters_present"), list):
                return f"scene_{index}_characters_present_not_list"
        active_controls = controls or {}
        primary_pov = str(active_controls.get("primary_pov_character") or "").strip()
        if primary_pov and str(response.get("pov_character") or "").strip().lower() != primary_pov.lower():
            return "primary_pov_outline_mismatch"
        chapter_controls = self._chapter_controls_for_generation(
            blueprint={"total_chapters": active_controls.get("chapter_count") or self.target_chapters},
            controls=active_controls,
            chapter_number=chapter_number,
        )
        outline_text = json.dumps(response, ensure_ascii=False)
        assigned_beats = chapter_controls.get("assigned_plot_beats") or []
        if assigned_beats and not any(self._texts_loosely_match(outline_text, beat) for beat in assigned_beats):
            return "chapter_required_plot_beat_missing"
        relationship_focus = chapter_controls.get("relationship_focus") or []
        return ""

    def _repair_blueprint_to_controls(
        self,
        response: Any,
        controls: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(response, dict):
            return None
        active_controls = controls or {}
        repaired = json.loads(json.dumps(response))
        chapter_count = int(active_controls.get("chapter_count") or repaired.get("total_chapters") or self.target_chapters)
        repaired["total_chapters"] = chapter_count
        if active_controls.get("canon_position"):
            repaired["canon_placement"] = active_controls["canon_position"]
        if active_controls.get("new_plot") and not str(repaired.get("new_plot_thread") or "").strip():
            repaired["new_plot_thread"] = str(active_controls.get("new_plot") or "").strip()
        if active_controls.get("divergence_anchor"):
            repaired["divergence_anchor"] = str(active_controls.get("divergence_anchor") or "").strip()
        requested_preserved = active_controls.get("canon_elements_to_preserve") or []
        if requested_preserved:
            existing_preserved = list(repaired.get("canon_elements_preserved") or [])
            for item in requested_preserved:
                requested_text = str(item.get("description") or item.get("event_id") or "").strip()
                if not requested_text:
                    continue
                if not any(
                    self._texts_loosely_match(
                        requested_text,
                        existing if isinstance(existing, str) else ((existing or {}).get("description") or (existing or {}).get("event_id") or ""),
                    )
                    for existing in existing_preserved
                ):
                    existing_preserved.append(requested_text)
            repaired["canon_elements_preserved"] = existing_preserved
        requested_relationships = active_controls.get("relationship_directions") or []
        if requested_relationships:
            existing_targets = list(repaired.get("relationship_targets") or [])
            for item in requested_relationships:
                requested_names = [
                    str(name).strip()
                    for name in (item.get("characters") or [])
                    if str(name).strip()
                ]
                requested_type = str(item.get("relationship_type") or "other").strip().lower()
                matched = False
                for target in existing_targets:
                    target_names = [
                        str(name).strip()
                        for name in (target.get("characters") or [])
                        if str(name).strip()
                    ]
                    if self._relationship_character_sets_match(requested_names, target_names) and str(target.get("relationship_type") or "").strip().lower() == requested_type:
                        matched = True
                        if not str(target.get("desired_direction") or "").strip():
                            target["desired_direction"] = str(item.get("desired_direction") or "").strip()
                        if not str(target.get("payoff") or "").strip():
                            target["payoff"] = str(item.get("notes") or item.get("desired_direction") or "").strip()
                        break
                if not matched:
                    existing_targets.append({
                        "characters": list(item.get("characters") or []),
                        "relationship_type": requested_type,
                        "desired_direction": str(item.get("desired_direction") or "").strip(),
                        "payoff": str(item.get("notes") or item.get("desired_direction") or "").strip(),
                    })
            repaired["relationship_targets"] = existing_targets
        primary_pov = str(active_controls.get("primary_pov_character") or "").strip()
        if primary_pov:
            continuity_anchor = str(repaired.get("continuity_anchor") or "").strip()
            if primary_pov.lower() not in continuity_anchor.lower():
                repaired["continuity_anchor"] = (
                    continuity_anchor + f" Primary POV: {primary_pov}."
                ).strip()
        acts = repaired.get("acts") or []
        if isinstance(acts, list) and acts:
            ranges = self._balanced_chapter_ranges(chapter_count, len(acts))
            for act, (start, end) in zip(acts, ranges):
                if isinstance(act, dict):
                    act["chapter_range"] = f"{start}-{end}"
            repaired["acts"] = acts
        return repaired

    def _balanced_chapter_ranges(self, total_chapters: int, segment_count: int) -> List[tuple[int, int]]:
        if total_chapters < 1 or segment_count < 1:
            return []
        base = total_chapters // segment_count
        remainder = total_chapters % segment_count
        ranges: List[tuple[int, int]] = []
        start = 1
        for index in range(segment_count):
            width = base + (1 if index < remainder else 0)
            if width < 1:
                width = 1
            end = min(total_chapters, start + width - 1)
            ranges.append((start, end))
            start = end + 1
        if ranges:
            ranges[-1] = (ranges[-1][0], total_chapters)
        return ranges

    def _scene_prose_validation_error(
        self,
        prose: Any,
        *,
        chapter_outline: Dict[str, Any],
        scene_outline: Dict[str, Any],
        controls: Optional[Dict[str, Any]] = None,
        narrative_voice: str = "third_person_limited",
        scene_context_packet: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not isinstance(prose, str):
            return "scene_prose_not_string"
        cleaned = prose.strip()
        if not cleaned:
            return "scene_prose_empty"
        if len(cleaned) < 400:
            return "scene_prose_too_short"
        pov = str(chapter_outline.get("pov_character") or controls.get("primary_pov_character") or "").strip()
        if cleaned.startswith("**") or cleaned.startswith("CHAPTER "):
            return "scene_prose_has_heading"
        if pov and not self._prose_mentions_character(cleaned, pov):
            return "scene_prose_pov_missing"
        scene_summary = str(scene_outline.get("summary") or "").strip()
        if narrative_voice == "third_person_limited":
            non_dialogue = self._strip_dialogue_for_voice_checks(cleaned)
            first_person_hits = re.findall(r"\b(i|me|my|mine|myself|we|our|ours|us)\b", non_dialogue, flags=re.IGNORECASE)
            if len(first_person_hits) > 6:
                return "scene_prose_first_person_drift"
        if self._has_overwrought_detail_repetition(cleaned):
            return "scene_prose_repetitive_ornamental_detail"
        if scene_context_packet and not self._prose_tracks_scene_outline(cleaned, scene_outline):
            return "scene_prose_scene_focus_drift"
        return ""

    def _has_overwrought_detail_repetition(self, prose: str) -> bool:
        lowered = str(prose or "").lower()
        noisy_phrases = [
            "moon-white silk robe",
            "moon white silk robe",
            "iron band on her finger",
            "iron ring on her finger",
            "pale skin",
        ]
        hits = sum(lowered.count(phrase) for phrase in noisy_phrases)
        return hits >= 3

    def _prose_tracks_scene_outline(self, prose: str, scene_outline: Dict[str, Any]) -> bool:
        prose_tokens = self._content_tokens(prose)
        summary_tokens = self._content_tokens(" ".join([
            str(scene_outline.get("summary") or ""),
            str(scene_outline.get("purpose") or ""),
            str(scene_outline.get("ends_on") or ""),
        ]))
        if not summary_tokens:
            return True
        present_names = [str(name or "").strip() for name in (scene_outline.get("characters_present") or []) if str(name or "").strip()]
        if present_names and all(self._prose_mentions_character(prose, name) for name in present_names[:2]):
            overlap = len(prose_tokens & summary_tokens)
            return overlap >= 1
        overlap = len(prose_tokens & summary_tokens)
        return overlap >= 1

    def _content_tokens(self, text: str) -> set[str]:
        stop = {
            "the", "and", "with", "that", "this", "from", "into", "their", "there", "then",
            "they", "them", "her", "his", "was", "were", "for", "but", "she", "him", "its",
            "had", "have", "has", "not", "are", "out", "you", "your", "hers", "over", "under",
        }
        return {
            token for token in re.findall(r"[a-z0-9']+", str(text).lower())
            if len(token) > 2 and token not in stop
        }

    def _preferred_narrative_voice(self, book_title: str, controls: Optional[Dict[str, Any]] = None) -> str:
        requested = str((controls or {}).get("narrative_voice") or "").strip().lower()
        if requested:
            return requested
        return "third_person_limited"

    def _normalize_scene_prose_output(self, prose: str) -> str:
        text = str(prose or "").replace("\r\n", "\n").strip()
        lines = text.split("\n")
        while lines and not lines[0].strip():
            lines.pop(0)
        stripped_lines: List[str] = []
        heading_budget = 3
        for line in lines:
            candidate = line.strip()
            if heading_budget > 0 and (
                candidate.startswith("**")
                or candidate.upper().startswith("CHAPTER ")
                or candidate.lower().startswith("chapter ")
            ):
                heading_budget -= 1
                continue
            stripped_lines.append(line)
        return "\n".join(stripped_lines).strip()

    def _strip_dialogue_for_voice_checks(self, prose: str) -> str:
        text = str(prose or "")
        text = re.sub(r'"[^"]*"', " ", text)
        text = re.sub(r"“[^”]*”", " ", text)
        text = re.sub(r"'[^']*'", " ", text)
        return text

    def _prose_mentions_character(self, prose: str, character_name: str) -> bool:
        lowered = str(prose or "").lower()
        full_name = str(character_name or "").strip().lower()
        if not full_name:
            return True
        if full_name in lowered:
            return True
        tokens = [token for token in re.split(r"\s+", full_name) if len(token) > 2]
        return any(token in lowered for token in tokens)
