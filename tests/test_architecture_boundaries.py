from __future__ import annotations

import ast
from pathlib import Path


ACTIVE_PYTHON_ROOTS = (
    Path("apps/dashboard_api"),
    Path("integrations"),
    Path("packages"),
    Path("scripts"),
)


def test_active_python_does_not_import_isolated_legacy_package() -> None:
    violations: list[str] = []
    for root in ACTIVE_PYTHON_ROOTS:
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    imported = [node.module or ""]
                else:
                    continue
                if any(name == "saga" or name.startswith("saga.") for name in imported):
                    violations.append(str(path))
    assert not violations, f"Active code imports isolated legacy modules: {sorted(set(violations))}"


def test_packaging_excludes_legacy_and_tests() -> None:
    project = Path("pyproject.toml").read_text(encoding="utf-8")
    package_includes = project.split("include = [", 1)[1].split("]", 1)[0]
    assert '"saga"' not in package_includes
    assert '"saga.*"' not in package_includes
    assert '"tests"' not in package_includes
