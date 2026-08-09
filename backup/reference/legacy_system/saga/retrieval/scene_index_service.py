from typing import Dict, List, Optional

from sklearn.feature_extraction.text import TfidfVectorizer


class SceneIndexService:
    """
    Builds a scene-sized retrieval index with threshold-first retrieval.
    """

    def __init__(self, min_similarity: float = 0.08, max_results: int = 5, excerpt_chars: int = 700):
        self.min_similarity = min_similarity
        self.max_results = max_results
        self.excerpt_chars = excerpt_chars
        self.vectorizer = None
        self.matrix = None
        self.scenes: List[Dict] = []

    def build(self, scenes: List[Dict]) -> Dict:
        self.scenes = list(scenes)
        texts = [scene.get("text", "") for scene in self.scenes]

        if not texts:
            self.vectorizer = None
            self.matrix = None
            return {"scene_count": 0}

        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self.matrix = self.vectorizer.fit_transform(texts)
        return {"scene_count": len(self.scenes)}

    def retrieve(self, query: str, min_similarity: Optional[float] = None, max_results: Optional[int] = None) -> List[Dict]:
        if not query or self.vectorizer is None or self.matrix is None or not self.scenes:
            return []

        threshold = self.min_similarity if min_similarity is None else min_similarity
        limit = self.max_results if max_results is None else max_results

        query_vector = self.vectorizer.transform([query])
        scores = (self.matrix @ query_vector.T).toarray().ravel()

        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
        results = []

        for index, score in ranked:
            if score < threshold:
                continue

            scene = self.scenes[index]
            results.append({
                "book_index": scene.get("book_index"),
                "chapter_index": scene.get("chapter_index"),
                "scene_index": scene.get("scene_index"),
                "length": scene.get("length"),
                "score": float(score),
                "text": self._excerpt(scene.get("text", "")),
            })

            if len(results) >= limit:
                break

        return results

    def _excerpt(self, text: str) -> str:
        text = (text or "").strip()
        if len(text) <= self.excerpt_chars:
            return text
        return text[:self.excerpt_chars].rstrip() + "..."
