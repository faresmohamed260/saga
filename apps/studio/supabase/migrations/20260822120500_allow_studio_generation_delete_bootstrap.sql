drop policy if exists "studio_generations_delete_bootstrap" on public.studio_generations;

create policy "studio_generations_delete_bootstrap"
on public.studio_generations
for delete
to anon
using (status = 'completed');
