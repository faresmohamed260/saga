begin;

alter table public.saga_analysis_jobs
  add constraint saga_analysis_jobs_identity_scope_unique
  unique (id, project_id, source_id, owner_user_id);

alter table public.saga_analysis_runs
  add constraint saga_analysis_runs_job_scope_fk
  foreign key (job_id, project_id, source_id, owner_user_id)
  references public.saga_analysis_jobs(id, project_id, source_id, owner_user_id)
  on delete cascade;

commit;
