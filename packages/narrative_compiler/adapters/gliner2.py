"""Lazy local GLiNER2.5 semantic-lexer challenger.

This adapter is optional qualification code. Importing this module does not
import torch or GLiNER2 and normal CI never downloads model weights.
"""

from __future__ import annotations

from typing import Any, Mapping

from ..fingerprint import artifact_fingerprint, config_fingerprint
from ..ir import EntityType, Mention, ModelDescriptor, SourceSpan, StageRunDescriptor
from ..model_manifest import GLINER25_BASE_V1
from ..source import NormalizedSource
from ..stages import LexerResult


_DEFAULT_LABELS: Mapping[str, EntityType] = {
    "person": EntityType.CHARACTER,
    "location": EntityType.LOCATION,
    "object": EntityType.OBJECT,
    "organization": EntityType.ORGANIZATION,
    "faction": EntityType.FACTION,
    "creature": EntityType.CREATURE,
}


class GLiNER25SemanticLexer:
    stage_name = "semantic-lexer-gliner2.5"
    stage_version = "v3.0.0"

    def __init__(
        self,
        *,
        model_id: str = GLINER25_BASE_V1.model_id,
        revision: str = GLINER25_BASE_V1.revision,
        model_path: str | None = None,
        threshold: float = 0.5,
        chunk_size: int = 384,
        chunk_overlap: int = 64,
        labels: Mapping[str, EntityType] | None = None,
        device: str = "cpu",
        model: Any | None = None,
    ) -> None:
        if not revision:
            raise ValueError("an exact model revision is required for qualification")
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        if chunk_size < 32 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("invalid long-document chunk configuration")
        self.model_id = model_id
        self.revision = revision
        self.model_path = model_path
        self.threshold = threshold
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.labels = dict(labels or _DEFAULT_LABELS)
        self.device = device
        self._model = model

    @property
    def descriptor(self) -> ModelDescriptor:
        return ModelDescriptor(
            model_id=self.model_id,
            revision=self.revision,
            adapter="gliner2.AutoExtractor",
            license_id=GLINER25_BASE_V1.license_id if self.model_id == GLINER25_BASE_V1.model_id else None,
        )

    def _load_model(self) -> Any:
        if self._model is None:
            try:
                from gliner2 import AutoExtractor
            except ImportError as exc:  # pragma: no cover - heavyweight optional path
                raise RuntimeError(
                    "GLiNER2 qualification dependency is intentionally outside normal CI; install the dedicated qualification requirements"
                ) from exc
            load_target = self.model_path or self.model_id
            load_kwargs = {"map_location": self.device}
            if self.model_path is None:
                load_kwargs["revision"] = self.revision
            self._model = AutoExtractor.from_pretrained(load_target, **load_kwargs)
        return self._model

    def analyze(self, source: NormalizedSource) -> LexerResult:
        model = self._load_model()
        label_names = tuple(self.labels)
        mentions: dict[tuple[int, int, str], Mention] = {}

        for section in source.sections:
            result = model.extract_entities_long(
                section.normalized_text,
                list(label_names),
                threshold=self.threshold,
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                include_spans=True,
                include_confidence=True,
            )
            entities = result.get("entities", {})
            for label, values in entities.items():
                entity_type = self.labels.get(str(label))
                if entity_type is None:
                    continue
                for raw in values:
                    if not isinstance(raw, Mapping):
                        continue
                    local_start = int(raw["start"])
                    local_end = int(raw["end"])
                    start = section.span.start_offset + local_start
                    end = section.span.start_offset + local_end
                    text = str(raw["text"])
                    if source.normalized_text[start:end] != text:
                        raise ValueError("GLiNER2 returned a span that does not match normalized source text")
                    confidence = float(raw["confidence"]) if raw.get("confidence") is not None else None
                    mention = Mention.create(
                        source_fingerprint=source.source_fingerprint,
                        source_unit_key=section.stable_key,
                        span=SourceSpan(start, end),
                        entity_type=entity_type,
                        text=text,
                        confidence=confidence,
                        attributes={"lexer_label": str(label)},
                    )
                    key = (start, end, entity_type.value)
                    previous = mentions.get(key)
                    if previous is None or (mention.confidence or 0.0) > (previous.confidence or 0.0):
                        mentions[key] = mention

        config = {
            "labels": {key: value.value for key, value in sorted(self.labels.items())},
            "threshold": self.threshold,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "device": self.device,
        }
        model_payload = {
            "model_id": self.model_id,
            "revision": self.revision,
            "adapter": self.descriptor.adapter,
        }
        artifact = artifact_fingerprint(
            source_fingerprint=source.source_fingerprint,
            stage_name=self.stage_name,
            stage_version=self.stage_version,
            config=config,
            model=model_payload,
        )
        return LexerResult(
            run=StageRunDescriptor(
                stage_name=self.stage_name,
                stage_version=self.stage_version,
                config_fingerprint=config_fingerprint(config),
                artifact_fingerprint=artifact,
                model=self.descriptor,
            ),
            mentions=tuple(
                sorted(
                    mentions.values(),
                    key=lambda item: (
                        item.evidence.span.start_offset,
                        item.evidence.span.end_offset,
                        item.entity_type.value,
                    ),
                )
            ),
        )
