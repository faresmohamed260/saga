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
begin
  -- Serialize the one-time bootstrap with any concurrent account writes.
  lock table public.saga_account_access in share row exclusive mode;

  if exists (select 1 from public.saga_account_access) then
    raise exception 'saga_bootstrap_already_completed';
  end if;

  if not exists (
    select 1
    from auth.users as u
    where u.id = p_user_id
      and u.email is not null
  ) then
    raise exception 'saga_bootstrap_auth_user_required';
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

  return query
    select a.user_id, a.role, a.status, a.invited_by, a.accepted_at
    from public.saga_account_access as a
    where a.user_id = p_user_id;
end;
$$;

revoke all on function public.saga_bootstrap_first_admin(uuid) from public, anon, authenticated;
grant execute on function public.saga_bootstrap_first_admin(uuid) to service_role;

commit;
