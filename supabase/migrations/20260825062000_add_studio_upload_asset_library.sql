create table if not exists public.studio_uploads (
  id uuid primary key default gen_random_uuid(),
  r2_key text not null unique,
  filename text not null check (char_length(filename) between 1 and 240),
  display_name text not null check (char_length(display_name) between 1 and 240),
  mime_type text not null check (mime_type in ('image/png','image/jpeg','image/webp')),
  size_bytes bigint not null check (size_bytes between 1 and 26214400),
  width integer check (width is null or width > 0),
  height integer check (height is null or height > 0),
  is_favorite boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint studio_uploads_library_key_check check (r2_key ~ '^uploads/[0-9]{4}/[0-9]{2}/[0-9a-f-]{36}\.(png|jpg|jpeg|webp)$')
);

create index if not exists studio_uploads_created_at_idx on public.studio_uploads (created_at desc, id desc);
create index if not exists studio_uploads_favorite_created_at_idx on public.studio_uploads (is_favorite, created_at desc);
create index if not exists studio_uploads_display_name_idx on public.studio_uploads (lower(display_name));

alter table public.studio_uploads enable row level security;

create policy "studio_uploads_demo_select" on public.studio_uploads for select to anon using (true);
create policy "studio_uploads_demo_insert" on public.studio_uploads for insert to anon with check (true);
create policy "studio_uploads_demo_update" on public.studio_uploads for update to anon using (true) with check (true);
create policy "studio_uploads_demo_delete" on public.studio_uploads for delete to anon using (true);
