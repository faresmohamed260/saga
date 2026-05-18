# Neo4j Deployment

SAGA uses Neo4j as the persistent narrative memory layer for the real
encode-once/decode-many workflow.

The repository ships a permanent Docker Compose deployment at
[deploy/neo4j/compose.yaml](/B:/Documents/PyCharm/graduationProject/deploy/neo4j/compose.yaml).
It is intended to be the real local or server-side deployment path, not a
temporary test harness.

## Files

- [deploy/neo4j/compose.yaml](/B:/Documents/PyCharm/graduationProject/deploy/neo4j/compose.yaml)
  Permanent Neo4j service definition with named persistent volumes.
- [deploy/neo4j/.env.example](/B:/Documents/PyCharm/graduationProject/deploy/neo4j/.env.example)
  Template for the real local secrets/config file.
- `deploy/neo4j/.env`
  Real local runtime configuration file. This file is intentionally ignored by
  git.

## First-Time Setup

1. Copy the template:

```powershell
Copy-Item deploy/neo4j/.env.example deploy/neo4j/.env
```

2. Edit `deploy/neo4j/.env` and set a real password.

3. Start Neo4j:

```powershell
docker compose --env-file deploy/neo4j/.env -f deploy/neo4j/compose.yaml up -d
```

4. Verify connectivity:

```powershell
python saga_tools.py probe-neo4j
```

Because `Neo4jIngestionService` now reads `deploy/neo4j/.env` automatically,
the CLI and services will use that configuration even if shell env vars are not
set.

## Operations

Start:

```powershell
docker compose --env-file deploy/neo4j/.env -f deploy/neo4j/compose.yaml up -d
```

Stop:

```powershell
docker compose --env-file deploy/neo4j/.env -f deploy/neo4j/compose.yaml stop
```

Restart:

```powershell
docker compose --env-file deploy/neo4j/.env -f deploy/neo4j/compose.yaml restart
```

View logs:

```powershell
docker compose --env-file deploy/neo4j/.env -f deploy/neo4j/compose.yaml logs -f
```

## Persistence Model

The deployment uses named Docker volumes:

- `saga_neo4j_data`
- `saga_neo4j_logs`

That means the graph persists across container restarts and normal upgrades.

## Production Workflow

1. Start Neo4j.
2. `python saga_tools.py register-corpus ...`
3. `python saga_tools.py encode-store ...`
4. `python saga_tools.py inspect-corpus ...`
5. `python saga_tools.py build-sequel-context-neo4j ...`
6. `python saga_tools.py generate-blueprint-neo4j ...`

This is the real persistence path for SAGA. Contract export remains available
for fallback/debugging, but Neo4j is the intended persistent store.

## Long-Running Encode Safety

`encode-store` is designed for long-running production ingest, not just quick
tests.

It now:

- plans the ingest before any heavy LLM work starts
- skips unchanged books by source hash
- encodes and persists one book at a time
- leaves already-completed books safely stored if a later book is interrupted
- writes resumable per-book checkpoints so an interrupted book can continue from
  its last completed scene on the next run
- writes persistent run artifacts to `analysis_outputs/encode_runs/<series_id>/`

For each run, SAGA writes:

- `encode.log`
- `status.json`
- `latest_status.json` at the series root
- one per-book contract JSON under `contracts/`
- resumable per-book checkpoint JSON under `resume_checkpoints/`

`status.json` is the main operational artifact for checking:

- finished books
- failed books
- skipped books
- remaining pending work
- current phase and last known progress

## Ollama Cloud Credential Rotation

If cloud-model runs hit provider rate limits, SAGA can rotate among multiple
locally configured Ollama Cloud credentials.

1. Copy the template:

```powershell
Copy-Item deploy/ollama/accounts.local.example.json deploy/ollama/accounts.local.json
```

2. Fill in real credentials in `deploy/ollama/accounts.local.json`.

Preferred production setup:

- use `api_key` entries for direct `https://ollama.com/api` access
- keep browser-signin `email` / `password` entries only as an interactive fallback

Example:

```json
{
  "active_index": 0,
  "accounts": [
    { "label": "primary-api", "api_key": "replace-me" },
    { "label": "backup-api", "api_key": "replace-me" }
  ]
}
```

That file is intentionally ignored by git. When `gpt_oss` or `deepseek` cloud
requests exhaust `429` retries, the LLM client will attempt to rotate to the
next configured API key, probe model access, and retry once with the rotated
credential. If no API key is present for an account, it falls back to the older
browser-signin flow for that entry.
