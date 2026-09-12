\set ON_ERROR_STOP on

RESET ROLE;

DO $$
BEGIN
  IF NOT has_function_privilege(
    'service_role',
    'public.saga_service_commit_identity_success(uuid,uuid,text,text,text,text,text,text,jsonb,jsonb)',
    'execute'
  ) OR NOT has_function_privilege(
    'service_role',
    'public.saga_service_commit_identity_failure(uuid,uuid,text,text,text,text,text,text,text)',
    'execute'
  ) THEN
    RAISE EXCEPTION 'service_role lacks identity commit functions';
  END IF;

  IF has_function_privilege(
    'authenticated',
    'public.saga_service_commit_identity_success(uuid,uuid,text,text,text,text,text,text,jsonb,jsonb)',
    'execute'
  ) THEN
    RAISE EXCEPTION 'authenticated role unexpectedly has identity worker commit authority';
  END IF;

  IF has_table_privilege('authenticated', 'public.saga_characters', 'insert')
     OR has_table_privilege('authenticated', 'public.saga_character_aliases', 'insert')
     OR has_table_privilege('authenticated', 'public.saga_character_mentions', 'insert') THEN
    RAISE EXCEPTION 'authenticated role unexpectedly has direct identity-result write privileges';
  END IF;
END;
$$;

INSERT INTO auth.users (id, email) VALUES
  ('e1111111-1111-4111-8111-111111111111', 'phase2c-owner@example.com'),
  ('e2222222-2222-4222-8222-222222222222', 'phase2c-other@example.com');

INSERT INTO public.saga_account_access (
  user_id, role, status, invited_by, accepted_at, updated_by
) VALUES
  ('e1111111-1111-4111-8111-111111111111', 'member', 'active', null, now(), null),
  ('e2222222-2222-4222-8222-222222222222', 'member', 'active', null, now(), null);

SET ROLE authenticated;
SELECT set_config('request.jwt.claim.sub', 'e1111111-1111-4111-8111-111111111111', false);

INSERT INTO public.saga_projects (id, owner_user_id, title) VALUES (
  'e3333333-3333-4333-8333-333333333333',
  'e1111111-1111-4111-8111-111111111111',
  'Phase 2C Identity Project'
);

RESET ROLE;
SET ROLE service_role;

INSERT INTO public.saga_sources (
  id, project_id, owner_user_id, original_filename, display_name, source_format,
  media_type, byte_size, content_sha256, object_key, ingestion_status, upload_completed_at
) VALUES (
  'e4444444-4444-4444-8444-444444444444',
  'e3333333-3333-4333-8333-333333333333',
  'e1111111-1111-4111-8111-111111111111',
  'identity.txt',
  'Identity Fixture',
  'txt',
  'text/plain; charset=utf-8',
  41,
  repeat('1', 64),
  'sources/e1111111-1111-4111-8111-111111111111/e3333333-3333-4333-8333-333333333333/e4444444-4444-4444-8444-444444444444/original',
  'uploaded',
  now()
);

INSERT INTO public.saga_analysis_jobs (
  id, project_id, source_id, owner_user_id, requested_by, kind, status, input_fingerprint
) VALUES (
  'e5555555-5555-4555-8555-555555555555',
  'e3333333-3333-4333-8333-333333333333',
  'e4444444-4444-4444-8444-444444444444',
  'e1111111-1111-4111-8111-111111111111',
  'e1111111-1111-4111-8111-111111111111',
  'source_ingestion',
  'queued',
  repeat('1', 64)
);

SELECT *
FROM public.saga_claim_analysis_job_kind('phase2c-ingestion-worker', 'source_ingestion', 300)
\gset ingestion_claim_

SELECT public.saga_service_mark_source_processing(
  :'ingestion_claim_job_id',
  :'ingestion_claim_lease_token'
);

SELECT public.saga_service_commit_ingestion_success(
  :'ingestion_claim_job_id',
  :'ingestion_claim_lease_token',
  'saga-normalizer-v1',
  repeat('2', 64),
  repeat('3', 64),
  repeat('4', 64),
  jsonb_build_array(
    jsonb_build_object(
      'stable_key', 'section-0000',
      'ordinal', 0,
      'section_kind', 'chapter',
      'title', 'Identity Fixture',
      'source_locator', 'txt:document#identity-fixture',
      'start_offset', 0,
      'end_offset', 41,
      'normalized_text', 'She ran. Ada Vale stopped. What happened.'
    )
  )
);

DO $$
DECLARE
  v_identity_jobs integer;
  v_fingerprint text;
