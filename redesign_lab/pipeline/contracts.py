"""Simple redesign-local contract validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


CONTRACT_DIR = Path(__file__).with_name("contracts")


class ContractValidationError(ValueError):
    """Raised when a redesign contract payload is malformed."""


def load_contract_schema(name: str) -> Dict[str, Any]:
    path = CONTRACT_DIR / f"{name}.json"
    if not path.exists():
        raise ContractValidationError(f"Unknown redesign contract: {name}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_contract(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    schema = load_contract_schema(name)
    required = schema.get("required") or {}
    if not isinstance(payload, dict):
        raise ContractValidationError(f"{name} payload must be an object.")
    for key, expected_type in required.items():
        if key not in payload:
            raise ContractValidationError(f"{name} is missing required field '{key}'.")
        if not _matches_type(payload[key], expected_type):
            raise ContractValidationError(
                f"{name}.{key} expected {expected_type}, got {type(payload[key]).__name__}."
            )
    return payload


def _matches_type(value: Any, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "boolean":
        return isinstance(value, bool)
    return True

