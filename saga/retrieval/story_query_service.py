"""High-level query adapter for presenting grounded search results."""

from typing import Dict, List


class StoryQueryService:
    """
    Produces grounded query results from the indexed story outputs.
    """

    def search(self, story_index_service, query: str, min_similarity: float = 0.05, max_results: int = 8) -> List[Dict]:
        matches = story_index_service.query(query, min_similarity=min_similarity, max_results=max_results)
        results = []

        for item in matches:
            metadata = item.get("metadata", {})
            summary = item.get("summary", "")
            scene_ref = self._scene_ref(metadata)
            results.append({
                "item_type": item.get("item_type"),
                "score": item.get("score"),
                "summary": summary,
                "scene_ref": scene_ref,
                "metadata": metadata,
                "text": item.get("text", ""),
            })

        return results

    def _scene_ref(self, metadata: Dict) -> str:
        if metadata.get("book_index") is None:
            return "No direct scene reference"

        chapter = metadata.get("chapter_index")
        scene = metadata.get("scene_index")
        if chapter is None or scene is None:
            return f"Book {metadata.get('book_index')}"

        return f"Book {metadata.get('book_index')} | Chapter {chapter} | Scene {scene}"