BEGIN
  SELECT count(*), min(input_fingerprint)
    INTO v_identity_jobs, v_fingerprint
  FROM public.saga_analysis_jobs
  WHERE source_id = 'e4444444-4444-4444-8444-444444444444'
    AND kind = 'character_identity';

  IF v_identity_jobs <> 1 OR v_fingerprint <> repeat('4', 64) THEN
    RAISE EXCEPTION 'successful ingestion did not atomically enqueue exactly one identity job';
  END IF;
END;
$$;

SELECT *
FROM public.saga_claim_analysis_job_kind('phase2c-identity-worker', 'character_identity', 300)
\gset identity_claim_

SELECT set_config('test.identity_job_id', :'identity_claim_job_id', false);

-- Keep the persistence validator strict. This preflight mirrors its mention
-- predicates so a future fixture drift reports the exact evidence row/reason
-- rather than weakening the transactional function.
DO $$
DECLARE
  v_characters jsonb := jsonb_build_array(
    jsonb_build_object(
      'character_key', 'character:ada-vale',
      'canonical_name', 'Ada Vale',
      'admission_tier', 'stabilized',
      'evidence_count', 2,
      'aliases', jsonb_build_array(
        jsonb_build_object(
          'surface_form', 'Ada Vale',
          'normalized_form', 'ada vale',
          'evidence_count', 1
        )
      )
    )
  );
  v_mentions jsonb := jsonb_build_array(
    jsonb_build_object(
      'evidence_id', 'mention-pronoun',
      'character_key', 'character:ada-vale',
      'surface_text', 'She',
      'start_offset', 0,
      'end_offset', 3,
      'structural_locator', 'txt:document#identity-fixture',
      'mention_kind', 'pronoun',
      'resolution_state', 'linked',
      'evidence_tier', 'attachment',
      'decision_reason', 'unique_provider_cluster_attachment'
    ),
    jsonb_build_object(
      'evidence_id', 'mention-name',
      'character_key', 'character:ada-vale',
      'surface_text', 'Ada Vale',
      'start_offset', 9,
      'end_offset', 17,
      'structural_locator', 'txt:document#identity-fixture',
      'mention_kind', 'proper_name',
      'resolution_state', 'linked',
      'evidence_tier', 'canonical_seed',
      'decision_reason', 'accepted_canonical_seed'
    ),
    jsonb_build_object(
      'evidence_id', 'mention-what',
      'character_key', null,
      'surface_text', 'What',
      'start_offset', 27,
      'end_offset', 31,
      'structural_locator', 'txt:document#identity-fixture',
      'mention_kind', 'proper_name',
      'resolution_state', 'quarantined',
      'evidence_tier', 'quarantined',
      'decision_reason', 'blocked_surface'
    )
  );
  v_total_characters bigint;
  v_invalid record;
