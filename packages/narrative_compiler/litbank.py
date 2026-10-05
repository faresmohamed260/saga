"""LitBank TSV adapter for reproducible V3 identity qualification.

This mirrors the frozen TypeScript converter's newline/token/span semantics but
uses Python code-point offsets natively. LitBank remains secondary public gold;
it is not the product-promotion corpus.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from .benchmark import GoldIdentityDocument, GoldIdentityMention
from .fingerprint import config_fingerprint, sha256_text
from .ir import EntityType, Mention, SourceSpan
from .source import NormalizedSection, NormalizedSource


LITBANK_COMMIT = "3e50db0ffc033d7ccbb94f4d88f6b99210328ed8"


@dataclass(frozen=True, slots=True)
class LitBankDocument:
    source: NormalizedSource
    gold: GoldIdentityDocument


@dataclass(frozen=True, slots=True)
class _RawMention:
    mention_id: str
    start_line: int
    start_token: int
    end_line: int
    end_token: int
    annotated_surface: str
    entity_class: str
    mention_class: str


def _normalize_newlines(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def _parse_annotations(annotation: str) -> tuple[list[_RawMention], dict[str, str]]:
    mentions: dict[str, _RawMention] = {}
    coref: dict[str, str] = {}
    for raw_line in _normalize_newlines(annotation).split("\n"):
        if not raw_line.strip():
            continue
        values = raw_line.split("\t")
        if values[0] == "MENTION":
            if len(values) < 9:
                raise ValueError(f"invalid_litbank_mention:{raw_line}")
            _, mention_id, start_line, start_token, end_line, end_token, surface, entity_class, mention_class = values[:9]
            mentions[mention_id] = _RawMention(
                mention_id=mention_id,
                start_line=int(start_line),
                start_token=int(start_token),
                end_line=int(end_line),
                end_token=int(end_token),
                annotated_surface=surface,
                entity_class=entity_class,
                mention_class=mention_class,
            )
        elif values[0] == "COREF":
            if len(values) < 3 or not values[1] or not values[2]:
                raise ValueError(f"invalid_litbank_coref:{raw_line}")
            coref[values[1]] = values[2]
    return list(mentions.values()), coref


def _mention_kind(value: str) -> str:
    mapping = {"PROP": "proper_name", "NOM": "nominal", "PRON": "pronoun"}
    if value not in mapping:
        raise ValueError(f"unsupported_litbank_mention_class:{value}")
    return mapping[value]


def _line_starts(text: str) -> list[int]:
    starts = [0]
    for index, char in enumerate(text):
        if char == "\n":
            starts.append(index + 1)
    return starts


def _token_spans(line: str) -> list[tuple[int, int]]:
    return [(match.start(), match.end()) for match in re.finditer(r"\S+", line, re.UNICODE)]


def _locate(text: str, raw: _RawMention) -> tuple[int, int, str]:
    lines = text.split("\n")
    starts = _line_starts(text)
    try:
        start_line_text = lines[raw.start_line]
        end_line_text = lines[raw.end_line]
        start_line_offset = starts[raw.start_line]
        end_line_offset = starts[raw.end_line]
        start_token = _token_spans(start_line_text)[raw.start_token]
        end_token = _token_spans(end_line_text)[raw.end_token]
    except IndexError as exc:
        raise ValueError(f"litbank_span_out_of_range:{raw.mention_id}") from exc

    start = start_line_offset + start_token[0]
    end = end_line_offset + end_token[1]
    surface = text[start:end]
    if _collapse_whitespace(surface) != _collapse_whitespace(raw.annotated_surface):
        raise ValueError(
            f"litbank_surface_mismatch:{raw.mention_id}:{raw.annotated_surface!r}:{surface!r}"
        )
    return start, end, surface


def convert_litbank_tsv_document(*, document_id: str, text: str, annotation: str) -> LitBankDocument:
    normalized_text = _normalize_newlines(text)
    raw_mentions, coref = _parse_annotations(annotation)
    gold_mentions: list[GoldIdentityMention] = []

    for raw in raw_mentions:
        start, end, surface = _locate(normalized_text, raw)
        entity_type = "person" if raw.entity_class == "PER" else "non_person"
        gold_mentions.append(
            GoldIdentityMention(
                mention_id=f"{document_id}:{raw.mention_id}",
                surface_text=surface,
                start_offset=start,
                end_offset=end,
                mention_kind=_mention_kind(raw.mention_class),
                entity_type=entity_type,
                gold_character_id=coref.get(raw.mention_id) if entity_type == "person" else None,
            )
        )

    gold_mentions.sort(key=lambda item: (item.start_offset, item.end_offset, item.mention_id))
    source_sha = sha256_text(normalized_text)
    section = NormalizedSection(
        stable_key=f"litbank:{document_id}",
        ordinal=0,
        section_kind="document",
        title=document_id,
        source_locator=f"litbank:{document_id}",
        span=SourceSpan(0, len(normalized_text)),
        normalized_text=normalized_text,
    )
    source = NormalizedSource(
        normalization_version="litbank-tsv-adapter-v1",
        config_fingerprint=config_fingerprint({"dataset": "dbamman/litbank", "commit": LITBANK_COMMIT}),
        normalized_sha256=source_sha,
        source_fingerprint=source_sha,
        normalized_text=normalized_text,
        sections=(section,),
    )
    return LitBankDocument(
        source=source,
        gold=GoldIdentityDocument(
            document_id=document_id,
            text=normalized_text,
            mentions=tuple(gold_mentions),
        ),
    )


def oracle_person_mentions(document: LitBankDocument) -> tuple[Mention, ...]:
    """Create source-bound oracle person mentions to isolate linker behavior."""

    result = []
    for gold in document.gold.mentions:
        if gold.entity_type != "person":
            continue
        result.append(
            Mention.create(
                source_fingerprint=document.source.source_fingerprint,
                source_unit_key=document.source.sections[0].stable_key,
                span=SourceSpan(gold.start_offset, gold.end_offset),
                entity_type=EntityType.CHARACTER,
                text=gold.surface_text,
                attributes={"gold_mention_kind": gold.mention_kind},
            )
        )
    return tuple(result)
