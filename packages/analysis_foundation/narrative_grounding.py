"""Deterministic narrative attribution grounding for analysis foundation scenes."""

from __future__ import annotations

import re
from typing import Any

from packages.analysis_foundation.contracts import (
    CanonicalCharacter,
    CanonicalIdentityBundle,
    NarrativeEvidenceSpan,
    SceneArtifact,
    SceneNarrativeGrounding,
)


FIRST_PERSON_TERMS = {"i", "me", "my", "mine", "myself", "we", "us", "our", "ours"}
SECOND_PERSON_TERMS = {"you", "your", "yours", "yourself", "yourselves"}


def ground_scene_narration(
    *,
    scenes: list[SceneArtifact],
    identity_bundle: CanonicalIdentityBundle,
    chapter_texts: list[str] | None = None,
) -> list[SceneNarrativeGrounding]:
    narrator_candidate = infer_global_narrator(identity_bundle=identity_bundle, texts=[*(chapter_texts or []), *[scene.text for scene in scenes]])
    addressee_candidates = infer_global_addressees(identity_bundle=identity_bundle, texts=[*(chapter_texts or []), *[scene.text for scene in scenes]])
    results: list[SceneNarrativeGrounding] = []
    for scene in scenes:
        first_person_count = _pronoun_count(scene.text, FIRST_PERSON_TERMS)
        second_person_count = _pronoun_count(scene.text, SECOND_PERSON_TERMS)
        diagnostics: list[str] = []
        evidence_spans: list[NarrativeEvidenceSpan] = []
        narrator_character_id = ""
        narrator_name = ""
        narrator_confidence = 0.0
        if identity_bundle.narrator.perspective == "first_person" and first_person_count:
            if narrator_candidate:
                narrator_character_id = str(narrator_candidate["character_id"])
                narrator_name = str(narrator_candidate["display_name"])
                narrator_confidence = float(narrator_candidate["confidence"])
                evidence_spans.extend(list(narrator_candidate.get("evidence_spans") or [])[:3])
            else:
                diagnostics.append("first_person_narrator_unresolved")
        scene_addressees = _scene_addressees(scene.text, identity_bundle=identity_bundle, global_addressees=addressee_candidates)
        if second_person_count and not scene_addressees:
            diagnostics.append("second_person_addressee_unresolved")
        results.append(
            SceneNarrativeGrounding(
                scene_id=scene.scene_id,
                perspective=identity_bundle.narrator.perspective,
                narrator_character_id=narrator_character_id,
                narrator_name=narrator_name,
                narrator_confidence=round(narrator_confidence, 4),
                addressee_character_ids=[item["character_id"] for item in scene_addressees],
                addressee_names=[item["display_name"] for item in scene_addressees],
                first_person_count=first_person_count,
                second_person_count=second_person_count,
                evidence_spans=evidence_spans,
                diagnostics=diagnostics,
            )
        )
    return results


def apply_scene_narrative_grounding(
    *,
    scenes: list[SceneArtifact],
    identity_bundle: CanonicalIdentityBundle,
    chapter_texts: list[str] | None = None,
) -> list[SceneArtifact]:
    grounding_by_scene_id = {
        item.scene_id: item
        for item in ground_scene_narration(scenes=scenes, identity_bundle=identity_bundle, chapter_texts=chapter_texts)
    }
    updated: list[SceneArtifact] = []
    for scene in scenes:
        grounding = grounding_by_scene_id.get(scene.scene_id)
        metadata = dict(scene.metadata or {})
        if grounding is not None:
            metadata["narrative_grounding"] = grounding.model_dump()
        updated.append(scene.model_copy(update={"metadata": metadata}))
    return updated


def infer_global_narrator(*, identity_bundle: CanonicalIdentityBundle, texts: list[str]) -> dict[str, Any] | None:
    if identity_bundle.narrator.perspective != "first_person":
        return None
    joined = "\n\n".join(str(text or "") for text in texts if str(text or "").strip())
    if not joined:
        return None
    scores: list[tuple[float, CanonicalCharacter, list[NarrativeEvidenceSpan]]] = []
    for character in identity_bundle.characters:
        score, evidence = _narrator_score(character, joined)
        if score > 0:
            scores.append((score, character, evidence))
    if not scores:
        return None
    scores.sort(key=lambda item: (-item[0], item[1].display_name.casefold()))
    best_score, character, evidence = scores[0]
    runner_up = scores[1][0] if len(scores) > 1 else 0.0
    confidence = best_score / max(best_score + runner_up, 1.0)
    if best_score < 4.0 or confidence < 0.55:
        return None
    return {
        "character_id": character.character_id,
        "display_name": character.display_name,
        "confidence": confidence,
        "score": best_score,
        "evidence_spans": evidence,
    }


