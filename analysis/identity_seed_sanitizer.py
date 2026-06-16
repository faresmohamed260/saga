from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from core.canon_normalization import CanonicalEntityNormalizer


LOCATION_SUFFIXES = {
    "drive",
    "street",
    "road",
    "lane",
    "avenue",
    "way",
    "court",
    "place",
    "square",
    "park",
}
NOISE_PREFIXES = {
    "anything",
    "everything",
    "nothing",
    "someone",
    "somebody",
    "anyone",
    "anybody",
    "gryffindor",
    "slytherin",
    "hufflepuff",
    "ravenclaw",
}
TITLE_PREFIXES = {
    "mr",
    "mrs",
    "ms",
    "miss",
    "sir",
    "lady",
    "lord",
    "professor",
    "madam",
    "uncle",
    "aunt",
}
MIN_SUPPORT_MALFORMED = 8
MIN_SUPPORT_NOISY_PREFIX = 8
MIN_SUPPORT_SPLIT_SHORT = 5
MIN_SUPPORT_TITLE_SINGLE = 5


def sanitize_identity_seed(
    *,
    character_rows: list[dict[str, Any]],
    non_character_entities: list[dict[str, Any]] | None = None,
    normalizer: CanonicalEntityNormalizer | None = None,
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, Any]]:
    normalizer = normalizer or CanonicalEntityNormalizer()
    non_character_entities = non_character_entities or []
    non_character_keys = {
        normalizer.normalized_entity_key(str(row.get("name") or row.get("canonical_name") or ""))
        for row in non_character_entities
        if str(row.get("entity_type") or "").strip().lower() != "character"
    }
    non_character_keys.discard("")

    working_rows = [_copy_seed_row(row) for row in character_rows]
    strong_surface_to_name, first_token_candidates, last_token_candidates = _build_surface_indexes(working_rows, normalizer)

    cleaned_rows: list[dict[str, Any]] = []
    alias_map: dict[str, list[str]] = {}
    diagnostics: dict[str, list[dict[str, Any]]] = {
        "suppressed_rows": [],
        "rewritten_surfaces": [],
        "merged_rows": [],
    }
    merged_by_name: dict[str, dict[str, Any]] = {}

    for row in working_rows:
        rewritten_surfaces: list[str] = []
        seen_surfaces: set[str] = set()
        for surface in [str(row.get("display_name") or "").strip(), *[str(item).strip() for item in row.get("aliases") or [] if str(item).strip()]]:
            rewritten = _rewrite_surface(
                surface=surface,
                row=row,
                normalizer=normalizer,
                non_character_keys=non_character_keys,
                strong_surface_to_name=strong_surface_to_name,
                first_token_candidates=first_token_candidates,
                last_token_candidates=last_token_candidates,
            )
            if rewritten is None:
                diagnostics["rewritten_surfaces"].append({"source": surface, "target": None, "reason": "suppressed"})
                continue
            if rewritten != surface:
                diagnostics["rewritten_surfaces"].append({"source": surface, "target": rewritten, "reason": "normalized"})
            key = normalizer.normalized_entity_key(rewritten)
            if key and key not in seen_surfaces:
                seen_surfaces.add(key)
                rewritten_surfaces.append(rewritten)

        if not rewritten_surfaces:
            diagnostics["suppressed_rows"].append(
                {"display_name": row.get("display_name"), "reason": "no_valid_character_surfaces"}
            )
            continue

        canonical = _pick_best_surface(rewritten_surfaces, mention_count=int(row.get("mention_count") or 0))
        aliases = [surface for surface in rewritten_surfaces if normalizer.normalized_entity_key(surface) != normalizer.normalized_entity_key(canonical)]
        canonical_key = normalizer.normalized_entity_key(canonical)
        merged = merged_by_name.get(canonical_key)
        if merged is None:
            merged = {
                **row,
                "display_name": canonical,
                "aliases": aliases,
            }
            merged_by_name[canonical_key] = merged
            cleaned_rows.append(merged)
        else:
            merged["mention_count"] = int(merged.get("mention_count") or 0) + int(row.get("mention_count") or 0)
            merged_aliases = [str(item).strip() for item in merged.get("aliases") or [] if str(item).strip()]
            for alias in [canonical, *aliases]:
                if (
                    alias
                    and normalizer.normalized_entity_key(alias) != canonical_key
                    and alias not in merged_aliases
                ):
                    merged_aliases.append(alias)
            merged["aliases"] = merged_aliases
            diagnostics["merged_rows"].append({"source": row.get("display_name"), "target": canonical})

    for row in cleaned_rows:
        canonical = str(row.get("display_name") or "").strip()
        aliases = []
        for item in [canonical, *[str(alias).strip() for alias in row.get("aliases") or [] if str(alias).strip()]]:
            key = normalizer.normalized_entity_key(item)
            if not key:
                continue
            alias_map.setdefault(canonical, [])
            if key not in {normalizer.normalized_entity_key(existing) for existing in alias_map[canonical]}:
                alias_map[canonical].append(item)
            if item != canonical and item not in aliases:
                aliases.append(item)
        row["aliases"] = aliases

    cleaned_rows.sort(key=lambda item: str(item.get("display_name") or "").lower())
    for canonical, aliases in alias_map.items():
        alias_map[canonical] = sorted(aliases, key=lambda value: (value != canonical, len(value.split()) < 2, value.lower()))
    diagnostics["character_count_before"] = len(character_rows)
    diagnostics["character_count_after"] = len(cleaned_rows)
    return cleaned_rows, alias_map, diagnostics


