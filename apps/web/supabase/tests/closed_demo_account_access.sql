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
  ('44444444-4444-4444-8444-444444444444', 'expired@example.com');

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
