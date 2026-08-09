"""Baseline persistence and vector schema."""

from pathlib import Path

from alembic import op


revision = "202607051730"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    root = Path(__file__).resolve().parents[2]
    op.execute((root / "supabase/migrations/20260705120000_init_persistence_runtime.sql").read_text(encoding="utf-8"))
    op.execute((root / "supabase/migrations/20260705173000_add_vector_documents.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("""
        drop table if exists public.vector_documents;
        drop table if exists public.audiobook_chapters;
        drop table if exists public.audiobook_runs;
        drop table if exists public.generated_stories;
        drop table if exists public.job_logs;
        drop table if exists public.jobs;
        drop table if exists public.identity_series;
        drop table if exists public.library_records;
        drop table if exists public.library_scenes;
        drop table if exists public.library_books;
        drop table if exists public.library_series;
        drop table if exists public.provider_statuses;
        drop table if exists public.provider_configs;
    """)
