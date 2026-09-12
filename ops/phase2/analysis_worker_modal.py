from __future__ import annotations

import subprocess

import modal

APP_NAME = "saga-phase2-analysis-worker"
WORKER_DIR = "/opt/saga-worker"
MODAL_VERSION = "1.4.2"

worker_secret = modal.Secret.from_name("saga-phase2-analysis-worker-runtime")

image = (
    modal.Image.from_registry("node:24-bookworm-slim", add_python="3.11")
    .apt_install("ca-certificates")
    .add_local_dir("services/analysis-worker", remote_path=WORKER_DIR, copy=True)
    .workdir(WORKER_DIR)
    .run_commands("npm ci")
    .env(
        {
            "SAGA_WORKER_ONCE": "1",
            "SAGA_WORKER_ID": "modal-phase2-hosted-proof",
            "SAGA_WORKER_LEASE_SECONDS": "600",
            "SAGA_WORKER_IDLE_POLL_MS": "1000",
            "NODE_ENV": "production",
        }
    )
)

app = modal.App(APP_NAME, image=image)


def _run_once() -> dict[str, object]:
    result = subprocess.run(
        ["npm", "run", "worker"],
        cwd=WORKER_DIR,
        text=True,
        capture_output=True,
        timeout=900,
        check=False,
    )
    stdout_lines = [line for line in (result.stdout or "").splitlines() if line.strip()]
    stderr_lines = [line for line in (result.stderr or "").splitlines() if line.strip()]
    if result.returncode != 0:
        detail = "\n".join(stderr_lines[-20:] + stdout_lines[-20:])[-8000:]
        raise RuntimeError(f"analysis worker exited {result.returncode}: {detail}")
    return {
        "ok": True,
        "stdout": stdout_lines[-20:],
        "stderrCount": len(stderr_lines),
    }


@app.function(
    image=image,
    timeout=1000,
    secrets=[worker_secret],
    schedule=modal.Cron("* * * * *"),
)
def poll() -> dict[str, object]:
    return _run_once()


@app.function(image=image, timeout=1000, secrets=[worker_secret])
def run_once() -> dict[str, object]:
    return _run_once()
