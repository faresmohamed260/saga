from __future__ import annotations

import json
import logging
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ftfy import fix_text

LOGGER = logging.getLogger(__name__)


IMPORTANT_CHARACTERS = [
    "Feyre",
    "Tamlin",
    "Lucien",
    "Nesta",
    "Elain",
    "Rhysand",
    "Rhys",
    "Alis",
    "Amarantha",
    "Suriel",
    "Attor",
    "Isaac Hale",
    "Clare Beddor",
    "Andras",
    "Tomas Mandray",
    "Jurian",
]

MOJIBAKE_PATTERNS = (
    "أ¢â‚¬",
    "أ¢â‚¬إ’",
    "أ¢â‚¬\u200c",
    "Iأ¢â‚¬",
    "Iâ€ â„¢",
    "â€ آ¦",
    "ط£آ¢أ¢â€ڑآ¬",
    "أ¢â€ڑآ¬",
)
TITLE_PREFIXES = {
    "mr",
    "mrs",
    "miss",
    "ms",
    "dr",
    "sir",
    "lady",
    "lord",
    "captain",
    "professor",
    "reverend",
}
REFERENCE_PREFIXES = ("my ", "the ", "our ")
GENERIC_REFERENCE_NAMES = {
    "my father",
    "my mother",
    "the high lord",
    "the suriel",
    "the attor",
    "the king of hybern",
}
SINGLETON_SUPPRESS = {
    "prythian",
    "cauldron",
    "i",
    "you",
    "he",
    "she",
    "they",
    "someone",
    "something",
}
NON_NAME_SINGLETONS = {
    "it",
    "we",
    "everyone",
    "someone",
    "fate",
    "rage",
    "solstice",
    "actually",
    "fed",
    "let",
    "don",
    "death",
    "hybern",
    "prythian",
    "calanmai",
    "horseshoes",
    "milady",
    "lady",
    "faerie",
    "faeries",
    "high fae",
    "cauldron",
    "bastard",
    "hollow",
    "didn",
    "whoever",
    "another high lord",
}
REFERENCE_SINGLETONS = {
    "father",
    "mother",
    "high lord",
    "king",
    "queen",
}
LOCATION_OBJECT_HINTS = {
    "prythian",
    "hybern",
    "cauldron",
    "court",
    "mountain",
    "woods",
    "forest",
}
PREPENDED_ALIAS_LEAK_HINTS = LOCATION_OBJECT_HINTS | {
    "kingdom",
    "court",
    "blessed",
    "state",
}
BROKEN_QUOTE_RE = re.compile(r'[\"â€œâ€‌]|\.{2,}|[?!]["â€‌]?')
NAME_TOKEN_RE = re.compile(r"^[A-Z][A-Za-z'â€™-]+$")


@dataclass
class ClusterRecord:
    raw_display_name: str
    display_name: str
    aliases: List[str]
    proper_mentions: List[Dict[str, Any]]
    common_mentions: List[Dict[str, Any]]
    pronoun_mentions: List[Dict[str, Any]]
    mention_count: int
    quote_count: int
    first_seen: Optional[int]
    risk_flags: set[str] = field(default_factory=set)
    cluster_ids: List[Any] = field(default_factory=list)
    merged_from_clusters: List[str] = field(default_factory=list)


@dataclass
class CandidateReviewContext:
    display_name: str
    current_bucket: str
    payload: Dict[str, Any]
    removed_aliases: List[Dict[str, str]] = field(default_factory=list)
    first_appearance_excerpt: str = ""
    evidence_snippets: List[str] = field(default_factory=list)
    rival_candidates: List[Dict[str, Any]] = field(default_factory=list)
    external_reference: Dict[str, Any] | None = None


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\n", " ").replace("\t", " ")).strip()


def normalize_surface(text: str) -> str:
    fixed = fix_text(text or "")
    fixed = normalize_whitespace(fixed)
    fixed = fixed.strip(" \"'â€œâ€‌â€کâ€™.,;:!?-")
    return fixed


def contains_mojibake(text: str) -> bool:
    return any(pattern in (text or "") for pattern in MOJIBAKE_PATTERNS)


def strip_mojibake(text: str) -> str:
    cleaned = fix_text(text or "")
    for pattern in MOJIBAKE_PATTERNS:
        cleaned = cleaned.replace(pattern, " ")
    cleaned = cleaned.replace("â€”", " ").replace("â€“", " ")
    cleaned = normalize_whitespace(cleaned)
    tokens = []
    for token in cleaned.split():
        token = re.sub(r"^[^A-Za-z\[]+", "", token)
        token = re.sub(r"(?<=[A-Za-z]{2})[^A-Za-z'â€™-]+$", "", token)
        if token:
            tokens.append(token)
    cleaned = " ".join(tokens)
    cleaned = cleaned.strip(" \"'â€œâ€‌â€کâ€™.,;:!?-")
    return cleaned


def normalize_name_key(text: str) -> str:
    cleaned = strip_mojibake(text).lower()
    cleaned = re.sub(r"[^a-z0-9\s'-]", "", cleaned)
    cleaned = normalize_whitespace(cleaned)
    return cleaned


def looks_name_like(text: str) -> bool:
    cleaned = strip_mojibake(text)
    if not cleaned:
        return False
    tokens = cleaned.split()
    if len(tokens) > 4:
        return False
    if cleaned.lower() in SINGLETON_SUPPRESS:
        return False
    if all(NAME_TOKEN_RE.match(tok) for tok in tokens):
        return True
    if len(tokens) >= 2 and tokens[0].lower().rstrip(".") in TITLE_PREFIXES and NAME_TOKEN_RE.match(tokens[-1]):
        return True
    return False


def compatible_alias(display_name: str, alias: str) -> bool:
    display_key = normalize_name_key(display_name)
    alias_key = normalize_name_key(alias)
    if not display_key or not alias_key:
        return False
    if display_key == alias_key:
        return True
    if alias_key in {display_key.removeprefix("the "), display_key.removeprefix("my ")}:
        return True
    if display_key in {alias_key.removeprefix("the "), alias_key.removeprefix("my ")}:
        return True

    display_tokens = display_key.split()
    alias_tokens = alias_key.split()
    if any(token in alias_tokens for token in ("and", "for", "with", "to", "from", "state", "ponder", "worse", "darling", "dear")):
        return False
    if len(display_tokens) == 1 and len(alias_tokens) >= 1:
        if len(alias_tokens) > 2:
            title_name = alias_tokens[0] in TITLE_PREFIXES or alias_tokens[0] in {"the", "my"}
            if not title_name:
                return False
        if alias_tokens[0] == display_tokens[0] or alias_tokens[-1] == display_tokens[0]:
            return True
    if len(display_tokens) >= 2 and all(tok in alias_tokens for tok in display_tokens):
        return True
    return False


