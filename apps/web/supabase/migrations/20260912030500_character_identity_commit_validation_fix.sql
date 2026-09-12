begin;

-- The initial Phase-2C commit function duplicated provider-evidence uniqueness
-- validation in PL/pgSQL even though the result table already enforces the
-- invariant with saga_character_mentions_run_provider_evidence_unique. Keep
-- semantic/shape/offset/character-link validation here and let the unique
-- index enforce duplicate evidence IDs atomically during the same transaction.
create or replace function public.saga_service_commit_identity_success(
  p_job_id uuid,
  p_lease_token uuid,
  p_resolver_version text,
  p_provider_name text,
  p_provider_model text,
  p_provider_revision text,
  p_config_fingerprint text,
  p_output_fingerprint text,
  p_characters jsonb,
  p_mentions jsonb
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_job public.saga_analysis_jobs%rowtype;
  v_run_id uuid := gen_random_uuid();
  v_normalized_sha256 text;
  v_total_characters bigint;
begin
  select job.*
    into v_job
  from public.saga_analysis_jobs as job
  where job.id = p_job_id
  for update;

  if not found
     or v_job.kind <> 'character_identity'
     or v_job.status <> 'running'
     or v_job.lease_token is distinct from p_lease_token
     or v_job.lease_expires_at is null
     or v_job.lease_expires_at <= now() then
    raise exception 'saga_stale_identity_lease';
  end if;

  if p_resolver_version is null
     or char_length(btrim(p_resolver_version)) not between 1 and 160
     or p_provider_name is null
     or char_length(btrim(p_provider_name)) not between 1 and 160
     or p_provider_revision is null
     or char_length(btrim(p_provider_revision)) not between 1 and 160
     or (p_provider_model is not null and char_length(btrim(p_provider_model)) not between 1 and 256)
     or p_config_fingerprint is null
     or p_config_fingerprint !~ '^[0-9a-f]{64}$'
     or p_output_fingerprint is null
     or p_output_fingerprint !~ '^[0-9a-f]{64}$'
     or p_characters is null
     or jsonb_typeof(p_characters) <> 'array'
     or p_mentions is null
     or jsonb_typeof(p_mentions) <> 'array' then
    raise exception 'saga_invalid_identity_result';
  end if;

  select normalized.normalized_sha256, normalized.total_characters
    into v_normalized_sha256, v_total_characters
  from public.saga_normalized_sources as normalized
  join public.saga_analysis_runs as ingestion_run
    on ingestion_run.id = normalized.run_id
   and ingestion_run.project_id = normalized.project_id
   and ingestion_run.source_id = normalized.source_id
   and ingestion_run.owner_user_id = normalized.owner_user_id
  where normalized.project_id = v_job.project_id
    and normalized.source_id = v_job.source_id
    and normalized.owner_user_id = v_job.owner_user_id
    and ingestion_run.status = 'succeeded'
    and ingestion_run.output_fingerprint = v_job.input_fingerprint
  order by ingestion_run.completed_at desc, ingestion_run.created_at desc
  limit 1;

  if v_normalized_sha256 is null then
    raise exception 'saga_identity_input_not_found';
  end if;

  if exists (
    select 1
    from jsonb_to_recordset(p_characters) as character(
      character_key text,
      canonical_name text,
      admission_tier text,
      evidence_count integer,
      aliases jsonb
    )
    where character.character_key is null
       or char_length(btrim(character.character_key)) not between 1 and 160
       or character.canonical_name is null
       or char_length(btrim(character.canonical_name)) not between 1 and 512
       or character.admission_tier not in ('canonical_seed', 'stabilized')
       or character.evidence_count is null
       or character.evidence_count < 1
       or character.aliases is null
       or jsonb_typeof(character.aliases) <> 'array'
  ) or exists (
    select 1
    from (
      select character_key, count(*) as row_count
      from jsonb_to_recordset(p_characters) as character(character_key text)
      group by character_key
      having count(*) > 1
    ) as duplicates
  ) then
    raise exception 'saga_invalid_identity_characters';
  end if;

  if exists (
    select 1
    from jsonb_array_elements(p_characters) as character_json
    cross join lateral jsonb_to_recordset(character_json->'aliases') as alias(
      surface_form text,
      normalized_form text,
      evidence_count integer
    )
    where alias.surface_form is null
       or char_length(btrim(alias.surface_form)) not between 1 and 512
       or alias.normalized_form is null
       or char_length(btrim(alias.normalized_form)) not between 1 and 512
       or alias.evidence_count is null
       or alias.evidence_count < 1
  ) then
    raise exception 'saga_invalid_identity_aliases';
  end if;

  if exists (
    select 1
    from jsonb_to_recordset(p_mentions) as mention(
      evidence_id text,
      character_key text,
      surface_text text,
      start_offset bigint,
      end_offset bigint,
      structural_locator text,
      mention_kind text,
      resolution_state text,
      evidence_tier text,
      decision_reason text
    )
    where mention.evidence_id is null
       or char_length(btrim(mention.evidence_id)) not between 1 and 256
       or mention.surface_text is null
       or char_length(mention.surface_text) not between 1 and 2000
       or mention.start_offset is null
       or mention.start_offset < 0
       or mention.end_offset is null
       or mention.end_offset <= mention.start_offset
       or mention.end_offset > v_total_characters
       or mention.mention_kind not in ('proper_name', 'nominal', 'pronoun')
       or mention.resolution_state not in ('linked', 'unresolved', 'quarantined')
       or mention.evidence_tier not in ('canonical_seed', 'attachment', 'quarantined')
       or mention.decision_reason is null
       or char_length(btrim(mention.decision_reason)) not between 1 and 1000
       or (mention.resolution_state = 'linked' and mention.character_key is null)
       or (mention.resolution_state in ('unresolved', 'quarantined') and mention.character_key is not null)
       or (
         mention.character_key is not null
         and not exists (
           select 1
           from jsonb_to_recordset(p_characters) as character(character_key text)
           where character.character_key = mention.character_key
         )
       )
  ) then
    raise exception 'saga_invalid_identity_mentions';
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
    provider_name,
    provider_model,
    provider_revision,
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
    v_normalized_sha256,
    btrim(p_resolver_version),
    btrim(p_provider_name),
    case when p_provider_model is null then null else btrim(p_provider_model) end,
    btrim(p_provider_revision),
    p_config_fingerprint,
    p_output_fingerprint,
    v_job.started_at,
    now()
  );

  insert into public.saga_characters (
    run_id,
    project_id,
    source_id,
    owner_user_id,
    resolver_key,
    canonical_name,
    admission_tier,
    evidence_count
  )
  select
    v_run_id,
    v_job.project_id,
    v_job.source_id,
    v_job.owner_user_id,
    character.character_key,
    btrim(character.canonical_name),
    character.admission_tier,
    character.evidence_count
  from jsonb_to_recordset(p_characters) as character(
    character_key text,
    canonical_name text,
    admission_tier text,
    evidence_count integer,
    aliases jsonb
  );

  insert into public.saga_character_aliases (
    character_id,
    run_id,
    project_id,
    source_id,
    owner_user_id,
    surface_form,
    normalized_form,
    evidence_count
  )
  select
    stored_character.id,
    v_run_id,
    v_job.project_id,
    v_job.source_id,
    v_job.owner_user_id,
    btrim(alias.surface_form),
    btrim(alias.normalized_form),
    alias.evidence_count
  from jsonb_array_elements(p_characters) as character_json
  cross join lateral jsonb_to_record(character_json) as character(character_key text, aliases jsonb)
  cross join lateral jsonb_to_recordset(character.aliases) as alias(
    surface_form text,
    normalized_form text,
    evidence_count integer
  )
  join public.saga_characters as stored_character
    on stored_character.run_id = v_run_id
   and stored_character.resolver_key = character.character_key;

  insert into public.saga_character_mentions (
    run_id,
    project_id,
    source_id,
    owner_user_id,
    character_id,
    provider_evidence_id,
    surface_text,
    start_offset,
    end_offset,
    structural_locator,
    mention_kind,
    resolution_state,
    evidence_tier,
    decision_reason
  )
  select
    v_run_id,
    v_job.project_id,
    v_job.source_id,
    v_job.owner_user_id,
    stored_character.id,
    mention.evidence_id,
    mention.surface_text,
    mention.start_offset,
    mention.end_offset,
    mention.structural_locator,
    mention.mention_kind,
    mention.resolution_state,
    mention.evidence_tier,
    mention.decision_reason
  from jsonb_to_recordset(p_mentions) as mention(
    evidence_id text,
    character_key text,
    surface_text text,
    start_offset bigint,
    end_offset bigint,
    structural_locator text,
    mention_kind text,
    resolution_state text,
    evidence_tier text,
    decision_reason text
  )
  left join public.saga_characters as stored_character
    on stored_character.run_id = v_run_id
   and stored_character.resolver_key = mention.character_key
  order by mention.start_offset, mention.end_offset, mention.evidence_id;

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

revoke all on function public.saga_service_commit_identity_success(uuid,uuid,text,text,text,text,text,text,jsonb,jsonb)
  from public, anon, authenticated;
grant execute on function public.saga_service_commit_identity_success(uuid,uuid,text,text,text,text,text,text,jsonb,jsonb)
  to service_role;

commit;
