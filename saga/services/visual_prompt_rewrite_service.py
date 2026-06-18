from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from saga.agents.visual_prompt_schema import (
    PERSISTENT_PROFILE_KEYS,
    compile_character_turnaround_prompt,
    normalize_dynamic_visual_changes,
    normalize_persistent_profile,
    profile_specificity_score,
)
from saga.providers.llm_client import LLMClient
from saga.services.sqlite_contract_adapter import is_db_book_ref, load_contract_like
from saga.services.wiki_character_reference_service import flatten_reference_entries

ROOT = Path(__file__).resolve().parents[2]

CORE_BASELINE_FIELDS = [
    "facial_structure",
    "hair_description",
    "eye_description",
    "body_type",
    "clothing_description",
    "footwear_description",
    "world_aesthetic_cues",
]

PLACEHOLDER_MARKERS = {
    "none",
    "not specified",
    "unknown",
    "unclear",
    "likely",
    "same as beast form",
    "eyes that soften",
    "faerie skin tone",
}

CREATURE_MARKERS = {
    "creature",
    "monster",
    "beast",
    "skeletal",
    "talon",
    "taloned",
    "fang",
    "forked tongue",
    "leathery",
    "clawed",
    "muzzle",
    "snout",
    "emaciated",
    "wings",
}

HUMANOID_MARKERS = {
    "woman",
    "man",
    "male",
    "female",
    "courtier",
    "lord",
    "lady",
    "sister",
    "servant",
    "attendant",
    "hunter",
    "warrior",
    "queen",
    "nobility",
}


