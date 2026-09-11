\set ON_ERROR_STOP on

DO $$
DECLARE
  v_invitation_id uuid;
  v_result_count integer;
BEGIN
  SELECT id
    INTO v_invitation_id
    FROM public.saga_invitations
    WHERE email_normalized = 'member@example.com'
      AND status = 'accepted'
    LIMIT 1;

  IF v_invitation_id IS NULL THEN
    RAISE EXCEPTION 'expected accepted invitation fixture is missing';
  END IF;

  SELECT count(*)
    INTO v_result_count
    FROM public.saga_admin_revoke_invitation(
      '11111111-1111-4111-8111-111111111111',
      v_invitation_id
    );

  IF v_result_count <> 0 THEN
    RAISE EXCEPTION 'settled invitation unexpectedly returned a revoke result';
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM public.saga_invitations
    WHERE id = v_invitation_id
      AND status = 'accepted'
      AND revoked_at IS NULL
  ) THEN
    RAISE EXCEPTION 'settled invitation state changed during revoke attempt';
  END IF;
END;
$$;