def infer_global_addressees(*, identity_bundle: CanonicalIdentityBundle, texts: list[str]) -> list[dict[str, Any]]:
    joined = "\n\n".join(str(text or "") for text in texts if str(text or "").strip())
    if not joined:
        return []
    scored: list[tuple[float, CanonicalCharacter]] = []
    for character in identity_bundle.characters:
        score = 0.0
        names = [character.display_name, *list(character.aliases or [])]
        for name in names:
            if not name:
                continue
            score += 4.0 * len(re.findall(rf"\byou\s*,\s*{re.escape(name)}\b", joined, flags=re.IGNORECASE))
            score += 4.0 * len(re.findall(rf"\b{re.escape(name)}\s*,\s*you\b", joined, flags=re.IGNORECASE))
            score += 2.0 * len(re.findall(rf"\byour\s+(?:sister|brother|mother|father|friend)\b[^.\n]{{0,80}}\b{re.escape(name)}\b", joined, flags=re.IGNORECASE))
        if score > 0:
            scored.append((score, character))
    scored.sort(key=lambda item: (-item[0], item[1].display_name.casefold()))
    return [
        {"character_id": character.character_id, "display_name": character.display_name, "score": score}
        for score, character in scored[:3]
    ]


def narrative_grounding_summary(scenes: list[SceneArtifact]) -> dict[str, Any]:
    groundings = [
        SceneNarrativeGrounding.model_validate(scene.metadata.get("narrative_grounding"))
        for scene in scenes
        if isinstance(scene.metadata.get("narrative_grounding"), dict)
    ]
    diagnostics = [code for item in groundings for code in item.diagnostics]
    return {
        "grounded_scene_count": len(groundings),
        "first_person_scene_count": sum(1 for item in groundings if item.first_person_count > 0),
        "resolved_narrator_scene_count": sum(1 for item in groundings if item.narrator_character_id),
        "addressee_scene_count": sum(1 for item in groundings if item.addressee_character_ids),
        "diagnostic_codes": sorted(set(diagnostics)),
    }


def _narrator_score(character: CanonicalCharacter, text: str) -> tuple[float, list[NarrativeEvidenceSpan]]:
    score = 0.0
    evidence: list[NarrativeEvidenceSpan] = []
    names = [character.display_name, *list(character.aliases or [])]
    for name in names:
        if not name:
            continue
        patterns = [
            (rf"\bthere\s+was\s+a\s+girl\s+named\s+{re.escape(name)}\b", 7.0, "self_story_name"),
            (rf"\bonce\s+upon\s+a\s+time[^.\n]{{0,120}}\b{re.escape(name)}\b", 5.0, "self_story_name"),
            (rf"\b{re.escape(name)}\s*,\s+you(?:'re| are| were| have| had)?\b", 4.0, "direct_address_to_narrator"),
            (rf"\bmy\s+name\s+is\s+{re.escape(name)}\b", 8.0, "explicit_self_name"),
            (rf"\bi\s+am\s+{re.escape(name)}\b", 8.0, "explicit_self_name"),
        ]
        for pattern, weight, kind in patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                window = _window(text, match.start(), match.end(), radius=360)
                if _pronoun_count(window, FIRST_PERSON_TERMS) <= 0:
                    continue
                score += weight
                evidence.append(
                    NarrativeEvidenceSpan(
                        kind=kind,
                        text=_clean_excerpt(window, max_chars=280),
                        start_char=max(0, match.start() - 360),
                        end_char=min(len(text), match.end() + 360),
                        character_id=character.character_id,
                        character_name=character.display_name,
                    )
                )
    return score, evidence


def _scene_addressees(
    text: str,
    *,
    identity_bundle: CanonicalIdentityBundle,
    global_addressees: list[dict[str, Any]],
) -> list[dict[str, str]]:
    matched: list[dict[str, str]] = []
    for character in identity_bundle.characters:
        names = [character.display_name, *list(character.aliases or [])]
        for name in names:
            if not name:
                continue
            if re.search(rf"\byou\s*,\s*{re.escape(name)}\b|\b{re.escape(name)}\s*,\s*you\b", text, flags=re.IGNORECASE):
                matched.append({"character_id": character.character_id, "display_name": character.display_name})
                break
    if matched:
        return _unique_character_rows(matched)
    if _pronoun_count(text, SECOND_PERSON_TERMS) >= 2 and global_addressees:
        best = global_addressees[0]
        return [{"character_id": str(best["character_id"]), "display_name": str(best["display_name"])}]
    return []


def _pronoun_count(text: str, terms: set[str]) -> int:
    if not text:
        return 0
    pattern = "|".join(re.escape(term) for term in sorted(terms, key=len, reverse=True))
    return len(re.findall(rf"\b(?:{pattern})\b", text, flags=re.IGNORECASE))


def _window(text: str, start: int, end: int, *, radius: int) -> str:
    return str(text or "")[max(0, start - radius): min(len(text), end + radius)]


def _clean_excerpt(text: str, *, max_chars: int) -> str:
    cleaned = " ".join(str(text or "").split()).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def _unique_character_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    results: list[dict[str, str]] = []
    for row in rows:
        key = str(row.get("character_id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        results.append(row)
    return results
