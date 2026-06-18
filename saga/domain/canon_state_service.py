from typing import Dict, List, Optional, Tuple


class CanonStateService:
    """
    Reconstructs canonical entity state at a chosen point in scene order or state order.
    """

    def snapshot_at(
        self,
        transitions: List[Dict],
        *,
        state_index: Optional[int] = None,
        scene_ref: Optional[Tuple[int, int, int]] = None,
    ) -> List[Dict]:
        filtered = []

        for transition in sorted(transitions, key=lambda item: item.get("state_index", 0)):
            if state_index is not None and transition.get("state_index", 0) > state_index:
                break

            if scene_ref is not None and self._scene_key(transition) > scene_ref:
                break

            filtered.append(transition)

        state_by_entity: Dict[Tuple[str, str], Dict] = {}

        for transition in filtered:
            key = (transition["entity_name"].strip().lower(), transition["entity_type"])
            state_by_entity.setdefault(key, {
                "entity_name": transition["entity_name"],
                "entity_type": transition["entity_type"],
                "attributes": {},
            })
            state_by_entity[key]["attributes"][transition["attribute"]] = transition["new_state"]

        return [
            {
                "entity_name": item["entity_name"],
                "entity_type": item["entity_type"],
                "attributes": dict(item["attributes"]),
            }
            for _, item in sorted(state_by_entity.items(), key=lambda entry: (entry[1]["entity_type"], entry[1]["entity_name"].lower()))
        ]

    def _scene_key(self, item: Dict) -> Tuple[int, int, int]:
        return (
            item.get("book_index", 0),
            item.get("chapter_index", 0),
            item.get("scene_index", 0),
        )
