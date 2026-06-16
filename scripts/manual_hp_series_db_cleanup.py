from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select

from services.entity_visual_prompt_service import EntityVisualPromptService
from sql_store.curation import SagaAnalysisCurator
from sql_store.models import (
    Book,
    CharacterProfile,
    DashboardJob,
    DashboardJobLog,
    Entity,
    Event,
    GeneratedImage,
    IdentityAlias,
    IdentityCharacter,
    IdentityReferenceEntity,
    IdentitySeries,
    StableCharacterState,
    VisualPrompt,
)
from sql_store.persistence import SagaSQLiteStore


DB_PATH = Path("analysis_outputs/saga_canonical.sqlite3")
SERIES_ID = "hp1-full-e2e-20260615"
IDENTITY_PROVIDER = "booknlp_clean"

PREFERRED_IDENTITY_DISPLAY_OVERRIDES = {
    "char_harry": "Harry Potter",
    "char_ron": "Ron Weasley",
    "char_hermione": "Hermione Granger",
    "char_dumbledore": "Albus Dumbledore",
    "char_hagrid": "Rubeus Hagrid",
    "char_mcgonagall": "Professor McGonagall",
    "char_snape": "Severus Snape",
    "char_sirius": "Sirius Black",
    "char_lupin": "Remus Lupin",
    "char_draco": "Draco Malfoy",
    "char_neville": "Neville Longbottom",
    "char_ginny": "Ginny Weasley",
    "char_fred": "Fred Weasley",
    "char_george": "George Weasley",
    "char_percy": "Percy Weasley",
    "char_bill": "Bill Weasley",
    "char_charlie": "Charlie Weasley",
    "char_molly": "Molly Weasley",
    "char_arthur": "Arthur Weasley",
    "char_cho": "Cho Chang",
    "char_luna": "Luna Lovegood",
    "char_umbridge": "Dolores Umbridge",
    "char_fudge": "Cornelius Fudge",
    "char_fleur": "Fleur Delacour",
    "char_cedric": "Cedric Diggory",
    "char_voldemort": "Lord Voldemort",
}

PERSON_TITLES = {
    "mr",
    "mrs",
    "ms",
    "miss",
    "sir",
    "madam",
    "madame",
    "professor",
    "prof",
    "aunt",
    "uncle",
    "lord",
    "lady",
    "dr",
}

BAD_ALIAS_WORDS = {
    "both",
    "neither",
    "murdering",
    "dog",
    "dead",
    "most",
    "had",
    "kiss",
    "magic",
    "memoriam",
    "improved",
    "phlegm",
    "taunt",
    "sobbing",
    "terrified-looking",
    "fanged",
    "young",
    "old",
    "apparently",
    "stunned",
    "professors",
    "reckon",
    "had",
    "that",
}

FORCE_ENTITY_TYPES = {
    "professor mcgonagall": "character",
    "minerva mcgonagall": "character",
    "professor flitwick": "character",
    "flitwick": "character",
    "harry": "character",
    "harry potter": "character",
    "ron": "character",
    "ron weasley": "character",
    "hermione": "character",
    "hermione granger": "character",
    "albus dumbledore": "character",
    "dumbledore": "character",
    "severus snape": "character",
    "snape": "character",
    "percy": "character",
    "dudley": "character",
    "vernon dursley": "character",
    "mr dursley": "character",
    "mrs dursley": "character",
    "petunia dursley": "character",
    "aunt petunia": "character",
    "dudley dursley": "character",
    "uncle vernon": "character",
    "fudge": "character",
    "cho": "character",
    "ginny weasley": "character",
    "bellatrix": "character",
    "tonks": "character",
    "draco malfoy": "character",
    "dolores umbridge": "character",
    "colin creevey": "character",
    "mrs figg": "character",
    "hedwig": "creature",
    "dobby": "creature",
    "kreacher": "creature",
    "griphook": "creature",
    "fang": "creature",
    "firenze": "creature",
    "peeves": "creature",
    "crookshanks": "creature",
    "mrs. norris": "creature",
    "mrs norris": "creature",
    "nagini": "creature",
    "errol": "creature",
    "fluffy": "creature",
    "norbert": "creature",
    "three-headed dog": "creature",
    "quidditch": "other",
    "gryffindor": "organization",
    "hogwarts": "location",
    "gringotts": "location",
    "hospital wing": "location",
    "gryffindor tower": "location",
    "astronomy tower": "location",
    "hogs head": "location",
    "hog's head": "location",
    "dormitory": "location",
    "dungeon": "location",
    "lake": "location",
    "cave": "location",
    "hogwarts express": "object",
    "wand": "object",
    "invisibility cloak": "object",
    "golden snitch": "object",
    "bludger": "object",
    "letter": "object",
    "quaffle": "object",
    "bezoar": "object",
    "nimbus two thousand": "object",
    "polyjuice potion": "object",
    "boat": "object",
    "blood": "object",
    "advanced potion-making": "object",
    "curtains": "object",
    "ink bottle": "object",
    "floo network": "other",
    "staircase": "location",
    "spiral staircase": "location",
    "london": "location",
}