def _copy_seed_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id") or "").strip(),
        "display_name": str(row.get("display_name") or "").strip(),
        "aliases": [str(item).strip() for item in row.get("aliases") or [] if str(item).strip()],
        "mention_count": int(row.get("mention_count") or 0),
        "risk_flags": list(row.get("risk_flags") or []),
    }


def _build_surface_indexes(
    rows: list[dict[str, Any]],
    normalizer: CanonicalEntityNormalizer,
) -> tuple[dict[str, str], dict[str, list[str]], dict[str, list[str]]]:
    scored_surfaces: dict[str, tuple[tuple[int, int, int, int, int], str]] = {}
    first_token_candidates: dict[str, list[str]] = defaultdict(list)
    last_token_candidates: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        support = int(row.get("mention_count") or 0)
        for surface in [str(row.get("display_name") or "").strip(), *[str(item).strip() for item in row.get("aliases") or [] if str(item).strip()]]:
            key = normalizer.normalized_entity_key(surface)
            if not key:
                continue
            score = _surface_score(surface, mention_count=support)
            current = scored_surfaces.get(key)
            if current is None or score > current[0]:
                scored_surfaces[key] = (score, surface)
            tokens = surface.split()
            if len(tokens) >= 2 and tokens[0].lower().rstrip(".") not in TITLE_PREFIXES and not tokens[0].isupper():
                first_key = normalizer.normalized_entity_key(tokens[0])
                if first_key and surface not in first_token_candidates[first_key]:
                    first_token_candidates[first_key].append(surface)
                last_key = normalizer.normalized_entity_key(tokens[-1])
                if last_key and surface not in last_token_candidates[last_key]:
                    last_token_candidates[last_key].append(surface)
    strong_surface_to_name = {key: value[1] for key, value in scored_surfaces.items() if len(value[1].split()) >= 2}
    return strong_surface_to_name, first_token_candidates, last_token_candidates


def _rewrite_surface(
    *,
    surface: str,
    row: dict[str, Any],
    normalizer: CanonicalEntityNormalizer,
    non_character_keys: set[str],
    strong_surface_to_name: dict[str, str],
    first_token_candidates: dict[str, list[str]],
    last_token_candidates: dict[str, list[str]],
) -> str | None:
    cleaned = " ".join(str(surface or "").strip().split())
    if not cleaned:
        return None
    tokens = cleaned.split()
    normalized_key = normalizer.normalized_entity_key(cleaned)
    if not normalized_key:
        return None
    support = int(row.get("mention_count") or 0)
    if normalized_key in non_character_keys and not _row_has_nonconflicting_surface(
        row,
        current_surface=cleaned,
        normalizer=normalizer,
        non_character_keys=non_character_keys,
    ):
        return None
    if tokens[-1].lower() in LOCATION_SUFFIXES:
        return None
    if len(tokens) >= 3 and tokens[0].lower().rstrip(".") in TITLE_PREFIXES:
        shortened = " ".join(tokens[:-1])
        shortened_key = normalizer.normalized_entity_key(shortened)
        if shortened_key in strong_surface_to_name:
            return strong_surface_to_name[shortened_key]
    if len(tokens) >= 2 and len(set(token.lower() for token in tokens)) == 1:
        if support < MIN_SUPPORT_MALFORMED:
            return None
        cleaned = tokens[0]
        tokens = [cleaned]
        normalized_key = normalizer.normalized_entity_key(cleaned)
    if len(tokens) >= 2 and (tokens[0].isupper() or tokens[0].lower() in NOISE_PREFIXES):
        if support < MIN_SUPPORT_NOISY_PREFIX:
            return None
        remainder = " ".join(tokens[1:])
        remainder_key = normalizer.normalized_entity_key(remainder)
        if remainder_key in strong_surface_to_name:
            return strong_surface_to_name[remainder_key]
        single_token_target = _resolve_single_token_candidate(
            remainder,
            normalizer=normalizer,
            first_token_candidates=first_token_candidates,
            last_token_candidates=last_token_candidates,
        )
        if single_token_target:
            return single_token_target
        if remainder:
            cleaned = remainder
            tokens = cleaned.split()
            normalized_key = normalizer.normalized_entity_key(cleaned)
    if _looks_like_merged_name(cleaned, row=row, normalizer=normalizer, strong_surface_to_name=strong_surface_to_name):
        if support < MIN_SUPPORT_MALFORMED:
            return None
        return None
    if "possible_split_cluster" in {str(flag).strip().lower() for flag in row.get("risk_flags") or []}:
        if len(tokens) == 1 and support < MIN_SUPPORT_SPLIT_SHORT:
            return None
        better = _resolve_split_cluster(
            cleaned,
            normalizer=normalizer,
            strong_surface_to_name=strong_surface_to_name,
            first_token_candidates=first_token_candidates,
            last_token_candidates=last_token_candidates,
        )
        if better:
            return better
    if len(tokens) == 2 and tokens[0].lower().rstrip(".") in TITLE_PREFIXES and support < MIN_SUPPORT_TITLE_SINGLE:
        full_name_target = _resolve_single_token_candidate(
            tokens[-1],
            normalizer=normalizer,
            first_token_candidates=first_token_candidates,
            last_token_candidates=last_token_candidates,
        )
        if full_name_target:
            return full_name_target
    if normalized_key in strong_surface_to_name:
        return strong_surface_to_name[normalized_key]
    return cleaned


