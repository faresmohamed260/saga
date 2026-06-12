from __future__ import annotations

import csv
import json
import re
import shutil
import time
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from ftfy import fix_text

from infrastructure.llm_client import LLMClient
from redesign_lab.identity.booknlp_identity_adapter import clean_booknlp_identity
from redesign_lab.identity.identity_provider import BookNLPCleanIdentityProvider
from services.series_processor import SeriesProcessor


IMPORTANT_CAST = [
    "Feyre",
    "Rhysand",
    "Rhys",
    "Tamlin",
    "Lucien",
    "Nesta",
    "Elain",
    "Morrigan",
    "Mor",
    "Amren",
    "Cassian",
    "Azriel",
    "Alis",
    "Amarantha",
    "Suriel",
    "Attor",
    "King of Hybern",
    "Jurian",
    "Vassa",
    "Koschei",
    "Emerie",
    "Gwyn",
    "Eris",
    "Helion",
]

BOOK_SLUG_OVERRIDES = {
    "a court of thorns and roses.epub": "acotar",
    "a court of mist and fury.epub": "acomaf",
    "a court of wings and ruin.epub": "acowar",
    "a court of frost and starlight.epub": "acofas",
    "a court of silver flames.epub": "acosf",
}

SHORT_NAME_MERGES = {
    "feyre": "feyre archeron",
    "rhys": "rhysand",
    "nesta": "nesta archeron",
    "elain": "elain archeron",
    "lucien": "lucien vanserra",
}

REFERENCE_ENTITY_HINTS = {
    "suriel",
    "attor",
    "king of hybern",
    "high lord",
    "my father",
    "my mother",
    "father",
    "mother",
    "hybern",
}


@contextmanager
def _booknlp_state_dict_compat():
    import torch

    original_torch_load = torch.load

    def patched_torch_load(*args, **kwargs):
        payload = original_torch_load(*args, **kwargs)
        if isinstance(payload, dict):
            payload = {
                key: value
                for key, value in payload.items()
                if key != "bert.embeddings.position_ids" and not key.endswith(".position_ids")
            }
        return payload

    torch.load = patched_torch_load
    try:
        yield
    finally:
        torch.load = original_torch_load


def _normalize_key(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip().lower())
    cleaned = re.sub(r"[^a-z0-9\s'-]", "", cleaned)
    return cleaned.strip()


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", _normalize_key(text))
    return slug.strip("_") or "entity"


def _clean_surface(text: str) -> str:
    fixed = fix_text(text or "")
    fixed = fixed.replace("\n", " ").replace("\t", " ")
    fixed = re.sub(r"\s+", " ", fixed).strip()
    fixed = fixed.strip("\"'â€œâ€‌â€کâ€™.,;:!?")
    fixed = re.sub(r"\s+[â€”-]\s+", "-", fixed)
    return fixed


def _looks_person_like_surface(text: str) -> bool:
    cleaned = _clean_surface(text)
    if not cleaned:
        return False
    lowered = cleaned.lower()
    if lowered in {"i", "me", "my", "myself", "you", "your", "yours"}:
        return False
    if re.search(r"(www\.|copyright|bloomsbury|chapter \d+$)", lowered):
        return False
    return any(ch.isalpha() for ch in cleaned)


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_booknlp_quotes(path: Path) -> Counter:
    counts: Counter = Counter()
    if not path.exists():
        return counts
    with path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            try:
                counts[int(row["char_id"])] += 1
            except Exception:
                continue
    return counts


def _load_booknlp_first_seen(path: Path) -> Dict[int, int]:
    first_seen: Dict[int, int] = {}
    if not path.exists():
        return first_seen
    with path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            try:
                coref = int(row["COREF"])
                start = int(row["start_token"])
            except Exception:
                continue
            if coref not in first_seen or start < first_seen[coref]:
                first_seen[coref] = start
    return first_seen


