from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from ebooklib import epub
from saga.services.artifact_storage_service import ArtifactStorageService


class GeneratedStoryEpubService:
    def __init__(self, export_root: str | Path | None = None, *, artifact_storage: ArtifactStorageService | None = None) -> None:
        self.artifact_storage = artifact_storage or ArtifactStorageService()
        self.export_root = Path(export_root) if export_root is not None else self.artifact_storage.generated_story_exports_root()
        self.export_root.mkdir(parents=True, exist_ok=True)

    def export_story(self, story: dict[str, Any]) -> Path:
        title = str(story.get("title") or "Generated Story").strip() or "Generated Story"
        story_id = str(story.get("id") or uuid4().hex).strip()
        book = epub.EpubBook()
        book.set_identifier(story_id)
        book.set_title(title)
        book.set_language("en")
        book.add_author("S.A.G.A. Decoder")

        metadata = story.get("metadata") if isinstance(story.get("metadata"), dict) else {}
        source_ref = str(metadata.get("book_ref") or "").strip()
        story_mode = str(story.get("story_mode") or "").strip()
        canon_position = str(story.get("canon_position") or "").strip()
        user_prompt = str(story.get("user_prompt") or "").strip()

        if source_ref:
            book.add_metadata("DC", "source", source_ref)
        if story_mode:
            book.add_metadata("DC", "subject", story_mode)
        if canon_position:
            book.add_metadata("DC", "coverage", canon_position)
        if user_prompt:
            book.add_metadata("DC", "description", user_prompt[:2000])

        intro = epub.EpubHtml(title="Title Page", file_name="title.xhtml", lang="en")
        intro.content = f"""
        <html>
          <head><title>{title}</title></head>
          <body>
            <h1>{title}</h1>
            <p><strong>Mode:</strong> {story_mode or "n/a"}</p>
            <p><strong>Canon position:</strong> {canon_position or "n/a"}</p>
            <p><strong>Prompt:</strong> {user_prompt or "n/a"}</p>
          </body>
        </html>
        """
        book.add_item(intro)

        spine = [intro]
        toc: list[Any] = [intro]

        for chapter in story.get("chapters") or []:
            chapter_number = int(chapter.get("chapter_number") or 0)
            chapter_title = str(chapter.get("chapter_title") or f"Chapter {chapter_number}").strip() or f"Chapter {chapter_number}"
            prose_text = str(chapter.get("prose_text") or "").strip()
            paragraphs = "".join(f"<p>{self._escape_html(line)}</p>" for line in prose_text.split("\n") if line.strip())
            chapter_doc = epub.EpubHtml(
                title=chapter_title,
                file_name=f"chapter_{chapter_number:02d}.xhtml",
                lang="en",
            )
            chapter_doc.content = f"""
            <html>
              <head><title>{chapter_title}</title></head>
              <body>
                <h1>{chapter_title}</h1>
                {paragraphs}
              </body>
            </html>
            """
            book.add_item(chapter_doc)
            spine.append(chapter_doc)
            toc.append(chapter_doc)

        book.toc = tuple(toc)
        book.spine = ["nav", *spine]
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        output_path = (
            self.artifact_storage.generated_story_epub_path(title=title, story_id=story_id)
            if self.export_root == self.artifact_storage.generated_story_exports_root()
            else self.export_root / f"{self._slugify(title)}_{story_id[:8]}.epub"
        )
        epub.write_epub(str(output_path), book)
        return output_path

    def _slugify(self, value: str) -> str:
        cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value or "").strip())
        while "--" in cleaned:
            cleaned = cleaned.replace("--", "-")
        return cleaned.strip("-") or "generated-story"

    def _escape_html(self, text: str) -> str:
        return (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
