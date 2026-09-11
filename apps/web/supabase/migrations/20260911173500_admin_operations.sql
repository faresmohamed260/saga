begin;

create or replace function public.saga_assert_active_admin(p_actor_user_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not exists (
    select 1
    from public.saga_account_access as a
    where a.user_id = p_actor_user_id
      and a.role = 'admin'
      and a.status = 'active'
  ) then
    raise exception using message = 'saga_admin_required', errcode = '42501';
  end if;
end;
$$;

revoke all on function public.saga_assert_active_admin(uuid) from public, anon, authenticated;
grant execute on function public.saga_assert_active_admin(uuid) to service_role;

create or replace function public.saga_admin_upsert_invitation_intent(
  p_actor_user_id uuid,
  p_email text,
  p_intended_role text,
  p_expires_at timestamptz
)
returns table (
  id uuid,
  email_normalized text,
  email_display text,
  intended_role text,
  status text,
  invited_by uuid,
  invited_at timestamptz,
  expires_at timestamptz,
  accepted_by uuid,
  accepted_at timestamptz,
  revoked_at timestamptz,
  created boolean
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_email_display text;
  v_email_normalized text;
  v_invitation public.saga_invitations%rowtype;
begin
  perform public.saga_assert_active_admin(p_actor_user_id);

  v_email_display := btrim(p_email);
  v_email_normalized := public.saga_normalize_email(v_email_display);

  if char_length(v_email_normalized) not between 3 and 320
     or position('@' in v_email_normalized) <= 1 then
    raise exception using message = 'saga_invalid_email', errcode = '22023';
  end if;

  if p_intended_role not in ('member', 'admin') then
    raise exception using message = 'saga_invalid_role', errcode = '22023';
  end if;

  if p_expires_at is null or p_expires_at <= now() then
    raise exception using message = 'saga_invalid_expiry', errcode = '22023';
  end if;

  -- Serialize one invitation lifecycle per normalized email, including retries.
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(v_email_normalized, 0));

  update public.saga_invitations as i
     set status = 'expired'
   where i.email_normalized = v_email_normalized
     and i.status = 'pending'
     and i.expires_at <= now();

  if exists (
    select 1
    from public.saga_account_access as a
    join auth.users as u on u.id = a.user_id
    where public.saga_normalize_email(u.email) = v_email_normalized
  ) then
    raise exception using message = 'saga_account_already_admitted', errcode = '23505';
  end if;

  select i.*
    into v_invitation
    from public.saga_invitations as i
    where i.email_normalized = v_email_normalized
      and i.status = 'pending'
    limit 1
    for update;

  if found then
    if v_invitation.intended_role <> p_intended_role then
      raise exception using message = 'saga_pending_invitation_role_conflict', errcode = '23505';
    end if;

    return query
      select
        v_invitation.id,
        v_invitation.email_normalized,
        v_invitation.email_display,
        v_invitation.intended_role,
        v_invitation.status,
        v_invitation.invited_by,
        v_invitation.invited_at,
        v_invitation.expires_at,
        v_invitation.accepted_by,
        v_invitation.accepted_at,
        v_invitation.revoked_at,
        false;
    return;
  end if;

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
    p_intended_role,
    'pending',
    p_actor_user_id,
    p_expires_at
  )
  returning * into v_invitation;

  return query
    select
      v_invitation.id,
      v_invitation.email_normalized,
      v_invitation.email_display,
      v_invitation.intended_role,
      v_invitation.status,
      v_invitation.invited_by,
      v_invitation.invited_at,
      v_invitation.expires_at,
      v_invitation.accepted_by,
      v_invitation.accepted_at,
      v_invitation.revoked_at,
      true;
end;
$$;

revoke all on function public.saga_admin_upsert_invitation_intent(uuid, text, text, timestamptz) from public, anon, authenticated;
grant execute on function public.saga_admin_upsert_invitation_intent(uuid, text, text, timestamptz) to service_role;

create or replace function public.saga_admin_revoke_invitation(
  p_actor_user_id uuid,
  p_invitation_id uuid
)
returns table (
  id uuid,
  status text,
  revoked_at timestamptz,
  updated_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_invitation public.saga_invitations%rowtype;
begin
  perform public.saga_assert_active_admin(p_actor_user_id);

  select i.*
    into v_invitation
    from public.saga_invitations as i
    where i.id = p_invitation_id
    for update;

  if not found then
    return;
  end if;

  if v_invitation.status = 'pending' and v_invitation.expires_at <= now() then
    update public.saga_invitations as i
       set status = 'expired'
     where i.id = p_invitation_id
     returning i.* into v_invitation;
  elsif v_invitation.status = 'pending' then
    update public.saga_invitations as i
       set status = 'revoked',
           revoked_at = now()
     where i.id = p_invitation_id
     returning i.* into v_invitation;
  end if;

  return query
    select v_invitation.id, v_invitation.status, v_invitation.revoked_at, v_invitation.updated_at;
end;
$$;

revoke all on function public.saga_admin_revoke_invitation(uuid, uuid) from public, anon, authenticated;
grant execute on function public.saga_admin_revoke_invitation(uuid, uuid) to service_role;

create or replace function public.saga_admin_update_account(
  p_actor_user_id uuid,
  p_target_user_id uuid,
  p_role text,
  p_status text
)
returns table (
  user_id uuid,
  role text,
  status text,
  invited_by uuid,
  accepted_at timestamptz,
  updated_by uuid,
  updated_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_target public.saga_account_access%rowtype;
  v_remaining_active_admins integer;
begin
  perform public.saga_assert_active_admin(p_actor_user_id);

  if p_role not in ('member', 'admin') then
    raise exception using message = 'saga_invalid_role', errcode = '22023';
  end if;

  if p_status not in ('active', 'suspended') then
    raise exception using message = 'saga_invalid_status', errcode = '22023';
  end if;

  -- Serialize role/status transitions so two concurrent demotions cannot remove all admins.
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended('saga_admin_account_mutation', 0));

  select a.*
    into v_target
    from public.saga_account_access as a
    where a.user_id = p_target_user_id
    for update;

  if not found then
    return;
  end if;

  if p_target_user_id = p_actor_user_id
     and (p_role <> 'admin' or p_status <> 'active') then
    raise exception using message = 'saga_admin_self_lockout', errcode = '42501';
  end if;

  if v_target.role = 'admin'
     and v_target.status = 'active'
     and (p_role <> 'admin' or p_status <> 'active') then
    select count(*)
      into v_remaining_active_admins
      from public.saga_account_access as a
      where a.user_id <> p_target_user_id
        and a.role = 'admin'
        and a.status = 'active';

    if v_remaining_active_admins = 0 then
      raise exception using message = 'saga_last_active_admin', errcode = '42501';
    end if;
  end if;

  update public.saga_account_access as a
     set role = p_role,
         status = p_status,
         updated_by = p_actor_user_id
   where a.user_id = p_target_user_id
   returning a.* into v_target;

  return query
    select
      v_target.user_id,
      v_target.role,
      v_target.status,
      v_target.invited_by,
      v_target.accepted_at,
      v_target.updated_by,
      v_target.updated_at;
end;
$$;

revoke all on function public.saga_admin_update_account(uuid, uuid, text, text) from public, anon, authenticated;
grant execute on function public.saga_admin_update_account(uuid, uuid, text, text) to service_role;

commit;
