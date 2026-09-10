begin;

create table if not exists public.saga_account_access (
  user_id uuid primary key references auth.users(id) on delete restrict,
  role text not null check (role in ('member', 'admin')),
  status text not null default 'active' check (status in ('active', 'suspended')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.saga_invitations (
  id uuid primary key default gen_random_uuid(),
  normalized_email text not null check (normalized_email = lower(trim(normalized_email))),
  role text not null check (role in ('member', 'admin')),
  invited_by uuid not null references auth.users(id) on delete restrict,
  expires_at timestamptz not null,
  claimed_by uuid references auth.users(id) on delete restrict,
  claimed_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  check ((claimed_at is null and claimed_by is null) or (claimed_at is not null and claimed_by is not null)),
  check (not (claimed_at is not null and revoked_at is not null))
);

create unique index if not exists saga_invitations_open_email_idx
  on public.saga_invitations (normalized_email)
  where claimed_at is null and revoked_at is null;

create index if not exists saga_invitations_expiry_idx
  on public.saga_invitations (expires_at)
  where claimed_at is null and revoked_at is null;

alter table public.saga_account_access enable row level security;
alter table public.saga_invitations enable row level security;

revoke all on table public.saga_account_access from anon, authenticated;
revoke all on table public.saga_invitations from anon, authenticated;
grant all on table public.saga_account_access to service_role;
grant all on table public.saga_invitations to service_role;

create or replace function public.saga_claim_invitation(p_user_id uuid, p_email text)
returns setof public.saga_account_access
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_verified_email text;
  v_invitation_id uuid;
  v_invitation_role text;
begin
  if p_user_id is null or p_email is null then
    return;
  end if;

  select lower(trim(u.email))
    into v_verified_email
    from auth.users as u
   where u.id = p_user_id;

  if v_verified_email is null or v_verified_email <> lower(trim(p_email)) then
    return;
  end if;

  if exists (select 1 from public.saga_account_access where user_id = p_user_id) then
    return query
      select * from public.saga_account_access where user_id = p_user_id;
    return;
  end if;

  select i.id, i.role
    into v_invitation_id, v_invitation_role
    from public.saga_invitations as i
   where i.normalized_email = v_verified_email
     and i.claimed_at is null
     and i.revoked_at is null
     and i.expires_at > now()
   order by i.created_at desc, i.id desc
   limit 1
   for update;

  if v_invitation_id is null then
    return;
  end if;

  insert into public.saga_account_access (user_id, role, status)
  values (p_user_id, v_invitation_role, 'active');

  update public.saga_invitations
     set claimed_by = p_user_id,
         claimed_at = now()
   where id = v_invitation_id
     and claimed_at is null
     and revoked_at is null;

  return query
    select * from public.saga_account_access where user_id = p_user_id;
end;
$$;

revoke all on function public.saga_claim_invitation(uuid, text) from public, anon, authenticated;
grant execute on function public.saga_claim_invitation(uuid, text) to service_role;

commit;
