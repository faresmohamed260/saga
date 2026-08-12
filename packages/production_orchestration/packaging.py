"""Provider-neutral EPUB and manifest packaging."""

from __future__ import annotations

import hashlib
import io
import time
import zipfile
from datetime import datetime, timezone
from html import escape
from typing import Protocol

from pydantic import BaseModel, Field

from packages.production_orchestration.contracts import (
    ArtifactReference,
    DeliverableManifestArtifact,
    OrchestrationRequest,
    StageOutcomeArtifact,
)


class PackageChapter(BaseModel):
    chapter_index: int
    title: str
    prose: str


class PackageSourceBundle(BaseModel):
    story_id: str
    title: str
    language: str = "en"
    modified_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    chapters: list[PackageChapter] = Field(default_factory=list)
    artifact_refs: list[ArtifactReference] = Field(default_factory=list)
    provenance: dict = Field(default_factory=dict)


class DeliverableSource(Protocol):
    def collect(self, *, request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> PackageSourceBundle: ...


class DeliverableSink(Protocol):
    def store_epub(self, *, request: OrchestrationRequest, filename: str, data: bytes) -> ArtifactReference: ...

    def store_manifest(self, *, request: OrchestrationRequest, filename: str, payload: dict) -> ArtifactReference: ...


class VersionedDeliverablePackager:
    def __init__(self, *, source: DeliverableSource, sink: DeliverableSink) -> None:
        self.source = source
        self.sink = sink

    def package(self, *, request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> DeliverableManifestArtifact:
        bundle = self.source.collect(request=request, outcomes=outcomes)
        if not bundle.chapters:
            raise ValueError(f"Story '{bundle.story_id}' has no accepted chapters to package.")
        slug = _slug(bundle.title) or bundle.story_id
        run_slug = _slug(request.run_id)
        epub = build_epub(bundle)
        resolved_request = request.model_copy(update={"story_id": bundle.story_id})
        epub_ref = self.sink.store_epub(request=resolved_request, filename=f"{slug}-{run_slug}-v1.epub", data=epub)
        artifacts = [*bundle.artifact_refs, epub_ref]
        manifest = DeliverableManifestArtifact(
            manifest_id=_stable_id("deliverable-manifest", request.run_id, bundle.story_id, 1),
            version=1,
            run_id=request.run_id,
            series_id=request.series_id,
            story_id=bundle.story_id,
            title=bundle.title,
            created_at=int(time.time()),
            artifacts=artifacts,
            stage_lineage=[outcomes[name] for name in outcomes],
            provenance={**bundle.provenance, "project_id": request.project_id},
            metadata={
                "project_id": request.project_id,
                "chapter_count": len(bundle.chapters),
                "epub_sha256": hashlib.sha256(epub).hexdigest(),
            },
        )
        manifest_ref = self.sink.store_manifest(
            request=resolved_request,
            filename=f"{slug}-{run_slug}-v1-manifest.json",
            payload=manifest.model_dump(),
        )
        manifest.metadata["manifest_reference"] = manifest_ref.model_copy(update={"byte_length": 0, "sha256": ""}).model_dump()
        self.sink.store_manifest(
            request=resolved_request,
            filename=f"{slug}-{run_slug}-v1-manifest.json",
            payload=manifest.model_dump(),
        )
        return manifest


def build_epub(bundle: PackageSourceBundle) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", _container_xml())
        chapter_names = []
        for chapter in sorted(bundle.chapters, key=lambda item: item.chapter_index):
            name = f"chapter-{chapter.chapter_index:03d}.xhtml"
            chapter_names.append((name, chapter))
            archive.writestr(f"OEBPS/{name}", _chapter_xhtml(chapter, bundle.language), compress_type=zipfile.ZIP_DEFLATED)
        archive.writestr("OEBPS/nav.xhtml", _nav_xhtml(bundle, chapter_names), compress_type=zipfile.ZIP_DEFLATED)
        archive.writestr("OEBPS/content.opf", _content_opf(bundle, chapter_names), compress_type=zipfile.ZIP_DEFLATED)
    return output.getvalue()


def _container_xml() -> str:
    return '<?xml version="1.0" encoding="UTF-8"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'


def _chapter_xhtml(chapter: PackageChapter, language: str) -> str:
    paragraphs = "".join(f"<p>{escape(item.strip())}</p>" for item in chapter.prose.split("\n\n") if item.strip())
    return f'<?xml version="1.0" encoding="UTF-8"?><html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{escape(language)}"><head><title>{escape(chapter.title)}</title></head><body><h1>{escape(chapter.title)}</h1>{paragraphs}</body></html>'


def _nav_xhtml(bundle: PackageSourceBundle, chapters: list[tuple[str, PackageChapter]]) -> str:
    links = "".join(f'<li><a href="{name}">{escape(chapter.title)}</a></li>' for name, chapter in chapters)
    return f'<?xml version="1.0" encoding="UTF-8"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>{escape(bundle.title)}</title></head><body><nav epub:type="toc"><h1>Contents</h1><ol>{links}</ol></nav></body></html>'


def _content_opf(bundle: PackageSourceBundle, chapters: list[tuple[str, PackageChapter]]) -> str:
    manifest = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>']
    spine = []
    for index, (name, _) in enumerate(chapters, start=1):
        manifest.append(f'<item id="chapter-{index}" href="{name}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="chapter-{index}"/>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id">'
        f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="book-id">{escape(bundle.story_id)}</dc:identifier><dc:title>{escape(bundle.title)}</dc:title><dc:language>{escape(bundle.language)}</dc:language><meta property="dcterms:modified">{escape(bundle.modified_at)}</meta></metadata>'
        f'<manifest>{"".join(manifest)}</manifest><spine>{"".join(spine)}</spine></package>'
    )


def _slug(value: str) -> str:
    return "-".join("".join(char.lower() if char.isalnum() else " " for char in value).split())[:80]


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256(":".join(str(item) for item in parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"