BEGIN
  SELECT normalized.total_characters
    INTO v_total_characters
  FROM public.saga_normalized_sources AS normalized
  JOIN public.saga_analysis_runs AS ingestion_run ON ingestion_run.id = normalized.run_id
  WHERE normalized.source_id = 'e4444444-4444-4444-8444-444444444444'
    AND ingestion_run.output_fingerprint = repeat('4', 64)
  LIMIT 1;

  SELECT mention.*
    INTO v_invalid
  FROM jsonb_to_recordset(v_mentions) AS mention(
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
  WHERE mention.evidence_id is null
     OR char_length(btrim(mention.evidence_id)) not between 1 and 256
     OR mention.surface_text is null
     OR char_length(mention.surface_text) not between 1 and 2000
     OR mention.start_offset is null
     OR mention.start_offset < 0
     OR mention.end_offset is null
     OR mention.end_offset <= mention.start_offset
     OR mention.end_offset > v_total_characters
     OR mention.mention_kind not in ('proper_name', 'nominal', 'pronoun')
     OR mention.resolution_state not in ('linked', 'unresolved', 'quarantined')
     OR mention.evidence_tier not in ('canonical_seed', 'attachment', 'quarantined')
     OR mention.decision_reason is null
     OR char_length(btrim(mention.decision_reason)) not between 1 and 1000
     OR (mention.resolution_state = 'linked' and mention.character_key is null)
     OR (mention.resolution_state in ('unresolved', 'quarantined') and mention.character_key is not null)
     OR (
       mention.character_key is not null
       AND NOT EXISTS (
         SELECT 1
         FROM jsonb_to_recordset(v_characters) AS character(character_key text)
         WHERE character.character_key = mention.character_key
       )
     )
  LIMIT 1;

  IF FOUND THEN
    RAISE EXCEPTION 'identity fixture preflight rejected evidence %, total_characters=%', row_to_json(v_invalid), v_total_characters;
  END IF;
END;
$$;

SELECT public.saga_service_commit_identity_success(
  :'identity_claim_job_id',
  :'identity_claim_lease_token',
  'saga-identity-resolver-v1',
  'recorded-fixture',
  null,
  'fixture-v1',
  repeat('7', 64),
  repeat('8', 64),
  jsonb_build_array(
    jsonb_build_object(
      'character_key', 'character:ada-vale',
      'canonical_name', 'Ada Vale',
      'admission_tier', 'stabilized',
      'evidence_count', 2,
      'aliases', jsonb_build_array(
        jsonb_build_object(
          'surface_form', 'Ada Vale',
          'normalized_form', 'ada vale',
          'evidence_count', 1
        )
      )
    )
  ),
  jsonb_build_array(
    jsonb_build_object(
      'evidence_id', 'mention-pronoun',
      'character_key', 'character:ada-vale',
      'surface_text', 'She',
      'start_offset', 0,
      'end_offset', 3,
      'structural_locator', 'txt:document#identity-fixture',
      'mention_kind', 'pronoun',
      'resolution_state', 'linked',
      'evidence_tier', 'attachment',
      'decision_reason', 'unique_provider_cluster_attachment'
    ),
    jsonb_build_object(
      'evidence_id', 'mention-name',
      'character_key', 'character:ada-vale',
      'surface_text', 'Ada Vale',
      'start_offset', 9,
      'end_offset', 17,
      'structural_locator', 'txt:document#identity-fixture',
      'mention_kind', 'proper_name',
      'resolution_state', 'linked',
      'evidence_tier', 'canonical_seed',
      'decision_reason', 'accepted_canonical_seed'
    ),
    jsonb_build_object(
      'evidence_id', 'mention-what',
      'character_key', null,
      'surface_text', 'What',
      'start_offset', 27,
      'end_offset', 31,
      'structural_locator', 'txt:document#identity-fixture',
      'mention_kind', 'proper_name',
      'resolution_state', 'quarantined',
      'evidence_tier', 'quarantined',
      'decision_reason', 'blocked_surface'
    )
  )
) AS identity_run_id
\gset

SELECT set_config('test.identity_run_id', :'identity_run_id', false);

DO $$
DECLARE
  v_job_status text;
  v_provider_name text;
  v_provider_revision text;
  v_normalized_fingerprint text;
  v_character_count integer;
  v_alias_count integer;
  v_mention_count integer;
  v_quarantined_count integer;
BEGIN
  SELECT status INTO v_job_status
  FROM public.saga_analysis_jobs
  WHERE id = current_setting('test.identity_job_id')::uuid;

  SELECT provider_name, provider_revision, normalized_input_fingerprint
    INTO v_provider_name, v_provider_revision, v_normalized_fingerprint
  FROM public.saga_analysis_runs
  WHERE id = current_setting('test.identity_run_id')::uuid;

  SELECT count(*) INTO v_character_count
  FROM public.saga_characters
  WHERE run_id = current_setting('test.identity_run_id')::uuid
    AND resolver_key = 'character:ada-vale'
    AND canonical_name = 'Ada Vale';

  SELECT count(*) INTO v_alias_count
  FROM public.saga_character_aliases
  WHERE run_id = current_setting('test.identity_run_id')::uuid;

  SELECT count(*) INTO v_mention_count
  FROM public.saga_character_mentions
  WHERE run_id = current_setting('test.identity_run_id')::uuid;

  SELECT count(*) INTO v_quarantined_count
  FROM public.saga_character_mentions
  WHERE run_id = current_setting('test.identity_run_id')::uuid
    AND resolution_state = 'quarantined'
    AND character_id is null;

  IF v_job_status <> 'succeeded'
     OR v_provider_name <> 'recorded-fixture'
     OR v_provider_revision <> 'fixture-v1'
     OR v_normalized_fingerprint <> repeat('3', 64)
     OR v_character_count <> 1
     OR v_alias_count <> 1
     OR v_mention_count <> 3
     OR v_quarantined_count <> 1 THEN
    RAISE EXCEPTION 'identity success did not persist one atomic provenance/result set';
  END IF;
END;
$$;

RESET ROLE;
SET ROLE authenticated;
SELECT set_config('request.jwt.claim.sub', 'e1111111-1111-4111-8111-111111111111', false);

DO $$
DECLARE
  v_characters integer;
  v_mentions integer;
BEGIN
  SELECT count(*) INTO v_characters
  FROM public.saga_characters
  WHERE source_id = 'e4444444-4444-4444-8444-444444444444';

  SELECT count(*) INTO v_mentions
  FROM public.saga_character_mentions
  WHERE source_id = 'e4444444-4444-4444-8444-444444444444';

  IF v_characters <> 1 OR v_mentions <> 3 THEN
    RAISE EXCEPTION 'owner cannot read identity results';
  END IF;
END;
$$;

SELECT set_config('request.jwt.claim.sub', 'e2222222-2222-4222-8222-222222222222', false);

DO $$
DECLARE
  v_count integer;
BEGIN
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
