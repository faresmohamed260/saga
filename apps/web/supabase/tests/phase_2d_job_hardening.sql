\set ON_ERROR_STOP on

RESET ROLE;
SET ROLE service_role;

-- Earlier database contracts intentionally exercise automatic ingestion ->
-- identity handoff and may leave queued work. Close only those completed-test
-- leftovers before introducing the dedicated Phase-2D qualification job so
-- the production FIFO claim policy remains unchanged.
UPDATE public.saga_analysis_jobs
SET status = 'cancelled',
    completed_at = now(),
    lease_token = null,
    lease_owner = null,
    lease_expires_at = null
WHERE kind = 'character_identity'
  AND status IN ('queued', 'running');

-- Reuse the completed Phase-2C source fixture but create an independent
-- identity attempt. This isolates lease/retry/idempotency qualification from
-- ingestion setup while exercising the real transactional commit functions.
INSERT INTO public.saga_analysis_jobs (
  id,
  project_id,
  source_id,
  owner_user_id,
  requested_by,
  kind,
  status,
  input_fingerprint
) VALUES (
  'f1000000-0000-4000-8000-000000000001',
  'e3333333-3333-4333-8333-333333333333',
  'e4444444-4444-4444-8444-444444444444',
  'e1111111-1111-4111-8111-111111111111',
  'e1111111-1111-4111-8111-111111111111',
  'character_identity',
  'queued',
  repeat('4', 64)
);

SELECT *
FROM public.saga_claim_analysis_job_kind('phase2d-worker-a', 'character_identity', 300)
WHERE job_id = 'f1000000-0000-4000-8000-000000000001'
\gset first_claim_

DO $$
BEGIN
  IF current_setting('first_claim_job_id', true) IS NULL THEN
    RAISE EXCEPTION 'first Phase 2D identity claim did not return the qualification job';
  END IF;
END;
$$;

-- Simulate a worker that lost ownership without sleeping in CI.
UPDATE public.saga_analysis_jobs
SET lease_expires_at = now() - interval '1 second'
WHERE id = 'f1000000-0000-4000-8000-000000000001';

SELECT *
FROM public.saga_claim_analysis_job_kind('phase2d-worker-b', 'character_identity', 300)
WHERE job_id = 'f1000000-0000-4000-8000-000000000001'
\gset second_claim_

DO $$
DECLARE
  v_attempt integer;
BEGIN
  SELECT attempt_count INTO v_attempt
  FROM public.saga_analysis_jobs
  WHERE id = 'f1000000-0000-4000-8000-000000000001';

  IF current_setting('second_claim_job_id', true) IS NULL
     OR current_setting('second_claim_lease_token') = current_setting('first_claim_lease_token')
     OR v_attempt <> 2 THEN
    RAISE EXCEPTION 'expired identity lease was not reclaimed with a new token/attempt';
  END IF;
END;
$$;

-- The worker that lost the lease must not be able to persist anything.
DO $$
DECLARE
  v_before integer;
  v_after integer;
BEGIN
  SELECT count(*) INTO v_before
  FROM public.saga_analysis_runs
  WHERE job_id = 'f1000000-0000-4000-8000-000000000001';

  BEGIN
    PERFORM public.saga_service_commit_identity_success(
      'f1000000-0000-4000-8000-000000000001',
      current_setting('first_claim_lease_token')::uuid,
      'saga-identity-resolver-v1',
      'phase2d-fixture',
      null,
      'fixture-v1',
      repeat('7', 64),
      repeat('8', 64),
      jsonb_build_array(
        jsonb_build_object(
          'character_key', 'character:ada-vale',
          'canonical_name', 'Ada Vale',
          'admission_tier', 'canonical_seed',
          'evidence_count', 1,
          'aliases', '[]'::jsonb
        )
      ),
      jsonb_build_array(
        jsonb_build_object(
          'evidence_id', 'phase2d-name',
          'character_key', 'character:ada-vale',
          'surface_text', 'Ada Vale',
          'start_offset', 9,
          'end_offset', 17,
          'structural_locator', 'txt:document#identity-fixture',
          'mention_kind', 'proper_name',
          'resolution_state', 'linked',
          'evidence_tier', 'canonical_seed',
          'decision_reason', 'accepted_canonical_seed'
        )
      )
    );
    RAISE EXCEPTION 'expired worker unexpectedly committed identity success';
  EXCEPTION
    WHEN OTHERS THEN
      IF SQLERRM <> 'saga_stale_identity_lease' THEN
        RAISE;
      END IF;
  END;

  SELECT count(*) INTO v_after
  FROM public.saga_analysis_runs
  WHERE job_id = 'f1000000-0000-4000-8000-000000000001';

  IF v_after <> v_before THEN
    RAISE EXCEPTION 'stale identity commit created an analysis run';
  END IF;
