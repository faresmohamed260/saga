import logging
import posixpath
import re
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup
from ebooklib import epub
import trafilatura

from packages.reasoning_runtime.contracts import ReasoningClient
from saga.providers.reasoning_runtime_adapter import MODE_GENERAL_COMPUTE, MODE_GPT_OSS, create_runtime_client

logging.getLogger("trafilatura").setLevel(logging.ERROR)
logging.getLogger("trafilatura.core").setLevel(logging.ERROR)


class EPUBProcessor:
    """
    Clean EPUB processor.

    Responsibilities:
    - Load EPUB
    - Extract ToC
    - Filter chapters using LLM
    - Extract clean chapter text

    Output:
        [
            {
                "chapter_title": str,
                "content": str
            }
        ]
    """

    def __init__(self, llm_client: ReasoningClient = None):
        self.llm = llm_client or create_runtime_client(mode=MODE_GPT_OSS)

    def process(self, file_path: str) -> List[Dict]:
        book = self._load_epub(file_path)
        if not book:
            return []

        raw_toc_entries = self._extract_toc_entries(book)
        raw_toc_titles = [entry["title"] for entry in raw_toc_entries]
        logging.info("Raw ToC entries: %s", len(raw_toc_titles))

        filtered_toc_titles = self._filter_toc_with_llm(raw_toc_titles)
        filtered_toc_titles = self._prune_leading_non_narrative_title(filtered_toc_titles)
        logging.info("Filtered chapters: %s", len(filtered_toc_titles))

        filtered_toc_entries = self._filter_toc_entries(raw_toc_entries, filtered_toc_titles)
        chapters = self._extract_chapters(book, raw_toc_entries, filtered_toc_entries)

        logging.info("Final chapters extracted: %s", len(chapters))
        return chapters

    def _load_epub(self, file_path: str):
        try:
            return epub.read_epub(file_path)
        except Exception as e:
            logging.error("Failed to load EPUB: %s", e)
            return None

    def _extract_toc_entries(self, book) -> List[Dict[str, Optional[str]]]:
        entries = []

        try:
            toc = book.toc

            def flatten(items):
                for item in items:
                    if isinstance(item, list):
                        yield from flatten(item)
                    elif isinstance(item, tuple):
                        yield from flatten(item)
                    elif hasattr(item, "title"):
                        title = (item.title or "").strip()
                        href = getattr(item, "href", None)

                        if title:
                            yield {
                                "title": title,
                                "href": href
                            }

            entries = list(flatten(toc))

        except Exception as e:
            logging.warning("ToC extraction failed: %s", e)

        return entries

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

    def _filter_toc_entries(
        self,
        raw_entries: List[Dict[str, Optional[str]]],
        filtered_titles: List[str]
    ) -> List[Dict[str, Optional[str]]]:
        selected = []
        search_start = 0

        for title in filtered_titles:
            for idx in range(search_start, len(raw_entries)):
                entry = raw_entries[idx]
                if entry["title"] == title:
                    selected.append({
                        **entry,
                        "_raw_index": idx
                    })
                    search_start = idx + 1
                    break

        return selected

    def _extract_chapters(
        self,
        book,
        all_toc_entries: List[Dict[str, Optional[str]]],
        filtered_toc_entries: List[Dict[str, Optional[str]]]
    ) -> List[Dict]:
        if not filtered_toc_entries:
            return []

        blocks = self._flatten_spine(book)
        if not blocks:
            return []

        file_index = {}
        for index, block in enumerate(blocks):
            file_index.setdefault(block["file"], []).append(index)

        filtered_raw_indexes = {entry["_raw_index"] for entry in filtered_toc_entries}
        resolved_entries = []
        cursor = -1

        for raw_index, entry in enumerate(all_toc_entries):
            start_index = self._resolve_toc_pointer(entry, blocks, file_index, min_index=cursor + 1)
            if start_index is None:
                if raw_index in filtered_raw_indexes:
                    logging.warning("Could not resolve ToC pointer for: %s", entry["title"])
                continue

            resolved_entries.append({
                "title": entry["title"],
                "start_index": start_index,
                "raw_index": raw_index
            })
            cursor = start_index

        resolved_by_raw_index = {entry["raw_index"]: entry for entry in resolved_entries}
        chapters = []

        for filtered_entry in filtered_toc_entries:
            start_info = resolved_by_raw_index.get(filtered_entry["_raw_index"])
            if not start_info:
                continue

            title = start_info["title"]
            start_index = start_info["start_index"]

            end_index = len(blocks)
            for candidate in resolved_entries:
                if candidate["raw_index"] > filtered_entry["_raw_index"]:
                    end_index = candidate["start_index"]
                    break

            chunk = blocks[start_index:end_index]

            if not chunk:
                continue

            content = self._clean("\n\n".join(block["text"] for block in chunk if block["text"]))

            if len(content.split()) < 3:
                continue

            if self._is_junk(title, content):
                continue

            chapters.append({
                "chapter_title": title,
                "content": content
            })
            logging.info("New chapter: %s", title)

        return chapters

    def _flatten_spine(self, book) -> List[Dict]:
        blocks = []
        spine_items = [item[0] for item in book.spine if item[0] != "nav"]

        for item_id in spine_items:
            item = book.get_item_with_id(item_id)
            if not item:
                continue

            file_name = self._normalize_href(item.get_name())
            html = item.get_content().decode("utf-8", errors="ignore")
            blocks.extend(self._extract_blocks_from_html(file_name, html))

        return blocks

    def _extract_blocks_from_html(self, file_name: str, html: str) -> List[Dict]:
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "noscript"]):
            tag.decompose()

        root = soup.body or soup
        block_names = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "pre", "div"}
        blocks = []

        for element in root.find_all(block_names):
            if element.name == "div" and element.find(block_names):
                continue

            text = self._clean(element.get_text(separator="", strip=False))
            if len(text.split()) < 2:
                continue

            anchor_ids = []
            node = element
            while node and getattr(node, "name", None):
                element_id = node.get("id")
                if element_id and element_id not in anchor_ids:
                    anchor_ids.append(element_id)
                node = node.parent

            blocks.append({
                "file": file_name,
                "text": text,
                "norm_text": self._normalize(text),
                "anchor_ids": anchor_ids
            })

        if blocks:
            return blocks

        text = self._extract_text(html)
        if not self._is_valid_text(text):
            return []

        return [{
            "file": file_name,
            "text": text,
            "norm_text": self._normalize(text),
            "anchor_ids": []
        }]

    def _resolve_toc_pointer(
        self,
        toc_entry: Dict[str, Optional[str]],
        blocks: List[Dict],
        file_index: Dict[str, List[int]],
        min_index: int = 0
    ) -> Optional[int]:
        title = toc_entry["title"]
        norm_title = self._normalize(title)
        path, fragment = self._split_href(toc_entry.get("href"))

        candidate_indexes = self._get_candidate_indexes(path, file_index, min_index)
        if not candidate_indexes:
            return None

        if fragment:
            for idx in candidate_indexes:
                if fragment in blocks[idx]["anchor_ids"]:
                    return idx

        for idx in candidate_indexes:
            block_text = blocks[idx]["norm_text"]
            if block_text == norm_title or block_text.startswith(norm_title + " "):
                return idx
            if len(norm_title) > 5 and norm_title in block_text:
                return idx

        return candidate_indexes[0]

    def _get_candidate_indexes(
        self,
        path: str,
        file_index: Dict[str, List[int]],
        min_index: int
    ) -> List[int]:
        exact = [idx for idx in file_index.get(path, []) if idx >= min_index]
        if exact:
            return exact

        if not path:
            return [
                idx
                for indexes in file_index.values()
                for idx in indexes
                if idx >= min_index
            ]

        path_tail = posixpath.basename(path)
        matches = []

        for file_name, indexes in file_index.items():
            if file_name == path or posixpath.basename(file_name) == path_tail:
                matches.extend(idx for idx in indexes if idx >= min_index)

        return sorted(matches)

    def _split_href(self, href: Optional[str]) -> Tuple[str, Optional[str]]:
        if not href:
            return "", None

        path, _, fragment = href.partition("#")
        return self._normalize_href(path), fragment or None

    def _normalize_href(self, href: str) -> str:
        href = (href or "").strip().replace("\\", "/")
        if not href:
            return ""

        return posixpath.normpath(href)

    def _extract_number(self, text: str):
        match = re.search(r"\d+", text)
        if match:
            return int(match.group())

        roman_map = {
            "i": 1,
            "ii": 2,
            "iii": 3,
            "iv": 4,
            "v": 5,
            "vi": 6,
            "vii": 7,
            "viii": 8,
            "ix": 9,
            "x": 10
        }

        for roman, value in roman_map.items():
            if f" {roman} " in f" {text} ":
                return value

        return None

    def _extract_text(self, html: str) -> str:
        try:
            extracted = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
                favor_precision=True
            )

            if extracted and len(extracted.split()) > 50:
                return self._clean(extracted)

        except Exception:
            pass

        return self._fallback(html)

    def _fallback(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        return self._clean(soup.get_text(separator="\n"))

    def _clean(self, text: str) -> str:
        text = re.sub(r"\r\n|\r", "\n", text)
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

        lines = [line.strip() for line in text.split("\n")]
        lines = [line for line in lines if line]

        text = "\n".join(lines)
        text = re.sub(r"[ \t]+", " ", text)

        return text.strip()

    def _extract_title(self, html: str) -> Optional[str]:
        soup = BeautifulSoup(html, "html.parser")

        for tag in ["h1", "h2", "h3"]:
            element = soup.find(tag)
            if element:
                title = element.get_text(strip=True)
                if title and len(title) < 100:
                    return title

        return None

    def _is_valid_text(self, text: str) -> bool:
        return bool(text and len(text.split()) > 50)

    def _is_junk(self, title: Optional[str], text: str) -> bool:
        title_lower = (title or "").lower()
        text_lower = (text or "").lower()

        junk_titles = [
            "contents",
            "table of contents",
            "copyright",
            "acknowledgments",
            "acknowledgements"
        ]

        if any(junk in title_lower for junk in junk_titles):
            return True

        junk_patterns = [
            "all rights reserved",
            "no part of this book may be reproduced",
            "isbn",
            "published by",
            "cover design",
            "printed in"
        ]

        matches = sum(1 for pattern in junk_patterns if pattern in text_lower)
        return matches >= 2

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", text.strip().lower())


