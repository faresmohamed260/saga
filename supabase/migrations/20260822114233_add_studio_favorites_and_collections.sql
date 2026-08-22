alter table public.studio_generations add column if not exists is_favorite boolean not null default false;
create index if not exists studio_generations_favorite_created_at_idx on public.studio_generations (is_favorite, created_at desc);

create table if not exists public.studio_collections (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(name) between 1 and 120),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.studio_collection_items (
  collection_id uuid not null references public.studio_collections(id) on delete cascade,
  generation_id uuid not null references public.studio_generations(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (collection_id, generation_id)
);
create index if not exists studio_collection_items_generation_idx on public.studio_collection_items (generation_id);

alter table public.studio_collections enable row level security;
alter table public.studio_collection_items enable row level security;

create policy "studio_collections_demo_select" on public.studio_collections for select to anon using (true);
create policy "studio_collections_demo_insert" on public.studio_collections for insert to anon with check (true);
create policy "studio_collections_demo_update" on public.studio_collections for update to anon using (true) with check (true);
create policy "studio_collections_demo_delete" on public.studio_collections for delete to anon using (true);
create policy "studio_collection_items_demo_select" on public.studio_collection_items for select to anon using (true);
create policy "studio_collection_items_demo_insert" on public.studio_collection_items for insert to anon with check (true);
create policy "studio_collection_items_demo_delete" on public.studio_collection_items for delete to anon using (true);
create policy "studio_generations_demo_update_favorite" on public.studio_generations for update to anon using (true) with check (true);
