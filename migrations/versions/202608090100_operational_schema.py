"""Add durable execution, lineage, observability, checkpoints, and releases."""

from alembic import op


revision = "202608090100"
down_revision = "202607051730"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    create table if not exists public.execution_queue_policies (
      queue_name varchar(120) primary key, payload jsonb not null default '{}'::jsonb,
      updated_at timestamptz not null default now()
    );
    create table if not exists public.execution_queue (
      queue_id varchar(160) primary key, run_id varchar(160) not null unique,
      queue_name varchar(120) not null, series_id varchar(120) not null default '',
      status varchar(64) not null default 'queued', priority integer not null default 0,
      capabilities jsonb not null default '[]'::jsonb, payload jsonb not null default '{}'::jsonb,
      available_at_ms bigint not null default 0, lease_owner varchar(160) not null default '',
      lease_token varchar(160) not null default '', lease_expires_at_ms bigint not null default 0,
      heartbeat_at_ms bigint not null default 0, cancellation_requested_at_ms bigint not null default 0,
      attempt_count integer not null default 0, max_attempts integer not null default 3,
      backoff_seconds integer not null default 5, last_error jsonb not null default '{}'::jsonb,
      created_at timestamptz not null default now(), updated_at timestamptz not null default now()
    );
    create index if not exists ix_execution_queue_claim on public.execution_queue (queue_name, status, available_at_ms, priority);
    create index if not exists ix_execution_queue_series on public.execution_queue (queue_name, series_id, status);
    create index if not exists ix_execution_queue_lease on public.execution_queue (status, lease_expires_at_ms);
    create table if not exists public.execution_telemetry (
      id bigint generated always as identity primary key, queue_name varchar(120) not null default '',
      queue_id varchar(160) not null default '', run_id varchar(160) not null default '',
      event_type varchar(120) not null, status varchar(64) not null default '', worker_id varchar(160) not null default '',
      timestamp_ms bigint not null default 0, payload jsonb not null default '{}'::jsonb
    );
    create index if not exists ix_execution_telemetry_run on public.execution_telemetry (run_id, id);
    create index if not exists ix_execution_telemetry_queue on public.execution_telemetry (queue_name, id);
    create table if not exists public.stage_lineage_records (
      execution_id varchar(160) primary key, run_id varchar(160) not null, series_id varchar(120) not null,
      stage varchar(120) not null, attempt integer not null default 1, status varchar(64) not null,
      execution_mode varchar(64) not null default 'executed', input_fingerprint varchar(64) not null,
      output_fingerprint varchar(64) not null default '', lineage_fingerprint varchar(64) not null,
      parent_fingerprints jsonb not null default '{}'::jsonb, versions jsonb not null default '{}'::jsonb,
      payload jsonb not null default '{}'::jsonb, created_at timestamptz not null default now()
    );
    create index if not exists ix_stage_lineage_run on public.stage_lineage_records (run_id, stage, created_at);
    create index if not exists ix_stage_lineage_match on public.stage_lineage_records (series_id, stage, input_fingerprint, status);
    create index if not exists ix_stage_lineage_output on public.stage_lineage_records (series_id, stage, output_fingerprint);
    create table if not exists public.observability_records (
      observation_id varchar(160) primary key, kind varchar(32) not null, timestamp_ms bigint not null,
      run_id varchar(160) not null default '', series_id varchar(120) not null default '',
      component varchar(120) not null default '', stage varchar(120) not null default '', provider varchar(120) not null default '',
      name varchar(160) not null, status varchar(64) not null default '', value double precision,
      unit varchar(32) not null default '', dimensions jsonb not null default '{}'::jsonb,
      payload jsonb not null default '{}'::jsonb, created_at timestamptz not null default now()
    );
    create index if not exists ix_observability_time on public.observability_records (kind, timestamp_ms);
    create index if not exists ix_observability_run on public.observability_records (run_id, timestamp_ms);
    create index if not exists ix_observability_metric on public.observability_records (name, timestamp_ms);
    create index if not exists ix_observability_component on public.observability_records (component, provider, timestamp_ms);
    create table if not exists public.agent_runtime_checkpoints (
      thread_id varchar(160) not null, checkpoint_ns varchar(255) not null default '', checkpoint_id varchar(160) not null,
      parent_checkpoint_id varchar(160), checkpoint_type varchar(120) not null, checkpoint_bytes bytea not null,
      metadata_type varchar(120) not null, metadata_bytes bytea not null, metadata_json jsonb not null default '{}'::jsonb,
      created_at timestamptz, primary key (thread_id, checkpoint_ns, checkpoint_id)
    );
    create table if not exists public.agent_runtime_checkpoint_blobs (
      thread_id varchar(160) not null, checkpoint_ns varchar(255) not null default '', channel varchar(255) not null,
      version varchar(160) not null, blob_type varchar(120) not null, blob_bytes bytea not null,
      primary key (thread_id, checkpoint_ns, channel, version)
    );
    create table if not exists public.agent_runtime_checkpoint_writes (
      thread_id varchar(160) not null, checkpoint_ns varchar(255) not null default '', checkpoint_id varchar(160) not null,
      task_id varchar(160) not null, write_idx integer not null, channel varchar(255) not null,
      value_type varchar(120) not null, value_bytes bytea not null, task_path varchar(512) not null default '',
      primary key (thread_id, checkpoint_ns, checkpoint_id, task_id, write_idx)
    );
    create table if not exists public.deployment_releases (
      release_id varchar(160) primary key, version varchar(80) not null, git_sha varchar(64) not null,
      image_digest varchar(160) not null default '', status varchar(32) not null,
      manifest jsonb not null default '{}'::jsonb, created_at timestamptz not null default now(), promoted_at timestamptz
    );
    create index if not exists ix_deployment_releases_status on public.deployment_releases (status, created_at);
    create table if not exists public.deployment_process_heartbeats (
      process_id varchar(160) primary key, role varchar(64) not null, release_id varchar(160) not null default '',
      status varchar(32) not null, metadata jsonb not null default '{}'::jsonb,
      last_seen_ms bigint not null, updated_at timestamptz not null default now()
    );
    create index if not exists ix_deployment_heartbeats_role on public.deployment_process_heartbeats (role, last_seen_ms);
    """)


def downgrade() -> None:
    op.execute("""
      drop table if exists public.deployment_process_heartbeats;
      drop table if exists public.deployment_releases;
      drop table if exists public.agent_runtime_checkpoint_writes;
      drop table if exists public.agent_runtime_checkpoint_blobs;
      drop table if exists public.agent_runtime_checkpoints;
      drop table if exists public.observability_records;
      drop table if exists public.stage_lineage_records;
      drop table if exists public.execution_telemetry;
      drop table if exists public.execution_queue;
      drop table if exists public.execution_queue_policies;
    """)
