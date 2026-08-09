"""Add immutable provider usage ledger and budget policies."""

from alembic import op

revision = "202608090300"
down_revision = "202608090200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    create table if not exists public.usage_ledger (
      entry_id varchar(160) primary key, reservation_id varchar(160) not null,
      entry_kind varchar(32) not null, timestamp_ms bigint not null, expires_at_ms bigint not null default 0,
      release_id varchar(160) not null default '', run_id varchar(160) not null default '',
      series_id varchar(120) not null default '', stage varchar(120) not null default '',
      agent varchar(120) not null default '', component varchar(120) not null default '',
      provider varchar(120) not null default '', account_alias varchar(160) not null default '',
      model varchar(160) not null default '', operation varchar(120) not null default '',
      request_count double precision not null default 0, input_tokens double precision not null default 0,
      output_tokens double precision not null default 0, cached_input_tokens double precision not null default 0,
      compute_seconds double precision not null default 0, image_count double precision not null default 0,
      audio_seconds double precision not null default 0, cost_usd double precision not null default 0,
      cost_status varchar(32) not null default 'unpriced', pricing_version varchar(80) not null default '',
      evidence jsonb not null default '{}'::jsonb, created_at timestamptz not null default now(),
      check (entry_kind in ('reservation', 'reservation_release', 'charge')),
      check (cost_status in ('native', 'estimated', 'unpriced'))
    );
    create index if not exists ix_usage_ledger_run on public.usage_ledger (run_id, timestamp_ms);
    create index if not exists ix_usage_ledger_provider on public.usage_ledger (provider, account_alias, timestamp_ms);
    create index if not exists ix_usage_ledger_reservation on public.usage_ledger (reservation_id, entry_kind);

    create table if not exists public.usage_budget_policies (
      policy_id varchar(160) primary key, scope_type varchar(32) not null,
      scope_value varchar(160) not null default '', window_seconds integer not null default 0,
      limits jsonb not null default '{}'::jsonb, hard_limit boolean not null default true,
      enabled boolean not null default true, created_at timestamptz not null default now(),
      updated_at timestamptz not null default now(),
      check (scope_type in ('global', 'run', 'provider', 'account', 'model')),
      check (window_seconds >= 0)
    );
    create index if not exists ix_usage_budget_scope on public.usage_budget_policies (scope_type, scope_value, enabled);
    """)


def downgrade() -> None:
    op.execute("""
      drop table if exists public.usage_budget_policies;
      drop table if exists public.usage_ledger;
    """)
