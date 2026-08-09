create extension if not exists vector;

create table if not exists public.vector_documents (
  id bigserial primary key,
  namespace text not null,
  document_id text not null,
  content text not null default '',
  summary text not null default '',
  metadata jsonb not null default '{}'::jsonb,
  embedding vector not null,
  updated_at timestamptz not null default now(),
  constraint uq_vector_documents_namespace_document unique (namespace, document_id)
);

create index if not exists ix_vector_documents_namespace
  on public.vector_documents (namespace);