GENERIC_DROP_NAMES = {
    "number",
    "privet",
    "bakery",
    "office",
    "crowd",
    "students",
    "books",
    "witch",
}

LOCATION_MERGES = {
    "privet drive corner": "Privet Drive",
    "privet drive wall": "Privet Drive",
    "dursley garden wall": "Privet Drive",
    "number four privet drive": "Privet Drive",
    "number": "Privet Drive",
    "privet": "Privet Drive",
    "charms corridor near trophy room": "Charms Corridor",
    "portrait of the fat lady": "Fat Lady Portrait",
}

OBJECT_MERGES = {
    "advanced potion-making book": "Advanced Potion-Making",
    "horcrux locket (false)": "Fake Horcrux Locket",
}


def _loads(value: Any) -> Any:
    if value in (None, "", []):
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return None


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _norm(value: Any) -> str:
    return _clean_text(value).lower()


def _is_valid_person_alias(alias: str) -> bool:
    text = _clean_text(alias)
    if not text:
        return False
    words = text.split()
    if len(words) > 4:
        return False
    lowered = text.lower()
    if any(word in lowered for word in BAD_ALIAS_WORDS):
        return False
    if re.search(r"[^A-Za-z0-9'’\\-\\. ]", text):
        return False
    allowed_lowercase = {"de", "del", "van", "von", "the"} | PERSON_TITLES
    for word in words:
        token = word.strip(".").lower()
        if token in allowed_lowercase:
            continue
        if not word[:1].isupper():
            return False
    return True


def _preferred_display_name(display_name: str, aliases: list[str]) -> str:
    cleaned_aliases = []
    for alias in aliases:
        alias_text = _clean_text(alias)
        if alias_text and alias_text.lower() not in {item.lower() for item in cleaned_aliases}:
            cleaned_aliases.append(alias_text)
    current = _clean_text(display_name)
    valid = [alias for alias in cleaned_aliases if _is_valid_person_alias(alias)]
    titled = [alias for alias in valid if alias.split()[0].strip(".").lower() in PERSON_TITLES]
    untitled = [alias for alias in valid if alias not in titled]
    candidates = untitled or valid or cleaned_aliases or ([current] if current else [])
    if not candidates:
        return current
    if current and len(current.split()) >= 2 and _is_valid_person_alias(current):
        return current
    for alias in sorted(candidates, key=lambda item: (-len(item.split()), -len(item))):
        if current and current.lower() in alias.lower().split():
            return alias
    return sorted(candidates, key=lambda item: (-len(item.split()), -len(item)))[0]


def _merge_lists(*values: Any) -> list[Any]:
    merged: list[Any] = []
    seen: set[str] = set()
    for value in values:
        rows = value if isinstance(value, list) else []
        for item in rows:
            key = json.dumps(item, sort_keys=True, ensure_ascii=False) if isinstance(item, (dict, list)) else repr(item)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged


