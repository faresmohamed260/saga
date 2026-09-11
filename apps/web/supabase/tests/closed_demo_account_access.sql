\set ON_ERROR_STOP on

DO $$
BEGIN
  IF has_table_privilege('anon', 'public.saga_account_access', 'select')
     OR has_table_privilege('authenticated', 'public.saga_account_access', 'select')
     OR has_table_privilege('anon', 'public.saga_invitations', 'select')
     OR has_table_privilege('authenticated', 'public.saga_invitations', 'select') THEN
    RAISE EXCEPTION 'browser roles unexpectedly have privileged table access';
  END IF;

  IF NOT has_function_privilege('service_role', 'public.saga_claim_invitation(uuid)', 'execute') THEN
    RAISE EXCEPTION 'service_role cannot execute saga_claim_invitation';
  END IF;

  IF NOT has_function_privilege('service_role', 'public.saga_admin_upsert_invitation_intent(uuid,text,text,timestamptz)', 'execute')
     OR NOT has_function_privilege('service_role', 'public.saga_admin_revoke_invitation(uuid,uuid)', 'execute')
     OR NOT has_function_privilege('service_role', 'public.saga_admin_update_account(uuid,uuid,text,text)', 'execute') THEN
    RAISE EXCEPTION 'service_role cannot execute Phase 1E admin routines';
  END IF;

  IF has_function_privilege('anon', 'public.saga_admin_update_account(uuid,uuid,text,text)', 'execute')
     OR has_function_privilege('authenticated', 'public.saga_admin_update_account(uuid,uuid,text,text)', 'execute') THEN
    RAISE EXCEPTION 'browser roles unexpectedly can execute admin routines';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relname IN ('saga_account_access', 'saga_invitations')
      AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity)
  ) THEN
    RAISE EXCEPTION 'closed-demo tables must enable and force RLS';
  END IF;
END;
$$;

INSERT INTO auth.users (id, email) VALUES
  ('11111111-1111-4111-8111-111111111111', 'admin@example.com'),
  ('22222222-2222-4222-8222-222222222222', 'Member@Example.com'),
  ('33333333-3333-4333-8333-333333333333', 'different@example.com'),
  ('44444444-4444-4444-8444-444444444444', 'expired@example.com'),
  ('55555555-5555-4555-8555-555555555555', 'second-admin@example.com');

INSERT INTO public.saga_account_access (
  user_id,
  role,
  status,
  invited_by,
  accepted_at,
  updated_by
) VALUES (
  '11111111-1111-4111-8111-111111111111',
  'admin',
  'active',
  null,
  now(),
  '11111111-1111-4111-8111-111111111111'
);

INSERT INTO public.saga_invitations (
  email_normalized,
  email_display,
  intended_role,
  invited_by,
  expires_at
) VALUES (
  'member@example.com',
  'Member@Example.com',
  'member',
  '11111111-1111-4111-8111-111111111111',
  now() + interval '1 day'
);

DO $$
DECLARE
  v_claim_count integer;
  v_role text;
  v_status text;
BEGIN
  SELECT count(*) INTO v_claim_count
  FROM public.saga_claim_invitation('22222222-2222-4222-8222-222222222222');

  IF v_claim_count <> 1 THEN
    RAISE EXCEPTION 'expected exactly one successful invitation claim, got %', v_claim_count;
  END IF;

  SELECT role, status INTO v_role, v_status
  FROM public.saga_account_access
  WHERE user_id = '22222222-2222-4222-8222-222222222222';

  IF v_role <> 'member' OR v_status <> 'active' THEN
    RAISE EXCEPTION 'claimed account state is incorrect';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM public.saga_invitations
    WHERE email_normalized = 'member@example.com'
      AND status = 'accepted'
      AND accepted_by = '22222222-2222-4222-8222-222222222222'
      AND accepted_at IS NOT NULL
  ) THEN
    RAISE EXCEPTION 'invitation was not atomically accepted';
  END IF;

  SELECT count(*) INTO v_claim_count
  FROM public.saga_claim_invitation('22222222-2222-4222-8222-222222222222');

  IF v_claim_count <> 0 THEN
    RAISE EXCEPTION 'accepted invitation was claimable twice';
  END IF;
