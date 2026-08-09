# Runtime Secrets

The active architecture separates secret ownership by runtime.

## Ownership

- `persistence runtime`
  - owns consumption of Supabase/Postgres connection and storage credentials
  - production source: environment or deployment secret manager
  - not stored in provider-config rows
- `reasoning runtime`
  - owns Ollama account-pool credentials and General Compute account-pool credentials
  - Ollama and General Compute pool records may be stored in persistence provider configs
  - Mistral and Gemini remain environment-owned runtime secrets
- `modal/general compute runtime`
  - owns Modal account-pool credentials and ComfyUI Hugging Face token
  - Modal pool records may be stored in persistence provider configs
- `agent runtime`
  - does not own secrets
  - consumes runtime surfaces only

## Active Clean Paths

- Ollama provider config
  - persistence provider config name: `ollama`
  - loader: `packages.reasoning_runtime.provider_config.apply_persistence_provider_configs(...)`
- General Compute provider config
  - persistence provider config name: `general_compute`
  - loader: `packages.reasoning_runtime.provider_config.apply_persistence_provider_configs(...)`
- Modal ComfyUI provider config
  - persistence provider config name: `modal_comfyui`
  - loader: `packages.modal_runtime.provider_config.load_modal_provider_secret_config(...)`
- Supabase runtime credentials
  - environment-only production path through `packages.persistence_runtime`

## Secret Re-Homing

One-time re-homing into the active architecture is handled by:

- [scripts/rehome_runtime_secrets.py](B:\Documents\PyCharm\graduationProject\scripts\rehome_runtime_secrets.py)

That script imports only from explicit local secret-bearing files and stores the resulting runtime-owned config in the persistence runtime. It does not print secret values.

## Dashboard API Behavior

The dashboard runtime API now exposes only sanitized provider summaries:

- presence flags such as `has_hf_token`
- account labels
- secret-presence flags such as `has_token_secret`

It must never return:

- raw Modal token ids/secrets
- raw Hugging Face tokens
- raw database URLs with credentials
- raw cloud API keys

## What Must Never Be Used In Production

- implicit localhost secret assumptions
- ad hoc secret values in frontend code
- direct runtime dependence on `SAGA_MODAL_TOKENS_JSON`, `MODAL_TOKEN_ID`, or `MODAL_TOKEN_SECRET` unless `SAGA_MODAL_ALLOW_ENV_FALLBACK=1` is intentionally enabled for explicit fallback/debug scenarios
- direct agent ownership of provider credentials

## Validation

- non-live tests prove sanitized API responses and persistence-backed reasoning/modal secret loading
- live validators:
  - [tests/test_real_supabase_runtime.py](B:\Documents\PyCharm\graduationProject\tests\test_real_supabase_runtime.py)
  - [tests/test_real_runtime_stack.py](B:\Documents\PyCharm\graduationProject\tests\test_real_runtime_stack.py)

The runtime-stack validator now expects the Ollama provider config to already be stored in the persistence runtime and uses the clean path instead of relying on direct reasoning env secrets.
