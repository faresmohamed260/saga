begin;

alter table public.saga_sources
  add column upload_completed_at timestamptz;

create table public.saga_normalized_sources (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null,
  project_id uuid not null,
  source_id uuid not null,
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  normalization_version text not null,
  normalized_sha256 text not null,
  total_characters bigint not null check (total_characters >= 0),
  section_count integer not null check (section_count > 0),
  created_at timestamptz not null default now(),
  constraint saga_normalized_sources_run_scope_fk
    foreign key (run_id, project_id, source_id, owner_user_id)
    references public.saga_analysis_runs(id, project_id, source_id, owner_user_id)
    on delete cascade,
  constraint saga_normalized_sources_version_check
    check (char_length(btrim(normalization_version)) between 1 and 160),
  constraint saga_normalized_sources_sha256_check
    check (normalized_sha256 ~ '^[0-9a-f]{64}$'),
  constraint saga_normalized_sources_run_unique unique (run_id),
  constraint saga_normalized_sources_identity_scope_unique
    unique (id, run_id, project_id, source_id, owner_user_id)
);

create index saga_normalized_sources_source_created_idx
  on public.saga_normalized_sources (source_id, created_at desc);

create table public.saga_normalized_sections (
  id uuid primary key default gen_random_uuid(),
  normalized_source_id uuid not null,
  run_id uuid not null,
  project_id uuid not null,
  source_id uuid not null,
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  stable_key text not null,
  ordinal integer not null check (ordinal >= 0),
  section_kind text not null check (section_kind in ('document', 'chapter', 'section')),
  title text,
  source_locator text not null,
  start_offset bigint not null check (start_offset >= 0),
  end_offset bigint not null check (end_offset > start_offset),
  normalized_text text not null,
  created_at timestamptz not null default now(),
  constraint saga_normalized_sections_source_scope_fk
    foreign key (normalized_source_id, run_id, project_id, source_id, owner_user_id)
    references public.saga_normalized_sources(id, run_id, project_id, source_id, owner_user_id)
    on delete cascade,
  constraint saga_normalized_sections_stable_key_check
    check (char_length(btrim(stable_key)) between 1 and 256),
  constraint saga_normalized_sections_title_check
    check (title is null or char_length(title) <= 1000),
  constraint saga_normalized_sections_locator_check
    check (char_length(btrim(source_locator)) between 1 and 2000),
  constraint saga_normalized_sections_text_check
    check (char_length(normalized_text) = end_offset - start_offset),
  constraint saga_normalized_sections_ordinal_unique unique (normalized_source_id, ordinal),
  constraint saga_normalized_sections_stable_key_unique unique (normalized_source_id, stable_key)
);

create index saga_normalized_sections_source_ordinal_idx
  on public.saga_normalized_sections (normalized_source_id, ordinal);

alter table public.saga_normalized_sources enable row level security;
alter table public.saga_normalized_sources force row level security;
alter table public.saga_normalized_sections enable row level security;
alter table public.saga_normalized_sections force row level security;

revoke all on table public.saga_normalized_sources from public, anon, authenticated;
revoke all on table public.saga_normalized_sections from public, anon, authenticated;

grant select on table public.saga_normalized_sources to authenticated;
grant select on table public.saga_normalized_sections to authenticated;
grant select, insert on table public.saga_normalized_sources to service_role;
grant select, insert on table public.saga_normalized_sections to service_role;

create policy saga_normalized_sources_owner_select
  on public.saga_normalized_sources
  for select
  to authenticated
  using (
    owner_user_id = (select auth.uid())
    and public.saga_current_user_has_active_access()
  );

create policy saga_normalized_sections_owner_select
  on public.saga_normalized_sections
  for select
  to authenticated
  using (
    owner_user_id = (select auth.uid())
    and public.saga_current_user_has_active_access()
  );

