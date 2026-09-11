begin;

create or replace function public.saga_bootstrap_first_admin(p_user_id uuid)
returns table (
  user_id uuid,
  role text,
  status text,
  invited_by uuid,
  accepted_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_email text;
  v_email_display text;
  v_email_normalized text;
begin
  -- Serialize the one-time bootstrap with any concurrent account writes.
  lock table public.saga_account_access in share row exclusive mode;

  if exists (select 1 from public.saga_account_access) then
    raise exception 'saga_bootstrap_already_completed';
  end if;

  select u.email
    into v_email
    from auth.users as u
    where u.id = p_user_id
      and u.email is not null;

  if v_email is null then
    raise exception 'saga_bootstrap_auth_user_required';
  end if;

  v_email_display := btrim(v_email);
  v_email_normalized := public.saga_normalize_email(v_email_display);

  -- The bootstrap Auth identity is created by the trusted operator invite.
  -- Pair it with a normal S.A.G.A. pending invitation so the first owner
  -- completes the same confirmation/password flow as every later invitee.
  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(v_email_normalized, 0)
  );

  if exists (
    select 1
    from public.saga_invitations as i
    where i.email_normalized = v_email_normalized
      and i.status = 'pending'
  ) then
    raise exception 'saga_bootstrap_invitation_conflict';
  end if;

  insert into public.saga_account_access (
    user_id,
    role,
    status,
    invited_by,
    accepted_at,
    updated_by
  ) values (
    p_user_id,
    'admin',
    'active',
    null,
    now(),
    p_user_id
  );

  insert into public.saga_invitations (
    email_normalized,
    email_display,
    intended_role,
    status,
    invited_by,
    expires_at
  ) values (
    v_email_normalized,
    v_email_display,
    'admin',
    'pending',
    p_user_id,
    now() + interval '7 days'
  );

  return query
    select a.user_id, a.role, a.status, a.invited_by, a.accepted_at
    from public.saga_account_access as a
    where a.user_id = p_user_id;
end;
$$;

revoke all on function public.saga_bootstrap_first_admin(uuid) from public, anon, authenticated;
grant execute on function public.saga_bootstrap_first_admin(uuid) to service_role;

commit;
