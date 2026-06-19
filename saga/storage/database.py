from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .models import Base


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "analysis_outputs" / "saga_canonical.sqlite3"

_ENGINE = None
_SESSION_FACTORY = None


def get_database_url(database_path: str | Path | None = None) -> str:
    explicit = str(database_path or os.getenv("SAGA_SQLITE_PATH") or "").strip()
    target = Path(explicit) if explicit else DEFAULT_DB_PATH
    if not target.is_absolute():
        target = (PROJECT_ROOT / target).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{target}"


def get_engine(database_path: str | Path | None = None):
    global _ENGINE
    if _ENGINE is None or database_path is not None:
        _ENGINE = create_engine(
            get_database_url(database_path),
            future=True,
            echo=False,
        )
    return _ENGINE


def get_session_factory(database_path: str | Path | None = None):
    global _SESSION_FACTORY
    if _SESSION_FACTORY is None or database_path is not None:
        _SESSION_FACTORY = sessionmaker(bind=get_engine(database_path), autoflush=False, expire_on_commit=False, future=True)
    return _SESSION_FACTORY


def initialize_database(database_path: str | Path | None = None) -> None:
    engine = get_engine(database_path)
    Base.metadata.create_all(engine)
    _ensure_sqlite_migrations(engine)


def _ensure_sqlite_migrations(engine) -> None:
    with engine.begin() as connection:
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(entities)")).fetchall()}
        if "baseline_visual_prompt" not in columns:
            connection.execute(text("ALTER TABLE entities ADD COLUMN baseline_visual_prompt TEXT"))
        if "generated_image_path" not in columns:
            connection.execute(text("ALTER TABLE entities ADD COLUMN generated_image_path TEXT"))
        if "generated_thumbnail_path" not in columns:
            connection.execute(text("ALTER TABLE entities ADD COLUMN generated_thumbnail_path TEXT"))
        if "generated_image_bytes" not in columns:
            connection.execute(text("ALTER TABLE entities ADD COLUMN generated_image_bytes BLOB"))
        image_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(generated_images)")).fetchall()}
        if "thumbnail_path" not in image_columns:
            connection.execute(text("ALTER TABLE generated_images ADD COLUMN thumbnail_path TEXT"))
