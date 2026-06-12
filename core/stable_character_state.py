"""Derive durable character canon facts from existing encoder outputs."""

from __future__ import annotations

import re
from typing import Any, Dict, List


class StableCharacterStateBuilder:
    """Build conservative stable character state packets from contract outputs."""

    STABLE_CANON_ATTRIBUTES = {
        "bond",
        "relationship_status",
        "role",
        "title",
        "court",
        "court_role",
        "political_role",
        "family_role",
        "mate_status",
        "allegiance",
        "loyalty",
        "residence",
        "power_status",
    }

    def build(
        self,
        *,
        character_profiles: List[Dict[str, Any]],
        identity_result: Dict[str, Any],
        canon_snapshot: List[Dict[str, Any]] | None = None,
        state_result: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        alias_map = identity_result.get("alias_map") or {}
        by_name: Dict[str, Dict[str, Any]] = {}

        def ensure(name: str) -> Dict[str, Any]:
            entry = by_name.setdefault(name, {"entity_name": name, "attributes": {}})
            return entry

        for snapshot in canon_snapshot or []:
            if snapshot.get("entity_type") != "character":
                continue
            name = self._canonical_name(str(snapshot.get("entity_name") or "").strip(), alias_map)
            if not name:
                continue
            entry = ensure(name)
            self._merge_attributes(entry["attributes"], snapshot.get("attributes") or {})

        latest_state = (state_result or {}).get("latest_state") or []
        for row in latest_state:
            if row.get("entity_type") != "character":
                continue
            name = self._canonical_name(str(row.get("entity_name") or "").strip(), alias_map)
            if not name:
                continue
            entry = ensure(name)
            self._merge_attributes(entry["attributes"], row.get("attributes") or {})

        for profile in character_profiles or []:
            name = self._canonical_name(str(profile.get("canonical_name") or "").strip(), alias_map)
            if not name:
                continue
            entry = ensure(name)
            self._merge_attributes(entry["attributes"], profile.get("state_at_latest") or {})
            self._merge_attributes(entry["attributes"], self._infer_from_profile(profile))
            self._merge_attributes(
                entry["attributes"],
                self._infer_from_aliases(alias_map.get(name) or []),
                overwrite=False,
            )

        result: List[Dict[str, Any]] = []
        for entry in by_name.values():
            attrs = self._stable_only(entry.get("attributes") or {})
            if not attrs:
                continue
            result.append({"entity_name": entry["entity_name"], "attributes": attrs})
        result.sort(key=lambda item: item["entity_name"].lower())
        return result

    def _canonical_name(self, name: str, alias_map: Dict[str, List[str]]) -> str:
        if not name:
            return ""
        lowered = name.lower()
        for canonical, aliases in alias_map.items():
            all_names = [canonical, *(aliases or [])]
            if lowered in {str(item or "").strip().lower() for item in all_names}:
                return canonical
        return name

    def _stable_only(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        stable: Dict[str, Any] = {}
        for key, value in attrs.items():
            if key not in self.STABLE_CANON_ATTRIBUTES:
                continue
            if not isinstance(value, str):
                continue
            cleaned = value.strip()
            if not cleaned:
                continue
            stable[key] = cleaned
        return stable

    def _merge_attributes(self, target: Dict[str, Any], source: Dict[str, Any], *, overwrite: bool = False) -> None:
        for raw_key, raw_value in (source or {}).items():
            key = self._normalize_attr_key(raw_key)
            if key not in self.STABLE_CANON_ATTRIBUTES:
                continue
            if not isinstance(raw_value, str):
                continue
            value = raw_value.strip()
            if not value:
                continue
            if overwrite or not target.get(key):
                target[key] = value

    def _normalize_attr_key(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        return text.replace(" ", "_").replace("-", "_").replace("/", "_")

    def _infer_from_aliases(self, aliases: List[str]) -> Dict[str, str]:
        text = " ".join(str(item or "") for item in aliases if str(item or "").strip())
        if not text:
            return {}
        lowered = text.lower()
        attrs: Dict[str, str] = {}
        if "high lord of spring" in lowered:
            attrs["title"] = "High Lord"
            attrs["court"] = "Spring Court"
        elif "high lord of the night court" in lowered or "high lord of night" in lowered:
            attrs["title"] = "High Lord"
            attrs["court"] = "Night Court"
        elif "high lady of the night court" in lowered:
            attrs["title"] = "High Lady"
            attrs["court"] = "Night Court"
        return attrs

    def _infer_from_profile(self, profile: Dict[str, Any]) -> Dict[str, str]:
        attrs: Dict[str, str] = {}
        profile_name = str(profile.get("canonical_name") or "").strip()
        primary_tokens = [token for token in profile_name.split() if token]
        first_token = primary_tokens[0] if primary_tokens else ""

        base_text = " ".join(
            chunk for chunk in [
                profile.get("core_description") or "",
                " ".join(profile.get("traits") or []),
            ] if chunk
        ).strip()
        if not base_text and not (profile.get("relationship_refs") or []):
            return attrs
        lowered_base = base_text.lower()

        title_match = re.search(r"\b(high lord|high lady|lord|lady|queen|king)\b(?!')", lowered_base)
        if title_match:
            attrs["title"] = title_match.group(1).title()

        if "spring court" in lowered_base:
            attrs.setdefault("court", "Spring Court")
        elif "night court" in lowered_base:
            attrs.setdefault("court", "Night Court")
        elif "day court" in lowered_base:
            attrs.setdefault("court", "Day Court")
        elif "dawn court" in lowered_base:
            attrs.setdefault("court", "Dawn Court")
        elif "autumn court" in lowered_base:
            attrs.setdefault("court", "Autumn Court")
        elif "winter court" in lowered_base:
            attrs.setdefault("court", "Winter Court")
        elif "summer court" in lowered_base:
            attrs.setdefault("court", "Summer Court")

        role_patterns = [
            (r"\bspymaster\b", "spymaster"),
            (r"\bshadowsinger\b", "shadowsinger"),
            (r"\bgeneral\b", "general"),
            (r"\bpriestess\b", "priestess"),
            (r"\bstrategist\b", "strategist"),
        ]
        for pattern, role in role_patterns:
            if re.search(pattern, lowered_base):
                attrs.setdefault("role", role)
                break

        if "emissary" in lowered_base:
            attrs.setdefault("political_role", "emissary")
        elif "investigate human queens" in lowered_base:
            attrs.setdefault("political_role", "investigating human queens")

        relation_text = " ".join(
            " ".join(str((rel or {}).get(field) or "") for field in ("relationship", "change", "evidence"))
            for rel in (profile.get("relationship_refs") or [])[:8]
        )
        relation_lower = relation_text.lower()

        if "former betrothed" in relation_lower or "engagement ended" in relation_lower:
            target = self._relationship_target(profile, {"former betrothed", "engagement ended"})
            attrs.setdefault(
                "relationship_status",
                f"former betrothed to {target}" if target else "former betrothed",
            )
        elif "partnered with cassian" in relation_lower:
            attrs.setdefault("relationship_status", "partnered with Cassian")
        elif "romantic" in relation_lower and "cassian" in relation_lower:
            attrs.setdefault("relationship_status", "romantically involved with Cassian")

        if "high lady's sister" in lowered_base:
            attrs.setdefault("family_role", "sister")

        if "cauldron-made" in lowered_base or "cauldron\u2011made" in lowered_base:
            attrs.setdefault("power_status", "Made")

        for event in (profile.get("important_history") or [])[:8]:
            summary = str((event or {}).get("summary") or "")
            lowered_summary = summary.lower()
            if (
                first_token
                and first_token.lower() in lowered_summary
                and "human emissary" in lowered_summary
            ):
                attrs.setdefault("political_role", "human emissary")
                break

        if "allied with" in relation_lower:
            match = re.search(r"allied with\s+([A-Z][A-Za-z'\\-]+(?:\s+[A-Z][A-Za-z'\\-]+){0,2})", relation_text)
            if match:
                attrs.setdefault("allegiance", match.group(1))

        return attrs

    def _relationship_target(self, profile: Dict[str, Any], phrases: set[str]) -> str:
        for rel in profile.get("relationship_refs") or []:
            haystack = " ".join(
                str((rel or {}).get(field) or "")
                for field in ("relationship", "change", "evidence")
            ).lower()
            if any(phrase in haystack for phrase in phrases):
                return str(rel.get("target_entity") or "").strip()
        return ""
