from __future__ import annotations

import json
import base64
import hmac
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
import uuid
import webbrowser
import hashlib
import secrets
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import case, delete, func, select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import defer

from saga.domain.builders.relationship_profile_builder import RelationshipProfileBuilder
from saga.providers.codex_session_store import CodexSessionStore
from saga.providers.general_compute_account_rotator import GeneralComputeAccountRotator
from saga.providers.llm_provider_registry import (
    GENERAL_COMPUTE_PROVIDER,
    OLLAMA_PROVIDER,
    read_llm_provider_config,
    save_llm_provider_config,
)
from saga.providers.llm_client import LLMClient
from saga.providers.status.service import (
    read_latest_inference_status_payload,
    read_latest_provider_status_payload,
    refresh_latest_provider_statuses as refresh_provider_statuses_service,
)
from saga.providers.status.shared import MODAL_POOL_PROVIDER
from saga.identity.series_identity_provider import (
    build_series_pipeline_identity,
    generate_book_identity_bundle,
)
from saga.services.comfyui_character_sheet_service import (
    DEFAULT_NEGATIVE_PROMPT,
    ComfyUICharacterSheetService,
    render_manifest_path_for_contract,
    render_output_dir_for_contract,
)
from saga.providers.inference_registry import (
    COREF_CAPABILITY,
    IMAGE_CAPABILITY,
    MODAL_COMFYUI_PROVIDER,
    MODAL_KOKORO_PROVIDER,
    MODAL_XCORE_PROVIDER,
    SPEECH_CAPABILITY,
    active_provider_name_for_capability,
    provider_capability,
    read_inference_provider_config,
    read_inference_selection,
    resolve_provider,
    save_inference_provider_config,
    save_inference_selection,
)
from saga.providers.inference_smoke import run_provider_smoke
from saga.agents.visual_prompt_schema import (
    compile_creature_negative_prompt,
    compile_location_negative_prompt,
    compile_object_negative_prompt,
)
from integrations.kokoro_tts.pool_manager import ModalTTSPoolManager
from saga.services.audiobook_generation_service import AudiobookGenerationService
from saga.services.database_analysis_run_service import DatabaseAnalysisRunService
from saga.services.database_decoder_service import DatabaseDecoderService
from saga.services.generated_story_epub_service import GeneratedStoryEpubService
from saga.services.image_thumbnail_service import ensure_thumbnail
from saga.storage.database import get_database_url
from saga.storage.persistence import SagaSQLiteStore
from saga.storage.models import Book as SqlBook
from saga.storage.models import AudiobookChapter as SqlAudiobookChapter
from saga.storage.models import CharacterProfile as SqlCharacterProfile
from saga.storage.models import CharacterVisualBaseline as SqlCharacterVisualBaseline
from saga.storage.models import CharacterVisualSceneState as SqlCharacterVisualSceneState
from saga.storage.models import Chapter as SqlChapter
from saga.storage.models import CreatureVisualBaseline as SqlCreatureVisualBaseline
from saga.storage.models import DashboardJob as SqlDashboardJob
from saga.storage.models import Entity as SqlEntity
from saga.storage.models import Event as SqlEvent
from saga.storage.models import GeneratedImage as SqlGeneratedImage
from saga.storage.models import GeneratedStory as SqlGeneratedStory
from saga.storage.models import IdentityAlias as SqlIdentityAlias
from saga.storage.models import IdentityBook as SqlIdentityBook
from saga.storage.models import IdentityCharacter as SqlIdentityCharacter
from saga.storage.models import IdentityNarrator as SqlIdentityNarrator
from saga.storage.models import IdentityReferenceEntity as SqlIdentityReferenceEntity
from saga.storage.models import IdentitySeries as SqlIdentitySeries
from saga.storage.models import LocationSceneState as SqlLocationSceneState
from saga.storage.models import LocationVisualBaseline as SqlLocationVisualBaseline
from saga.storage.models import ObjectSceneState as SqlObjectSceneState
from saga.storage.models import ObjectVisualBaseline as SqlObjectVisualBaseline
from saga.storage.models import Series as SqlSeries
from saga.storage.models import Scene as SqlScene
from saga.storage.models import StableCharacterState as SqlStableCharacterState
from saga.storage.models import TimelineRow as SqlTimelineRow
from saga.storage.models import UploadedSource as SqlUploadedSource
from saga.storage.models import VisualPrompt as SqlVisualPrompt


ROOT = Path(__file__).resolve().parents[2]
PRO_DIST_DIR = ROOT / "apps" / "dashboard_pro" / "dist"
DIST_DIR = PRO_DIST_DIR
OUTPUTS_DIR = Path(os.environ.get("SAGA_OUTPUTS_DIR") or (ROOT / "analysis_outputs")).resolve()
DASHBOARD_DIR = Path(os.environ.get("SAGA_DASHBOARD_DIR") or (OUTPUTS_DIR / "dashboard")).resolve()
UPLOADS_DIR = Path(os.environ.get("SAGA_UPLOADS_DIR") or (DASHBOARD_DIR / "uploads")).resolve()
STORY_EXPORTS_DIR = Path(os.environ.get("SAGA_STORY_EXPORTS_DIR") or (DASHBOARD_DIR / "story_exports")).resolve()
CODEX_ACCOUNTS_FILE = ROOT / "deploy" / "openai" / "accounts.local.json"
LEGACY_TTS_MODAL_PROVIDER = "tts_modal"
DEFAULT_TTS_MODAL_APP_NAME = "graduation-kokoro-tts"

DEFAULT_BOOKS = [
    r"D:\Books\Ebooks\Sarah J. Maas\A Court of Thorns and Roses\A Court of Thorns and Roses.epub",
    r"D:\Books\Ebooks\Sarah J. Maas\A Court of Mist and Fury\A Court of Mist and Fury.epub",
    r"D:\Books\Ebooks\Sarah J. Maas\A Court of Wings and Ruin\A Court of Wings and Ruin.epub",
    r"D:\Books\Ebooks\Sarah J. Maas\A Court of Frost and Starlight\A Court of Frost and Starlight.epub",
    r"D:\Books\Ebooks\Sarah J. Maas\A Court of Silver Flames\A Court of Silver Flames.epub",
]

PROMPT_FILES = [
    "saga/identity/identity_analyzer.py",
    "saga/agents/db_event_agent.py",
    "saga/agents/db_entity_agent.py",
    "saga/agents/db_character_profile_agent.py",
    "saga/agents/db_character_visual_baseline_agent.py",
    "saga/agents/db_character_visual_scene_state_agent.py",
    "saga/agents/db_noncharacter_visual_baseline_agent.py",
    "saga/agents/db_noncharacter_scene_state_agent.py",
    "saga/agents/db_relationship_agent.py",
    "saga/agents/db_timeline_agent.py",
    "saga/agents/db_stable_character_state_agent.py",
    "saga/agents/microtasks/scene_fallback_synthesizer.py",
    "saga/agents/microtasks/scene_semantic_reviewer.py",
    "saga/agents/microtasks/identity_semantic_reviewer.py",
    "saga/services/narrative_generation_service.py",
    "saga/services/epub_processor.py",
    "saga/services/pdf_processor.py",
    "saga/prompts/causal_graph_prompt.py",
]

HEAVY_CONTRACT_BYTES = 2 * 1024 * 1024
SCAN_CACHE_TTL_SECONDS = 0
CONTRACT_SUMMARY_CACHE: dict[str, dict[str, Any]] = {}
SCAN_CACHE: dict[str, Any] = {"created_at": 0.0, "payload": None}
SQLITE_STORE = SagaSQLiteStore()
CODEX_SESSION_STORE = CodexSessionStore()

PLACEHOLDER_ANALYSIS_VALUES = {
    "",
    "n/a",
    "none",
    "null",
    "unknown",
    "not_explicitly_stated_in_text",
}

SPECULATIVE_ANALYSIS_PATTERNS = (
    "not explicitly stated",
    "not explicitly described",
    "commonly depicted",
    "presumed",
    "unspecified",
)


class ProviderAccount(BaseModel):
    label: str
    email: str = ""
    password: str = ""
    api_key: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    limits: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)


class OllamaProviderConfig(BaseModel):
    active_index: int = 0
    accounts: list[ProviderAccount] = Field(default_factory=list)


class CodexProviderConfig(BaseModel):
    active_index: int = 0
    accounts: list[ProviderAccount] = Field(default_factory=list)


class GeneralComputeProviderConfig(BaseModel):
    active_index: int = 0
    accounts: list[ProviderAccount] = Field(default_factory=list)


class TTSModalProviderConfig(BaseModel):
    app_name: str = DEFAULT_TTS_MODAL_APP_NAME
    api_url: str = ""
    default_voice: str = "af_bella"
    default_lang_code: str = "a"
    default_sample_rate: int = 24000
    default_audio_format: str = "wav"
    default_normalize_audio: bool = True
    default_trim_silence: bool = False
    default_sentence_pause_ms: int = 0
    timeout_seconds: int = 300


class InferenceModalAccountConfig(BaseModel):
    label: str
    token_id: str = ""
    token_secret: str = ""
    app_name_override: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class InferenceProviderConfig(BaseModel):
    provider_name: str
    app_name: str = ""
    api_url: str = ""
    health_url: str = ""
    ui_url: str = ""
    request_timeout_seconds: int = 300
    default_voice: str = ""
    default_lang_code: str = ""
    default_sample_rate: int = 24000
    default_audio_format: str = "wav"
    default_normalize_audio: bool = True
    default_trim_silence: bool = False
    default_sentence_pause_ms: int = 0
    model_name: str = ""
    accounts: list[InferenceModalAccountConfig] = Field(default_factory=list)


class InferenceSelectionConfig(BaseModel):
    provider_name: str


class SignUpRequest(BaseModel):
    name: str
    email: str
    password: str
    workspace_name: str = ""


class SignInRequest(BaseModel):
    email: str
    password: str


class AuthUserResponse(BaseModel):
    id: str
    name: str
    email: str
    workspace_name: str = ""
    created_at: str


PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 310_000
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_auth_email(email: str) -> str:
    return str(email or "").strip().lower()


def _validate_auth_email(email: str) -> str:
    normalized = _normalize_auth_email(email)
    if not EMAIL_PATTERN.match(normalized):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    return normalized


