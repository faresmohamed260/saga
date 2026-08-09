"""Add immutable release gate evidence."""

from alembic import op

revision = "202608090400"
down_revision = "202608090300"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    create table if not exists public.deployment_release_gate_evidence (
      evidence_id varchar(160) primary key,
      release_id varchar(160) not null references public.deployment_releases(release_id) on delete restrict,
      gate varchar(80) not null,
      status varchar(32) not null,
      observed_at_ms bigint not null,
      expires_at_ms bigint not null default 0,
      source varchar(160) not null,
      evidence_sha256 varchar(64) not null,
      details jsonb not null default '{}'::jsonb,
      artifact_reference jsonb not null default '{}'::jsonb,
      created_at timestamptz not null default now(),
      check (gate in (
        'ci', 'database_recovery', 'artifact_recovery', 'migration', 'staging_readiness',
        'process_health', 'production_qualification', 'usage_cost', 'slo', 'rollback', 'canary'
      )),
      check (status in ('passed', 'failed')),
      check (observed_at_ms > 0),
      check (expires_at_ms >= 0),
      check (char_length(evidence_sha256) = 64)
    );
    create index if not exists ix_deployment_release_gate_latest
      on public.deployment_release_gate_evidence (release_id, gate, observed_at_ms desc);
    """)


def downgrade() -> None:
    op.execute("drop table if exists public.deployment_release_gate_evidence;")
