"""Add explicit project attribution to provider usage accounting."""

from alembic import op

revision = "202608120100"
down_revision = "202608090400"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    alter table public.usage_ledger
      add column if not exists project_id varchar(160) not null default '';
    create index if not exists ix_usage_ledger_project
      on public.usage_ledger (project_id, timestamp_ms);
    """)


def downgrade() -> None:
    op.execute("drop index if exists public.ix_usage_ledger_project;")
    op.execute("alter table public.usage_ledger drop column if exists project_id;")