def _best_display_name(character: Dict[str, Any]) -> str:
    char_id = character["id"]
    mentions = character.get("mentions", {})
    proper = mentions.get("proper", [])
    common = mentions.get("common", [])
    pronoun = mentions.get("pronoun", [])
    if char_id == 0 and pronoun:
        return "[NARRATOR]"
    ranked_proper = sorted(
        [m for m in proper if _looks_person_like_surface(m.get("n", ""))],
        key=lambda m: (-m.get("c", 0), len(_clean_surface(m.get("n", "")))),
    )
    if ranked_proper:
        return _clean_surface(ranked_proper[0]["n"])
    ranked_common = sorted(
        [m for m in common if _looks_person_like_surface(m.get("n", ""))],
        key=lambda m: (-m.get("c", 0), len(_clean_surface(m.get("n", "")))),
    )
    if ranked_common:
        return _clean_surface(ranked_common[0]["n"])
    if pronoun:
        return _clean_surface(pronoun[0]["n"]) or f"cluster_{char_id}"
    return f"cluster_{char_id}"


def _risk_flags_for_booknlp_character(
    display_name: str,
    character: Dict[str, Any],
    all_display_names: Iterable[str],
) -> List[str]:
    flags: List[str] = []
    mentions = character.get("mentions", {})
    proper = [_clean_surface(m.get("n", "")) for m in mentions.get("proper", []) if _clean_surface(m.get("n", ""))]
    common = [_clean_surface(m.get("n", "")) for m in mentions.get("common", []) if _clean_surface(m.get("n", ""))]
    pronoun = [_clean_surface(m.get("n", "")) for m in mentions.get("pronoun", []) if _clean_surface(m.get("n", ""))]
    lowered = display_name.lower()
    if display_name == "[NARRATOR]":
        flags.append("narrator_cluster")
    if len(pronoun) and not proper and not common:
        flags.append("pronoun_only_cluster")
    if any("ï؟½" in p or "ؤپ" in p or "أ¢" in p for p in proper + common):
        flags.append("encoding_noise")
    if any(re.search(r"(www\.|bloomsbury|copyright|sarah j\. maas|josh)", p.lower()) for p in proper + common):
        flags.append("front_or_back_matter_noise")
    if lowered in {"prythian", "hybern"}:
        flags.append("location_like_name")
    if lowered in {"i", "[narrator]"}:
        flags.append("pov_cluster")
    if lowered.startswith("the ") and len(common) == 0 and len(proper) == 0:
        flags.append("generic_common_cluster")
    if display_name in {"Tam", "Rhys", "Mor"}:
        flags.append("possible_split_short_name")
    longer_competitor = any(
        other != display_name and lowered in other.lower().split() and len(other) > len(display_name)
        for other in all_display_names
    )
    if longer_competitor:
        flags.append("possible_split_cluster")
    return sorted(set(flags))


def book_slug_from_book(book: Dict[str, Any], index: int) -> str:
    title = str(book.get("title") or Path(book["path"]).name)
    normalized = title.strip().lower()
    if normalized in BOOK_SLUG_OVERRIDES:
        return BOOK_SLUG_OVERRIDES[normalized]
    parent_name = Path(book["path"]).parent.name.strip().lower()
    if parent_name and parent_name in BOOK_SLUG_OVERRIDES:
        return BOOK_SLUG_OVERRIDES[parent_name]
    return f"book_{index:02d}"


def book_output_dir(output_root: Path, book: Dict[str, Any], index: int) -> Path:
    return output_root / f"book_{index:02d}_{book_slug_from_book(book, index)}"


def _booknlp_basename(book: Dict[str, Any], index: int) -> str:
    return f"acotar_{book_slug_from_book(book, index)}"


