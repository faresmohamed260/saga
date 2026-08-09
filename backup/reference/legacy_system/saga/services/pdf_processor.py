"""PDF ingestion and chapter extraction service."""

import logging
import re
from typing import Dict, List, Optional

import fitz
from pypdf import PdfReader

from packages.reasoning_runtime.contracts import ReasoningClient
from saga.providers.reasoning_runtime_adapter import MODE_GENERAL_COMPUTE, MODE_GPT_OSS, create_runtime_client


class PDFProcessor:
    """
    PDF processor aligned with EPUBProcessor's output contract.

    Output:
        [
            {
                "chapter_title": str,
                "content": str
            }
        ]
    """

    CHAPTER_PATTERN = re.compile(
        r"(?im)^\s*(prologue|epilogue|chapter\s+(?:\d+|[ivxlcdm]+|one|two|three|four|five|six|seven|eight|nine|ten|"
        r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty))\b[^\n]{0,80}"
    )

    def __init__(self, llm_client: ReasoningClient = None):
        self.llm = llm_client or create_runtime_client(mode=MODE_GPT_OSS)

    def process(self, file_path: str) -> List[Dict]:
        doc = self._load_pdf(file_path)
        if not doc:
            return []

        try:
            page_texts = self._extract_pages_text(doc["fitz_doc"])
            if not page_texts:
                return []

            raw_toc_entries = self._extract_toc_entries(doc["reader"])
            if raw_toc_entries:
                raw_toc_titles = [entry["title"] for entry in raw_toc_entries]
                logging.info("Raw ToC entries: %s", len(raw_toc_titles))

                filtered_toc_titles = self._prune_leading_non_narrative_title(
                    self._filter_toc_with_llm(raw_toc_titles)
                )
                logging.info("Filtered chapters: %s", len(filtered_toc_titles))

                toc_entries = self._filter_toc_entries(raw_toc_entries, filtered_toc_titles)
            else:
                toc_entries = self._detect_candidate_chapters(page_texts)
                raw_toc_titles = [entry["title"] for entry in toc_entries]
                logging.info("Detected candidate chapters: %s", len(raw_toc_titles))

                filtered_toc_titles = self._prune_leading_non_narrative_title(
                    self._filter_toc_with_llm(raw_toc_titles)
                )
                logging.info("Filtered chapters: %s", len(filtered_toc_titles))

                toc_entries = self._filter_toc_entries(toc_entries, filtered_toc_titles)

            chapters = self._extract_chapters(page_texts, toc_entries)
            logging.info("Final chapters extracted: %s", len(chapters))
            return chapters
        finally:
            doc["fitz_doc"].close()

    def _load_pdf(self, file_path: str):
        try:
            return {
                "reader": PdfReader(file_path),
                "fitz_doc": fitz.open(file_path),
            }
        except Exception as e:
            logging.error("Failed to load PDF: %s", e)
            return None

    def _extract_pages_text(self, doc: fitz.Document) -> List[Dict]:
        pages = []

        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            text = self._clean(page.get_text("text"))

            if not text:
                continue

            pages.append(
                {
                    "page_index": page_index,
                    "text": text,
                    "norm_text": self._normalize(text),
                }
            )

        return pages

    def _extract_toc_entries(self, reader: PdfReader) -> List[Dict]:
        entries = []

        try:
            outline = getattr(reader, "outline", None) or []

            def flatten(items):
                for item in items:
                    if isinstance(item, list):
                        yield from flatten(item)
                        continue

                    title = (getattr(item, "title", None) or "").strip()
                    if not title:
                        continue

                    try:
                        page_number = reader.get_destination_page_number(item)
                    except Exception:
                        page_number = None

                    yield {
                        "title": title,
                        "page_index": page_number,
                    }

            entries = [entry for entry in flatten(outline) if entry["page_index"] is not None]

        except Exception as e:
            logging.warning("PDF ToC extraction failed: %s", e)

        return entries

    def _detect_candidate_chapters(self, page_texts: List[Dict]) -> List[Dict]:
        entries = []

        for page in page_texts:
            matches = list(self.CHAPTER_PATTERN.finditer(page["text"]))
            if not matches:
                continue

            for match in matches:
                title = self._clean(match.group(1 if match.lastindex else 0))
                if not title:
                    continue

                entries.append(
                    {
                        "title": title,
                        "page_index": page["page_index"],
                    }
                )

        deduped = []
        seen = set()

        for entry in entries:
            key = (entry["title"], entry["page_index"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(entry)

        return deduped

    def _filter_toc_with_llm(self, toc_titles: List[str]) -> List[str]:
        if not toc_titles:
            return []

        prompt = f"""
        You are given a book's Table of Contents.

        Select ONLY narrative chapters.

        STRICT RULES:
        - Keep exact text
        - Keep order
        - No modifications

        INCLUDE:
        - Chapters
        - Prologue
        - Epilogue

        EXCLUDE:
        - Copyright
        - Acknowledgments
        - TOC
        - Parts (unless actual story)

        Return JSON:
        {{
          "chapters": ["entry1", "entry2"]
        }}

        ToC:
        {toc_titles}
        """

        response = self.llm.generate_json(prompt, strict=True)

        if "error" in response or "chapters" not in response:
            logging.warning("LLM ToC filtering failed; falling back to heuristic filtering")
            return self._filter_toc_heuristically(toc_titles)

        toc_set = set(toc_titles)
        valid = [chapter for chapter in response["chapters"] if chapter in toc_set]

        if not valid:
            logging.warning("LLM returned no valid ToC chapters; falling back to heuristic filtering")
            return self._filter_toc_heuristically(toc_titles)

        return valid

    def _filter_toc_heuristically(self, toc_titles: List[str]) -> List[str]:
        keep = []
        include_patterns = [
            r"^chapter\b",
            r"^prologue\b",
            r"^epilogue\b",
        ]
        exclude_patterns = [
            r"copyright",
            r"acknowledg",
            r"\bcontents?\b",
            r"\btable of contents\b",
            r"\btitle page\b",
            r"\bcover\b",
            r"\babout the author\b",
            r"\bglossary\b",
            r"\bindex\b",
        ]

        for title in toc_titles:
            cleaned = (title or "").strip()
            if not cleaned:
                continue
            lowered = cleaned.lower()
            if any(re.search(pattern, lowered) for pattern in exclude_patterns):
                continue
            if any(re.search(pattern, lowered) for pattern in include_patterns):
                keep.append(cleaned)

        if keep:
            return keep

        return [title for title in toc_titles if (title or "").strip()]

    def _prune_leading_non_narrative_title(self, toc_titles: List[str]) -> List[str]:
        if len(toc_titles) < 2:
            return toc_titles

        first = (toc_titles[0] or "").strip()
        second = (toc_titles[1] or "").strip()
        narrative_pattern = re.compile(r"^(chapter\b|prologue\b|epilogue\b)", re.IGNORECASE)

        if first and second and not narrative_pattern.search(first) and narrative_pattern.search(second):
            logging.info("Dropping leading non-narrative ToC entry: %s", first)
            return toc_titles[1:]

        return toc_titles

    def _filter_toc_entries(self, raw_entries: List[Dict], filtered_titles: List[str]) -> List[Dict]:
        selected = []
        search_start = 0

        for title in filtered_titles:
            for idx in range(search_start, len(raw_entries)):
                entry = raw_entries[idx]
                if entry["title"] == title:
                    selected.append(entry)
                    search_start = idx + 1
                    break

        return selected

    def _extract_chapters(self, page_texts: List[Dict], toc_entries: List[Dict]) -> List[Dict]:
        if not toc_entries:
            return []

        page_lookup = {page["page_index"]: page for page in page_texts}
        resolved_starts = []

        for toc_entry in toc_entries:
            page = page_lookup.get(toc_entry["page_index"])
            if not page:
                continue

            start_offset = self._resolve_title_offset(page["text"], toc_entry["title"])
            resolved_starts.append(
                {
                    "title": toc_entry["title"],
                    "page_index": toc_entry["page_index"],
                    "offset": start_offset,
                }
            )

        chapters = []

        for index, start in enumerate(resolved_starts):
            next_start = resolved_starts[index + 1] if index + 1 < len(resolved_starts) else None
            content = self._slice_chapter(page_texts, start, next_start)

            if len(content.split()) < 3:
                continue

            if self._is_junk(start["title"], content):
                continue

            chapters.append(
                {
                    "chapter_title": start["title"],
                    "content": content,
                }
            )
            logging.info("New chapter: %s", start["title"])

        return chapters

    def _slice_chapter(self, page_texts: List[Dict], start: Dict, next_start: Optional[Dict]) -> str:
        chunk_parts = []

        for page in page_texts:
            page_index = page["page_index"]
            if page_index < start["page_index"]:
                continue

            if next_start and page_index > next_start["page_index"]:
                break

            text = page["text"]
            page_start = 0
            page_end = len(text)

            if page_index == start["page_index"]:
                page_start = min(start["offset"], len(text))

            if next_start and page_index == next_start["page_index"]:
                page_end = min(next_start["offset"], len(text))

            if next_start and page_index == next_start["page_index"] and page_index == start["page_index"]:
                if page_end <= page_start:
                    continue

            snippet = self._clean(text[page_start:page_end])
            if snippet:
                chunk_parts.append(snippet)

            if next_start and page_index == next_start["page_index"]:
                break

        return self._clean("\n\n".join(chunk_parts))

    def _resolve_title_offset(self, page_text: str, title: str) -> int:
        if not title:
            return 0

        for match in re.finditer(re.escape(title), page_text, re.IGNORECASE):
            return match.start()

        title_pattern = re.compile(rf"(?im)^\s*{re.escape(title)}\b")
        heading_match = title_pattern.search(page_text)
        if heading_match:
            return heading_match.start()

        chapter_match = self.CHAPTER_PATTERN.search(page_text)
        if chapter_match:
            return chapter_match.start()

        return 0

    def _clean(self, text: str) -> str:
        text = re.sub(r"\r\n|\r", "\n", text or "")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

        lines = [line.strip() for line in text.split("\n")]
        lines = [line for line in lines if line]

        return "\n".join(lines).strip()

    def _is_junk(self, title: Optional[str], text: str) -> bool:
        title_lower = (title or "").lower()
        text_lower = (text or "").lower()

        junk_titles = [
            "contents",
            "table of contents",
            "copyright",
            "acknowledgments",
            "acknowledgements",
        ]

        if any(junk in title_lower for junk in junk_titles):
            return True

        junk_patterns = [
            "all rights reserved",
            "no part of this book may be reproduced",
            "isbn",
            "published by",
            "cover design",
            "printed in",
        ]

        matches = sum(1 for pattern in junk_patterns if pattern in text_lower)
        return matches >= 2

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().lower())