def _validate_password(password: str) -> str:
    value = str(password or "")
    if len(value) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    return value


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS)
    return "$".join(
        [
            PASSWORD_HASH_ALGORITHM,
            str(PASSWORD_HASH_ITERATIONS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        ]
    )


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt_text, digest_text = str(password_hash or "").split("$", 3)
        if algorithm != PASSWORD_HASH_ALGORITHM:
            return False
        salt = base64.b64decode(salt_text.encode("ascii"))
        expected = base64.b64decode(digest_text.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", str(password or "").encode("utf-8"), salt, int(iterations))
    except (ValueError, TypeError, OSError):
        return False
    return hmac.compare_digest(actual, expected)


AUTH_MONGO_CLIENT: Any = None
AUTH_MONGO_CLIENT_URI = ""
AUTH_MONGO_LOCK = threading.Lock()


def _auth_mongo_config() -> dict[str, str]:
    return {
        "uri": str(os.environ.get("SAGA_MONGODB_URI") or os.environ.get("MONGODB_URI") or "").strip(),
        "database": str(os.environ.get("SAGA_MONGODB_DATABASE") or "saga").strip() or "saga",
        "collection": str(os.environ.get("SAGA_MONGODB_USERS_COLLECTION") or "users").strip() or "users",
    }


def _load_mongo_client_class():
    try:
        from pymongo import MongoClient
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="pymongo is required for MongoDB signup storage.") from exc
    return MongoClient


def _get_auth_users_collection():
    config = _auth_mongo_config()
    if not config["uri"]:
        raise HTTPException(status_code=503, detail="MongoDB is not configured. Set SAGA_MONGODB_URI or MONGODB_URI.")

    global AUTH_MONGO_CLIENT, AUTH_MONGO_CLIENT_URI
    with AUTH_MONGO_LOCK:
        if AUTH_MONGO_CLIENT is None or AUTH_MONGO_CLIENT_URI != config["uri"]:
            mongo_client = _load_mongo_client_class()
            AUTH_MONGO_CLIENT = mongo_client(config["uri"], serverSelectionTimeoutMS=5000)
            AUTH_MONGO_CLIENT_URI = config["uri"]
    return AUTH_MONGO_CLIENT[config["database"]][config["collection"]]


def _auth_user_response(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(document.get("id") or document.get("_id") or ""),
        "name": str(document.get("name") or ""),
        "email": str(document.get("email") or ""),
        "workspace_name": str(document.get("workspace_name") or ""),
        "created_at": str(document.get("created_at") or ""),
    }


def _create_auth_user(request: SignUpRequest) -> dict[str, Any]:
    name = str(request.name or "").strip()
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Name must be at least 2 characters.")
    email = _validate_auth_email(request.email)
    password = _validate_password(request.password)
    workspace_name = str(request.workspace_name or "").strip()
    collection = _get_auth_users_collection()
    now = utc_now()
    document = {
        "id": str(uuid.uuid4()),
        "name": name,
        "email": email,
        "workspace_name": workspace_name,
        "password_hash": _hash_password(password),
        "role": "operator",
        "created_at": now,
        "updated_at": now,
    }
    try:
        collection.create_index("email", unique=True)
        if collection.find_one({"email": email}, {"_id": 1}):
            raise HTTPException(status_code=409, detail="An account with this email already exists.")
        collection.insert_one(document)
    except HTTPException:
        raise
    except Exception as exc:
        if exc.__class__.__name__ == "DuplicateKeyError":
            raise HTTPException(status_code=409, detail="An account with this email already exists.") from exc
        raise HTTPException(status_code=503, detail=f"MongoDB signup failed: {type(exc).__name__}.") from exc
    return _auth_user_response(document)


def _find_auth_user_by_email(email: str) -> dict[str, Any] | None:
    collection = _get_auth_users_collection()
    try:
        return collection.find_one({"email": _validate_auth_email(email)})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MongoDB signin failed: {type(exc).__name__}.") from exc


def _authenticate_auth_user(request: SignInRequest) -> dict[str, Any]:
    user = _find_auth_user_by_email(request.email)
    if not user or not _verify_password(request.password, str(user.get("password_hash") or "")):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    return _auth_user_response(user)


def _is_placeholder_analysis_value(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    lowered = text.lower()
    if lowered in PLACEHOLDER_ANALYSIS_VALUES:
        return True
    return any(pattern in lowered for pattern in SPECULATIVE_ANALYSIS_PATTERNS)


def _clean_analysis_text(value: Any) -> str:
    text = str(value or "").strip()
    return "" if _is_placeholder_analysis_value(text) else text


def _clean_analysis_list(values: Any) -> list[Any]:
    if not isinstance(values, list):
        return []
    cleaned: list[Any] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, str):
            normalized = _clean_analysis_text(value)
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(normalized)
            continue
        if isinstance(value, dict):
            normalized = _clean_analysis_dict(value)
            if normalized:
                key = json.dumps(normalized, sort_keys=True, ensure_ascii=True)
                if key in seen:
                    continue
                seen.add(key)
                cleaned.append(normalized)
            continue
        if value in (None, "", [], {}):
            continue
        key = repr(value)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(value)
    return cleaned


def _clean_analysis_dict(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            nested = _clean_analysis_dict(value)
            if nested:
                cleaned[key] = nested
            continue
        if isinstance(value, list):
            nested = _clean_analysis_list(value)
            if nested:
                cleaned[key] = nested
            continue
        if isinstance(value, str):
            normalized = _clean_analysis_text(value)
            if normalized:
                cleaned[key] = normalized
            continue
        if value in (None, "", [], {}):
            continue
        cleaned[key] = value
    return cleaned


def _prompt_negative_base_for_entity(entity_type: str) -> str:
    normalized = str(entity_type or "").strip().lower()
    if normalized == "location":
        return compile_location_negative_prompt()
    if normalized == "creature":
        return compile_creature_negative_prompt()
    if normalized == "object":
        return compile_object_negative_prompt()
    return DEFAULT_NEGATIVE_PROMPT


def _split_negative_prompt_for_editor(prompt: str, entity_type: str) -> dict[str, str]:
    value = str(prompt or "").strip()
    locked_base = _prompt_negative_base_for_entity(entity_type)
    if not value:
        return {"locked_base": locked_base, "editable_tail": ""}
    if value.startswith(locked_base):
        return {"locked_base": locked_base, "editable_tail": value[len(locked_base):].lstrip(", ")}
    embedded_index = value.find(locked_base)
    if embedded_index >= 0:
        return {"locked_base": locked_base, "editable_tail": value[embedded_index + len(locked_base):].lstrip(", ")}
    return {"locked_base": locked_base, "editable_tail": value}


def _split_positive_prompt_for_editor(prompt: str, entity_type: str) -> dict[str, str]:
    lines = [str(line or "").strip() for line in str(prompt or "").splitlines()]
    lines = [line for line in lines if line]
    normalized_type = str(entity_type or "").strip().lower()
    if not lines:
        return {"locked_prefix": "", "editable_body": "", "locked_suffix": ""}

    if normalized_type == "character":
        if (
            len(lines) >= len(CHARACTER_PROMPT_PREFIX_LINES) + len(CHARACTER_PROMPT_SUFFIX_LINES)
            and lines[: len(CHARACTER_PROMPT_PREFIX_LINES)] == CHARACTER_PROMPT_PREFIX_LINES
            and lines[-len(CHARACTER_PROMPT_SUFFIX_LINES):] == CHARACTER_PROMPT_SUFFIX_LINES
        ):
            return {
                "locked_prefix": "\n".join(CHARACTER_PROMPT_PREFIX_LINES),
                "editable_body": "\n".join(lines[len(CHARACTER_PROMPT_PREFIX_LINES): -len(CHARACTER_PROMPT_SUFFIX_LINES)]),
                "locked_suffix": "\n".join(CHARACTER_PROMPT_SUFFIX_LINES),
            }
        return {"locked_prefix": "", "editable_body": "\n".join(lines), "locked_suffix": ""}

    first_line = lines[0]
    prefix_lines: list[str] = []
    suffix_lines: list[str] = []

    if normalized_type == "location" and first_line.startswith("Create a photorealistic empty environment reference image of "):
        legacy_prefix_starts = (
            "The location itself is the only subject.",
            "Show no people, no characters, no creatures, no silhouettes, no body parts, and no active figure of any kind.",
            "Treat this as a worldbuilding reference plate for a canon location",
            "Empty environment reference plate focused entirely on the location itself.",
            "Neutral worldbuilding reference for a canon location",
        )
        remaining = lines[1:]
        while remaining and remaining[0].startswith(legacy_prefix_starts):
            prefix_lines.append(remaining.pop(0))
        editable_lines = [first_line]
        while remaining and (
            remaining[-1] in LOCATION_SUFFIX_LINES
            or remaining[-1].startswith("Use a wide ")
            or remaining[-1].startswith("Use a wide room-level composition")
            or remaining[-1].startswith("Keep the framing observational and documentary")
            or remaining[-1].startswith("The scene must read as a permanent, believable place")
            or remaining[-1].startswith("The scene is completely empty.")
        ):
            suffix_lines.insert(0, remaining.pop())
        return {
            "locked_prefix": "\n".join(prefix_lines),
            "editable_body": "\n".join([*editable_lines, *remaining]),
            "locked_suffix": "\n".join(suffix_lines),
        }

    if normalized_type == "creature" and first_line.startswith("Create a photorealistic creature reference image of "):
        legacy_prefix_starts = (
            "The creature itself is the only subject.",
            "Show no people, no characters, no handlers, no riders, no extra creatures, and no environmental storytelling action.",
            "Treat this as a worldbuilding reference plate for a canon creature",
            "Single-subject creature reference plate focused entirely on the creature.",
            "Neutral worldbuilding reference for a canon creature",
        )
        remaining = lines[1:]
        while remaining and remaining[0].startswith(legacy_prefix_starts):
            prefix_lines.append(remaining.pop(0))
        editable_lines = [first_line]
        while remaining and (
            remaining[-1] in CREATURE_SUFFIX_LINES
            or remaining[-1].startswith("Keep the framing observational and documentary")
        ):
            suffix_lines.insert(0, remaining.pop())
        return {
            "locked_prefix": "\n".join(prefix_lines),
            "editable_body": "\n".join([*editable_lines, *remaining]),
            "locked_suffix": "\n".join(suffix_lines),
        }

    if normalized_type == "object" and first_line.startswith("Create a photorealistic isolated prop reference image of "):
        legacy_prefix_starts = (
            "The object itself is the only subject.",
            "Show no people, no hands, no characters, no creatures, no shelves full of props, and no environmental storytelling clutter.",
            "Treat this as a worldbuilding reference plate for a canon object",
            "Single-subject prop reference plate with the object fully visible and clearly readable.",
            "Neutral worldbuilding reference for a canon object",
        )
        remaining = lines[1:]
        while remaining and remaining[0].startswith(legacy_prefix_starts):
            prefix_lines.append(remaining.pop(0))
        editable_lines = [first_line]
        while remaining and (
            remaining[-1] in OBJECT_SUFFIX_LINES
            or remaining[-1].startswith("Keep the framing observational and documentary")
        ):
            suffix_lines.insert(0, remaining.pop())
        return {
            "locked_prefix": "\n".join(prefix_lines),
            "editable_body": "\n".join([*editable_lines, *remaining]),
            "locked_suffix": "\n".join(suffix_lines),
        }

    return {"locked_prefix": "", "editable_body": "\n".join(lines), "locked_suffix": ""}


def _build_prompt_editor_payload(positive_prompt: str, negative_prompt: str, entity_type: str) -> dict[str, Any]:
    positive = _split_positive_prompt_for_editor(positive_prompt, entity_type)
    negative = _split_negative_prompt_for_editor(negative_prompt, entity_type)
    compiled_positive = "\n".join(
        part for part in [positive["locked_prefix"], positive["editable_body"], positive["locked_suffix"]] if str(part or "").strip()
    )
    compiled_negative = negative["locked_base"]
    if str(negative["editable_tail"] or "").strip():
        compiled_negative = f"{compiled_negative}, {str(negative['editable_tail']).strip()}"
    return {
        "positive": positive,
        "negative": negative,
        "compiled_positive": compiled_positive,
        "compiled_negative": compiled_negative,
    }


def _canonical_prompt_rows(prompt_rows: list[SqlVisualPrompt]) -> list[SqlVisualPrompt]:
    if not prompt_rows:
        return []
    sorted_rows = sorted(prompt_rows, key=lambda row: row.updated_at or row.created_at, reverse=True)
    preferred_types = {
        str(row.prompt_type or "").strip().lower()
        for row in sorted_rows
        if str(row.prompt_type or "").strip().lower().startswith("initial_")
    }
    if preferred_types:
        sorted_rows = [row for row in sorted_rows if str(row.prompt_type or "").strip().lower() in preferred_types]
    return sorted_rows[:1]


def _summarize_analysis_fields(payload: dict[str, Any], keys: list[str], *, limit: int = 8) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for key in keys:
        value = _clean_analysis_text(payload.get(key))
        if not value:
            continue
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        parts.append(value)
        if len(parts) >= limit:
            break
    return ", ".join(parts)


class CharacterRenderRequest(BaseModel):
    contract_path: str
    limit: int = 0
    overwrite: bool = False
    entity_types: list[str] = Field(default_factory=lambda: ["character"])
    entity_ids: list[str] = Field(default_factory=list)
    prompt_ids: list[str] = Field(default_factory=list)


class SeriesCharacterRenderRequest(BaseModel):
    series_id: str
    overwrite: bool = False
    limit_per_book: int = 0
    entity_types: list[str] = Field(default_factory=lambda: ["character"])


class DecoderRequest(BaseModel):
    series_id: str = ""
    book_ref: str = ""
    story_mode: str = "post_canon"
    provider: str = ""
    user_prompt: str = ""
    chapter_count: int = 20
    primary_pov_character: str = ""
    continuity_anchor: str = ""
    divergence_anchor: str = ""


class ImportPlanBook(BaseModel):
    source_id: str
    target_title: str = ""
    book_index: int = 1
    selected: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ImportPlanRequest(BaseModel):
    series_id: str
    series_title: str
    books: list[ImportPlanBook] = Field(default_factory=list)
    shared_config: dict[str, Any] = Field(default_factory=dict)


class PromptVersionRequest(BaseModel):
    positive_prompt: str
    negative_prompt: str = ""
    source: str = "dashboard_edit"
    activate: bool = True
    details: dict[str, Any] = Field(default_factory=dict)


class EntityRenderRequest(BaseModel):
    prompt_id: str = ""
    overwrite: bool = False
    settings: dict[str, Any] = Field(default_factory=dict)


class AssetPreviewRenderRequest(BaseModel):
    positive_prompt: str
    negative_prompt: str = ""


class AssetSaveRenderRequest(BaseModel):
    positive_prompt: str
    negative_prompt: str = ""
    preview_image_path: str


class EntityRenameRequest(BaseModel):
    name: str


class RenderBatchRequest(BaseModel):
    book_ref: str = ""
    series_id: str = ""
    scope: str = "missing"
    entity_types: list[str] = Field(default_factory=list)
    entity_ids: list[str] = Field(default_factory=list)
    overwrite: bool = False
    limit: int = 0


class DecoderPlanRequest(BaseModel):
    series_id: str = ""
    book_ref: str = ""
    story_mode: str = "post_canon"
    provider: str = ""
    user_prompt: str = ""
    chapter_count: int = 20
    primary_pov_character: str = ""
    continuity_anchor: str = ""
    divergence_anchor: str = ""


class AudiobookStageRequest(BaseModel):
    scope: str = "book"
    series_id: str
    book_ref: str = ""
    tone: str = "classic"
    rewrite_provider: str = "ollama"
    rewrite_fallback_mode: str = "strict_rewrite"
    voice: str = "af_bella"
    lang_code: str = "a"
    sample_rate: int = 24000
    audio_format: str = "wav"
    normalize_audio: bool = True
    trim_silence: bool = False
    sentence_pause_ms: int = 0
    store_transcript: bool = True
    store_audio: bool = True



def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs() -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    STORY_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def is_db_book_ref(value: str) -> bool:
    return str(value or "").startswith("db://book/")


def parse_db_book_ref(value: str) -> str:
    if not is_db_book_ref(value):
        return ""
    return str(value).split("db://book/", 1)[-1].strip()


def slugify(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", str(text or "").strip().lower())
    return value.strip("-") or "series"


def normalize_books(books: list[str], book_index_base: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for offset, book_path in enumerate(books):
        clean = str(book_path or "").strip()
        if not clean:
            continue
        path = Path(clean)
        rows.append(
            {
                "path": clean,
                "title": path.name,
                "book_index": int(book_index_base) + offset,
            }
        )
    return rows


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _safe_db(default: Any, operation: str, func_call) -> Any:
    try:
        return func_call()
    except (OperationalError, SQLAlchemyError) as exc:
        print(f"[apps.dashboard_api] database operation failed: {operation}: {exc}", file=sys.stderr)
        return default
    except Exception as exc:
        print(f"[apps.dashboard_api] unexpected operation failure: {operation}: {exc}", file=sys.stderr)
        return default


def _audiobook_audio_path(*, run_id: str, series_id: str, book_index: int | None, chapter_index: int | None, audio_format: str) -> str:
    safe_series = slugify(series_id or "series")
    extension = "flac" if str(audio_format or "").strip().lower() == "flac" else "wav"
    filename = f"book_{int(book_index or 0):02d}_chapter_{int(chapter_index or 0):03d}.{extension}"
    return str((DASHBOARD_DIR / "audiobooks" / safe_series / run_id / "audio" / filename).resolve())


def _audiobook_recovery_log_tail(run_id: str, *, limit: int = 40) -> list[str]:
    candidates = [
        DASHBOARD_DIR / "logs" / f"audiobook-recovery-{run_id}.log",
        DASHBOARD_DIR / "logs" / f"audiobook-recovery-{str(run_id)[:8]}.log",
        DASHBOARD_DIR / "logs" / "audiobook-recovery.log",
    ]
    for target in candidates:
        if not target.exists() or not target.is_file():
            continue
        try:
            raw = target.read_bytes()
            text = ""
            for encoding in ("utf-8", "utf-16", "utf-16-le", "utf-16-be"):
                try:
                    text = raw.decode(encoding)
                    if text:
                        break
                except Exception:
                    continue
            if not text:
                text = raw.decode("utf-8", errors="replace")
            return [line.replace("\x00", "") for line in text.splitlines() if str(line).replace("\x00", "").strip()][-limit:]
        except Exception:
            continue
    return []


def _augment_audiobook_run_from_outputs(run_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(run_payload, dict):
        return run_payload
    chapters = run_payload.get("chapters") if isinstance(run_payload.get("chapters"), list) else []
    if not chapters:
        return run_payload

    completed_count = 0
    failed_count = int(run_payload.get("failed_chapters") or 0)
    next_pending: dict[str, Any] | None = None
    latest_mtime = ""
    for chapter in chapters:
        audio_path_raw = str(chapter.get("audio_path") or "").strip()
        audio_path = Path(audio_path_raw).resolve() if audio_path_raw else None
        exists = bool(audio_path and audio_path.exists() and audio_path.is_file() and audio_path.stat().st_size > 0)
        if exists:
            completed_count += 1
            chapter["audio_status"] = "completed"
            latest_mtime = max(latest_mtime, datetime.fromtimestamp(audio_path.stat().st_mtime, tz=timezone.utc).isoformat())
            if not chapter.get("audio_byte_size"):
                chapter["audio_byte_size"] = int(audio_path.stat().st_size)
        elif next_pending is None:
            next_pending = chapter

    total_chapters = int(run_payload.get("total_chapters") or len(chapters) or 0)
    run_payload["completed_chapters"] = completed_count
    run_payload["failed_chapters"] = failed_count
    if total_chapters and completed_count >= total_chapters and failed_count == 0:
        run_payload["status"] = "completed"
        run_payload["progress"] = _job_progress_payload(
            stage="complete",
            current=completed_count,
            total=total_chapters,
            label="Audiobook pipeline completed",
            status="completed",
            details={"run_id": str(run_payload.get("id") or ""), "chapter_count": total_chapters, "phase": "tts", "failed_chapters": failed_count},
        )
    elif next_pending is not None:
        next_title = str(next_pending.get("chapter_title") or "").strip() or f"Chapter {int(next_pending.get('chapter_index') or 0)}"
        run_payload["status"] = "running"
        run_payload["progress"] = _job_progress_payload(
            stage="tts",
            current=completed_count,
            total=total_chapters,
            label=f"Synthesizing {next_title}",
            status="running",
            details={
                "run_id": str(run_payload.get("id") or ""),
                "chapter_count": total_chapters,
                "phase": "tts",
                "chapter_number": int(next_pending.get("chapter_index") or 0),
                "book_index": int(next_pending.get("book_index") or 1),
                "chapter_index": int(next_pending.get("chapter_index") or 0),
                "chapter_title": next_title,
                "failed_chapters": failed_count,
            },
        )
    if latest_mtime:
        run_payload["updated_at"] = latest_mtime
    run_payload["available_audio_files"] = completed_count
    return run_payload


def _list_audiobook_audio_rows(run_id: str) -> list[SqlAudiobookChapter]:
    with SQLITE_STORE.session_factory() as session:
        return session.execute(
            select(SqlAudiobookChapter)
            .where(SqlAudiobookChapter.run_id == run_id)
            .order_by(SqlAudiobookChapter.book_index.asc(), SqlAudiobookChapter.chapter_index.asc())
        ).scalars().all()


def _resolve_audiobook_bundle_path(run_id: str) -> Path:
    return (DASHBOARD_DIR / "audiobooks" / "bundles" / f"{run_id}.wav").resolve()


def _build_audiobook_bundle(run_id: str) -> Path:
    rows = _list_audiobook_audio_rows(run_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Audiobook run not found.")

    ready_rows: list[SqlAudiobookChapter] = []
    newest_source_mtime = 0.0
    for row in rows:
        audio_path = Path(str(row.audio_path or "")).resolve() if str(row.audio_path or "").strip() else None
        if audio_path is None or not audio_path.exists() or not audio_path.is_file():
            continue
        if audio_path.suffix.lower() != ".wav":
            raise HTTPException(status_code=409, detail="Full audiobook download currently requires WAV chapter outputs.")
        ready_rows.append(row)
        newest_source_mtime = max(newest_source_mtime, audio_path.stat().st_mtime)

    if not ready_rows:
        raise HTTPException(status_code=404, detail="No completed audiobook chapter files are available for bundling.")

    bundle_path = _resolve_audiobook_bundle_path(run_id)
    if bundle_path.exists() and bundle_path.is_file() and bundle_path.stat().st_mtime >= newest_source_mtime:
        return bundle_path

    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    params = None
    with wave.open(str(bundle_path), "wb") as writer:
        for row in ready_rows:
            audio_path = Path(str(row.audio_path or "")).resolve()
            with wave.open(str(audio_path), "rb") as reader:
                current_params = (
                    reader.getnchannels(),
                    reader.getsampwidth(),
                    reader.getframerate(),
                    reader.getcomptype(),
                    reader.getcompname(),
                )
                if params is None:
                    params = current_params
                    writer.setnchannels(current_params[0])
                    writer.setsampwidth(current_params[1])
                    writer.setframerate(current_params[2])
                    writer.setcomptype(current_params[3], current_params[4])
                elif current_params != params:
                    raise HTTPException(status_code=409, detail="Chapter WAV files are incompatible for full audiobook bundling.")
                writer.writeframes(reader.readframes(reader.getnframes()))
    return bundle_path


def _resolve_audiobook_scope(request: AudiobookStageRequest) -> dict[str, Any]:
    scope = str(request.scope or "book").strip().lower()
    if scope not in {"book", "series"}:
        raise HTTPException(status_code=400, detail="scope must be 'book' or 'series'.")
    if not str(request.series_id or "").strip():
        raise HTTPException(status_code=400, detail="series_id is required.")

    selected_book_id = parse_db_book_ref(request.book_ref)
    if scope == "book" and not selected_book_id:
        raise HTTPException(status_code=400, detail="book_ref is required for book scope.")

    with SQLITE_STORE.session_factory() as session:
        series = session.execute(select(SqlSeries).where(SqlSeries.series_id == str(request.series_id))).scalar_one_or_none()
        if series is None:
            raise HTTPException(status_code=404, detail="Series not found.")

        book_query = (
            select(SqlBook)
            .where(SqlBook.series_id == str(request.series_id))
            .order_by(SqlBook.book_index.asc(), SqlBook.title.asc())
        )
        if scope == "book":
            book_query = book_query.where(SqlBook.id == selected_book_id)
        books = session.execute(book_query).scalars().all()
        if not books:
            raise HTTPException(status_code=404, detail="No books found for the selected audiobook scope.")

        chapters_by_book: dict[str, list[SqlChapter]] = {}
        total_chapters = 0
        for book in books:
            chapter_rows = session.execute(
                select(SqlChapter)
                .where(SqlChapter.book_id == book.id)
                .order_by(SqlChapter.chapter_index.asc())
            ).scalars().all()
            chapters_by_book[book.id] = chapter_rows
            total_chapters += len(chapter_rows)

        if total_chapters <= 0:
            raise HTTPException(status_code=409, detail="The selected audiobook scope has no chapter rows in the database.")

        return {
            "series": series,
            "books": books,
            "chapters_by_book": chapters_by_book,
            "total_chapters": total_chapters,
        }


def _build_audiobook_run_title(*, request: AudiobookStageRequest, scope_payload: dict[str, Any]) -> str:
    series = scope_payload["series"]
    books = scope_payload["books"]
    if str(request.scope or "").strip().lower() == "series":
        return f"{str(series.title or request.series_id).strip() or request.series_id} audiobook"
    selected = books[0]
    return str(selected.title or f"Book {selected.book_index or 0}").strip() or "Audiobook run"


def _resolve_chapter_source_text(chapter_row: SqlChapter | None, *, session=None) -> str:
    if chapter_row is None:
        return ""

    direct_text = str(getattr(chapter_row, "text", "") or "").strip()
    if direct_text:
        return direct_text

    metadata = getattr(chapter_row, "metadata_json", None)
    if isinstance(metadata, dict):
        metadata_text = str(metadata.get("content") or metadata.get("text") or "").strip()
        if metadata_text:
            return metadata_text

    close_session = False
    active_session = session
    if active_session is None:
        active_session = SQLITE_STORE.session_factory()
        close_session = True
    try:
        scene_rows = active_session.execute(
            select(SqlScene)
            .where(SqlScene.chapter_id == chapter_row.id)
            .order_by(SqlScene.scene_index.asc(), SqlScene.id.asc())
        ).scalars().all()
        scene_texts = [str(scene.text or "").strip() for scene in scene_rows if str(scene.text or "").strip()]
        if scene_texts:
            return "\n\n".join(scene_texts)
        scene_summaries = [str(scene.summary or "").strip() for scene in scene_rows if str(scene.summary or "").strip()]
        if scene_summaries:
            return "\n\n".join(scene_summaries)
    finally:
        if close_session:
            active_session.close()

    return ""


def _audiobook_llm_mode(provider_name: str) -> str:
    value = str(provider_name or "ollama").strip().lower()
    if value == "general_compute":
        return LLMClient.MODE_GENERAL_COMPUTE
    if value == "codex":
        return LLMClient.MODE_CODEX
    if value == "mistral":
        return LLMClient.MODE_MISTRAL
    if value == "gemini":
        return LLMClient.MODE_GEMINI
    return LLMClient.MODE_GPT_OSS


def _create_staged_audiobook_run(request: AudiobookStageRequest) -> dict[str, Any]:
    if not request.store_transcript and not request.store_audio:
        raise HTTPException(status_code=400, detail="At least one storage target must be enabled.")

    scope_payload = _resolve_audiobook_scope(request)
    books = scope_payload["books"]
    chapters_by_book = scope_payload["chapters_by_book"]
    run_title = _build_audiobook_run_title(request=request, scope_payload=scope_payload)
    tts_provider_name = active_provider_name_for_capability(SPEECH_CAPABILITY, store=SQLITE_STORE)
    tts_provider_config = read_inference_provider_config(tts_provider_name, store=SQLITE_STORE, mask=False)
    run = _safe_db(
        None,
        "create_audiobook_run",
        lambda: SQLITE_STORE.create_audiobook_run(
            {
                "series_id": request.series_id,
                "book_id": books[0].id if str(request.scope or "").strip().lower() == "book" else None,
                "scope_type": str(request.scope or "book").strip().lower(),
                "title": run_title,
                "status": "staged",
                "source_provider": "ollama",
                "tts_provider": tts_provider_name,
                "tts_app_name": str(tts_provider_config.get("app_name") or ""),
                "voice": request.voice,
                "lang_code": request.lang_code,
                "sample_rate": request.sample_rate,
                "audio_format": request.audio_format,
                "normalize_audio": request.normalize_audio,
                "trim_silence": request.trim_silence,
                "sentence_pause_ms": request.sentence_pause_ms,
                "total_books": len(books),
                "total_chapters": scope_payload["total_chapters"],
                "transcript_storage_mode": "database" if request.store_transcript else "disabled",
                "audio_storage_mode": "path" if request.store_audio else "disabled",
                "progress": {"current": 0, "total": scope_payload["total_chapters"], "phase": "staged"},
                "metadata": {
                    "tone": request.tone,
                    "rewrite_provider": str(request.rewrite_provider or "ollama").strip().lower() or "ollama",
                    "rewrite_fallback_mode": str(request.rewrite_fallback_mode or "strict_rewrite").strip().lower() or "strict_rewrite",
                    "scope_label": str(request.scope or "book").strip().lower(),
                    "book_ids": [book.id for book in books],
                    "staged_at": utc_now(),
                    "source": "dashboard_pro",
                },
            }
        ),
    )
    if run is None:
        raise HTTPException(status_code=500, detail="Failed to create audiobook run.")

    for book in books:
        for chapter in chapters_by_book.get(book.id, []):
            transcript_text = str(chapter.text or "").strip() if request.store_transcript else ""
            audio_path = (
                _audiobook_audio_path(
                    run_id=str(run["id"]),
                    series_id=request.series_id,
                    book_index=book.book_index,
                    chapter_index=chapter.chapter_index,
                    audio_format=request.audio_format,
                )
                if request.store_audio
                else ""
            )
            _safe_db(
                None,
                "upsert_audiobook_chapter",
                lambda payload={
                    "run_id": run["id"],
                    "series_id": request.series_id,
                    "book_id": book.id,
                    "chapter_id": chapter.id,
                    "book_index": book.book_index,
                    "chapter_index": chapter.chapter_index,
                    "chapter_title": chapter.title or f"Chapter {chapter.chapter_index}",
                    "transcript_status": "staged" if request.store_transcript else "skipped",
                    "audio_status": "staged" if request.store_audio else "skipped",
                    "transcript_text": transcript_text,
                    "transcript_word_count": chapter.word_count,
                    "audio_path": audio_path,
                    "audio_mime_type": "audio/flac" if str(request.audio_format).lower() == "flac" else "audio/wav",
                    "source_provider": "ollama",
                    "tts_provider": tts_provider_name,
                    "tts_app_name": str(tts_provider_config.get("app_name") or ""),
                    "voice": request.voice,
                    "lang_code": request.lang_code,
                    "sample_rate": request.sample_rate,
                    "audio_format": request.audio_format,
                    "metadata": {
                        "tone": request.tone,
                        "rewrite_provider": str(request.rewrite_provider or "ollama").strip().lower() or "ollama",
                        "rewrite_fallback_mode": str(request.rewrite_fallback_mode or "strict_rewrite").strip().lower() or "strict_rewrite",
                        "source_text_staged": bool(transcript_text),
                        "book_title": book.title,
                    },
                }: SQLITE_STORE.upsert_audiobook_chapter(payload),
            )

    payload = _safe_db(None, "get_audiobook_run", lambda: SQLITE_STORE.get_audiobook_run(str(run["id"])))
    if payload is None:
        raise HTTPException(status_code=500, detail="Failed to load staged audiobook run.")
    return payload


def _queue_audiobook_run(run_id: str, *, retry_of: str = "") -> dict[str, Any]:
    run = _safe_db(None, "get_audiobook_run", lambda: SQLITE_STORE.get_audiobook_run(run_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Audiobook run not found.")
    stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    active_jobs = []
    for job in list_jobs():
        if str((job.get("artifacts") or {}).get("audiobook_run_id") or "") != str(run_id):
            continue
        if str(job.get("status") or "").lower() not in {"queued", "starting", "running"}:
            continue
        if str(job.get("type") or "") == "audiobook-pipeline":
            run_updated_at_raw = str(run.get("updated_at") or "").strip()
            job_started_at_raw = str(job.get("started_at") or job.get("created_at") or "").strip()
            try:
                run_updated_at = datetime.fromisoformat(run_updated_at_raw.replace("Z", "+00:00")) if run_updated_at_raw else None
            except ValueError:
                run_updated_at = None
            try:
                job_started_at = datetime.fromisoformat(job_started_at_raw.replace("Z", "+00:00")) if job_started_at_raw else None
            except ValueError:
                job_started_at = None
            if run_updated_at and (run_updated_at.tzinfo is None):
                run_updated_at = run_updated_at.replace(tzinfo=timezone.utc)
            if job_started_at and (job_started_at.tzinfo is None):
                job_started_at = job_started_at.replace(tzinfo=timezone.utc)
            if (run_updated_at and run_updated_at < stale_cutoff) or (job_started_at and job_started_at < stale_cutoff):
                continue
        active_jobs.append(job)
    if active_jobs:
        return active_jobs[0]

    job_id = f"audiobook_{datetime.now().strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    progress = _job_progress_payload(
        stage="queued",
        current=0,
        total=int(run.get("total_chapters") or len(run.get("chapters") or []) or 1),
        label="Queued audiobook pipeline",
        status="queued",
        details={
            "run_id": run_id,
            "chapter_count": int(run.get("total_chapters") or len(run.get("chapters") or []) or 0),
            "scope_type": run.get("scope_type") or "book",
            "title": run.get("title") or "Audiobook run",
        },
    )
    payload = {
        "id": job_id,
        "type": "audiobook-pipeline",
        "status": "queued",
        "status_reason": f"Queued audiobook run {run_id}",
        "created_at": utc_now(),
        "request": {"run_id": run_id},
        "artifacts": {"audiobook_run_id": run_id, "retry_of": retry_of} if retry_of else {"audiobook_run_id": run_id},
        "progress": progress,
        "command": f"db-audiobook:{run_id}",
    }
    save_job(payload)
    _safe_db(
        None,
        "update_audiobook_run",
        lambda: SQLITE_STORE.update_audiobook_run(
            run_id,
            {
                "job_id": job_id,
                "status": "queued",
                "progress": progress,
            },
        ),
    )
    SQLITE_STORE.append_dashboard_job_log(job_id, f"AUDIOBOOK_PIPELINE_QUEUED run_id={run_id}", level="INFO")
    thread = threading.Thread(target=run_audiobook_job, args=(job_id, run_id), daemon=True)
    thread.start()
    return load_job(job_id)


def tail_lines(path: Path, limit: int = 80) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    except Exception:
        return []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def derive_scene_quality(scene_rows: list[Any], quality: dict[str, Any] | None = None) -> dict[str, int]:
    base = quality or {}
    successful = base.get("successful_scenes")
    failed = base.get("failed_scenes")
    total = base.get("total_scenes")
    if isinstance(successful, int) and isinstance(failed, int):
        return {
            "successful_scenes": successful,
            "failed_scenes": failed,
            "total_scenes": int(total) if isinstance(total, int) else successful + failed,
        }

    success_count = 0
    failed_count = 0
    for row in scene_rows or []:
        if not isinstance(row, dict):
            continue
        final_status = str(row.get("final_status") or "").strip().lower()
        error_flag = bool(row.get("error") or row.get("last_error"))
        error_category = str(row.get("error_category") or "").strip().lower()
        if final_status in {"failed", "error"} or error_flag or error_category:
            failed_count += 1
        else:
            success_count += 1
    return {
        "successful_scenes": success_count,
        "failed_scenes": failed_count,
        "total_scenes": len(scene_rows or []),
    }


def mask_secret(value: str) -> dict[str, Any]:
    value = str(value or "")
    if not value:
        return {"configured": False, "preview": ""}
    return {"configured": True, "preview": f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "configured"}


def contract_summary(path: Path, *, parse_heavy: bool = False) -> dict[str, Any]:
    stat = path.stat()
    cache_key = str(path.resolve())
    cached = CONTRACT_SUMMARY_CACHE.get(cache_key)
    if cached and cached.get("mtime_ns") == stat.st_mtime_ns and cached.get("size") == stat.st_size:
        return dict(cached["summary"])
    if stat.st_size > HEAVY_CONTRACT_BYTES and not parse_heavy:
        return {
            "path": rel(path),
            "name": path.name.replace(".contract.json", ""),
            "mtime": stat.st_mtime,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "run_status": "load on select",
            "identity_provider": "load on select",
            "scenes": "load",
            "successful_scenes": None,
            "failed_scenes": None,
            "entity_registry": "load",
            "timeline": "load",
            "event_ledger": "load",
            "character_profiles": "load",
            "stable_character_states": "load",
            "story_index_docs": "load",
            "load_deferred": True,
        }
    payload = load_json(path) or {}
    outputs = payload.get("outputs") or {}
    metadata = payload.get("metadata") or {}
    quality = metadata.get("scene_analysis_quality") or payload.get("scene_analysis_quality") or {}
    scenes = outputs.get("resolved_scene_analyses") or outputs.get("scene_analyses") or []
    derived_quality = derive_scene_quality(scenes, quality if isinstance(quality, dict) else {})
    title = metadata.get("book_title") or path.name.replace(".contract.json", "")
    summary = {
        "path": rel(path),
        "name": title,
        "mtime": stat.st_mtime,
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
        "run_status": metadata.get("run_status") or payload.get("run_status") or "unknown",
        "identity_provider": metadata.get("identity_provider") or payload.get("identity_provider") or "n/a",
        "scenes": len(scenes),
        "successful_scenes": derived_quality.get("successful_scenes"),
        "failed_scenes": derived_quality.get("failed_scenes"),
        "entity_registry": len(outputs.get("entity_registry") or []),
        "timeline": len(outputs.get("timeline") or []),
        "event_ledger": len(outputs.get("event_ledger") or []),
        "character_profiles": len(outputs.get("character_profiles") or []),
        "stable_character_states": len(outputs.get("stable_character_states") or []),
        "story_index_docs": len(((outputs.get("story_index") or {}).get("documents") or [])),
    }
    CONTRACT_SUMMARY_CACHE[cache_key] = {
        "mtime_ns": stat.st_mtime_ns,
        "size": stat.st_size,
        "summary": summary,
    }
    return summary


def _db_contract_summaries(limit: int = 200) -> list[dict[str, Any]]:
    def _query() -> list[dict[str, Any]]:
        with SQLITE_STORE.session_factory() as session:
            books = session.execute(select(SqlBook).order_by(SqlBook.updated_at.desc())).scalars().all()
            rows: list[dict[str, Any]] = []
            for book in books[:limit]:
                scene_count = session.execute(select(func.count()).select_from(SqlScene).where(SqlScene.book_id == book.id)).scalar_one()
                event_count = session.execute(select(func.count()).select_from(SqlEvent).where(SqlEvent.book_id == book.id)).scalar_one()
                entity_count = session.execute(select(func.count()).select_from(SqlEntity).where(SqlEntity.book_id == book.id)).scalar_one()
                profile_count = session.execute(select(func.count()).select_from(SqlCharacterProfile).where(SqlCharacterProfile.book_id == book.id)).scalar_one()
                stable_count = session.execute(select(func.count()).select_from(SqlStableCharacterState).where(SqlStableCharacterState.book_id == book.id)).scalar_one()
                timeline_count = session.execute(select(func.count()).select_from(SqlTimelineRow).where(SqlTimelineRow.book_id == book.id)).scalar_one()
                quality = book.scene_analysis_quality if isinstance(book.scene_analysis_quality, dict) else {}
                rows.append({
                    "path": f"db://book/{book.id}",
                    "name": book.title.replace(".contract.json", ""),
                    "series_id": book.series_id or "",
                    "book_index": book.book_index,
                    "book_id": book.id,
                    "mtime": book.updated_at.timestamp() if getattr(book, "updated_at", None) else 0,
                    "size_mb": 0.0,
                    "run_status": book.run_status or "unknown",
                    "identity_provider": book.identity_provider or "n/a",
                    "scenes": int(scene_count or 0),
                    "successful_scenes": quality.get("successful_scenes"),
                    "failed_scenes": quality.get("failed_scenes"),
                    "entity_registry": int(entity_count or 0),
                    "timeline": int(timeline_count or 0),
                    "event_ledger": int(event_count or 0),
                    "character_profiles": int(profile_count or 0),
                    "stable_character_states": int(stable_count or 0),
                    "story_index_docs": 0,
                    "load_deferred": False,
                })
            return rows

    return _safe_db([], "_db_contract_summaries", _query)


def run_summary(run_dir: Path) -> dict[str, Any]:
    contracts_dir = run_dir / "contracts"
    contracts = [contract_summary(path) for path in contracts_dir.glob("*.contract.json")] if contracts_dir.exists() else []
    status_payload = load_json(run_dir / "status.json")
    latest_status_payload = load_json(run_dir.parent / "latest_status.json")
    statuses = [item for item in [status_payload, latest_status_payload] if isinstance(item, dict)]
    run_status = ""
    if isinstance(status_payload, dict):
        run_status = str(status_payload.get("status") or "").strip().lower()
    if not run_status and isinstance(latest_status_payload, dict):
        run_status = str(latest_status_payload.get("status") or "").strip().lower()
    status_reason = ""
    status_source = "run_status"
    latest_worker_pid = (status_payload or {}).get("worker_pid") if isinstance(status_payload, dict) else None
    latest_update_age = _status_update_age_seconds(status_payload if isinstance(status_payload, dict) else latest_status_payload)
    worker_stale = (
        isinstance(status_payload, dict)
        and run_status == "running"
        and latest_worker_pid not in (None, "", 0, "0")
        and not _pid_is_running(latest_worker_pid)
        and latest_update_age is not None
        and latest_update_age > 30
    )
    latest_run_dir = ""
    if isinstance(latest_status_payload, dict):
        latest_run_dir = str(latest_status_payload.get("run_dir") or "").strip().replace("\\", "/").lower()
    this_run_dir = str(rel(run_dir)).replace("\\", "/").lower()
    active_books = []
    if isinstance(status_payload, dict):
        active_books = status_payload.get("books") or []
    if not contracts and active_books:
        contracts = [
            {
                "path": str(book.get("contract_path") or ""),
                "name": str(book.get("title") or ""),
                "mtime": run_dir.stat().st_mtime,
                "size_mb": 0.0,
                "run_status": str(book.get("status") or "unknown"),
                "identity_provider": str(book.get("identity_provider") or "n/a"),
                "scenes": int(book.get("total_scenes") or book.get("scenes_processed") or 0),
                "successful_scenes": int(book.get("successful_scenes") or 0) if book.get("successful_scenes") is not None else None,
                "failed_scenes": int(book.get("failed_scenes") or 0) if book.get("failed_scenes") is not None else None,
                "entity_registry": int(book.get("entity_registry") or 0) if book.get("entity_registry") is not None else 0,
                "timeline": int(book.get("timeline") or 0) if book.get("timeline") is not None else 0,
                "event_ledger": int(book.get("event_ledger") or 0) if book.get("event_ledger") is not None else 0,
                "character_profiles": int(book.get("character_profiles") or 0) if book.get("character_profiles") is not None else 0,
                "stable_character_states": int(book.get("stable_character_states") or 0) if book.get("stable_character_states") is not None else 0,
                "story_index_docs": int(book.get("story_index_docs") or 0) if book.get("story_index_docs") is not None else 0,
            }
            for book in active_books if isinstance(book, dict)
        ]
    active_book = next(
        (
            book for book in active_books
            if isinstance(book, dict) and str(book.get("status") or "").strip().lower() == "running"
        ),
        None,
    )
    active_scene_total = 0
    if active_books:
        for book in active_books:
            if not isinstance(book, dict):
                continue
            active_scene_total += int(book.get("scenes_processed") or book.get("total_scenes") or 0)
    failed_books = sum(1 for row in contracts if str(row.get("run_status")).lower() in {"failed", "partial", "paused"})
    status_value = "failed" if failed_books else (run_status or ("completed" if contracts else "unknown"))
    if worker_stale:
        status_value = "failed"
        status_reason = _humanize_status_reason("stale_encode_worker_process")
        status_source = "stale_worker_guard"
    elif status_value == "failed" and not status_reason:
        status_reason = _humanize_status_reason(
            str((status_payload or {}).get("error") or (latest_status_payload or {}).get("error") or "").strip()
        )
    if status_value == "running" and latest_run_dir and latest_run_dir != this_run_dir:
        status_value = "superseded"
        status_reason = "a newer run for this series is now the latest active status"
        status_source = "latest_status_pointer"
    if worker_stale and active_books:
        for book in active_books:
            if not isinstance(book, dict):
                continue
            if str(book.get("status") or "").strip().lower() == "running":
                book["status"] = "failed"
                book["error"] = status_reason
        for row in contracts:
            if not isinstance(row, dict):
                continue
            if str(row.get("run_status") or "").strip().lower() == "running":
                row["run_status"] = "failed"
    books_count = len(contracts) if contracts else len(active_books)
    contracts_count = len(contracts)
    total_scenes = sum(int(row.get("scenes") or 0) for row in contracts if isinstance(row.get("scenes"), int))
    if not total_scenes and active_scene_total:
        total_scenes = active_scene_total
    progress = None
    if active_book:
        scenes_processed = int(active_book.get("scenes_processed") or 0)
        total_book_scenes = int(active_book.get("total_scenes") or 0)
        phase = str(active_book.get("phase") or "running")
        label = str((active_book.get("last_progress") or {}).get("status") or f"{active_book.get('title') or 'Book'} ط¢- {phase}")
        progress = {
            "stage": "encode",
            "current": scenes_processed,
            "total": total_book_scenes,
            "label": label,
            "status": status_value or "running",
            "details": {
                "book_title": active_book.get("title") or "",
                "book_phase": phase,
                "checkpoint_path": active_book.get("checkpoint_path") or "",
                "status_reason": status_reason,
                "status_source": status_source,
                "status_update_age_seconds": latest_update_age,
            },
        }
    log_tail = tail_lines(run_dir / "encode.log", limit=120) if status_value == "running" else []
    return {
        "path": rel(run_dir),
        "series_id": run_dir.parent.name,
        "run_id": run_dir.name,
        "mtime": run_dir.stat().st_mtime,
        "status": status_value,
        "status_reason": status_reason,
        "status_source": status_source,
        "books": books_count,
        "contracts": contracts_count,
        "failed_books": failed_books,
        "total_scenes": total_scenes,
        "book_rows": contracts if contracts else active_books,
        "status_payload_count": len(statuses),
        "worker_pid": latest_worker_pid,
        "status_update_age_seconds": latest_update_age,
        "progress": progress,
        "log_tail": log_tail,
        "command": ((status_payload or {}).get("plan") or {}).get("mode") if isinstance(status_payload, dict) else "",
    }


def is_real_run_dir(path: Path) -> bool:
    return (
        path.is_dir()
        and len(path.name) >= 4
        and path.name[:4].isdigit()
        and (path / "status.json").exists()
    )


def scan_artifacts() -> dict[str, Any]:
    now = time.monotonic()
    cached_payload = SCAN_CACHE.get("payload")
    if cached_payload and (now - float(SCAN_CACHE.get("created_at") or 0.0)) < SCAN_CACHE_TTL_SECONDS:
        return cached_payload
    OUTPUTS_DIR.mkdir(exist_ok=True)
    contracts = _db_contract_summaries(limit=200)
    runs = _safe_db([], "get_pipeline_runs", lambda: SQLITE_STORE.get_pipeline_runs(limit=100))
    runs = [row for row in runs if not str(row.get("path") or "").startswith("db://job/")]
    if not runs:
        job_runs = []
        for job in list_jobs():
            if str(job.get("type") or "").strip().lower() != "encode-pipeline":
                continue
            job_runs.append(_job_to_run_summary(job))
        runs = job_runs[:100]
    reports: list[dict[str, Any]] = []
    visual_states: list[dict[str, Any]] = []
    identities: list[dict[str, Any]] = []
    identity_db = _safe_db([], "db_identity_summaries", db_identity_summaries)
    db_counts = database_summary()
    payload = {
        "books": contracts,
        "contracts": contracts,
        "runs": runs,
        "reports": reports,
        "visual_states": visual_states,
        "identities": identities,
        "identity_db": identity_db,
        "database": db_counts,
        "counts": {
            "contracts": len(contracts),
            "runs": len(runs),
            "reports": len(reports),
            "visual_states": int(db_counts.get("generated_images") or 0),
            "identities": len(identities),
            "identity_db": len(identity_db),
            "total_scenes": sum(int(row.get("scenes") or 0) for row in contracts if isinstance(row.get("scenes"), int)),
        },
    }
    SCAN_CACHE["created_at"] = now
    SCAN_CACHE["payload"] = payload
    return payload


def database_summary() -> dict[str, Any]:
    from sqlalchemy import func, select
    from saga.storage.models import Book, Entity, GeneratedImage, IdentityCharacter, IdentitySeries, Scene, VisualPrompt

    def _query() -> dict[str, Any]:
        with SQLITE_STORE.session_factory() as session:
            return {
                "books": session.execute(select(func.count()).select_from(Book)).scalar_one(),
                "scenes": session.execute(select(func.count()).select_from(Scene)).scalar_one(),
                "entities": session.execute(select(func.count()).select_from(Entity)).scalar_one(),
                "visual_prompts": session.execute(select(func.count()).select_from(VisualPrompt)).scalar_one(),
                "generated_images": session.execute(select(func.count()).select_from(GeneratedImage)).scalar_one(),
                "generated_stories": session.execute(select(func.count()).select_from(SqlGeneratedStory)).scalar_one(),
                "identity_series": session.execute(select(func.count()).select_from(IdentitySeries)).scalar_one(),
                "identity_characters": session.execute(select(func.count()).select_from(IdentityCharacter)).scalar_one(),
            }

    return _safe_db(
        {
            "books": 0,
            "scenes": 0,
            "entities": 0,
            "visual_prompts": 0,
            "generated_images": 0,
            "generated_stories": 0,
            "identity_series": 0,
            "identity_characters": 0,
        },
        "database_summary",
        _query,
    )


def _provider_file(provider_name: str) -> Path:
    mapping = {
        "codex": CODEX_ACCOUNTS_FILE,
    }
    return mapping[str(provider_name).strip().lower()]


def _masked_provider_payload(payload: dict[str, Any]) -> dict[str, Any]:
    masked = {"active_index": int(payload.get("active_index", 0) or 0), "accounts": []}
    for index, item in enumerate(payload.get("accounts") or []):
        if not isinstance(item, dict):
            continue
        masked["accounts"].append(
            {
                "index": int(item.get("index", index) or index),
                "label": str(item.get("label") or f"account-{index + 1}"),
                "email": str(item.get("email") or ""),
                "auth_mode": str(item.get("auth_mode") or ""),
                "account_id": str(item.get("account_id") or ""),
                "has_password": bool(item.get("password")),
                "has_api_key": bool(item.get("api_key")),
                "password": mask_secret(item.get("password") or ""),
                "api_key": mask_secret(item.get("api_key") or ""),
                "active": bool(item.get("active")),
            }
        )
    return masked


def _read_provider_config(provider_name: str, *, mask: bool = True) -> dict[str, Any]:
    provider_key = str(provider_name).strip().lower()
    if provider_key in {OLLAMA_PROVIDER, GENERAL_COMPUTE_PROVIDER}:
        return read_llm_provider_config(provider_key, store=SQLITE_STORE, mask=mask)
    stored = SQLITE_STORE.get_provider_config(provider_key)
    if not isinstance(stored, dict):
        stored = {"provider_name": provider_key, "active_index": 0, "accounts": []}
    return _masked_provider_payload(stored) if mask else stored


def _seed_provider_configs_from_local_files() -> None:
    for provider_key in ("codex",):
        existing = SQLITE_STORE.get_provider_config(provider_key)
        if isinstance(existing, dict) and (existing.get("accounts") or []):
            continue
        raw = load_json(_provider_file(provider_key))
        if not isinstance(raw, dict):
            continue
        payload = {"provider_name": provider_key, "active_index": int(raw.get("active_index", 0) or 0), "accounts": []}
        for index, item in enumerate(raw.get("accounts") or []):
            if not isinstance(item, dict):
                continue
            payload["accounts"].append(
                {
                    "index": index,
                    "label": str(item.get("label") or f"account-{index + 1}"),
                    "email": str(item.get("email") or ""),
                    "auth_mode": str(item.get("auth_mode") or ""),
                    "account_id": str(item.get("account_id") or ""),
                    "password": str(item.get("password") or ""),
                    "api_key": str(item.get("api_key") or ""),
                    "active": index == int(raw.get("active_index", 0) or 0),
                }
            )
        SQLITE_STORE.upsert_provider_config(provider_key, payload)


def _persist_provider_file(provider_name: str, payload: dict[str, Any]) -> None:
    return


def _merge_provider_payload(provider_name: str, incoming_accounts: list[ProviderAccount], active_index: int) -> dict[str, Any]:
    existing = _read_provider_config(provider_name, mask=False) or {"active_index": 0, "accounts": []}
    existing_by_label = {str(item.get("label") or ""): item for item in existing.get("accounts") or []}
    accounts: list[dict[str, Any]] = []
    for index, account in enumerate(incoming_accounts):
        label = account.label.strip() or f"account-{index + 1}"
        previous = existing_by_label.get(label, {})
        merged = {
            "index": index,
            "label": label,
            "email": account.email or str(previous.get("email") or ""),
            "password": account.password or str(previous.get("password") or ""),
            "api_key": account.api_key or str(previous.get("api_key") or ""),
            "auth_mode": str(previous.get("auth_mode") or ""),
            "account_id": str(previous.get("account_id") or ""),
            "metadata": {
                **(dict(previous.get("metadata") or {}) if isinstance(previous.get("metadata"), dict) else {}),
                **(dict(account.metadata or {}) if isinstance(account.metadata, dict) else {}),
            },
            "limits": dict(account.limits or previous.get("limits") or {}) if isinstance(account.limits or previous.get("limits") or {}, dict) else {},
            "usage": dict(account.usage or previous.get("usage") or {}) if isinstance(account.usage or previous.get("usage") or {}, dict) else {},
        }
        if provider_name == "codex" and not merged["api_key"] and CODEX_SESSION_STORE.active_session():
            merged["auth_mode"] = CODEX_SESSION_STORE.active_session().auth_mode or "codex_session"
            merged["account_id"] = CODEX_SESSION_STORE.active_session().account_id or ""
        if provider_name == GENERAL_COMPUTE_PROVIDER:
            merged.pop("email", None)
            merged.pop("password", None)
        if merged.get("api_key") or merged.get("password") or merged.get("auth_mode"):
            accounts.append(merged)
    bounded_index = max(0, min(int(active_index or 0), max(len(accounts) - 1, 0)))
    for idx, row in enumerate(accounts):
        row["active"] = idx == bounded_index
    return {"provider_name": provider_name, "active_index": bounded_index, "accounts": accounts}


def _save_provider_config(provider_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if provider_name in {OLLAMA_PROVIDER, GENERAL_COMPUTE_PROVIDER}:
        return save_llm_provider_config(provider_name, payload, store=SQLITE_STORE)
    SQLITE_STORE.upsert_provider_config(provider_name, payload)
    return _read_provider_config(provider_name, mask=True)


def read_ollama_accounts(mask: bool = True) -> dict[str, Any]:
    return _read_provider_config("ollama", mask=mask)


def merge_and_save_ollama_accounts(config: OllamaProviderConfig) -> dict[str, Any]:
    payload = _merge_provider_payload("ollama", config.accounts, config.active_index)
    return _save_provider_config("ollama", payload)


def read_codex_accounts(mask: bool = True) -> dict[str, Any]:
    payload = _read_provider_config("codex", mask=mask)
    if not payload.get("accounts") and mask:
        session = CODEX_SESSION_STORE.active_session()
        if session:
            payload["accounts"] = [{
                "index": 0,
                "label": "codex-session",
                "email": "",
                "auth_mode": session.auth_mode or "codex_session",
                "account_id": session.account_id or "",
                "has_password": False,
                "has_api_key": False,
                "password": "",
                "api_key": "",
                "active": True,
            }]
    return payload


def merge_and_save_codex_accounts(config: CodexProviderConfig) -> dict[str, Any]:
    payload = _merge_provider_payload("codex", config.accounts, config.active_index)
    return _save_provider_config("codex", payload)


def read_general_compute_accounts(mask: bool = True) -> dict[str, Any]:
    return _read_provider_config("general_compute", mask=mask)


def merge_and_save_general_compute_accounts(config: GeneralComputeProviderConfig) -> dict[str, Any]:
    payload = _merge_provider_payload("general_compute", config.accounts, config.active_index)
    return _save_provider_config("general_compute", payload)


def read_tts_modal_provider(mask: bool = True) -> dict[str, Any]:
    legacy = SQLITE_STORE.get_provider_config(LEGACY_TTS_MODAL_PROVIDER) or {}
    if isinstance(legacy, dict) and legacy:
        payload = dict(legacy)
        if mask:
            payload = dict(payload)
            masked_accounts: list[dict[str, Any]] = []
            for item in payload.get("accounts") or []:
                if not isinstance(item, dict):
                    continue
                masked = dict(item)
                if masked.get("token_secret"):
                    masked["token_secret"] = "***"
                masked_accounts.append(masked)
            payload["accounts"] = masked_accounts
    else:
        payload = read_inference_provider_config(MODAL_KOKORO_PROVIDER, store=SQLITE_STORE, mask=mask)
    payload["timeout_seconds"] = int(payload.get("request_timeout_seconds") or 300)
    return payload


def save_tts_modal_provider(config: TTSModalProviderConfig) -> dict[str, Any]:
    payload = {
        "provider_name": MODAL_KOKORO_PROVIDER,
        "app_name": str(config.app_name or DEFAULT_TTS_MODAL_APP_NAME).strip() or DEFAULT_TTS_MODAL_APP_NAME,
        "api_url": str(config.api_url or "").strip(),
        "default_voice": str(config.default_voice or "af_bella").strip() or "af_bella",
        "default_lang_code": str(config.default_lang_code or "a").strip() or "a",
        "default_sample_rate": max(8000, int(config.default_sample_rate or 24000)),
        "default_audio_format": str(config.default_audio_format or "wav").strip().lower() or "wav",
        "default_normalize_audio": bool(config.default_normalize_audio),
        "default_trim_silence": bool(config.default_trim_silence),
        "default_sentence_pause_ms": max(0, int(config.default_sentence_pause_ms or 0)),
        "request_timeout_seconds": max(30, int(config.timeout_seconds or 300)),
        "accounts": [],
        "transport": "modal_api",
    }
    save_inference_provider_config(MODAL_KOKORO_PROVIDER, payload, store=SQLITE_STORE)
    SQLITE_STORE.upsert_provider_config(
        LEGACY_TTS_MODAL_PROVIDER,
        {
            **payload,
            "provider_name": LEGACY_TTS_MODAL_PROVIDER,
        },
    )
    save_inference_selection(SPEECH_CAPABILITY, MODAL_KOKORO_PROVIDER, store=SQLITE_STORE)
    return read_tts_modal_provider(mask=True)


def read_prompts() -> list[dict[str, Any]]:
    prompts = []
    for relative in PROMPT_FILES:
        path = ROOT / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        prompt_hits = [
            line.strip()
            for line in text.splitlines()
            if "prompt" in line.lower() or "you are" in line.lower() or "return only valid json" in line.lower()
        ][:30]
        prompts.append(
            {
                "path": relative,
                "name": path.name,
                "line_count": len(text.splitlines()),
                "size_bytes": path.stat().st_size,
                "prompt_hits": prompt_hits,
            }
        )
    return prompts


def db_identity_summaries(limit: int = 50) -> list[dict[str, Any]]:
    with SQLITE_STORE.session_factory() as session:
        rows = session.execute(select(SqlIdentitySeries).order_by(SqlIdentitySeries.updated_at.desc())).scalars().all()
        summaries: list[dict[str, Any]] = []
        for row in rows[:limit]:
            book_count = session.execute(select(func.count()).select_from(SqlIdentityBook).where(SqlIdentityBook.identity_series_id == row.id)).scalar_one()
            summaries.append(
                {
                    "series_id": row.series_id,
                    "provider": row.provider or "booknlp_clean",
                    "source_path": row.source_path or "",
                    "character_count": int(row.character_count or 0),
                    "alias_count": int(row.alias_count or 0),
                    "reference_entity_count": int(row.reference_entity_count or 0),
                    "narrator_count": int(row.narrator_count or 0),
                    "book_count": int(book_count or 0),
                    "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else "",
                    "diagnostics": row.metadata_json or {},
                }
            )
        return summaries


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_probe_ollama_account(account: dict[str, Any]) -> dict[str, Any]:
    api_key = str(account.get("api_key") or "").strip() or None
    model_name = LLMClient(mode=LLMClient.MODE_GPT_OSS).resolved_model_name()
    try:
        probe = LLMClient.probe_ollama_mode_access(LLMClient.MODE_GPT_OSS, model_name, api_key=api_key)
    except Exception as exc:
        probe = {"status": "error", "detail": repr(exc)}
    quota_source = "provider_api_unavailable" if api_key else "local_runtime"
    return {
        "provider_name": "ollama",
        "label": str(account.get("label") or ""),
        "probe_status": str(probe.get("status") or "unknown"),
        "transport": "ollama_cloud" if api_key else "ollama_local",
        "resolved_model": str(probe.get("model") or model_name),
        "quota_source": quota_source,
        "credits_remaining": "unknown",
        "detail": str(probe.get("detail") or ("Live model probe succeeded." if probe.get("status") == "ok" else "")).strip(),
        "last_checked_at_utc": _utc_now_iso(),
        "payload": probe,
    }


def _safe_probe_general_compute_account(account: dict[str, Any]) -> dict[str, Any]:
    rotator = GeneralComputeAccountRotator()
    raw = read_llm_provider_config(GENERAL_COMPUTE_PROVIDER, store=SQLITE_STORE, mask=False)
    raw_accounts = list((raw or {}).get("accounts") or []) if isinstance(raw, dict) else []
    raw_match = next((row for row in raw_accounts if str(row.get("label") or "") == str(account.get("label") or "")), {})
    api_key = str(account.get("api_key") or "").strip() or None
    model_name = LLMClient(mode=LLMClient.MODE_GENERAL_COMPUTE).resolved_model_name()
    try:
        probe = LLMClient.probe_general_compute_model_access(model_name, api_key=api_key)
    except Exception as exc:
        probe = {"status": "error", "detail": repr(exc)}
    limits = rotator._limits(raw_match) if isinstance(raw_match, dict) else {}
    usage = rotator._usage(raw_match) if isinstance(raw_match, dict) else {}
    return {
        "provider_name": "general_compute",
        "label": str(account.get("label") or ""),
        "probe_status": str(probe.get("status") or "unknown"),
        "transport": "general_compute_api",
        "resolved_model": str(probe.get("model") or model_name),
        "quota_source": "local_budget_tracking",
        "remaining_requests_minute": max(0, int(limits.get("requests_per_minute", 0)) - int(usage.get("minute_requests", 0))),
        "remaining_input_tokens_minute": max(0, int(limits.get("input_tokens_per_minute", 0)) - int(usage.get("minute_input_tokens", 0))),
        "remaining_output_tokens_minute": max(0, int(limits.get("output_tokens_per_minute", 0)) - int(usage.get("minute_output_tokens", 0))),
        "remaining_requests_day": max(0, int(limits.get("requests_per_day", 0)) - int(usage.get("day_requests", 0))),
        "remaining_tokens_day": max(0, int(limits.get("tokens_per_day", 0)) - int(usage.get("day_tokens", 0))),
        "credits_remaining": "unknown",
        "detail": str(probe.get("detail") or ("Live model probe succeeded." if probe.get("status") == "ok" else "")).strip(),
        "last_checked_at_utc": _utc_now_iso(),
        "payload": {**probe, "usage": usage, "limits": limits},
    }


def _safe_probe_codex_account(account: dict[str, Any]) -> dict[str, Any]:
    api_key = str(account.get("api_key") or "").strip() or None
    model_name = LLMClient(mode=LLMClient.MODE_CODEX).resolved_model_name()
    try:
        probe = LLMClient.probe_codex_model_access(model_name, api_key=api_key)
    except Exception as exc:
        probe = {"status": "error", "detail": repr(exc)}
    transport = str(probe.get("transport") or ("codex_session" if str(account.get("auth_mode") or "").strip() else "openai_api"))
    return {
        "provider_name": "codex",
        "label": str(account.get("label") or ""),
        "probe_status": str(probe.get("status") or "unknown"),
        "transport": transport,
        "resolved_model": str(probe.get("model") or model_name),
        "quota_source": "provider_api_unavailable",
        "credits_remaining": "unknown",
        "detail": str(probe.get("detail") or ("Live model probe succeeded." if probe.get("status") == "ok" else "")).strip(),
        "last_checked_at_utc": _utc_now_iso(),
        "payload": probe,
    }


def _safe_probe_inference_provider(provider_name: str, config: dict[str, Any]) -> dict[str, Any]:
    provider_key = str(provider_name or "").strip().lower()
    app_name = str(config.get("app_name") or "").strip()
    api_url = str(config.get("api_url") or "").strip()
    detail_parts: list[str] = []
    probe_status = "unconfigured"
    if api_url:
        probe_status = "ready"
        detail_parts.append("Configured provider API URL is present.")

    accounts = list(config.get("accounts") or [])
    if not api_url and accounts:
        try:
            provider = resolve_provider(provider_name=provider_key, store=SQLITE_STORE)
            live = provider.ensure_live()
            api_url = str(live.get("api_url") or "").strip()
            probe_status = "ready"
            token_name = str(live.get("token_name") or "").strip()
            if token_name:
                detail_parts.append(f"Resolved provider API URL from account '{token_name}'.")
            else:
                detail_parts.append("Resolved provider API URL from the active pool.")
        except Exception as exc:
            probe_status = "error"
            detail_parts.append(f"Provider probe failed: {type(exc).__name__}")
    elif not api_url and not accounts:
        detail_parts.append("No explicit API URL and no provider accounts were available.")

    resolved_model = ""
    if provider_key == MODAL_KOKORO_PROVIDER:
        resolved_model = f"{str(config.get('default_voice') or 'af_bella')}/{str(config.get('default_lang_code') or 'a')}"
    elif provider_key == MODAL_XCORE_PROVIDER:
        resolved_model = str(config.get("model_name") or "sapienzanlp/xcore-litbank")
    elif provider_key == MODAL_COMFYUI_PROVIDER:
        resolved_model = str(config.get("app_name") or "graduation-comfyui")
    return {
        "provider_name": provider_key,
        "label": app_name or provider_key,
        "probe_status": probe_status,
        "transport": str(config.get("transport") or "modal_api"),
        "resolved_model": resolved_model,
        "quota_source": "modal_token_pool",
        "credits_remaining": "unknown",
        "detail": " ".join(detail_parts).strip() or "No provider detail recorded.",
        "last_checked_at_utc": _utc_now_iso(),
        "payload": {
            "app_name": app_name,
            "api_url": api_url,
            "health_url": str(config.get("health_url") or ""),
            "ui_url": str(config.get("ui_url") or ""),
            "request_timeout_seconds": int(config.get("request_timeout_seconds") or config.get("timeout_seconds") or 300),
        },
    }


def _safe_probe_tts_modal_provider(config: dict[str, Any]) -> dict[str, Any]:
    payload = dict(config or {})
    payload.setdefault("provider_name", LEGACY_TTS_MODAL_PROVIDER)
    payload.setdefault("request_timeout_seconds", int(payload.get("timeout_seconds") or 300))
    probe = _safe_probe_inference_provider(MODAL_KOKORO_PROVIDER, payload)
    probe["provider_name"] = LEGACY_TTS_MODAL_PROVIDER
    return probe


def _tts_modal_status_payload(*, refresh: bool) -> dict[str, Any]:
    config = read_tts_modal_provider(mask=True)
    statuses = list(SQLITE_STORE.get_provider_statuses(LEGACY_TTS_MODAL_PROVIDER) or [])
    if refresh:
        probe = _safe_probe_tts_modal_provider(read_tts_modal_provider(mask=False))
        statuses = SQLITE_STORE.replace_provider_statuses(LEGACY_TTS_MODAL_PROVIDER, [probe])
    return {"config": config, "statuses": statuses}


def refresh_provider_statuses() -> dict[str, Any]:
    payload = refresh_provider_statuses_service(store=SQLITE_STORE)
    return dict(payload.get("providers") or {})


def reduce_contract_row(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {"description": str(row)}
    allowed_keys = [
        "id",
        "title",
        "scene_id",
        "event_id",
        "character_id",
        "character_name",
        "entity_id",
        "entity_name",
        "chapter_index",
        "scene_index",
        "scene_summary",
        "summary",
        "name",
        "display_name",
        "canonical_name",
        "event",
        "description",
        "type",
        "event_type",
        "relationship_type",
        "state",
        "evidence",
        "notes",
        "location",
        "event_location",
        "characters",
        "entities_present",
        "events",
        "state_changes",
        "relationship_changes",
        "visual_analysis",
        "persistent_visual_profile",
        "dynamic_visual_changes",
        "persistent_visual_prompt",
        "aliases",
        "roles",
        "affiliations",
        "entity_type",
        "first_seen",
        "mention_count",
        "descriptions",
        "state_changes",
        "event_links",
        "initial_physical_description",
        "visual_change_log",
        "entity_context",
        "analysis_quality_flags",
        "core_description",
        "traits",
        "personality",
        "goals",
        "fears",
        "loyalties",
        "abilities",
        "constraints",
        "important_history",
        "relationship_id",
        "source_character",
        "target_character",
        "relationship_type",
        "baseline_dynamic",
        "trust_level",
        "conflict_level",
        "romantic_signal",
        "shared_history",
        "change_log",
        "participants",
        "entities_involved",
        "reason",
        "outcome",
        "text",
        "positive_prompt",
        "image_edit_prompt",
        "prompt_type",
        "beat_title",
        "visual_bucket",
        "visual_bucket_label",
        "source_evidence",
        "confidence",
        "details",
        "generated_image_path",
        "render_status",
        "negative_prompt",
        "baseline_prompt",
        "baseline_prompt_type",
        "baseline_source_evidence",
        "baseline_confidence",
        "baseline_details",
        "change_prompts",
        "scene_prompts",
        "entity_world_state",
        "typed_attributes",
        "narrative_roles",
        "first_appearance_profile",
        "latest_world_state",
        "visual_profile",
        "world_state_profile",
        "relationship_refs",
        "attributes",
        "latest_state",
        "agent_metadata",
        "state_history",
        "state_at_latest",
        "tool_runtime",
        "provider",
        "model",
        "resolved_model",
        "provider_account_alias",
        "rotation_used",
        "rotation_attempt_count",
        "fallback_used",
        "analysis_duration_seconds",
        "book_index",
        "final_status",
    ]
    reduced: dict[str, Any] = {}
    for key in allowed_keys:
        value = row.get(key)
        if value in (None, "", [], {}):
            continue
        reduced[key] = value
    return reduced


def _merge_character_sheet_renders(
    contract_path: Path,
    visual_sections: dict[str, list[Any]],
) -> dict[str, Any]:
    manifest_path = render_manifest_path_for_contract(contract_path)
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        return {}
    rows = (manifest.get("render_report") or {}).get("renders") or manifest.get("renders") or []
    render_map: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = str(row.get("entity_name") or "").strip().lower()
        if not key:
            continue
        render_map[key] = row
    enriched = []
    for row in visual_sections.get("initial_characters", []):
        if not isinstance(row, dict):
            enriched.append(row)
            continue
        match = render_map.get(str(row.get("entity_name") or "").strip().lower())
        if match:
            merged = dict(row)
            merged["generated_image_path"] = match.get("relative_output_path") or match.get("output_path") or ""
            merged["render_status"] = match.get("status") or "rendered"
            merged["negative_prompt"] = match.get("negative_prompt") or ""
            if match.get("positive_prompt"):
                merged["positive_prompt"] = match.get("positive_prompt")
            enriched.append(merged)
        else:
            enriched.append(row)
    visual_sections["initial_characters"] = enriched
    return {
        "manifest_path": rel(manifest_path),
        "render_count": len(rows),
        "rendered_count": sum(1 for row in rows if Path(str((row or {}).get("output_path") or "")).exists()),
    }


def _render_map_for_contract(contract_path: Path) -> dict[str, dict[str, Any]]:
    manifest_path = render_manifest_path_for_contract(contract_path)
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        return {}
    rows = (manifest.get("render_report") or {}).get("renders") or manifest.get("renders") or []
    render_map: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = str(row.get("entity_name") or "").strip().lower()
        if not key:
            continue
        render_map[key] = row
    return render_map


def _build_visual_inventory(
    *,
    entity_registry: list[dict[str, Any]],
    visual_sections: dict[str, list[Any]],
    render_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    baseline_map: dict[tuple[str, str], dict[str, Any]] = {}
    change_map: dict[tuple[str, str], list[dict[str, Any]]] = {}
    scene_map: dict[str, list[dict[str, Any]]] = {}

    for bucket in ["initial_characters", "objects_creatures", "locations"]:
        for row in visual_sections.get(bucket, []):
            if not isinstance(row, dict):
                continue
            name = str(row.get("entity_name") or "").strip()
            entity_type = str(row.get("entity_type") or "").strip().lower()
            if not name or not entity_type:
                continue
            baseline_map[(name.lower(), entity_type)] = row

    for row in visual_sections.get("character_changes", []):
        if not isinstance(row, dict):
            continue
        name = str(row.get("entity_name") or "").strip()
        entity_type = str(row.get("entity_type") or "character").strip().lower() or "character"
        if not name:
            continue
        change_map.setdefault((name.lower(), entity_type), []).append(row)

    for row in visual_sections.get("scene_compositions", []):
        if not isinstance(row, dict):
            continue
        entity_names = [
            str(item).strip()
            for item in (row.get("details") or {}).get("entities", row.get("entities") or [])
            if str(item).strip()
        ]
        for name in entity_names:
            scene_map.setdefault(name.lower(), []).append(row)

    inventory: list[dict[str, Any]] = []
    for entity in entity_registry:
        if not isinstance(entity, dict):
            continue
        name = str(entity.get("name") or "").strip()
        entity_type = str(entity.get("entity_type") or "").strip().lower()
        if not name or entity_type not in {"character", "location", "object", "creature"}:
            continue
        key = (name.lower(), entity_type)
        baseline = baseline_map.get(key) or {}
        changes = change_map.get(key, [])
        render = render_map.get(name.lower()) or {}
        inventory.append(
            {
                "name": name,
                "entity_type": entity_type,
                "mention_count": entity.get("mention_count"),
                "first_seen": entity.get("first_seen") or {},
                "entity_context": entity.get("entity_context") or "",
                "initial_physical_description": entity.get("initial_physical_description") or {},
                "first_appearance_profile": entity.get("first_appearance_profile") or {},
                "typed_attributes": entity.get("typed_attributes") or {},
                "analysis_quality_flags": entity.get("analysis_quality_flags") or [],
                "baseline_prompt": str(baseline.get("positive_prompt") or "").strip(),
                "baseline_prompt_type": str(baseline.get("prompt_type") or "").strip(),
                "baseline_source_evidence": str(baseline.get("source_evidence") or "").strip(),
                "baseline_confidence": str(baseline.get("confidence") or "").strip(),
                "baseline_details": baseline.get("details") or {},
                "change_prompts": [
                    {
                        "prompt": str(row.get("image_edit_prompt") or row.get("positive_prompt") or "").strip(),
                        "prompt_type": str(row.get("prompt_type") or "").strip(),
                        "source_evidence": str(row.get("source_evidence") or "").strip(),
                        "confidence": str(row.get("confidence") or "").strip(),
                        "book_index": row.get("book_index"),
                        "chapter_index": row.get("chapter_index"),
                        "scene_index": row.get("scene_index"),
                    }
                    for row in changes
                    if str(row.get("image_edit_prompt") or row.get("positive_prompt") or "").strip()
                ][:8],
                "scene_prompts": [
                    {
                        "beat_title": str(row.get("entity_name") or row.get("details", {}).get("beat_title") or "").strip(),
                        "prompt": str(row.get("positive_prompt") or "").strip(),
                        "source_evidence": str(row.get("source_evidence") or "").strip(),
                        "confidence": str(row.get("confidence") or "").strip(),
                        "book_index": row.get("book_index"),
                        "chapter_index": row.get("chapter_index"),
                        "scene_index": row.get("scene_index"),
                    }
                    for row in scene_map.get(name.lower(), [])
                    if str(row.get("positive_prompt") or "").strip()
                ][:6],
                "generated_image_path": str(render.get("relative_output_path") or render.get("output_path") or "").strip(),
                "negative_prompt": str(render.get("negative_prompt") or "").strip(),
                "render_status": str(render.get("status") or "").strip(),
            }
        )
    return inventory


def _db_book_by_contract_path(path: Path | str) -> SqlBook | None:
    raw = str(path)
    book_id = parse_db_book_ref(raw)
    with SQLITE_STORE.session_factory() as session:
        if book_id:
            return session.get(SqlBook, book_id)
        if raw.startswith("db://book/"):
            return None
        normalized = str(Path(raw).resolve())
        books = session.execute(select(SqlBook)).scalars().all()
        for book in books:
            source_path = str(book.source_path or "").strip()
            contract_path = str(book.contract_path or "").strip()
            candidates = [item for item in [contract_path, source_path] if item]
            for candidate in candidates:
                try:
                    if str(Path(candidate).resolve()) == normalized:
                        return book
                except OSError:
                    if candidate == normalized:
                        return book
    return None


def _db_contract_view(path: Path | str, *, limit: int = 200, section: str | None = None) -> dict[str, Any] | None:
    book_row = _db_book_by_contract_path(path)
    if book_row is None:
        return None
    with SQLITE_STORE.session_factory() as session:
        book = session.get(SqlBook, book_row.id)
        if book is None:
            return None
        requested_section = str(section or "all").strip().lower()
        if requested_section not in {"all", "", "scenes", "entities", "events", "timeline", "states", "world", "visuals"}:
            requested_section = "all"

        def include_output(name: str) -> bool:
            if requested_section in {"", "all"}:
                return True
            return name == requested_section

        chapters = session.execute(select(SqlChapter).where(SqlChapter.book_id == book.id).order_by(SqlChapter.chapter_index.asc())).scalars().all()
        scenes = session.execute(select(SqlScene).where(SqlScene.book_id == book.id).order_by(SqlScene.chapter_index.asc(), SqlScene.scene_index.asc())).scalars().all()
        events = session.execute(select(SqlEvent).where(SqlEvent.book_id == book.id).order_by(SqlEvent.chapter_index.asc(), SqlEvent.scene_index.asc())).scalars().all()
        should_load_entities = include_output("entities") or include_output("visuals")
        entities = session.execute(
            select(SqlEntity)
            .options(defer(SqlEntity.generated_image_bytes))
            .where(SqlEntity.book_id == book.id)
            .order_by(SqlEntity.entity_type.asc(), SqlEntity.canonical_name.asc())
        ).scalars().all() if should_load_entities else []
        entity_count = len(entities) if should_load_entities else int(session.execute(select(func.count()).select_from(SqlEntity).where(SqlEntity.book_id == book.id)).scalar_one() or 0)
        profiles = session.execute(select(SqlCharacterProfile).where(SqlCharacterProfile.book_id == book.id)).scalars().all()
        states = session.execute(select(SqlStableCharacterState).where(SqlStableCharacterState.book_id == book.id)).scalars().all()
        timeline = session.execute(select(SqlTimelineRow).where(SqlTimelineRow.book_id == book.id).order_by(SqlTimelineRow.row_index.asc())).scalars().all()
        prompts = session.execute(select(SqlVisualPrompt).where(SqlVisualPrompt.book_id == book.id)).scalars().all() if include_output("visuals") else []
        images = session.execute(
            select(
                SqlGeneratedImage.entity_name,
                SqlGeneratedImage.entity_type,
                SqlGeneratedImage.output_path,
                SqlGeneratedImage.render_status,
            ).where(SqlGeneratedImage.book_id == book.id)
        ).all() if include_output("visuals") else []

        prompt_map = {}
        for row in prompts:
            key = (str(row.entity_name or "").lower(), str(row.entity_type or "").lower())
            prompt_map.setdefault(key, row)
        image_map = {}
        for row in images:
            key = (str(row.entity_name or "").lower(), str(row.entity_type or "").lower())
            image_map.setdefault(
                key,
                {
                    "output_path": str(row.output_path or ""),
                    "render_status": str(row.render_status or ""),
                },
            )

        entity_rows = []
        visual_inventory = []
        for entity in entities:
            key = (str(entity.canonical_name or "").lower(), str(entity.entity_type or "").lower())
            prompt = prompt_map.get(key)
            image = image_map.get(key)
            initial_physical_description = _clean_analysis_dict(entity.initial_physical_description or {})
            first_appearance_profile = _clean_analysis_dict(entity.first_appearance_profile or {})
            latest_world_state = _clean_analysis_dict(entity.latest_world_state or {})
            descriptions = _clean_analysis_list(entity.descriptions or [])[:8]
            state_changes = _clean_analysis_list(entity.state_changes or [])[:8]
            event_links = _clean_analysis_list(entity.event_links or [])[:8]
            narrative_roles = _clean_analysis_list(entity.narrative_roles or [])[:8]
            visual_change_log = _clean_analysis_list(entity.visual_change_log or [])[:8]
            analysis_quality_flags = _clean_analysis_list(entity.analysis_quality_flags or [])[:8]
            scene_visual_states = _clean_analysis_list(((entity.metadata_json or {}).get("scene_visual_states") or []))[:8]

            if initial_physical_description and "description" not in initial_physical_description:
                baseline_fields = initial_physical_description.get("baseline_visual_fields") or {}
                description = _summarize_analysis_fields(
                    baseline_fields,
                    [
                        "gender_presentation",
                        "species_or_race",
                        "apparent_age_group",
                        "height_impression",
                        "build",
                        "skin_tone_or_complexion",
                        "hair_color",
                        "hair_length_or_style",
                        "eye_color",
                        "facial_features",
                        "distinguishing_marks",
                        "location_class",
                        "indoor_outdoor",
                        "environment_type",
                        "region_or_domain",
                        "architecture_or_terrain_style",
                        "object_class",
                        "function",
                        "primary_material",
                        "species_kind",
                        "size_class",
                        "body_plan",
                        "head_features",
                    ],
                )
                if description:
                    initial_physical_description["description"] = description

            if first_appearance_profile and "baseline_description" not in first_appearance_profile:
                persistent_traits = first_appearance_profile.get("persistent_traits") or {}
                baseline_description = _summarize_analysis_fields(
                    persistent_traits,
                    [
                        "gender_presentation",
                        "species_or_race",
                        "apparent_age_group",
                        "height_impression",
                        "build",
                        "skin_tone_or_complexion",
                        "hair_color",
                        "hair_length_or_style",
                        "eye_color",
                        "facial_features",
                        "distinguishing_marks",
                        "default_clothing_style",
                        "default_accessories",
                        "default_footwear",
                        "signature_items",
                        "location_class",
                        "environment_type",
                        "architecture_or_terrain_style",
                        "object_class",
                        "function",
                        "primary_material",
                        "species_kind",
                        "size_class",
                        "body_plan",
                        "head_features",
                    ],
                )
                if baseline_description:
                    first_appearance_profile["baseline_description"] = baseline_description

            first_seen = {
                "book_index": entity.first_seen_book_index,
                "chapter_index": entity.first_seen_chapter_index,
                "scene_index": entity.first_seen_scene_index,
            }
            entity_row = {
                "name": entity.canonical_name,
                "entity_type": entity.entity_type,
                "mention_count": entity.mention_count,
                "first_seen": first_seen,
                "entity_context": _clean_analysis_text(entity.entity_context),
                "initial_physical_description": initial_physical_description,
                "first_appearance_profile": first_appearance_profile,
                "typed_attributes": _clean_analysis_dict(entity.typed_attributes or {}),
                "persistent_traits": (first_appearance_profile.get("persistent_traits") or latest_world_state.get("persistent_traits") or {}),
                "descriptions": descriptions,
                "state_changes": state_changes,
                "event_links": event_links,
                "narrative_roles": narrative_roles,
                "latest_world_state": latest_world_state,
                "visual_change_log": visual_change_log,
                "scene_visual_states": scene_visual_states,
                "analysis_quality_flags": analysis_quality_flags,
                "baseline_visual_prompt": entity.baseline_visual_prompt or "",
                "generated_image_path": entity.generated_image_path or "",
            }
            entity_rows.append(entity_row)
            visual_inventory.append({
                **entity_row,
                "baseline_prompt": entity.baseline_visual_prompt or str(getattr(prompt, "positive_prompt", "") or ""),
                "baseline_prompt_type": str(getattr(prompt, "prompt_type", "") or ""),
                "baseline_source_evidence": str(getattr(prompt, "source_evidence", "") or ""),
                "baseline_confidence": str(getattr(prompt, "confidence", "") or ""),
                "baseline_details": getattr(prompt, "details_json", None) or {},
                "change_prompts": [],
                "scene_prompts": [],
                "generated_image_path": entity.generated_image_path or str((image or {}).get("output_path") or ""),
                "negative_prompt": str(getattr(prompt, "negative_prompt", "") or ""),
                "render_status": str((image or {}).get("render_status") or ""),
            })

        chapter_title_map = {
            int(chapter.chapter_index or 0): str(chapter.title or "").strip()
            for chapter in chapters
        }
        scene_rows = []
        for scene in scenes:
            row = dict(scene.payload_json or {})
            row.setdefault("book_index", scene.book_index)
            row.setdefault("chapter_index", scene.chapter_index)
            row.setdefault("scene_index", scene.scene_index)
            row.setdefault("scene_summary", scene.summary)
            row.setdefault("summary", scene.summary)
            row.setdefault("title", chapter_title_map.get(int(scene.chapter_index or 0)) or scene.summary or f"Chapter {scene.chapter_index} Scene {scene.scene_index}")
            row.setdefault("text", scene.text)
            row.setdefault("location", {"name": scene.location_name, "description": scene.location_description})
            row.setdefault("final_status", scene.final_status)
            row.setdefault("error_category", scene.error_category)
            row.setdefault("last_error", scene.last_error)
            row.setdefault("provider", scene.provider)
            row.setdefault("model", scene.model)
            row.setdefault("provider_account_alias", scene.provider_account_alias)
            row.setdefault("rotation_used", scene.rotation_used)
            row.setdefault("rotation_attempt_count", scene.rotation_attempt_count)
            row.setdefault("analysis_duration_seconds", scene.analysis_duration_seconds)
            scene_rows.append(row)

        event_rows = []
        for event in events:
            row = dict(event.payload_json or {})
            row.setdefault("ledger_event_id", event.event_id_external)
            row.setdefault("event_id", event.event_id_external)
            row.setdefault("event_type", event.event_type)
            row.setdefault("type", event.event_type)
            row.setdefault("description", event.description)
            row.setdefault("summary", event.description)
            row.setdefault("title", event.description)
            row.setdefault("reason", event.reason)
            row.setdefault("outcome", event.outcome)
            row.setdefault("entities_involved", event.entities_involved or [])
            row.setdefault("chapter_index", event.chapter_index)
            row.setdefault("scene_index", event.scene_index)
            row.setdefault("participants", row.get("characters") or [])
            if not row.get("location"):
                location_name = ""
                if isinstance(event.entities_involved, dict):
                    location_value = event.entities_involved.get("location") or event.entities_involved.get("locations")
                    if isinstance(location_value, list):
                        location_name = ", ".join(str(item).strip() for item in location_value if str(item).strip())
                    else:
                        location_name = str(location_value or "").strip()
                location_name = location_name or str(row.get("event_location") or row.get("location_name") or "").strip()
                if location_name:
                    row["location"] = {"name": location_name}
            event_rows.append(row)
        timeline_rows = [row.payload_json or {} for row in timeline]
        profile_rows = [row.payload_json or {"character_name": row.character_name} for row in profiles]
        state_rows = [row.payload_json or {"character_name": row.character_name} for row in states]
        relationship_profiles = RelationshipProfileBuilder().build(scene_analyses=scene_rows)
        quality = book.scene_analysis_quality if isinstance(book.scene_analysis_quality, dict) else {}
        successful_scenes = quality.get("successful_scenes")
        failed_scenes = quality.get("failed_scenes")
        if successful_scenes is None and failed_scenes is None and scene_rows:
            successful_scenes = len(scene_rows)
            failed_scenes = 0
        summary = {
            "path": str(path) if is_db_book_ref(str(path)) else rel(Path(path)),
            "name": book.title.replace(".contract.json", ""),
            "mtime": book.updated_at.timestamp() if getattr(book, "updated_at", None) else 0,
            "size_mb": round((Path(path).stat().st_size / (1024 * 1024)), 2) if not is_db_book_ref(str(path)) and Path(path).exists() else 0.0,
            "run_status": book.run_status or "unknown",
            "identity_provider": book.identity_provider or "n/a",
            "scenes": len(scene_rows),
            "successful_scenes": successful_scenes,
            "failed_scenes": failed_scenes,
            "entity_registry": entity_count,
            "timeline": len(timeline_rows),
            "event_ledger": len(event_rows),
            "character_profiles": len(profile_rows),
            "stable_character_states": len(state_rows),
            "story_index_docs": 0,
        }
        scene_payload = [reduce_contract_row(row) for row in scene_rows[:limit]] if include_output("scenes") else []
        event_payload = [reduce_contract_row(row) for row in event_rows[:limit]] if include_output("events") else []
        entity_payload = [reduce_contract_row(row) for row in entity_rows[:limit]] if include_output("entities") else []
        timeline_payload = [reduce_contract_row(row) for row in timeline_rows[:limit]] if include_output("timeline") else []
        state_payload = [reduce_contract_row(row) for row in state_rows[:limit]] if include_output("states") else []
        world_payload = [
            reduce_contract_row({
                "scene_id": f"b{row.get('book_index', '?')}_c{row.get('chapter_index', '?')}_s{row.get('scene_index', '?')}",
                "book_index": row.get("book_index"),
                "chapter_index": row.get("chapter_index"),
                "scene_index": row.get("scene_index"),
                "scene_summary": row.get("scene_summary") or "",
                "location": row.get("location") or {},
                "visual_analysis": row.get("visual_analysis") or {},
                "entity_world_state": row.get("entity_world_state") or {},
                "state_changes": row.get("state_changes") or [],
                "relationship_changes": row.get("relationship_changes") or [],
                "text": row.get("text") or "",
            })
            for row in scene_rows[:limit]
        ] if include_output("world") else []
        visual_payload = [reduce_contract_row(row) for row in visual_inventory[:limit]] if include_output("visuals") else []
        visual_prompt_sets_payload = {
            "initial_characters": [reduce_contract_row({
                "entity_name": item["name"],
                "entity_type": item["entity_type"],
                "positive_prompt": item["baseline_prompt"],
                "generated_image_path": item["generated_image_path"],
                "prompt_type": item["baseline_prompt_type"],
                "source_evidence": item["baseline_source_evidence"],
                "confidence": item["baseline_confidence"],
            }) for item in visual_inventory if item["entity_type"] == "character"][:limit],
            "objects_creatures": [reduce_contract_row({
                "entity_name": item["name"],
                "entity_type": item["entity_type"],
                "positive_prompt": item["baseline_prompt"],
                "generated_image_path": item["generated_image_path"],
                "prompt_type": item["baseline_prompt_type"],
                "source_evidence": item["baseline_source_evidence"],
                "confidence": item["baseline_confidence"],
            }) for item in visual_inventory if item["entity_type"] in {"object", "creature"}][:limit],
            "locations": [reduce_contract_row({
                "entity_name": item["name"],
                "entity_type": item["entity_type"],
                "positive_prompt": item["baseline_prompt"],
                "generated_image_path": item["generated_image_path"],
                "prompt_type": item["baseline_prompt_type"],
                "source_evidence": item["baseline_source_evidence"],
                "confidence": item["baseline_confidence"],
            }) for item in visual_inventory if item["entity_type"] == "location"][:limit],
            "character_changes": [],
            "scene_compositions": [],
        } if include_output("visuals") else {}
        return {
            "path": str(path) if is_db_book_ref(str(path)) else rel(Path(path)),
            "summary": summary,
            "metadata": (book.metadata_json or {}).get("metadata") or {},
            "outputs": {
                "resolved_scene_analyses": scene_payload,
                "event_ledger": event_payload,
                "entity_registry": entity_payload,
                "timeline": timeline_payload,
                "character_profiles": [reduce_contract_row(row) for row in profile_rows[:limit]],
                "stable_character_states": state_payload,
                "relationship_profiles": [reduce_contract_row(row) for row in relationship_profiles[:limit]],
                "scene_world_state": world_payload,
                "visual_prompt_sets": visual_prompt_sets_payload,
                "visual_inventory": visual_payload,
                "visual_prompt_diagnostics": {},
            },
            "counts": {
                "resolved_scene_analyses": len(scene_rows),
                "event_ledger": len(event_rows),
                "entity_registry": entity_count,
                "timeline": len(timeline_rows),
                "character_profiles": len(profile_rows),
                "stable_character_states": len(state_rows),
                "relationship_profiles": len(relationship_profiles),
                "scene_world_state": len(scene_rows),
                "visual_initial_characters": len([row for row in visual_inventory if row["entity_type"] == "character"]),
                "visual_objects_creatures": len([row for row in visual_inventory if row["entity_type"] in {"object", "creature"}]),
                "visual_locations": len([row for row in visual_inventory if row["entity_type"] == "location"]),
                "visual_character_changes": 0,
                "visual_scene_compositions": 0,
                "visual_inventory": len(visual_inventory) if include_output("visuals") else entity_count,
            },
            "render_summary": {
                "manifest_path": rel(render_manifest_path_for_contract(path)) if render_manifest_path_for_contract(path).exists() else "",
                "render_count": len(images),
                "rendered_count": len([row for row in images if str(row.output_path or "").strip()]),
            },
            "truncated_at": limit,
        }


def contract_view(path: Path, *, limit: int = 200) -> dict[str, Any]:
    db_view = _db_contract_view(path, limit=limit)
    if db_view:
        return db_view
    payload = load_json(path) or {}
    outputs = payload.get("outputs") or {}
    scene_rows = outputs.get("resolved_scene_analyses") or outputs.get("scene_analyses") or []
    relationship_profiles = outputs.get("relationship_profiles") or RelationshipProfileBuilder().build(scene_analyses=scene_rows)
    sections = {
        "resolved_scene_analyses": scene_rows,
        "event_ledger": outputs.get("event_ledger") or [],
        "entity_registry": outputs.get("entity_registry") or [],
        "timeline": outputs.get("timeline") or [],
        "character_profiles": outputs.get("character_profiles") or [],
        "stable_character_states": outputs.get("stable_character_states") or [],
        "relationship_profiles": relationship_profiles,
        "scene_world_state": [
            {
                "scene_id": f"b{scene.get('book_index', '?')}_c{scene.get('chapter_index', '?')}_s{scene.get('scene_index', '?')}",
                "book_index": scene.get("book_index"),
                "chapter_index": scene.get("chapter_index"),
                "scene_index": scene.get("scene_index"),
                "scene_summary": scene.get("scene_summary") or "",
                "location": scene.get("location") or {},
                "visual_analysis": scene.get("visual_analysis") or {},
                "entity_world_state": scene.get("entity_world_state") or {},
                "state_changes": scene.get("state_changes") or [],
                "relationship_changes": scene.get("relationship_changes") or [],
                "text": scene.get("text") or "",
            }
            for scene in scene_rows
        ],
    }
    visual_prompt_sets = outputs.get("visual_prompt_sets") or {}
    visual_sections: dict[str, list[Any]] = {}
    if isinstance(visual_prompt_sets, dict):
        for key in ["initial_characters", "character_changes", "objects_creatures", "locations", "scene_compositions"]:
            visual_sections[key] = visual_prompt_sets.get(key) or []
    render_summary = _merge_character_sheet_renders(path, visual_sections)
    render_map = _render_map_for_contract(path)
    visual_inventory = _build_visual_inventory(
        entity_registry=sections["entity_registry"],
        visual_sections=visual_sections,
        render_map=render_map,
    )
    return {
        "path": rel(path),
        "summary": contract_summary(path, parse_heavy=True),
        "metadata": payload.get("metadata") or {},
        "outputs": {
            key: [reduce_contract_row(row) for row in values[:limit]]
            for key, values in sections.items()
        } | {
            "visual_prompt_sets": {
                key: [reduce_contract_row(row) for row in values[:limit]]
                for key, values in visual_sections.items()
            },
            "visual_inventory": [reduce_contract_row(row) for row in visual_inventory[: max(limit, 500)]],
            "visual_prompt_diagnostics": visual_prompt_sets.get("diagnostics") if isinstance(visual_prompt_sets, dict) else {},
        },
        "counts": {
            **{key: len(values) for key, values in sections.items()},
            **{f"visual_{key}": len(values) for key, values in visual_sections.items()},
            "visual_inventory": len(visual_inventory),
        },
        "render_summary": render_summary,
        "truncated_at": limit,
    }


class DashboardJobLogHandle:
    def __init__(self, job_id: str) -> None:
        self.job_id = str(job_id)

    def write(self, text: str) -> None:
        SQLITE_STORE.append_dashboard_job_log(self.job_id, text)

    def flush(self) -> None:
        return


def load_job(job_id: str) -> dict[str, Any]:
    payload = SQLITE_STORE.get_dashboard_job(job_id)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=404, detail="Job not found")
    return _normalize_job_payload(payload, persist=True)


def save_job(payload: dict[str, Any]) -> None:
    normalized = {**payload, "log_path": ""}
    SQLITE_STORE.upsert_dashboard_job(normalized)
    _sync_pipeline_run_from_job_payload(normalized)


def list_jobs() -> list[dict[str, Any]]:
    ensure_dirs()
    rows = []
    db_rows = _safe_db([], "get_dashboard_jobs", lambda: SQLITE_STORE.get_dashboard_jobs(limit=100))
    for data in db_rows:
        if isinstance(data, dict):
            rows.append(_normalize_job_payload(data, persist=True))
    return rows[:50]


def _sync_pipeline_run_from_job_payload(payload: dict[str, Any]) -> None:
    return


def _pid_is_running(pid: Any) -> bool:
    try:
        numeric = int(pid)
    except (TypeError, ValueError):
        return False
    if numeric <= 0:
        return False
    try:
        os.kill(numeric, 0)
        return True
    except OSError:
        return False
    except Exception:
        return False


def _status_update_age_seconds(status_payload: dict[str, Any] | None) -> float | None:
    if not isinstance(status_payload, dict):
        return None
    updated_at = str(status_payload.get("updated_at_utc") or "").strip()
    if not updated_at:
        return None
    try:
        updated_dt = datetime.fromisoformat(updated_at)
    except ValueError:
        return None
    return max(0.0, (datetime.now(timezone.utc) - updated_dt).total_seconds())


def _iso_age_seconds(value: Any) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds())


def _humanize_status_reason(code: str, *, fallback: str = "") -> str:
    value = str(code or "").strip()
    mapping = {
        "stale_encode_worker_process": "The encoder worker stopped unexpectedly and did not write a terminal status.",
        "stale_dashboard_job_process": "The dashboard wrapper process stopped after the underlying run had already ended.",
        "stale_dashboard_thread_no_heartbeat": "The dashboard job stopped reporting progress and is no longer considered active.",
        "blocked_rate_limit": "The run was blocked by provider rate limits before it could complete.",
    }
    return mapping.get(value, fallback or value)


def _is_stale_status_reason(value: str) -> bool:
    text = str(value or "").strip().lower()
    return text in {
        _humanize_status_reason("stale_encode_worker_process").lower(),
        _humanize_status_reason("stale_dashboard_job_process").lower(),
        _humanize_status_reason("stale_dashboard_thread_no_heartbeat").lower(),
    }


def _humanize_job_failure(payload: dict[str, Any]) -> str:
    error_text = str(payload.get("error") or "").strip()
    return_code = payload.get("return_code")
    if error_text:
        return _humanize_status_reason(error_text, fallback=error_text)
    if return_code not in (None, "", 0, "0"):
        return f"Subprocess failed with exit code {return_code}."
    return ""


def _job_to_run_summary(payload: dict[str, Any]) -> dict[str, Any]:
    request = payload.get("request") if isinstance(payload.get("request"), dict) else {}
    books = request.get("books") if isinstance(request.get("books"), list) else []
    progress = payload.get("progress") if isinstance(payload.get("progress"), dict) else {}
    details = progress.get("details") if isinstance(progress.get("details"), dict) else {}
    status = str(payload.get("status") or "unknown").strip().lower() or "unknown"
    status_reason = str(payload.get("status_reason") or "").strip()
    if (not status_reason or _is_stale_status_reason(status_reason)) and status in {"failed", "blocked_rate_limit"}:
        status_reason = _humanize_job_failure(payload)
    book_title = ""
    if books:
        book_title = re.sub(r"^\d{8}T\d{6}_", "", Path(str(books[0])).name)
    elif details.get("book_title"):
        book_title = str(details.get("book_title") or "")
    scene_count = int(details.get("total_scenes") or details.get("scenes_processed") or 0)
    return {
        "path": f"db://job/{payload.get('id')}",
        "series_id": str(request.get("series_id") or payload.get("id") or "job"),
        "run_id": str(payload.get("id") or ""),
        "mtime": 0,
        "status": status,
        "status_reason": status_reason,
        "status_source": "dashboard_job",
        "books": len(books) or 1,
        "contracts": 0,
        "failed_books": 1 if status in {"failed", "partial", "paused"} else 0,
        "total_scenes": scene_count,
        "book_rows": [
            {
                "path": f"db://job/{payload.get('id')}/book/1",
                "name": book_title or "Book",
                "run_status": status,
                "scenes": scene_count,
                "identity_provider": str(request.get("identity_provider") or "n/a"),
            }
        ],
        "status_payload_count": 0,
        "worker_pid": payload.get("pid"),
        "status_update_age_seconds": None,
        "progress": progress if progress else None,
        "log_tail": payload.get("log_tail") or [],
        "command": str(payload.get("command") or ""),
    }


def _normalize_job_payload(payload: dict[str, Any], *, persist: bool = False) -> dict[str, Any]:
    def _current_status() -> str:
        return str(payload.get("status") or "").strip().lower()

    pid = payload.get("pid")
    job_type = str(payload.get("type") or "").strip().lower()
    request = payload.get("request") if isinstance(payload.get("request"), dict) else {}
    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
    series_id = str(request.get("series_id") or "").strip()
    audiobook_run_id = str(
        request.get("run_id")
        or artifacts.get("audiobook_run_id")
        or ""
    ).strip()
    should_sync_pipeline_run = False
    latest_run = _safe_db(
        None,
        "get_latest_pipeline_run",
        lambda: SQLITE_STORE.get_latest_pipeline_run(series_id=series_id),
    ) if (series_id and should_sync_pipeline_run) else None
    latest_worker_pid = (latest_run or {}).get("worker_pid") if isinstance(latest_run, dict) else None
    latest_run_status = str((latest_run or {}).get("status") or "").strip().lower()
    latest_update_age = None
    if isinstance(latest_run, dict):
        try:
            latest_update_age = max(0.0, time.time() - float(latest_run.get("mtime") or 0.0))
        except Exception:
            latest_update_age = None
    audiobook_run = _safe_db(
        None,
        "get_audiobook_run",
        lambda: SQLITE_STORE.get_audiobook_run(audiobook_run_id),
    ) if (job_type == "audiobook-pipeline" and audiobook_run_id) else None
    audiobook_run = _augment_audiobook_run_from_outputs(audiobook_run) if isinstance(audiobook_run, dict) else audiobook_run
    audiobook_run_status = str((audiobook_run or {}).get("status") or "").strip().lower()
    if isinstance(audiobook_run, dict):
        run_progress = audiobook_run.get("progress") if isinstance(audiobook_run.get("progress"), dict) else {}
        if run_progress:
            payload["progress"] = run_progress
        if audiobook_run_status in {"staged", "queued", "running", "partial", "completed", "failed", "cancelled"}:
            payload["status"] = "running" if audiobook_run_status == "partial" else audiobook_run_status
        if audiobook_run.get("error"):
            payload["error"] = str(audiobook_run.get("error") or "")
        if payload.get("status") in {"completed", "failed", "cancelled"}:
            payload["finished_at"] = payload.get("finished_at") or str(audiobook_run.get("updated_at") or utc_now())
        else:
            payload.pop("finished_at", None)
            if payload.get("error") == "stale_dashboard_thread_no_heartbeat":
                payload.pop("error", None)
            if _is_stale_status_reason(str(payload.get("status_reason") or "")):
                payload.pop("status_reason", None)
        recovery_log_tail = _audiobook_recovery_log_tail(audiobook_run_id, limit=40)
        if recovery_log_tail:
            existing_tail = payload.get("log_tail") if isinstance(payload.get("log_tail"), list) else []
            payload["log_tail"] = [*existing_tail, *recovery_log_tail][-120:]
    if isinstance(latest_run, dict):
        if latest_run_status in {"running", "blocked_rate_limit", "failed", "completed"}:
            progress = latest_run.get("progress") if isinstance(latest_run.get("progress"), dict) else None
            if progress:
                progress.setdefault("details", {})
                progress["details"]["status_updated_at_utc"] = str(latest_run.get("finished_at") or latest_run.get("started_at") or "")
                progress["details"]["status_update_age_seconds"] = latest_update_age
                payload["progress"] = progress
            if _current_status() in {"queued", "running", "failed"} and latest_run_status == "running":
                payload["status"] = "running"
                payload.pop("error", None)
                payload.pop("status_reason", None)
            elif _current_status() == "running" and latest_run_status in {"failed", "completed", "blocked_rate_limit"}:
                payload["status"] = latest_run_status
                if latest_run_status == "blocked_rate_limit":
                    payload["status_reason"] = _humanize_status_reason("blocked_rate_limit")
    if (
        _current_status() == "running"
        and isinstance(latest_run, dict)
        and latest_run_status == "running"
        and latest_worker_pid not in (None, "", 0, "0")
        and not _pid_is_running(latest_worker_pid)
        and latest_update_age is not None
        and latest_update_age > 30
    ):
        payload["status"] = "failed"
        payload["error"] = payload.get("error") or "stale_encode_worker_process"
        payload["status_reason"] = _humanize_status_reason("stale_encode_worker_process")
        progress = payload.get("progress") or {}
        if isinstance(progress, dict):
            progress["status"] = "failed"
            progress["label"] = progress.get("label") or "encoder worker stopped unexpectedly"
            progress.setdefault("details", {})
            progress["details"]["stale_worker_pid"] = latest_worker_pid
            progress["details"]["status_update_age_seconds"] = latest_update_age
            payload["progress"] = progress
        if persist:
            save_job(payload)
    if _current_status() == "running" and pid in (None, "", 0, "0"):
        if job_type == "audiobook-pipeline" and audiobook_run_status == "running":
            return payload
        progress = payload.get("progress") if isinstance(payload.get("progress"), dict) else {}
        progress_age = _iso_age_seconds(progress.get("updated_at")) if isinstance(progress, dict) else None
        started_age = _iso_age_seconds(payload.get("started_at"))
        stale_age = progress_age if progress_age is not None else started_age
        if stale_age is not None and stale_age > 30 * 60:
            has_cancel_request = "cancel" in str(payload.get("status_reason") or "").lower() or "cancel" in str(payload.get("artifacts") or "").lower()
            payload["status"] = "cancelled" if has_cancel_request else "failed"
            payload["error"] = payload.get("error") or "stale_dashboard_thread_no_heartbeat"
            payload["status_reason"] = "Cancelled after the worker stopped responding." if has_cancel_request else _humanize_status_reason("stale_dashboard_thread_no_heartbeat")
            if isinstance(progress, dict):
                progress["status"] = payload["status"]
                progress["label"] = payload["status_reason"]
                progress.setdefault("details", {})
                progress["details"]["stale_heartbeat_age_seconds"] = stale_age
                payload["progress"] = progress
            payload["finished_at"] = payload.get("finished_at") or utc_now()
            if persist:
                save_job(payload)
    if _current_status() == "running" and pid not in (None, "", 0, "0") and not _pid_is_running(pid):
        if latest_run_status != "running":
            payload["status"] = "failed"
            payload["error"] = payload.get("error") or "stale_dashboard_job_process"
            payload["status_reason"] = _humanize_status_reason("stale_dashboard_job_process")
            progress = payload.get("progress") or {}
            if isinstance(progress, dict):
                progress["status"] = "failed"
                progress["label"] = progress.get("label") or "stale job cleaned up"
                progress.setdefault("details", {})
                progress["details"]["stale_pid"] = pid
                payload["progress"] = progress
            if persist:
                save_job(payload)
    if _current_status() in {"failed", "blocked_rate_limit"}:
        derived_reason = _humanize_job_failure(payload)
        if derived_reason and (not payload.get("status_reason") or _is_stale_status_reason(str(payload.get("status_reason") or ""))):
            payload["status_reason"] = derived_reason
            progress = payload.get("progress") or {}
            if isinstance(progress, dict):
                progress.setdefault("details", {})
                progress["details"]["status_reason"] = derived_reason
                if str(progress.get("status") or "").strip().lower() != "failed":
                    progress["status"] = "failed"
                payload["progress"] = progress
            if persist:
                save_job(payload)
    if not payload.get("status_reason") and payload.get("error"):
        payload["status_reason"] = _humanize_status_reason(str(payload.get("error") or ""))
    return payload


def _job_progress_payload(
    *,
    stage: str,
    current: int | None = None,
    total: int | None = None,
    label: str = "",
    status: str = "",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "stage": stage,
        "label": label,
        "status": status or stage,
        "details": details or {},
    }
    if current is not None:
        payload["current"] = int(current)
    if total is not None:
        payload["total"] = int(total)
    return payload


def update_job_progress(job_id: str, **progress: Any) -> None:
    payload = load_job(job_id)
    payload["progress"] = _job_progress_payload(**progress)
    save_job(payload)


def append_job_log(log_handle, text: str) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    raw = str(text or "")
    if not raw:
        return
    chunks = raw.splitlines(keepends=True)
    if not chunks:
        return
    for chunk in chunks:
        if not chunk.strip():
            log_handle.write(chunk)
            continue
        stripped = chunk.rstrip("\r\n")
        newline = chunk[len(stripped):]
        if re.match(r"^\d{4}-\d{2}-\d{2}", stripped):
            log_handle.write(chunk)
        else:
            log_handle.write(f"{timestamp} | {stripped}{newline}")
    log_handle.flush()


def _format_log_fields(fields: dict[str, Any]) -> str:
    ordered = []
    for key, value in fields.items():
        if value in (None, ""):
            continue
        text = str(value).replace("\n", "\\n")
        if any(ch.isspace() for ch in text) or "|" in text or "=" in text:
            text = json.dumps(text, ensure_ascii=False)
        ordered.append(f"{key}={text}")
    return " ".join(ordered)


def append_stage_log(log_handle, stage: str, message: str, **fields: Any) -> None:
    payload = {
        "level": "INFO",
        "stage": stage,
        "event": message,
        **fields,
    }
    append_job_log(log_handle, _format_log_fields(payload) + "\n")


def append_progress_log(log_handle, stage: str, payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        return
    fields = {
        "status": payload.get("status"),
        "scene_position": payload.get("scene_position"),
        "total_scenes": payload.get("total_scenes"),
        "book_index": payload.get("book_index"),
        "chapter_index": payload.get("chapter_index"),
        "scene_index": payload.get("scene_index"),
        "elapsed_seconds": payload.get("elapsed_seconds"),
        "analysis_model": payload.get("analysis_model"),
        "identity_model": payload.get("identity_model"),
        "provider_mode": payload.get("provider_mode"),
    }
    append_stage_log(log_handle, stage, "progress update", **fields)


def derive_encode_progress(status_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(status_payload, dict):
        return None
    books = status_payload.get("books") or []
    summary = status_payload.get("summary") or {}
    total_books = len(books) or int(summary.get("total_requested") or 0)
    active_book = next((row for row in books if str(row.get("status") or "").lower() == "running"), None)
    if active_book:
        scenes_processed = int(active_book.get("scenes_processed") or 0)
        total_scenes = int(active_book.get("total_scenes") or 0)
        phase = str(active_book.get("phase") or "running")
        phase_labels = {
            "chapters": "loading chapters",
            "identity": "loading BookNLP identity",
            "scene": "analyzing scenes",
            "scene_wait": "scene still running",
            "artifacts": "building downstream artifacts",
            "causal_graph": "building causal graph",
            "scene_failure_policy": "book failed policy checks",
        }
        progress_status = str((active_book.get("last_progress") or {}).get("status") or "").strip()
        label = f"{active_book.get('title') or 'Book'} ط¢- {phase_labels.get(phase, phase)}"
        if total_scenes > 0:
            label += f" ط¢- scene {scenes_processed}/{total_scenes}"
        if progress_status and phase == "scene_wait":
            label = f"{active_book.get('title') or 'Book'} ط¢- {progress_status}"
        details = {
            "book_title": active_book.get("title") or "",
            "book_phase": phase,
            "completed_books": int(summary.get("completed") or 0),
            "failed_books": int(summary.get("failed") or 0),
            "total_books": total_books,
            "checkpoint_path": active_book.get("checkpoint_path") or "",
            "book_elapsed_seconds": active_book.get("elapsed_seconds"),
            "elapsed_seconds": (active_book.get("last_progress") or {}).get("elapsed_seconds"),
            "analysis_model": (active_book.get("last_progress") or {}).get("analysis_model"),
            "identity_model": (active_book.get("last_progress") or {}).get("identity_model"),
        }
        return _job_progress_payload(
            stage="encode",
            current=scenes_processed,
            total=total_scenes if total_scenes > 0 else total_books,
            label=label,
            status=str(status_payload.get("status") or "running"),
            details=details,
        )
    completed_books = int(summary.get("completed") or 0) + int(summary.get("failed") or 0) + int(summary.get("skipped") or 0)
    label = f"books complete {completed_books}/{total_books}" if total_books else str(status_payload.get("status") or "running")
    return _job_progress_payload(
        stage="encode",
        current=completed_books if total_books else None,
        total=total_books if total_books else None,
        label=label,
        status=str(status_payload.get("status") or "running"),
        details={
            "completed_books": int(summary.get("completed") or 0),
            "failed_books": int(summary.get("failed") or 0),
            "skipped_books": int(summary.get("skipped") or 0),
            "total_books": total_books,
        },
    )


def poll_encode_status(job_id: str, series_id: str, stop_event: threading.Event, log_handle=None) -> None:
    last_progress_signature = ""
    last_status_signature = ""
    while not stop_event.is_set():
        try:
            latest_run = _safe_db(
                None,
                "get_latest_pipeline_run",
                lambda: SQLITE_STORE.get_latest_pipeline_run(series_id=series_id),
            )
            if isinstance(latest_run, dict):
                progress = latest_run.get("progress") if isinstance(latest_run.get("progress"), dict) else None
                status_signature = json.dumps(
                    {
                        "status": latest_run.get("status"),
                        "status_reason": latest_run.get("status_reason"),
                        "mtime": latest_run.get("mtime"),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )
                payload = load_job(job_id)
                if progress:
                    payload["progress"] = progress
                if status_signature != last_status_signature:
                    last_status_signature = status_signature
                    payload["status"] = str(latest_run.get("status") or payload.get("status") or "running")
                    if latest_run.get("status_reason"):
                        payload["status_reason"] = str(latest_run.get("status_reason") or "")
                    save_job(payload)
                if progress and log_handle is not None:
                    signature = json.dumps(progress, ensure_ascii=False, sort_keys=True, default=str)
                    if signature != last_progress_signature:
                        last_progress_signature = signature
                        append_progress_log(log_handle, str(progress.get("stage") or "encode"), progress)
        except Exception:
            pass
        stop_event.wait(1.0)


def build_character_render_command(request: CharacterRenderRequest) -> list[str]:
    command = [sys.executable, "-u", "saga_tools.py", "render-character-sheets", "--book-ref", request.contract_path]
    if request.limit and request.limit > 0:
        command.extend(["--limit", str(request.limit)])
    if request.overwrite:
        command.append("--overwrite")
    for entity_type in request.entity_types or []:
        if str(entity_type or "").strip():
            command.extend(["--entity-type", str(entity_type).strip()])
    for entity_id in request.entity_ids or []:
        if str(entity_id or "").strip():
            command.extend(["--entity-id", str(entity_id).strip()])
    for prompt_id in request.prompt_ids or []:
        if str(prompt_id or "").strip():
            command.extend(["--prompt-id", str(prompt_id).strip()])
    return command


def _series_book_refs(series_id: str) -> list[str]:
    rows = _safe_db([], "get_series_books", lambda: SQLITE_STORE.get_series_books(series_id))
    ordered = sorted(rows, key=lambda row: int(row.get("book_index") or 0))
    return [f"db://book/{row.get('book_id')}" for row in ordered if str(row.get("book_id") or "").strip()]


def _resolve_decoder_book_ref(*, series_id: str = "", book_ref: str = "") -> str:
    explicit = str(book_ref or "").strip()
    if explicit:
        return explicit
    series_value = str(series_id or "").strip()
    if not series_value:
        return ""
    refs = _series_book_refs(series_value)
    return refs[-1] if refs else ""


DECODER_PROVIDER_CHOICES: tuple[tuple[str, str], ...] = (
    ("ollama", "Ollama"),
    ("general_compute", "General Compute"),
    ("codex", "Codex"),
)

CHARACTER_PROMPT_PREFIX_LINES = [
    "Create a photorealistic studio character-sheet photograph.",
    "Use a three-view layout with a pure white seamless background.",
    "Show the same person three times side by side: front view full body, side profile full body, and back view full body.",
    "Keep the face, body, hairstyle, and proportions identical across all views.",
    "Place the subject in a T-pose with arms relaxed at the sides, legs straight, feet shoulder-width apart, and the full body visible head to toe with no cropping.",
]
CHARACTER_PROMPT_SUFFIX_LINES = [
    "Photorealistic, real human skin texture, visible pores, and natural skin tone variation.",
    "Subtle facial asymmetry, realistic anatomy and proportions, natural hair strand detail, and physically accurate fabric texture.",
    "Neutral studio lighting with soft diffuse even light, no dramatic contrast, and no rim light.",
    "Sharp focus across the entire image, no depth-of-field blur, no stylization, clean controlled studio documentation photo, RAW photo, shot on Canon EOS R5, 8k UHD.",
]
LOCATION_PREFIX_LINES = [
    "Empty environment reference plate focused entirely on the location itself.",
    "Neutral worldbuilding reference for a canon location, presented as observational production design documentation.",
]
LOCATION_SUFFIX_LINES = [
    "Observational documentary framing suitable for production design reference.",
    "The scene must read as a permanent, believable place with coherent architecture, stable layout, and realistic scale.",
    "Photorealistic rendering, naturalistic light, physically plausible textures, sharp focus, no stylization, and no painterly effects.",
]
CREATURE_PREFIX_LINES = [
    "Single-subject creature reference plate focused entirely on the creature.",
    "Neutral worldbuilding reference for a canon creature, presented as design documentation rather than narrative action.",
]
CREATURE_SUFFIX_LINES = [
    "Use a clear full-subject composition with readable silhouette, believable anatomy, grounded material detail, and stable proportions.",
    "Observational documentary framing suitable for a production design reference library.",
    "Photorealistic rendering, naturalistic light, physically plausible textures, sharp focus, no stylization, and no painterly effects.",
]
OBJECT_PREFIX_LINES = [
    "Single-subject prop reference plate with the object fully visible and clearly readable.",
    "Neutral worldbuilding reference for a canon object, presented as production design documentation.",
]
OBJECT_SUFFIX_LINES = [
    "Use a clean readable composition with the full object clearly visible, stable proportions, believable construction, and grounded material detail.",
    "Observational documentary framing suitable for production design reference.",
    "Photorealistic rendering, naturalistic light, physically plausible textures, sharp focus, no stylization, and no painterly effects.",
]


def _decoder_provider_status_rows(provider_name: str, *, refresh: bool = False) -> list[dict[str, Any]]:
    if refresh:
        return list((refresh_provider_statuses().get(provider_name) or {}).get("statuses") or [])
    return list(SQLITE_STORE.get_provider_statuses(provider_name) or [])


def _decoder_provider_available(provider_name: str, *, refresh: bool = False) -> bool:
    rows = _decoder_provider_status_rows(provider_name, refresh=refresh)
    for row in rows:
        if str(row.get("probe_status") or "").strip().lower() == "ok":
            return True
    return False


def _available_decoder_providers(*, refresh: bool = False) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for provider_name, label in DECODER_PROVIDER_CHOICES:
        if _decoder_provider_available(provider_name, refresh=refresh):
            rows.append({"value": provider_name, "label": label})
    return rows


def _auto_decoder_anchors(*, story_mode: str, book_ref: str, continuity_anchor: str = "", divergence_anchor: str = "") -> tuple[str, str]:
    continuity_value = str(continuity_anchor or "").strip()
    divergence_value = str(divergence_anchor or "").strip()
    if continuity_value and (story_mode != "alternate_universe" or divergence_value):
        return continuity_value, divergence_value

    book_row = _db_book_by_contract_path(book_ref) if str(book_ref or "").strip() else None
    book_title = str(getattr(book_row, "title", "") or "").strip()
    anchor_label = book_title or "the resolved canon anchor"

    if story_mode == "mid_canon" and not continuity_value:
        continuity_value = (
            f"Stay fully consistent with canon through {anchor_label} and insert the new material "
            "between established events without contradicting known outcomes."
        )
    if story_mode == "alternate_universe":
        if not continuity_value:
            continuity_value = f"Preserve canon continuity through {anchor_label} until the divergence point."
        if not divergence_value:
            divergence_value = f"Diverge from canon immediately after the resolved anchor in {anchor_label}."
    return continuity_value, divergence_value


def _decoder_series_options() -> list[dict[str, Any]]:
    with SQLITE_STORE.session_factory() as session:
        series_rows = session.execute(select(SqlSeries).order_by(SqlSeries.title.asc())).scalars().all()
        books = session.execute(select(SqlBook)).scalars().all()
    books_by_series: dict[str, list[SqlBook]] = {}
    for book in books:
        key = str(book.series_id or "").strip()
        if not key:
            continue
        books_by_series.setdefault(key, []).append(book)
    rows: list[dict[str, Any]] = []
    for row in series_rows:
        series_id = str(row.series_id or "").strip()
        if not series_id:
            continue
        ordered = sorted(books_by_series.get(series_id, []), key=lambda book: (int(book.book_index or 0), str(book.title or "").lower()))
        latest = ordered[-1] if ordered else None
        rows.append(
            {
                "series_id": series_id,
                "title": str(row.title or series_id),
                "book_count": len(ordered),
                "latest_book_ref": f"db://book/{latest.id}" if latest else "",
                "latest_book_title": str(latest.title or "") if latest else "",
            }
        )
    return rows


def _normalize_runtime_path(path: str) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    try:
        resolved = Path(raw).resolve()
    except OSError:
        return raw
    return str(resolved)


def _ensure_runtime_thumbnail(image_path: str, thumbnail_path: str = "") -> str:
    source = _normalize_runtime_path(image_path)
    if not source:
        return ""
    existing = _normalize_runtime_path(thumbnail_path)
    if existing and Path(existing).exists():
        return existing
    try:
        return _normalize_runtime_path(ensure_thumbnail(source))
    except Exception:
        return ""


def _slugify_asset_name(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())
    return cleaned.strip("-") or "asset"


def _asset_prompt_fingerprint(positive_prompt: str, negative_prompt: str) -> str:
    payload = f"{str(positive_prompt or '').strip()}\n---\n{str(negative_prompt or '').strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _asset_preview_dir(entity_id: str) -> Path:
    path = DASHBOARD_DIR / "asset_previews" / str(entity_id or "").strip()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _asset_preview_meta_path(image_path: Path) -> Path:
    return image_path.with_suffix(f"{image_path.suffix}.json")


def _resolve_project_file(path: str | Path) -> Path:
    raw = Path(str(path or "")).resolve()
    if not str(raw).lower().startswith(str(ROOT).lower()):
        raise HTTPException(status_code=400, detail="File path must stay inside the project.")
    return raw


def _safe_runtime_cleanup_path(path: str | Path) -> Path | None:
    raw_text = str(path or "").strip()
    if not raw_text:
        return None
    raw = Path(raw_text).resolve()
    allowed_roots = [ROOT.resolve(), OUTPUTS_DIR.resolve(), DASHBOARD_DIR.resolve()]
    if not any(str(raw).lower().startswith(str(base).lower()) for base in allowed_roots):
        return None
    return raw


def _remove_runtime_artifact(path: str | Path) -> None:
    target = _safe_runtime_cleanup_path(path)
    if target is None or not target.exists():
        return
    try:
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            target.unlink(missing_ok=True)
    except OSError:
        return


def _asset_render_row(entity_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    entity_key = str(entity_id or "").strip()
    if not entity_key:
        raise HTTPException(status_code=400, detail="entity_id is required.")
    with SQLITE_STORE.session_factory() as session:
        entity = session.get(SqlEntity, entity_key)
        if entity is None:
            raise HTTPException(status_code=404, detail="Entity not found.")
        book = session.get(SqlBook, entity.book_id)
    service = ComfyUICharacterSheetService()
    rows = service.collect_entity_visual_prompts_filtered(
        f"db://book/{entity.book_id}",
        entity_ids={entity.id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No visual prompt payload available for the selected entity.")
    return dict(rows[0]), {
        "entity_id": entity.id,
        "entity_name": str(entity.canonical_name or "").strip(),
        "entity_type": str(entity.entity_type or "").strip().lower(),
        "book_id": entity.book_id,
        "book_title": str(book.title or "") if book else "",
    }


def _replace_name_in_text(value: str | None, old_name: str, new_name: str) -> str | None:
    if value is None:
        return None
    return str(value).replace(old_name, new_name)


def _replace_name_in_payload(value: Any, old_name: str, new_name: str) -> Any:
    if isinstance(value, dict):
        return {key: _replace_name_in_payload(item, old_name, new_name) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_name_in_payload(item, old_name, new_name) for item in value]
    if isinstance(value, str):
        return value.replace(old_name, new_name)
    return value


def resolve_identity_output_root(request: EncodeRequest) -> Path:
    configured = str(request.identity_output_root or "").strip()
    if configured:
        return (ROOT / configured).resolve() if not Path(configured).is_absolute() else Path(configured)
    return OUTPUTS_DIR / "identity_series" / slugify(request.series_id)


def resolve_series_identity_output_path(request: EncodeRequest, identity_root: Path) -> Path:
    return identity_root / f"{slugify(request.series_id)}_series_pipeline_identity.json"


def cleanup_identity_bundle_files(identity_root: Path, log_handle=None) -> None:
    try:
        if identity_root.exists():
            shutil.rmtree(identity_root, ignore_errors=True)
            if log_handle is not None:
                append_stage_log(log_handle, "identity_bundle", "removed temporary identity bundle files", output_root=identity_root)
    except Exception as exc:
        if log_handle is not None:
            append_stage_log(log_handle, "identity_bundle", "failed to remove temporary identity bundle files", error=repr(exc), output_root=identity_root)


def cleanup_legacy_series_artifacts(series_id: str, log_handle=None) -> None:
    targets = [
        OUTPUTS_DIR / "pipeline_runtime" / str(series_id),
        OUTPUTS_DIR / "contract_exports" / str(series_id),
    ]
    for target in targets:
        try:
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
                if log_handle is not None:
                    append_stage_log(log_handle, "cleanup", "removed legacy series artifact directory", path=target)
        except Exception as exc:
            if log_handle is not None:
                append_stage_log(log_handle, "cleanup", "failed to remove legacy series artifact directory", path=target, error=repr(exc))


def generate_identity_bundles_for_request(job_id: str, request: EncodeRequest, log_handle) -> Path:
    books = normalize_books(request.books, request.book_index_base)
    if not books:
        raise HTTPException(status_code=400, detail="At least one book path is required.")
    identity_root = resolve_identity_output_root(request)
    identity_root.mkdir(parents=True, exist_ok=True)
    append_stage_log(log_handle, "identity_bundle", "starting identity bundle generation", output_root=identity_root)
    summaries: list[dict[str, Any]] = []
    total = (len(books) * 3) + 1
    step = 0
    for idx, book in enumerate(books, start=1):
        title = book.get("title") or Path(book["path"]).name
        step += 1
        update_job_progress(
            job_id,
            stage="identity_bundle",
            current=step,
            total=total,
            label=f"{title} ط¢- preparing identity bundle",
            status="running",
            details={
                "book_index": book.get("book_index"),
                "output_root": str(identity_root),
                "substage": "prepare_book",
                "book_title": title,
                "book_position": idx,
                "book_total": len(books),
            },
        )
        append_stage_log(log_handle, "identity_bundle", "generating book identity bundle", book_title=title, book_position=f"{idx}/{len(books)}")
        step += 1
        update_job_progress(
            job_id,
            stage="identity_bundle",
            current=step,
            total=total,
            label=f"{title} ط¢- running BookNLP and cleanup adapter",
            status="running",
            details={
                "book_index": book.get("book_index"),
                "output_root": str(identity_root),
                "substage": "generate_bundle",
                "book_title": title,
                "book_position": idx,
                "book_total": len(books),
            },
        )
        summary = generate_book_identity_bundle(
            book=book,
            book_index=int(book["book_index"]),
            output_root=identity_root,
            reuse_book1_seed=False,
        )
        summaries.append(summary)
        step += 1
        update_job_progress(
            job_id,
            stage="identity_bundle",
            current=step,
            total=total,
            label=f"{title} ط¢- bundle ready",
            status="running",
            details={
                "book_index": book.get("book_index"),
                "output_root": str(identity_root),
                "substage": "book_complete",
                "book_title": title,
                "book_position": idx,
                "book_total": len(books),
                "character_count": summary.get("character_count", 0),
                "alias_count": summary.get("alias_count", 0),
                "reference_entity_count": summary.get("reference_entity_count", 0),
            },
        )
        append_stage_log(
            log_handle,
            "identity_bundle",
            "book identity bundle ready",
            book_title=title,
            characters=summary.get("character_count", 0),
            aliases=summary.get("alias_count", 0),
            references=summary.get("reference_entity_count", 0),
            pipeline=summary.get("pipeline_identity_path"),
        )
    series_identity_path = resolve_series_identity_output_path(request, identity_root)
    step += 1
    append_stage_log(log_handle, "identity_bundle", "building series identity map", output_path=series_identity_path)
    update_job_progress(
        job_id,
        stage="identity_bundle",
        current=step,
        total=total,
        label="building series identity map",
        status="running",
        details={
            "substage": "series_merge",
            "output_root": str(identity_root),
            "book_total": len(books),
        },
    )
    payload = build_series_pipeline_identity(book_summaries=summaries, output_json=series_identity_path)
    payload["series_id"] = request.series_id
    payload.setdefault("provider", "booknlp_clean")
    SQLITE_STORE.persist_identity_bundle(
        series_id=request.series_id,
        source_path=f"db://identity-series/{request.series_id}",
        series_payload=payload,
        book_summaries=summaries,
    )
    update_job_progress(
        job_id,
        stage="identity_bundle",
        current=step,
        total=total,
        label="series identity ready",
        status="completed",
        details={
            "series_identity_json": f"db://identity-series/{request.series_id}",
            "character_count": len(payload.get("characters") or []),
            "book_count": len(summaries),
            "substage": "complete",
        },
    )
    append_stage_log(
        log_handle,
        "identity_bundle",
        "series identity ready",
        characters=len(payload.get("characters") or []),
        books=len(summaries),
        db_ref=f"db://identity-series/{request.series_id}",
    )
    return series_identity_path


def format_duration_seconds(seconds: float | int | None) -> str:
    if seconds is None:
        return "0s"
    total = max(0, int(round(float(seconds))))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def generate_identity_bundles_for_request_v2(job_id: str, request: EncodeRequest, log_handle) -> Path:
    books = normalize_books(request.books, request.book_index_base)
    if not books:
        raise HTTPException(status_code=400, detail="At least one book path is required.")
    identity_root = resolve_identity_output_root(request)
    identity_root.mkdir(parents=True, exist_ok=True)
    append_stage_log(log_handle, "identity_bundle", "starting identity bundle generation", output_root=identity_root)
    summaries: list[dict[str, Any]] = []
    total = (len(books) * 8) + 1
    stage_order = {
        "extract_chapters_start": 2,
        "extract_chapters_complete": 3,
        "write_booknlp_input_start": 4,
        "write_booknlp_input_complete": 4,
        "booknlp_process_start": 5,
        "booknlp_process_heartbeat": 5,
        "booknlp_process_complete": 6,
        "adapt_raw_identity_start": 6,
        "adapt_raw_identity_complete": 6,
        "cleanup_identity_start": 7,
        "cleanup_identity_complete": 7,
        "build_pipeline_identity_start": 8,
        "build_pipeline_identity_complete": 8,
        "reuse_existing_bundle": 8,
        "reuse_seed_bundle": 8,
    }
    stage_labels = {
        "extract_chapters_start": "extracting chapter text",
        "extract_chapters_complete": "chapter text ready",
        "write_booknlp_input_start": "writing BookNLP input",
        "write_booknlp_input_complete": "BookNLP input ready",
        "booknlp_process_start": "running BookNLP small",
        "booknlp_process_heartbeat": "BookNLP small running",
        "booknlp_process_complete": "BookNLP small complete",
        "adapt_raw_identity_start": "adapting raw BookNLP output",
        "adapt_raw_identity_complete": "raw identity adapted",
        "cleanup_identity_start": "cleaning identity bundle",
        "cleanup_identity_complete": "identity cleanup complete",
        "build_pipeline_identity_start": "building pipeline identity",
        "build_pipeline_identity_complete": "pipeline identity ready",
        "reuse_existing_bundle": "reusing existing identity bundle",
        "reuse_seed_bundle": "reusing seeded identity bundle",
    }
    step = 0
    for idx, book in enumerate(books, start=1):
        title = book.get("title") or Path(book["path"]).name
        step = ((idx - 1) * 8) + 1
        update_job_progress(
            job_id,
            stage="identity_bundle",
            current=step,
            total=total,
            label=f"{title} ط¢- preparing identity bundle",
            status="running",
            details={
                "book_index": book.get("book_index"),
                "output_root": str(identity_root),
                "substage": "prepare_book",
                "book_title": title,
                "book_position": idx,
                "book_total": len(books),
            },
        )
        append_stage_log(log_handle, "identity_bundle", "generating book identity bundle", book_title=title, book_position=f"{idx}/{len(books)}")

        def _bundle_progress_callback(bundle_stage: str, bundle_payload: dict[str, Any]) -> None:
            relative_step = stage_order.get(bundle_stage, 2)
            current_value = ((idx - 1) * 8) + relative_step
            elapsed = bundle_payload.get("elapsed_seconds")
            label = stage_labels.get(bundle_stage, bundle_stage.replace("_", " "))
            if bundle_stage == "booknlp_process_heartbeat" and elapsed is not None:
                label = f"{label} ({format_duration_seconds(elapsed)} elapsed)"
            update_job_progress(
                job_id,
                stage="identity_bundle",
                current=current_value,
                total=total,
                label=f"{title} ط¢- {label}",
                status="running",
                details={
                    "book_index": book.get("book_index"),
                    "output_root": str(identity_root),
                    "substage": bundle_stage,
                    "book_title": title,
                    "book_position": idx,
                    "book_total": len(books),
                    "elapsed_seconds": elapsed,
                    "character_count": bundle_payload.get("character_count"),
                    "alias_count": bundle_payload.get("alias_count"),
                    "reference_entity_count": bundle_payload.get("reference_entity_count"),
                },
            )
            append_stage_log(
                log_handle,
                "identity_bundle",
                "bundle substage",
                book_title=title,
                book_position=f"{idx}/{len(books)}",
                substage=bundle_stage,
                elapsed_seconds=elapsed,
            )

        summary = generate_book_identity_bundle(
            book=book,
            book_index=int(book["book_index"]),
            output_root=identity_root,
            reuse_book1_seed=False,
            progress_callback=_bundle_progress_callback,
        )
        summaries.append(summary)
        step = idx * 8
        update_job_progress(
            job_id,
            stage="identity_bundle",
            current=step,
            total=total,
            label=f"{title} ط¢- bundle ready",
            status="running",
            details={
                "book_index": book.get("book_index"),
                "output_root": str(identity_root),
                "substage": "book_complete",
                "book_title": title,
                "book_position": idx,
                "book_total": len(books),
                "character_count": summary.get("character_count", 0),
                "alias_count": summary.get("alias_count", 0),
                "reference_entity_count": summary.get("reference_entity_count", 0),
            },
        )
        append_stage_log(
            log_handle,
            "identity_bundle",
            "book identity bundle ready",
            book_title=title,
            characters=summary.get("character_count", 0),
            aliases=summary.get("alias_count", 0),
            references=summary.get("reference_entity_count", 0),
            pipeline=summary.get("pipeline_identity_path"),
        )
    step += 1
    series_identity_path = resolve_series_identity_output_path(request, identity_root)
    append_stage_log(log_handle, "identity_bundle", "building series identity map", output_path=series_identity_path)
    update_job_progress(
        job_id,
        stage="identity_bundle",
        current=step,
        total=total,
        label="building series identity map",
        status="running",
        details={
            "substage": "series_merge",
            "output_root": str(identity_root),
            "book_total": len(books),
        },
    )
    payload = build_series_pipeline_identity(book_summaries=summaries, output_json=series_identity_path)
    payload["series_id"] = request.series_id
    payload.setdefault("provider", "booknlp_clean")
    SQLITE_STORE.persist_identity_bundle(
        series_id=request.series_id,
        source_path=f"db://identity-series/{request.series_id}",
        series_payload=payload,
        book_summaries=summaries,
    )
    update_job_progress(
        job_id,
        stage="identity_bundle",
        current=step,
        total=total,
        label="series identity ready",
        status="completed",
        details={
            "series_identity_json": f"db://identity-series/{request.series_id}",
            "character_count": len(payload.get("characters") or []),
            "book_count": len(summaries),
            "substage": "complete",
        },
    )
    append_stage_log(
        log_handle,
        "identity_bundle",
        "series identity ready",
        characters=len(payload.get("characters") or []),
        books=len(summaries),
        db_ref=f"db://identity-series/{request.series_id}",
    )
    return series_identity_path


def run_subprocess_job(
    job_id: str,
    command: list[str],
    log_handle,
    *,
    progress_pattern: re.Pattern[str] | None = None,
    progress_transform=None,
    status_monitor=None,
) -> int:
    stop_event = threading.Event()
    monitor_thread = None
    started_at = time.perf_counter()
    try:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        payload = load_job(job_id)
        payload["pid"] = process.pid
        save_job(payload)
        append_stage_log(log_handle, "subprocess", "started", pid=process.pid, command=subprocess.list2cmdline(command))
        if callable(status_monitor):
            monitor_thread = threading.Thread(target=status_monitor, args=(stop_event,), daemon=True)
            monitor_thread.start()
        assert process.stdout is not None
        for line in process.stdout:
            append_job_log(log_handle, line)
            if progress_pattern:
                match = progress_pattern.search(line.strip())
                if match:
                    payload = load_job(job_id)
                    payload["progress"] = progress_transform(match, payload.get("progress") or {}) if callable(progress_transform) else {
                        "current": int(match.group("current")),
                        "total": int(match.group("total")),
                        "label": match.group("label"),
                        "status": match.group("status"),
                    }
                    save_job(payload)
        code = process.wait()
        append_stage_log(log_handle, "subprocess", "finished", exit_code=code, elapsed_seconds=round(time.perf_counter() - started_at, 2))
        return code
    finally:
        stop_event.set()
        if monitor_thread:
            monitor_thread.join(timeout=2.0)


def render_visuals_for_run(
    job_id: str,
    contract_paths: list[str],
    log_handle,
    *,
    overwrite: bool = True,
    limit_per_book: int = 0,
    entity_types: list[str] | None = None,
) -> None:
    total = len(contract_paths)
    progress_pattern = re.compile(r"RENDER_PROGRESS\|(?P<current>\d+)\|(?P<total>\d+)\|(?P<label>.*?)\|(?P<status>[a-z_]+)")
    for index, contract_path in enumerate(contract_paths, start=1):
        contract_name = Path(contract_path).name
        update_job_progress(
            job_id,
            stage="visual_render",
            current=index - 1,
            total=total,
            label=f"queueing {contract_name}",
            status="running",
            details={"contract_path": contract_path},
        )
        append_job_log(log_handle, f"\n# Visual render {index}/{total}: {contract_path}\n")
        command = build_character_render_command(
            CharacterRenderRequest(
                contract_path=contract_path,
                overwrite=overwrite,
                limit=limit_per_book,
                entity_types=list(entity_types or ["character"]),
            )
        )

        def _transform(match, existing):
            entity_name = str(match.group("label") or "").strip()
            render_status = str(match.group("status") or "").strip()
            return _job_progress_payload(
                stage="visual_render",
                current=int(match.group("current")),
                total=int(match.group("total")),
                label=f"{contract_name} ط¢- {entity_name} ط¢- {render_status.replace('_', ' ')}",
                status=render_status,
                details={
                    "contract_path": contract_path,
                    "contract_name": contract_name,
                    "contract_index": index,
                    "contract_total": total,
                    "current_entity": entity_name,
                    "render_status": render_status,
                    "render_current": int(match.group("current")),
                    "render_total": int(match.group("total")),
                },
            )

        code = run_subprocess_job(job_id, command, log_handle, progress_pattern=progress_pattern, progress_transform=_transform)
        if code != 0:
            raise RuntimeError(f"Character-sheet render failed for {contract_name} with exit code {code}.")
    update_job_progress(job_id, stage="visual_render", current=total, total=total, label="visual renders complete", status="completed")


def run_series_character_render_job(job_id: str, request: SeriesCharacterRenderRequest) -> None:
    payload = load_job(job_id)
    payload.update({"status": "running", "started_at": utc_now(), "pid": None})
    save_job(payload)
    log = DashboardJobLogHandle(job_id)
    append_stage_log(log, "visual_render", "series render job started", series_id=request.series_id)
    try:
        book_refs = _series_book_refs(request.series_id)
        if not book_refs:
            raise RuntimeError(f"No DB-backed books found for series_id={request.series_id}.")
        render_visuals_for_run(
            job_id,
            book_refs,
            log,
            overwrite=request.overwrite,
            limit_per_book=request.limit_per_book,
            entity_types=request.entity_types,
        )
        payload = load_job(job_id)
        payload.update(
            {
                "status": "completed",
                "return_code": 0,
                "finished_at": utc_now(),
                "artifacts": {"book_refs": book_refs, "series_id": request.series_id},
            }
        )
        save_job(payload)
        append_stage_log(log, "visual_render", "series render job completed", series_id=request.series_id, books=len(book_refs))
    except Exception as exc:
        append_stage_log(log, "visual_render", "series render job failed", error=repr(exc), series_id=request.series_id)
        append_job_log(log, traceback.format_exc() + "\n")
        payload = load_job(job_id)
        payload.update({"status": "failed", "return_code": -1, "finished_at": utc_now(), "error": repr(exc)})
        save_job(payload)


def run_selected_entity_render_job(
    job_id: str,
    entity_groups: list[dict[str, Any]],
    *,
    overwrite: bool = False,
    limit: int = 0,
    fallback_entity_types: list[str] | None = None,
) -> None:
    payload = load_job(job_id)
    payload.update({"status": "running", "started_at": utc_now(), "pid": None})
    save_job(payload)
    log = DashboardJobLogHandle(job_id)
    append_stage_log(log, "visual_render", "selected entity render batch started", groups=len(entity_groups))
    total = len(entity_groups)
    try:
        for index, group in enumerate(entity_groups, start=1):
            contract_path = str(group.get("book_ref") or "").strip()
            entity_ids = [str(item or "").strip() for item in group.get("entity_ids") or [] if str(item or "").strip()]
            entity_types = [str(item or "").strip() for item in group.get("entity_types") or [] if str(item or "").strip()]
            if not contract_path or not entity_ids:
                continue
            contract_name = Path(contract_path).name
            update_job_progress(
                job_id,
                stage="visual_render",
                current=index - 1,
                total=total,
                label=f"queueing {contract_name}",
                status="running",
                details={"contract_path": contract_path, "entity_ids": entity_ids},
            )
            append_job_log(log, f"\n# Selected entity render {index}/{total}: {contract_path} ({len(entity_ids)} entities)\n")
            service = ComfyUICharacterSheetService()
            manifest = service.render_from_contract(
                contract_path,
                overwrite=overwrite,
                limit=limit,
                entity_types=set(entity_types or list(fallback_entity_types or ["character", "creature", "object", "location"])),
                entity_ids=set(entity_ids),
            )
            rendered_rows = list((manifest.get("render_report") or {}).get("renders") or manifest.get("renders") or [])
            failed_rows = [row for row in rendered_rows if str(row.get("status") or "").strip().lower() == "failed"]
            summary = {
                "rendered": sum(1 for row in rendered_rows if str(row.get("status") or "").strip().lower() == "rendered"),
                "skipped_existing": sum(1 for row in rendered_rows if str(row.get("status") or "").strip().lower() == "skipped_existing"),
                "failed": len(failed_rows),
            }
            append_job_log(log, f"Rendered summary: {json.dumps(summary, ensure_ascii=False)}\n")
            update_job_progress(
                job_id,
                stage="visual_render",
                current=index,
                total=total,
                label=f"{contract_name} complete",
                status="running" if index < total else "completed",
                details={
                    "contract_path": contract_path,
                    "contract_name": contract_name,
                    "contract_index": index,
                    "contract_total": total,
                    "selected_entity_ids": entity_ids,
                    "summary": summary,
                },
            )
            if failed_rows:
                raise RuntimeError(f"Selected entity render failed for {contract_name}: {failed_rows[0].get('last_error') or failed_rows[0].get('status')}")

        update_job_progress(job_id, stage="visual_render", current=total, total=total, label="selected entity renders complete", status="completed")
        payload = load_job(job_id)
        payload.update(
            {
                "status": "completed",
                "return_code": 0,
                "finished_at": utc_now(),
                "artifacts": {
                    "groups": entity_groups,
                    "entity_ids": [entity_id for group in entity_groups for entity_id in (group.get("entity_ids") or [])],
                },
            }
        )
        save_job(payload)
        append_stage_log(log, "visual_render", "selected entity render batch completed", groups=len(entity_groups))
    except Exception as exc:
        append_stage_log(log, "visual_render", "selected entity render batch failed", error=repr(exc), groups=len(entity_groups))
        append_job_log(log, traceback.format_exc() + "\n")
        payload = load_job(job_id)
        payload.update({"status": "failed", "return_code": -1, "finished_at": utc_now(), "error": repr(exc)})
        save_job(payload)


def run_decoder_job(job_id: str, request: DecoderRequest) -> None:
    resolved_book_ref = _resolve_decoder_book_ref(series_id=request.series_id, book_ref=request.book_ref)
    request = request.model_copy(update={"book_ref": resolved_book_ref})
    payload = load_job(job_id)
    payload.update({"status": "running", "started_at": utc_now(), "pid": None})
    save_job(payload)
    log = DashboardJobLogHandle(job_id)
    append_stage_log(
        log,
        "decoder",
        "decoder job started",
        series_id=request.series_id,
        book_ref=request.book_ref,
        story_mode=request.story_mode,
        provider=request.provider,
        chapter_count=request.chapter_count,
    )
    total_chapters = max(1, int(request.chapter_count or 1))

    def _decoder_progress_callback(event: dict[str, Any]) -> None:
        if not isinstance(event, dict):
            return
        chapter_total = max(1, int(event.get("chapter_total") or total_chapters))
        chapter_current = max(0, min(int(event.get("chapter_current") or 0), chapter_total))
        scene_number = int(event.get("scene_number") or 0)
        total_scenes = int(event.get("total_scenes") or 0)
        label = str(event.get("label") or "decoder running").strip() or "decoder running"
        details = {
            "series_id": request.series_id,
            "book_ref": request.book_ref,
            "story_mode": request.story_mode,
            "provider": request.provider,
            "chapter_count": request.chapter_count,
            "primary_pov_character": request.primary_pov_character,
            "event": str(event.get("event") or "").strip(),
            "chapter_number": int(event.get("chapter_number") or 0),
            "scene_number": scene_number,
            "total_scenes": total_scenes,
        }
        update_job_progress(
            job_id,
            stage="decoder",
            current=chapter_current,
            total=chapter_total,
            label=label,
            status="running",
            details=details,
        )
        append_stage_log(
            log,
            "decoder",
            str(event.get("event") or "progress").strip() or "progress",
            chapter_number=int(event.get("chapter_number") or 0) or None,
            scene_number=scene_number or None,
            total_scenes=total_scenes or None,
            label=label,
        )
    try:
        update_job_progress(
            job_id,
            stage="decoder",
            current=0,
            total=total_chapters,
            label="building canon-aware story",
            status="running",
            details={
                "series_id": request.series_id,
                "book_ref": request.book_ref,
                "story_mode": request.story_mode,
                "provider": request.provider,
                "chapter_count": request.chapter_count,
                "primary_pov_character": request.primary_pov_character,
            },
        )
        service = DatabaseDecoderService(sqlite_store=SQLITE_STORE)
        result = service.generate_and_store(
            book_ref=request.book_ref,
            series_id=request.series_id,
            story_mode=request.story_mode,
            provider=request.provider,
            user_prompt=request.user_prompt,
            chapter_count=request.chapter_count,
            primary_pov_character=request.primary_pov_character,
            continuity_anchor=request.continuity_anchor,
            divergence_anchor=request.divergence_anchor,
            progress_callback=_decoder_progress_callback,
        )
        update_job_progress(
            job_id,
            stage="decoder",
            current=int(result.get("chapter_count") or request.chapter_count or 1),
            total=total_chapters,
            label=f"generated {result.get('title') or 'story'}",
            status="completed",
            details={
                "story_id": result.get("story_id"),
                "chapter_count": result.get("chapter_count"),
                "output_characters": result.get("output_characters"),
                "status": result.get("status"),
            },
        )
        payload = load_job(job_id)
        payload.update(
            {
                "status": "completed",
                "return_code": 0,
                "finished_at": utc_now(),
                "artifacts": {"story_id": result.get("story_id"), "book_ref": request.book_ref, "series_id": request.series_id},
            }
        )
        save_job(payload)
        append_stage_log(
            log,
            "decoder",
            "decoder job completed",
            story_id=result.get("story_id"),
            title=result.get("title"),
            chapter_count=result.get("chapter_count"),
            status=result.get("status"),
        )
    except Exception as exc:
        append_stage_log(log, "decoder", "decoder job failed", error=repr(exc))
        append_job_log(log, traceback.format_exc() + "\n")
        payload = load_job(job_id)
        payload.update({"status": "failed", "return_code": -1, "finished_at": utc_now(), "error": repr(exc)})
        save_job(payload)


def run_job(job_id: str, command: list[str]) -> None:
    payload = load_job(job_id)
    payload.update({"status": "running", "started_at": utc_now(), "pid": None})
    save_job(payload)
    log = DashboardJobLogHandle(job_id)
    append_stage_log(log, "runtime", "generic job started", job_id=job_id, command=subprocess.list2cmdline(command))
    log.write("$ " + subprocess.list2cmdline(command) + "\n\n")
    try:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        payload["pid"] = process.pid
        save_job(payload)
        assert process.stdout is not None
        progress_pattern = re.compile(r"RENDER_PROGRESS\|(?P<current>\d+)\|(?P<total>\d+)\|(?P<label>.*?)\|(?P<status>[a-z_]+)")
        for line in process.stdout:
            log.write(line)
            log.flush()
            match = progress_pattern.search(line.strip())
            if match:
                payload = load_job(job_id)
                payload["progress"] = {
                    "current": int(match.group("current")),
                    "total": int(match.group("total")),
                    "label": match.group("label"),
                    "status": match.group("status"),
                }
                save_job(payload)
        code = process.wait()
        payload = load_job(job_id)
        payload.update(
            {
                "status": "completed" if code == 0 else "failed",
                "return_code": code,
                "finished_at": utc_now(),
            }
        )
        save_job(payload)
    except Exception as exc:
        append_stage_log(log, "runtime", "generic job failed", error=repr(exc))
        log.write(traceback.format_exc() + "\n")
        payload = load_job(job_id)
        payload.update({"status": "failed", "return_code": -1, "finished_at": utc_now(), "error": repr(exc)})
        save_job(payload)


def run_audiobook_job(job_id: str, run_id: str) -> None:
    payload = load_job(job_id)
    payload.update({"status": "running", "started_at": utc_now(), "pid": None})
    save_job(payload)
    log = DashboardJobLogHandle(job_id)
    append_stage_log(log, "audiobook", "audiobook job started", job_id=job_id, run_id=run_id)

    run_payload = _safe_db(None, "get_audiobook_run", lambda: SQLITE_STORE.get_audiobook_run(run_id))
    if run_payload is None:
        append_stage_log(log, "audiobook", "run missing", run_id=run_id)
        payload = load_job(job_id)
        payload.update({"status": "failed", "return_code": -1, "finished_at": utc_now(), "error": "audiobook_run_missing"})
        save_job(payload)
        return

    tts_provider_name = active_provider_name_for_capability(SPEECH_CAPABILITY, store=SQLITE_STORE)
    tts_config = read_inference_provider_config(tts_provider_name, store=SQLITE_STORE, mask=False)
    run_metadata = run_payload.get("metadata") if isinstance(run_payload.get("metadata"), dict) else {}
    rewrite_provider = str(run_metadata.get("rewrite_provider") or "ollama").strip().lower() or "ollama"
    rewrite_fallback_mode = str(run_metadata.get("rewrite_fallback_mode") or "strict_rewrite").strip().lower() or "strict_rewrite"
    tts_pool = ModalTTSPoolManager(
        app_name=str(tts_config.get("app_name") or DEFAULT_TTS_MODAL_APP_NAME).strip() or DEFAULT_TTS_MODAL_APP_NAME,
        request_timeout_seconds=max(30, int(tts_config.get("request_timeout_seconds") or tts_config.get("timeout_seconds") or 300)),
    )
    rewrite_llm = LLMClient(mode=_audiobook_llm_mode(rewrite_provider), allow_cross_provider_fallback=False)
    service = AudiobookGenerationService(llm_client=rewrite_llm, tts_pool=tts_pool)
    total_chapters = len(run_payload.get("chapters") or [])
    completed = 0
    failed = 0
    existing_chapters = {
        str(chapter.get("chapter_id") or ""): chapter
        for chapter in (run_payload.get("chapters") or [])
        if str(chapter.get("chapter_id") or "").strip()
    }
    completed_chapter_ids: set[str] = set()
    failed_chapter_ids: set[str] = set()
    for chapter_id, chapter in existing_chapters.items():
        audio_status = str(chapter.get("audio_status") or "").strip().lower()
        transcript_status = str(chapter.get("transcript_status") or "").strip().lower()
        audio_path = Path(str(chapter.get("audio_path") or "")).resolve() if str(chapter.get("audio_path") or "").strip() else None
        audio_exists = bool(audio_path and audio_path.exists() and audio_path.is_file())
        if audio_status == "completed" and audio_exists:
            completed_chapter_ids.add(chapter_id)
        elif audio_status == "failed" or transcript_status == "failed":
            failed_chapter_ids.add(chapter_id)
    completed = len(completed_chapter_ids)
    failed = len(failed_chapter_ids)

    _safe_db(
        None,
        "update_audiobook_run",
        lambda: SQLITE_STORE.update_audiobook_run(
            run_id,
            {
                "job_id": job_id,
                "status": "running",
                "progress": _job_progress_payload(
                    stage="starting",
                    current=0,
                    total=total_chapters,
                    label="Starting audiobook pipeline",
                    status="running",
                    details={"run_id": run_id, "chapter_count": total_chapters},
                ),
            },
        ),
    )

    try:
        transcript_results: list[dict[str, Any]] = []

        for chapter_number, chapter in enumerate(run_payload.get("chapters") or [], start=1):
            fresh_job = load_job(job_id)
            if str(((fresh_job.get("artifacts") or {}).get("control_requested") or "")).lower() == "cancel":
                append_stage_log(log, "audiobook", "cancellation requested", chapter_number=chapter_number, total_chapters=total_chapters)
                _safe_db(
                    None,
                    "update_audiobook_run",
                    lambda: SQLITE_STORE.update_audiobook_run(
                        run_id,
                        {
                            "status": "cancelled",
                            "progress": _job_progress_payload(
                                stage="cancelled",
                                current=completed,
                                total=total_chapters,
                                label="Audiobook run cancelled",
                                status="cancelled",
                                details={"run_id": run_id, "chapter_count": total_chapters, "failed_chapters": failed},
                            ),
                            "failed_chapters": failed,
                            "completed_chapters": completed,
                        },
                    ),
                )
                fresh_job.update({"status": "cancelled", "finished_at": utc_now(), "status_reason": "Cancelled from dashboard."})
                save_job(fresh_job)
                return

            chapter_id = str(chapter.get("chapter_id") or "")
            chapter_title = str(chapter.get("chapter_title") or f"Chapter {chapter_number}").strip() or f"Chapter {chapter_number}"
            chapter_index = int(chapter.get("chapter_index") or chapter_number)
            book_index = int(chapter.get("book_index") or 0)
            existing_chapter = existing_chapters.get(chapter_id, {})
            stored_transcript_text = str(existing_chapter.get("transcript_text") or "").strip()
            transcript_already_completed = str(existing_chapter.get("transcript_status") or "").strip().lower() == "completed" and bool(stored_transcript_text)
            if transcript_already_completed:
                append_stage_log(
                    log,
                    "narration",
                    "reusing stored transcript",
                    chapter_number=chapter_number,
                    total_chapters=total_chapters,
                    book_index=book_index,
                    chapter_index=chapter_index,
                    chapter_title=chapter_title,
                    transcript_chars=len(stored_transcript_text),
                )
                transcript_results.append(
                    {
                        "chapter": {**chapter, **existing_chapter},
                        "chapter_id": chapter_id,
                        "chapter_number": chapter_number,
                        "chapter_title": chapter_title,
                        "chapter_index": chapter_index,
                        "book_index": book_index,
                        "transcript_text": stored_transcript_text,
                        "rewrite": {
                            "source_provider": existing_chapter.get("source_provider") or run_payload.get("source_provider") or rewrite_provider,
                            "source_model": existing_chapter.get("source_model") or run_payload.get("source_model") or "",
                            "metadata": existing_chapter.get("metadata") if isinstance(existing_chapter.get("metadata"), dict) else {},
                        },
                    }
                )
                continue
            update_job_progress(
                job_id,
                stage="transcript",
                current=completed + failed,
                total=total_chapters,
                label=f"Rewriting {chapter_title}",
                status="running",
                details={
                    "run_id": run_id,
                    "chapter_count": total_chapters,
                    "phase": "transcript",
                    "chapter_number": chapter_number,
                    "book_index": book_index,
                    "chapter_index": chapter_index,
                    "chapter_title": chapter_title,
                },
            )
            append_stage_log(
                log,
                "narration",
                "chapter started",
                chapter_number=chapter_number,
                total_chapters=total_chapters,
                book_index=book_index,
                chapter_index=chapter_index,
                chapter_title=chapter_title,
            )

            with SQLITE_STORE.session_factory() as session:
                chapter_row = session.get(SqlChapter, chapter_id)
                source_text = _resolve_chapter_source_text(chapter_row, session=session)
                if not source_text:
                    raise RuntimeError(f"Chapter source text is missing for chapter_id={chapter_id}.")

            try:
                try:
                    rewrite = service.rewrite_chapter_text(
                        chapter_title=chapter_title,
                        chapter_text=source_text,
                        tone=str((run_payload.get("metadata") or {}).get("tone") or "classic"),
                        fallback_mode=rewrite_fallback_mode,
                    )
                except Exception as exc:
                    if rewrite_fallback_mode == "fallback_to_source":
                        append_stage_log(log, "narration", "rewrite failed; falling back to source text", chapter_id=chapter_id, error=repr(exc))
                        rewrite = {
                            "transcript_text": source_text,
                            "source_provider": rewrite_provider,
                            "source_model": "fallback_source_text",
                            "metadata": {"rewrite_mode": "source_passthrough_error", "rewrite_error": repr(exc), "fallback_mode": rewrite_fallback_mode},
                        }
                    else:
                        raise

                transcript_text = str(rewrite.get("transcript_text") or "").strip() or source_text
                transcript_to_store = transcript_text if str(run_payload.get("transcript_storage_mode") or "").lower() != "disabled" else ""
                _safe_db(
                    None,
                    "upsert_audiobook_chapter",
                    lambda payload={
                        "run_id": run_id,
                        "series_id": run_payload.get("series_id") or "",
                        "book_id": chapter.get("book_id") or "",
                        "chapter_id": chapter_id,
                        "book_index": book_index,
                        "chapter_index": chapter_index,
                        "chapter_title": chapter_title,
                        "transcript_status": "completed",
                        "transcript_text": transcript_to_store,
                        "transcript_word_count": len(transcript_text.split()),
                        "source_provider": rewrite.get("source_provider") or run_payload.get("source_provider") or "ollama",
                        "source_model": rewrite.get("source_model") or "",
                        "metadata": {
                            **(chapter.get("metadata") if isinstance(chapter.get("metadata"), dict) else {}),
                            **(rewrite.get("metadata") if isinstance(rewrite.get("metadata"), dict) else {}),
                        },
                    }: SQLITE_STORE.upsert_audiobook_chapter(payload),
                )
                transcript_results.append(
                    {
                        "chapter": chapter,
                        "chapter_id": chapter_id,
                        "chapter_number": chapter_number,
                        "chapter_title": chapter_title,
                        "chapter_index": chapter_index,
                        "book_index": book_index,
                        "transcript_text": transcript_text,
                        "rewrite": rewrite,
                    }
                )
                if str(run_payload.get("audio_storage_mode") or "").lower() == "disabled":
                    completed_chapter_ids.add(chapter_id)
                completed = len(completed_chapter_ids)
                failed = len(failed_chapter_ids)
                run_progress = _job_progress_payload(
                    stage="transcript_completed",
                    current=completed + failed,
                    total=total_chapters,
                    label=f"Prepared transcript for {chapter_title}",
                    status="running",
                    details={
                        "run_id": run_id,
                        "chapter_count": total_chapters,
                        "phase": "transcript",
                        "chapter_number": chapter_number,
                        "book_index": book_index,
                        "chapter_index": chapter_index,
                        "chapter_title": chapter_title,
                        "failed_chapters": failed,
                    },
                )
                _safe_db(
                    None,
                    "update_audiobook_run",
                    lambda: SQLITE_STORE.update_audiobook_run(
                        run_id,
                        {
                            "status": "running",
                            "job_id": job_id,
                            "progress": run_progress,
                            "completed_chapters": completed,
                            "failed_chapters": failed,
                            "source_provider": rewrite.get("source_provider") or run_payload.get("source_provider") or "ollama",
                            "source_model": rewrite.get("source_model") or run_payload.get("source_model") or "",
                            "tts_provider": tts_provider_name,
                            "tts_app_name": str(tts_config.get("app_name") or ""),
                        },
                    ),
                )
                update_job_progress(
                    job_id,
                    stage="transcript_completed",
                    current=completed + failed,
                    total=total_chapters,
                    label=f"Prepared transcript for {chapter_title}",
                    status="running",
                    details={
                        "run_id": run_id,
                        "chapter_count": total_chapters,
                        "phase": "transcript",
                        "chapter_number": chapter_number,
                        "book_index": book_index,
                        "chapter_index": chapter_index,
                        "chapter_title": chapter_title,
                        "failed_chapters": failed,
                    },
                )
            except Exception as exc:
                failed_chapter_ids.add(chapter_id)
                completed = len(completed_chapter_ids)
                failed = len(failed_chapter_ids)
                append_stage_log(log, "audiobook", "chapter failed", chapter_number=chapter_number, chapter_title=chapter_title, error=repr(exc))
                append_job_log(log, traceback.format_exc() + "\n")
                _safe_db(
                    None,
                    "upsert_audiobook_chapter",
                    lambda payload={
                        "run_id": run_id,
                        "series_id": run_payload.get("series_id") or "",
                        "book_id": chapter.get("book_id") or "",
                        "chapter_id": chapter_id,
                        "book_index": book_index,
                        "chapter_index": chapter_index,
                        "chapter_title": chapter_title,
                        "transcript_status": "failed",
                        "audio_status": "failed" if str(run_payload.get("audio_storage_mode") or "").lower() != "disabled" else "skipped",
                        "error": repr(exc),
                    }: SQLITE_STORE.upsert_audiobook_chapter(payload),
                )
                run_progress = _job_progress_payload(
                    stage="transcript_failed",
                    current=completed + failed,
                    total=total_chapters,
                    label=f"Transcript failed for {chapter_title}",
                    status="running",
                    details={
                        "run_id": run_id,
                        "chapter_count": total_chapters,
                        "phase": "transcript",
                        "chapter_number": chapter_number,
                        "book_index": book_index,
                        "chapter_index": chapter_index,
                        "chapter_title": chapter_title,
                        "failed_chapters": failed,
                    },
                )
                _safe_db(
                    None,
                    "update_audiobook_run",
                    lambda: SQLITE_STORE.update_audiobook_run(
                        run_id,
                        {
                            "status": "running",
                            "job_id": job_id,
                            "progress": run_progress,
                            "completed_chapters": completed,
                            "failed_chapters": failed,
                            "error": repr(exc),
                        },
                    ),
                )
                update_job_progress(
                    job_id,
                    stage="transcript_failed",
                    current=completed + failed,
                    total=total_chapters,
                    label=f"Transcript failed for {chapter_title}",
                    status="running",
                    details={
                        "run_id": run_id,
                        "chapter_count": total_chapters,
                        "phase": "transcript",
                        "chapter_number": chapter_number,
                        "book_index": book_index,
                        "chapter_index": chapter_index,
                        "chapter_title": chapter_title,
                        "failed_chapters": failed,
                    },
                )
                continue

        if str(run_payload.get("audio_storage_mode") or "").lower() != "disabled" and transcript_results:
            live = service.tts_pool.ensure_live()
            append_stage_log(
                log,
                "audiobook",
                "tts app ready",
                token_name=live.get("token_name"),
                api_url=live.get("api_url"),
                app_name=tts_config.get("app_name") or "",
                rewrite_provider=rewrite_provider,
                rewrite_fallback_mode=rewrite_fallback_mode,
            )

            for transcript_result in transcript_results:
                chapter = transcript_result["chapter"]
                chapter_id = str(transcript_result["chapter_id"])
                chapter_number = int(transcript_result["chapter_number"])
                chapter_title = str(transcript_result["chapter_title"])
                chapter_index = int(transcript_result["chapter_index"])
                book_index = int(transcript_result["book_index"])
                transcript_text = str(transcript_result["transcript_text"])
                rewrite = transcript_result["rewrite"] if isinstance(transcript_result.get("rewrite"), dict) else {}
                existing_chapter = existing_chapters.get(chapter_id, {})
                existing_audio_path_raw = str(existing_chapter.get("audio_path") or chapter.get("audio_path") or "").strip()
                existing_audio_path = Path(existing_audio_path_raw).resolve() if existing_audio_path_raw else None
                existing_audio_status = str(existing_chapter.get("audio_status") or "").strip().lower()
                if existing_audio_status == "completed" and existing_audio_path and existing_audio_path.exists() and existing_audio_path.is_file():
                    append_stage_log(
                        log,
                        "tts",
                        "reusing existing audio output",
                        chapter_number=chapter_number,
                        total_chapters=total_chapters,
                        chapter_title=chapter_title,
                        audio_path=str(existing_audio_path),
                        audio_bytes=existing_audio_path.stat().st_size,
                    )
                    completed_chapter_ids.add(chapter_id)
                    failed_chapter_ids.discard(chapter_id)
                    completed = len(completed_chapter_ids)
                    failed = len(failed_chapter_ids)
                    update_job_progress(
                        job_id,
                        stage="chapter_completed",
                        current=completed,
                        total=total_chapters,
                        label=f"Completed {chapter_title}",
                        status="running",
                        details={
                            "run_id": run_id,
                            "chapter_count": total_chapters,
                            "phase": "tts",
                            "chapter_number": chapter_number,
                            "book_index": book_index,
                            "chapter_index": chapter_index,
                            "chapter_title": chapter_title,
                            "failed_chapters": failed,
                            "resumed": True,
                        },
                    )
                    continue

                update_job_progress(
                    job_id,
                    stage="tts",
                    current=completed,
                    total=total_chapters,
                    label=f"Synthesizing {chapter_title}",
                    status="running",
                    details={
                        "run_id": run_id,
                        "chapter_count": total_chapters,
                        "phase": "tts",
                        "chapter_number": chapter_number,
                        "book_index": book_index,
                        "chapter_index": chapter_index,
                        "chapter_title": chapter_title,
                        "transcripts_ready": len(transcript_results),
                    },
                )
                try:
                    def log_tts_event(event_name: str, **fields: Any) -> None:
                        append_stage_log(
                            log,
                            "tts",
                            event_name,
                            chapter_number=chapter_number,
                            total_chapters=total_chapters,
                            book_index=book_index,
                            chapter_index=chapter_index,
                            chapter_title=chapter_title,
                            **fields,
                        )

                    audio_result = service.synthesize_audio(
                        transcript_text=transcript_text,
                        voice=str(run_payload.get("voice") or tts_config.get("default_voice") or "af_bella"),
                        lang_code=str(run_payload.get("lang_code") or tts_config.get("default_lang_code") or "a"),
                        sample_rate=int(run_payload.get("sample_rate") or tts_config.get("default_sample_rate") or 24000),
                        audio_format=str(run_payload.get("audio_format") or tts_config.get("default_audio_format") or "wav"),
                        normalize_audio=bool(run_payload.get("normalize_audio") if run_payload.get("normalize_audio") is not None else tts_config.get("default_normalize_audio", True)),
                        trim_silence=bool(run_payload.get("trim_silence") if run_payload.get("trim_silence") is not None else tts_config.get("default_trim_silence", False)),
                        sentence_pause_ms=int(run_payload.get("sentence_pause_ms") or tts_config.get("default_sentence_pause_ms") or 0),
                        progress_logger=log_tts_event,
                    )
                    audio_path = Path(str(chapter.get("audio_path") or "")).resolve()
                    audio_path.parent.mkdir(parents=True, exist_ok=True)
                    audio_bytes = audio_result.get("audio_bytes") or b""
                    audio_path.write_bytes(audio_bytes)
                    _safe_db(
                        None,
                        "upsert_audiobook_chapter",
                        lambda payload={
                            "run_id": run_id,
                            "series_id": run_payload.get("series_id") or "",
                            "book_id": chapter.get("book_id") or "",
                            "chapter_id": chapter_id,
                            "book_index": book_index,
                            "chapter_index": chapter_index,
                            "chapter_title": chapter_title,
                            "audio_status": "completed",
                            "audio_path": str(audio_path),
                            "audio_mime_type": audio_result.get("media_type") or ("audio/flac" if audio_path.suffix.lower() == ".flac" else "audio/wav"),
                            "audio_byte_size": len(audio_bytes),
                            "duration_seconds": float(audio_result.get("duration_seconds") or 0.0),
                            "tts_provider": tts_provider_name,
                            "tts_app_name": str(tts_config.get("app_name") or ""),
                            "provider_account_alias": str(audio_result.get("token_name") or ""),
                            "voice": audio_result.get("voice") or run_payload.get("voice") or "",
                            "lang_code": audio_result.get("lang_code") or run_payload.get("lang_code") or "",
                            "sample_rate": int(audio_result.get("sample_rate") or run_payload.get("sample_rate") or 24000),
                            "audio_format": audio_result.get("audio_format") or run_payload.get("audio_format") or "wav",
                        }: SQLITE_STORE.upsert_audiobook_chapter(payload),
                    )
                    append_stage_log(
                        log,
                        "tts",
                        "chapter audio completed",
                        chapter_number=chapter_number,
                        total_chapters=total_chapters,
                        chapter_title=chapter_title,
                        audio_path=str(audio_path),
                        duration_seconds=audio_result.get("duration_seconds"),
                        token_name=audio_result.get("token_name"),
                    )
                    completed_chapter_ids.add(chapter_id)
                    completed = len(completed_chapter_ids)
                    failed = len(failed_chapter_ids)
                    run_progress = _job_progress_payload(
                        stage="chapter_completed",
                        current=completed,
                        total=total_chapters,
                        label=f"Completed {chapter_title}",
                        status="running",
                        details={
                            "run_id": run_id,
                            "chapter_count": total_chapters,
                            "phase": "tts",
                            "chapter_number": chapter_number,
                            "book_index": book_index,
                            "chapter_index": chapter_index,
                            "chapter_title": chapter_title,
                            "failed_chapters": failed,
                        },
                    )
                    _safe_db(
                        None,
                        "update_audiobook_run",
                        lambda: SQLITE_STORE.update_audiobook_run(
                            run_id,
                            {
                                "status": "running",
                                "job_id": job_id,
                                "progress": run_progress,
                                "completed_chapters": completed,
                                "failed_chapters": failed,
                                "source_provider": rewrite.get("source_provider") or run_payload.get("source_provider") or "ollama",
                                "source_model": rewrite.get("source_model") or run_payload.get("source_model") or "",
                                "tts_provider": tts_provider_name,
                                "tts_app_name": str(tts_config.get("app_name") or ""),
                            },
                        ),
                    )
                    update_job_progress(
                        job_id,
                        stage="chapter_completed",
                        current=completed,
                        total=total_chapters,
                        label=f"Completed {chapter_title}",
                        status="running",
                        details={
                            "run_id": run_id,
                            "chapter_count": total_chapters,
                            "phase": "tts",
                            "chapter_number": chapter_number,
                            "book_index": book_index,
                            "chapter_index": chapter_index,
                            "chapter_title": chapter_title,
                            "failed_chapters": failed,
                        },
                    )
                except Exception as exc:
                    failed_chapter_ids.add(chapter_id)
                    completed_chapter_ids.discard(chapter_id)
                    completed = len(completed_chapter_ids)
                    failed = len(failed_chapter_ids)
                    append_stage_log(log, "audiobook", "chapter failed", chapter_number=chapter_number, chapter_title=chapter_title, error=repr(exc))
                    append_job_log(log, traceback.format_exc() + "\n")
                    _safe_db(
                        None,
                        "upsert_audiobook_chapter",
                        lambda payload={
                            "run_id": run_id,
                            "series_id": run_payload.get("series_id") or "",
                            "book_id": chapter.get("book_id") or "",
                            "chapter_id": chapter_id,
                            "book_index": book_index,
                            "chapter_index": chapter_index,
                            "chapter_title": chapter_title,
                            "audio_status": "failed",
                            "error": repr(exc),
                        }: SQLITE_STORE.upsert_audiobook_chapter(payload),
                    )
                    run_progress = _job_progress_payload(
                        stage="chapter_failed",
                        current=completed,
                        total=total_chapters,
                        label=f"Audio failed for {chapter_title}",
                        status="running",
                        details={
                            "run_id": run_id,
                            "chapter_count": total_chapters,
                            "phase": "tts",
                            "chapter_number": chapter_number,
                            "book_index": book_index,
                            "chapter_index": chapter_index,
                            "chapter_title": chapter_title,
                            "failed_chapters": failed,
                        },
                    )
                    _safe_db(
                        None,
                        "update_audiobook_run",
                        lambda: SQLITE_STORE.update_audiobook_run(
                            run_id,
                            {
                                "status": "running",
                                "job_id": job_id,
                                "progress": run_progress,
                                "completed_chapters": completed,
                                "failed_chapters": failed,
                                "error": repr(exc),
                            },
                        ),
                    )
                    update_job_progress(
                        job_id,
                        stage="chapter_failed",
                        current=completed,
                        total=total_chapters,
                        label=f"Audio failed for {chapter_title}",
                        status="running",
                        details={
                            "run_id": run_id,
                            "chapter_count": total_chapters,
                            "phase": "tts",
                            "chapter_number": chapter_number,
                            "book_index": book_index,
                            "chapter_index": chapter_index,
                            "chapter_title": chapter_title,
                            "failed_chapters": failed,
                        },
                    )
                    continue

        completed = len(completed_chapter_ids)
        failed = len(failed_chapter_ids)

        final_status = "completed" if failed == 0 else ("partial" if completed > 0 else "failed")
        final_progress = _job_progress_payload(
            stage="complete" if final_status == "completed" else final_status,
            current=completed,
            total=total_chapters,
            label="Audiobook pipeline completed" if final_status == "completed" else "Audiobook pipeline completed with failures",
            status="completed" if final_status == "completed" else final_status,
            details={"run_id": run_id, "chapter_count": total_chapters, "failed_chapters": failed},
        )
        _safe_db(
            None,
            "update_audiobook_run",
            lambda: SQLITE_STORE.update_audiobook_run(
                run_id,
                {
                    "status": final_status,
                    "job_id": job_id,
                    "progress": final_progress,
                    "completed_chapters": completed,
                    "failed_chapters": failed,
                },
            ),
        )
        payload = load_job(job_id)
        payload.update(
            {
                "status": "completed" if final_status == "completed" else "failed",
                "return_code": 0 if final_status == "completed" else 2,
                "finished_at": utc_now(),
                "status_reason": "Audiobook pipeline finished." if final_status == "completed" else "Audiobook pipeline finished with chapter failures.",
                "progress": final_progress,
            }
        )
        save_job(payload)
        append_stage_log(log, "audiobook", "audiobook job finished", run_id=run_id, completed_chapters=completed, failed_chapters=failed, final_status=final_status)
    except Exception as exc:
        failed += 1
        append_stage_log(log, "audiobook", "audiobook job failed", run_id=run_id, error=repr(exc))
        append_job_log(log, traceback.format_exc() + "\n")
        final_progress = _job_progress_payload(
            stage="failed",
            current=completed,
            total=total_chapters,
            label=f"Audiobook pipeline failed: {type(exc).__name__}",
            status="failed",
            details={"run_id": run_id, "chapter_count": total_chapters, "failed_chapters": failed},
        )
        _safe_db(
            None,
            "update_audiobook_run",
            lambda: SQLITE_STORE.update_audiobook_run(
                run_id,
                {
                    "status": "failed" if completed == 0 else "partial",
                    "job_id": job_id,
                    "progress": final_progress,
                    "completed_chapters": completed,
                    "failed_chapters": failed,
                    "error": repr(exc),
                },
            ),
        )
        payload = load_job(job_id)
        payload.update({"status": "failed", "return_code": -1, "finished_at": utc_now(), "error": repr(exc), "progress": final_progress})
        save_job(payload)


app = FastAPI(title="S.A.G.A. Local Web Runtime")


@app.on_event("startup")
def on_startup() -> None:
    ensure_dirs()
    _seed_provider_configs_from_local_files()


@app.get("/runtime/state")
def runtime_state() -> dict[str, Any]:
    provider_statuses = {
        "ollama": SQLITE_STORE.get_provider_statuses("ollama"),
        "general_compute": SQLITE_STORE.get_provider_statuses("general_compute"),
        "codex": SQLITE_STORE.get_provider_statuses("codex"),
        MODAL_POOL_PROVIDER: SQLITE_STORE.get_provider_statuses(MODAL_POOL_PROVIDER),
        MODAL_KOKORO_PROVIDER: [],
        MODAL_COMFYUI_PROVIDER: [],
        MODAL_XCORE_PROVIDER: [],
        "tts_modal": SQLITE_STORE.get_provider_statuses(MODAL_POOL_PROVIDER),
    }
    uploads = _safe_db([], "get_uploaded_sources", lambda: SQLITE_STORE.get_uploaded_sources(limit=100))
    return {
        "workspace": {"root": str(ROOT), "outputs": rel(OUTPUTS_DIR), "uploads": rel(UPLOADS_DIR), "database_url": get_database_url()},
        "defaults": {
            "books": DEFAULT_BOOKS,
            "series_identity_json": r"db://identity-series/acotar-full-booknlp-clean-live",
            "models": [
                {"value": "gpt_oss", "label": "gpt_oss (Ollama)"},
                {"value": "general_compute", "label": "deepseek_v3 (GC)"},
                {"value": "codex", "label": "codex"},
                {"value": "mistral", "label": "mistral"},
                {"value": "gemini", "label": "gemini"},
            ],
            "story_modes": ["pre_canon", "mid_canon", "post_canon", "alternate_universe"],
            "provider_modes": ["single_provider", "same_provider_rotating", "cross_provider_fallback"],
            "quality_presets": ["fast_debug", "balanced", "high_quality", "max_quality"],
            "visual_strictness_modes": ["relaxed", "strict", "very_strict"],
        },
        "artifacts": scan_artifacts(),
        "jobs": list_jobs(),
        "providers": {
            "ollama": read_ollama_accounts(mask=True),
            "general_compute": read_general_compute_accounts(mask=True),
            "codex": read_codex_accounts(mask=True),
        },
        "provider_statuses": provider_statuses,
        "uploads": uploads,
        "prompts": read_prompts(),
        "loaded_at": utc_now(),
    }


@app.get("/runtime/artifact")
def runtime_artifact(path: str) -> dict[str, Any]:
    target = (ROOT / path).resolve()
    if not str(target).lower().startswith(str(ROOT).lower()):
        raise HTTPException(status_code=400, detail="Artifact path must stay inside the project.")
    if not target.exists():
        raise HTTPException(status_code=404, detail="Artifact not found.")
    if target.suffix.lower() == ".json":
        return {"path": rel(target), "type": "json", "content": load_json(target)}
    return {"path": rel(target), "type": "text", "content": target.read_text(encoding="utf-8", errors="replace")}


@app.get("/runtime/contract-view")
def runtime_contract_view(path: str, limit: int = 200) -> dict[str, Any]:
    payload = _db_contract_view(path, limit=max(20, min(limit, 500)))
    if payload is None:
        raise HTTPException(status_code=404, detail="Book record not found in SQLite.")
    return payload


@app.get("/runtime/export-book-json")
def runtime_export_book_json(path: str, limit: int = 1000):
    payload = runtime_contract_view(path=path, limit=limit)
    safe_name = str(payload.get("summary", {}).get("name") or "book").replace("/", "_").replace("\\", "_")
    body = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.json"'},
    )


@app.post("/runtime/upload-book")
async def upload_book(file: UploadFile = File(...)) -> dict[str, Any]:
    ensure_dirs()
    safe_name = Path(file.filename or "book.epub").name
    target = UPLOADS_DIR / f"{datetime.now().strftime('%Y%m%dT%H%M%S')}_{safe_name}"
    digest = hashlib.sha256()
    total_bytes = 0
    with target.open("wb") as handle:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
            digest.update(chunk)
            total_bytes += len(chunk)
    stored = _safe_db(
        None,
        "register_uploaded_source",
        lambda: SQLITE_STORE.register_uploaded_source(
            original_name=safe_name,
            stored_path=str(target),
            size_bytes=total_bytes,
            mime_type=str(file.content_type or "").strip() or None,
            sha256=digest.hexdigest(),
            source_kind="book_upload",
            metadata={
                "relative_path": rel(target),
                "uploaded_at": utc_now(),
            },
        ),
    ) or {}
    return {
        "id": stored.get("id") or "",
        "path": str(target),
        "relative_path": rel(target),
        "name": safe_name,
        "size_bytes": total_bytes,
        "mime_type": str(file.content_type or "").strip(),
        "sha256": digest.hexdigest(),
    }


@app.get("/runtime/uploads")
def runtime_uploads() -> dict[str, Any]:
    return {"uploads": _safe_db([], "get_uploaded_sources", lambda: SQLITE_STORE.get_uploaded_sources(limit=500))}


@app.post("/runtime/uploads/batch")
async def runtime_upload_batch(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    uploads: list[dict[str, Any]] = []
    for file in files:
        uploads.append(await upload_book(file))
    return {"uploads": uploads, "count": len(uploads)}


@app.delete("/runtime/uploads/{source_id}")
def runtime_delete_upload(source_id: str) -> dict[str, Any]:
    with SQLITE_STORE.session_factory() as session:
        row = session.get(SqlUploadedSource, source_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Uploaded source not found.")
        stored_path = row.stored_path
        session.delete(row)
        session.commit()
    return {"deleted": True, "source_id": source_id, "file_retained": stored_path}


def _import_plan_payload(plan: ImportPlanRequest) -> dict[str, Any]:
    return {
        "series_id": slugify(plan.series_id),
        "series_title": plan.series_title.strip() or plan.series_id.strip() or "Untitled Series",
        "books": [book.model_dump() for book in plan.books if book.selected],
        "shared_config": plan.shared_config,
        "created_at": utc_now(),
    }


def _validate_import_plan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return DatabaseAnalysisRunService(SQLITE_STORE).validate_import_plan_payload(payload)


def _run_import_plan_analysis_job(job_id: str, request_payload: dict[str, Any]) -> None:
    DatabaseAnalysisRunService(SQLITE_STORE).run_import_plan_job(job_id, request_payload)


@app.post("/runtime/import-plans")
def runtime_create_import_plan(request: ImportPlanRequest) -> dict[str, Any]:
    ensure_dirs()
    plan_id = f"import_plan_{datetime.now().strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    plan_payload = _import_plan_payload(request)
    payload = {
        "id": plan_id,
        "type": "import-plan",
        "status": "staging",
        "created_at": utc_now(),
        "request": plan_payload,
        "progress": {"current": 0, "total": len(plan_payload["books"]), "label": "Plan created", "phase": "staging"},
    }
    save_job(payload)
    return load_job(plan_id)


@app.get("/runtime/import-plans/{plan_id}")
def runtime_import_plan(plan_id: str) -> dict[str, Any]:
    return load_job(plan_id)


@app.post("/runtime/import-plans/{plan_id}/validate")
def runtime_validate_import_plan(plan_id: str) -> dict[str, Any]:
    payload = load_job(plan_id)
    if payload.get("type") != "import-plan":
        raise HTTPException(status_code=400, detail="Job is not an import plan.")
    validation = _validate_import_plan_payload(payload.get("request") or {})
    payload["status"] = "validated" if validation["can_start"] else "blocked"
    payload["artifacts"] = {**(payload.get("artifacts") or {}), "validation": validation}
    payload["progress"] = {"current": len((payload.get("request") or {}).get("books") or []), "total": len((payload.get("request") or {}).get("books") or []), "label": validation["summary"], "phase": "validation"}
    save_job(payload)
    SQLITE_STORE.append_dashboard_job_log(plan_id, f"IMPORT_PLAN_VALIDATION {json.dumps(validation, ensure_ascii=False)}", level="INFO")
    return {"id": plan_id, "validation": validation, "plan": load_job(plan_id)}


@app.post("/runtime/import-plans/{plan_id}/start")
def runtime_start_import_plan(plan_id: str) -> dict[str, Any]:
    payload = load_job(plan_id)
    validation = _validate_import_plan_payload(payload.get("request") or {})
    if not validation["can_start"]:
        raise HTTPException(status_code=409, detail={"message": "Import plan is blocked.", "validation": validation})
    job_id = f"analysis_{datetime.now().strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    job = {
        "id": job_id,
        "type": "db-native-analysis",
        "status": "queued",
        "status_reason": "Queued from validated dashboard import plan.",
        "created_at": utc_now(),
        "request": payload.get("request") or {},
        "artifacts": {"import_plan_id": plan_id, "validation": validation},
        "progress": {"current": 0, "total": len((payload.get("request") or {}).get("books") or []), "label": "Queued database-native analysis", "phase": "queued"},
    }
    save_job(job)
    SQLITE_STORE.append_dashboard_job_log(job_id, "DB_NATIVE_ANALYSIS_QUEUED from validated import plan.", level="INFO")
    thread = threading.Thread(target=_run_import_plan_analysis_job, args=(job_id, payload.get("request") or {}), daemon=True)
    thread.start()
    return load_job(job_id)


@app.get("/runtime/series")
def runtime_series() -> dict[str, Any]:
    with SQLITE_STORE.session_factory() as session:
        series_rows = session.execute(select(SqlSeries).order_by(SqlSeries.title.asc())).scalars().all()
        books = session.execute(select(SqlBook)).scalars().all()
        counts: dict[str, int] = {}
        for book in books:
            counts[str(book.series_id or "")] = counts.get(str(book.series_id or ""), 0) + 1
        rows = [
            {
                "id": row.id,
                "series_id": row.series_id,
                "title": row.title,
                "book_count": counts.get(row.series_id, 0),
                "metadata": row.metadata_json or {},
            }
            for row in series_rows
        ]
    return {"series": rows}


@app.get("/runtime/series/{series_id}/books")
def runtime_series_books(series_id: str) -> dict[str, Any]:
    return {"books": SQLITE_STORE.get_series_books(series_id)}


@app.get("/runtime/audiobook/runs")
def runtime_audiobook_runs(series_id: str = "", book_id: str = "", limit: int = 100) -> dict[str, Any]:
    rows = _safe_db(
        [],
        "get_audiobook_runs",
        lambda: SQLITE_STORE.get_audiobook_runs(
            series_id=str(series_id or "").strip() or None,
            book_id=str(book_id or "").strip() or None,
            limit=max(1, min(limit, 500)),
        ),
    )
    return {"runs": [_augment_audiobook_run_from_outputs(item) for item in rows]}


@app.get("/runtime/audiobook/runs/{run_id}")
def runtime_audiobook_run(run_id: str) -> dict[str, Any]:
    payload = _safe_db(None, "get_audiobook_run", lambda: SQLITE_STORE.get_audiobook_run(run_id))
    if payload is None:
        raise HTTPException(status_code=404, detail="Audiobook run not found.")
    return _augment_audiobook_run_from_outputs(payload)


@app.get("/runtime/audiobook/runs/{run_id}/chapters/{chapter_id}/audio")
def runtime_audiobook_chapter_audio(run_id: str, chapter_id: str):
    with SQLITE_STORE.session_factory() as session:
        row = session.execute(
            select(SqlAudiobookChapter)
            .where(SqlAudiobookChapter.run_id == run_id, SqlAudiobookChapter.chapter_id == chapter_id)
        ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Audiobook chapter not found.")
    audio_path = Path(str(row.audio_path or "")).resolve() if str(row.audio_path or "").strip() else None
    if audio_path is None or not audio_path.exists() or not audio_path.is_file():
        raise HTTPException(status_code=404, detail="Audio output is not available for this chapter.")
    media_type = str(row.audio_mime_type or "").strip() or ("audio/flac" if audio_path.suffix.lower() == ".flac" else "audio/wav")
    return FileResponse(audio_path, media_type=media_type, filename=audio_path.name)


@app.get("/runtime/audiobook/runs/{run_id}/audio")
def runtime_audiobook_run_audio(run_id: str):
    run = _safe_db(None, "get_audiobook_run", lambda: SQLITE_STORE.get_audiobook_run(run_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Audiobook run not found.")
    bundle_path = _build_audiobook_bundle(run_id)
    safe_title = re.sub(r"[^A-Za-z0-9._-]+", "_", str((run or {}).get("title") or "audiobook").strip()).strip("_") or "audiobook"
    return FileResponse(bundle_path, media_type="audio/wav", filename=f"{safe_title}.wav")


@app.post("/runtime/audiobook/runs/stage")
def runtime_stage_audiobook_run(request: AudiobookStageRequest) -> dict[str, Any]:
    return {"run": _create_staged_audiobook_run(request)}


@app.post("/runtime/audiobook/jobs")
def runtime_start_audiobook_job(request: AudiobookStageRequest) -> dict[str, Any]:
    run = _create_staged_audiobook_run(request)
    job = _queue_audiobook_run(str(run.get("id") or ""))
    return {"run": _safe_db(None, "get_audiobook_run", lambda: SQLITE_STORE.get_audiobook_run(str(run.get("id") or ""))), "job": job}


@app.post("/runtime/audiobook/runs/{run_id}/start")
def runtime_start_existing_audiobook_run(run_id: str) -> dict[str, Any]:
    job = _queue_audiobook_run(run_id)
    run = _safe_db(None, "get_audiobook_run", lambda: SQLITE_STORE.get_audiobook_run(run_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Audiobook run not found.")
    return {"run": run, "job": job}


@app.get("/runtime/books/{book_ref:path}/analysis")
def runtime_book_analysis(book_ref: str, limit: int = 1000, section: str | None = None) -> dict[str, Any]:
    payload = _db_contract_view(book_ref, limit=max(20, min(limit, 1000)), section=section)
    if payload is None:
        raise HTTPException(status_code=404, detail="Book not found in SQLite.")
    return payload


@app.get("/runtime/jobs/{job_id}/logs")
def runtime_job_logs(job_id: str, limit: int = 300) -> dict[str, Any]:
    load_job(job_id)
    lines = SQLITE_STORE.get_dashboard_job_log_tail(job_id, limit=max(1, min(limit, 2000)))
    return {"job_id": job_id, "lines": lines}


@app.post("/runtime/jobs/{job_id}/{action}")
def runtime_job_control(job_id: str, action: str) -> dict[str, Any]:
    if action not in {"pause", "resume", "cancel", "retry"}:
        raise HTTPException(status_code=404, detail="Unsupported job action.")
    payload = load_job(job_id)
    status = str(payload.get("status") or "").lower()
    if action == "cancel" and status in {"running", "queued"}:
        artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
        artifacts["control_requested"] = "cancel"
        payload["artifacts"] = artifacts
        payload["status_reason"] = "Cancellation requested; worker will stop at the next safe boundary."
        save_job(payload)
        SQLITE_STORE.append_dashboard_job_log(job_id, "JOB_CANCEL_REQUESTED safe-boundary cancellation requested from dashboard.", level="WARNING")
        return load_job(job_id)
    if action == "cancel" and status in {"queued", "staging", "validated", "blocked"}:
        payload.update({"status": "cancelled", "finished_at": utc_now(), "status_reason": "Cancelled from dashboard before worker execution."})
        save_job(payload)
        SQLITE_STORE.append_dashboard_job_log(job_id, "JOB_CANCELLED safe pre-worker cancellation from dashboard.", level="WARNING")
        return load_job(job_id)
    if action == "retry" and status in {"failed", "cancelled"} and str(payload.get("type") or "") == "db-native-analysis":
        request_payload = dict(payload.get("request") or {})
        resume_payload = dict(request_payload.get("resume") or {})
        resume_payload["retry_of"] = job_id
        request_payload["resume"] = resume_payload
        retry_id = f"analysis_retry_{datetime.now().strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
        retry_job = {
            "id": retry_id,
            "type": "db-native-analysis",
            "status": "queued",
            "status_reason": f"Retry of {job_id}",
            "created_at": utc_now(),
            "request": request_payload,
            "artifacts": {"retry_of": job_id, "resume_enabled": True},
            "progress": {"current": 0, "total": len((payload.get("request") or {}).get("books") or []), "label": "Queued retry", "phase": "queued"},
        }
        save_job(retry_job)
        SQLITE_STORE.append_dashboard_job_log(retry_id, f"DB_NATIVE_ANALYSIS_RETRY queued from {job_id} with resume semantics enabled.", level="INFO")
        thread = threading.Thread(target=_run_import_plan_analysis_job, args=(retry_id, retry_job.get("request") or {}), daemon=True)
        thread.start()
        return load_job(retry_id)
    if action == "retry" and status in {"failed", "cancelled"} and str(payload.get("type") or "") == "audiobook-pipeline":
        run_id = str((payload.get("artifacts") or {}).get("audiobook_run_id") or "").strip()
        if not run_id:
            raise HTTPException(status_code=409, detail="Audiobook retry is missing the persisted run_id artifact.")
        return _queue_audiobook_run(run_id, retry_of=job_id)
    raise HTTPException(status_code=409, detail=f"{action} is not safe for this job type/status in the current runtime.")


@app.post("/runtime/start-character-render")
def start_character_render(request: CharacterRenderRequest) -> dict[str, Any]:
    ensure_dirs()
    command = build_character_render_command(request)
    job_id = f"render_{datetime.now().strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    payload = {
        "id": job_id,
        "type": "render-character-sheets",
        "status": "queued",
        "created_at": utc_now(),
        "command": subprocess.list2cmdline(command),
        "request": request.model_dump(),
    }
    save_job(payload)
    thread = threading.Thread(target=run_job, args=(job_id, command), daemon=True)
    thread.start()
    return load_job(job_id)


@app.post("/runtime/start-series-character-render")
def start_series_character_render(request: SeriesCharacterRenderRequest) -> dict[str, Any]:
    ensure_dirs()
    job_id = f"series_render_{datetime.now().strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    payload = {
        "id": job_id,
        "type": "render-series-character-visuals",
        "status": "queued",
        "created_at": utc_now(),
        "command": f"db-series-render:{request.series_id}",
        "request": request.model_dump(),
    }
    save_job(payload)
    thread = threading.Thread(target=run_series_character_render_job, args=(job_id, request), daemon=True)
    thread.start()
    return load_job(job_id)


@app.post("/runtime/start-decoder")
def start_decoder(request: DecoderRequest) -> dict[str, Any]:
    ensure_dirs()
    resolved_book_ref = _resolve_decoder_book_ref(series_id=request.series_id, book_ref=request.book_ref)
    if not str(request.series_id or "").strip() and not resolved_book_ref:
        raise HTTPException(status_code=400, detail="series_id is required.")
    if not str(request.user_prompt or "").strip():
        raise HTTPException(status_code=400, detail="user_prompt is required.")
    request = request.model_copy(update={"book_ref": resolved_book_ref})
    job_id = f"decoder_{datetime.now().strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    payload = {
        "id": job_id,
        "type": "decoder-generate-story",
        "status": "queued",
        "created_at": utc_now(),
        "command": f"db-decoder:{request.story_mode}:{request.provider or 'auto'}",
        "request": request.model_dump(),
    }
    save_job(payload)
    thread = threading.Thread(target=run_decoder_job, args=(job_id, request), daemon=True)
    thread.start()
    return load_job(job_id)


@app.get("/runtime/generated-stories")
def runtime_generated_stories(series_id: str = "", book_id: str = "") -> dict[str, Any]:
    if series_id:
        stories = SQLITE_STORE.get_generated_stories_for_series(series_id)
    elif book_id:
        stories = SQLITE_STORE.get_generated_stories(book_id=book_id)
    else:
        stories = SQLITE_STORE.get_generated_stories()
    book_lookup = {row["book_id"]: row for row in _safe_db([], "all_series_books", lambda: sum([SQLITE_STORE.get_series_books(sid) for sid in {str(item.get("series_id") or "") for item in _db_contract_summaries(limit=500)} if sid], []))}
    for story in stories:
        book_row = book_lookup.get(str(story.get("book_id") or ""))
        if book_row:
            story["book_title"] = book_row.get("title") or ""
            story["series_id"] = book_row.get("series_id") or ""
    return {"stories": stories}


@app.get("/runtime/generated-stories/{story_id}")
def runtime_generated_story(story_id: str) -> dict[str, Any]:
    story = SQLITE_STORE.get_generated_story(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Generated story not found.")
    return story


@app.get("/runtime/stories")
def runtime_stories(series_id: str = "", book_id: str = "") -> dict[str, Any]:
    return runtime_generated_stories(series_id=series_id, book_id=book_id)


@app.get("/runtime/stories/{story_id}")
def runtime_story(story_id: str) -> dict[str, Any]:
    return runtime_generated_story(story_id)


@app.get("/runtime/decoder/options")
def runtime_decoder_options() -> dict[str, Any]:
    books = _db_contract_summaries(limit=500)
    series_rows = _decoder_series_options()
    providers = _available_decoder_providers(refresh=True)
    return {
        "modes": [
            {"value": "pre_canon", "label": "Pre-canon", "requires": ["series_id", "provider", "user_prompt"]},
            {"value": "mid_canon", "label": "Mid-canon", "requires": ["series_id", "provider", "user_prompt"]},
            {"value": "post_canon", "label": "Post-canon", "requires": ["series_id", "provider", "user_prompt"]},
            {"value": "alternate_universe", "label": "Alternate universe", "requires": ["series_id", "provider", "user_prompt"]},
        ],
        "defaults": {
            "chapter_count": 20,
            "story_mode": "post_canon",
            "provider": providers[0]["value"] if providers else "",
        },
        "books": books,
        "series": series_rows,
        "providers": providers,
    }


@app.post("/runtime/decoder/plans/validate")
def runtime_validate_decoder_plan(request: DecoderPlanRequest) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    resolved_book_ref = _resolve_decoder_book_ref(series_id=request.series_id, book_ref=request.book_ref)
    resolved_series_id = str(request.series_id or "").strip()
    available_providers = _available_decoder_providers(refresh=False)
    available_provider_keys = {str(row.get("value") or "").strip().lower() for row in available_providers}
    requested_provider = str(request.provider or "").strip().lower()
    if not resolved_series_id and not resolved_book_ref:
        errors.append("A database-backed series must be selected.")
    elif resolved_series_id and not _series_book_refs(resolved_series_id):
        errors.append("Selected series was not found in SQLite.")
    elif resolved_book_ref and _db_book_by_contract_path(resolved_book_ref) is None:
        errors.append("Selected decoder anchor book was not found in SQLite.")
    if request.story_mode not in {"pre_canon", "mid_canon", "post_canon", "alternate_universe"}:
        errors.append("Story mode is not supported.")
    if request.chapter_count < 1 or request.chapter_count > 60:
        errors.append("Chapter count must be between 1 and 60.")
    if not str(request.user_prompt or "").strip():
        errors.append("User prompt is required.")
    if not available_providers:
        errors.append("No decoder providers are currently available.")
    elif requested_provider and requested_provider not in available_provider_keys:
        errors.append("Selected decoder provider is not currently available.")
    elif not requested_provider:
        requested_provider = available_providers[0]["value"]
    continuity_anchor, divergence_anchor = _auto_decoder_anchors(
        story_mode=request.story_mode,
        book_ref=resolved_book_ref,
        continuity_anchor=request.continuity_anchor,
        divergence_anchor=request.divergence_anchor,
    )
    plan = request.model_dump()
    plan["series_id"] = resolved_series_id
    plan["book_ref"] = resolved_book_ref
    plan["provider"] = requested_provider
    plan["continuity_anchor"] = continuity_anchor
    plan["divergence_anchor"] = divergence_anchor
    return {"valid": not errors, "errors": errors, "warnings": warnings, "plan": plan}


@app.post("/runtime/decoder/jobs")
def runtime_decoder_jobs(request: DecoderRequest) -> dict[str, Any]:
    validation = runtime_validate_decoder_plan(DecoderPlanRequest(**request.model_dump()))
    if not validation["valid"]:
        raise HTTPException(status_code=400, detail=validation)
    validated_request = DecoderRequest(**validation["plan"])
    if not str(validated_request.user_prompt or "").strip():
        validated_request.user_prompt = request.user_prompt
    if not str(validated_request.primary_pov_character or "").strip():
        validated_request.primary_pov_character = request.primary_pov_character
    if not str(validated_request.continuity_anchor or "").strip():
        validated_request.continuity_anchor = request.continuity_anchor
    if not str(validated_request.divergence_anchor or "").strip():
        validated_request.divergence_anchor = request.divergence_anchor
    if not int(validated_request.chapter_count or 0):
        validated_request.chapter_count = request.chapter_count
    return start_decoder(validated_request)


@app.get("/runtime/export-generated-story-epub")
def runtime_export_generated_story_epub(story_id: str):
    story = SQLITE_STORE.get_generated_story(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Generated story not found.")
    exporter = GeneratedStoryEpubService(STORY_EXPORTS_DIR)
    output_path = exporter.export_story(story)
    return FileResponse(output_path, filename=output_path.name, media_type="application/epub+zip")


@app.get("/runtime/assets/series-summary")
def runtime_assets_series_summary() -> dict[str, Any]:
    with SQLITE_STORE.session_factory() as session:
        rows = session.execute(
            select(
                SqlBook.series_id.label("series_id"),
                SqlSeries.title.label("series_title"),
                func.count(SqlEntity.id).label("asset_count"),
                func.sum(case((SqlEntity.generated_image_path.is_not(None), 1), else_=0)).label("rendered_count"),
            )
            .join(SqlEntity, SqlEntity.book_id == SqlBook.id)
            .join(SqlSeries, SqlSeries.series_id == SqlBook.series_id, isouter=True)
            .group_by(SqlBook.series_id, SqlSeries.title)
            .order_by(SqlSeries.title.asc(), SqlBook.series_id.asc())
        ).mappings().all()
    return {
        "series": [
            {
                "series_id": str(row.get("series_id") or "").strip(),
                "series_title": str(row.get("series_title") or row.get("series_id") or "Unassigned").strip(),
                "asset_count": int(row.get("asset_count") or 0),
                "rendered_count": int(row.get("rendered_count") or 0),
            }
            for row in rows
            if str(row.get("series_id") or "").strip()
        ]
    }


@app.get("/runtime/assets/entities")
def runtime_assets_entities(entity_type: str = "", q: str = "", book_id: str = "", series_id: str = "", limit: int = 48, offset: int = 0) -> dict[str, Any]:
    with SQLITE_STORE.session_factory() as session:
        safe_limit = max(1, min(int(limit or 48), 120))
        safe_offset = max(0, int(offset or 0))
        base_query = (
            select(
                SqlEntity.id.label("entity_id"),
                SqlEntity.book_id.label("book_id"),
                SqlEntity.canonical_name.label("canonical_name"),
                SqlEntity.entity_type.label("entity_type"),
                SqlEntity.mention_count.label("mention_count"),
                SqlEntity.generated_image_path.label("generated_image_path"),
                SqlEntity.generated_thumbnail_path.label("generated_thumbnail_path"),
                SqlBook.title.label("book_title"),
                SqlBook.series_id.label("series_id"),
                SqlBook.book_index.label("book_index"),
            )
            .join(SqlBook, SqlEntity.book_id == SqlBook.id)
        )
        if entity_type:
            base_query = base_query.where(SqlEntity.entity_type == entity_type)
        if book_id:
            base_query = base_query.where(SqlEntity.book_id == book_id)
        if series_id:
            base_query = base_query.where(SqlBook.series_id == series_id)
        needle = q.strip().lower()
        if needle:
            base_query = base_query.where(func.lower(SqlEntity.canonical_name).contains(needle))
        total_count = session.execute(
            select(func.count()).select_from(base_query.subquery())
        ).scalar_one()
        rows = session.execute(
            base_query
            .order_by(SqlBook.book_index.asc(), SqlEntity.entity_type.asc(), SqlEntity.canonical_name.asc())
            .offset(safe_offset)
            .limit(safe_limit)
        ).mappings().all()
        entity_ids = [str(row.get("entity_id") or "").strip() for row in rows if str(row.get("entity_id") or "").strip()]
        series_ids = sorted({str(row.get("series_id") or "").strip() for row in rows if str(row.get("series_id") or "").strip()})
        prompt_counts: dict[str, int] = {}
        image_counts: dict[str, int] = {}
        latest_images: dict[str, dict[str, Any]] = {}
        if entity_ids:
            prompt_counts = {
                str(row[0]): 1
                for row in session.execute(
                    select(SqlVisualPrompt.entity_id)
                    .where(SqlVisualPrompt.entity_id.in_(entity_ids))
                    .group_by(SqlVisualPrompt.entity_id)
                ).all()
                if str(row[0] or "").strip()
            }
            image_counts = dict(
                session.execute(
                    select(SqlGeneratedImage.entity_id, func.count(SqlGeneratedImage.id))
                    .where(SqlGeneratedImage.entity_id.in_(entity_ids))
                    .group_by(SqlGeneratedImage.entity_id)
                ).all()
            )
            image_rows = session.execute(
                select(
                    SqlGeneratedImage.entity_id.label("entity_id"),
                    SqlGeneratedImage.output_path.label("output_path"),
                    SqlGeneratedImage.thumbnail_path.label("thumbnail_path"),
                    SqlGeneratedImage.render_status.label("render_status"),
                )
                .where(SqlGeneratedImage.entity_id.in_(entity_ids))
                .order_by(SqlGeneratedImage.entity_id.asc(), SqlGeneratedImage.updated_at.desc())
            ).mappings().all()
            for row in image_rows:
                entity_id_value = str(row.get("entity_id") or "").strip()
                if entity_id_value and entity_id_value not in latest_images:
                    latest_images[entity_id_value] = dict(row)
        series_lookup = {
            str(row.series_id): str(row.title or "")
            for row in session.execute(select(SqlSeries).where(SqlSeries.series_id.in_(series_ids))).scalars().all()
            if row.series_id
        } if series_ids else {}
        output: list[dict[str, Any]] = []
        for row in rows:
            entity_id_value = str(row.get("entity_id") or "").strip()
            image = latest_images.get(entity_id_value) or {}
            image_path = str(row.get("generated_image_path") or image.get("output_path") or "").strip()
            thumbnail_path = _ensure_runtime_thumbnail(
                image_path,
                str(row.get("generated_thumbnail_path") or image.get("thumbnail_path") or "").strip(),
            )
            output.append(
                {
                    "id": entity_id_value,
                    "book_id": row.get("book_id") or "",
                    "book_title": row.get("book_title") or "",
                    "series_id": row.get("series_id") or "",
                    "series_title": series_lookup.get(str(row.get("series_id") or "").strip(), ""),
                    "name": row.get("canonical_name") or "",
                    "entity_type": row.get("entity_type") or "",
                    "mention_count": int(row.get("mention_count") or 0),
                    "prompt_count": int(prompt_counts.get(entity_id_value) or 0),
                    "image_count": int(image_counts.get(entity_id_value) or 0),
                    "render_status": str(image.get("render_status") or "").strip(),
                    "generated_image_path": image_path,
                    "generated_thumbnail_path": thumbnail_path,
                }
            )
    return {"entities": output, "count": len(output), "total": int(total_count or 0), "limit": safe_limit, "offset": safe_offset}


@app.get("/runtime/assets/entities/{entity_id}")
def runtime_asset_entity(entity_id: str) -> dict[str, Any]:
    with SQLITE_STORE.session_factory() as session:
        entity = session.get(SqlEntity, entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="Entity not found.")
        book = session.get(SqlBook, entity.book_id)
        prompts = session.execute(select(SqlVisualPrompt).where(SqlVisualPrompt.entity_id == entity.id).order_by(SqlVisualPrompt.updated_at.desc())).scalars().all()
        prompts = _canonical_prompt_rows(prompts)
        images = session.execute(select(SqlGeneratedImage).where(SqlGeneratedImage.entity_id == entity.id).order_by(SqlGeneratedImage.updated_at.desc())).scalars().all()
        entity_payload = {
            "id": entity.id,
            "book_id": entity.book_id,
            "book_title": book.title if book else "",
            "name": entity.canonical_name,
            "entity_type": entity.entity_type,
            "mention_count": entity.mention_count or 0,
            "initial_physical_description": entity.initial_physical_description or {},
            "first_appearance_profile": entity.first_appearance_profile or {},
            "typed_attributes": entity.typed_attributes or {},
            "latest_world_state": entity.latest_world_state or {},
            "baseline_visual_prompt": entity.baseline_visual_prompt or "",
            "generated_image_path": entity.generated_image_path or "",
            "generated_thumbnail_path": _ensure_runtime_thumbnail(entity.generated_image_path or "", entity.generated_thumbnail_path or ""),
            "analysis_quality_flags": entity.analysis_quality_flags or [],
        }
        prompt_rows = [
            {
                "id": row.id,
                "prompt_type": row.prompt_type,
                "visual_bucket": row.visual_bucket,
                "positive_prompt": row.positive_prompt,
                "negative_prompt": row.negative_prompt,
                "source_evidence": row.source_evidence,
                "confidence": row.confidence,
                "details": row.details_json or {},
                "metadata": row.metadata_json or {},
                "updated_at": row.updated_at.isoformat() if row.updated_at else "",
            }
            for row in prompts
        ]
        latest_positive_prompt = str(prompt_rows[0]["positive_prompt"] if prompt_rows else entity.baseline_visual_prompt or "").strip()
        latest_negative_prompt = str(prompt_rows[0]["negative_prompt"] if prompt_rows else "").strip()
        image_rows = [
            {
                "id": row.id,
                "prompt_id": row.prompt_id,
                "output_path": row.output_path,
                "thumbnail_path": _ensure_runtime_thumbnail(row.output_path or "", row.thumbnail_path or ""),
                "render_status": row.render_status,
                "workflow_name": row.workflow_name,
                "manifest": row.manifest_json or {},
                "updated_at": row.updated_at.isoformat() if row.updated_at else "",
            }
            for row in images
        ]
    return {
        "entity": entity_payload,
        "prompts": prompt_rows,
        "images": image_rows,
        "prompt_editor": _build_prompt_editor_payload(
            latest_positive_prompt,
            latest_negative_prompt,
            str(entity.entity_type or "").strip().lower(),
        ),
    }


@app.patch("/runtime/assets/entities/{entity_id}")
def runtime_rename_asset_entity(entity_id: str, request: EntityRenameRequest) -> dict[str, Any]:
    new_name = str(request.name or "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="name is required.")

    with SQLITE_STORE.session_factory() as session:
        entity = session.get(SqlEntity, entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="Entity not found.")

        old_name = str(entity.canonical_name or "").strip()
        if not old_name:
            raise HTTPException(status_code=400, detail="Entity has no canonical name to rename.")
        if new_name == old_name:
            session.commit()
            return {"renamed": True, "entity_id": entity_id, "old_name": old_name, "new_name": new_name, "asset": runtime_asset_entity(entity_id)}

        conflict = session.execute(
            select(SqlEntity).where(
                SqlEntity.book_id == entity.book_id,
                SqlEntity.entity_type == entity.entity_type,
                SqlEntity.canonical_name == new_name,
                SqlEntity.id != entity.id,
            )
        ).scalar_one_or_none()
        if conflict is not None:
            raise HTTPException(status_code=409, detail="Another entity with this name and type already exists in the same book.")

        entity.canonical_name = new_name
        entity.entity_context = _replace_name_in_text(entity.entity_context, old_name, new_name)
        entity.initial_physical_description = _replace_name_in_payload(entity.initial_physical_description, old_name, new_name)
        entity.first_appearance_profile = _replace_name_in_payload(entity.first_appearance_profile, old_name, new_name)
        entity.typed_attributes = _replace_name_in_payload(entity.typed_attributes, old_name, new_name)
        entity.latest_world_state = _replace_name_in_payload(entity.latest_world_state, old_name, new_name)
        entity.narrative_roles = _replace_name_in_payload(entity.narrative_roles, old_name, new_name)
        entity.descriptions = _replace_name_in_payload(entity.descriptions, old_name, new_name)
        entity.state_changes = _replace_name_in_payload(entity.state_changes, old_name, new_name)
        entity.event_links = _replace_name_in_payload(entity.event_links, old_name, new_name)
        entity.visual_change_log = _replace_name_in_payload(entity.visual_change_log, old_name, new_name)
        entity.analysis_quality_flags = _replace_name_in_payload(entity.analysis_quality_flags, old_name, new_name)
        entity.baseline_visual_prompt = _replace_name_in_text(entity.baseline_visual_prompt, old_name, new_name)
        entity.metadata_json = _replace_name_in_payload(entity.metadata_json, old_name, new_name)

        for row in session.execute(select(SqlCharacterProfile).where(SqlCharacterProfile.entity_id == entity.id)).scalars().all():
            row.character_name = new_name
            row.payload_json = _replace_name_in_payload(row.payload_json, old_name, new_name)

        for row in session.execute(select(SqlStableCharacterState).where(SqlStableCharacterState.entity_id == entity.id)).scalars().all():
            row.character_name = new_name
            row.payload_json = _replace_name_in_payload(row.payload_json, old_name, new_name)

        for row in session.execute(select(SqlVisualPrompt).where(SqlVisualPrompt.entity_id == entity.id)).scalars().all():
            row.entity_name = new_name
            row.positive_prompt = _replace_name_in_text(row.positive_prompt, old_name, new_name)
            row.negative_prompt = _replace_name_in_text(row.negative_prompt, old_name, new_name)
            row.source_evidence = _replace_name_in_text(row.source_evidence, old_name, new_name)
            row.details_json = _replace_name_in_payload(row.details_json, old_name, new_name)
            row.metadata_json = _replace_name_in_payload(row.metadata_json, old_name, new_name)

        for row in session.execute(select(SqlGeneratedImage).where(SqlGeneratedImage.entity_id == entity.id)).scalars().all():
            row.entity_name = new_name
            row.manifest_json = _replace_name_in_payload(row.manifest_json, old_name, new_name)

        for row in session.execute(select(SqlEvent).where(SqlEvent.book_id == entity.book_id)).scalars().all():
            row.entities_involved = _replace_name_in_payload(row.entities_involved, old_name, new_name)
            row.payload_json = _replace_name_in_payload(row.payload_json, old_name, new_name)

        for row in session.execute(select(SqlScene).where(SqlScene.book_id == entity.book_id)).scalars().all():
            if str(entity.entity_type or "").strip().lower() == "location":
                row.location_name = _replace_name_in_text(row.location_name, old_name, new_name)
                row.location_description = _replace_name_in_text(row.location_description, old_name, new_name)
            row.payload_json = _replace_name_in_payload(row.payload_json, old_name, new_name)

        for row in session.execute(select(SqlTimelineRow).where(SqlTimelineRow.book_id == entity.book_id)).scalars().all():
            row.payload_json = _replace_name_in_payload(row.payload_json, old_name, new_name)

        for row in session.execute(select(SqlGeneratedStory).where(SqlGeneratedStory.book_id == entity.book_id)).scalars().all():
            row.primary_pov_character = _replace_name_in_text(row.primary_pov_character, old_name, new_name)
            row.output_text = _replace_name_in_text(row.output_text, old_name, new_name)
            row.blueprint_json = _replace_name_in_payload(row.blueprint_json, old_name, new_name)
            row.progress_json = _replace_name_in_payload(row.progress_json, old_name, new_name)
            row.verification_json = _replace_name_in_payload(row.verification_json, old_name, new_name)
            row.metadata_json = _replace_name_in_payload(row.metadata_json, old_name, new_name)

        session.commit()

    return {"renamed": True, "entity_id": entity_id, "old_name": old_name, "new_name": new_name, "asset": runtime_asset_entity(entity_id)}


@app.delete("/runtime/assets/entities/{entity_id}")
def runtime_delete_asset_entity(entity_id: str) -> dict[str, Any]:
    deleted_files: list[str] = []
    preview_dir = DASHBOARD_DIR / "asset_previews" / str(entity_id or "").strip()
    with SQLITE_STORE.session_factory() as session:
        entity = session.get(SqlEntity, entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="Entity not found.")

        image_rows = session.execute(select(SqlGeneratedImage).where(SqlGeneratedImage.entity_id == entity.id)).scalars().all()
        prompt_rows = session.execute(select(SqlVisualPrompt).where(SqlVisualPrompt.entity_id == entity.id)).scalars().all()
        file_candidates = {
            str(entity.generated_image_path or "").strip(),
            str(entity.generated_thumbnail_path or "").strip(),
        }
        for row in image_rows:
            file_candidates.add(str(row.output_path or "").strip())
            file_candidates.add(str(row.thumbnail_path or "").strip())

        deleted_counts = {
            "generated_images": len(image_rows),
            "visual_prompts": len(prompt_rows),
            "character_profiles": session.execute(
                delete(SqlCharacterProfile).where(SqlCharacterProfile.entity_id == entity.id)
            ).rowcount or 0,
            "character_visual_baselines": session.execute(
                delete(SqlCharacterVisualBaseline).where(SqlCharacterVisualBaseline.entity_id == entity.id)
            ).rowcount or 0,
            "character_visual_scene_states": session.execute(
                delete(SqlCharacterVisualSceneState).where(SqlCharacterVisualSceneState.entity_id == entity.id)
            ).rowcount or 0,
            "creature_visual_baselines": session.execute(
                delete(SqlCreatureVisualBaseline).where(SqlCreatureVisualBaseline.entity_id == entity.id)
            ).rowcount or 0,
            "object_visual_baselines": session.execute(
                delete(SqlObjectVisualBaseline).where(SqlObjectVisualBaseline.entity_id == entity.id)
            ).rowcount or 0,
            "object_scene_states": session.execute(
                delete(SqlObjectSceneState).where(SqlObjectSceneState.entity_id == entity.id)
            ).rowcount or 0,
            "location_visual_baselines": session.execute(
                delete(SqlLocationVisualBaseline).where(SqlLocationVisualBaseline.entity_id == entity.id)
            ).rowcount or 0,
            "location_scene_states": session.execute(
                delete(SqlLocationSceneState).where(SqlLocationSceneState.entity_id == entity.id)
            ).rowcount or 0,
            "stable_character_states": session.execute(
                delete(SqlStableCharacterState).where(SqlStableCharacterState.entity_id == entity.id)
            ).rowcount or 0,
        }
        if image_rows:
            session.execute(delete(SqlGeneratedImage).where(SqlGeneratedImage.entity_id == entity.id))
        if prompt_rows:
            session.execute(delete(SqlVisualPrompt).where(SqlVisualPrompt.entity_id == entity.id))
        session.delete(entity)
        session.commit()

    for path in sorted(candidate for candidate in file_candidates if candidate):
        target = _safe_runtime_cleanup_path(path)
        if target and target.exists():
            deleted_files.append(str(target))
        _remove_runtime_artifact(path)
    _remove_runtime_artifact(preview_dir)

    return {
        "deleted": True,
        "entity_id": entity_id,
        "deleted_counts": deleted_counts,
        "deleted_files": deleted_files,
    }


@app.post("/runtime/assets/entities/{entity_id}/prompt-versions")
def runtime_create_prompt_version(entity_id: str, request: PromptVersionRequest) -> dict[str, Any]:
    with SQLITE_STORE.session_factory() as session:
        entity = session.get(SqlEntity, entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="Entity not found.")
        if not request.positive_prompt.strip():
            raise HTTPException(status_code=400, detail="positive_prompt is required.")
        prompt_rows = session.execute(
            select(SqlVisualPrompt).where(SqlVisualPrompt.entity_id == entity.id).order_by(SqlVisualPrompt.updated_at.desc())
        ).scalars().all()
        prompt_rows = _canonical_prompt_rows(prompt_rows)
        prompt = prompt_rows[0] if prompt_rows else None
        if prompt is None:
            prompt = SqlVisualPrompt(
                book_id=entity.book_id,
                entity_id=entity.id,
                entity_name=entity.canonical_name,
                entity_type=entity.entity_type,
            )
            session.add(prompt)
            session.flush()
        prompt.entity_name = entity.canonical_name
        prompt.entity_type = entity.entity_type
        prompt.prompt_type = prompt.prompt_type or f"initial_{entity.entity_type}_description"
        prompt.visual_bucket = prompt.visual_bucket or ("locations" if entity.entity_type == "location" else ("objects_creatures" if entity.entity_type in {"creature", "object"} else "initial_characters"))
        prompt.positive_prompt = request.positive_prompt.strip()
        prompt.negative_prompt = request.negative_prompt.strip()
        prompt.source_evidence = "dashboard prompt edit"
        prompt.confidence = "manual"
        prompt.details_json = request.details
        prompt.metadata_json = {"source": request.source, "created_from_dashboard": True, "updated_at": utc_now()}
        extra_prompt_ids = [row.id for row in session.execute(
            select(SqlVisualPrompt).where(SqlVisualPrompt.entity_id == entity.id, SqlVisualPrompt.id != prompt.id)
        ).scalars().all()]
        if extra_prompt_ids:
            session.execute(delete(SqlVisualPrompt).where(SqlVisualPrompt.id.in_(extra_prompt_ids)))
        if request.activate:
            entity.baseline_visual_prompt = request.positive_prompt.strip()
        session.commit()
        return {"prompt_id": prompt.id, "entity_id": entity.id, "activated": request.activate}


@app.post("/runtime/assets/entities/{entity_id}/render")
def runtime_render_entity(entity_id: str, request: EntityRenderRequest) -> dict[str, Any]:
    with SQLITE_STORE.session_factory() as session:
        entity = session.get(SqlEntity, entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="Entity not found.")
        book_id = entity.book_id
        entity_type = entity.entity_type
    render_request = CharacterRenderRequest(
        contract_path=f"db://book/{book_id}",
        limit=0,
        overwrite=request.overwrite,
        entity_types=[entity_type],
        entity_ids=[entity_id],
        prompt_ids=[request.prompt_id] if request.prompt_id else [],
    )
    job = start_character_render(render_request)
    job["entity_id"] = entity_id
    return job


@app.post("/runtime/assets/entities/{entity_id}/preview-render")
def runtime_preview_render_entity(entity_id: str, request: AssetPreviewRenderRequest) -> dict[str, Any]:
    positive_prompt = str(request.positive_prompt or "").strip()
    if not positive_prompt:
        raise HTTPException(status_code=400, detail="positive_prompt is required.")
    negative_prompt = str(request.negative_prompt or "").strip()
    base_row, entity_info = _asset_render_row(entity_id)
    service = ComfyUICharacterSheetService()
    preview_dir = _asset_preview_dir(entity_info["entity_id"])
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    output_name = f"{stamp}_{_slugify_asset_name(entity_info['entity_name'])}.png"
    preview_path = preview_dir / output_name
    render_row = dict(base_row)
    render_row["positive_prompt"] = positive_prompt
    render_row["negative_prompt"] = negative_prompt
    render_row = service.render_single_payload(
        render_row,
        negative_prompt=negative_prompt,
        output_path=preview_path,
    )
    thumbnail_path = _ensure_runtime_thumbnail(str(preview_path))
    fingerprint = _asset_prompt_fingerprint(positive_prompt, negative_prompt)
    metadata = {
        "entity_id": entity_info["entity_id"],
        "entity_name": entity_info["entity_name"],
        "entity_type": entity_info["entity_type"],
        "book_id": entity_info["book_id"],
        "positive_prompt": positive_prompt,
        "negative_prompt": negative_prompt,
        "fingerprint": fingerprint,
        "workflow_mode": render_row.get("workflow_mode"),
        "width": render_row.get("width"),
        "height": render_row.get("height"),
        "created_at": utc_now(),
    }
    _asset_preview_meta_path(preview_path).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "entity_id": entity_info["entity_id"],
        "preview_image_path": str(preview_path),
        "preview_thumbnail_path": thumbnail_path,
        "render_status": "rendered",
        "fingerprint": fingerprint,
    }


@app.post("/runtime/assets/entities/{entity_id}/save-render")
def runtime_save_render_entity(entity_id: str, request: AssetSaveRenderRequest) -> dict[str, Any]:
    positive_prompt = str(request.positive_prompt or "").strip()
    preview_image_path = str(request.preview_image_path or "").strip()
    if not positive_prompt:
        raise HTTPException(status_code=400, detail="positive_prompt is required.")
    if not preview_image_path:
        raise HTTPException(status_code=400, detail="preview_image_path is required.")

    preview_path = _resolve_project_file(preview_image_path)
    if not preview_path.exists() or not preview_path.is_file():
        raise HTTPException(status_code=404, detail="Rendered preview image was not found.")
    preview_meta_path = _asset_preview_meta_path(preview_path)
    if not preview_meta_path.exists():
        raise HTTPException(status_code=400, detail="Preview metadata is missing. Render again before saving.")
    preview_meta = json.loads(preview_meta_path.read_text(encoding="utf-8"))
    requested_negative = str(request.negative_prompt or "").strip()
    requested_fingerprint = _asset_prompt_fingerprint(positive_prompt, requested_negative)
    if str(preview_meta.get("entity_id") or "").strip() != str(entity_id or "").strip():
        raise HTTPException(status_code=400, detail="Preview does not belong to the selected entity.")
    if str(preview_meta.get("fingerprint") or "").strip() != requested_fingerprint:
        raise HTTPException(status_code=400, detail="Preview is stale for the current prompt draft. Render again before saving.")

    base_row, entity_info = _asset_render_row(entity_id)
    target_dir = render_output_dir_for_contract(f"db://book/{entity_info['book_id']}") / "images"
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    output_name = f"manual_{stamp}_{_slugify_asset_name(entity_info['entity_name'])}.png"
    final_path = (target_dir / output_name).resolve()
    shutil.copy2(preview_path, final_path)
    thumbnail_path = _ensure_runtime_thumbnail(str(final_path))

    render_row = dict(base_row)
    render_row.update(
        {
            "entity_name": entity_info["entity_name"],
            "entity_id": entity_info["entity_id"],
            "entity_type": entity_info["entity_type"],
            "positive_prompt": positive_prompt,
            "negative_prompt": requested_negative,
            "output_filename": output_name,
            "output_path": str(final_path),
            "relative_output_path": str(final_path.relative_to(ROOT)),
            "status": "rendered",
            "render_status": "rendered",
            "thumbnail_path": thumbnail_path,
            "source_evidence": "dashboard modal save",
            "details": {
                **dict(base_row.get("details") or {}),
                "saved_from_modal": True,
                "preview_image_path": str(preview_path),
            },
        }
    )
    image_bytes = final_path.read_bytes()

    with SQLITE_STORE.session_factory() as session:
        entity = session.get(SqlEntity, entity_info["entity_id"])
        if entity is None:
            raise HTTPException(status_code=404, detail="Entity not found.")

        existing_prompts = session.execute(
            select(SqlVisualPrompt).where(SqlVisualPrompt.entity_id == entity_info["entity_id"]).order_by(SqlVisualPrompt.updated_at.desc())
        ).scalars().all()
        primary_prompt = existing_prompts[0] if existing_prompts else None
        if primary_prompt is None:
            primary_prompt = SqlVisualPrompt(
                book_id=entity.book_id,
                entity_id=entity.id,
                entity_name=entity.canonical_name,
                entity_type=entity.entity_type,
            )
            session.add(primary_prompt)
            session.flush()
        primary_prompt.entity_name = entity_info["entity_name"]
        primary_prompt.entity_type = entity_info["entity_type"] or primary_prompt.entity_type
        primary_prompt.prompt_type = str(base_row.get("prompt_type") or primary_prompt.prompt_type or f"{entity.entity_type}_baseline").strip() or None
        primary_prompt.visual_bucket = str(base_row.get("visual_bucket") or primary_prompt.visual_bucket or "baseline").strip() or None
        primary_prompt.positive_prompt = positive_prompt
        primary_prompt.negative_prompt = requested_negative
        primary_prompt.source_evidence = "dashboard modal save"
        primary_prompt.confidence = str(base_row.get("confidence") or primary_prompt.confidence or "manual").strip() or None
        primary_prompt.book_index = base_row.get("book_index")
        primary_prompt.chapter_index = base_row.get("chapter_index")
        primary_prompt.scene_index = base_row.get("scene_index")
        primary_prompt.details_json = {
            **dict(base_row.get("details") or {}),
            "saved_from_modal": True,
            "preview_image_path": str(preview_path),
        }
        primary_prompt.metadata_json = {"source": "dashboard_modal_edit", "created_from_dashboard": True, "updated_at": utc_now()}
        session.flush()

        render_row["prompt_id"] = primary_prompt.id

        existing_images = session.execute(
            select(SqlGeneratedImage).where(SqlGeneratedImage.entity_id == entity_info["entity_id"]).order_by(SqlGeneratedImage.updated_at.desc())
        ).scalars().all()
        primary_image = existing_images[0] if existing_images else None
        if primary_image is None:
            primary_image = SqlGeneratedImage(
                book_id=entity.book_id,
                entity_id=entity.id,
                entity_name=entity.canonical_name,
                entity_type=entity.entity_type,
            )
            session.add(primary_image)
            session.flush()
        primary_image.prompt_id = primary_prompt.id
        primary_image.entity_name = entity_info["entity_name"]
        primary_image.entity_type = entity_info["entity_type"] or primary_image.entity_type
        primary_image.output_path = str(final_path)
        primary_image.thumbnail_path = thumbnail_path or None
        primary_image.mime_type = "image/png" if str(final_path).lower().endswith(".png") else primary_image.mime_type
        primary_image.image_bytes = image_bytes
        primary_image.render_status = "rendered"
        primary_image.workflow_name = "dashboard/manual-save"
        primary_image.manifest_json = render_row

        primary_prompt_id = primary_prompt.id
        primary_image_id = primary_image.id
        extra_image_ids = [row.id for row in existing_images[1:] if row.id != primary_image_id]
        if extra_image_ids:
            session.execute(delete(SqlGeneratedImage).where(SqlGeneratedImage.id.in_(extra_image_ids)))
        extra_prompt_ids = [row.id for row in existing_prompts[1:] if row.id != primary_prompt_id]
        if extra_prompt_ids:
            session.execute(delete(SqlVisualPrompt).where(SqlVisualPrompt.id.in_(extra_prompt_ids)))

        entity.baseline_visual_prompt = positive_prompt
        entity.generated_image_path = str(final_path)
        entity.generated_thumbnail_path = thumbnail_path or ""
        entity.generated_image_bytes = image_bytes
        session.commit()

    return {
        "saved": True,
        "prompt_id": render_row["prompt_id"],
        "image_path": str(final_path),
        "thumbnail_path": thumbnail_path,
        "asset": runtime_asset_entity(entity_info["entity_id"]),
    }


@app.post("/runtime/assets/render-batch")
def runtime_render_batch(request: RenderBatchRequest) -> dict[str, Any]:
    normalized_entity_ids = [str(item or "").strip() for item in request.entity_ids if str(item or "").strip()]
    if normalized_entity_ids:
        with SQLITE_STORE.session_factory() as session:
            rows = session.execute(
                select(
                    SqlEntity.id.label("entity_id"),
                    SqlEntity.book_id.label("book_id"),
                    SqlEntity.entity_type.label("entity_type"),
                    SqlBook.book_index.label("book_index"),
                )
                .join(SqlBook, SqlEntity.book_id == SqlBook.id)
                .where(SqlEntity.id.in_(normalized_entity_ids))
            ).mappings().all()
        row_map = {
            str(row.get("entity_id") or "").strip(): {
                "book_id": str(row.get("book_id") or "").strip(),
                "entity_type": str(row.get("entity_type") or "").strip(),
                "book_index": int(row.get("book_index") or 0),
            }
            for row in rows
            if str(row.get("entity_id") or "").strip() and str(row.get("book_id") or "").strip()
        }
        missing_ids = [entity_id for entity_id in normalized_entity_ids if entity_id not in row_map]
        if missing_ids:
            raise HTTPException(status_code=404, detail=f"Some selected entities were not found: {', '.join(missing_ids[:6])}")

        grouped: dict[str, dict[str, Any]] = {}
        for entity_id in normalized_entity_ids:
            row = row_map[entity_id]
            book_id = row["book_id"]
            grouped.setdefault(
                book_id,
                {
                    "book_ref": f"db://book/{book_id}",
                    "book_index": row["book_index"],
                    "entity_ids": [],
                    "entity_types": [],
                },
            )
            grouped[book_id]["entity_ids"].append(entity_id)
            entity_type = row["entity_type"]
            if entity_type and entity_type not in grouped[book_id]["entity_types"]:
                grouped[book_id]["entity_types"].append(entity_type)

        entity_groups = sorted(grouped.values(), key=lambda item: int(item.get("book_index") or 0))
        job_id = f"entity_render_{datetime.now().strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
        payload = {
            "id": job_id,
            "type": "render-selected-assets",
            "status": "queued",
            "created_at": utc_now(),
            "command": f"selected-asset-render:{len(normalized_entity_ids)}",
            "request": {
                "entity_ids": normalized_entity_ids,
                "entity_groups": entity_groups,
                "overwrite": request.overwrite,
                "limit": request.limit,
                "entity_types": request.entity_types or ["character", "creature", "object", "location"],
            },
        }
        save_job(payload)
        thread = threading.Thread(
            target=run_selected_entity_render_job,
            args=(job_id, entity_groups),
            kwargs={
                "overwrite": request.overwrite,
                "limit": request.limit,
                "fallback_entity_types": request.entity_types or ["character", "creature", "object", "location"],
            },
            daemon=True,
        )
        thread.start()
        return load_job(job_id)

    if request.series_id:
        return start_series_character_render(
            SeriesCharacterRenderRequest(
                series_id=request.series_id,
                overwrite=request.overwrite,
                limit_per_book=request.limit,
                entity_types=request.entity_types or ["character", "creature", "object", "location"],
            )
        )
    if request.book_ref:
        return start_character_render(
            CharacterRenderRequest(
                contract_path=request.book_ref,
                limit=request.limit,
                overwrite=request.overwrite,
                entity_types=request.entity_types or ["character", "creature", "object", "location"],
                entity_ids=normalized_entity_ids,
            )
        )
    raise HTTPException(status_code=400, detail="book_ref or series_id is required.")


@app.post("/runtime/assets/images/{image_id}/preferred")
def runtime_mark_preferred_image(image_id: str) -> dict[str, Any]:
    with SQLITE_STORE.session_factory() as session:
        image = session.get(SqlGeneratedImage, image_id)
        if image is None:
            raise HTTPException(status_code=404, detail="Generated image not found.")
        entity = session.get(SqlEntity, image.entity_id) if image.entity_id else None
        if entity is None:
            raise HTTPException(status_code=400, detail="Image is not linked to an entity.")
        entity.generated_image_path = image.output_path
        entity.generated_image_bytes = image.image_bytes
        session.commit()
    return {"image_id": image_id, "entity_id": entity.id, "preferred": True}


@app.get("/runtime/jobs")
def get_jobs() -> dict[str, Any]:
    return {"jobs": list_jobs()}


@app.get("/api/runs")
def api_runs() -> list[dict[str, Any]]:
    return scan_artifacts().get("runs") or []


@app.get("/runtime/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    return load_job(job_id)


@app.post("/runtime/providers/ollama")
def save_ollama_provider(config: OllamaProviderConfig) -> dict[str, Any]:
    return {"ollama": merge_and_save_ollama_accounts(config)}


@app.post("/runtime/providers/general-compute")
def save_general_compute_provider(config: GeneralComputeProviderConfig) -> dict[str, Any]:
    return {"general_compute": merge_and_save_general_compute_accounts(config)}


@app.post("/runtime/providers/codex")
def save_codex_provider(config: CodexProviderConfig) -> dict[str, Any]:
    return {"codex": merge_and_save_codex_accounts(config)}


@app.post("/runtime/providers/tts-modal")
def save_tts_modal_provider_route(config: TTSModalProviderConfig) -> dict[str, Any]:
    return {"tts_modal": save_tts_modal_provider(config)}


@app.get("/runtime/inference/providers/{provider_name}")
def get_inference_provider(provider_name: str) -> dict[str, Any]:
    return {"provider": read_inference_provider_config(provider_name, store=SQLITE_STORE, mask=True)}


@app.post("/runtime/inference/providers/{provider_name}")
def save_inference_provider_route(provider_name: str, config: InferenceProviderConfig) -> dict[str, Any]:
    payload = {
        "provider_name": provider_name,
        "app_name": config.app_name,
        "api_url": config.api_url,
        "health_url": config.health_url,
        "ui_url": config.ui_url,
        "request_timeout_seconds": config.request_timeout_seconds,
        "default_voice": config.default_voice,
        "default_lang_code": config.default_lang_code,
        "default_sample_rate": config.default_sample_rate,
        "default_audio_format": config.default_audio_format,
        "default_normalize_audio": config.default_normalize_audio,
        "default_trim_silence": config.default_trim_silence,
        "default_sentence_pause_ms": config.default_sentence_pause_ms,
        "model_name": config.model_name,
        "accounts": [
            {
                "label": account.label,
                "token_id": account.token_id,
                "token_secret": account.token_secret,
                "app_name_override": account.app_name_override,
                "metadata": account.metadata,
            }
            for account in config.accounts
        ],
    }
    saved = save_inference_provider_config(provider_name, payload, store=SQLITE_STORE)
    capability = str(saved.get("capability") or "").strip().lower()
    if capability in {SPEECH_CAPABILITY, IMAGE_CAPABILITY, COREF_CAPABILITY}:
        save_inference_selection(capability, str(saved.get("provider_name") or provider_name), store=SQLITE_STORE)
    return {"provider": saved}


@app.get("/runtime/inference/capabilities/{capability}")
def get_inference_selection_route(capability: str) -> dict[str, Any]:
    return {"selection": read_inference_selection(capability, store=SQLITE_STORE)}


@app.post("/runtime/inference/capabilities/{capability}")
def save_inference_selection_route(capability: str, config: InferenceSelectionConfig) -> dict[str, Any]:
    return {"selection": save_inference_selection(capability, config.provider_name, store=SQLITE_STORE)}


@app.post("/runtime/inference/providers/{provider_name}/smoke")
def run_inference_provider_smoke_route(provider_name: str) -> dict[str, Any]:
    capability = provider_capability(provider_name)
    return {"smoke": run_provider_smoke(capability=capability, provider_name=provider_name, store=SQLITE_STORE)}


@app.get("/runtime/inference/status")
def get_inference_statuses(refresh: bool = False) -> dict[str, Any]:
    payload = refresh_provider_statuses_service(store=SQLITE_STORE) if refresh else read_latest_inference_status_payload(store=SQLITE_STORE)
    return {
        "providers": payload.get("providers") or {},
        "selections": payload.get("selections") or {},
        "refreshed_at": str(payload.get("refreshed_at") or utc_now()),
    }


@app.get("/runtime/providers/status")
def get_provider_statuses(refresh: bool = False) -> dict[str, Any]:
    if refresh:
        payload = refresh_provider_statuses_service(store=SQLITE_STORE)
    else:
        payload = read_latest_provider_status_payload(store=SQLITE_STORE)
    providers = dict(payload.get("providers") or {})
    providers[LEGACY_TTS_MODAL_PROVIDER] = _tts_modal_status_payload(refresh=refresh)
    return {
        "providers": providers,
        "refreshed_at": str(payload.get("refreshed_at") or utc_now()),
    }


@app.get("/runtime/file")
def runtime_file(path: str):
    target = (ROOT / path).resolve()
    if not str(target).lower().startswith(str(ROOT).lower()):
        raise HTTPException(status_code=400, detail="File path must stay inside the project.")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    media_type = None
    lower_name = target.name.lower()
    if lower_name.endswith(".json"):
        media_type = "application/json"
    elif lower_name.endswith(".md"):
        media_type = "text/markdown; charset=utf-8"
    return FileResponse(target, filename=target.name, media_type=media_type)


def _active_dist_dir() -> Path:
    return PRO_DIST_DIR


ACTIVE_DIST_DIR = _active_dist_dir()
if (ACTIVE_DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=ACTIVE_DIST_DIR / "assets"), name="assets")


@app.get("/{full_path:path}")
def serve_dashboard(full_path: str = ""):
    dist_dir = _active_dist_dir()
    target = dist_dir / full_path
    if full_path and target.exists() and target.is_file():
        return FileResponse(target)
    index = dist_dir / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"status": "dashboard build missing", "hint": "Run npm run build in apps/dashboard_pro first."}


def main() -> None:
    ensure_dirs()
    host = os.environ.get("SAGA_DASHBOARD_HOST", "127.0.0.1")
    port = int(os.environ.get("SAGA_DASHBOARD_PORT", "8675"))
    log_level = os.environ.get("SAGA_DASHBOARD_LOG_LEVEL", "info")
    url = f"http://{host}:{port}"
    if os.environ.get("SAGA_DASHBOARD_NO_BROWSER") != "1":
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=port, log_level=log_level)


if __name__ == "__main__":
    main()

