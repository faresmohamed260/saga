from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

import modal

APP_NAME = "saga-phase2-xcore-provider"
MODEL_REPO = "sapienzanlp/xcore-litbank"
MODEL_REVISION = os.environ.get("SAGA_XCORE_MODEL_REVISION", "main").strip() or "main"
XCORE_SOURCE_REVISION = "9a5713b210abaaa6ded158966b200740ea1bfbfc"
MODEL_DIR = "/cache/xcore-litbank"
CACHE_DIR = "/cache"
PROVIDER_NAME = "modal_xcore_litbank"
ADAPTER_REVISION = "saga-xcore-spacy-adapter-v1"
MODAL_VERSION = "1.4.2"

cache = modal.Volume.from_name("saga-phase2-xcore-cache", create_if_missing=True)
provider_secret = modal.Secret.from_name("saga-phase2-xcore-provider")

image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.4.1-runtime-ubuntu22.04",
        add_python="3.11",
    )
    .entrypoint([])
    .apt_install("git", "libgomp1")
    .uv_pip_install(
        f"modal=={MODAL_VERSION}",
        "fastapi[standard]==0.121.0",
        "huggingface-hub==0.36.0",
        "spacy==3.7.5",
        f"git+https://github.com/SapienzaNLP/xcore.git@{XCORE_SOURCE_REVISION}",
        "torch==2.6.0",
        extra_index_url="https://download.pytorch.org/whl/cu124",
        extra_options="--index-strategy unsafe-best-match",
    )
    .run_commands(
        "python -m pip install --no-deps https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl"
    )
    .env(
        {
            "HF_HOME": CACHE_DIR,
            "TRANSFORMERS_CACHE": CACHE_DIR,
            "SAGA_XCORE_MODEL_REVISION": MODEL_REVISION,
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        }
    )
)

app = modal.App(APP_NAME, image=image)

NON_PERSON_LABELS = {
    "FAC",
    "GPE",
    "LOC",
    "ORG",
    "PRODUCT",
    "EVENT",
    "WORK_OF_ART",
    "LAW",
    "LANGUAGE",
    "NORP",
}
TRAILING_BAD_POS = {"ADP", "CCONJ", "SCONJ"}


def _section_locator(sections: list[dict[str, Any]], start: int, end: int) -> str | None:
    for section in sections:
        try:
            left = int(section["start_offset"])
            right = int(section["end_offset"])
        except (KeyError, TypeError, ValueError):
            continue
        if left <= start and end <= right:
            locator = section.get("source_locator")
            return str(locator) if locator is not None else None
    return None


def _overlapping_label(doc: Any, start: int, end: int) -> str | None:
    for ent in doc.ents:
        if ent.start_char < end and start < ent.end_char:
            return str(ent.label_)
    return None


def _mention_kind(tokens: list[Any]) -> str:
    if tokens and all(token.pos_ == "PRON" for token in tokens):
        return "pronoun"
    if any(token.pos_ == "PROPN" for token in tokens):
        return "proper_name"
    return "nominal"


def _boundary_quality(tokens: list[Any]) -> str:
    if not tokens:
        return "malformed"
    if tokens[-1].pos_ in TRAILING_BAD_POS:
        return "malformed"
    return "clean"


def _load_runtime() -> tuple[Any, Any, str]:
    from huggingface_hub import snapshot_download
    import spacy
    from xcore import xCoRe

    local_path = snapshot_download(
        repo_id=MODEL_REPO,
        revision=MODEL_REVISION,
        local_dir=MODEL_DIR,
    )
    cache.commit()
    nlp = spacy.load("en_core_web_sm")
    nlp.max_length = 8_000_000
    model = xCoRe(hf_name_or_path=local_path, device="cuda:0")
    return model, nlp, local_path