END;
$$;

INSERT INTO public.saga_invitations (
  email_normalized,
  email_display,
  intended_role,
  invited_by,
  expires_at
) VALUES (
  'expected@example.com',
  'expected@example.com',
  'member',
  '11111111-1111-4111-8111-111111111111',
  now() + interval '1 day'
);

DO $$
DECLARE
  v_claim_count integer;
BEGIN
  SELECT count(*) INTO v_claim_count
  FROM public.saga_claim_invitation('33333333-3333-4333-8333-333333333333');

  IF v_claim_count <> 0 THEN
    RAISE EXCEPTION 'mismatched verified Auth email claimed an invitation';
  END IF;

  IF EXISTS (
    SELECT 1 FROM public.saga_account_access
    WHERE user_id = '33333333-3333-4333-8333-333333333333'
  ) THEN
    RAISE EXCEPTION 'mismatched Auth identity was admitted';
  END IF;
END;
$$;

INSERT INTO public.saga_invitations (
  email_normalized,
  email_display,
  intended_role,
  invited_by,
  invited_at,
  expires_at
) VALUES (
  'expired@example.com',
  'expired@example.com',
  'member',
  '11111111-1111-4111-8111-111111111111',
  now() - interval '2 hours',
  now() - interval '1 hour'
);

DO $$
DECLARE
  v_claim_count integer;
BEGIN
  SELECT count(*) INTO v_claim_count
  FROM public.saga_claim_invitation('44444444-4444-4444-8444-444444444444');

  IF v_claim_count <> 0 THEN
    RAISE EXCEPTION 'expired invitation was accepted';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM public.saga_invitations
    WHERE email_normalized = 'expired@example.com'
      AND status = 'expired'
  ) THEN
    RAISE EXCEPTION 'expired invitation did not settle to expired state';
  END IF;
END;
$$;

DO $$
BEGIN
  BEGIN
    INSERT INTO public.saga_invitations (
      email_normalized,
      email_display,
      intended_role,
      invited_by,
      expires_at
    ) VALUES (
      'expected@example.com',
      'expected@example.com',
      'member',
      '11111111-1111-4111-8111-111111111111',
      now() + interval '1 day'
    );
    RAISE EXCEPTION 'duplicate pending invitation unexpectedly succeeded';
  EXCEPTION
    WHEN unique_violation THEN
      NULL;
  END;
END;
$$;

DO $$
DECLARE
  v_created boolean;
  v_invitation_id uuid;
BEGIN
  SELECT r.id, r.created
    INTO v_invitation_id, v_created
    FROM public.saga_admin_upsert_invitation_intent(
      '11111111-1111-4111-8111-111111111111',
      ' NewPerson@Example.com ',
      'member',
      now() + interval '7 days'
    ) as r;

  IF v_invitation_id IS NULL OR v_created IS DISTINCT FROM true THEN
    RAISE EXCEPTION 'admin invitation intent was not created';
  END IF;

  SELECT r.created
    INTO v_created
    FROM public.saga_admin_upsert_invitation_intent(
      '11111111-1111-4111-8111-111111111111',
      'newperson@example.com',
      'member',
      now() + interval '7 days'
    ) as r;

  IF v_created IS DISTINCT FROM false THEN
    RAISE EXCEPTION 'same-role pending invitation was not reused for safe retry';
  END IF;

  IF (SELECT count(*) FROM public.saga_invitations WHERE email_normalized = 'newperson@example.com' AND status = 'pending') <> 1 THEN
    RAISE EXCEPTION 'retry created duplicate pending invitation intent';
  END IF;

  BEGIN
    PERFORM * FROM public.saga_admin_upsert_invitation_intent(
      '11111111-1111-4111-8111-111111111111',
      'newperson@example.com',
      'admin',
      now() + interval '7 days'
    );
    RAISE EXCEPTION 'role-conflicting retry unexpectedly succeeded';
  EXCEPTION
    WHEN unique_violation THEN
      NULL;
  END;

  PERFORM * FROM public.saga_admin_revoke_invitation(
    '11111111-1111-4111-8111-111111111111',
    v_invitation_id
  );

  IF NOT EXISTS (
    SELECT 1 FROM public.saga_invitations
    WHERE id = v_invitation_id
      AND status = 'revoked'
      AND revoked_at IS NOT NULL
  ) THEN
    RAISE EXCEPTION 'admin revoke did not settle pending invitation';
  END IF;