def _entity_richness(entity: Entity) -> tuple[int, int, int]:
    init_payload = _loads(entity.initial_physical_description) or {}
    first_payload = _loads(entity.first_appearance_profile) or {}
    typed = _loads(entity.typed_attributes) or {}
    return (
        int(entity.mention_count or 0),
        len(json.dumps(first_payload, ensure_ascii=False)),
        len(json.dumps(typed, ensure_ascii=False)) + len(json.dumps(init_payload, ensure_ascii=False)),
    )


def _merge_entity_rows(target: Entity, source: Entity) -> None:
    target.mention_count = int(target.mention_count or 0) + int(source.mention_count or 0)
    target.entity_context = _clean_text(" | ".join(part for part in [target.entity_context or "", source.entity_context or ""] if _clean_text(part)))
    target.descriptions = _merge_lists(_loads(target.descriptions), _loads(source.descriptions))
    target.state_changes = _merge_lists(_loads(target.state_changes), _loads(source.state_changes))
    target.event_links = _merge_lists(_loads(target.event_links), _loads(source.event_links))
    target.visual_change_log = _merge_lists(_loads(target.visual_change_log), _loads(source.visual_change_log))
    target.analysis_quality_flags = _merge_lists(_loads(target.analysis_quality_flags), _loads(source.analysis_quality_flags))
    for field in [
        "initial_physical_description",
        "first_appearance_profile",
        "typed_attributes",
        "latest_world_state",
        "narrative_roles",
        "metadata_json",
    ]:
        current = _loads(getattr(target, field))
        incoming = _loads(getattr(source, field))
        if (not current or current == {}) and incoming:
            setattr(target, field, incoming)
    if not _clean_text(target.baseline_visual_prompt) and _clean_text(source.baseline_visual_prompt):
        target.baseline_visual_prompt = source.baseline_visual_prompt
    if not _clean_text(target.generated_image_path) and _clean_text(source.generated_image_path):
        target.generated_image_path = source.generated_image_path
    if target.generated_image_bytes is None and source.generated_image_bytes is not None:
        target.generated_image_bytes = source.generated_image_bytes
    if _entity_richness(source) > _entity_richness(target):
        target.first_seen_book_index = source.first_seen_book_index
        target.first_seen_chapter_index = source.first_seen_chapter_index
        target.first_seen_scene_index = source.first_seen_scene_index


def _update_name_in_jsonish(value: Any, rename_map: dict[str, str]) -> Any:
    payload = _loads(value)
    if payload is None:
        return value
    if isinstance(payload, list):
        updated = []
        seen: set[str] = set()
        for item in payload:
            if isinstance(item, str):
                renamed = rename_map.get(_norm(item), _clean_text(item))
                key = renamed.lower()
                if key in seen:
                    continue
                seen.add(key)
                updated.append(renamed)
            else:
                updated.append(item)
        return updated
    if isinstance(payload, dict):
        updated = {}
        for key, item in payload.items():
            if isinstance(item, str):
                updated[key] = rename_map.get(_norm(item), item)
            elif isinstance(item, list):
                updated[key] = _update_name_in_jsonish(item, rename_map)
            else:
                updated[key] = item
        return updated
    return payload