def salvage_alias(alias: str, display_name: str) -> Tuple[Optional[str], Optional[str]]:
    original = normalize_surface(alias)
    if not original:
        return None, "empty_alias"
    cleaned = strip_mojibake(original)
    if not cleaned:
        return None, "artifact_only_alias"
    lowered = cleaned.lower()
    if lowered in SINGLETON_SUPPRESS:
        return None, "pronoun_or_generic_alias"
    if len(cleaned.split()) > 6:
        return None, "sentence_fragment_alias"
    if any(punct in original for punct in (".", "?", "!", ":", ";")):
        if normalize_name_key(cleaned) != normalize_name_key(display_name):
            title_name = len(cleaned.split()) >= 2 and cleaned.split()[0].lower().rstrip(".") in TITLE_PREFIXES
            if not title_name:
                return None, "dialogue_fragment_alias"
    if BROKEN_QUOTE_RE.search(original) and not compatible_alias(display_name, cleaned):
        return None, "dialogue_fragment_alias"
    if any(token in lowered.split() for token in LOCATION_OBJECT_HINTS) and not compatible_alias(display_name, cleaned):
        return None, "location_or_object_alias"
    display_tokens = normalize_name_key(display_name).split()
    alias_tokens = normalize_name_key(cleaned).split()
    if (
        display_tokens
        and alias_tokens
        and alias_tokens[-len(display_tokens):] == display_tokens
        and len(alias_tokens) > len(display_tokens)
    ):
        prefix_tokens = alias_tokens[:-len(display_tokens)]
        if prefix_tokens and prefix_tokens[0] not in TITLE_PREFIXES and any(token in PREPENDED_ALIAS_LEAK_HINTS for token in prefix_tokens):
            return None, "prepended_location_or_object_alias"
    if not compatible_alias(display_name, cleaned):
        return None, "incompatible_alias"
    return cleaned, None


def merge_name_key(record: ClusterRecord) -> str:
    base = normalize_name_key(record.display_name)
    if base:
        return base
    for alias in record.aliases:
        alias_key = normalize_name_key(alias)
        if alias_key:
            return alias_key
    return normalize_name_key(record.raw_display_name)


def choose_display_name(display_names: Iterable[str]) -> str:
    candidates = [strip_mojibake(name) for name in display_names if strip_mojibake(name)]
    if not candidates:
        return ""

    def score(name: str) -> Tuple[int, int, str]:
        lower = name.lower()
        is_reference = lower.startswith(REFERENCE_PREFIXES)
        is_title_name = len(name.split()) >= 2 and name.split()[0].lower().rstrip(".") in TITLE_PREFIXES
        name_like = looks_name_like(name)
        return (
            3 if name_like else 2 if is_title_name else 1 if is_reference else 0,
            len(name.split()),
            name,
        )

    return sorted(candidates, key=score, reverse=True)[0]


def cluster_kind(record: ClusterRecord) -> str:
    display = record.display_name.lower()
    pronoun_total = sum(int(item.get("count", 0) or 0) for item in record.pronoun_mentions)
    proper_total = sum(int(item.get("count", 0) or 0) for item in record.proper_mentions)
    if record.display_name == "[NARRATOR]":
        return "narrator"
    if not record.display_name:
        return "suppressed"
    if display in SINGLETON_SUPPRESS:
        return "suppressed"
    if display in NON_NAME_SINGLETONS:
        return "suppressed"
    if display in REFERENCE_SINGLETONS:
        return "reference"
    if display in GENERIC_REFERENCE_NAMES or display.startswith(REFERENCE_PREFIXES):
        return "reference"
    if "high lord" in display or "high lady" in display:
        return "reference"
    if display.startswith("the ") and not looks_name_like(record.display_name):
        return "reference"
    if len(display.split()) == 1 and display in LOCATION_OBJECT_HINTS:
        return "suppressed"
    if any(flag in record.risk_flags for flag in ("pronoun_only_cluster", "encoding_artifact_only")):
        return "suppressed"
    if looks_name_like(record.display_name):
        if len(display.split()) == 1 and record.mention_count < 20 and record.quote_count == 0 and pronoun_total < 5 and proper_total < 10:
            return "suppressed"
        return "stable"
    if any(token in display.split() for token in ("suriel", "attor")):
        return "reference"
    return "suppressed"