END;
$$;

DO $$
BEGIN
  BEGIN
    PERFORM * FROM public.saga_admin_upsert_invitation_intent(
      '22222222-2222-4222-8222-222222222222',
      'forbidden@example.com',
      'member',
      now() + interval '7 days'
    );
    RAISE EXCEPTION 'member unexpectedly created invitation intent';
  EXCEPTION
    WHEN insufficient_privilege THEN
      NULL;
  END;
END;
$$;

DO $$
DECLARE
  v_role text;
  v_status text;
BEGIN
  SELECT r.role, r.status
    INTO v_role, v_status
    FROM public.saga_admin_update_account(
      '11111111-1111-4111-8111-111111111111',
      '22222222-2222-4222-8222-222222222222',
      'member',
      'suspended'
    ) as r;

  IF v_role <> 'member' OR v_status <> 'suspended' THEN
    RAISE EXCEPTION 'admin account status mutation failed';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM public.saga_account_access
    WHERE user_id = '22222222-2222-4222-8222-222222222222'
      AND updated_by = '11111111-1111-4111-8111-111111111111'
  ) THEN
    RAISE EXCEPTION 'account mutation did not preserve actor audit metadata';
  END IF;

  BEGIN
    PERFORM * FROM public.saga_admin_update_account(
      '11111111-1111-4111-8111-111111111111',
      '11111111-1111-4111-8111-111111111111',
      'member',
      'active'
    );
    RAISE EXCEPTION 'admin self-demotion unexpectedly succeeded';
  EXCEPTION
    WHEN insufficient_privilege THEN
      NULL;
  END;

  BEGIN
    PERFORM * FROM public.saga_admin_update_account(
      '11111111-1111-4111-8111-111111111111',
      '11111111-1111-4111-8111-111111111111',
      'admin',
      'suspended'
    );
    RAISE EXCEPTION 'admin self-suspension unexpectedly succeeded';
  EXCEPTION
    WHEN insufficient_privilege THEN
      NULL;
  END;
END;
$$;

INSERT INTO public.saga_account_access (
  user_id,
  role,
  status,
  invited_by,
  accepted_at,
  updated_by
) VALUES (
  '55555555-5555-4555-8555-555555555555',
  'admin',
  'active',
  '11111111-1111-4111-8111-111111111111',
  now(),
  '11111111-1111-4111-8111-111111111111'
);

DO $$
DECLARE
  v_role text;
BEGIN
  SELECT r.role
    INTO v_role
    FROM public.saga_admin_update_account(
      '11111111-1111-4111-8111-111111111111',
      '55555555-5555-4555-8555-555555555555',
      'member',
      'active'
    ) as r;

  IF v_role <> 'member' THEN
    RAISE EXCEPTION 'authorized second-admin demotion failed';
  END IF;

  IF (SELECT count(*) FROM public.saga_account_access WHERE role = 'admin' AND status = 'active') <> 1 THEN
    RAISE EXCEPTION 'admin mutation left unexpected active-admin count';
  END IF;
END;
$$;