END;
$$;

-- Invalid result validation must be atomic: no run, character, alias, mention,
-- or job-state transition may leak from the failed statement.
DO $$
DECLARE
  v_run_count integer;
  v_character_count integer;
  v_mention_count integer;
  v_status text;
  v_lease uuid;
BEGIN
  BEGIN
    PERFORM public.saga_service_commit_identity_success(
      'f1000000-0000-4000-8000-000000000001',
      current_setting('second_claim_lease_token')::uuid,
      'saga-identity-resolver-v1',
      'phase2d-fixture',
      null,
      'fixture-v1',
      repeat('7', 64),
      repeat('9', 64),
      jsonb_build_array(
        jsonb_build_object(
          'character_key', 'character:ada-vale',
          'canonical_name', 'Ada Vale',
          'admission_tier', 'canonical_seed',
          'evidence_count', 1,
          'aliases', '[]'::jsonb
        )
      ),
      jsonb_build_array(
        jsonb_build_object(
          'evidence_id', 'phase2d-invalid-offset',
          'character_key', 'character:ada-vale',
          'surface_text', 'Ada Vale',
          'start_offset', 9,
          'end_offset', 9999,
          'structural_locator', 'txt:document#identity-fixture',
          'mention_kind', 'proper_name',
          'resolution_state', 'linked',
          'evidence_tier', 'canonical_seed',
          'decision_reason', 'accepted_canonical_seed'
        )
      )
    );
    RAISE EXCEPTION 'invalid identity result unexpectedly committed';
  EXCEPTION
    WHEN OTHERS THEN
      IF SQLERRM <> 'saga_invalid_identity_mentions' THEN
        RAISE;
      END IF;
  END;

  SELECT count(*) INTO v_run_count
  FROM public.saga_analysis_runs
  WHERE job_id = 'f1000000-0000-4000-8000-000000000001';

  SELECT count(*) INTO v_character_count
  FROM public.saga_characters
  WHERE source_id = 'e4444444-4444-4444-8444-444444444444'
    AND run_id IN (
      SELECT id FROM public.saga_analysis_runs
      WHERE job_id = 'f1000000-0000-4000-8000-000000000001'
    );

  SELECT count(*) INTO v_mention_count
  FROM public.saga_character_mentions
  WHERE source_id = 'e4444444-4444-4444-8444-444444444444'
    AND run_id IN (
      SELECT id FROM public.saga_analysis_runs
      WHERE job_id = 'f1000000-0000-4000-8000-000000000001'
    );

  SELECT status, lease_token INTO v_status, v_lease
  FROM public.saga_analysis_jobs
  WHERE id = 'f1000000-0000-4000-8000-000000000001';

  IF v_run_count <> 0
     OR v_character_count <> 0
     OR v_mention_count <> 0
     OR v_status <> 'running'
     OR v_lease IS DISTINCT FROM current_setting('second_claim_lease_token')::uuid THEN
    RAISE EXCEPTION 'invalid identity result was not transactionally rolled back';
  END IF;
END;
$$;