def adapt_booknlp_directory(book_path: Path, system_name: str, runtime_seconds: Optional[float] = None) -> Dict[str, Any]:
    book_files = sorted(book_path.glob("*.book"))
    if not book_files:
        raise FileNotFoundError(f"No .book file found in {book_path}")
    book_json_path = book_files[0]
    base = book_json_path.stem
    book_json = _load_json(book_json_path)
    quote_counts = _load_booknlp_quotes(book_path / f"{base}.quotes")
    first_seen = _load_booknlp_first_seen(book_path / f"{base}.entities")

    raw_characters = book_json.get("characters", [])
    display_names = [_best_display_name(c) for c in raw_characters]
    stable_characters: List[Dict[str, Any]] = []
    alias_map: Dict[str, List[str]] = {}

    for character, display_name in zip(raw_characters, display_names):
        mentions = character.get("mentions", {})
        proper_mentions = [
            {"text": _clean_surface(m.get("n", "")), "count": m.get("c", 0)}
            for m in mentions.get("proper", [])
            if _clean_surface(m.get("n", ""))
        ]
        common_mentions = [
            {"text": _clean_surface(m.get("n", "")), "count": m.get("c", 0)}
            for m in mentions.get("common", [])
            if _clean_surface(m.get("n", ""))
        ]
        pronoun_mentions = [
            {"text": _clean_surface(m.get("n", "")), "count": m.get("c", 0)}
            for m in mentions.get("pronoun", [])
            if _clean_surface(m.get("n", ""))
        ]

        person_like_common = any(
            mention["text"].lower() in REFERENCE_ENTITY_HINTS
            or any(token in mention["text"].lower().split() for token in {"father", "mother", "sister", "brother", "queen", "king", "lord", "lady", "suriel", "attor"})
            for mention in common_mentions
        )
        if display_name != "[NARRATOR]" and not proper_mentions and not person_like_common:
            continue

        aliases: List[str] = []
        for mention_list in (proper_mentions, common_mentions):
            for mention in mention_list:
                text = mention["text"]
                if text and text not in aliases and len(aliases) < 12:
                    aliases.append(text)

        risk_flags = _risk_flags_for_booknlp_character(display_name, character, display_names)
        if display_name in aliases:
            aliases = [a for a in aliases if a != display_name]
            aliases.insert(0, display_name)

        stable_entry = {
            "display_name": display_name,
            "aliases": aliases,
            "proper_mentions": proper_mentions[:20],
            "common_mentions": common_mentions[:20],
            "pronoun_mentions": pronoun_mentions[:20],
            "mention_count": character.get("count", 0),
            "quote_count": quote_counts.get(character["id"], 0),
            "first_seen": first_seen.get(character["id"]),
            "risk_flags": risk_flags,
            "cluster_id": character["id"],
        }
        stable_characters.append(stable_entry)
        alias_map[display_name] = aliases

    stable_characters.sort(key=lambda row: (-row["mention_count"], row["display_name"]))
    return {
        "system": system_name,
        "stable_characters": stable_characters,
        "alias_map": alias_map,
        "diagnostics": {
            "runtime_seconds": runtime_seconds,
            "runtime_note": "BookNLP small on cleaned narrative-only input.",
            "total_clusters": len(raw_characters),
            "exported_clusters": len(stable_characters),
            "narrator_cluster_present": any(c["display_name"] == "[NARRATOR]" for c in stable_characters),
            "book_path": str(book_path),
        },
    }


