"""Production deployment and release engineering runtime.

Exports are loaded on first access so lightweight release-candidate operations do
not initialize persistence, backup, health, and process dependencies.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "ArtifactBackupRuntime": (".backup", "ArtifactBackupRuntime"),
    "BackupRuntime": (".backup", "BackupRuntime"),
    "CANARY_REQUIRED_GATES": (".gates", "CANARY_REQUIRED_GATES"),
    "DependencyStatus": (".contracts", "DependencyStatus"),
    "MigrationRuntime": (".migrations", "MigrationRuntime"),
    "PRODUCTION_REQUIRED_GATES": (".gates", "PRODUCTION_REQUIRED_GATES"),
    "ProcessTickResult": (".contracts", "ProcessTickResult"),
    "ReadinessReport": (".contracts", "ReadinessReport"),
    "ReleaseCandidateBundle": (".contracts", "ReleaseCandidateBundle"),
    "ReleaseGateCheck": (".contracts", "ReleaseGateCheck"),
    "ReleaseGateDecision": (".contracts", "ReleaseGateDecision"),
    "ReleaseGateEvidence": (".contracts", "ReleaseGateEvidence"),
    "ReleaseGateRuntime": (".gates", "ReleaseGateRuntime"),
    "ReleaseManifest": (".contracts", "ReleaseManifest"),
    "ReleaseRuntime": (".release", "ReleaseRuntime"),
    "check_readiness": (".health", "check_readiness"),
    "create_deployment_persistence_client": (".config", "create_deployment_persistence_client"),
    "create_release_candidate": (".candidate", "create_release_candidate"),
    "create_release_manifest": (".release", "create_release_manifest"),
    "observability_tick": (".processes", "observability_tick"),
    "scheduler_tick": (".processes", "scheduler_tick"),
    "verify_release_candidate": (".candidate", "verify_release_candidate"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted((*globals(), *__all__))
