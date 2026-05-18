from typing import Dict, List, Optional

from infrastructure.llm_client import LLMClient


class EventExtractor:
    """
    Extracts a small set of events from a scene using the LLM client.
    """

    VALID_TYPES = {"action", "interaction", "movement", "discovery"}

    def __init__(self, llm_client: Optional[LLMClient] = None, max_attempts: int = 2):
        self.llm = llm_client or LLMClient(mode=LLMClient.MODE_GPT_OSS)
        self.max_attempts = max_attempts

    def extract(self, scene: Dict) -> Dict:
        last_response = None

        for attempt in range(1, self.max_attempts + 1):
            prompt = self._build_prompt(
                scene_text=scene.get("text", ""),
                retry_hint=attempt > 1
            )

            response = self.llm.generate_json(
                prompt,
                strict=True,
                validator=self._validate_response
            )
            last_response = response

            if "error" not in response:
                return {"events": self._normalize_events(response.get("events", []))}

        return {"events": [], "error": last_response.get("error") if isinstance(last_response, dict) else "unknown_error"}

    def extract_many(self, scenes: List[Dict]) -> List[Dict]:
        extracted = []

        for scene in scenes:
            result = self.extract(scene)
            extracted.append({
                "book_index": scene.get("book_index"),
                "chapter_index": scene.get("chapter_index"),
                "scene_index": scene.get("scene_index"),
                "events": result["events"],
                "error": result.get("error")
            })

        return extracted

    def _build_prompt(self, scene_text: str, retry_hint: bool = False) -> str:
        retry_line = ""
        if retry_hint:
            retry_line = (
                "Your previous response was invalid. "
                "Return only valid JSON matching the required schema.\n"
            )

        return f"""
        Extract only the core story events from this scene.

        {retry_line}

        Rules:
        - Return at most 5 events
        - Focus only on concrete events that happen in the scene
        - Do not include relationships
        - Do not include entity states
        - Do not include alias maps
        - "characters" means only consequential participants in the event
        - A character may be:
          - a named person
          - a role-based but story-relevant figure
          - a sentient nonhuman being with meaningful agency in the event
        - Include a character only if they act, speak, decide, are directly addressed, or are a meaningful target of the event
        - Do not include background or inconsequential entities
        - Exclude incidental animals, prey, scenery, objects, crowds, and generic background groups unless they are clearly story-relevant participants in that specific event
        - If no consequential character is clearly involved, return an empty characters list for that event
        - Use only these event types:
          action, interaction, movement, discovery

        Return JSON:
        {{
          "events": [
            {{
              "description": "short event description",
              "characters": ["Character A", "Character B"],
              "type": "action"
            }}
          ]
        }}

        Scene:
        {scene_text}
        """

    def _normalize_events(self, events: List[Dict]) -> List[Dict]:
        normalized = []

        for index, event in enumerate(events[:5], start=1):
            event_type = (event.get("type") or "").strip().lower()
            if event_type not in self.VALID_TYPES:
                event_type = "action"

            characters = event.get("characters") or []
            if not isinstance(characters, list):
                characters = []

            description = (event.get("description") or "").strip()
            if not description:
                continue

            normalized.append({
                "event_id": f"evt_{index}",
                "description": description,
                "characters": [str(character).strip() for character in characters if str(character).strip()],
                "type": event_type
            })

        return normalized

    def _validate_response(self, response: Dict) -> bool:
        events = response.get("events")
        if not isinstance(events, list):
            return False

        for event in events[:5]:
            if not isinstance(event, dict):
                return False
            if not event.get("description"):
                return False

        return True