class VisualPromptRewriteService:
    def __init__(self, llm_client: LLMClient | None = None):
        self.llm = llm_client or LLMClient(mode=LLMClient.MODE_CODEX)

    def load_contract(self, contract_path: str | Path) -> dict[str, Any]:
        if is_db_book_ref(str(contract_path)):
            return load_contract_like(str(contract_path))
        return json.loads(Path(contract_path).read_text(encoding="utf-8-sig"))

    def load_reference_notes(self, reference_json: str | Path | None) -> dict[str, Any]:
        if not reference_json:
            return {}
        path = Path(reference_json)
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(payload, dict) and isinstance(payload.get("entries"), list):
            return flatten_reference_entries(payload)
        if isinstance(payload, dict):
            return {str(key).strip().lower(): value for key, value in payload.items()}
        return {}

    def collect_initial_rows(self, contract_path: str | Path) -> list[dict[str, Any]]:
        payload = self.load_contract(contract_path)
        outputs = payload.get("outputs") or {}
        rows = ((outputs.get("visual_prompt_sets") or {}).get("initial_characters") or [])
        collected: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("entity_name") or "").strip()
            if not name:
                continue
            details = row.get("details") or {}
            profile = normalize_persistent_profile(details.get("persistent_visual_profile") or {})
            collected.append(
                {
                    "entity_name": name,
                    "book_index": row.get("book_index"),
                    "chapter_index": row.get("chapter_index"),
                    "scene_index": row.get("scene_index"),
                    "source_evidence": row.get("source_evidence") or "",
                    "positive_prompt": row.get("positive_prompt") or "",
                    "profile": profile,
                    "dynamic_visual_changes": normalize_dynamic_visual_changes(
                        details.get("dynamic_visual_changes") or [],
                        display_name=name,
                    ),
                }
            )
        return collected

    def audit_contract(
        self,
        contract_path: str | Path,
        *,
        reference_json: str | Path | None = None,
        names: list[str] | None = None,
    ) -> dict[str, Any]:
        target_names = {name.strip().lower() for name in (names or []) if str(name).strip()}
        reference_notes = self.load_reference_notes(reference_json)
        rows = self.collect_initial_rows(contract_path)
        entries: list[dict[str, Any]] = []
        for row in rows:
            name = row["entity_name"]
            if target_names and name.lower() not in target_names:
                continue
            profile = row["profile"]
            missing = [field for field in CORE_BASELINE_FIELDS if not str(profile.get(field) or "").strip()]
            contaminated = [
                field
                for field, value in profile.items()
                if field != "lore_terms" and _looks_placeholder(value)
            ]
            classification = self._classify_entity(row)
            issues = []
            if missing:
                issues.append(f"Missing core baseline slots: {', '.join(missing)}")
            if contaminated:
                issues.append(f"Placeholder or weak values in: {', '.join(contaminated)}")
            if classification == "creature":
                issues.append("Should stay out of human character-sheet render queue.")
            reference = reference_notes.get(name.lower()) or {}
            entries.append(
                {
                    "entity_name": name,
                    "entity_type": classification,
                    "profile_specificity_score": profile_specificity_score(profile),
                    "missing_core_slots": missing,
                    "contaminated_fields": contaminated,
                    "has_dynamic_changes": bool(row["dynamic_visual_changes"]),
                    "current_prompt": row["positive_prompt"],
                    "source_evidence": row["source_evidence"],
                    "persistent_visual_profile": profile,
                    "reference_notes": reference,
                    "issues": issues,
                }
            )
        return {
            "contract_path": str(contract_path),
            "reference_json": str(reference_json or ""),
            "entries": entries,
        }

    def rewrite_contract_prompts(
        self,
        contract_path: str | Path,
        *,
        reference_json: str | Path | None = None,
        names: list[str] | None = None,
    ) -> dict[str, Any]:
        audit = self.audit_contract(contract_path, reference_json=reference_json, names=names)
        rewritten: list[dict[str, Any]] = []
        for entry in audit["entries"]:
            rewritten.append(self._rewrite_entry(entry))
        return {
            "contract_path": str(contract_path),
            "reference_json": str(reference_json or ""),
            "provider": self.llm.provider_name(),
            "model": self.llm.resolved_model_name(),
            "rewritten_prompts": rewritten,
        }

    def _rewrite_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        prompt = self._build_rewrite_prompt(entry)
        response = self.llm.generate_json(prompt, strict=True, validator=self._validate_rewrite_response)
        if isinstance(response, dict) and "error" not in response:
            profile = normalize_persistent_profile(response.get("persistent_visual_profile") or {})
            rewritten_prompt = str(response.get("rewritten_prompt") or "").strip()
            if not rewritten_prompt:
                rewritten_prompt = compile_character_turnaround_prompt(profile, display_name=entry["entity_name"])
            return {
                "entity_name": entry["entity_name"],
                "entity_type": str(response.get("entity_type") or entry["entity_type"] or "character"),
                "issues": response.get("issues") or [],
                "confidence": str(response.get("confidence") or "medium"),
                "persistent_visual_profile": profile,
                "rewritten_prompt": rewritten_prompt,
                "source_evidence": entry.get("source_evidence") or "",
                "reference_notes": entry.get("reference_notes") or {},
            }
        return {
            "entity_name": entry["entity_name"],
            "entity_type": entry["entity_type"],
            "issues": (entry.get("issues") or []) + [f"rewrite_failed: {response.get('error') if isinstance(response, dict) else 'unknown'}"],
            "confidence": "low",
            "persistent_visual_profile": entry["persistent_visual_profile"],
            "rewritten_prompt": compile_character_turnaround_prompt(
                entry["persistent_visual_profile"],
                display_name=entry["entity_name"],
            ),
            "source_evidence": entry.get("source_evidence") or "",
            "reference_notes": entry.get("reference_notes") or {},
        }

    def _classify_entity(self, row: dict[str, Any]) -> str:
        profile = row.get("profile") or {}
        profile_text = json.dumps(profile, ensure_ascii=False).lower()
        haystack = " ".join(
            str(part or "")
            for part in [
                row.get("entity_name"),
                row.get("source_evidence"),
                profile_text,
            ]
        ).lower()
        if any(marker in str(profile.get("species_or_race") or "").lower() for marker in {"creature", "monster", "beast"}):
            return "creature"
        if any(marker in str(profile.get("role_or_archetype") or "").lower() for marker in {"creature", "monster", "beast"}):
            return "creature"
        if any(marker in str(profile.get("model_safe_identity") or "").lower() for marker in {"creature", "monster", "beast"}):
            return "creature"
        has_creature = any(marker in haystack for marker in CREATURE_MARKERS)
        has_humanoid = any(marker in haystack for marker in HUMANOID_MARKERS)
        if has_creature and not has_humanoid:
            return "creature"
        return "character"

    def _build_rewrite_prompt(self, entry: dict[str, Any]) -> str:
        profile = entry.get("persistent_visual_profile") or {}
        reference = entry.get("reference_notes") or {}
        return f"""
You are a visual prompt rewrite agent for canon-consistent character sheets.
Return strict JSON only.

Task:
- Clean and normalize the persistent character baseline.
- Keep only durable visual identity traits.
- Remove placeholders like "none", "not specified", "unknown", "likely", and weak filler.
- Do not invent details unsupported by the extracted evidence or reference notes.
- If the entity is clearly a non-human creature, classify it as `creature`.
- Rewrite the final prompt for a natural-sentence image model prompt, suitable for z-image-turbo.
- Keep dynamic scene-state out of the baseline prompt.
- Explicitly preserve world/material/aesthetic cues when supported.
- If a core slot is missing, leave it blank instead of guessing.

Required JSON schema:
{{
  "entity_name": "{entry['entity_name']}",
  "entity_type": "character|creature",
  "persistent_visual_profile": {{
    {", ".join(f'"{key}": ""' for key in PERSISTENT_PROFILE_KEYS if key != "lore_terms")},
    "lore_terms": [""]
  }},
  "rewritten_prompt": "",
  "issues": [""],
  "confidence": "high|medium|low"
}}

Core baseline slots that matter most:
- facial_structure
- hair_description
- eye_description
- body_type
- clothing_description
- footwear_description
- world_aesthetic_cues

Extracted persistent profile:
{json.dumps(profile, ensure_ascii=False)}

Current prompt:
{entry.get('current_prompt') or ''}

Source evidence:
{entry.get('source_evidence') or ''}

Reference notes:
{json.dumps(reference, ensure_ascii=False)}
"""

    @staticmethod
    def _validate_rewrite_response(response: dict[str, Any]) -> bool:
        return (
            isinstance(response, dict)
            and isinstance(response.get("persistent_visual_profile"), dict)
            and isinstance(response.get("rewritten_prompt"), str)
            and isinstance(response.get("issues"), list)
        )


def _looks_placeholder(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    return any(marker in text for marker in PLACEHOLDER_MARKERS)
