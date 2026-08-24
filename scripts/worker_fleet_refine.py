from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    content = read(path)
    if old not in content:
        raise SystemExit(f"Expected anchor not found in {path}: {old[:160]!r}")
    write(path, content.replace(old, new, 1))


# Once an ecosystem has a real fleet, exclusions must never fall through to modal-01.
replace_once(
    "apps/studio/api/_worker-registry.js",
    """  const configured = listConfiguredWorkers()\n    .filter((worker) => worker.enabled && worker.ecosystem === ecosystem && !excluded.has(worker.id))\n    .sort((a, b) => {\n      const role = (a.role === 'primary' ? 0 : 1) - (b.role === 'primary' ? 0 : 1);\n      return role || a.order - b.order || a.id.localeCompare(b.id);\n    });\n  if (configured.length) return configured;\n  const legacy = legacyWorker(workflow);\n  return legacy && !excluded.has(legacy.id) ? [legacy] : [];\n""",
    """  const fleet = listConfiguredWorkers()\n    .filter((worker) => worker.enabled && worker.ecosystem === ecosystem);\n  const configured = fleet\n    .filter((worker) => !excluded.has(worker.id))\n    .sort((a, b) => {\n      const role = (a.role === 'primary' ? 0 : 1) - (b.role === 'primary' ? 0 : 1);\n      return role || a.order - b.order || a.id.localeCompare(b.id);\n    });\n  if (fleet.length) return configured;\n  const legacy = legacyWorker(workflow);\n  return legacy && !excluded.has(legacy.id) ? [legacy] : [];\n""",
)

# A generic 429 is safe to try on another worker during submit, but not safe to
# duplicate an already-accepted generation during poll-time reassignment.
replace_once(
    "apps/studio/api/_worker-registry.js",
    """  if (Number(status) === 429) {\n    return { retryable: true, safeToReassign: true, kind: 'unavailable', code: 'WORKER_UNAVAILABLE' };\n  }\n""",
    """  if (Number(status) === 429) {\n    return { retryable: true, safeToReassign: false, kind: 'unavailable', code: 'WORKER_UNAVAILABLE' };\n  }\n""",
)

# Flux needs the same deployment-time secret injection pattern already used by
# LTX so clean workers can prefetch gated/private model assets without baking
# credentials into source or the generated public registry.
flux_path = "integrations/comfyui/flux2_klein_app.py"
flux = read(flux_path)
if "RUNTIME_SECRETS = [modal.Secret.from_dict" not in flux:
    anchor = "worker_state = modal.Dict.from_name(STATE_DICT_NAME, create_if_missing=True)\n\n"
    if anchor not in flux:
        raise SystemExit("Flux worker-state anchor not found")
    secret_block = """worker_state = modal.Dict.from_name(STATE_DICT_NAME, create_if_missing=True)\n\n_runtime_secret_values: dict[str, str] = {}\nfor _name in (\"HF_TOKEN\", \"CIVITAI_API_TOKEN\"):\n    _value = str(os.environ.get(_name) or \"\").strip()\n    if _value:\n        _runtime_secret_values[_name] = _value\nRUNTIME_SECRETS = [modal.Secret.from_dict(_runtime_secret_values)] if _runtime_secret_values else []\n\n"""
    flux = flux.replace(anchor, secret_block, 1)

prefetch_old = "@app.function(image=image, timeout=FUNCTION_TIMEOUT_SECONDS, volumes={CACHE_DIR: cache_volume})\ndef prefetch_klein"
prefetch_new = "@app.function(image=image, timeout=FUNCTION_TIMEOUT_SECONDS, volumes={CACHE_DIR: cache_volume}, secrets=RUNTIME_SECRETS)\ndef prefetch_klein"
if prefetch_old in flux:
    flux = flux.replace(prefetch_old, prefetch_new, 1)
elif prefetch_new not in flux:
    raise SystemExit("Flux prefetch decorator anchor not found")

cls_old = """    min_containers=WORKER_MIN_CONTAINERS,\n    max_containers=WORKER_MAX_CONTAINERS,\n    volumes={CACHE_DIR: cache_volume},\n)\n@modal.concurrent(max_inputs=1)\nclass Flux2KleinWorker:\n"""
cls_new = """    min_containers=WORKER_MIN_CONTAINERS,\n    max_containers=WORKER_MAX_CONTAINERS,\n    volumes={CACHE_DIR: cache_volume},\n    secrets=RUNTIME_SECRETS,\n)\n@modal.concurrent(max_inputs=1)\nclass Flux2KleinWorker:\n"""
if cls_old in flux:
    flux = flux.replace(cls_old, cls_new, 1)
elif cls_new not in flux:
    raise SystemExit("Flux class decorator anchor not found")
write(flux_path, flux)

# Clean LTX provisioning verifies the REDGraft checkpoint hash; Flux keeps its
# existing force_checkpoint=False behavior.
fleet_path = "scripts/modal_worker_fleet.py"
fleet = read(fleet_path)
old = """    code = (\n        \"import modal, json; \"\n        f\"fn=modal.Function.from_name({ecosystem['runtimeApp']!r}, {prefetch!r}); \"\n        \"result=fn.remote(False); print(json.dumps({'ready': bool(result.get('ready')), 'model': result.get('model')}))\"\n    )\n"""
new = """    prefetch_arg = \"True\" if ecosystem_id == \"ltx25-redgraft\" else \"False\"\n    code = (\n        \"import modal, json; \"\n        f\"fn=modal.Function.from_name({ecosystem['runtimeApp']!r}, {prefetch!r}); \"\n        f\"result=fn.remote({prefetch_arg}); print(json.dumps({{'ready': bool(result.get('ready')), 'model': result.get('model')}}))\"\n    )\n"""
if old not in fleet:
    raise SystemExit("Prefetch invocation anchor not found")
write(fleet_path, fleet.replace(old, new, 1))

# Extend the deterministic architecture contract with the two safety refinements.
contract_path = "apps/studio/scripts/check-worker-registry-contract.mjs"
contract = read(contract_path)
marker = "const resultSource = await readFile(new URL('../api/generate/result.js', import.meta.url), 'utf8');"
addition = """assert.equal(classifyWorkerFailure({ status: 429, body: { detail: 'rate limited' } }).safeToReassign, false, 'Generic 429 must not duplicate an accepted generation during poll-time failover');\n\nprocess.env.SAGA_MODAL_WORKER_REGISTRY_JSON = JSON.stringify({ workers: [\n  { id: 'only-primary', ecosystem: 'flux2-klein-9b', gatewayUrl: 'https://only.example', role: 'primary', enabled: true },\n] });\nassert.deepEqual(workersForWorkflow(flux, { excludeWorkerIds: ['only-primary'] }), [], 'Configured fleets must not fall through to the legacy modal-01 worker after exclusions');\n\nconst fluxRuntimeSource = await readFile(new URL('../../../integrations/comfyui/flux2_klein_app.py', import.meta.url), 'utf8');\nassert.ok(fluxRuntimeSource.includes('RUNTIME_SECRETS = [modal.Secret.from_dict'), 'Flux worker must inject deployment-time model credentials as Modal secrets');\nassert.ok(fluxRuntimeSource.includes('secrets=RUNTIME_SECRETS'), 'Flux prefetch/runtime must receive deployment-time model credentials');\n\n"""
if addition.strip() not in contract:
    if marker not in contract:
        raise SystemExit("Worker contract insertion marker not found")
    contract = contract.replace(marker, addition + marker, 1)
write(contract_path, contract)

print("Worker fleet safety refinement applied.")
