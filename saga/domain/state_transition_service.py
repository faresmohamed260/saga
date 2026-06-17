from typing import Dict, List, Tuple


class StateTransitionService:
    """
    Applies state changes in scene order and builds a transition log plus latest state.
    """

    def build(self, analyzed_scenes: List[Dict]) -> Dict:
        transitions = []
        current_state: Dict[Tuple[str, str], Dict] = {}
        state_index = 1

        for scene in sorted(analyzed_scenes, key=self._scene_key):
            for change in scene.get("state_changes", []):
                key = (change["entity_name"].strip().lower(), change["entity_type"])
                entity_state = current_state.setdefault(key, {
                    "entity_name": change["entity_name"],
                    "entity_type": change["entity_type"],
                    "attributes": {},
                })

                previous_state = change["previous_state"] or entity_state["attributes"].get(change["attribute"], "")
                entity_state["attributes"][change["attribute"]] = change["new_state"]

                transitions.append({
                    "state_index": state_index,
                    "book_index": scene.get("book_index"),
                    "chapter_index": scene.get("chapter_index"),
                    "scene_index": scene.get("scene_index"),
                    "entity_name": change["entity_name"],
                    "entity_type": change["entity_type"],
                    "attribute": change["attribute"],
                    "previous_state": previous_state,
                    "new_state": change["new_state"],
                    "change_type": change["change_type"],
                    "evidence": change["evidence"],
                })
                state_index += 1

        latest_state = [
            {
                "entity_name": item["entity_name"],
                "entity_type": item["entity_type"],
                "attributes": dict(item["attributes"]),
            }
            for _, item in sorted(current_state.items(), key=lambda entry: (entry[1]["entity_type"], entry[1]["entity_name"].lower()))
        ]

        return {
            "transitions": transitions,
            "latest_state": latest_state,
        }

    def _scene_key(self, scene: Dict) -> Tuple[int, int, int]:
        return (
            scene.get("book_index", 0),
            scene.get("chapter_index", 0),
            scene.get("scene_index", 0),
        )
