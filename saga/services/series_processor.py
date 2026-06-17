"""Unified series ingestion entry point for EPUB and PDF books."""

import os
from typing import Dict, List, Optional

from saga.providers.llm_client import LLMClient
from saga.services.epub_processor import EPUBProcessor
from saga.services.pdf_processor import PDFProcessor


class SeriesProcessor:
    """
    Unified entry point for processing one or more books in a series.

    Input:
        [
            {"path": "...", "type": "epub"},
            {"path": "...", "type": "pdf"}
        ]

    Output:
        [
            {
                "book_index": 1,
                "chapter_index": 1,
                "chapter_title": "...",
                "content": "...",
                "source_file": "..."
            }
        ]
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        epub_processor: Optional[EPUBProcessor] = None,
        pdf_processor: Optional[PDFProcessor] = None
    ):
        shared_llm = llm_client or LLMClient(mode=LLMClient.MODE_GPT_OSS)
        self.epub_processor = epub_processor or EPUBProcessor(llm_client=shared_llm)
        self.pdf_processor = pdf_processor or PDFProcessor(llm_client=shared_llm)

    def process(self, books: List[Dict]) -> List[Dict]:
        if not books:
            return []

        series_chapters = []

        for book_index, book in enumerate(books, start=1):
            source_file = book.get("path")

            if not source_file:
                raise ValueError(f"Book entry #{book_index} is missing 'path'")

            book_type = self._resolve_book_type(source_file, book.get("type"))
            processor = self._get_processor(book_type)
            chapters = processor.process(source_file)

            for chapter_index, chapter in enumerate(chapters, start=1):
                series_chapters.append({
                    "book_index": book_index,
                    "chapter_index": chapter_index,
                    "chapter_title": chapter["chapter_title"],
                    "content": chapter["content"],
                    "source_file": source_file
                })

        return series_chapters

    def _get_processor(self, book_type: str):
        if book_type == "epub":
            return self.epub_processor

        if book_type == "pdf":
            return self.pdf_processor

        raise ValueError(f"Unsupported book type: {book_type}")

    def _resolve_book_type(self, source_file: str, book_type: Optional[str]) -> str:
        normalized = (book_type or "").strip().lower()
        if normalized:
            return normalized

        _, extension = os.path.splitext(source_file or "")
        extension = extension.strip().lower()

        if extension == ".epub":
            return "epub"

        if extension == ".pdf":
            return "pdf"

        raise ValueError(f"Could not determine book type for file: {source_file}")
