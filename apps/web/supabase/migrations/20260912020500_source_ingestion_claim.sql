begin;

create or replace function public.saga_claim_analysis_job_kind(
  p_worker_id text,
  p_kind text,
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

  if p_kind not in ('source_ingestion', 'character_identity') then
    raise exception using errcode = '22023', message = 'invalid_job_kind';
  end if;

  if p_lease_seconds not between 30 and 3600 then
    raise exception using errcode = '22023', message = 'invalid_lease_seconds';
  end if;

  select job.*
    into v_job
    from public.saga_analysis_jobs as job
    where job.kind = p_kind
      and job.attempt_count < job.max_attempts
      and (
        (job.status = 'queued' and job.available_at <= now())
        or (
          job.status = 'running'
          and job.lease_expires_at <= now()
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
  returning job.* into v_job;

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

revoke all on function public.saga_claim_analysis_job_kind(text,text,integer)
  from public, anon, authenticated;
grant execute on function public.saga_claim_analysis_job_kind(text,text,integer)
  to service_role;

commit;
