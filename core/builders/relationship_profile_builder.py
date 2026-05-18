"""Builds relationship profiles from scene-level relationship changes."""

from __future__ import annotations

from typing import Dict, List

from core.normalization.helpers import dedupe_strings, stable_pair_slug


class RelationshipProfileBuilder:
    """Aggregate relationship changes into stable pair-level profiles."""

    TRUST_GAIN_MARKERS = ("trust", "support", "ally", "rely", "confide", "rescue", "protect", "closer")
    CONFLICT_MARKERS = ("betray", "fight", "attack", "threat", "resent", "argue", "conflict", "hostile")
    ROMANTIC_MARKERS = ("romantic", "romance", "love", "kiss", "attraction", "closer", "jealous")

    def build(self, *, scene_analyses: List[Dict]) -> List[Dict]:
        grouped: Dict[str, Dict] = {}
        for scene in scene_analyses:
            for item in scene.get("relationship_changes") or []:
                source = (item.get("source_entity") or "").strip()
                target = (item.get("target_entity") or "").strip()
                if not source or not target:
                    continue
                relationship_id = stable_pair_slug("rel", source, target)
                profile = grouped.setdefault(
                    relationship_id,
                    {
                        "relationship_id": relationship_id,
                        "source_character": source,
                        "target_character": target,
                        "relationship_type": (item.get("relationship") or "").strip(),
                        "baseline_dynamic": "",
                        "trust_level": "unknown",
                        "conflict_level": "unknown",
                        "romantic_signal": "unknown",
                        "shared_history": [],
                        "change_log": [],
                        "_signals": {
                            "positive": 0,
                            "conflict": 0,
                            "romantic": 0,
                            "relationship_types": [],
                        },
                    },
                )
                relationship = (item.get("relationship") or "").strip()
                change = (item.get("change") or "").strip()
                evidence = (item.get("evidence") or "").strip()
                profile["change_log"].append({
                    "book_index": scene.get("book_index"),
                    "chapter_index": scene.get("chapter_index"),
                    "scene_index": scene.get("scene_index"),
                    "relationship": relationship,
                    "change": change,
                    "evidence": evidence,
                })
                if not profile["baseline_dynamic"]:
                    profile["baseline_dynamic"] = relationship
                if evidence:
                    profile["shared_history"].append(evidence)
                if relationship:
                    profile["_signals"]["relationship_types"].append(relationship)
                signal_text = " ".join(filter(None, [relationship, change, evidence])).lower()
                if any(marker in signal_text for marker in self.TRUST_GAIN_MARKERS):
                    profile["_signals"]["positive"] += 1
                if any(marker in signal_text for marker in self.CONFLICT_MARKERS):
                    profile["_signals"]["conflict"] += 1
                if any(marker in signal_text for marker in self.ROMANTIC_MARKERS):
                    profile["_signals"]["romantic"] += 1
        for profile in grouped.values():
            profile["shared_history"] = dedupe_strings(profile["shared_history"])
            signal = profile.pop("_signals")
            profile["relationship_type"] = self._most_common(signal["relationship_types"]) or profile["relationship_type"]
            profile["baseline_dynamic"] = profile["baseline_dynamic"] or profile["relationship_type"]
            profile["trust_level"] = self._trust_level(signal["positive"], signal["conflict"])
            profile["conflict_level"] = self._conflict_level(signal["conflict"])
            profile["romantic_signal"] = self._romantic_signal(signal["romantic"])
        return sorted(grouped.values(), key=lambda item: item["relationship_id"])

    def _most_common(self, values: List[str]) -> str:
        counts: Dict[str, int] = {}
        for value in values:
            cleaned = (value or "").strip()
            if cleaned:
                counts[cleaned] = counts.get(cleaned, 0) + 1
        if not counts:
            return ""
        return sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))[0][0]

    def _trust_level(self, positive: int, conflict: int) -> str:
        if positive >= 2 and positive > conflict:
            return "high"
        if positive >= 1 and positive >= conflict:
            return "medium"
        if conflict >= 2:
            return "low"
        return "unknown"

    def _conflict_level(self, conflict: int) -> str:
        if conflict >= 2:
            return "high"
        if conflict == 1:
            return "medium"
        return "low"

    def _romantic_signal(self, romantic: int) -> str:
        if romantic >= 2:
            return "strong"
        if romantic == 1:
            return "possible"
        return "none"
