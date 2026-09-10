# Model and Provider Manifest

This manifest records externally required models/providers without storing credentials or model weights.

## Active production dependencies

| Area | Provider/model identity | Status | Required configuration |
| --- | --- | --- | --- |
| Persistence | Supabase Postgres, pgvector, Supabase Storage | Active | `SAGA_SUPABASE_*` or component DB env; service-role key server-side only |
| Execution/orchestration | PostgreSQL-backed queues and leases | Active | Supabase/Postgres runtime configuration |
| Identity resolution | Modal XCore/LitBank integration | Active according to docs; live-gated | persisted Modal provider config or `SAGA_MODAL_TOKENS_JSON` for provisioning |
| Visual generation | Modal/ComfyUI provider through `integrations/comfyui` | Active according to docs; live-gated | persisted `modal_comfyui`, Modal token roster, Hugging Face/Civitai tokens where model prefetch requires them |
| Audiobook TTS | Modal Kokoro TTS | Active according to docs; live-gated | persisted `modal_kokoro_tts`, Modal token roster |
| Audio transcription QA | Mistral Voxtral, documented as `voxtral-mini-latest` | Active according to docs; live-gated | `MISTRAL_API_KEY` |
| Visual semantic QA | Mistral vision profiles, including `mistral-small-2603` and `mistral-medium-2604` | Active according to docs; live-gated | `MISTRAL_API_KEY` and versioned cost rates |

## Evaluation-only or local candidates

| Area | Provider/model identity | Status | Notes |
| --- | --- | --- | --- |
| Local reasoning | Ollama local/remote routes, including local candidate records such as `gemma4:31b-cloud` | Evaluation/local | GitHub-hosted Actions cannot rely on developer-local Ollama. Use mocked/unit gates for normal CI and a self-hosted/live workflow only when explicitly configured. |
| General compute reasoning | `deepseek-v3.1` through general compute configuration | Candidate/evaluation | Requires provider config and cost/latency evidence before production claims. |
| Legacy Neo4j retrieval | Neo4j local deployment files | Historical/local | Current storage docs identify Supabase/Postgres/pgvector as production persistence. |

## Studio / image-video surface

The local checkout contains untracked Studio/generation manifests for Z-Image, Qwen image edit, FLUX Klein, LTX video, and ReActor face swap. Current S.A.G.A. recovery treats this as unresolved or separately owned work, not an active S.A.G.A. core dependency to migrate automatically.

If the surface remains in S.A.G.A., record exact model URLs/revisions, workflow hashes, provider volumes, and storage ownership in this manifest. If the surface is externalized to RenderLab, keep only a historical note here.

## Model weight policy

- Do not commit checkpoints, LoRAs, GGUFs, ONNX files, PyTorch weights, or downloaded model caches.
- CI/live workflows should download models from authoritative upstream URLs into provider-local caches or volumes.
- Every adopted model needs source URL, version/revision, expected destination, checksum when available, license/use constraints, and live gate that proves it loads.
