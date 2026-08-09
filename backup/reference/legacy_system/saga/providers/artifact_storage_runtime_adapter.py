from __future__ import annotations

from pathlib import Path

from packages.artifact_storage_runtime.factory import create_artifact_storage_client
from packages.artifact_storage_runtime.models import ArtifactStorageProfile, ArtifactStorageRuntimeConfig

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def create_runtime_artifact_storage_client(
    *,
    root_dir: str = "analysis_outputs",
    temp_root_dir: str = "analysis_outputs/tmp",
):
    resolved_root = Path(root_dir)
    if not resolved_root.is_absolute():
        resolved_root = (PROJECT_ROOT / resolved_root).resolve()
    resolved_temp_root = Path(temp_root_dir)
    if not resolved_temp_root.is_absolute():
        resolved_temp_root = (PROJECT_ROOT / resolved_temp_root).resolve()
    profile = ArtifactStorageProfile(
        name="runtime_artifact_storage",
        root_dir=str(resolved_root),
        temp_root_dir=str(resolved_temp_root),
    )
    return create_artifact_storage_client(config=ArtifactStorageRuntimeConfig(profile=profile), profile=profile)
