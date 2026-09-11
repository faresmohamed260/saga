\set ON_ERROR_STOP on

DO $$
DECLARE
  v_table text;
BEGIN
  FOREACH v_table IN ARRAY ARRAY[
    'saga_projects',
    'saga_sources',
    'saga_analysis_jobs',
    'saga_analysis_runs',
    'saga_characters',
    'saga_character_aliases',
    'saga_character_mentions'
  ]
  LOOP
    IF EXISTS (
      SELECT 1
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE n.nspname = 'public'
        AND c.relname = v_table
        AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity)
    ) THEN
      RAISE EXCEPTION '% must enable and force RLS', v_table;
    END IF;
  END LOOP;

  IF NOT has_table_privilege('authenticated', 'public.saga_projects', 'select')
     OR NOT has_table_privilege('authenticated', 'public.saga_projects', 'insert')
     OR NOT has_table_privilege('authenticated', 'public.saga_projects', 'update')
     OR NOT has_table_privilege('authenticated', 'public.saga_projects', 'delete') THEN
    RAISE EXCEPTION 'authenticated project privileges are incomplete';
  END IF;

  IF has_table_privilege('authenticated', 'public.saga_sources', 'insert')
     OR has_table_privilege('authenticated', 'public.saga_analysis_jobs', 'insert')
     OR has_table_privilege('authenticated', 'public.saga_analysis_runs', 'insert')
     OR has_table_privilege('authenticated', 'public.saga_characters', 'insert') THEN
    RAISE EXCEPTION 'authenticated role unexpectedly has result/control-plane write privileges';
  END IF;

  IF has_table_privilege('service_role', 'public.saga_analysis_runs', 'update')
     OR has_table_privilege('service_role', 'public.saga_analysis_runs', 'delete')
     OR has_table_privilege('service_role', 'public.saga_characters', 'update')
     OR has_table_privilege('service_role', 'public.saga_character_mentions', 'delete') THEN
    RAISE EXCEPTION 'immutable analysis/result tables expose mutation privileges to the worker role';
  END IF;

  IF NOT has_function_privilege('authenticated', 'public.saga_enqueue_analysis_job(uuid,text,text)', 'execute') THEN
    RAISE EXCEPTION 'authenticated users cannot enqueue owned analysis work';
  END IF;

  IF has_function_privilege('authenticated', 'public.saga_claim_analysis_job(text,integer)', 'execute')
     OR has_function_privilege('authenticated', 'public.saga_finish_analysis_job(uuid,uuid,boolean,boolean,text,text,integer)', 'execute') THEN
    RAISE EXCEPTION 'browser role unexpectedly has worker lease authority';
  END IF;

  IF NOT has_function_privilege('service_role', 'public.saga_claim_analysis_job(text,integer)', 'execute')
     OR NOT has_function_privilege('service_role', 'public.saga_renew_analysis_job_lease(uuid,uuid,integer)', 'execute')
     OR NOT has_function_privilege('service_role', 'public.saga_finish_analysis_job(uuid,uuid,boolean,boolean,text,text,integer)', 'execute') THEN
    RAISE EXCEPTION 'service_role lacks Phase 2 worker lease functions';
  END IF;
END;
$$;

INSERT INTO auth.users (id, email) VALUES
  ('a1111111-1111-4111-8111-111111111111', 'phase2-owner@example.com'),
  ('a2222222-2222-4222-8222-222222222222', 'phase2-other@example.com'),
  ('a3333333-3333-4333-8333-333333333333', 'phase2-suspended@example.com');

INSERT INTO public.saga_account_access (
  user_id,
  role,
  status,
  invited_by,
  accepted_at,
  updated_by
) VALUES
  ('a1111111-1111-4111-8111-111111111111', 'member', 'active', null, now(), null),
  ('a2222222-2222-4222-8222-222222222222', 'member', 'active', null, now(), null),
  ('a3333333-3333-4333-8333-333333333333', 'member', 'suspended', null, now(), null);

SET ROLE authenticated;
SELECT set_config('request.jwt.claim.sub', 'a1111111-1111-4111-8111-111111111111', false);

