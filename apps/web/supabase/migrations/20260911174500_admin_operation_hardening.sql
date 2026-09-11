begin;

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

  if not found or v_invitation.status <> 'pending' then
    return;
  end if;

  if v_invitation.expires_at <= now() then
    update public.saga_invitations as i
       set status = 'expired'
     where i.id = p_invitation_id
     returning i.* into v_invitation;
  else
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

commit;