def _row_has_nonconflicting_surface(
    row: dict[str, Any],
    *,
    current_surface: str,
    normalizer: CanonicalEntityNormalizer,
    non_character_keys: set[str],
) -> bool:
    current_key = normalizer.normalized_entity_key(current_surface)
    surfaces = [str(row.get("display_name") or "").strip(), *[str(item).strip() for item in row.get("aliases") or [] if str(item).strip()]]
    for surface in surfaces:
        key = normalizer.normalized_entity_key(surface)
        if not key or key == current_key:
            continue
        if key not in non_character_keys:
            return True
    return False


def _looks_like_merged_name(
    surface: str,
    *,
    row: dict[str, Any],
    normalizer: CanonicalEntityNormalizer,
    strong_surface_to_name: dict[str, str],
) -> bool:
    tokens = surface.split()
    if len(tokens) < 3:
        return False
    support = int(row.get("mention_count") or 0)
    lowered_tokens = [token.lower() for token in tokens]
    if len(set(lowered_tokens)) != len(lowered_tokens):
        return support <= 10
    for pivot in range(1, len(tokens)):
        left = " ".join(tokens[:pivot])
        right = " ".join(tokens[pivot:])
        left_key = normalizer.normalized_entity_key(left)
        right_key = normalizer.normalized_entity_key(right)
        if left_key in strong_surface_to_name and right_key in strong_surface_to_name:
            left_name = strong_surface_to_name[left_key]
            right_name = strong_surface_to_name[right_key]
            if left_name != right_name and support <= 10:
                return True
    return False


def _resolve_split_cluster(
    surface: str,
    *,
    normalizer: CanonicalEntityNormalizer,
    strong_surface_to_name: dict[str, str],
    first_token_candidates: dict[str, list[str]],
    last_token_candidates: dict[str, list[str]],
) -> str | None:
    normalized_key = normalizer.normalized_entity_key(surface)
    if normalized_key in strong_surface_to_name:
        return strong_surface_to_name[normalized_key]
    tokens = surface.split()
    if not tokens:
        return None
    if len(tokens) == 1:
        first_matches = [candidate for candidate in first_token_candidates.get(normalized_key, []) if normalizer.normalized_entity_key(candidate) != normalized_key]
        if len(first_matches) == 1:
            return first_matches[0]
    last_key = normalizer.normalized_entity_key(tokens[-1])
    candidates = [candidate for candidate in last_token_candidates.get(last_key, []) if normalizer.normalized_entity_key(candidate) != normalized_key]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _pick_best_surface(surfaces: list[str], *, mention_count: int) -> str:
    best = surfaces[0]
    best_score = _surface_score(best, mention_count=mention_count)
    for surface in surfaces[1:]:
        score = _surface_score(surface, mention_count=mention_count)
        if score > best_score:
            best = surface
            best_score = score
    return best


def _surface_score(surface: str, *, mention_count: int) -> tuple[int, int, int, int, int]:
    cleaned = str(surface or "").strip()
    tokens = cleaned.split()
    token_count = len(tokens)
    has_full_name = 1 if token_count >= 2 else 0
    non_title_bonus = 1 if tokens and tokens[0].lower().rstrip(".") not in TITLE_PREFIXES else 0
    proper_case_bonus = 1 if cleaned and cleaned[:1].isupper() else 0
    noise_penalty = 1 if any(token.isupper() and len(token) > 1 for token in tokens) else 0
    return (has_full_name, non_title_bonus, token_count, proper_case_bonus, mention_count - noise_penalty)


def _resolve_single_token_candidate(
    surface: str,
    *,
    normalizer: CanonicalEntityNormalizer,
    first_token_candidates: dict[str, list[str]],
    last_token_candidates: dict[str, list[str]],
) -> str | None:
    token_key = normalizer.normalized_entity_key(surface)
    if not token_key:
        return None
    first_matches = first_token_candidates.get(token_key, [])
    if len(first_matches) == 1:
        return first_matches[0]
    last_matches = last_token_candidates.get(token_key, [])
    if len(last_matches) == 1:
        return last_matches[0]
    return None
