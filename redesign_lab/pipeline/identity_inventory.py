"""Series-wide identity inventory update stage."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any, Dict, List

from redesign_lab.pipeline.contracts import validate_contract


def empty_identity_inventory(series_id: str) -> Dict[str, Any]:
    payload = {
        "series_id": series_id,
        "canonical_characters": {},
        "alias_map": {},
        "unresolved_mentions": {},
        "rejected_non_characters": [],
        "evidence_log": [],
    }
    return validate_contract("identity_inventory", payload)


class IdentityInventoryUpdater:
    """Accumulate identity memory across chapter batches."""

    def update(self, inventory: Dict[str, Any], extraction: Dict[str, Any]) -> Dict[str, Any]:
        updated = deepcopy(inventory)
        for item in extraction.get("canonical_characters") or []:
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            canonical = updated["canonical_characters"].setdefault(
                name,
                {
                    "name": name,
                    "role": str(item.get("role") or "").strip(),
                    "names_used": [],
                    "mention_count": 0,
                    "evidence": [],
                },
            )
            canonical["mention_count"] += 1
            for used_name in item.get("names_used") or []:
                cleaned = str(used_name or "").strip()
                if cleaned and cleaned not in canonical["names_used"]:
                    canonical["names_used"].append(cleaned)
            canonical["evidence"].append({
                "batch_id": extraction["batch_id"],
                "summary": extraction.get("scene_summary", ""),
            })
            aliases = updated["alias_map"].setdefault(name, [])
            for alias in canonical["names_used"]:
                if alias and alias != name and alias not in aliases:
                    aliases.append(alias)

        for alias_update in extraction.get("alias_updates") or []:
            alias = str(alias_update.get("alias") or "").strip()
            canonical_name = str(alias_update.get("canonical_name") or "").strip()
            if not alias or not canonical_name:
                continue
            aliases = updated["alias_map"].setdefault(canonical_name, [])
            if alias not in aliases and alias != canonical_name:
                aliases.append(alias)

        for mention in extraction.get("character_mentions") or []:
            mention_text = str(mention.get("mention_text") or "").strip()
            canonical_name = str(mention.get("canonical_name") or "").strip()
            if not mention_text or canonical_name:
                continue
            bucket = updated["unresolved_mentions"].setdefault(
                mention_text,
                {"count": 0, "batches": []},
            )
            bucket["count"] += 1
            if extraction["batch_id"] not in bucket["batches"]:
                bucket["batches"].append(extraction["batch_id"])

        for rejected in extraction.get("rejected_identity_candidates") or []:
            cleaned = str(rejected or "").strip()
            if cleaned and cleaned not in updated["rejected_non_characters"]:
                updated["rejected_non_characters"].append(cleaned)

        updated["evidence_log"].append({
            "batch_id": extraction["batch_id"],
            "character_count": len(extraction.get("canonical_characters") or []),
            "mention_count": len(extraction.get("character_mentions") or []),
            "alias_update_count": len(extraction.get("alias_updates") or []),
        })
        return validate_contract("identity_inventory", updated)


def inventory_to_identity_result(inventory: Dict[str, Any]) -> Dict[str, Any]:
    alias_map = {
        canonical: sorted(set(aliases))
        for canonical, aliases in (inventory.get("alias_map") or {}).items()
    }
    alias_history = []
    for canonical, aliases in alias_map.items():
        for alias in aliases:
            alias_history.append({"alias": alias, "canonical_name": canonical, "source": "inventory"})
    return {
        "alias_map": alias_map,
        "rejected_non_characters": sorted(set(inventory.get("rejected_non_characters") or [])),
        "decisions": [],
        "alias_history": alias_history,
        "identity_strategy": "redesign_inventory",
    }

