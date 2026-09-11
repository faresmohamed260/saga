begin;

create or replace function public.saga_normalize_email(input_email text)
returns text
language sql
immutable
strict
set search_path = ''
as $$
  select lower(btrim(input_email));
$$;

revoke all on function public.saga_normalize_email(text) from public, anon, authenticated;
grant execute on function public.saga_normalize_email(text) to service_role;

create table public.saga_account_access (
  user_id uuid primary key references auth.users(id) on delete cascade,
  role text not null check (role in ('member', 'admin')),
  status text not null check (status in ('active', 'suspended')),
  invited_by uuid references auth.users(id) on delete set null,
  accepted_at timestamptz not null default now(),
  updated_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.saga_invitations (
  id uuid primary key default gen_random_uuid(),
  email_normalized text not null,
  email_display text not null,
  intended_role text not null check (intended_role in ('member', 'admin')),
  status text not null default 'pending'
    check (status in ('pending', 'accepted', 'revoked', 'expired')),
  invited_by uuid references auth.users(id) on delete set null,
  invited_at timestamptz not null default now(),
  expires_at timestamptz not null,
  accepted_by uuid references auth.users(id) on delete set null,
  accepted_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint saga_invitations_email_normalized_check check (
    email_normalized = public.saga_normalize_email(email_normalized)
    and char_length(email_normalized) between 3 and 320
  ),
  constraint saga_invitations_email_display_check check (
    char_length(btrim(email_display)) between 3 and 320
  ),
  constraint saga_invitations_expiry_check check (expires_at > invited_at),
  constraint saga_invitations_state_check check (
    (status = 'pending' and accepted_by is null and accepted_at is null and revoked_at is null)
    or (status = 'accepted' and accepted_by is not null and accepted_at is not null and revoked_at is null)
    or (status = 'revoked' and accepted_by is null and accepted_at is null and revoked_at is not null)
    or (status = 'expired' and accepted_by is null and accepted_at is null and revoked_at is null)
  )
);

create unique index saga_invitations_one_pending_email_idx
  on public.saga_invitations (email_normalized)
  where status = 'pending';

create index saga_invitations_status_invited_at_idx
  on public.saga_invitations (status, invited_at desc);

create or replace function public.saga_touch_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

revoke all on function public.saga_touch_updated_at() from public, anon, authenticated;
grant execute on function public.saga_touch_updated_at() to service_role;

create trigger saga_account_access_touch_updated_at
before update on public.saga_account_access
for each row execute function public.saga_touch_updated_at();

create trigger saga_invitations_touch_updated_at
before update on public.saga_invitations
for each row execute function public.saga_touch_updated_at();

alter table public.saga_account_access enable row level security;
alter table public.saga_account_access force row level security;
alter table public.saga_invitations enable row level security;
alter table public.saga_invitations force row level security;

revoke all on table public.saga_account_access from public, anon, authenticated;
revoke all on table public.saga_invitations from public, anon, authenticated;
grant select, insert, update, delete on table public.saga_account_access to service_role;
grant select, insert, update, delete on table public.saga_invitations to service_role;

create or replace function public.saga_claim_invitation(p_user_id uuid)
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
  v_email_normalized text;
  v_invitation public.saga_invitations%rowtype;
  v_account public.saga_account_access%rowtype;
begin
  select u.email
    into v_email
    from auth.users as u
    where u.id = p_user_id;

  if v_email is null then
    return;
  end if;

  v_email_normalized := public.saga_normalize_email(v_email);

  select i.*
    into v_invitation
    from public.saga_invitations as i
    where i.email_normalized = v_email_normalized
      and i.status = 'pending'
    order by i.invited_at desc
    limit 1
    for update;

  if not found then
    return;
  end if;

  if v_invitation.expires_at <= now() then
    update public.saga_invitations as i
      set status = 'expired'
      where i.id = v_invitation.id;
    return;
  end if;

  select a.*
    into v_account
    from public.saga_account_access as a
    where a.user_id = p_user_id
    for update;

  if found then
    update public.saga_invitations as i
      set status = 'accepted',
          accepted_by = p_user_id,
          accepted_at = now()
      where i.id = v_invitation.id;

    return query
      select a.user_id, a.role, a.status, a.invited_by, a.accepted_at
      from public.saga_account_access as a
      where a.user_id = p_user_id;
    return;
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
    v_invitation.intended_role,
    'active',
    v_invitation.invited_by,
    now(),
    v_invitation.invited_by
  );

  update public.saga_invitations as i
    set status = 'accepted',
        accepted_by = p_user_id,
        accepted_at = now()
    where i.id = v_invitation.id;

  return query
    select a.user_id, a.role, a.status, a.invited_by, a.accepted_at
    from public.saga_account_access as a
    where a.user_id = p_user_id;
end;
$$;

revoke all on function public.saga_claim_invitation(uuid) from public, anon, authenticated;
grant execute on function public.saga_claim_invitation(uuid) to service_role;

commit;
