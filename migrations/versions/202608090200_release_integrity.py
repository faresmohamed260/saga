"""Enforce a single production release at the database boundary."""

from alembic import op


revision = "202608090200"
down_revision = "202608090100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      create unique index if not exists uq_deployment_single_production
      on public.deployment_releases ((status))
      where status = 'production';
    """)


def downgrade() -> None:
    op.execute("drop index if exists public.uq_deployment_single_production;")
