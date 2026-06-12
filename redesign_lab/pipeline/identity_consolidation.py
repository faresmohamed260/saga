"""Identity consolidation stage for redesign inventory."""

from __future__ import annotations

from typing import Any, Dict

from core.canon_normalization import CanonicalEntityNormalizer
from redesign_lab.pipeline.contracts import validate_contract
from services.web_entity_hint_service import WebEntityHintService


class IdentityConsolidator:
    """Collapse aliases and duplicate canonicals after inventory accumulation."""

    def __init__(self, *, use_web_hints: bool = True) -> None:
        self.normalizer = CanonicalEntityNormalizer()
        self.use_web_hints = use_web_hints
        self.web_hints = WebEntityHintService()

    def consolidate(self, inventory: Dict[str, Any]) -> Dict[str, Any]:
        canonical_names = list((inventory.get("canonical_characters") or {}).keys())
        alias_map = inventory.get("alias_map") or {}
        hints = self.web_hints.load_series_hints(inventory.get("series_id", ""), canonical_names) if self.use_web_hints else {}
        merge_map, _unresolved = self.normalizer.build_merge_map(
            names=canonical_names,
            alias_map=alias_map,
            hints=hints,
        )
        consolidated_aliases: Dict[str, list[str]] = {}
        consolidated_characters = set()
        for name in canonical_names:
            target = merge_map.get(name) or name
            consolidated_characters.add(target)
            aliases = consolidated_aliases.setdefault(target, [])
            for alias in alias_map.get(name, []):
                resolved = merge_map.get(alias) or alias
                if resolved != target and alias not in aliases:
                    aliases.append(alias)
        payload = {
            "series_id": inventory["series_id"],
            "canonical_characters": sorted(consolidated_characters),
            "alias_map": {key: sorted(set(value)) for key, value in consolidated_aliases.items()},
            "rejected_non_characters": sorted(set(inventory.get("rejected_non_characters") or [])),
            "unresolved_mentions": inventory.get("unresolved_mentions") or {},
        }
        return validate_contract("identity_consolidation_result", payload)
