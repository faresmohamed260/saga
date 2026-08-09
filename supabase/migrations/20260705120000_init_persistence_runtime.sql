create table if not exists public.provider_configs (
  provider_name text primary key,
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.provider_statuses (
  id bigint generated always as identity primary key,
  provider_name text not null,
  label text not null,
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  constraint uq_provider_status_provider_label unique (provider_name, label)
);

create index if not exists ix_provider_status_provider
  on public.provider_statuses (provider_name);

create table if not exists public.library_series (
  series_id text primary key,
  title text not null default '',
  metadata jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.library_books (
  book_id text primary key,
  series_id text references public.library_series(series_id) on delete set null,
  title text not null default '',
  book_index integer,
  source_uri text not null default '',
  source_type text not null default '',
  metadata jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create index if not exists ix_library_books_series
  on public.library_books (series_id, book_index);

create table if not exists public.library_scenes (
  scene_id text primary key,
  book_id text not null references public.library_books(book_id) on delete cascade,
  chapter_index integer not null,
  scene_index integer not null,
  summary text not null default '',
  text text not null default '',
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  constraint uq_library_scenes_position unique (book_id, chapter_index, scene_index)
);

create index if not exists ix_library_scenes_book
  on public.library_scenes (book_id, chapter_index, scene_index);

create table if not exists public.library_records (
  record_id text primary key,
  record_type text not null,
  series_id text not null default '',
  book_id text not null default '',
  scene_id text not null default '',
  title text not null default '',
  ordinal integer,
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create index if not exists ix_library_records_scope
  on public.library_records (record_type, series_id, book_id, scene_id);

create table if not exists public.identity_series (
  series_id text primary key,
  provider_name text not null default '',
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.jobs (
  job_id text primary key,
  job_type text not null,
  status text not null,
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create index if not exists ix_jobs_type_status
  on public.jobs (job_type, status);

create table if not exists public.job_logs (
  id bigint generated always as identity primary key,
  job_id text not null references public.jobs(job_id) on delete cascade,
  stage text not null default '',
  message text not null default '',
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists ix_job_logs_job
  on public.job_logs (job_id, id);

create table if not exists public.generated_stories (
  story_id text primary key,
  series_id text not null default '',
  book_id text not null default '',
  title text not null default '',
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create index if not exists ix_generated_stories_scope
  on public.generated_stories (series_id, book_id);

create table if not exists public.audiobook_runs (
  run_id text primary key,
  series_id text not null default '',
  book_id text not null default '',
  title text not null default '',
  status text not null default 'staged',
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create index if not exists ix_audiobook_runs_scope
  on public.audiobook_runs (series_id, book_id, status);

create table if not exists public.audiobook_chapters (
  chapter_id text primary key,
  run_id text not null references public.audiobook_runs(run_id) on delete cascade,
  book_index integer not null,
  chapter_index integer not null,
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  constraint uq_audiobook_chapter_position unique (run_id, book_index, chapter_index)
);

create index if not exists ix_audiobook_chapters_run
  on public.audiobook_chapters (run_id, book_index, chapter_index);
