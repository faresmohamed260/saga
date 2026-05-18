import re
from typing import Dict, List, Optional, Set, Tuple

from infrastructure.llm_client import LLMClient
from rag.scene_index_service import SceneIndexService
from timeline.character_normalizer import CharacterNormalizer


class CharacterIdentityService:
    """
    Resolves raw character identities into an alias map using:
    1. deterministic normalization
    2. weak-identity validation
    3. one-to-many grounded mapping onto canonical candidates

    Original timelines are never modified. This service returns a separate
    alias map plus detailed decisions.
    """

    STOPWORDS = {
        "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "for",
        "with", "from", "by", "her", "his", "their", "my", "our", "your"
    }
    ROLE_LIKE_NAMES = {
        "narrator", "the narrator", "girl", "the girl", "boy", "the boy",
        "woman", "the woman", "man", "the man", "mother", "the mother",
        "father", "the father", "sister", "the sister", "brother", "the brother",
        "daughter", "the daughter", "son", "the son", "wife", "the wife",
        "husband", "the husband", "queen", "the queen", "king", "the king",
        "prince", "the prince", "princess", "the princess", "lord", "the lord",
        "lady", "the lady", "guard", "the guard", "servant", "the servant",
        "maid", "the maid", "huntress", "the huntress", "hunter", "the hunter",
        "faerie", "the faerie", "wolf", "the wolf", "doe", "the doe"
    }

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        top_k: int = 3,
        min_similarity: float = 0.08,
        weak_event_threshold: int = 3,
        merge_confidence_threshold: float = 0.75,
        max_attempts: int = 2,
    ):
        self.llm = llm_client or LLMClient(mode=LLMClient.MODE_GPT_OSS)
        self.top_k = top_k
        self.min_similarity = min_similarity
        self.weak_event_threshold = weak_event_threshold
        self.merge_confidence_threshold = merge_confidence_threshold
        self.max_attempts = max_attempts
        self.normalizer = CharacterNormalizer()
        self.scene_index_service = SceneIndexService(min_similarity=min_similarity, max_results=top_k)

    def build(self, character_timelines: List[Dict], scenes: List[Dict]) -> Dict:
        return self.build_incremental(character_timelines, scenes)

    def build_incremental(self, character_timelines: List[Dict], scenes: List[Dict]) -> Dict:
        normalized = self.normalizer.normalize(character_timelines)
        working_timelines = normalized["character_timelines"]

        alias_map = {
            canonical: set(aliases)
            for canonical, aliases in normalized["alias_map"].items()
        }
        alias_to_canonical = {
            alias: canonical
            for canonical, aliases in alias_map.items()
            for alias in aliases
        }

        self.scene_index_service.build(scenes)
        strong_candidates, weak_candidates = self._split_candidates(working_timelines)
        strong_candidates = sorted(strong_candidates, key=self._timeline_position)
        weak_candidates = sorted(weak_candidates, key=self._timeline_position)

        decisions = []
        rejected_non_characters = []
        alias_history = []
        seen_canonicals = self._seed_seen_canonicals(strong_candidates, weak_candidates)

        for weak_item in weak_candidates:
            character_name = weak_item["character"]
            events = self._select_representative_events(weak_item.get("events", []))
            context_chunks = self._retrieve_context(character_name, events)
            resolved_at = self._timeline_position(weak_item)

            existence = self._validate_character_existence(character_name, events, context_chunks)
            existence["resolved_at_time_index"] = resolved_at
            decisions.append(existence)

            if not existence["is_character"]:
                rejected_non_characters.append(character_name)
                continue

            candidate_pool = self._select_canonical_candidates(weak_item, seen_canonicals, resolved_at)
            if not candidate_pool:
                continue

            mapping = self._map_to_canonical(
                character_name,
                events,
                candidate_pool,
                context_chunks,
            )
            mapping["resolved_at_time_index"] = resolved_at
            decisions.append(mapping)

            if (
                mapping["same_character"]
                and float(mapping["confidence"]) >= self.merge_confidence_threshold
                and mapping.get("canonical_name")
            ):
                self._merge_alias(
                    alias_map,
                    alias_to_canonical,
                    mapping["canonical_name"],
                    character_name,
                )
                alias_history.append({
                    "resolved_at_time_index": resolved_at,
                    "canonical_name": mapping["canonical_name"],
                    "alias_name": character_name,
                })
            else:
                seen_canonicals.append(weak_item)

        alias_history.sort(key=lambda item: (item["resolved_at_time_index"], item["canonical_name"].lower(), item["alias_name"].lower()))

        return {
            "alias_map": {
                canonical: sorted(aliases, key=str.lower)
                for canonical, aliases in sorted(alias_map.items(), key=lambda item: item[0].lower())
            },
            "rejected_non_characters": sorted(set(rejected_non_characters), key=str.lower),
            "decisions": decisions,
            "alias_history": alias_history,
        }

    def _split_candidates(self, character_timelines: List[Dict]) -> tuple[List[Dict], List[Dict]]:
        strong = []
        weak = []

        for item in character_timelines:
            if len(item.get("events", [])) >= self.weak_event_threshold:
                strong.append(item)
            else:
                weak.append(item)

        if not strong:
            strong = list(character_timelines)
            weak = []

        return strong, weak

    def _retrieve_context(self, character_name: str, events: List[Dict]) -> List[Dict]:
        query = self._build_query(character_name, events)
        return self.scene_index_service.retrieve(
            query,
            min_similarity=self.min_similarity,
            max_results=self.top_k,
        )

    def _validate_character_existence(self, character_name: str, events: List[Dict], context_chunks: List[Dict]) -> Dict:
        prompt = f"""
        Decide whether this identity refers to a consequential character in the story.

        Rules:
        - Use only the supplied events and retrieved book evidence
        - A consequential character may be named, role-based, or sentient nonhuman
        - Reject incidental animals, prey, scenery, objects, background groups, and one-off inconsequential entities
        - Do not guess beyond the evidence
        - Keep reasoning brief

        Return JSON:
        {{
          "is_character": true,
          "confidence": 0.82,
          "reasoning": "brief grounded explanation"
        }}

        Identity:
        - name: {character_name}
        - representative events: {[event.get("summary", "") for event in events]}

        Retrieved Book Context:
        {context_chunks}
        """

        response = self._call_with_retries(
            prompt,
            validator=self._validate_existence_response,
        )

        if "error" in response:
            return {
                "decision_type": "existence",
                "character": character_name,
                "is_character": True,
                "confidence": 0.0,
                "reasoning": f"existence_check_failed:{response.get('error')}",
                "retrieved_chunks": context_chunks,
            }

        return {
            "decision_type": "existence",
            "character": character_name,
            "is_character": bool(response["is_character"]),
            "confidence": float(response["confidence"]),
            "reasoning": (response.get("reasoning") or "").strip(),
            "retrieved_chunks": context_chunks,
        }

    def _select_canonical_candidates(self, weak_item: Dict, known_canonicals: List[Dict], resolved_at: int) -> List[Dict]:
        weak_name = weak_item["character"]
        candidates = []

        eligible_canonicals = [
            candidate for candidate in known_canonicals
            if candidate["character"] != weak_name and self._timeline_position(candidate) <= resolved_at
        ]
        if not eligible_canonicals:
            eligible_canonicals = [candidate for candidate in known_canonicals if candidate["character"] != weak_name]

        for candidate in eligible_canonicals:
            if candidate["character"] == weak_name:
                continue
            candidates.append((self._candidate_score(weak_item, candidate), candidate))

        candidates.sort(
            key=lambda item: (
                -item[0],
                -len(item[1].get("events", [])),
                item[1]["character"].lower(),
            )
        )
        return [candidate for _, candidate in candidates]

    def _candidate_score(self, weak_item: Dict, candidate: Dict) -> float:
        weak_name = weak_item["character"]
        candidate_name = candidate["character"]

        score = 0.0
        norm_weak = self._normalize_name(weak_name)
        norm_candidate = self._normalize_name(candidate_name)

        if norm_weak == norm_candidate:
            return 10.0

        if norm_candidate.startswith(norm_weak) or norm_weak.startswith(norm_candidate):
            score += 4.0

        weak_tokens = self._name_tokens(weak_name)
        candidate_tokens = self._name_tokens(candidate_name)
        if weak_tokens and candidate_tokens and weak_tokens.intersection(candidate_tokens):
            score += 3.0

        if self._is_descriptor_like(weak_name):
            event_keywords_weak = self._event_keywords(weak_item.get("events", []))
            event_keywords_candidate = self._event_keywords(candidate.get("events", []))
            overlap = len(event_keywords_weak.intersection(event_keywords_candidate))
            score += overlap * 0.5

        return score

    def _map_to_canonical(
        self,
        weak_name: str,
        weak_events: List[Dict],
        candidate_pool: List[Dict],
        context_chunks: List[Dict],
    ) -> Dict:
        candidate_summaries = [
            {
                "candidate_name": candidate["character"],
                "representative_events": [event.get("summary", "") for event in self._select_representative_events(candidate.get("events", []))],
                "event_count": len(candidate.get("events", [])),
            }
            for candidate in candidate_pool
        ]

        prompt = f"""
        Determine whether this weak identity maps to one of the known canonical characters.

        Rules:
        - Use only the supplied events and retrieved book evidence
        - Do not guess beyond the evidence
        - If the identity does not clearly map to any known character, return canonical_name as NONE
        - canonical_name must be exactly one of the supplied known characters or NONE
        - Do not invent a new canonical identity
        - Keep reasoning brief and grounded

        Return JSON:
        {{
          "same_character": true,
          "confidence": 0.84,
          "reasoning": "brief grounded explanation",
          "canonical_name": "Feyre"
        }}

        Weak identity:
        - name: {weak_name}
        - representative events: {[event.get("summary", "") for event in weak_events]}

        Known canonical characters:
        {candidate_summaries}

        Retrieved Book Context:
        {context_chunks}
        """

        response = self._call_with_retries(
            prompt,
            validator=self._validate_mapping_response,
        )

        if "error" in response:
            return {
                "decision_type": "mapping",
                "character": weak_name,
                "same_character": False,
                "confidence": 0.0,
                "reasoning": f"mapping_failed:{response.get('error')}",
                "canonical_name": None,
                "candidate_names": [candidate["character"] for candidate in candidate_pool],
                "retrieved_chunks": context_chunks,
            }

        canonical_name = response.get("canonical_name")
        same_character = bool(response.get("same_character")) and canonical_name not in {None, "", "NONE"}

        return {
            "decision_type": "mapping",
            "character": weak_name,
            "same_character": same_character,
            "confidence": float(response["confidence"]),
            "reasoning": (response.get("reasoning") or "").strip(),
            "canonical_name": canonical_name if same_character else None,
            "candidate_names": [candidate["character"] for candidate in candidate_pool],
            "retrieved_chunks": context_chunks,
        }

    def _call_with_retries(self, prompt: str, validator) -> Dict:
        last_response = None

        for attempt in range(1, self.max_attempts + 1):
            retry_hint = ""
            if attempt > 1:
                retry_hint = (
                    "\nYour previous response was invalid. "
                    "Return only valid JSON matching the exact required schema.\n"
                )

            response = self.llm.generate_json(
                prompt + retry_hint,
                strict=True,
                validator=validator,
            )
            last_response = response

            if "error" not in response:
                return response

        return last_response or {"error": "unknown_error"}

    def _merge_alias(
        self,
        alias_map: Dict[str, Set[str]],
        alias_to_canonical: Dict[str, str],
        canonical_name: str,
        alias_name: str,
    ):
        current_canonical = alias_to_canonical.get(alias_name)
        if current_canonical and current_canonical != canonical_name:
            return

        alias_map.setdefault(canonical_name, set()).update({canonical_name, alias_name})
        alias_to_canonical[canonical_name] = canonical_name
        alias_to_canonical[alias_name] = canonical_name

    def _validate_existence_response(self, response: Dict) -> bool:
        return (
            isinstance(response.get("is_character"), bool)
            and isinstance(response.get("confidence"), (int, float))
            and isinstance(response.get("reasoning"), str)
            and bool(response.get("reasoning").strip())
        )

    def _validate_mapping_response(self, response: Dict) -> bool:
        return (
            isinstance(response.get("same_character"), bool)
            and isinstance(response.get("confidence"), (int, float))
            and isinstance(response.get("reasoning"), str)
            and bool(response.get("reasoning").strip())
            and "canonical_name" in response
        )

    def _select_representative_events(self, events: List[Dict]) -> List[Dict]:
        if len(events) <= 3:
            return events

        middle_index = len(events) // 2
        return [events[0], events[middle_index], events[-1]]

    def _build_query(self, character_name: str, events: List[Dict]) -> str:
        event_bits = [event.get("summary", "") for event in events]
        return " ".join([character_name] + event_bits)

    def _seed_seen_canonicals(self, strong_candidates: List[Dict], weak_candidates: List[Dict]) -> List[Dict]:
        if strong_candidates:
            return list(strong_candidates)
        return list(weak_candidates)

    def _timeline_position(self, item: Dict) -> int:
        events = item.get("events", [])
        if not events:
            return 10 ** 9
        return min(event.get("time_index", 10 ** 9) for event in events)

    def _event_keywords(self, events: List[Dict]) -> Set[str]:
        words = set()
        for event in self._select_representative_events(events):
            text = (event.get("summary") or "").lower()
            for token in re.findall(r"[a-zA-Z][a-zA-Z'-]+", text):
                if token not in self.STOPWORDS and len(token) > 3:
                    words.add(token)
        return words

    def _normalize_name(self, name: str) -> str:
        return re.sub(r"\s+", " ", (name or "").strip().lower())

    def _name_tokens(self, name: str) -> Set[str]:
        return {
            token for token in re.findall(r"[a-zA-Z][a-zA-Z'-]+", self._normalize_name(name))
            if token not in self.STOPWORDS
        }

    def _is_descriptor_like(self, name: str) -> bool:
        lowered = self._normalize_name(name)
        if not lowered:
            return False

        if lowered in self.ROLE_LIKE_NAMES:
            return True

        if lowered.startswith(("the ", "a ", "an ")):
            return True

        raw = (name or "").strip()
        return raw == raw.lower()
