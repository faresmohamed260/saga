#!/usr/bin/env python3
"""Probe Saturn Cloud as a GPU worker backend without touching production.

The probe:
- enumerates resources and instance types available to the authenticated account;
- selects a conservative GPU candidate (A10/L4/T4 preferred);
- attempts a real Saturn Deployment exposing port 8000;
- falls back to a routed GPU Workspace only if Deployment creation is rejected;
- records state/log/route evidence and stops/deletes only resources created by the probe.

Authentication is read only from SATURN_BASE_URL and SATURN_TOKEN.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from saturn_client import SaturnConnection
from saturn_client.core import ServerOptionTypes

BASE_URL = os.environ.get("SATURN_BASE_URL", "https://app.community.saturnenterprise.io").rstrip("/")
TOKEN = os.environ.get("SATURN_TOKEN", "").strip()
OUT = Path(os.environ.get("SATURN_PROBE_OUTPUT", "/tmp/saturn-worker-probe.json"))
DEPLOYMENT_NAME = os.environ.get("SATURN_DEPLOYMENT_NAME", "saga-worker-probe")
WORKSPACE_NAME = os.environ.get("SATURN_WORKSPACE_NAME", "saga-worker-probe-workspace")
IMAGE = os.environ.get("SATURN_IMAGE", "community/saturncloud/saturn-python:2023.09.01")


def emit(data: dict[str, Any]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(data, indent=2, default=str))


def as_gpu_value(value: Any) -> float:
    if value is None or value is False:
        return 0.0
    if value is True:
        return 1.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 1.0 if str(value).strip() else 0.0


def choose_gpu(sizes: list[dict[str, Any]]) -> dict[str, Any] | None:
    gpu_sizes = [s for s in sizes if as_gpu_value(s.get("gpu")) > 0 or "gpu" in str(s.get("name", "")).lower()]
    if not gpu_sizes:
        return None
    priority = ["a10", "l4", "t4", "v100", "a100", "l40", "h100", "h200"]
    for needle in priority:
        for size in gpu_sizes:
            if needle in str(size.get("name", "")).lower():
                return size
    return gpu_sizes[0]


def state_status(resource: dict[str, Any]) -> str:
    return str((resource.get("state") or {}).get("status") or (resource.get("spec") or {}).get("status") or "unknown").lower()


def collect_urls(obj: Any) -> list[str]:
    found: list[str] = []
    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
        elif isinstance(value, str) and value.startswith(("http://", "https://")):
            found.append(value.rstrip("/"))
    walk(obj)
    return list(dict.fromkeys(found))


def http_probe(urls: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for base in urls:
        req = Request(base + "/", headers={"Authorization": f"token {TOKEN}"})
        started = time.monotonic()
        try:
            with urlopen(req, timeout=20) as response:
                sample = response.read(300).decode("utf-8", "replace")
                results.append({"url": base, "status": response.status, "seconds": round(time.monotonic() - started, 3), "sample": sample})
        except HTTPError as exc:
            results.append({"url": base, "status": exc.code, "seconds": round(time.monotonic() - started, 3), "error": str(exc)})
        except (URLError, TimeoutError, OSError) as exc:
            results.append({"url": base, "status": None, "seconds": round(time.monotonic() - started, 3), "error": str(exc)})
    return results


def wait_for(conn: SaturnConnection, resource_type: str, name: str, timeout: int = 600) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    timeline: list[dict[str, Any]] = []
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = conn.get_resource(resource_type, name)
        status = state_status(last)
        timeline.append({"elapsed_seconds": round(timeout - max(0, deadline - time.monotonic()), 1), "status": status})
        if status in {"running", "ready", "error", "failed", "stopped"}:
            return last, timeline
        time.sleep(10)
    return last, timeline


def safe_logs(conn: SaturnConnection, resource_type: str, name: str) -> str:
    try:
        resource = conn.get_resource(resource_type, name)
        resource_id = resource["state"]["id"]
        logs = conn.get_logs(resource_type, name)
        return logs[-12000:] if logs else f"No logs returned (id={resource_id})"
    except Exception as exc:  # evidence only
        return f"log collection failed: {type(exc).__name__}: {exc}"


def safe_cleanup(conn: SaturnConnection, resource_type: str, name: str, evidence: dict[str, Any]) -> None:
    cleanup: dict[str, Any] = {}
    try:
        current = conn.get_resource(resource_type, name)
        resource_id = current["state"]["id"]
        try:
            conn.stop(resource_type, resource_id)
            cleanup["stop"] = "requested"
        except Exception as exc:
            cleanup["stop"] = f"failed: {type(exc).__name__}: {exc}"
        time.sleep(2)
        try:
            code = conn.delete(resource_type, resource_id)
            cleanup["delete_status"] = code
        except Exception as exc:
            cleanup["delete"] = f"failed: {type(exc).__name__}: {exc}"
    except Exception as exc:
        cleanup["lookup"] = f"failed: {type(exc).__name__}: {exc}"
    evidence["cleanup"] = cleanup


def main() -> int:
    if not TOKEN:
        print("SATURN_TOKEN is required", file=sys.stderr)
        return 2

    conn = SaturnConnection()
    evidence: dict[str, Any] = {
        "base_url": BASE_URL,
        "probe": "saturn-gpu-worker-feasibility-v1",
        "existing_resources": [],
        "instance_types": [],
        "selected_gpu": None,
        "deployment": None,
        "workspace_fallback": None,
    }

    try:
        evidence["existing_resources"] = conn.list_resources()
        sizes = list(conn.list_options(ServerOptionTypes.SIZES))
        evidence["instance_types"] = sizes
        selected = choose_gpu(sizes)
        evidence["selected_gpu"] = selected
        emit(evidence)
        if not selected:
            evidence["outcome"] = "no_gpu_instance_types_available"
            emit(evidence)
            return 3

        instance_type = str(selected["name"])
        deployment_recipe = {
            "type": "deployment",
            "spec": {
                "name": DEPLOYMENT_NAME,
                "description": "Temporary SAGA Saturn GPU worker feasibility probe",
                "image": IMAGE,
                "instance_type": instance_type,
                "command": "bash -lc 'nvidia-smi && exec python -m http.server 8000 --bind 0.0.0.0'",
                "scale": 1,
                "routes": [{"container_port": 8000, "visibility": "account"}],
                "environment_variables": {"SAGA_SATURN_PROBE": "1"},
                "use_spot_instance": False,
            },
        }
        deployment_ev: dict[str, Any] = {"recipe": deployment_recipe}
        evidence["deployment"] = deployment_ev
        try:
            started = time.monotonic()
            applied = conn.apply(deployment_recipe)
            deployment_ev["apply"] = applied
            resource_id = applied["state"]["id"]
            start_result = conn.start("deployment", resource_id)
            deployment_ev["start"] = start_result
            final, timeline = wait_for(conn, "deployment", DEPLOYMENT_NAME)
            deployment_ev["startup_seconds"] = round(time.monotonic() - started, 1)
            deployment_ev["timeline"] = timeline
            deployment_ev["final"] = final
            deployment_ev["logs"] = safe_logs(conn, "deployment", DEPLOYMENT_NAME)
            urls = collect_urls(final)
            deployment_ev["candidate_urls"] = urls
            deployment_ev["http_probes"] = http_probe(urls)
            successful_http = any(item.get("status") == 200 for item in deployment_ev["http_probes"])
            deployment_ev["success"] = state_status(final) in {"running", "ready"} and successful_http
            if deployment_ev["success"]:
                evidence["outcome"] = "gpu_deployment_supported"
                return_code = 0
            else:
                evidence["outcome"] = "deployment_created_but_not_reachable"
                return_code = 4
        except Exception as exc:
            deployment_ev["error"] = f"{type(exc).__name__}: {exc}"
            deployment_ev["traceback"] = traceback.format_exc(limit=8)
            deployment_ev["success"] = False
            evidence["outcome"] = "deployment_rejected_try_workspace"
            return_code = 0
        finally:
            try:
                safe_cleanup(conn, "deployment", DEPLOYMENT_NAME, deployment_ev)
            except Exception:
                pass

        if deployment_ev.get("success"):
            emit(evidence)
            return return_code

        workspace_recipe = {
            "type": "workspace",
            "spec": {
                "name": WORKSPACE_NAME,
                "description": "Temporary SAGA Saturn GPU workspace worker feasibility probe",
                "image": IMAGE,
                "instance_type": instance_type,
                "ide": "jupyter",
                "disk_space": "64Gi",
                "auto_shutoff": "1 hour",
                "routes": [{"container_port": 8000, "visibility": "owner"}],
                "start_script": "nvidia-smi; nohup python -m http.server 8000 --bind 0.0.0.0 >/tmp/saga-saturn-probe.log 2>&1 &",
                "environment_variables": {"SAGA_SATURN_PROBE": "1"},
                "start_ssh": False,
                "use_spot_instance": False,
            },
        }
        workspace_ev: dict[str, Any] = {"recipe": workspace_recipe}
        evidence["workspace_fallback"] = workspace_ev
        try:
            started = time.monotonic()
            applied = conn.apply(workspace_recipe)
            workspace_ev["apply"] = applied
            resource_id = applied["state"]["id"]
            workspace_ev["start"] = conn.start("workspace", resource_id)
            final, timeline = wait_for(conn, "workspace", WORKSPACE_NAME)
            workspace_ev["startup_seconds"] = round(time.monotonic() - started, 1)
            workspace_ev["timeline"] = timeline
            workspace_ev["final"] = final
            workspace_ev["logs"] = safe_logs(conn, "workspace", WORKSPACE_NAME)
            urls = collect_urls(final)
            workspace_ev["candidate_urls"] = urls
            workspace_ev["http_probes"] = http_probe(urls)
            successful_http = any(item.get("status") == 200 for item in workspace_ev["http_probes"])
            workspace_ev["success"] = state_status(final) in {"running", "ready"} and successful_http
            evidence["outcome"] = "gpu_workspace_route_supported" if workspace_ev["success"] else "workspace_created_but_not_reachable"
            return_code = 0 if workspace_ev["success"] else 5
        except Exception as exc:
            workspace_ev["error"] = f"{type(exc).__name__}: {exc}"
            workspace_ev["traceback"] = traceback.format_exc(limit=8)
            workspace_ev["success"] = False
            evidence["outcome"] = "gpu_workspace_rejected"
            return_code = 6
        finally:
            try:
                safe_cleanup(conn, "workspace", WORKSPACE_NAME, workspace_ev)
            except Exception:
                pass

        emit(evidence)
        return return_code
    except Exception as exc:
        evidence["fatal_error"] = f"{type(exc).__name__}: {exc}"
        evidence["fatal_traceback"] = traceback.format_exc(limit=12)
        emit(evidence)
        return 10


if __name__ == "__main__":
    raise SystemExit(main())