SELECT public.saga_service_commit_identity_success(
  'f1000000-0000-4000-8000-000000000001',
  :'second_claim_lease_token',
  'saga-identity-resolver-v1',
  'phase2d-fixture',
  null,
  'fixture-v1',
  repeat('7', 64),
  repeat('a', 64),
  jsonb_build_array(
    jsonb_build_object(
      'character_key', 'character:ada-vale',
      'canonical_name', 'Ada Vale',
      'admission_tier', 'canonical_seed',
      'evidence_count', 1,
      'aliases', jsonb_build_array(
        jsonb_build_object(
          'surface_form', 'Ada',
          'normalized_form', 'ada',
          'evidence_count', 1
        )
      )
    )
  ),
  jsonb_build_array(
    jsonb_build_object(
      'evidence_id', 'phase2d-name',
      'character_key', 'character:ada-vale',
      'surface_text', 'Ada Vale',
      'start_offset', 9,
      'end_offset', 17,
      'structural_locator', 'txt:document#identity-fixture',
      'mention_kind', 'proper_name',
      'resolution_state', 'linked',
      'evidence_tier', 'canonical_seed',
      'decision_reason', 'accepted_canonical_seed'
    )
  )
) AS hardening_run_id
\gset

DO $$
DECLARE
  v_runs integer;
  v_characters integer;
  v_aliases integer;
  v_mentions integer;
BEGIN
  SELECT count(*) INTO v_runs
  FROM public.saga_analysis_runs
  WHERE job_id = 'f1000000-0000-4000-8000-000000000001';

  SELECT count(*) INTO v_characters
  FROM public.saga_characters
  WHERE run_id = current_setting('hardening_run_id')::uuid;

  SELECT count(*) INTO v_aliases
  FROM public.saga_character_aliases
  WHERE run_id = current_setting('hardening_run_id')::uuid;

  SELECT count(*) INTO v_mentions
  FROM public.saga_character_mentions
  WHERE run_id = current_setting('hardening_run_id')::uuid;

  IF v_runs <> 1 OR v_characters <> 1 OR v_aliases <> 1 OR v_mentions <> 1 THEN
    RAISE EXCEPTION 'valid reclaimed lease did not persist exactly one identity result set';
  END IF;
END;
$$;

-- Replaying the same successful commit after the lease has been cleared must
-- fail closed and leave the immutable result set at exactly one run.
DO $$
DECLARE
  v_runs_before integer;
  v_runs_after integer;
BEGIN
  SELECT count(*) INTO v_runs_before
  FROM public.saga_analysis_runs
  WHERE job_id = 'f1000000-0000-4000-8000-000000000001';

  BEGIN
    PERFORM public.saga_service_commit_identity_success(
      'f1000000-0000-4000-8000-000000000001',
      current_setting('second_claim_lease_token')::uuid,
      'saga-identity-resolver-v1',
      'phase2d-fixture',
      null,
      'fixture-v1',
      repeat('7', 64),
      repeat('a', 64),
      jsonb_build_array(
        jsonb_build_object(
          'character_key', 'character:ada-vale',
          'canonical_name', 'Ada Vale',
          'admission_tier', 'canonical_seed',
          'evidence_count', 1,
          'aliases', '[]'::jsonb
        )
      ),
      jsonb_build_array(
        jsonb_build_object(
          'evidence_id', 'phase2d-name',
          'character_key', 'character:ada-vale',
          'surface_text', 'Ada Vale',
          'start_offset', 9,
          'end_offset', 17,
          'structural_locator', 'txt:document#identity-fixture',
          'mention_kind', 'proper_name',
          'resolution_state', 'linked',
          'evidence_tier', 'canonical_seed',
          'decision_reason', 'accepted_canonical_seed'
        )
      )
    );
    RAISE EXCEPTION 'duplicate identity success unexpectedly committed';
  EXCEPTION
    WHEN OTHERS THEN
      IF SQLERRM <> 'saga_stale_identity_lease' THEN
        RAISE;
      END IF;
  END;

  SELECT count(*) INTO v_runs_after
  FROM public.saga_analysis_runs
  WHERE job_id = 'f1000000-0000-4000-8000-000000000001';

  IF v_runs_before <> 1 OR v_runs_after <> 1 THEN
    RAISE EXCEPTION 'duplicate commit changed immutable identity run cardinality';
  END IF;
END;
$$;

RESET ROLE;