def compress_mentions(mentions: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counter: Counter[str] = Counter()
    for mention in mentions:
        text = normalize_surface(mention.get("text", ""))
        if text:
            counter[text] += int(mention.get("count", 0) or 0)
    return [{"text": text, "count": count} for text, count in counter.most_common(20)]


def cleaned_aliases_for_record(record: ClusterRecord) -> Tuple[List[str], List[Dict[str, str]]]:
    aliases: List[str] = []
    removed: List[Dict[str, str]] = []
    for alias in [record.display_name] + list(record.aliases):
        cleaned, reason = salvage_alias(alias, record.display_name)
        if cleaned:
            if cleaned not in aliases:
                aliases.append(cleaned)
        else:
            removed.append({"alias": alias, "reason": reason or "dropped"})
    return aliases, removed


def derive_narrator_payload(narrator_record: ClusterRecord, stable_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    hypothesis_candidates = []
    for row in stable_records:
        pronoun_total = sum(item["count"] for item in row.get("pronoun_mentions", []))
        proper_total = sum(item["count"] for item in row.get("proper_mentions", []))
        if row["display_name"] == "[NARRATOR]":
            continue
        if proper_total >= 3 and pronoun_total <= 5 and row.get("mention_count", 0) >= 10:
            hypothesis_candidates.append((row["mention_count"], row["display_name"]))
    hypothesis_candidates.sort(reverse=True)
    possible_name = hypothesis_candidates[0][1] if hypothesis_candidates else None
    return {
        "display_name": "[NARRATOR]",
        "possible_name": possible_name,
        "confidence": "hypothesis" if possible_name else "unknown",
        "quote_count": narrator_record.quote_count,
        "pronoun_mentions": compress_mentions(narrator_record.pronoun_mentions),
        "mention_count": narrator_record.mention_count,
        "first_seen": narrator_record.first_seen,
        "risk_flags": sorted(narrator_record.risk_flags | {"separate_narrator"}),
        "cluster_ids": narrator_record.cluster_ids,
    }


def important_character_coverage(cleaned: Dict[str, Any]) -> List[Dict[str, Any]]:
    def rows_for_tier(tier_name: str) -> List[Dict[str, Any]]:
        payload = cleaned.get(tier_name, [])
        if payload is None:
            return []
        if isinstance(payload, dict):
            return [payload]
        return payload

    tiers = [
        ("stable_named_characters", rows_for_tier("stable_named_characters")),
        ("reference_entities", rows_for_tier("reference_entities")),
        ("narrator", rows_for_tier("narrator")),
    ]
    coverage = []
    for name in IMPORTANT_CHARACTERS:
        match = None
        match_tier = None
        for tier_name, rows in tiers:
            for row in rows:
                surfaces = [row.get("display_name", "")] + row.get("aliases", [])
                target_key = normalize_name_key(name)
                def _matches(surface: str) -> bool:
                    surface_key = normalize_name_key(surface)
                    if not surface_key:
                        return False
                    if surface_key == target_key:
                        return True
                    surface_tokens = surface_key.split()
                    target_tokens = target_key.split()
                    if len(target_tokens) == 1:
                        return surface_tokens in ([target_tokens[0]], ["the", target_tokens[0]], [target_tokens[0], "hale"], [target_tokens[0], "beddor"], [target_tokens[0], "mandray"])
                    return all(tok in surface_tokens for tok in target_tokens)
                if any(_matches(surface) for surface in surfaces):
                    match = row
                    match_tier = tier_name
                    break
            if match:
                break
        coverage.append(
            {
                "name": name,
                "present": match is not None,
                "tier": match_tier or "",
                "display_name": match.get("display_name", "") if match else "",
                "aliases": match.get("aliases", [])[:8] if match else [],
                "mention_count": match.get("mention_count", 0) if match else 0,
                "quote_count": match.get("quote_count", 0) if match else 0,
                "risk_flags": match.get("risk_flags", []) if match else [],
                "merged_from_clusters": match.get("merged_from_clusters", []) if match else [],
            }
        )
    return coverage


def markdown_table(headers: List[str], rows: List[Dict[str, Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        vals = []
        for header in headers:
            value = row.get(header, "")
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            elif value is None:
                value = ""
            else:
                value = str(value)
            value = value.replace("\n", " ").replace("|", "\\|")
            vals.append(value)
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def build_cluster_record(entry: Dict[str, Any]) -> ClusterRecord:
    raw_display = entry.get("display_name", "")
    cleaned_display = strip_mojibake(raw_display) if raw_display != "[NARRATOR]" else "[NARRATOR]"
    if raw_display != "[NARRATOR]" and not cleaned_display:
        cleaned_display = normalize_surface(raw_display)
    return ClusterRecord(
        raw_display_name=raw_display,
        display_name=cleaned_display,
        aliases=list(entry.get("aliases", [])),
        proper_mentions=list(entry.get("proper_mentions", [])),
        common_mentions=list(entry.get("common_mentions", [])),
        pronoun_mentions=list(entry.get("pronoun_mentions", [])),
        mention_count=int(entry.get("mention_count", 0) or 0),
        quote_count=int(entry.get("quote_count", 0) or 0),
        first_seen=entry.get("first_seen"),
        risk_flags=set(entry.get("risk_flags", [])),
        cluster_ids=[entry.get("cluster_id")],
        merged_from_clusters=[raw_display],
    )


def merge_records(records: List[ClusterRecord]) -> List[ClusterRecord]:
    merged: Dict[str, ClusterRecord] = {}
    for record in records:
        key = merge_name_key(record)
        if not key:
            key = normalize_name_key(record.raw_display_name)
        if not key:
            key = f"cluster_{len(merged)+1}"
        target = merged.get(key)
        if target is None:
            merged[key] = record
            continue
        target.aliases.extend(record.aliases)
        target.proper_mentions.extend(record.proper_mentions)
        target.common_mentions.extend(record.common_mentions)
        target.pronoun_mentions.extend(record.pronoun_mentions)
        target.mention_count += record.mention_count
        target.quote_count += record.quote_count
        if target.first_seen is None or (record.first_seen is not None and record.first_seen < target.first_seen):
            target.first_seen = record.first_seen
        target.risk_flags |= record.risk_flags
        target.cluster_ids.extend(record.cluster_ids)
        target.merged_from_clusters.extend(record.merged_from_clusters)
        target.display_name = choose_display_name([target.display_name, record.display_name])
    return list(merged.values())


def merge_short_name_variants(records: List[ClusterRecord]) -> List[ClusterRecord]:
    consumed: set[int] = set()
    for idx, record in enumerate(records):
        if idx in consumed:
            continue
        key = normalize_name_key(record.display_name)
        tokens = key.split()
        if len(tokens) != 1:
            continue
        token = tokens[0]
        if not (3 <= len(token) <= 5):
            continue
        candidates: List[Tuple[int, ClusterRecord]] = []
        for jdx, other in enumerate(records):
            if jdx == idx or jdx in consumed:
                continue
            other_key = normalize_name_key(other.display_name)
            if other_key.startswith(token) and other_key != key and len(other_key) > len(key):
                candidates.append((jdx, other))
        if len(candidates) != 1:
            continue
        _, other = candidates[0]
        if other.mention_count < max(20, record.mention_count * 3):
            continue
        other.aliases.extend(record.aliases + [record.display_name])
        other.proper_mentions.extend(record.proper_mentions)
        other.common_mentions.extend(record.common_mentions)
        other.pronoun_mentions.extend(record.pronoun_mentions)
        other.mention_count += record.mention_count
        other.quote_count += record.quote_count
        other.risk_flags |= record.risk_flags | {"merged_short_variant"}
        other.cluster_ids.extend(record.cluster_ids)
        other.merged_from_clusters.extend(record.merged_from_clusters)
        consumed.add(idx)
    return [record for idx, record in enumerate(records) if idx not in consumed]


def serialize_record(record: ClusterRecord, aliases: List[str]) -> Dict[str, Any]:
    return {
        "display_name": record.display_name,
        "aliases": aliases,
        "proper_mentions": compress_mentions(record.proper_mentions),
        "common_mentions": compress_mentions(record.common_mentions),
        "pronoun_mentions": compress_mentions(record.pronoun_mentions),
        "mention_count": record.mention_count,
        "quote_count": record.quote_count,
        "first_seen": record.first_seen,
        "risk_flags": sorted(record.risk_flags),
        "cluster_ids": record.cluster_ids,
        "merged_from_clusters": sorted(set(record.merged_from_clusters)),
    }


def _snippetize(text: str, *, max_chars: int = 320) -> str:
    cleaned = normalize_whitespace(text or "")
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rstrip() + "..."


def _collect_candidate_text_evidence(
    display_name: str,
    aliases: List[str],
    chapters: List[Dict[str, Any]] | None,
    *,
    max_snippets: int = 6,
) -> Tuple[str, List[str]]:
    if not chapters:
        return "", []
    surfaces = [item for item in [display_name, *aliases] if str(item or "").strip()]
    pattern = re.compile("|".join(re.escape(item) for item in surfaces), re.IGNORECASE) if surfaces else None
    first_excerpt = ""
    snippets: List[str] = []
    for chapter in chapters:
        content = str(chapter.get("content") or "").strip()
        if not content:
            continue
        paragraphs = [item.strip() for item in re.split(r"\n\s*\n", content) if item.strip()]
        if not paragraphs:
            paragraphs = [content]
        for paragraph in paragraphs:
            if pattern is None or not pattern.search(paragraph):
                continue
            snippet = _snippetize(paragraph)
            if not first_excerpt:
                first_excerpt = snippet
            if snippet not in snippets:
                snippets.append(snippet)
            if len(snippets) >= max_snippets:
                return first_excerpt, snippets
    return first_excerpt, snippets


def _candidate_rivals(
    display_name: str,
    aliases: List[str],
    pool: List[Dict[str, Any]],
    *,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    current_key = normalize_name_key(display_name)
    current_aliases = {normalize_name_key(item) for item in aliases if normalize_name_key(item)}
    current_tokens = set(current_key.split())
    rivals: List[Tuple[int, Dict[str, Any]]] = []
    for row in pool:
        other_name = str(row.get("display_name") or "").strip()
        other_key = normalize_name_key(other_name)
        if not other_name or other_key == current_key:
            continue
        other_aliases = {normalize_name_key(item) for item in row.get("aliases", []) if normalize_name_key(item)}
        other_tokens = set(other_key.split())
        overlap = len(current_tokens & other_tokens)
        alias_overlap = len(current_aliases & other_aliases)
        prefix_overlap = int(
            bool(current_key and other_key and (current_key.startswith(other_key) or other_key.startswith(current_key)))
        )
        score = overlap * 3 + alias_overlap * 4 + prefix_overlap * 2
        if score <= 0:
            continue
        rivals.append(
            (
                score,
                {
                    "display_name": other_name,
                    "aliases": list(row.get("aliases") or [])[:8],
                    "mention_count": int(row.get("mention_count", 0) or 0),
                    "risk_flags": list(row.get("risk_flags") or []),
                    "current_bucket": str(row.get("_bucket") or "").strip(),
                },
            )
        )
    rivals.sort(key=lambda item: (-item[0], -item[1]["mention_count"], item[1]["display_name"].lower()))
    return [row for _, row in rivals[:limit]]


def _identity_suspicion_score(row: Dict[str, Any]) -> int:
    display_name = str(row.get("display_name") or "").strip()
    lowered = normalize_name_key(display_name)
    tokens = lowered.split()
    risk_flags = list(row.get("risk_flags") or [])
    score = 0
    if len(tokens) >= 2 and len(set(tokens)) < len(tokens):
        score += 8
    if any(flag in risk_flags for flag in ("possible_split_cluster", "encoding_noise", "noisy_ocr_or_tokenization_in_mentions")):
        score += 6
    if any(ch.isdigit() for ch in display_name) or any(ch in display_name for ch in "[]{}<>"):
        score += 5
    if any(piece in display_name.lower() for piece in ("mr ", "mrs ", "miss ", "uncle ", "aunt ")) and len(tokens) >= 3:
        score += 4
    if any(not token.isalpha() and "'" not in token for token in display_name.split()):
        score += 3
    if str(row.get("_bucket") or "") == "stable" and len(tokens) == 1 and int(row.get("mention_count", 0) or 0) <= 6:
        score += 2
    return score


def _llm_identity_review_validator(response: Dict[str, Any]) -> bool:
    return (
        isinstance(response, dict)
        and str(response.get("recommended_bucket") or "") in {"stable", "reference", "suppressed"}
        and isinstance(response.get("approved_aliases"), list)
        and isinstance(response.get("rejected_aliases"), list)
        and isinstance(response.get("notes"), list)
        and isinstance(response.get("risk_flags_add"), list)
    )


def _build_book_context_summary(cleaned: Dict[str, Any]) -> Dict[str, Any]:
    stable_rows = list(cleaned.get("stable_named_characters") or [])
    reference_rows = list(cleaned.get("reference_entities") or [])
    suppressed_rows = list(cleaned.get("suppressed_clusters") or [])
    return {
        "stable_count": len(stable_rows),
        "reference_count": len(reference_rows),
        "suppressed_count": len(suppressed_rows),
        "top_stable": [
            {
                "display_name": row.get("display_name"),
                "mention_count": row.get("mention_count", 0),
                "aliases": list(row.get("aliases") or [])[:5],
            }
            for row in stable_rows[:10]
        ],
        "top_reference": [
            {
                "display_name": row.get("display_name"),
                "mention_count": row.get("mention_count", 0),
                "aliases": list(row.get("aliases") or [])[:5],
            }
            for row in reference_rows[:10]
        ],
        "important_cast_coverage": list((cleaned.get("diagnostics") or {}).get("important_cast_coverage") or [])[:20],
    }


def _build_candidate_review_prompt(
    context: CandidateReviewContext,
    *,
    book_title: str,
    book_context: Dict[str, Any],
) -> str:
    return f"""
You are the second-pass identity audit layer for a canon extraction pipeline.
Return strict JSON only.

Your task is to review one cleaned BookNLP identity candidate using evidence from the source book.

Rules:
- Be conservative. Prefer "keep separate" over unsafe merges.
- Do not invent new characters or aliases that are not supported by the evidence.
- If the candidate is a generic reference, title-only mention, place/object leak, or malformed surface, demote it to "reference" or "suppressed".
- Recommend a merge only when the evidence strongly supports that this candidate is the same identity as an existing rival candidate.
- Approved aliases should be selected from the candidate aliases or safe normalized title/name variants already implied by the evidence.
- Use the optional external reference only as supporting evidence, never as permission to override contradictory book evidence.

Book:
- title: {book_title or "unknown"}

Book context:
{json.dumps(book_context, ensure_ascii=False)}

Candidate:
{json.dumps({
    "display_name": context.display_name,
    "current_bucket": context.current_bucket,
    "payload": context.payload,
    "removed_aliases": context.removed_aliases,
}, ensure_ascii=False)}

First appearance excerpt:
{context.first_appearance_excerpt or "none"}

Evidence snippets:
{json.dumps(context.evidence_snippets or [], ensure_ascii=False)}

Rival candidates:
{json.dumps(context.rival_candidates or [], ensure_ascii=False)}

Optional external reference:
{json.dumps(context.external_reference or {}, ensure_ascii=False)}

Return JSON with this schema:
{{
  "recommended_bucket": "stable|reference|suppressed",
  "recommended_display_name": "",
  "approved_aliases": [""],
  "merge_target_display_name": "",
  "confidence": "high|medium|low",
  "notes": [""],
  "risk_flags_add": [""],
  "rejected_aliases": [{{"alias": "", "reason": ""}}]
}}
"""


def _build_residual_cleanup_prompt(
    context: CandidateReviewContext,
    *,
    book_title: str,
    book_context: Dict[str, Any],
) -> str:
    return f"""
You are the residual identity cleanup pass for a canon extraction pipeline.
Return strict JSON only.

This is pass 2. The candidate survived an earlier review but still looks suspicious.

Decision policy for pass 2:
- Bias against leaving suspicious rows in stable characters.
- Keep `stable` only if the evidence clearly supports a recurring person-like saga.identity.
- Use `reference` for places, schools, houses, teams, groups, titles, creatures-as-references, and generic named concepts.
- Use `suppressed` for malformed strings, duplicated strings, OCR noise, concatenated mentions, pronouns, and non-identity fragments.
- Merge only when the target is clearly the same identity and the target is cleaner.
- Do not invent aliases.

Book:
- title: {book_title or "unknown"}

Book context:
{json.dumps(book_context, ensure_ascii=False)}

Suspicious candidate:
{json.dumps({
    "display_name": context.display_name,
    "current_bucket": context.current_bucket,
    "payload": context.payload,
    "removed_aliases": context.removed_aliases,
}, ensure_ascii=False)}

First appearance excerpt:
{context.first_appearance_excerpt or "none"}

Evidence snippets:
{json.dumps(context.evidence_snippets or [], ensure_ascii=False)}

Rival candidates:
{json.dumps(context.rival_candidates or [], ensure_ascii=False)}

Optional external reference:
{json.dumps(context.external_reference or {}, ensure_ascii=False)}

Return JSON with this schema:
{{
  "recommended_bucket": "stable|reference|suppressed",
  "recommended_display_name": "",
  "approved_aliases": [""],
  "merge_target_display_name": "",
  "confidence": "high|medium|low",
  "notes": [""],
  "risk_flags_add": [""],
  "rejected_aliases": [{{"alias": "", "reason": ""}}]
}}
"""


def _merge_payload_rows(source: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(target)
    merged["aliases"] = list(dict.fromkeys([*(target.get("aliases") or []), *(source.get("aliases") or [])]))
    merged["proper_mentions"] = list(target.get("proper_mentions") or []) + list(source.get("proper_mentions") or [])
    merged["common_mentions"] = list(target.get("common_mentions") or []) + list(source.get("common_mentions") or [])
    merged["pronoun_mentions"] = list(target.get("pronoun_mentions") or []) + list(source.get("pronoun_mentions") or [])
    merged["mention_count"] = int(target.get("mention_count", 0) or 0) + int(source.get("mention_count", 0) or 0)
    merged["quote_count"] = int(target.get("quote_count", 0) or 0) + int(source.get("quote_count", 0) or 0)
    target_first = target.get("first_seen")
    source_first = source.get("first_seen")
    if target_first is None or (source_first is not None and source_first < target_first):
        merged["first_seen"] = source_first
    merged["risk_flags"] = sorted(set(list(target.get("risk_flags") or []) + list(source.get("risk_flags") or []) + ["llm_merge_applied"]))
    merged["cluster_ids"] = list(dict.fromkeys(list(target.get("cluster_ids") or []) + list(source.get("cluster_ids") or [])))
    merged["merged_from_clusters"] = sorted(
        set(list(target.get("merged_from_clusters") or []) + list(source.get("merged_from_clusters") or []) + [source.get("display_name", "")])
    )
    return merged


def _select_residual_cleanup_candidates(
    cleaned: Dict[str, Any],
    *,
    max_candidates: int = 16,
) -> List[str]:
    stable_rows = [dict(row) for row in cleaned.get("stable_named_characters") or []]
    references = {
        normalize_name_key(str(row.get("display_name") or "")): row
        for row in cleaned.get("reference_entities") or []
        if str(row.get("display_name") or "").strip()
    }
    candidates: List[Tuple[int, str]] = []
    for row in stable_rows:
        display_name = str(row.get("display_name") or "").strip()
        if not display_name:
            continue
        payload = dict(row)
        payload["_bucket"] = "stable"
        score = _identity_suspicion_score(payload)
        lowered = normalize_name_key(display_name)
        if lowered in references:
            score += 10
        if any(term in lowered.split() for term in {"school", "house", "team", "drive", "street", "road", "bank"}):
            score += 6
        if any(term in lowered for term in {"hogwarts", "gryffindor", "quidditch", "gringotts", "privet", "muggles"}):
            score += 8
        if len(lowered.split()) >= 2 and any(token in {"harry", "ron", "hermione", "vernon", "mcgonagall", "dumbledore"} for token in lowered.split()):
            score += 2
        if score > 0:
            candidates.append((score, display_name))
    candidates.sort(key=lambda item: (-item[0], item[1].lower()))
    return [name for _, name in candidates[: max(1, int(max_candidates or 16))]]


def _apply_llm_identity_review(
    cleaned: Dict[str, Any],
    *,
    chapters: List[Dict[str, Any]] | None = None,
    book_title: str = "",
    llm_review_mode: str = "",
    enable_external_research: bool = False,
    max_review_candidates: int = 24,
    web_search_tool=None,
) -> Dict[str, Any]:
    if not str(llm_review_mode or "").strip():
        return cleaned

    from saga.providers.reasoning_runtime_adapter import create_runtime_client

    LOGGER.info(
        "BookNLP identity LLM review start | mode=%s external_research=%s max_candidates=%s",
        llm_review_mode,
        enable_external_research,
        max_review_candidates,
    )

    book_context = _build_book_context_summary(cleaned)
    llm = create_runtime_client(
        mode=str(llm_review_mode).strip(),
        max_retries=2,
        base_delay=1.0,
        timeout=120,
        allow_account_rotation=True,
        allow_cross_provider_fallback=False,
    )
    review_max_attempts = 3
    review_retry_delay_seconds = 1.5

    wiki_service = None
    if enable_external_research:
        try:
            from saga.services.wiki_character_reference_service import WikiCharacterReferenceService

            wiki_service = WikiCharacterReferenceService(llm_client=llm, web_search_tool=web_search_tool)
        except Exception:
            wiki_service = None

    pool: List[Dict[str, Any]] = []
    for bucket_name in ("stable_named_characters", "reference_entities", "suppressed_clusters"):
        for row in cleaned.get(bucket_name) or []:
            payload = dict(row)
            payload["_bucket"] = (
                "stable" if bucket_name == "stable_named_characters"
                else "reference" if bucket_name == "reference_entities"
                else "suppressed"
            )
            pool.append(payload)

    candidate_rows = sorted(
        [
            row for row in pool
            if int(row.get("mention_count", 0) or 0) >= 3
            or str(row.get("display_name") or "").strip() in IMPORTANT_CHARACTERS
            or _identity_suspicion_score(row) > 0
        ],
        key=lambda row: (
            -_identity_suspicion_score(row),
            -int(row.get("mention_count", 0) or 0),
            str(row.get("display_name") or "").lower(),
        ),
    )[: max(1, int(max_review_candidates or 24))]

    def build_review_contexts(rows: List[Dict[str, Any]]) -> List[CandidateReviewContext]:
        contexts: List[CandidateReviewContext] = []
        for row in rows:
            display_name = str(row.get("display_name") or "").strip()
            aliases = list(row.get("aliases") or [])
            first_excerpt, snippets = _collect_candidate_text_evidence(display_name, aliases, chapters)
            external_reference = None
            if wiki_service and row.get("_bucket") in {"stable", "reference"}:
                try:
                    external_reference = wiki_service.research_character(
                        display_name,
                        local_context={"aliases": aliases, "mention_count": int(row.get("mention_count", 0) or 0)},
                        contract_title=book_title,
                    )
                except Exception as exc:
                    external_reference = {"issues": [f"external_reference_error:{exc.__class__.__name__}"]}
            contexts.append(
                CandidateReviewContext(
                    display_name=display_name,
                    current_bucket=str(row.get("_bucket") or ""),
                    payload={key: value for key, value in row.items() if not str(key).startswith("_")},
                    removed_aliases=[],
                    first_appearance_excerpt=first_excerpt,
                    evidence_snippets=snippets,
                    rival_candidates=_candidate_rivals(display_name, aliases, pool),
                    external_reference=external_reference,
                )
            )
        return contexts

    review_contexts = build_review_contexts(candidate_rows)
    LOGGER.info(
        "BookNLP identity broad review prepared | candidates=%s stable=%s reference=%s suppressed=%s",
        len(review_contexts),
        len(cleaned.get("stable_named_characters") or []),
        len(cleaned.get("reference_entities") or []),
        len(cleaned.get("suppressed_clusters") or []),
    )

    applied_decisions: List[Dict[str, Any]] = []
    decisions_by_name: Dict[str, Dict[str, Any]] = {}

    def collect_decisions(
        contexts: List[CandidateReviewContext],
        *,
        pass_name: str,
        prompt_builder,
    ) -> None:
        if not contexts:
            return

        def _review_one(context: CandidateReviewContext) -> Tuple[CandidateReviewContext, Dict[str, Any] | Any]:
            prompt = prompt_builder(context, book_title=book_title, book_context=book_context)
            last_error = "unknown_error"
            for attempt in range(1, review_max_attempts + 1):
                LOGGER.info(
                    "BookNLP identity %s candidate attempt start | name=%s bucket=%s attempt=%s/%s",
                    pass_name,
                    context.display_name,
                    context.current_bucket,
                    attempt,
                    review_max_attempts,
                )
                response = llm.generate_json(
                    prompt,
                    strict=True,
                    validator=_llm_identity_review_validator,
                    max_tokens=1200,
                )
                if isinstance(response, dict) and "error" not in response:
                    LOGGER.info(
                        "BookNLP identity %s candidate attempt complete | name=%s attempt=%s/%s",
                        pass_name,
                        context.display_name,
                        attempt,
                        review_max_attempts,
                    )
                    return context, response
                last_error = str((response or {}).get("error") or "unknown_error")
                LOGGER.warning(
                    "BookNLP identity %s candidate attempt failed | name=%s attempt=%s/%s error=%s",
                    pass_name,
                    context.display_name,
                    attempt,
                    review_max_attempts,
                    last_error,
                )
                if attempt < review_max_attempts and review_retry_delay_seconds > 0:
                    time.sleep(review_retry_delay_seconds)
            return context, {"error": f"max_attempts_exhausted:{last_error}"}

        max_workers = min(4, max(1, len(contexts)))
        futures = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for context in contexts:
                futures.append(executor.submit(_review_one, context))
            results: List[Tuple[CandidateReviewContext, Dict[str, Any] | Any]] = []
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as exc:
                    LOGGER.exception("BookNLP identity %s candidate exception", pass_name)
                    results.append((CandidateReviewContext(display_name="<unknown>", current_bucket="", payload={}), {"error": f"review_exception:{exc.__class__.__name__}"}))

        results.sort(key=lambda item: item[0].display_name.lower())
        for context, response in results:
            if not isinstance(response, dict) or "error" in response:
                applied_decisions.append(
                    {
                        "display_name": context.display_name,
                        "status": "llm_error",
                        "pass": pass_name,
                        "response": response,
                    }
                )
                continue
            response["display_name"] = context.display_name
            response["review_pass"] = pass_name
            decisions_by_name[context.display_name] = response
            applied_decisions.append(
                {
                    "display_name": context.display_name,
                    "status": "reviewed",
                    "pass": pass_name,
                    "recommended_bucket": response.get("recommended_bucket"),
                    "merge_target_display_name": response.get("merge_target_display_name", ""),
                    "confidence": response.get("confidence", ""),
                    "notes": response.get("notes", []),
                }
            )

    collect_decisions(review_contexts, pass_name="broad_review", prompt_builder=_build_candidate_review_prompt)

    stable_rows = [dict(row) for row in cleaned.get("stable_named_characters") or []]
    reference_rows = [dict(row) for row in cleaned.get("reference_entities") or []]
    suppressed_rows = [dict(row) for row in cleaned.get("suppressed_clusters") or []]
    row_lookup: Dict[str, Tuple[str, Dict[str, Any]]] = {}
    for bucket, rows in (
        ("stable", stable_rows),
        ("reference", reference_rows),
        ("suppressed", suppressed_rows),
    ):
        for row in rows:
            row_lookup[str(row.get("display_name") or "")] = (bucket, row)

    merged_sources: set[str] = set()
    for display_name, decision in decisions_by_name.items():
        current = row_lookup.get(display_name)
        if current is None:
            continue
        bucket, row = current
        approved_aliases = []
        for alias in decision.get("approved_aliases") or []:
            cleaned_alias, _ = salvage_alias(str(alias), display_name)
            if cleaned_alias and cleaned_alias not in approved_aliases:
                approved_aliases.append(cleaned_alias)
        if approved_aliases:
            row["aliases"] = list(dict.fromkeys([*(row.get("aliases") or []), *approved_aliases]))
        add_flags = [str(item).strip() for item in decision.get("risk_flags_add") or [] if str(item).strip()]
        row["risk_flags"] = sorted(set(list(row.get("risk_flags") or []) + add_flags + ["llm_reviewed"]))
        row["llm_review"] = {
            "recommended_bucket": decision.get("recommended_bucket"),
            "confidence": decision.get("confidence"),
            "notes": list(decision.get("notes") or []),
            "merge_target_display_name": str(decision.get("merge_target_display_name") or "").strip(),
            "external_reference_used": bool(review_contexts and next((ctx.external_reference for ctx in review_contexts if ctx.display_name == display_name), None)),
        }
        target_name = str(decision.get("merge_target_display_name") or "").strip()
        confidence = str(decision.get("confidence") or "").strip().lower()
        if target_name and confidence == "high" and target_name in row_lookup and target_name != display_name:
            target_bucket, target_row = row_lookup[target_name]
            if normalize_name_key(display_name) in normalize_name_key(target_name) or normalize_name_key(target_name) in normalize_name_key(display_name) or set(normalize_name_key(display_name).split()) & set(normalize_name_key(target_name).split()):
                merged = _merge_payload_rows(row, target_row)
                target_row.clear()
                target_row.update(merged)
                row.clear()
                row["__merged_source__"] = True
                merged_sources.add(display_name)
                continue
        recommended_bucket = str(decision.get("recommended_bucket") or bucket).strip()
        if recommended_bucket != bucket and confidence in {"high", "medium"}:
            row["_move_to_bucket"] = recommended_bucket

    def _finalize_rows(rows: List[Dict[str, Any]], bucket_name: str) -> List[Dict[str, Any]]:
        finalized: List[Dict[str, Any]] = []
        for row in rows:
            if row.get("__merged_source__"):
                continue
            move_to = str(row.pop("_move_to_bucket", "") or "").strip()
            row.pop("__merged_source__", None)
            if move_to and move_to != bucket_name:
                continue
            finalized.append(row)
        finalized.sort(key=lambda item: (-int(item.get("mention_count", 0) or 0), str(item.get("display_name") or "").lower()))
        return finalized

    moved_rows: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for rows, bucket_name in ((stable_rows, "stable"), (reference_rows, "reference"), (suppressed_rows, "suppressed")):
        for row in rows:
            move_to = str(row.get("_move_to_bucket", "") or "").strip()
            if move_to and move_to != bucket_name and not row.get("__merged_source__"):
                cleaned_row = dict(row)
                cleaned_row.pop("_move_to_bucket", None)
                moved_rows[move_to].append(cleaned_row)
    cleaned["stable_named_characters"] = _finalize_rows(stable_rows, "stable") + moved_rows["stable"]
    cleaned["reference_entities"] = _finalize_rows(reference_rows, "reference") + moved_rows["reference"]
    cleaned["suppressed_clusters"] = _finalize_rows(suppressed_rows, "suppressed") + moved_rows["suppressed"]
    cleaned["stable_named_characters"].sort(key=lambda item: (-int(item.get("mention_count", 0) or 0), str(item.get("display_name") or "").lower()))
    cleaned["reference_entities"].sort(key=lambda item: (-int(item.get("mention_count", 0) or 0), str(item.get("display_name") or "").lower()))
    cleaned["suppressed_clusters"].sort(key=lambda item: (-int(item.get("mention_count", 0) or 0), str(item.get("display_name") or "").lower()))
    cleaned["alias_map"] = {
        str(row.get("display_name") or ""): list(row.get("aliases") or [])
        for row in cleaned["stable_named_characters"]
        if str(row.get("display_name") or "").strip()
    }
    diagnostics = dict(cleaned.get("diagnostics") or {})

    residual_names = _select_residual_cleanup_candidates(cleaned, max_candidates=max(6, min(16, int(max_review_candidates or 24))))
    residual_rows: List[Dict[str, Any]] = []
    for row in cleaned.get("stable_named_characters") or []:
        if str(row.get("display_name") or "") in residual_names:
            payload = dict(row)
            payload["_bucket"] = "stable"
            residual_rows.append(payload)
    residual_contexts = build_review_contexts(residual_rows)
    LOGGER.info(
        "BookNLP identity residual cleanup prepared | candidates=%s names=%s",
        len(residual_contexts),
        residual_names,
    )
    if residual_contexts:
        collect_decisions(residual_contexts, pass_name="residual_cleanup", prompt_builder=_build_residual_cleanup_prompt)

        stable_rows = [dict(row) for row in cleaned.get("stable_named_characters") or []]
        reference_rows = [dict(row) for row in cleaned.get("reference_entities") or []]
        suppressed_rows = [dict(row) for row in cleaned.get("suppressed_clusters") or []]
        row_lookup = {}
        for bucket, rows in (("stable", stable_rows), ("reference", reference_rows), ("suppressed", suppressed_rows)):
            for row in rows:
                row_lookup[str(row.get("display_name") or "")] = (bucket, row)
        merged_sources_pass2: set[str] = set()
        moved_rows = defaultdict(list)
        for display_name, decision in decisions_by_name.items():
            if str(decision.get("review_pass") or "") != "residual_cleanup":
                continue
            current = row_lookup.get(display_name)
            if current is None:
                continue
            bucket, row = current
            approved_aliases = []
            for alias in decision.get("approved_aliases") or []:
                cleaned_alias, _ = salvage_alias(str(alias), display_name)
                if cleaned_alias and cleaned_alias not in approved_aliases:
                    approved_aliases.append(cleaned_alias)
            if approved_aliases:
                row["aliases"] = list(dict.fromkeys([*(row.get("aliases") or []), *approved_aliases]))
            add_flags = [str(item).strip() for item in decision.get("risk_flags_add") or [] if str(item).strip()]
            row["risk_flags"] = sorted(set(list(row.get("risk_flags") or []) + add_flags + ["llm_reviewed_pass2"]))
            llm_review = dict(row.get("llm_review") or {})
            llm_review["pass2"] = {
                "recommended_bucket": decision.get("recommended_bucket"),
                "confidence": decision.get("confidence"),
                "notes": list(decision.get("notes") or []),
                "merge_target_display_name": str(decision.get("merge_target_display_name") or "").strip(),
            }
            row["llm_review"] = llm_review
            target_name = str(decision.get("merge_target_display_name") or "").strip()
            confidence = str(decision.get("confidence") or "").strip().lower()
            if target_name and confidence in {"high", "medium"} and target_name in row_lookup and target_name != display_name:
                _, target_row = row_lookup[target_name]
                merged = _merge_payload_rows(row, target_row)
                target_row.clear()
                target_row.update(merged)
                row.clear()
                row["__merged_source__"] = True
                merged_sources_pass2.add(display_name)
                continue
            recommended_bucket = str(decision.get("recommended_bucket") or bucket).strip()
            if recommended_bucket != bucket and confidence in {"high", "medium"}:
                row["_move_to_bucket"] = recommended_bucket

        for rows, bucket_name in ((stable_rows, "stable"), (reference_rows, "reference"), (suppressed_rows, "suppressed")):
            for row in rows:
                move_to = str(row.get("_move_to_bucket", "") or "").strip()
                if move_to and move_to != bucket_name and not row.get("__merged_source__"):
                    cleaned_row = dict(row)
                    cleaned_row.pop("_move_to_bucket", None)
                    moved_rows[move_to].append(cleaned_row)
        cleaned["stable_named_characters"] = _finalize_rows(stable_rows, "stable") + moved_rows["stable"]
        cleaned["reference_entities"] = _finalize_rows(reference_rows, "reference") + moved_rows["reference"]
        cleaned["suppressed_clusters"] = _finalize_rows(suppressed_rows, "suppressed") + moved_rows["suppressed"]
        cleaned["stable_named_characters"].sort(key=lambda item: (-int(item.get("mention_count", 0) or 0), str(item.get("display_name") or "").lower()))
        cleaned["reference_entities"].sort(key=lambda item: (-int(item.get("mention_count", 0) or 0), str(item.get("display_name") or "").lower()))
        cleaned["suppressed_clusters"].sort(key=lambda item: (-int(item.get("mention_count", 0) or 0), str(item.get("display_name") or "").lower()))
        cleaned["alias_map"] = {
            str(row.get("display_name") or ""): list(row.get("aliases") or [])
            for row in cleaned["stable_named_characters"]
            if str(row.get("display_name") or "").strip()
        }
        merged_sources |= merged_sources_pass2

    diagnostics["llm_review"] = {
        "enabled": True,
        "mode": str(llm_review_mode).strip(),
        "provider": llm.provider_name(),
        "model": llm.resolved_model_name(),
        "external_research_enabled": bool(enable_external_research),
        "reviewed_candidate_count": len(review_contexts),
        "residual_cleanup_candidate_count": len(residual_contexts),
        "residual_cleanup_candidates": residual_names,
        "applied_decisions": applied_decisions,
        "merged_sources": sorted(merged_sources),
    }
    cleaned["diagnostics"] = diagnostics
    cleaned["diagnostics"]["important_cast_coverage"] = important_character_coverage(cleaned)
    LOGGER.info(
        "BookNLP identity LLM review complete | stable=%s reference=%s suppressed=%s reviewed=%s residual=%s merged=%s",
        len(cleaned.get("stable_named_characters") or []),
        len(cleaned.get("reference_entities") or []),
        len(cleaned.get("suppressed_clusters") or []),
        len(review_contexts),
        len(residual_contexts),
        len(merged_sources),
    )
    return cleaned


def clean_booknlp_identity(
    input_json: str | Path,
    output_json: str | Path,
    report_md: str | Path,
    *,
    chapters: List[Dict[str, Any]] | None = None,
    book_title: str = "",
    llm_review_mode: str = "",
    enable_external_research: bool = False,
    max_review_candidates: int = 24,
    web_search_tool=None,
) -> Dict[str, Any]:
    input_path = Path(input_json)
    output_path = Path(output_json)
    report_path = Path(report_md)
    LOGGER.info("BookNLP identity cleanup start | input=%s output=%s", input_path, output_path)
    raw = json.loads(input_path.read_text(encoding="utf-8"))

    records = [build_cluster_record(entry) for entry in raw.get("stable_characters", [])]
    before_stable_count = len(records)
    before_alias_count = sum(len(record.aliases) for record in records)
    merged_records = merge_short_name_variants(merge_records(records))

    stable_named: List[Dict[str, Any]] = []
    reference_entities: List[Dict[str, Any]] = []
    suppressed_clusters: List[Dict[str, Any]] = []
    narrator_record: Optional[ClusterRecord] = None
    cleaned_alias_examples: List[Dict[str, str]] = []
    merged_clusters_report: List[Dict[str, Any]] = []

    for record in merged_records:
        aliases, removed_aliases = cleaned_aliases_for_record(record)
        for item in removed_aliases[:10]:
            cleaned_alias_examples.append(
                {
                    "cluster": record.display_name,
                    "alias": item["alias"],
                    "reason": item["reason"],
                }
            )

        if record.display_name == "[NARRATOR]":
            narrator_record = record
            continue

        if contains_mojibake(record.raw_display_name) and not aliases:
            record.risk_flags.add("encoding_artifact_only")

        if record.display_name.lower() in SINGLETON_SUPPRESS:
            record.risk_flags.add("suppressed_surface")

        kind = cluster_kind(record)
        payload = serialize_record(record, aliases)
        if len(set(record.merged_from_clusters)) > 1:
            merged_clusters_report.append(
                {
                    "display_name": payload["display_name"],
                    "merged_from_clusters": payload["merged_from_clusters"],
                }
            )

        if kind == "stable":
            stable_named.append(payload)
        elif kind == "reference":
            payload["category"] = "reference_entity"
            reference_entities.append(payload)
        else:
            suppressed_clusters.append(
                {
                    "display_name": payload["display_name"] or record.raw_display_name,
                    "aliases": payload["aliases"],
                    "mention_count": payload["mention_count"],
                    "quote_count": payload["quote_count"],
                    "cluster_ids": payload["cluster_ids"],
                    "risk_flags": payload["risk_flags"],
                    "suppression_reason": cluster_kind(record),
                    "merged_from_clusters": payload["merged_from_clusters"],
                }
            )

    stable_named.sort(key=lambda row: (-row["mention_count"], row["display_name"].lower()))
    reference_entities.sort(key=lambda row: (-row["mention_count"], row["display_name"].lower()))
    suppressed_clusters.sort(key=lambda row: (-row["mention_count"], row["display_name"].lower()))

    narrator_payload = derive_narrator_payload(narrator_record, stable_named) if narrator_record else None
    alias_map = {row["display_name"]: row["aliases"] for row in stable_named}

    cleaned = {
        "system": "booknlp_small_clean",
        "source_system": raw.get("system", "booknlp_small"),
        "stable_named_characters": stable_named,
        "narrator": narrator_payload,
        "reference_entities": reference_entities,
        "suppressed_clusters": suppressed_clusters,
        "alias_map": alias_map,
        "diagnostics": {
            "input_json": str(input_path),
            "before_stable_count": before_stable_count,
            "after_stable_named_count": len(stable_named),
            "reference_entity_count": len(reference_entities),
            "suppressed_cluster_count": len(suppressed_clusters),
            "before_alias_count": before_alias_count,
            "after_alias_count": sum(len(row["aliases"]) for row in stable_named),
            "merged_cluster_count": len(merged_clusters_report),
            "cleaned_alias_example_count": len(cleaned_alias_examples),
        },
    }

    coverage = important_character_coverage(cleaned)
    cleaned["diagnostics"]["important_cast_coverage"] = coverage

    if str(llm_review_mode or "").strip():
        try:
            cleaned = _apply_llm_identity_review(
                cleaned,
                chapters=chapters,
                book_title=book_title,
                llm_review_mode=llm_review_mode,
                enable_external_research=enable_external_research,
                max_review_candidates=max_review_candidates,
                web_search_tool=web_search_tool,
            )
            coverage = important_character_coverage(cleaned)
            cleaned["diagnostics"]["important_cast_coverage"] = coverage
        except Exception as exc:
            LOGGER.exception("BookNLP identity LLM review failed; keeping deterministic cleanup result")
            diagnostics = dict(cleaned.get("diagnostics") or {})
            diagnostics["llm_review"] = {
                "enabled": True,
                "mode": str(llm_review_mode).strip(),
                "provider": "",
                "model": "",
                "external_research_enabled": bool(enable_external_research),
                "reviewed_candidate_count": 0,
                "residual_cleanup_candidate_count": 0,
                "residual_cleanup_candidates": [],
                "applied_decisions": [],
                "merged_sources": [],
                "status": "failed_soft",
                "error": f"{exc.__class__.__name__}: {exc}",
            }
            cleaned["diagnostics"] = diagnostics

    output_path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    LOGGER.info(
        "BookNLP identity cleanup complete | stable=%s reference=%s suppressed=%s report=%s",
        len(cleaned.get("stable_named_characters") or []),
        len(cleaned.get("reference_entities") or []),
        len(cleaned.get("suppressed_clusters") or []),
        report_path,
    )

    final_stable_named = list(cleaned.get("stable_named_characters") or [])
    final_reference_entities = list(cleaned.get("reference_entities") or [])
    final_suppressed_clusters = list(cleaned.get("suppressed_clusters") or [])

    risky_clusters = [
        {
            "display_name": row["display_name"],
            "risk_flags": row.get("risk_flags", []),
            "mention_count": row.get("mention_count", 0),
        }
        for row in final_stable_named + final_reference_entities
        if row.get("risk_flags")
    ][:20]
    verdict = "usable" if any(item["name"] == "Feyre" and item["present"] for item in coverage) and len(final_stable_named) <= before_stable_count else "needs review"

    report_lines = [
        "# BookNLP Small Cleanup Report",
        "",
        "## Counts",
        "",
        markdown_table(
            ["metric", "value"],
            [
                {"metric": "before_stable_count", "value": before_stable_count},
                {"metric": "after_stable_named_count", "value": len(final_stable_named)},
                {"metric": "reference_entity_count", "value": len(final_reference_entities)},
                {"metric": "suppressed_cluster_count", "value": len(final_suppressed_clusters)},
                {"metric": "before_alias_count", "value": before_alias_count},
                {"metric": "after_alias_count", "value": sum(len(row["aliases"]) for row in final_stable_named)},
            ],
        ),
        "",
        "## LLM Review",
        "",
        markdown_table(
            ["metric", "value"],
            [
                {"metric": "enabled", "value": bool(str(llm_review_mode or "").strip())},
                {"metric": "mode", "value": (cleaned.get("diagnostics") or {}).get("llm_review", {}).get("mode", "")},
                {"metric": "provider", "value": (cleaned.get("diagnostics") or {}).get("llm_review", {}).get("provider", "")},
                {"metric": "model", "value": (cleaned.get("diagnostics") or {}).get("llm_review", {}).get("model", "")},
                {"metric": "reviewed_candidate_count", "value": (cleaned.get("diagnostics") or {}).get("llm_review", {}).get("reviewed_candidate_count", 0)},
                {"metric": "external_research_enabled", "value": (cleaned.get("diagnostics") or {}).get("llm_review", {}).get("external_research_enabled", False)},
            ],
        ),
        "",
        "## Merged Clusters",
        "",
        markdown_table(["display_name", "merged_from_clusters"], merged_clusters_report[:30] or [{"display_name": "none", "merged_from_clusters": []}]),
        "",
        "## Suppressed Clusters",
        "",
        markdown_table(["display_name", "mention_count", "suppression_reason", "risk_flags"], final_suppressed_clusters[:30] or [{"display_name": "none", "mention_count": 0, "suppression_reason": "", "risk_flags": []}]),
        "",
        "## Cleaned Alias Examples",
        "",
        markdown_table(["cluster", "alias", "reason"], cleaned_alias_examples[:40] or [{"cluster": "none", "alias": "", "reason": ""}]),
        "",
        "## Remaining Risky Clusters",
        "",
        markdown_table(["display_name", "mention_count", "risk_flags"], risky_clusters or [{"display_name": "none", "mention_count": 0, "risk_flags": []}]),
        "",
        "## Important Cast Coverage",
        "",
        markdown_table(["name", "present", "tier", "display_name", "aliases", "mention_count", "quote_count", "risk_flags", "merged_from_clusters"], coverage),
        "",
        "## Final Verdict",
        "",
        f"`{verdict}`",
    ]
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    return cleaned


