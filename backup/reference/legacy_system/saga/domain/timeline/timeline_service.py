from typing import Dict, List, Tuple


class TimelineService:
    """
    Builds a global timeline by sorting scene events in reading order.
    """

    def build(self, scenes: List[Dict], extracted_events: List[Dict]) -> List[Dict]:
        scene_order = sorted(
            scenes,
            key=lambda scene: (
                scene["book_index"],
                scene["chapter_index"],
                scene["scene_index"]
            )
        )

        events_by_scene = {
            self._scene_key(item): item.get("events", [])
            for item in extracted_events
        }

        timeline = []
        time_index = 1

        for scene in scene_order:
            scene_key = self._scene_key(scene)
            events = events_by_scene.get(scene_key, [])

            for event in events:
                timeline.append({
                    "time_index": time_index,
                    "book_index": scene["book_index"],
                    "chapter_index": scene["chapter_index"],
                    "scene_index": scene["scene_index"],
                    "event_id": event["event_id"],
                    "summary": event["description"],
                    "event_type": event.get("event_type") or event.get("type", ""),
                    "type": event.get("event_type") or event.get("type", ""),
                    "characters": event.get("characters", []),
                    "entities_involved": event.get("entities_involved", []),
                    "reason": event.get("reason", ""),
                    "outcome": event.get("outcome", ""),
                })
                time_index += 1

        return timeline

    def build_from_scene_analyses(self, scene_analyses: List[Dict]) -> List[Dict]:
        ordered_scene_analyses = sorted(
            scene_analyses,
            key=lambda scene: (
                scene["book_index"],
                scene["chapter_index"],
                scene["scene_index"],
            )
        )

        timeline = []
        time_index = 1

        for scene in ordered_scene_analyses:
            for event in scene.get("events", []):
                timeline.append({
                    "time_index": time_index,
                    "book_index": scene["book_index"],
                    "chapter_index": scene["chapter_index"],
                    "scene_index": scene["scene_index"],
                    "event_id": event["event_id"],
                    "summary": event["description"],
                    "event_type": event.get("event_type") or event.get("type", ""),
                    "type": event.get("event_type") or event.get("type", ""),
                    "characters": event.get("characters", []),
                    "entities_involved": event.get("entities_involved", []),
                    "reason": event.get("reason", ""),
                    "outcome": event.get("outcome", ""),
                })
                time_index += 1

        return timeline

    def _scene_key(self, item: Dict) -> Tuple[int, int, int]:
        return (
            item["book_index"],
            item["chapter_index"],
            item["scene_index"]
        )