INSERT INTO public.saga_projects (
  id,
  owner_user_id,
  title,
  description
) VALUES (
  'c1111111-1111-4111-8111-111111111111',
  'a1111111-1111-4111-8111-111111111111',
  'Phase 2 Fixture Project',
  'Owner-visible story intelligence fixture.'
);

DO $$
DECLARE
  v_count integer;
BEGIN
  SELECT count(*) INTO v_count FROM public.saga_projects;
  IF v_count <> 1 THEN
    RAISE EXCEPTION 'owner should see exactly one project, saw %', v_count;
  END IF;
END;
$$;

SELECT set_config('request.jwt.claim.sub', 'a2222222-2222-4222-8222-222222222222', false);

DO $$
DECLARE
  v_count integer;
BEGIN
  SELECT count(*) INTO v_count FROM public.saga_projects;
  IF v_count <> 0 THEN
    RAISE EXCEPTION 'cross-user project read leaked % rows', v_count;
  END IF;

  BEGIN
    INSERT INTO public.saga_projects (owner_user_id, title)
    VALUES ('a1111111-1111-4111-8111-111111111111', 'Forbidden Project');
    RAISE EXCEPTION 'cross-user project insert unexpectedly succeeded';
  EXCEPTION
    WHEN insufficient_privilege THEN
      NULL;
  END;
END;
$$;

SELECT set_config('request.jwt.claim.sub', 'a3333333-3333-4333-8333-333333333333', false);

DO $$
DECLARE
  v_count integer;
BEGIN
  SELECT count(*) INTO v_count FROM public.saga_projects;
  IF v_count <> 0 THEN
    RAISE EXCEPTION 'suspended user should not see project rows';
  END IF;

  BEGIN
    INSERT INTO public.saga_projects (owner_user_id, title)
    VALUES ('a3333333-3333-4333-8333-333333333333', 'Suspended Project');
    RAISE EXCEPTION 'suspended user project insert unexpectedly succeeded';
  EXCEPTION
    WHEN insufficient_privilege THEN
      NULL;
  END;
END;
$$;

RESET ROLE;
SET ROLE service_role;

INSERT INTO public.saga_sources (
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
) VALUES (
  'c2222222-2222-4222-8222-222222222222',
  'c1111111-1111-4111-8111-111111111111',
  'a1111111-1111-4111-8111-111111111111',
  'fixture.txt',
  'Fixture Story',
  'txt',
  'text/plain; charset=utf-8',
  128,
  repeat('a', 64),
  'sources/a1111111-1111-4111-8111-111111111111/c1111111-1111-4111-8111-111111111111/c2222222-2222-4222-8222-222222222222/original',
  'uploaded'
);

RESET ROLE;
SET ROLE authenticated;
SELECT set_config('request.jwt.claim.sub', 'a1111111-1111-4111-8111-111111111111', false);

DO $$
DECLARE
  v_count integer;
  v_first record;
  v_duplicate record;
BEGIN
  SELECT count(*) INTO v_count
  FROM public.saga_sources
  WHERE id = 'c2222222-2222-4222-8222-222222222222';

  IF v_count <> 1 THEN
    RAISE EXCEPTION 'source owner cannot read own source';
  END IF;

  SELECT * INTO v_first
  FROM public.saga_enqueue_analysis_job(
    'c2222222-2222-4222-8222-222222222222',
    'character_identity',
    repeat('b', 64)
  );

  IF v_first.was_created IS DISTINCT FROM true OR v_first.job_status <> 'queued' THEN
    RAISE EXCEPTION 'first enqueue did not create a queued job';
  END IF;

  SELECT * INTO v_duplicate
  FROM public.saga_enqueue_analysis_job(
    'c2222222-2222-4222-8222-222222222222',
    'character_identity',
    repeat('b', 64)
  );

  IF v_duplicate.job_id <> v_first.job_id OR v_duplicate.was_created IS DISTINCT FROM false THEN
    RAISE EXCEPTION 'duplicate active enqueue was not idempotent';
  END IF;
END;
$$;

SELECT set_config('request.jwt.claim.sub', 'a2222222-2222-4222-8222-222222222222', false);

DO $$
DECLARE
  v_count integer;
