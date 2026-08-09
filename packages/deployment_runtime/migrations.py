"""Alembic migration control kept outside application startup."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Engine
from sqlalchemy import inspect


BASELINE_TABLES = frozenset({"provider_configs", "provider_statuses", "library_series", "library_books", "library_scenes", "library_records", "identity_series", "jobs", "job_logs", "generated_stories", "audiobook_runs", "audiobook_chapters", "vector_documents"})


class MigrationRuntime:
    def __init__(self, *, root_dir: str | Path | None = None) -> None:
        self.root_dir = Path(root_dir or Path(__file__).resolve().parents[2]).resolve()
        self.config = Config(str(self.root_dir / "alembic.ini"))

    def upgrade(self, revision: str = "head") -> None:
        command.upgrade(self.config, revision)

    def downgrade(self, revision: str) -> None:
        if not str(revision or "").strip():
            raise ValueError("A downgrade revision is required.")
        command.downgrade(self.config, revision)

    def current(self, engine: Engine) -> str:
        with engine.connect() as connection:
            return str(MigrationContext.configure(connection, opts={"version_table_schema": "public"}).get_current_revision() or "")

    def head(self) -> str:
        return str(ScriptDirectory.from_config(self.config).get_current_head() or "")

    def check(self, engine: Engine) -> dict[str, object]:
        current, head = self.current(engine), self.head()
        return {"ready": bool(current and current == head), "current": current, "head": head}

    def adopt_existing(self, engine: Engine, *, baseline_revision: str = "202607051730", upgrade: bool = True) -> dict[str, object]:
        current = self.current(engine)
        if current:
            raise RuntimeError(f"Database is already versioned at '{current}'.")
        schema = "public" if engine.dialect.name == "postgresql" else None
        existing = set(inspect(engine).get_table_names(schema=schema))
        missing = sorted(BASELINE_TABLES - existing)
        if missing:
            raise RuntimeError("Cannot adopt an incomplete baseline; missing: " + ", ".join(missing))
        command.stamp(self.config, baseline_revision)
        if upgrade:
            command.upgrade(self.config, "head")
        return {"adopted": True, "baseline": baseline_revision, "current": self.head() if upgrade else baseline_revision}
