# Modal xcore_litbank Integration

This folder vendors a project-local Modal deployment for `sapienzanlp/xcore-litbank` using the same loose-coupled service pattern already used for the project's other Modal workloads.

## What this gives you

- `modal_app.py`: a dedicated Modal GPU app exposing:
  - `POST` API for coreference analysis
  - `GET` health endpoint
  - local entrypoint for one-shot file-based runs
- `workspace_client.py`: resolves or deploys the Modal app for a specific token
- `client.py`: HTTP client for the deployed endpoint
- `pool_manager.py`: token-aware endpoint failover and sticky live endpoint reuse
- `token_pool.py`: local rotation state using the shared Modal token file already used by the project

## Input contract

The API accepts either:

- `text`: one full text string
- `chapters`: a list of chapter objects with `chapter_index`, `chapter_title`, and `content`

Chunking is enabled by default because that is how the winning benchmark path was run on complete books.

## Local prerequisites

From the project root:

```powershell
venv\Scripts\python.exe -m pip install modal==1.4.2
```

Modal account pools are resolved from the shared DB-backed inference provider config, not from token files in this folder.

## Deploy

```powershell
venv\Scripts\modal.exe deploy integrations\xcore_litbank\modal_app.py
```

If you want token-scoped deployment, use `workspace_client.py` or the existing token-pool command style already used elsewhere in the repo.

## One-shot remote run

```powershell
venv\Scripts\modal.exe run integrations\xcore_litbank\modal_app.py --input-path analysis_outputs\coref_benchmark\fullbook_runs\20260623_215725\samples\acotar_full.txt
```

## Programmatic usage

```python
from integrations.xcore_litbank.pool_manager import ModalXCorePoolManager

manager = ModalXCorePoolManager()
payload = manager.analyze(text="Feyre watched the wolf in the snow.")
print(payload["clusters"][:5])
```

## Scaling intent

This service is intentionally isolated from the rest of SAGA:

- independent deployment lifecycle
- independent GPU scaling boundary
- clean HTTP contract
- no direct dependency on the main app runtime state
