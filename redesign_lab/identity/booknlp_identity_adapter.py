from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ftfy import fix_text


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
    "â€",
    "â€Œ",
    "â€\u200c",
    "Iâ€",
    "I†™",
    "†¦",
    "أ¢â‚¬",
    "â‚¬",
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
BROKEN_QUOTE_RE = re.compile(r'[\"“”]|\.{2,}|[?!]["”]?')
NAME_TOKEN_RE = re.compile(r"^[A-Z][A-Za-z'’-]+$")


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


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\n", " ").replace("\t", " ")).strip()


def normalize_surface(text: str) -> str:
    fixed = fix_text(text or "")
    fixed = normalize_whitespace(fixed)
    fixed = fixed.strip(" \"'“”‘’.,;:!?-")
    return fixed


def contains_mojibake(text: str) -> bool:
    return any(pattern in (text or "") for pattern in MOJIBAKE_PATTERNS)


def strip_mojibake(text: str) -> str:
    cleaned = fix_text(text or "")
    for pattern in MOJIBAKE_PATTERNS:
        cleaned = cleaned.replace(pattern, " ")
    cleaned = cleaned.replace("—", " ").replace("–", " ")
    cleaned = normalize_whitespace(cleaned)
    tokens = []
    for token in cleaned.split():
        token = re.sub(r"^[^A-Za-z\[]+", "", token)
        token = re.sub(r"(?<=[A-Za-z]{2})[^A-Za-z'’-]+$", "", token)
        if token:
            tokens.append(token)
    cleaned = " ".join(tokens)
    cleaned = cleaned.strip(" \"'“”‘’.,;:!?-")
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


def clean_booknlp_identity(
    input_json: str | Path,
    output_json: str | Path,
    report_md: str | Path,
) -> Dict[str, Any]:
    input_path = Path(input_json)
    output_path = Path(output_json)
    report_path = Path(report_md)
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
    output_path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")

    risky_clusters = [
        {
            "display_name": row["display_name"],
            "risk_flags": row.get("risk_flags", []),
            "mention_count": row.get("mention_count", 0),
        }
        for row in stable_named + reference_entities
        if row.get("risk_flags")
    ][:20]
    verdict = "usable" if any(item["name"] == "Feyre" and item["present"] for item in coverage) and len(stable_named) < before_stable_count else "needs review"

    report_lines = [
        "# BookNLP Small Cleanup Report",
        "",
        "## Counts",
        "",
        markdown_table(
            ["metric", "value"],
            [
                {"metric": "before_stable_count", "value": before_stable_count},
                {"metric": "after_stable_named_count", "value": len(stable_named)},
                {"metric": "reference_entity_count", "value": len(reference_entities)},
                {"metric": "suppressed_cluster_count", "value": len(suppressed_clusters)},
                {"metric": "before_alias_count", "value": before_alias_count},
                {"metric": "after_alias_count", "value": sum(len(row["aliases"]) for row in stable_named)},
            ],
        ),
        "",
        "## Merged Clusters",
        "",
        markdown_table(["display_name", "merged_from_clusters"], merged_clusters_report[:30] or [{"display_name": "none", "merged_from_clusters": []}]),
        "",
        "## Suppressed Clusters",
        "",
        markdown_table(["display_name", "mention_count", "suppression_reason", "risk_flags"], suppressed_clusters[:30] or [{"display_name": "none", "mention_count": 0, "suppression_reason": "", "risk_flags": []}]),
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