def _fix_identity_series(session) -> tuple[dict[str, str], dict[str, str]]:
    series = session.execute(select(IdentitySeries).where(IdentitySeries.series_id == SERIES_ID)).scalar_one_or_none()
    if series is None:
        return {}, {}

    characters = session.execute(
        select(IdentityCharacter).where(IdentityCharacter.identity_series_id == series.id)
    ).scalars().all()
    alias_rows = session.execute(
        select(IdentityAlias).where(IdentityAlias.identity_series_id == series.id)
    ).scalars().all()

    target_to_display: dict[str, str] = {}
    alias_to_display: dict[str, str] = {}
    characters = sorted(characters, key=lambda row: int(row.mention_count or 0), reverse=True)
    for character in characters:
        payload = dict(_loads(character.payload_json) or {})
        aliases = list(payload.get("aliases") or [])
        preferred = PREFERRED_IDENTITY_DISPLAY_OVERRIDES.get(str(character.character_id or "").strip()) or _preferred_display_name(str(character.display_name or ""), aliases)
        valid_aliases = [alias for alias in aliases if _is_valid_person_alias(alias)]
        if preferred and preferred not in valid_aliases:
            valid_aliases.insert(0, preferred)
        if character.display_name and character.display_name not in valid_aliases and _is_valid_person_alias(str(character.display_name)):
            valid_aliases.insert(0, str(character.display_name))
        valid_aliases = list(dict.fromkeys(_clean_text(alias) for alias in valid_aliases if _clean_text(alias)))
        character.display_name = preferred or character.display_name
        payload["display_name"] = character.display_name
        payload["aliases"] = valid_aliases
        character.payload_json = payload
        target_to_display[str(character.character_id)] = str(character.display_name or "")
        for alias in valid_aliases:
            alias_to_display.setdefault(_norm(alias), str(character.display_name or ""))

    session.execute(delete(IdentityAlias).where(IdentityAlias.identity_series_id == series.id))
    for alias_key, display_name in sorted(alias_to_display.items()):
        target_id = None
        for character in characters:
            if str(character.display_name or "") == display_name:
                target_id = str(character.character_id or "")
                break
        session.add(
            IdentityAlias(
                identity_series_id=series.id,
                alias_key=alias_key,
                target_character_id=target_id or None,
            )
        )
    return alias_to_display, target_to_display


