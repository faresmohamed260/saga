\set ON_ERROR_STOP on

RESET ROLE;

DO $$
DECLARE
  v_table text;
BEGIN
  FOREACH v_table IN ARRAY ARRAY[
    'saga_normalized_sources',
    'saga_normalized_sections'
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

  IF has_table_privilege('authenticated', 'public.saga_normalized_sources', 'insert')
     OR has_table_privilege('authenticated', 'public.saga_normalized_sections', 'insert') THEN
    RAISE EXCEPTION 'authenticated role unexpectedly has normalized-result write privileges';
  END IF;

  IF has_table_privilege('service_role', 'public.saga_normalized_sources', 'update')
     OR has_table_privilege('service_role', 'public.saga_normalized_sources', 'delete')
     OR has_table_privilege('service_role', 'public.saga_normalized_sections', 'update')
     OR has_table_privilege('service_role', 'public.saga_normalized_sections', 'delete') THEN
    RAISE EXCEPTION 'normalized ingestion results are not append-only';
  END IF;

  IF NOT has_function_privilege(
    'authenticated',
    'public.saga_create_source_upload_intent(uuid,text,text,text,bigint,text)',
    'execute'
  ) THEN
    RAISE EXCEPTION 'authenticated users cannot create owned upload intents';
  END IF;

  IF has_function_privilege(
    'authenticated',
    'public.saga_service_finalize_source_upload(uuid,uuid,bigint,text,text,text)',
    'execute'
  ) OR has_function_privilege(
    'authenticated',
    'public.saga_service_commit_ingestion_success(uuid,uuid,text,text,text,text,jsonb)',
    'execute'
  ) THEN
    RAISE EXCEPTION 'browser role unexpectedly has trusted upload/worker finalization authority';
  END IF;

  IF NOT has_function_privilege(
    'service_role',
    'public.saga_service_finalize_source_upload(uuid,uuid,bigint,text,text,text)',
    'execute'
  ) OR NOT has_function_privilege(
    'service_role',
    'public.saga_service_mark_source_processing(uuid,uuid)',
    'execute'
  ) OR NOT has_function_privilege(
    'service_role',
    'public.saga_service_commit_ingestion_success(uuid,uuid,text,text,text,text,jsonb)',
    'execute'
  ) OR NOT has_function_privilege(
    'service_role',
    'public.saga_service_commit_ingestion_failure(uuid,uuid,text,text,text,text)',
    'execute'
  ) THEN
    RAISE EXCEPTION 'service_role lacks source-ingestion lifecycle authority';
  END IF;
END;
$$;

INSERT INTO auth.users (id, email) VALUES
  ('d1111111-1111-4111-8111-111111111111', 'phase2b-owner@example.com'),
  ('d2222222-2222-4222-8222-222222222222', 'phase2b-other@example.com');

INSERT INTO public.saga_account_access (
  user_id,
  role,
  status,
  invited_by,
  accepted_at,
  updated_by
) VALUES
  ('d1111111-1111-4111-8111-111111111111', 'member', 'active', null, now(), null),
  ('d2222222-2222-4222-8222-222222222222', 'member', 'active', null, now(), null);

SET ROLE authenticated;
SELECT set_config('request.jwt.claim.sub', 'd1111111-1111-4111-8111-111111111111', false);

INSERT INTO public.saga_projects (
  id,
  owner_user_id,
  title
) VALUES (
  'd3333333-3333-4333-8333-333333333333',
  'd1111111-1111-4111-8111-111111111111',
  'Phase 2B Ingestion Project'
);

SELECT *
FROM public.saga_create_source_upload_intent(
  'd3333333-3333-4333-8333-333333333333',
  'fixture.txt',
  'Fixture Text',
  'txt',
  11,
  repeat('1', 64)
) \gset txt_

DO $$
DECLARE
  v_status text;
  v_key text;
BEGIN
  SELECT ingestion_status, object_key
    INTO v_status, v_key
  FROM public.saga_sources
  WHERE id = :'txt_source_id';

  IF v_status <> 'pending_upload' THEN
    RAISE EXCEPTION 'new source intent was not pending_upload';
  END IF;

  IF v_key <> format(
    'sources/%s/%s/%s/%s/original',
    'd1111111-1111-4111-8111-111111111111',
    'd3333333-3333-4333-8333-333333333333',
    :'txt_source_id',
    repeat('1', 64)
  ) THEN
    RAISE EXCEPTION 'source object key is not owner/project/source/fingerprint scoped: %', v_key;
  END IF;
END;
$$;

SELECT set_config('request.jwt.claim.sub', 'd2222222-2222-4222-8222-222222222222', false);

DO $$
BEGIN
  BEGIN
    PERFORM *
    FROM public.saga_create_source_upload_intent(
      'd3333333-3333-4333-8333-333333333333',
      'forbidden.txt',
      'Forbidden',
      'txt',
      5,
      repeat('2', 64)
    );
    RAISE EXCEPTION 'cross-user upload intent unexpectedly succeeded';
  EXCEPTION
    WHEN OTHERS THEN
      IF SQLERRM = 'cross-user upload intent unexpectedly succeeded' THEN
        RAISE;
      END IF;
  END;
END;
$$;

SELECT set_config('request.jwt.claim.sub', 'd1111111-1111-4111-8111-111111111111', false);

SELECT *
FROM public.saga_create_source_upload_intent(
  'd3333333-3333-4333-8333-333333333333',
  'broken.epub',
  'Broken EPUB',
  'epub',
  100,
  repeat('9', 64)
) \gset bad_

RESET ROLE;
SET ROLE service_role;

SELECT *
FROM public.saga_service_finalize_source_upload(
  :'bad_source_id',
  'd1111111-1111-4111-8111-111111111111',
  101,
  'application/epub+zip',
  repeat('9', 64),
  :'bad_source_id'
) \gset bad_final_

DO $$
DECLARE
  v_jobs integer;
BEGIN
  IF :'bad_final_source_status' <> 'failed'
     OR :'bad_final_result_failure_code' <> 'upload_metadata_mismatch' THEN
    RAISE EXCEPTION 'mismatched upload metadata did not fail closed';
  END IF;

  SELECT count(*) INTO v_jobs
  FROM public.saga_analysis_jobs
  WHERE source_id = :'bad_source_id';

  IF v_jobs <> 0 THEN
    RAISE EXCEPTION 'mismatched upload enqueued ingestion work';
  END IF;
END;
$$;

SELECT *
FROM public.saga_service_finalize_source_upload(
  :'txt_source_id',
  'd1111111-1111-4111-8111-111111111111',
  11,
  'text/plain',
  repeat('1', 64),
  :'txt_source_id'
) \gset final_

DO $$
DECLARE
  v_completed_at timestamptz;
BEGIN
  IF :'final_source_status' <> 'uploaded' OR :'final_job_id' = '' THEN
    RAISE EXCEPTION 'verified upload did not enqueue ingestion';
  END IF;

  SELECT upload_completed_at
    INTO v_completed_at
  FROM public.saga_sources
  WHERE id = :'txt_source_id';

  IF v_completed_at IS NULL THEN
    RAISE EXCEPTION 'verified upload did not retain completion time';
  END IF;
END;
$$;

SELECT *
FROM public.saga_claim_analysis_job('phase2b-worker', 300) \gset claim_

DO $$
BEGIN
  IF :'claim_job_id' <> :'final_job_id' OR :'claim_job_kind' <> 'source_ingestion' THEN
    RAISE EXCEPTION 'worker did not claim the verified source-ingestion job';
  END IF;

  IF NOT public.saga_service_mark_source_processing(:'claim_job_id', :'claim_lease_token') THEN
    RAISE EXCEPTION 'valid ingestion lease did not mark source processing';
  END IF;
END;
$$;

SELECT public.saga_service_commit_ingestion_success(
  :'claim_job_id',
  :'claim_lease_token',
  'saga-normalizer-v1',
  repeat('2', 64),
  repeat('3', 64),
  repeat('4', 64),
  jsonb_build_array(
    jsonb_build_object(
      'stable_key', 'section-0000',
      'ordinal', 0,
      'section_kind', 'chapter',
      'title', 'Chapter One',
      'source_locator', 'txt:document#chapter-one',
      'start_offset', 0,
      'end_offset', 11,
      'normalized_text', 'Chapter One'
    ),
    jsonb_build_object(
      'stable_key', 'section-0001',
      'ordinal', 1,
      'section_kind', 'section',
      'title', null,
      'source_locator', 'txt:document#body',
      'start_offset', 13,
      'end_offset', 25,
      'normalized_text', 'Ada arrived.'
    )
  )
) AS run_id \gset run_

DO $$
DECLARE
  v_source_status text;
  v_job_status text;
  v_structure_count integer;
  v_section_count integer;
BEGIN
  SELECT ingestion_status INTO v_source_status
  FROM public.saga_sources
  WHERE id = :'txt_source_id';

  SELECT status INTO v_job_status
  FROM public.saga_analysis_jobs
  WHERE id = :'final_job_id';

  SELECT count(*) INTO v_structure_count
  FROM public.saga_normalized_sources
  WHERE run_id = :'run_run_id';

  SELECT count(*) INTO v_section_count
  FROM public.saga_normalized_sections
  WHERE run_id = :'run_run_id';

  IF v_source_status <> 'ready' OR v_job_status <> 'succeeded' THEN
    RAISE EXCEPTION 'successful ingestion did not settle source/job state';
  END IF;

  IF v_structure_count <> 1 OR v_section_count <> 2 THEN
    RAISE EXCEPTION 'normalized structure was not persisted atomically';
  END IF;

  IF public.saga_service_mark_source_processing(:'claim_job_id', :'claim_lease_token') THEN
    RAISE EXCEPTION 'stale completed lease remained usable';
  END IF;
END;
$$;

RESET ROLE;
SET ROLE authenticated;
SELECT set_config('request.jwt.claim.sub', 'd1111111-1111-4111-8111-111111111111', false);

DO $$
DECLARE
  v_count integer;
BEGIN
  SELECT count(*) INTO v_count
  FROM public.saga_normalized_sources
  WHERE source_id = :'txt_source_id';

  IF v_count <> 1 THEN
    RAISE EXCEPTION 'owner cannot read normalized source result';
  END IF;

  SELECT count(*) INTO v_count
  FROM public.saga_normalized_sections
  WHERE source_id = :'txt_source_id';

  IF v_count <> 2 THEN
    RAISE EXCEPTION 'owner cannot read normalized sections';
  END IF;
END;
$$;

SELECT set_config('request.jwt.claim.sub', 'd2222222-2222-4222-8222-222222222222', false);

DO $$
DECLARE
  v_count integer;
BEGIN
  SELECT count(*) INTO v_count FROM public.saga_normalized_sources;
  IF v_count <> 0 THEN
    RAISE EXCEPTION 'cross-user normalized source read leaked % rows', v_count;
  END IF;

  SELECT count(*) INTO v_count FROM public.saga_normalized_sections;
  IF v_count <> 0 THEN
    RAISE EXCEPTION 'cross-user normalized section read leaked % rows', v_count;
  END IF;
END;
$$;

RESET ROLE;
