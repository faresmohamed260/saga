begin;

create or replace function public.saga_current_user_has_active_access()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.saga_account_access as access
    where access.user_id = (select auth.uid())
      and access.status = 'active'
  );
$$;

revoke all on function public.saga_current_user_has_active_access() from public, anon;
grant execute on function public.saga_current_user_has_active_access() to authenticated, service_role;

create table public.saga_projects (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  title text not null,
  description text,
  status text not null default 'active' check (status in ('active', 'archived')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint saga_projects_title_check check (char_length(btrim(title)) between 1 and 160),
  constraint saga_projects_description_check check (
    description is null or char_length(description) <= 4000
  ),
  constraint saga_projects_owner_identity_unique unique (id, owner_user_id)
);

create index saga_projects_owner_updated_idx
  on public.saga_projects (owner_user_id, updated_at desc);

create trigger saga_projects_touch_updated_at
before update on public.saga_projects
for each row execute function public.saga_touch_updated_at();

create table public.saga_sources (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null,
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  original_filename text not null,
  display_name text not null,
  source_format text not null check (source_format in ('txt', 'epub')),
  media_type text not null,
  byte_size bigint not null check (byte_size >= 0),
  content_sha256 text not null,
  object_key text not null,
  ingestion_status text not null default 'uploaded'
    check (ingestion_status in ('pending_upload', 'uploaded', 'processing', 'ready', 'failed')),
  failure_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint saga_sources_project_owner_fk
    foreign key (project_id, owner_user_id)
    references public.saga_projects(id, owner_user_id)
    on delete cascade,
  constraint saga_sources_filename_check check (char_length(btrim(original_filename)) between 1 and 512),
  constraint saga_sources_display_name_check check (char_length(btrim(display_name)) between 1 and 512),
  constraint saga_sources_media_type_check check (char_length(btrim(media_type)) between 3 and 160),
  constraint saga_sources_sha256_check check (content_sha256 ~ '^[0-9a-f]{64}$'),
  constraint saga_sources_object_key_check check (char_length(btrim(object_key)) between 1 and 1024),
  constraint saga_sources_failure_state_check check (
    (ingestion_status = 'failed' and failure_code is not null)
    or (ingestion_status <> 'failed' and failure_code is null)
  ),
  constraint saga_sources_identity_scope_unique unique (id, project_id, owner_user_id),
  constraint saga_sources_object_key_unique unique (object_key)
);

create index saga_sources_owner_created_idx
  on public.saga_sources (owner_user_id, created_at desc);

create index saga_sources_project_created_idx
  on public.saga_sources (project_id, created_at desc);

create index saga_sources_content_sha_idx
  on public.saga_sources (owner_user_id, content_sha256);

create trigger saga_sources_touch_updated_at
before update on public.saga_sources
for each row execute function public.saga_touch_updated_at();

create table public.saga_analysis_jobs (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null,
  source_id uuid not null,
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  requested_by uuid not null references auth.users(id) on delete cascade,
  kind text not null check (kind in ('source_ingestion', 'character_identity')),
  status text not null default 'queued'
    check (status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
  input_fingerprint text not null,
  attempt_count integer not null default 0 check (attempt_count >= 0),
  max_attempts integer not null default 3 check (max_attempts between 1 and 10),
  available_at timestamptz not null default now(),
  lease_token uuid,
  lease_owner text,
  lease_expires_at timestamptz,
  started_at timestamptz,
  completed_at timestamptz,
  error_code text,
  error_summary text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint saga_analysis_jobs_source_owner_fk
    foreign key (source_id, project_id, owner_user_id)
    references public.saga_sources(id, project_id, owner_user_id)
    on delete cascade,
  constraint saga_analysis_jobs_requested_by_owner_check check (requested_by = owner_user_id),
  constraint saga_analysis_jobs_input_fingerprint_check check (input_fingerprint ~ '^[0-9a-f]{64}$'),
  constraint saga_analysis_jobs_lease_owner_check check (
    lease_owner is null or char_length(btrim(lease_owner)) between 1 and 256
  ),
  constraint saga_analysis_jobs_error_code_check check (
    error_code is null or char_length(btrim(error_code)) between 1 and 128
  ),
  constraint saga_analysis_jobs_error_summary_check check (
    error_summary is null or char_length(error_summary) <= 1000
  ),
  constraint saga_analysis_jobs_state_check check (
    (
      status = 'queued'
      and lease_token is null
      and lease_owner is null
      and lease_expires_at is null
      and completed_at is null
    )
    or (
      status = 'running'
      and lease_token is not null
      and lease_owner is not null
      and lease_expires_at is not null
      and started_at is not null
      and completed_at is null
    )
    or (
      status in ('succeeded', 'failed', 'cancelled')
      and lease_token is null
      and lease_owner is null
      and lease_expires_at is null
      and completed_at is not null
    )
  )
);

create index saga_analysis_jobs_owner_created_idx
  on public.saga_analysis_jobs (owner_user_id, created_at desc);

create index saga_analysis_jobs_claim_idx
  on public.saga_analysis_jobs (status, available_at, created_at)
  where status in ('queued', 'running');

create unique index saga_analysis_jobs_one_active_input_idx
  on public.saga_analysis_jobs (source_id, kind, input_fingerprint)
  where status in ('queued', 'running');

create trigger saga_analysis_jobs_touch_updated_at
before update on public.saga_analysis_jobs
for each row execute function public.saga_touch_updated_at();

create table public.saga_analysis_runs (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references public.saga_analysis_jobs(id) on delete cascade,
  project_id uuid not null,
  source_id uuid not null,
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  status text not null check (status in ('succeeded', 'failed')),
  input_fingerprint text not null,
  normalized_input_fingerprint text,
  engine_version text not null,
  provider_name text,
  provider_model text,
  provider_revision text,
  config_fingerprint text not null,
  output_fingerprint text,
  failure_code text,
  started_at timestamptz not null,
  completed_at timestamptz not null,
  created_at timestamptz not null default now(),
  constraint saga_analysis_runs_source_owner_fk
    foreign key (source_id, project_id, owner_user_id)
    references public.saga_sources(id, project_id, owner_user_id)
    on delete cascade,
  constraint saga_analysis_runs_input_fingerprint_check check (input_fingerprint ~ '^[0-9a-f]{64}$'),
  constraint saga_analysis_runs_normalized_fingerprint_check check (
    normalized_input_fingerprint is null or normalized_input_fingerprint ~ '^[0-9a-f]{64}$'
  ),
  constraint saga_analysis_runs_config_fingerprint_check check (config_fingerprint ~ '^[0-9a-f]{64}$'),
  constraint saga_analysis_runs_output_fingerprint_check check (
    output_fingerprint is null or output_fingerprint ~ '^[0-9a-f]{64}$'
  ),
  constraint saga_analysis_runs_engine_version_check check (char_length(btrim(engine_version)) between 1 and 160),
  constraint saga_analysis_runs_terminal_state_check check (
    (
      status = 'succeeded'
      and normalized_input_fingerprint is not null
      and output_fingerprint is not null
      and failure_code is null
    )
    or (
      status = 'failed'
      and output_fingerprint is null
      and failure_code is not null
    )
  ),
  constraint saga_analysis_runs_time_check check (completed_at >= started_at),
  constraint saga_analysis_runs_identity_scope_unique unique (id, project_id, source_id, owner_user_id)
);

create index saga_analysis_runs_source_completed_idx
  on public.saga_analysis_runs (source_id, completed_at desc);

create index saga_analysis_runs_owner_completed_idx
  on public.saga_analysis_runs (owner_user_id, completed_at desc);

create table public.saga_characters (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null,
  project_id uuid not null,
  source_id uuid not null,
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  canonical_name text not null,
  admission_tier text not null check (admission_tier in ('canonical_seed', 'stabilized')),
  evidence_count integer not null default 1 check (evidence_count >= 1),
  created_at timestamptz not null default now(),
  constraint saga_characters_run_scope_fk
    foreign key (run_id, project_id, source_id, owner_user_id)
    references public.saga_analysis_runs(id, project_id, source_id, owner_user_id)
    on delete cascade,
  constraint saga_characters_canonical_name_check check (char_length(btrim(canonical_name)) between 1 and 512),
  constraint saga_characters_identity_scope_unique unique (id, run_id, project_id, source_id, owner_user_id)
);

create index saga_characters_run_name_idx
  on public.saga_characters (run_id, canonical_name);

create table public.saga_character_aliases (
  id uuid primary key default gen_random_uuid(),
  character_id uuid not null,
  run_id uuid not null,
  project_id uuid not null,
  source_id uuid not null,
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  surface_form text not null,
  normalized_form text not null,
  evidence_count integer not null default 1 check (evidence_count >= 1),
  created_at timestamptz not null default now(),
  constraint saga_character_aliases_character_scope_fk
    foreign key (character_id, run_id, project_id, source_id, owner_user_id)
    references public.saga_characters(id, run_id, project_id, source_id, owner_user_id)
    on delete cascade,
  constraint saga_character_aliases_surface_form_check check (char_length(btrim(surface_form)) between 1 and 512),
  constraint saga_character_aliases_normalized_form_check check (char_length(btrim(normalized_form)) between 1 and 512),
  constraint saga_character_aliases_run_normalized_unique unique (run_id, character_id, normalized_form)
);

create index saga_character_aliases_character_idx
  on public.saga_character_aliases (character_id, evidence_count desc);

create table public.saga_character_mentions (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null,
  project_id uuid not null,
  source_id uuid not null,
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  character_id uuid,
  surface_text text not null,
  start_offset bigint not null check (start_offset >= 0),
  end_offset bigint not null check (end_offset > start_offset),
  structural_locator text,
  mention_kind text not null check (mention_kind in ('proper_name', 'nominal', 'pronoun')),
  resolution_state text not null check (resolution_state in ('linked', 'unresolved', 'quarantined')),
  evidence_tier text not null check (evidence_tier in ('canonical_seed', 'attachment', 'quarantined')),
  decision_reason text not null,
  created_at timestamptz not null default now(),
  constraint saga_character_mentions_run_scope_fk
    foreign key (run_id, project_id, source_id, owner_user_id)
    references public.saga_analysis_runs(id, project_id, source_id, owner_user_id)
    on delete cascade,
  constraint saga_character_mentions_character_scope_fk
    foreign key (character_id, run_id, project_id, source_id, owner_user_id)
    references public.saga_characters(id, run_id, project_id, source_id, owner_user_id)
    on delete cascade,
  constraint saga_character_mentions_surface_text_check check (char_length(surface_text) between 1 and 2000),
  constraint saga_character_mentions_locator_check check (
    structural_locator is null or char_length(structural_locator) <= 1000
  ),
  constraint saga_character_mentions_reason_check check (char_length(btrim(decision_reason)) between 1 and 1000),
  constraint saga_character_mentions_resolution_check check (
    (resolution_state = 'linked' and character_id is not null and evidence_tier <> 'quarantined')
    or (resolution_state in ('unresolved', 'quarantined') and character_id is null)
  )
);

create index saga_character_mentions_run_offset_idx
  on public.saga_character_mentions (run_id, start_offset, end_offset);

create index saga_character_mentions_character_idx
  on public.saga_character_mentions (character_id, start_offset)
  where character_id is not null;

alter table public.saga_projects enable row level security;
alter table public.saga_projects force row level security;
alter table public.saga_sources enable row level security;
alter table public.saga_sources force row level security;
alter table public.saga_analysis_jobs enable row level security;
alter table public.saga_analysis_jobs force row level security;
alter table public.saga_analysis_runs enable row level security;
alter table public.saga_analysis_runs force row level security;
alter table public.saga_characters enable row level security;
alter table public.saga_characters force row level security;
alter table public.saga_character_aliases enable row level security;
alter table public.saga_character_aliases force row level security;
alter table public.saga_character_mentions enable row level security;
alter table public.saga_character_mentions force row level security;

revoke all on table public.saga_projects from public, anon, authenticated;
revoke all on table public.saga_sources from public, anon, authenticated;
revoke all on table public.saga_analysis_jobs from public, anon, authenticated;
revoke all on table public.saga_analysis_runs from public, anon, authenticated;
revoke all on table public.saga_characters from public, anon, authenticated;
revoke all on table public.saga_character_aliases from public, anon, authenticated;
revoke all on table public.saga_character_mentions from public, anon, authenticated;

grant select, insert, update, delete on table public.saga_projects to authenticated;
grant select on table public.saga_sources to authenticated;
grant select on table public.saga_analysis_jobs to authenticated;
grant select on table public.saga_analysis_runs to authenticated;
grant select on table public.saga_characters to authenticated;
grant select on table public.saga_character_aliases to authenticated;
grant select on table public.saga_character_mentions to authenticated;

grant select, insert, update, delete on table public.saga_projects to service_role;
grant select, insert, update, delete on table public.saga_sources to service_role;
grant select, insert, update, delete on table public.saga_analysis_jobs to service_role;
grant select, insert on table public.saga_analysis_runs to service_role;
grant select, insert on table public.saga_characters to service_role;
grant select, insert on table public.saga_character_aliases to service_role;
grant select, insert on table public.saga_character_mentions to service_role;

create policy saga_projects_owner_select
  on public.saga_projects
  for select
  to authenticated
  using (
    owner_user_id = (select auth.uid())
    and public.saga_current_user_has_active_access()
  );

create policy saga_projects_owner_insert
  on public.saga_projects
  for insert
  to authenticated
  with check (
    owner_user_id = (select auth.uid())
    and public.saga_current_user_has_active_access()
  );

create policy saga_projects_owner_update
  on public.saga_projects
  for update
  to authenticated
  using (
    owner_user_id = (select auth.uid())
    and public.saga_current_user_has_active_access()
  )
  with check (
    owner_user_id = (select auth.uid())
    and public.saga_current_user_has_active_access()
  );

create policy saga_projects_owner_delete
  on public.saga_projects
  for delete
  to authenticated
  using (
    owner_user_id = (select auth.uid())
    and public.saga_current_user_has_active_access()
  );

create policy saga_sources_owner_select
  on public.saga_sources
  for select
  to authenticated
  using (
    owner_user_id = (select auth.uid())
    and public.saga_current_user_has_active_access()
  );

create policy saga_analysis_jobs_owner_select
  on public.saga_analysis_jobs
  for select
  to authenticated
  using (
    owner_user_id = (select auth.uid())
    and public.saga_current_user_has_active_access()
  );

create policy saga_analysis_runs_owner_select
  on public.saga_analysis_runs
  for select
  to authenticated
  using (
    owner_user_id = (select auth.uid())
    and public.saga_current_user_has_active_access()
  );

create policy saga_characters_owner_select
  on public.saga_characters
  for select
  to authenticated
  using (
    owner_user_id = (select auth.uid())
    and public.saga_current_user_has_active_access()
  );

create policy saga_character_aliases_owner_select
  on public.saga_character_aliases
  for select
  to authenticated
  using (
    owner_user_id = (select auth.uid())
    and public.saga_current_user_has_active_access()
  );

create policy saga_character_mentions_owner_select
  on public.saga_character_mentions
  for select
  to authenticated
  using (
    owner_user_id = (select auth.uid())
    and public.saga_current_user_has_active_access()
  );

create or replace function public.saga_enqueue_analysis_job(
  p_source_id uuid,
  p_kind text,
  p_input_fingerprint text
)
returns table (
  job_id uuid,
  job_status text,
  was_created boolean
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user_id uuid;
  v_project_id uuid;
  v_existing public.saga_analysis_jobs%rowtype;
  v_created public.saga_analysis_jobs%rowtype;
begin
  v_user_id := auth.uid();

  if v_user_id is null or not public.saga_current_user_has_active_access() then
    raise exception using errcode = '42501', message = 'active_account_required';
  end if;

  if p_kind not in ('source_ingestion', 'character_identity') then
    raise exception using errcode = '22023', message = 'invalid_job_kind';
  end if;

  if p_input_fingerprint is null or p_input_fingerprint !~ '^[0-9a-f]{64}$' then
    raise exception using errcode = '22023', message = 'invalid_input_fingerprint';
  end if;

  select source.project_id
    into v_project_id
    from public.saga_sources as source
    where source.id = p_source_id
      and source.owner_user_id = v_user_id;

  if not found then
    raise exception using errcode = 'P0002', message = 'source_not_found';
  end if;

  select job.*
    into v_existing
    from public.saga_analysis_jobs as job
    where job.source_id = p_source_id
      and job.owner_user_id = v_user_id
      and job.kind = p_kind
      and job.input_fingerprint = p_input_fingerprint
      and job.status in ('queued', 'running')
    order by job.created_at desc
    limit 1;

  if found then
    return query select v_existing.id, v_existing.status, false;
    return;
  end if;

  insert into public.saga_analysis_jobs (
    project_id,
    source_id,
    owner_user_id,
    requested_by,
    kind,
    input_fingerprint
  ) values (
    v_project_id,
    p_source_id,
    v_user_id,
    v_user_id,
    p_kind,
    p_input_fingerprint
  )
  returning * into v_created;

  return query select v_created.id, v_created.status, true;
end;
$$;

revoke all on function public.saga_enqueue_analysis_job(uuid,text,text) from public, anon;
grant execute on function public.saga_enqueue_analysis_job(uuid,text,text) to authenticated, service_role;

create or replace function public.saga_claim_analysis_job(
  p_worker_id text,
  p_lease_seconds integer default 300
)
returns table (
  job_id uuid,
  project_id uuid,
  source_id uuid,
  owner_user_id uuid,
  job_kind text,
  input_fingerprint text,
  attempt_count integer,
  lease_token uuid,
  lease_expires_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_job public.saga_analysis_jobs%rowtype;
  v_token uuid;
begin
  if p_worker_id is null or char_length(btrim(p_worker_id)) not between 1 and 256 then
    raise exception using errcode = '22023', message = 'invalid_worker_id';
  end if;

  if p_lease_seconds not between 30 and 3600 then
    raise exception using errcode = '22023', message = 'invalid_lease_seconds';
  end if;

  update public.saga_analysis_jobs as job
    set status = 'failed',
        completed_at = now(),
        lease_token = null,
        lease_owner = null,
        lease_expires_at = null,
        error_code = 'lease_attempts_exhausted',
        error_summary = 'Worker lease expired after the maximum number of attempts.'
    where job.status = 'running'
      and job.lease_expires_at <= now()
      and job.attempt_count >= job.max_attempts;

  select job.*
    into v_job
    from public.saga_analysis_jobs as job
    where (
      (job.status = 'queued' and job.available_at <= now())
      or (
        job.status = 'running'
        and job.lease_expires_at <= now()
        and job.attempt_count < job.max_attempts
      )
    )
    order by job.available_at asc, job.created_at asc
    limit 1
    for update skip locked;

  if not found then
    return;
  end if;

  v_token := gen_random_uuid();

  update public.saga_analysis_jobs as job
    set status = 'running',
        attempt_count = job.attempt_count + 1,
        lease_token = v_token,
        lease_owner = btrim(p_worker_id),
        lease_expires_at = now() + make_interval(secs => p_lease_seconds),
        started_at = coalesce(job.started_at, now()),
        completed_at = null,
        error_code = null,
        error_summary = null
    where job.id = v_job.id
    returning * into v_job;

  return query
    select
      v_job.id,
      v_job.project_id,
      v_job.source_id,
      v_job.owner_user_id,
      v_job.kind,
      v_job.input_fingerprint,
      v_job.attempt_count,
      v_job.lease_token,
      v_job.lease_expires_at;
end;
$$;

revoke all on function public.saga_claim_analysis_job(text,integer) from public, anon, authenticated;
grant execute on function public.saga_claim_analysis_job(text,integer) to service_role;

create or replace function public.saga_renew_analysis_job_lease(
  p_job_id uuid,
  p_lease_token uuid,
  p_lease_seconds integer default 300
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
begin
  if p_lease_seconds not between 30 and 3600 then
    raise exception using errcode = '22023', message = 'invalid_lease_seconds';
  end if;

  update public.saga_analysis_jobs as job
    set lease_expires_at = now() + make_interval(secs => p_lease_seconds)
    where job.id = p_job_id
      and job.status = 'running'
      and job.lease_token = p_lease_token
      and job.lease_expires_at > now();

  return found;
end;
$$;

revoke all on function public.saga_renew_analysis_job_lease(uuid,uuid,integer) from public, anon, authenticated;
grant execute on function public.saga_renew_analysis_job_lease(uuid,uuid,integer) to service_role;

create or replace function public.saga_finish_analysis_job(
  p_job_id uuid,
  p_lease_token uuid,
  p_succeeded boolean,
  p_retry boolean default false,
  p_error_code text default null,
  p_error_summary text default null,
  p_retry_delay_seconds integer default 0
)
returns text
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_job public.saga_analysis_jobs%rowtype;
begin
  if p_retry_delay_seconds not between 0 and 86400 then
    raise exception using errcode = '22023', message = 'invalid_retry_delay';
  end if;

  select job.*
    into v_job
    from public.saga_analysis_jobs as job
    where job.id = p_job_id
    for update;

  if not found
     or v_job.status <> 'running'
     or v_job.lease_token is distinct from p_lease_token
     or v_job.lease_expires_at <= now() then
    return 'stale_lease';
  end if;

  if p_succeeded then
    update public.saga_analysis_jobs as job
      set status = 'succeeded',
          completed_at = now(),
          lease_token = null,
          lease_owner = null,
          lease_expires_at = null,
          error_code = null,
          error_summary = null
      where job.id = p_job_id;
    return 'succeeded';
  end if;

  if p_retry and v_job.attempt_count < v_job.max_attempts then
    update public.saga_analysis_jobs as job
      set status = 'queued',
          available_at = now() + make_interval(secs => p_retry_delay_seconds),
          completed_at = null,
          lease_token = null,
          lease_owner = null,
          lease_expires_at = null,
          error_code = null,
          error_summary = null
      where job.id = p_job_id;
    return 'queued';
  end if;

  update public.saga_analysis_jobs as job
    set status = 'failed',
        completed_at = now(),
        lease_token = null,
        lease_owner = null,
        lease_expires_at = null,
        error_code = coalesce(nullif(btrim(p_error_code), ''), 'analysis_failed'),
        error_summary = nullif(left(btrim(coalesce(p_error_summary, '')), 1000), '')
    where job.id = p_job_id;

  return 'failed';
end;
$$;

revoke all on function public.saga_finish_analysis_job(uuid,uuid,boolean,boolean,text,text,integer) from public, anon, authenticated;
grant execute on function public.saga_finish_analysis_job(uuid,uuid,boolean,boolean,text,text,integer) to service_role;

commit;
