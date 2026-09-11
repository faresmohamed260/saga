\set ON_ERROR_STOP on

begin;

DO $$
BEGIN
  IF NOT has_function_privilege('service_role', 'public.saga_bootstrap_first_admin(uuid)', 'execute') THEN
    RAISE EXCEPTION 'service_role cannot execute saga_bootstrap_first_admin';
  END IF;

  IF has_function_privilege('anon', 'public.saga_bootstrap_first_admin(uuid)', 'execute')
     OR has_function_privilege('authenticated', 'public.saga_bootstrap_first_admin(uuid)', 'execute') THEN
    RAISE EXCEPTION 'browser roles unexpectedly can execute saga_bootstrap_first_admin';
  END IF;
END;
$$;

INSERT INTO auth.users (id, email) VALUES
  ('66666666-6666-4666-8666-666666666666', 'owner@example.com'),
  ('77777777-7777-4777-8777-777777777777', 'other@example.com');

DO $$
DECLARE
  v_count integer;
  v_role text;
  v_status text;
  v_invited_by uuid;
  v_updated_by uuid;
BEGIN
  BEGIN
    PERFORM 1
    FROM public.saga_bootstrap_first_admin('88888888-8888-4888-8888-888888888888');
    RAISE EXCEPTION 'unknown Auth user unexpectedly bootstrapped';
  EXCEPTION
    WHEN OTHERS THEN
      IF SQLERRM NOT LIKE '%saga_bootstrap_auth_user_required%' THEN
        RAISE;
      END IF;
  END;

  SELECT count(*) INTO v_count
  FROM public.saga_bootstrap_first_admin('66666666-6666-4666-8666-666666666666');

  IF v_count <> 1 THEN
    RAISE EXCEPTION 'expected exactly one bootstrap row, got %', v_count;
  END IF;

  SELECT role, status, invited_by, updated_by
    INTO v_role, v_status, v_invited_by, v_updated_by
    FROM public.saga_account_access
    WHERE user_id = '66666666-6666-4666-8666-666666666666';

  IF v_role <> 'admin' OR v_status <> 'active' OR v_invited_by IS NOT NULL THEN
    RAISE EXCEPTION 'bootstrap account state is incorrect';
  END IF;

  IF v_updated_by <> '66666666-6666-4666-8666-666666666666'::uuid THEN
    RAISE EXCEPTION 'bootstrap audit actor is incorrect';
  END IF;

  BEGIN
    PERFORM 1
    FROM public.saga_bootstrap_first_admin('77777777-7777-4777-8777-777777777777');
    RAISE EXCEPTION 'second bootstrap unexpectedly succeeded';
  EXCEPTION
    WHEN OTHERS THEN
      IF SQLERRM NOT LIKE '%saga_bootstrap_already_completed%' THEN
        RAISE;
      END IF;
  END;

  IF EXISTS (
    SELECT 1
    FROM public.saga_account_access
    WHERE user_id = '77777777-7777-4777-8777-777777777777'
  ) THEN
    RAISE EXCEPTION 'second bootstrap created another account';
  END IF;
END;
$$;

rollback;