create or replace function public.saga_create_source_upload_intent(
  p_project_id uuid,
  p_original_filename text,
  p_display_name text,
  p_source_format text,
  p_byte_size bigint,
  p_content_sha256 text
)
returns table (
  source_id uuid,
  object_key text,
  media_type text
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_owner_user_id uuid := (select auth.uid());
  v_source_id uuid := gen_random_uuid();
  v_object_key text;
  v_media_type text;
begin
  if v_owner_user_id is null or not public.saga_current_user_has_active_access() then
    raise exception 'saga_active_account_required';
  end if;

  if not exists (
    select 1
    from public.saga_projects as project
    where project.id = p_project_id
      and project.owner_user_id = v_owner_user_id
      and project.status = 'active'
  ) then
    raise exception 'saga_project_not_found';
  end if;

  if p_source_format = 'txt' then
    v_media_type := 'text/plain';
  elsif p_source_format = 'epub' then
    v_media_type := 'application/epub+zip';
  else
    raise exception 'saga_invalid_source_format';
  end if;

  if p_original_filename is null
     or char_length(btrim(p_original_filename)) not between 1 and 512
     or p_display_name is null
     or char_length(btrim(p_display_name)) not between 1 and 512
     or p_byte_size is null
     or p_byte_size <= 0
     or p_content_sha256 is null
     or p_content_sha256 !~ '^[0-9a-f]{64}$' then
    raise exception 'saga_invalid_source_metadata';
  end if;

  v_object_key := format(
    'sources/%s/%s/%s/%s/original',
    v_owner_user_id,
    p_project_id,
    v_source_id,
    p_content_sha256
  );

  insert into public.saga_sources (
    id,
    project_id,
    owner_user_id,
    original_filename,
    display_name,
    source_format,
    media_type,
    byte_size,
    content_sha256,
    object_key,
    ingestion_status
  ) values (
    v_source_id,
    p_project_id,
    v_owner_user_id,
    btrim(p_original_filename),
    btrim(p_display_name),
    p_source_format,
    v_media_type,
    p_byte_size,
    p_content_sha256,
    v_object_key,
    'pending_upload'
  );

  return query select v_source_id, v_object_key, v_media_type;
end;
$$;

revoke all on function public.saga_create_source_upload_intent(uuid,text,text,text,bigint,text)
  from public, anon, service_role;
grant execute on function public.saga_create_source_upload_intent(uuid,text,text,text,bigint,text)
  to authenticated;

create or replace function public.saga_service_finalize_source_upload(
  p_source_id uuid,
  p_owner_user_id uuid,
  p_observed_byte_size bigint,
  p_observed_content_type text,
  p_observed_sha256_metadata text,
  p_observed_source_id_metadata text
)
returns table (
  source_id uuid,
  source_status text,
  job_id uuid,
  result_failure_code text
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_source public.saga_sources%rowtype;
  v_job_id uuid;
begin
  select source.*
    into v_source
  from public.saga_sources as source
  where source.id = p_source_id
    and source.owner_user_id = p_owner_user_id
  for update;

  if not found then
    raise exception 'saga_source_not_found';
  end if;

  if v_source.ingestion_status = 'failed' then
    return query
      select v_source.id, v_source.ingestion_status, null::uuid, v_source.failure_code;
    return;
  end if;

  if v_source.ingestion_status in ('uploaded', 'processing', 'ready') then
    select job.id
      into v_job_id
    from public.saga_analysis_jobs as job
    where job.source_id = v_source.id
      and job.kind = 'source_ingestion'
    order by job.created_at desc
    limit 1;

    return query
      select v_source.id, v_source.ingestion_status, v_job_id, null::text;
    return;
  end if;

  if v_source.ingestion_status <> 'pending_upload' then
    raise exception 'saga_source_upload_state_conflict';
  end if;

  if p_observed_byte_size is distinct from v_source.byte_size
     or p_observed_content_type is distinct from v_source.media_type
     or p_observed_sha256_metadata is distinct from v_source.content_sha256
     or p_observed_source_id_metadata is distinct from v_source.id::text then
    update public.saga_sources as source
      set ingestion_status = 'failed',
          failure_code = 'upload_metadata_mismatch',
          upload_completed_at = now()
    where source.id = v_source.id;

    return query
      select v_source.id, 'failed'::text, null::uuid, 'upload_metadata_mismatch'::text;
    return;
  end if;

  update public.saga_sources as source
    set ingestion_status = 'uploaded',
        failure_code = null,
        upload_completed_at = now()
  where source.id = v_source.id;

  insert into public.saga_analysis_jobs (
    project_id,
    source_id,
    owner_user_id,
    requested_by,
    kind,
    input_fingerprint
  ) values (
    v_source.project_id,
    v_source.id,
    v_source.owner_user_id,
    v_source.owner_user_id,
    'source_ingestion',
    v_source.content_sha256
  )
  returning id into v_job_id;

  return query
    select v_source.id, 'uploaded'::text, v_job_id, null::text;
end;
$$;

revoke all on function public.saga_service_finalize_source_upload(uuid,uuid,bigint,text,text,text)
  from public, anon, authenticated;
grant execute on function public.saga_service_finalize_source_upload(uuid,uuid,bigint,text,text,text)
  to service_role;

create or replace function public.saga_service_mark_source_processing(
  p_job_id uuid,
  p_lease_token uuid
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_job public.saga_analysis_jobs%rowtype;
begin
  select job.*
    into v_job
  from public.saga_analysis_jobs as job
  where job.id = p_job_id
  for update;

  if not found
     or v_job.kind <> 'source_ingestion'
     or v_job.status <> 'running'
     or v_job.lease_token is distinct from p_lease_token
     or v_job.lease_expires_at is null
     or v_job.lease_expires_at <= now() then
    return false;
  end if;

  update public.saga_sources as source
    set ingestion_status = 'processing',
        failure_code = null
  where source.id = v_job.source_id
    and source.project_id = v_job.project_id
    and source.owner_user_id = v_job.owner_user_id
    and source.ingestion_status in ('uploaded', 'processing');

  return found;
end;
$$;

revoke all on function public.saga_service_mark_source_processing(uuid,uuid)
  from public, anon, authenticated;
grant execute on function public.saga_service_mark_source_processing(uuid,uuid)
  to service_role;

create or replace function public.saga_service_commit_ingestion_success(
  p_job_id uuid,
  p_lease_token uuid,
  p_normalization_version text,
  p_config_fingerprint text,
  p_normalized_sha256 text,
  p_output_fingerprint text,
  p_sections jsonb
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_job public.saga_analysis_jobs%rowtype;
  v_run_id uuid := gen_random_uuid();
  v_normalized_source_id uuid := gen_random_uuid();
  v_section_count integer;
  v_total_characters bigint;
begin
  select job.*
    into v_job
  from public.saga_analysis_jobs as job
  where job.id = p_job_id
  for update;

  if not found
     or v_job.kind <> 'source_ingestion'
     or v_job.status <> 'running'
     or v_job.lease_token is distinct from p_lease_token
     or v_job.lease_expires_at is null
     or v_job.lease_expires_at <= now() then
    raise exception 'saga_stale_ingestion_lease';
  end if;

  if p_normalization_version is null
     or char_length(btrim(p_normalization_version)) not between 1 and 160
     or p_config_fingerprint is null
     or p_config_fingerprint !~ '^[0-9a-f]{64}$'
     or p_normalized_sha256 is null
     or p_normalized_sha256 !~ '^[0-9a-f]{64}$'
     or p_output_fingerprint is null
     or p_output_fingerprint !~ '^[0-9a-f]{64}$'
     or p_sections is null
     or jsonb_typeof(p_sections) <> 'array'
     or jsonb_array_length(p_sections) = 0 then
    raise exception 'saga_invalid_ingestion_result';
  end if;

  with section_rows as (
    select *
    from jsonb_to_recordset(p_sections) as section(
      stable_key text,
      ordinal integer,
      section_kind text,
      title text,
      source_locator text,
      start_offset bigint,
      end_offset bigint,
      normalized_text text
    )
  ), ordered as (
    select
      section_rows.*,
      lag(end_offset) over (order by ordinal) as previous_end
    from section_rows
  )
  select count(*)::integer, max(end_offset)
    into v_section_count, v_total_characters
  from ordered
  where stable_key is not null
    and ordinal is not null
    and section_kind is not null
    and source_locator is not null
    and start_offset is not null
    and end_offset is not null
    and normalized_text is not null;

  if v_section_count <> jsonb_array_length(p_sections)
     or exists (
       select 1
       from (
         select
           ordinal,
           start_offset,
           end_offset,
           normalized_text,
           lag(end_offset) over (order by ordinal) as previous_end
         from jsonb_to_recordset(p_sections) as section(
           stable_key text,
           ordinal integer,
           section_kind text,
           title text,
           source_locator text,
           start_offset bigint,
           end_offset bigint,
           normalized_text text
         )
       ) as ordered
       where ordinal < 0
          or end_offset <= start_offset
          or char_length(normalized_text) <> end_offset - start_offset
          or (ordinal = 0 and start_offset <> 0)
          or (ordinal > 0 and start_offset <> previous_end + 2)
     )
     or exists (
       select 1
       from (
         select
           count(*) as row_count,
           count(distinct ordinal) as distinct_ordinals,
           min(ordinal) as min_ordinal,
           max(ordinal) as max_ordinal
         from jsonb_to_recordset(p_sections) as section(ordinal integer)
       ) as ordinals
       where min_ordinal <> 0
          or max_ordinal <> row_count - 1
          or distinct_ordinals <> row_count
     ) then
    raise exception 'saga_invalid_ingestion_sections';
  end if;

  insert into public.saga_analysis_runs (
    id,
    job_id,
    project_id,
    source_id,
    owner_user_id,
    status,
    input_fingerprint,
    normalized_input_fingerprint,
    engine_version,
    config_fingerprint,
    output_fingerprint,
    started_at,
    completed_at
  ) values (
    v_run_id,
    v_job.id,
    v_job.project_id,
    v_job.source_id,
    v_job.owner_user_id,
    'succeeded',
    v_job.input_fingerprint,
    p_normalized_sha256,
    btrim(p_normalization_version),
    p_config_fingerprint,
    p_output_fingerprint,
    v_job.started_at,
    now()
  );

  insert into public.saga_normalized_sources (
    id,
    run_id,
    project_id,
    source_id,
    owner_user_id,
    normalization_version,
    normalized_sha256,
    total_characters,
    section_count
  ) values (
    v_normalized_source_id,
    v_run_id,
    v_job.project_id,
    v_job.source_id,
    v_job.owner_user_id,
    btrim(p_normalization_version),
    p_normalized_sha256,
    v_total_characters,
    v_section_count
  );

  insert into public.saga_normalized_sections (
    normalized_source_id,
    run_id,
    project_id,
    source_id,
    owner_user_id,
    stable_key,
    ordinal,
    section_kind,
    title,
    source_locator,
    start_offset,
    end_offset,
    normalized_text
  )
  select
    v_normalized_source_id,
    v_run_id,
    v_job.project_id,
    v_job.source_id,
    v_job.owner_user_id,
    section.stable_key,
    section.ordinal,
    section.section_kind,
    section.title,
    section.source_locator,
    section.start_offset,
    section.end_offset,
    section.normalized_text
  from jsonb_to_recordset(p_sections) as section(
    stable_key text,
    ordinal integer,
    section_kind text,
    title text,
    source_locator text,
    start_offset bigint,
    end_offset bigint,
    normalized_text text
  )
  order by section.ordinal;

  update public.saga_sources as source
    set ingestion_status = 'ready',
        failure_code = null
  where source.id = v_job.source_id
    and source.project_id = v_job.project_id
    and source.owner_user_id = v_job.owner_user_id;

  update public.saga_analysis_jobs as job
    set status = 'succeeded',
        completed_at = now(),
        lease_token = null,
        lease_owner = null,
        lease_expires_at = null,
        error_code = null,
        error_summary = null
  where job.id = v_job.id;

  return v_run_id;
end;
$$;

revoke all on function public.saga_service_commit_ingestion_success(uuid,uuid,text,text,text,text,jsonb)
  from public, anon, authenticated;
grant execute on function public.saga_service_commit_ingestion_success(uuid,uuid,text,text,text,text,jsonb)
  to service_role;

create or replace function public.saga_service_commit_ingestion_failure(
  p_job_id uuid,
  p_lease_token uuid,
  p_engine_version text,
  p_config_fingerprint text,
  p_failure_code text,
  p_error_summary text default null
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_job public.saga_analysis_jobs%rowtype;
  v_run_id uuid := gen_random_uuid();
begin
  select job.*
    into v_job
  from public.saga_analysis_jobs as job
  where job.id = p_job_id
  for update;

  if not found
     or v_job.kind <> 'source_ingestion'
     or v_job.status <> 'running'
     or v_job.lease_token is distinct from p_lease_token
     or v_job.lease_expires_at is null
     or v_job.lease_expires_at <= now() then
    raise exception 'saga_stale_ingestion_lease';
  end if;

  if p_engine_version is null
     or char_length(btrim(p_engine_version)) not between 1 and 160
     or p_config_fingerprint is null
     or p_config_fingerprint !~ '^[0-9a-f]{64}$'
     or p_failure_code is null
     or char_length(btrim(p_failure_code)) not between 1 and 128
     or (p_error_summary is not null and char_length(p_error_summary) > 1000) then
    raise exception 'saga_invalid_ingestion_failure';
  end if;

  insert into public.saga_analysis_runs (
    id,
    job_id,
    project_id,
    source_id,
    owner_user_id,
    status,
    input_fingerprint,
    engine_version,
    config_fingerprint,
    failure_code,
    started_at,
    completed_at
  ) values (
    v_run_id,
    v_job.id,
    v_job.project_id,
    v_job.source_id,
    v_job.owner_user_id,
    'failed',
    v_job.input_fingerprint,
    btrim(p_engine_version),
    p_config_fingerprint,
    btrim(p_failure_code),
    v_job.started_at,
    now()
  );

  update public.saga_sources as source
    set ingestion_status = 'failed',
        failure_code = btrim(p_failure_code)
  where source.id = v_job.source_id
    and source.project_id = v_job.project_id
    and source.owner_user_id = v_job.owner_user_id;

  update public.saga_analysis_jobs as job
    set status = 'failed',
        completed_at = now(),
        lease_token = null,
        lease_owner = null,
        lease_expires_at = null,
        error_code = btrim(p_failure_code),
        error_summary = p_error_summary
  where job.id = v_job.id;

  return v_run_id;
end;
$$;

revoke all on function public.saga_service_commit_ingestion_failure(uuid,uuid,text,text,text,text)
  from public, anon, authenticated;
grant execute on function public.saga_service_commit_ingestion_failure(uuid,uuid,text,text,text,text)
  to service_role;

commit;