def _cleanup_book(session, book: Book, alias_to_display: dict[str, str]) -> None:
    rows = session.execute(select(Entity).where(Entity.book_id == book.id)).scalars().all()
    rename_map: dict[str, str] = {}
    delete_ids: set[str] = set()
    planned: dict[str, tuple[str, str]] = {}

    # First pass: normalize names, force obvious types, drop obvious junk.
    for row in rows:
        name = _clean_text(row.canonical_name)
        lowered = name.lower()
        if lowered in GENERIC_DROP_NAMES and int(row.mention_count or 0) <= 1:
            delete_ids.add(row.id)
            continue
        if lowered in OBJECT_MERGES:
            desired_name = OBJECT_MERGES[lowered]
            desired_type = "object"
            planned[row.id] = (desired_name, desired_type)
            rename_map[lowered] = desired_name
            continue
        elif lowered in alias_to_display and row.entity_type.lower() == "character":
            preferred = alias_to_display[lowered]
            desired_name = preferred or name
            desired_type = row.entity_type.lower()
        else:
            desired_name = name
            desired_type = row.entity_type.lower()
        forced_type = FORCE_ENTITY_TYPES.get(_norm(desired_name))
        if forced_type:
            desired_type = forced_type
        if lowered in LOCATION_MERGES:
            desired_name = LOCATION_MERGES[lowered]
            desired_type = "location"
        planned[row.id] = (_clean_text(desired_name), _clean_text(desired_type).lower() or row.entity_type.lower())
        rename_map[lowered] = _clean_text(desired_name)

    # Apply desired canonical names/types through merge buckets first so uniqueness stays intact.
    buckets: dict[tuple[str, str], list[Entity]] = defaultdict(list)
    for row in rows:
        if row.id in delete_ids:
            continue
        desired_name, desired_type = planned.get(row.id, (_clean_text(row.canonical_name), row.entity_type.lower()))
        buckets[(desired_type, _norm(desired_name))].append(row)
    for (desired_type, desired_name_key), bucket in buckets.items():
        bucket = [row for row in bucket if row.id not in delete_ids]
        if not bucket:
            continue
        bucket = sorted(bucket, key=_entity_richness, reverse=True)
        target = bucket[0]
        for source in bucket[1:]:
            source.canonical_name = f"__merge__{source.id}"
        if len(bucket) > 1:
            session.flush()
            target = session.get(Entity, target.id)
        target.canonical_name = planned.get(target.id, (_clean_text(target.canonical_name), desired_type))[0]
        target.entity_type = desired_type
        rename_map[_norm(target.canonical_name)] = _clean_text(target.canonical_name)
        for source in bucket[1:]:
            source = session.get(Entity, source.id)
            _merge_entity_rows(target, source)
            rename_map[_norm(source.canonical_name)] = _clean_text(target.canonical_name)
            delete_ids.add(source.id)
            for profile in session.execute(select(CharacterProfile).where(CharacterProfile.entity_id == source.id)).scalars().all():
                profile.entity_id = target.id
                profile.character_name = target.canonical_name
            for state in session.execute(select(StableCharacterState).where(StableCharacterState.entity_id == source.id)).scalars().all():
                state.entity_id = target.id

    for row in rows:
        if row.id in delete_ids:
            session.delete(row)

    session.flush()
    rows = session.execute(select(Entity).where(Entity.book_id == book.id)).scalars().all()

    # Second pass: merge same-type duplicates after normalization.
    grouped: dict[tuple[str, str], list[Entity]] = defaultdict(list)
    for row in rows:
        if row.id in delete_ids:
            continue
        grouped[(row.entity_type.lower(), _norm(row.canonical_name))].append(row)
    for (_, _), bucket in grouped.items():
        if len(bucket) <= 1:
            continue
        bucket = sorted(bucket, key=_entity_richness, reverse=True)
        target = bucket[0]
        for source in bucket[1:]:
            source.canonical_name = f"__merge__{source.id}"
        session.flush()
        target = session.get(Entity, target.id)
        if target is None:
            continue
        for source in bucket[1:]:
            source = session.get(Entity, source.id)
            if source is None:
                continue
            _merge_entity_rows(target, source)
            rename_map[_norm(source.canonical_name)] = _clean_text(target.canonical_name)
            delete_ids.add(source.id)
            for profile in session.execute(select(CharacterProfile).where(CharacterProfile.entity_id == source.id)).scalars().all():
                profile.entity_id = target.id
                profile.character_name = target.canonical_name
            for state in session.execute(select(StableCharacterState).where(StableCharacterState.entity_id == source.id)).scalars().all():
                state.entity_id = target.id

    session.flush()
    entities = session.execute(select(Entity).where(Entity.book_id == book.id)).scalars().all()
    type_map = { _norm(entity.canonical_name): entity.entity_type.lower() for entity in entities }
    canonical_map = { _norm(entity.canonical_name): _clean_text(entity.canonical_name) for entity in entities }

    # Third pass: normalize event payloads to the cleaned entity registry.
    for event in session.execute(select(Event).where(Event.book_id == book.id)).scalars().all():
        payload = dict(_loads(event.payload_json) or {})
        title = _clean_text(payload.get("title") or payload.get("summary") or event.description or "")
        event.description = _clean_text(payload.get("description") or title or event.description or "")
        event.reason = _clean_text(payload.get("reason") or event.reason or "")
        event.outcome = _clean_text(payload.get("outcome") or event.outcome or "")
        event.event_type = _clean_text(payload.get("type") or event.event_type or "action").lower()

        collected: dict[str, list[str]] = {
            "characters": [],
            "creatures_involved": [],
            "objects_involved": [],
            "locations_involved": [],
            "organizations_involved": [],
        }
        seen_by_bucket: dict[str, set[str]] = {key: set() for key in collected}

        def push(bucket: str, raw_name: str) -> None:
            lowered_raw = _norm(raw_name)
            lowered_raw = _norm(LOCATION_MERGES.get(lowered_raw, OBJECT_MERGES.get(lowered_raw, lowered_raw)))
            cleaned_name = canonical_map.get(lowered_raw, alias_to_display.get(lowered_raw, _clean_text(raw_name)))
            if not cleaned_name:
                return
            lowered_name = cleaned_name.lower()
            actual_type = FORCE_ENTITY_TYPES.get(lowered_name) or type_map.get(lowered_name)
            if actual_type == "character":
                bucket = "characters"
            elif actual_type == "creature":
                bucket = "creatures_involved"
            elif actual_type == "location":
                bucket = "locations_involved"
            elif actual_type == "organization":
                bucket = "organizations_involved"
            elif actual_type == "object":
                bucket = "objects_involved"
            if lowered_name in seen_by_bucket[bucket]:
                return
            seen_by_bucket[bucket].add(lowered_name)
            collected[bucket].append(cleaned_name)

        for bucket in collected:
            for name in payload.get(bucket) or []:
                if isinstance(name, str):
                    push(bucket, name)

        participants = payload.get("participants") or []
        for name in participants:
            if isinstance(name, str):
                push("characters", name)

        location_payload = payload.get("location") or {}
        if isinstance(location_payload, dict):
            location_name = _clean_text(location_payload.get("name") or payload.get("event_location") or "")
        else:
            location_name = _clean_text(location_payload or payload.get("event_location") or "")
        if location_name:
            push("locations_involved", location_name)
            location_name = collected["locations_involved"][0] if collected["locations_involved"] else location_name

        entities_involved: list[str] = []
        for bucket in ["characters", "creatures_involved", "objects_involved", "locations_involved", "organizations_involved"]:
            for name in collected[bucket]:
                if name.lower() not in {item.lower() for item in entities_involved}:
                    entities_involved.append(name)

        payload["title"] = title or event.description
        payload["summary"] = title or event.description
        payload["description"] = event.description
        payload["reason"] = event.reason
        payload["outcome"] = event.outcome
        payload["type"] = event.event_type
        payload["participants"] = collected["characters"]
        payload["characters"] = collected["characters"]
        payload["creatures_involved"] = collected["creatures_involved"]
        payload["objects_involved"] = collected["objects_involved"]
        payload["locations_involved"] = collected["locations_involved"]
        payload["organizations_involved"] = collected["organizations_involved"]
        payload["entities_involved"] = entities_involved
        payload["event_location"] = location_name
        payload["location"] = {"name": location_name} if location_name else {}

        event.entities_involved = entities_involved
        event.payload_json = payload

    # Fourth pass: fix character profile naming after merges.
    for profile in session.execute(select(CharacterProfile).where(CharacterProfile.book_id == book.id)).scalars().all():
        if profile.entity_id:
            entity = session.get(Entity, profile.entity_id)
            if entity is not None:
                profile.character_name = entity.canonical_name

    # Remove stale prompt/image rows; they will be regenerated.
    session.execute(delete(GeneratedImage).where(GeneratedImage.book_id == book.id))
    session.execute(delete(VisualPrompt).where(VisualPrompt.book_id == book.id))


def main() -> None:
    store = SagaSQLiteStore(DB_PATH)
    with store.session_factory() as session:
        alias_to_display, _ = _fix_identity_series(session)
        books = session.execute(
            select(Book)
            .where(Book.series_id == SERIES_ID)
            .order_by(Book.book_index.asc())
        ).scalars().all()
        for book in books:
            _cleanup_book(session, book, alias_to_display)
        # Clear stale dashboard job noise for old failed jobs in this manual pass.
        session.execute(delete(DashboardJobLog).where(DashboardJobLog.job_id.in_(select(DashboardJob.id))))
        session.commit()

    curator = SagaAnalysisCurator(store)
    curator.curate_all_books()

    prompt_service = EntityVisualPromptService(store)
    with store.session_factory() as session:
        books = session.execute(
            select(Book)
            .where(Book.series_id == SERIES_ID)
            .order_by(Book.book_index.asc())
        ).scalars().all()
    for book in books:
        prompt_service.build_book_prompts(f"db://book/{book.id}", overwrite=True)

    print(f"Cleanup complete for series {SERIES_ID} using {IDENTITY_PROVIDER}.")


if __name__ == "__main__":
    main()