@app.function(
    image=image,
    gpu="A10G",
    timeout=1800,
    scaledown_window=300,
    max_containers=1,
    volumes={CACHE_DIR: cache},
    secrets=[provider_secret],
)
@modal.asgi_app()
def web():
    from fastapi import FastAPI, HTTPException, Request

    api = FastAPI(title="S.A.G.A. Phase 2 xCoRe Evidence Provider", version="1.0.0")
    state: dict[str, Any] = {"model": None, "nlp": None, "local_path": None}

    def runtime() -> tuple[Any, Any, str]:
        if state["model"] is None:
            model, nlp, local_path = _load_runtime()
            state.update(model=model, nlp=nlp, local_path=local_path)
        return state["model"], state["nlp"], state["local_path"]

    def authorize(request: Request) -> None:
        expected = os.environ.get("SAGA_IDENTITY_PROVIDER_TOKEN", "").strip()
        if not expected:
            raise HTTPException(status_code=503, detail="provider credential missing")
        header = request.headers.get("authorization", "")
        supplied = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else ""
        if not supplied or not hmac.compare_digest(supplied, expected):
            raise HTTPException(status_code=401, detail="unauthorized")

    @api.get("/health")
    async def health():
        return {
            "ready": True,
            "provider": PROVIDER_NAME,
            "model": MODEL_REPO,
            "model_revision": MODEL_REVISION,
            "xcore_source_revision": XCORE_SOURCE_REVISION,
            "adapter_revision": ADAPTER_REVISION,
            "license": "CC-BY-NC-SA-4.0",
            "qualification_only": True,
        }

    @api.post("/")
    async def collect(request: Request):
        authorize(request)
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="invalid payload")
        fingerprint = payload.get("normalizedInputFingerprint")
        text = payload.get("normalizedText")
        sections = payload.get("sections")
        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
            raise HTTPException(status_code=400, detail="invalid fingerprint")
        if not isinstance(text, str) or not text:
            raise HTTPException(status_code=400, detail="normalizedText is required")
        if not isinstance(sections, list):
            raise HTTPException(status_code=400, detail="sections must be a list")
        actual = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if actual != fingerprint:
            raise HTTPException(status_code=409, detail="normalized input fingerprint mismatch")

        model, nlp, _ = runtime()
        doc = nlp(text)
        input_tokens = [token.text for token in doc]
        if not input_tokens:
            return {"mentions": []}

        if len(input_tokens) > 3500:
            prediction = model.predict(input_tokens, "long", max_length=4000, singletons=True)
        else:
            prediction = model.predict(input_tokens, singletons=True)

        returned_tokens = prediction.get("tokens")
        if returned_tokens != input_tokens:
            raise HTTPException(status_code=502, detail="xcore token alignment mismatch")
        clusters = prediction.get("clusters_token_offsets")
        if not isinstance(clusters, list):
            raise HTTPException(status_code=502, detail="xcore missing clusters")

        mentions: list[dict[str, Any]] = []
        for cluster_index, cluster in enumerate(clusters):
            if not isinstance(cluster, (list, tuple)):
                continue
            prepared: list[dict[str, Any]] = []
            cluster_has_person_seed = False
            for span in cluster:
                if not isinstance(span, (list, tuple)) or len(span) != 2:
                    continue
                token_start, token_end = int(span[0]), int(span[1])
                if token_start < 0 or token_end < token_start or token_end >= len(doc):
                    continue
                span_tokens = [doc[index] for index in range(token_start, token_end + 1)]
                start = span_tokens[0].idx
                end = span_tokens[-1].idx + len(span_tokens[-1].text)
                surface = text[start:end]
                label = _overlapping_label(doc, start, end)
                kind = _mention_kind(span_tokens)
                strong_person = label == "PERSON" and kind == "proper_name"
                cluster_has_person_seed = cluster_has_person_seed or strong_person
                prepared.append(
                    {
                        "start": start,
                        "end": end,
                        "surface": surface,
                        "label": label,
                        "kind": kind,
                        "boundary": _boundary_quality(span_tokens),
                    }
                )

            cluster_id = f"xcore:{cluster_index}"
            for item in prepared:
                label = item["label"]
                kind = item["kind"]
                if label == "PERSON":
                    entity_type = "person"
                    person_evidence = "strong" if kind == "proper_name" else "supporting"
                elif label in NON_PERSON_LABELS:
                    entity_type = "non_person"
                    person_evidence = "none"
                elif cluster_has_person_seed:
                    entity_type = "person"
                    person_evidence = "supporting" if kind != "proper_name" else "weak"
                else:
                    entity_type = "unknown"
                    person_evidence = "weak" if kind == "proper_name" else "none"

                start = int(item["start"])
                end = int(item["end"])
                evidence_id = hashlib.sha256(
                    f"{fingerprint}|{cluster_id}|{start}|{end}|{item['surface']}".encode("utf-8")
                ).hexdigest()[:32]
                mentions.append(
                    {
                        "evidenceId": f"xcore:{evidence_id}",
                        "surfaceText": item["surface"],
                        "startOffset": start,
                        "endOffset": end,
                        "structuralLocator": _section_locator(sections, start, end),
                        "mentionKind": kind,
                        "entityType": entity_type,
                        "personEvidence": person_evidence,
                        "boundaryQuality": item["boundary"],
                        "providerClusterId": cluster_id,
                    }
                )

        mentions.sort(key=lambda row: (row["startOffset"], row["endOffset"], row["evidenceId"]))
        return {"mentions": mentions}

    return api
