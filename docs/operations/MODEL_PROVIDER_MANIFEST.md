# Model and Provider Manifest

This manifest records externally required models/providers without storing credentials or model weights.

## Active production dependencies

| Area | Provider/model identity | Status | Required configuration |
| --- | --- | --- | --- |
| Persistence | Supabase Postgres, pgvector, Supabase Storage | Active | `SAGA_SUPABASE_*` or component DB env; service-role key server-side only |
| Execution/orchestration | PostgreSQL-backed queues and leases | Active | Supabase/Postgres runtime configuration |
| Identity resolution | Modal XCore/LitBank integration | Active according to docs; live-gated | persisted Modal provider config or `SAGA_MODAL_TOKENS_JSON` for provisioning |
| Visual generation | S.A.G.A. visual runtime with Modal/ComfyUI and Qwen provider integrations | Active according to docs; live-gated | persisted provider config, `config/modal-worker-ecosystems.json`, `config/modal-worker-registry.json`, Modal token roster, Hugging Face/Civitai tokens where model prefetch requires them |
| Audiobook TTS | Modal Kokoro TTS | Active according to docs; live-gated | persisted `modal_kokoro_tts`, Modal token roster |
| Audio transcription QA | Mistral Voxtral, documented as `voxtral-mini-latest` | Active according to docs; live-gated | `MISTRAL_API_KEY` |
| Visual semantic QA | Mistral vision profiles, including `mistral-small-2603` and `mistral-medium-2604` | Active according to docs; live-gated | `MISTRAL_API_KEY` and versioned cost rates |

## Retained visual provider ecosystems

The generic `apps/studio/` product surface is retired and its successor is the separate RenderLab project. The following provider/model resources remain in S.A.G.A. because they can serve S.A.G.A.'s stage-7 narrative-to-media pipeline:

| Ecosystem | Provider/model identity | Runtime ownership | Current routing ownership |
| --- | --- | --- | --- |
| `flux2-klein-9b` | FLUX.2 Klein 9B / DarkBeast workflow | `integrations/comfyui` | `config/modal-worker-registry.json` |
| `qwen-image-edit-2511` | Qwen Image Edit 2511 with pinned Civitai transformer + Lightning profile | `integrations/qwen` | `config/modal-worker-registry.json` |
| `ltx25-redgraft` | REDGraft LTX 2.5 / Sulphur2 workflow | `integrations/comfyui` | `config/modal-worker-registry.json` |

These entries are provider/runtime capabilities, not authorization to recreate RenderLab's generic product UI, gallery, jobs, or media-library behavior inside S.A.G.A.

Public worker endpoints/account labels are non-secret operational metadata. Credentials remain in secret stores. Live readiness claims require current workflow evidence bound to an exact commit/deployment state.

## Evaluation-only or local candidates

| Area | Provider/model identity | Status | Notes |
| --- | --- | --- | --- |
| Local reasoning | Ollama local/remote routes, including local candidate records such as `gemma4:31b-cloud` | Evaluation/local | GitHub-hosted Actions cannot rely on developer-local Ollama. Use mocked/unit gates for normal CI and a self-hosted/live workflow only when explicitly configured. |
| General compute reasoning | `deepseek-v3.1` through general compute configuration | Candidate/evaluation | Requires provider config and cost/latency evidence before production claims. |
| Legacy Neo4j retrieval | Neo4j local deployment files | Historical/local | Current storage docs identify Supabase/Postgres/pgvector as production persistence. |
| ReActor / generic face-swap product behavior | historical Studio/RenderLab-side experimentation | Not active S.A.G.A. dependency | Do not migrate into S.A.G.A. without a new evidence-backed use case and explicit adoption decision. |
| Z-Image and other generic image-product presets not referenced by the active S.A.G.A. visual runtime | historical Studio/RenderLab-side experimentation | Not active S.A.G.A. dependency | Evaluate separately if S.A.G.A. later needs them. |

## Legacy cloud-resource note

Removing Studio code and migration definitions from this repository does not delete already-created remote resources. Any Studio-era Supabase tables, R2 buckets/objects, Modal caches/deployments, or credentials that are no longer consumed by S.A.G.A. must be audited and migrated/decommissioned in a separate explicit operation. RenderLab resource ownership must be confirmed from the RenderLab repository before moving anything.

## Model weight policy

- Do not commit checkpoints, LoRAs, GGUFs, ONNX files, PyTorch weights, or downloaded model caches.
- CI/live workflows should download models from authoritative upstream URLs into provider-local caches or volumes.
- Every adopted model needs source URL, version/revision, expected destination, checksum when available, license/use constraints, and live gate that proves it loads.
