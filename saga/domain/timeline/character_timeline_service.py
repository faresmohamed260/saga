from typing import Dict, List


class CharacterTimelineService:
    """
    Reorganizes the global timeline into per-character timelines.

    Each character name is treated exactly as-is from the source saga.domain.timeline.
    No identity resolution or alias merging is performed.
    """

    def build(self, timeline: List[Dict]) -> List[Dict]:
        ordered_timeline = sorted(timeline, key=lambda item: item["time_index"])
        timelines_by_character = {}

        for item in ordered_timeline:
            characters = item.get("characters") or []
            for character in characters:
                if not character:
                    continue

                timelines_by_character.setdefault(character, []).append({
                    "time_index": item["time_index"],
                    "book_index": item["book_index"],
                    "chapter_index": item["chapter_index"],
                    "scene_index": item["scene_index"],
                    "event_id": item["event_id"],
                    "summary": item["summary"]
                })

        return [
            {
                "character": character,
                "events": events
            }
            for character, events in sorted(timelines_by_character.items(), key=lambda entry: entry[0].lower())
        ]