BEGIN
  SELECT count(*) INTO v_count FROM public.saga_sources;
  IF v_count <> 0 THEN
    RAISE EXCEPTION 'cross-user source read leaked % rows', v_count;
  END IF;

  SELECT count(*) INTO v_count FROM public.saga_analysis_jobs;
  IF v_count <> 0 THEN
    RAISE EXCEPTION 'cross-user job read leaked % rows', v_count;
  END IF;
END;
$$;

RESET ROLE;
SET ROLE service_role;

DO $$
DECLARE
  v_claim_one record;
  v_claim_two record;
  v_count integer;
  v_attempt integer;
  v_job_id uuid;
BEGIN
  SELECT id INTO v_job_id
  FROM public.saga_analysis_jobs
  WHERE source_id = 'c2222222-2222-4222-8222-222222222222'
    AND kind = 'character_identity';

  SELECT * INTO v_claim_one
  FROM public.saga_claim_analysis_job('phase2-test-worker', 300);

  IF v_claim_one.job_id <> v_job_id OR v_claim_one.attempt_count <> 1 THEN
    RAISE EXCEPTION 'first worker claim returned unexpected job/attempt';
  END IF;

  SELECT count(*) INTO v_count
  FROM public.saga_claim_analysis_job('phase2-second-worker', 300);

  IF v_count <> 0 THEN
    RAISE EXCEPTION 'active lease allowed a second worker claim';
  END IF;

  IF NOT public.saga_renew_analysis_job_lease(v_job_id, v_claim_one.lease_token, 300) THEN
    RAISE EXCEPTION 'valid worker lease could not be renewed';
  END IF;

  IF public.saga_renew_analysis_job_lease(
    v_job_id,
    'ffffffff-ffff-4fff-8fff-ffffffffffff',
    300
  ) THEN
    RAISE EXCEPTION 'invalid worker lease token was accepted';
  END IF;

  IF public.saga_finish_analysis_job(
    v_job_id,
    v_claim_one.lease_token,
    false,
    true,
    'retryable_fixture',
    'fixture requests one retry',
    0
  ) <> 'queued' THEN
    RAISE EXCEPTION 'retryable failure did not requeue job';
  END IF;

  SELECT attempt_count INTO v_attempt
  FROM public.saga_analysis_jobs
  WHERE id = v_job_id;

  IF v_attempt <> 1 THEN
    RAISE EXCEPTION 'requeue changed attempt_count unexpectedly';
  END IF;

  SELECT * INTO v_claim_two
  FROM public.saga_claim_analysis_job('phase2-test-worker', 300);

  IF v_claim_two.job_id <> v_job_id OR v_claim_two.attempt_count <> 2 THEN
    RAISE EXCEPTION 'second claim did not preserve job identity/increment attempt';
  END IF;

  IF public.saga_finish_analysis_job(
    v_job_id,
    v_claim_one.lease_token,
    true,
    false,
    null,
    null,
    0
  ) <> 'stale_lease' THEN
    RAISE EXCEPTION 'stale lease token could finish a newer attempt';
  END IF;

  IF public.saga_finish_analysis_job(
    v_job_id,
    v_claim_two.lease_token,
    true,
    false,
    null,
    null,
    0
  ) <> 'succeeded' THEN
    RAISE EXCEPTION 'valid second lease could not finish job';
  END IF;
END;
$$;

INSERT INTO public.saga_analysis_runs (
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
) VALUES (
  'b1111111-1111-4111-8111-111111111111',
  (
    select id
    from public.saga_analysis_jobs
    where source_id = 'c2222222-2222-4222-8222-222222222222'
      and kind = 'character_identity'
  ),
  'c1111111-1111-4111-8111-111111111111',
  'c2222222-2222-4222-8222-222222222222',
  'a1111111-1111-4111-8111-111111111111',
  'succeeded',
  repeat('b', 64),
  repeat('c', 64),
  'fixture-engine-v1',
  'fixture-provider',
  'fixture-model',
  'fixture-revision',
  repeat('d', 64),
  repeat('e', 64),
  now() - interval '1 second',
  now()
);

