#!/usr/bin/env python3
"""Inspect the live Saturn recipe schema without exposing credentials."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests

BASE_URL = os.environ.get("SATURN_BASE_URL", "https://app.community.saturnenterprise.io").rstrip("/")
TOKEN = os.environ.get("SATURN_TOKEN", "").strip()
OUT = Path(os.environ.get("SATURN_SCHEMA_OUTPUT", "/tmp/saturn-recipe-schema.json"))
SUMMARY_OUT = Path(os.environ.get("SATURN_SCHEMA_SUMMARY_OUTPUT", "/tmp/saturn-recipe-schema-summary.json"))

KEY_DEFINITIONS = (
    "ResourceConfigSpec",
    "OwnerResourceCreate",
    "OwnerResourceEnvironmentCreate",
    "CommandCreate",
    "Command",
    "Port",
    "ResourceScaleCreate",
    "ResourceScale",
    "RecipeResourceImageCreate",
    "RecipeResourceDiskCreate",
    "GitRepositoryInput",
    "GlobalEnvVariableInput",
    "ResourceEnvVariableCreate",
    "VolumeMountInput",
)


def describe_schema(schema: dict[str, Any]) -> dict[str, Any]:
    defs = schema.get("$defs") or schema.get("definitions") or {}
    interesting: dict[str, Any] = {}
    for name, value in defs.items():
        if not isinstance(value, dict):
            continue
        props = value.get("properties") or {}
        lname = name.lower()
        type_prop = props.get("type") if isinstance(props, dict) else None
        type_values: list[Any] = []
        if isinstance(type_prop, dict):
            if "const" in type_prop:
                type_values.append(type_prop["const"])
            if isinstance(type_prop.get("enum"), list):
                type_values.extend(type_prop["enum"])
        if any(word in lname for word in ("resource", "recipe", "deploy", "workspace", "job")) or type_values:
            interesting[name] = {
                "required": value.get("required"),
                "property_keys": sorted(props.keys()) if isinstance(props, dict) else [],
                "type_values": type_values,
                "spec": props.get("spec") if isinstance(props, dict) else None,
            }

    return {
        "schema_title": schema.get("title"),
        "schema_version": schema.get("$schema"),
        "root_keys": sorted(schema.keys()),
        "root_required": schema.get("required"),
        "root_properties": schema.get("properties"),
        "root_one_of": schema.get("oneOf"),
        "root_any_of": schema.get("anyOf"),
        "definition_names": sorted(defs.keys()),
        "interesting_definitions": interesting,
        "key_definitions": {name: defs.get(name) for name in KEY_DEFINITIONS if name in defs},
    }


def main() -> int:
    if not TOKEN:
        raise SystemExit("SATURN_TOKEN is missing")
    response = requests.get(
        BASE_URL + "/api/recipes/schema",
        headers={"Authorization": f"token {TOKEN}"},
        timeout=30,
    )
    print(f"recipe schema HTTP {response.status_code}")
    response.raise_for_status()
    schema = response.json()
    OUT.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    summary = describe_schema(schema)
    SUMMARY_OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