def _build_booknlp_input_text(chapters: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for chapter in chapters:
        title = str(chapter.get("chapter_title") or "").strip()
        content = str(chapter.get("content") or "").strip()
        if title:
            parts.append(title)
        if content:
            parts.append(content)
        parts.append("")
    return "\n".join(parts).strip() + "\n"


def _copy_book1_seed_if_available(target_dir: Path) -> bool:
    source_root = Path("analysis_outputs/identity_model_shootout/acotar_book1_fair_v2")
    required = [
        source_root / "booknlp_small_identity_result.json",
        source_root / "booknlp_small_clean_identity_result.json",
        source_root / "booknlp_small_pipeline_identity.json",
        source_root / "booknlp_small_cleanup_report.md",
    ]
    if not all(path.exists() for path in required):
        return False
    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(required[0], target_dir / "booknlp_small_identity_result.json")
    shutil.copy2(required[1], target_dir / "booknlp_small_clean_identity_result.json")
    provider = BookNLPCleanIdentityProvider.from_path(required[1])
    pipeline_identity = provider.build_pipeline_identity()
    (target_dir / "booknlp_small_pipeline_identity.json").write_text(
        json.dumps(pipeline_identity, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    shutil.copy2(required[3], target_dir / "booknlp_cleanup_report.md")
    source_booknlp_dir = source_root / "booknlp_small"
    if source_booknlp_dir.exists():
        copied_dir = target_dir / "booknlp_small"
        if copied_dir.exists():
            shutil.rmtree(copied_dir)
        shutil.copytree(source_booknlp_dir, copied_dir)
    return True


def generate_book_identity_bundle(
    *,
    book: Dict[str, Any],
    book_index: int,
    output_root: str | Path,
    reuse_book1_seed: bool = True,
) -> Dict[str, Any]:
    root = Path(output_root)
    out_dir = book_output_dir(root, book, book_index)
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = book_slug_from_book(book, book_index)

    existing_pipeline_path = out_dir / "booknlp_small_pipeline_identity.json"
    existing_clean_path = out_dir / "booknlp_small_clean_identity_result.json"
    if existing_pipeline_path.exists() and existing_clean_path.exists() and not (reuse_book1_seed and book_index == 1):
        pipeline_identity = _load_json(existing_pipeline_path)
        return {
            "book_index": book_index,
            "book_slug": slug,
            "title": book.get("title") or Path(book["path"]).name,
            "output_dir": str(out_dir),
            "booknlp_runtime_seconds": _load_json(out_dir / "booknlp_small_identity_result.json").get("diagnostics", {}).get("runtime_seconds"),
            "pipeline_identity_path": str(existing_pipeline_path),
            "character_count": len(pipeline_identity.get("characters") or []),
            "alias_count": len(pipeline_identity.get("alias_index") or {}),
            "reference_entity_count": len(pipeline_identity.get("reference_entities") or []),
            "suppressed_cluster_count": len(pipeline_identity.get("suppressed_clusters") or []),
            "narrator": pipeline_identity.get("narrator") or {},
            "reused_seed": True,
        }

    if reuse_book1_seed and book_index == 1 and _copy_book1_seed_if_available(out_dir):
        pipeline_path = out_dir / "booknlp_small_pipeline_identity.json"
        pipeline = _load_json(pipeline_path)
        return {
            "book_index": book_index,
            "book_slug": slug,
            "title": book.get("title") or Path(book["path"]).name,
            "output_dir": str(out_dir),
            "booknlp_runtime_seconds": _load_json(out_dir / "booknlp_small_identity_result.json").get("diagnostics", {}).get("runtime_seconds"),
            "pipeline_identity_path": str(pipeline_path),
            "character_count": len(pipeline.get("characters") or []),
            "alias_count": len(pipeline.get("alias_index") or {}),
            "reference_entity_count": len(pipeline.get("reference_entities") or []),
            "suppressed_cluster_count": len(pipeline.get("suppressed_clusters") or []),
            "narrator": pipeline.get("narrator") or {},
            "reused_seed": True,
        }

    processor = SeriesProcessor(
        llm_client=LLMClient(mode=LLMClient.MODE_GPT_OSS, max_retries=1, base_delay=0.0, timeout=60)
    )
    chapters = processor.process([book])
    input_dir = out_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    input_text_path = input_dir / f"{slug}_booknlp_input_clean.txt"
    input_text_path.write_text(_build_booknlp_input_text(chapters), encoding="utf-8")

    booknlp_output_dir = out_dir / "booknlp_small"
    booknlp_output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    from booknlp.booknlp import BookNLP

    params = {"pipeline": "entity,quote,supersense,event,coref", "model": "small"}
    with _booknlp_state_dict_compat():
        model = BookNLP("en", params)
    model.process(str(input_text_path), str(booknlp_output_dir), _booknlp_basename(book, book_index))
    runtime_seconds = round(time.perf_counter() - started, 2)

    raw_identity = adapt_booknlp_directory(booknlp_output_dir, "booknlp_small", runtime_seconds)
    raw_identity_path = out_dir / "booknlp_small_identity_result.json"
    raw_identity_path.write_text(json.dumps(raw_identity, ensure_ascii=False, indent=2), encoding="utf-8")

    clean_identity_path = out_dir / "booknlp_small_clean_identity_result.json"
    cleanup_report_path = out_dir / "booknlp_cleanup_report.md"
    clean_booknlp_identity(
        input_json=raw_identity_path,
        output_json=clean_identity_path,
        report_md=cleanup_report_path,
    )

    provider = BookNLPCleanIdentityProvider.from_path(clean_identity_path)
    pipeline_identity = provider.build_pipeline_identity()
    pipeline_path = out_dir / "booknlp_small_pipeline_identity.json"
    pipeline_path.write_text(json.dumps(pipeline_identity, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "book_index": book_index,
        "book_slug": slug,
        "title": book.get("title") or Path(book["path"]).name,
        "output_dir": str(out_dir),
        "booknlp_runtime_seconds": runtime_seconds,
        "pipeline_identity_path": str(pipeline_path),
        "character_count": len(pipeline_identity.get("characters") or []),
        "alias_count": len(pipeline_identity.get("alias_index") or {}),
        "reference_entity_count": len(pipeline_identity.get("reference_entities") or []),
        "suppressed_cluster_count": len(pipeline_identity.get("suppressed_clusters") or []),
        "narrator": pipeline_identity.get("narrator") or {},
        "reused_seed": False,
    }


def _important_cast_status(pipeline_identity: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    characters = pipeline_identity.get("characters") or []
    alias_index = pipeline_identity.get("alias_index") or {}
    for target in IMPORTANT_CAST:
        normalized = _normalize_key(target)
        char_id = alias_index.get(normalized)
        matched = next((row for row in characters if row.get("id") == char_id), None)
        rows.append(
            {
                "target": target,
                "present": bool(matched),
                "display_name": matched.get("display_name") if matched else "",
                "mention_count": int(matched.get("mention_count", 0) or 0) if matched else 0,
                "quote_count": int(matched.get("quote_count", 0) or 0) if matched else 0,
                "risk_flags": list(matched.get("risk_flags") or []) if matched else [],
                "aliases": list(matched.get("aliases") or [])[:6] if matched else [],
            }
        )
    return rows


def _possible_split_identities(characters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    names = [str(row.get("display_name") or "") for row in characters]
    for row in characters:
        display_name = str(row.get("display_name") or "")
        lowered = _normalize_key(display_name)
        if not lowered or len(display_name.split()) > 2:
            continue
        competitors = [
            other
            for other in names
            if other != display_name and lowered and lowered in _normalize_key(other).split() and len(other) > len(display_name)
        ]
        if competitors or "possible_split_short_name" in (row.get("risk_flags") or []):
            rows.append(
                {
                    "display_name": display_name,
                    "competitors": competitors[:5],
                    "risk_flags": row.get("risk_flags") or [],
                }
            )
    return rows[:20]


def _possible_false_identities(characters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in characters:
        display_name = str(row.get("display_name") or "")
        risks = list(row.get("risk_flags") or [])
        if any(flag in risks for flag in {"encoding_noise", "front_or_back_matter_noise", "location_like_name", "generic_common_cluster"}):
            rows.append(
                {
                    "display_name": display_name,
                    "mention_count": row.get("mention_count", 0),
                    "aliases": row.get("aliases", [])[:6],
                    "risk_flags": risks,
                }
            )
    return rows[:20]


def _risky_aliases(characters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in characters:
        display_name = str(row.get("display_name") or "")
        for alias in row.get("aliases") or []:
            lowered = _normalize_key(alias)
            if not lowered:
                continue
            if len(alias.split()) > 5 or re.search(r"(cauldron|hybern|you|him|her)\b", lowered):
                rows.append({"display_name": display_name, "alias": alias})
    return rows[:30]


def _markdown_table(headers: List[str], rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "| " + " | ".join(headers) + " |\n| " + " | ".join(["---"] * len(headers)) + " |\n"
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        values = []
        for header in headers:
            value = row.get(header, "")
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def write_series_identity_audit(
    *,
    book_summaries: List[Dict[str, Any]],
    output_root: str | Path,
    audit_json_path: str | Path,
    audit_md_path: str | Path,
) -> Dict[str, Any]:
    root = Path(output_root)
    books_report: List[Dict[str, Any]] = []
    for summary in book_summaries:
        out_dir = Path(summary["output_dir"])
        pipeline = _load_json(out_dir / "booknlp_small_pipeline_identity.json")
        characters = pipeline.get("characters") or []
        books_report.append(
            {
                "book_index": summary["book_index"],
                "book_slug": summary["book_slug"],
                "title": summary["title"],
                "stable_character_count": len(characters),
                "alias_count": len(pipeline.get("alias_index") or {}),
                "reference_entity_count": len(pipeline.get("reference_entities") or []),
                "narrator": pipeline.get("narrator") or {},
                "suppressed_cluster_count": len(pipeline.get("suppressed_clusters") or []),
                "top_characters": characters[:20],
                "risky_aliases": _risky_aliases(characters),
                "possible_split_identities": _possible_split_identities(characters),
                "possible_false_identities": _possible_false_identities(characters),
                "important_cast": _important_cast_status(pipeline),
                "pipeline_identity_path": str(out_dir / "booknlp_small_pipeline_identity.json"),
            }
        )

    payload = {
        "series_id": "acotar",
        "books": books_report,
        "generated_at": time.time(),
    }
    Path(audit_json_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: List[str] = ["# ACOTAR Series Identity Audit", ""]
    for book in books_report:
        lines.extend(
            [
                f"## Book {book['book_index']:02d} `{book['book_slug']}`",
                "",
                f"- Title: `{book['title']}`",
                f"- Stable characters: `{book['stable_character_count']}`",
                f"- Alias count: `{book['alias_count']}`",
                f"- Reference entities: `{book['reference_entity_count']}`",
                f"- Narrator: `{book['narrator'].get('display_name')}`",
                f"- Suppressed clusters: `{book['suppressed_cluster_count']}`",
                "",
                "### Top Characters",
                "",
                _markdown_table(
                    ["display_name", "aliases", "mention_count", "quote_count", "risk_flags"],
                    [
                        {
                            "display_name": row.get("display_name"),
                            "aliases": (row.get("aliases") or [])[:6],
                            "mention_count": row.get("mention_count"),
                            "quote_count": row.get("quote_count"),
                            "risk_flags": row.get("risk_flags") or [],
                        }
                        for row in book["top_characters"][:20]
                    ],
                ),
                "",
                "### Important Cast Coverage",
                "",
                _markdown_table(
                    ["target", "present", "display_name", "mention_count", "quote_count", "risk_flags"],
                    book["important_cast"],
                ),
                "",
            ]
        )
    Path(audit_md_path).write_text("\n".join(lines), encoding="utf-8")
    return payload


def _merge_key_for_character(row: Dict[str, Any]) -> str:
    display_name = str(row.get("display_name") or "")
    normalized = _normalize_key(display_name)
    if normalized in SHORT_NAME_MERGES:
        return SHORT_NAME_MERGES[normalized]
    return normalized


def build_series_pipeline_identity(
    *,
    book_summaries: List[Dict[str, Any]],
    output_json: str | Path,
) -> Dict[str, Any]:
    merged: Dict[str, Dict[str, Any]] = {}
    alias_index: Dict[str, str] = {}
    reference_entities: Dict[str, Dict[str, Any]] = {}
    narrators: List[Dict[str, Any]] = []
    book_identity_paths: Dict[str, str] = {}
    uncertain_merges: List[Dict[str, Any]] = []

    for summary in book_summaries:
        out_dir = Path(summary["output_dir"])
        pipeline = _load_json(out_dir / "booknlp_small_pipeline_identity.json")
        book_slug = summary["book_slug"]
        book_index = int(summary["book_index"])
        book_identity_paths[book_slug] = str(out_dir / "booknlp_small_pipeline_identity.json")
        narrators.append(
            {
                "book_index": book_index,
                "book_slug": book_slug,
                **(pipeline.get("narrator") or {}),
            }
        )
        for ref in pipeline.get("reference_entities") or []:
            key = _normalize_key(ref.get("display_name", ""))
            if not key:
                continue
            entry = reference_entities.setdefault(
                key,
                {
                    "id": ref.get("id") or f"ref_{_slugify(ref.get('display_name') or key)}",
                    "display_name": ref.get("display_name"),
                    "aliases": [],
                    "category": ref.get("category") or "reference_entity",
                    "book_sources": [],
                    "risk_flags": [],
                },
            )
            for alias in ref.get("aliases") or []:
                if alias not in entry["aliases"]:
                    entry["aliases"].append(alias)
            entry["book_sources"].append(
                {
                    "book_index": book_index,
                    "book_slug": book_slug,
                    "source_character_id": ref.get("id"),
                    "mention_count": int(ref.get("mention_count", 0) or 0),
                    "quote_count": int(ref.get("quote_count", 0) or 0),
                }
            )
            for risk in ref.get("risk_flags") or []:
                if risk not in entry["risk_flags"]:
                    entry["risk_flags"].append(risk)

        for row in pipeline.get("characters") or []:
            merge_key = _merge_key_for_character(row)
            if not merge_key:
                continue
            display_name = str(row.get("display_name") or "")
            existing = merged.get(merge_key)
            if existing is None:
                merged[merge_key] = {
                    "id": f"char_{_slugify(merge_key)}",
                    "display_name": display_name,
                    "aliases": list(row.get("aliases") or []),
                    "book_sources": [
                        {
                            "book_index": book_index,
                            "book_slug": book_slug,
                            "source_character_id": row.get("id"),
                            "mention_count": int(row.get("mention_count", 0) or 0),
                            "quote_count": int(row.get("quote_count", 0) or 0),
                        }
                    ],
                    "risk_flags": list(row.get("risk_flags") or []),
                }
                continue
            current_display = str(existing.get("display_name") or "")
            if _normalize_key(display_name) != _normalize_key(current_display):
                if merge_key not in {_normalize_key(current_display), _normalize_key(display_name)} and display_name and current_display:
                    uncertain_merges.append(
                        {
                            "merge_key": merge_key,
                            "existing_display_name": current_display,
                            "incoming_display_name": display_name,
                            "book_slug": book_slug,
                        }
                    )
            if len(display_name.split()) > len(current_display.split()) or len(display_name) > len(current_display):
                existing["display_name"] = display_name
            for alias in row.get("aliases") or []:
                if alias not in existing["aliases"]:
                    existing["aliases"].append(alias)
            existing["book_sources"].append(
                {
                    "book_index": book_index,
                    "book_slug": book_slug,
                    "source_character_id": row.get("id"),
                    "mention_count": int(row.get("mention_count", 0) or 0),
                    "quote_count": int(row.get("quote_count", 0) or 0),
                }
            )
            for risk in row.get("risk_flags") or []:
                if risk not in existing["risk_flags"]:
                    existing["risk_flags"].append(risk)

    characters = sorted(merged.values(), key=lambda row: (-sum(src["mention_count"] for src in row["book_sources"]), row["display_name"].lower()))
    for row in characters:
        for alias in [row["display_name"], *(row.get("aliases") or [])]:
            key = _normalize_key(alias)
            if key:
                alias_index[key] = row["id"]

    payload = {
        "series_id": "acotar",
        "characters": characters,
        "alias_index": alias_index,
        "book_identity_paths": book_identity_paths,
        "reference_entities": sorted(reference_entities.values(), key=lambda row: row["display_name"].lower()),
        "narrators": narrators,
        "diagnostics": {
            "uncertain_merges": uncertain_merges,
            "book_count": len(book_summaries),
        },
    }
    Path(output_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


@dataclass
class SeriesBookNLPCleanIdentityProvider:
    input_json: Path

    @classmethod
    def from_path(cls, input_json: str | Path) -> "SeriesBookNLPCleanIdentityProvider":
        return cls(input_json=Path(input_json))

    def load_raw(self) -> Dict[str, Any]:
        return _load_json(self.input_json)

    def _book_slug_candidates(self, book: Dict[str, Any]) -> List[str]:
        title = str(book.get("title") or Path(book["path"]).name)
        path = str(book.get("path") or "")
        candidates = [
            book_slug_from_book(book, int(book.get("book_index", 1) or 1)),
            BOOK_SLUG_OVERRIDES.get(title.strip().lower(), ""),
            BOOK_SLUG_OVERRIDES.get(Path(path).name.strip().lower(), ""),
        ]
        seen: List[str] = []
        for candidate in candidates:
            if candidate and candidate not in seen:
                seen.append(candidate)
        return seen

    def resolve_book_identity_path(self, book: Dict[str, Any]) -> Optional[Path]:
        raw = self.load_raw()
        mapping = raw.get("book_identity_paths") or {}
        for slug in self._book_slug_candidates(book):
            if slug in mapping:
                return Path(mapping[slug])
        return None

    def build_pipeline_identity(self, book_inputs: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        raw = self.load_raw()
        selected_paths: List[Path] = []
        if book_inputs:
            for book in book_inputs:
                path = self.resolve_book_identity_path(book)
                if path and path not in selected_paths:
                    selected_paths.append(path)
        if not selected_paths:
            selected_paths = [Path(path) for path in (raw.get("book_identity_paths") or {}).values()]

        characters: Dict[str, Dict[str, Any]] = {}
        alias_index: Dict[str, str] = {}
        reference_entities: List[Dict[str, Any]] = []
        narrators: List[Dict[str, Any]] = []
        suppressed_clusters: List[Dict[str, Any]] = []

        for path in selected_paths:
            provider = BookNLPCleanIdentityProvider.from_path(path)
            payload = provider.build_pipeline_identity()
            narrators.append(payload.get("narrator") or {})
            suppressed_clusters.extend(payload.get("suppressed_clusters") or [])
            reference_entities.extend(payload.get("reference_entities") or [])
            for row in payload.get("characters") or []:
                row_id = str(row.get("id") or "")
                if row_id and row_id not in characters:
                    characters[row_id] = dict(row)
                    continue
                display_name = str(row.get("display_name") or "")
                match = next((key for key, value in characters.items() if _normalize_key(value.get("display_name", "")) == _normalize_key(display_name)), None)
                if not match:
                    characters[row_id or f"char_{_slugify(display_name)}"] = dict(row)

        ordered = sorted(characters.values(), key=lambda row: (-int(row.get("mention_count", 0) or 0), str(row.get("display_name") or "").lower()))
        for row in ordered:
            for alias in row.get("aliases") or []:
                key = _normalize_key(alias)
                if key:
                    alias_index[key] = row["id"]

        narrator = narrators[0] if narrators else {"id": "narrator_0", "display_name": "[NARRATOR]"}
        return {
            "provider": "booknlp_clean_series",
            "source_file": str(self.input_json),
            "characters": ordered,
            "narrator": narrator,
            "reference_entities": reference_entities,
            "alias_index": alias_index,
            "suppressed_clusters": suppressed_clusters,
            "diagnostics": {"book_identity_paths": [str(path) for path in selected_paths]},
        }

    def build_identity_result_compat(self, book_inputs: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        payload = self.build_pipeline_identity(book_inputs=book_inputs)
        alias_map = {row["display_name"]: list(row.get("aliases") or []) for row in payload.get("characters") or []}
        rejected = [
            str(row.get("display_name") or "").strip()
            for row in payload.get("suppressed_clusters") or []
            if str(row.get("display_name") or "").strip()
        ]
        return {
            "alias_map": alias_map,
            "rejected_non_characters": sorted(set(rejected), key=str.lower),
            "decisions": [],
            "alias_history": [],
            "identity_strategy": "booknlp_small_clean_series",
            "identity_provider": "booknlp_clean",
            "provider_locked": True,
            "provider_characters": payload["characters"],
            "provider_alias_index": payload["alias_index"],
            "unresolved_identity_candidates": [],
            "narrator": payload["narrator"],
            "reference_entities": payload["reference_entities"],
        }
