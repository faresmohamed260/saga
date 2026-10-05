"""Adapter for the existing v2 normalized-source contract.

V3 does not invent a second source-normalization truth. It consumes the exact
normalization result already produced by services/analysis-worker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .ir import SourceSpan


_ALLOWED_SECTION_KINDS = {"document", "chapter", "section"}


@dataclass(frozen=True, slots=True)
class NormalizedSection:
    stable_key: str
    ordinal: int
    section_kind: str
    title: str | None
    source_locator: str
    span: SourceSpan
    normalized_text: str

    def __post_init__(self) -> None:
        if not self.stable_key or not self.source_locator:
            raise ValueError("stable_key and source_locator are required")
        if self.ordinal < 0:
            raise ValueError("ordinal must be >= 0")
        if self.section_kind not in _ALLOWED_SECTION_KINDS:
            raise ValueError(f"unsupported section_kind: {self.section_kind}")


@dataclass(frozen=True, slots=True)
class NormalizedSource:
    normalization_version: str
    config_fingerprint: str
    normalized_sha256: str
    source_fingerprint: str
    normalized_text: str
    sections: tuple[NormalizedSection, ...]

    def __post_init__(self) -> None:
        if not all(
            (
                self.normalization_version,
                self.config_fingerprint,
                self.normalized_sha256,
                self.source_fingerprint,
            )
        ):
            raise ValueError("normalization metadata must be non-empty")
        for expected_ordinal, section in enumerate(self.sections):
            if section.ordinal != expected_ordinal:
                raise ValueError("section ordinals must be contiguous and source ordered")
            if section.span.end_offset > len(self.normalized_text):
                raise ValueError("section span exceeds normalized text")
            if self.normalized_text[section.span.start_offset : section.span.end_offset] != section.normalized_text:
                raise ValueError(f"section text/offset mismatch: {section.stable_key}")

    @classmethod
    def from_v2_payload(cls, payload: Mapping[str, Any]) -> "NormalizedSource":
        """Load the exact TypeScript `NormalizationResult` JSON shape."""

        required = {
            "normalizationVersion",
            "configFingerprint",
            "normalizedSha256",
            "outputFingerprint",
            "normalizedText",
            "sections",
        }
        missing = sorted(required.difference(payload))
        if missing:
            raise ValueError(f"normalization payload missing fields: {', '.join(missing)}")

        raw_sections = payload["sections"]
        if not isinstance(raw_sections, Sequence) or isinstance(raw_sections, (str, bytes, bytearray)):
            raise ValueError("sections must be a sequence")

        sections = []
        for raw in raw_sections:
            if not isinstance(raw, Mapping):
                raise ValueError("each section must be an object")
            sections.append(
                NormalizedSection(
                    stable_key=str(raw["stable_key"]),
                    ordinal=int(raw["ordinal"]),
                    section_kind=str(raw["section_kind"]),
                    title=None if raw.get("title") is None else str(raw["title"]),
                    source_locator=str(raw["source_locator"]),
                    span=SourceSpan(int(raw["start_offset"]), int(raw["end_offset"])),
                    normalized_text=str(raw["normalized_text"]),
                )
            )

        return cls(
            normalization_version=str(payload["normalizationVersion"]),
            config_fingerprint=str(payload["configFingerprint"]),
            normalized_sha256=str(payload["normalizedSha256"]),
            source_fingerprint=str(payload["outputFingerprint"]),
            normalized_text=str(payload["normalizedText"]),
            sections=tuple(sections),
        )

    def section_for_offset(self, offset: int) -> NormalizedSection | None:
        if offset < 0 or offset > len(self.normalized_text):
            raise ValueError("offset outside normalized text")
        for section in self.sections:
            if section.span.start_offset <= offset < section.span.end_offset:
                return section
        return None