INSERT INTO public.saga_characters (
  id,
  run_id,
  project_id,
  source_id,
  owner_user_id,
  canonical_name,
  admission_tier,
  evidence_count
) VALUES (
  'b2222222-2222-4222-8222-222222222222',
  'b1111111-1111-4111-8111-111111111111',
  'c1111111-1111-4111-8111-111111111111',
  'c2222222-2222-4222-8222-222222222222',
  'a1111111-1111-4111-8111-111111111111',
  'Ada Vale',
  'canonical_seed',
  2
);

INSERT INTO public.saga_character_aliases (
  character_id,
  run_id,
  project_id,
  source_id,
  owner_user_id,
  surface_form,
  normalized_form,
  evidence_count
) VALUES (
  'b2222222-2222-4222-8222-222222222222',
  'b1111111-1111-4111-8111-111111111111',
  'c1111111-1111-4111-8111-111111111111',
  'c2222222-2222-4222-8222-222222222222',
  'a1111111-1111-4111-8111-111111111111',
  'Ada',
  'ada',
  2
);

INSERT INTO public.saga_character_mentions (
  run_id,
  project_id,
  source_id,
  owner_user_id,
  character_id,
  surface_text,
  start_offset,
  end_offset,
  structural_locator,
  mention_kind,
  resolution_state,
  evidence_tier,
  decision_reason
) VALUES
  (
    'b1111111-1111-4111-8111-111111111111',
    'c1111111-1111-4111-8111-111111111111',
    'c2222222-2222-4222-8222-222222222222',
    'a1111111-1111-4111-8111-111111111111',
    'b2222222-2222-4222-8222-222222222222',
    'Ada',
    0,
    3,
    'chapter:1',
    'proper_name',
    'linked',
    'canonical_seed',
    'typed_person_name_seed'
  ),
  (
    'b1111111-1111-4111-8111-111111111111',
    'c1111111-1111-4111-8111-111111111111',
    'c2222222-2222-4222-8222-222222222222',
    'a1111111-1111-4111-8111-111111111111',
    null,
    'she',
    10,
    13,
    'chapter:1',
    'pronoun',
    'unresolved',
    'attachment',
    'ambiguous_pronoun_attachment'
  );

RESET ROLE;
SET ROLE authenticated;
SELECT set_config('request.jwt.claim.sub', 'a1111111-1111-4111-8111-111111111111', false);

DO $$
DECLARE
  v_count integer;
BEGIN
  SELECT count(*) INTO v_count FROM public.saga_analysis_runs;
  IF v_count <> 1 THEN
    RAISE EXCEPTION 'owner cannot read analysis run';
  END IF;

  SELECT count(*) INTO v_count FROM public.saga_characters;
  IF v_count <> 1 THEN
    RAISE EXCEPTION 'owner cannot read character result';
  END IF;

  SELECT count(*) INTO v_count FROM public.saga_character_aliases;
  IF v_count <> 1 THEN
    RAISE EXCEPTION 'owner cannot read alias result';
  END IF;

  SELECT count(*) INTO v_count FROM public.saga_character_mentions;
  IF v_count <> 2 THEN
    RAISE EXCEPTION 'owner cannot read mention evidence';
  END IF;
END;
$$;

SELECT set_config('request.jwt.claim.sub', 'a2222222-2222-4222-8222-222222222222', false);

DO $$
DECLARE
  v_count integer;
BEGIN
  SELECT count(*) INTO v_count FROM public.saga_analysis_runs;
  IF v_count <> 0 THEN
    RAISE EXCEPTION 'cross-user run read leaked % rows', v_count;
  END IF;

  SELECT count(*) INTO v_count FROM public.saga_characters;
  IF v_count <> 0 THEN
    RAISE EXCEPTION 'cross-user character read leaked % rows', v_count;
  END IF;

  SELECT count(*) INTO v_count FROM public.saga_character_aliases;
  IF v_count <> 0 THEN
    RAISE EXCEPTION 'cross-user alias read leaked % rows', v_count;
  END IF;

  SELECT count(*) INTO v_count FROM public.saga_character_mentions;
  IF v_count <> 0 THEN
    RAISE EXCEPTION 'cross-user mention read leaked % rows', v_count;
  END IF;
END;
$$;

RESET ROLE;
