import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { runtimeApi } from "../../api/runtimeApi";
import { Badge, Button, EmptyState, Field, Panel, SearchBox, text, toneFor } from "../../components/ui/primitives";
import { useAsync } from "../../hooks/useAsync";

export function VisualAssetsPage() {
  const { entityId } = useParams();
  const [type, setType] = useState("");
  const [query, setQuery] = useState("");
  const assets = useAsync(() => runtimeApi.assets({ entity_type: type, q: query }), [type, query]);
  const selectedId = entityId || assets.value?.entities?.[0]?.id;
  const detail = useAsync(() => selectedId ? runtimeApi.asset(selectedId) : Promise.resolve(null), [selectedId]);

  const entities = assets.value?.entities || [];
  return (
    <div className="grid gap-5 xl:grid-cols-[460px_1fr]">
      <Panel title="Visual Asset Browser" subtitle="One row per entity, with prompt and image versions sourced from SQLite.">
        <div className="mb-3 flex flex-wrap gap-2">
          {["", "character", "creature", "location", "object", "organization"].map((item) => <Button key={item || "all"} onClick={() => setType(item)}>{item || "all"}</Button>)}
        </div>
        <SearchBox value={query} onChange={setQuery} placeholder="Search entities..." />
        <div className="mt-4 space-y-3">
          {entities.length ? entities.map((entity) => (
            <a key={entity.id} href={`/assets/entities/${encodeURIComponent(entity.id)}`} className="block rounded-2xl border border-slate-800 bg-slate-900/45 p-4 hover:border-sky-500/60">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-black text-white">{entity.name}</p>
                  <p className="mt-1 text-sm text-slate-500">{entity.book_title || entity.book_id}</p>
                </div>
                <Badge tone={entity.image_count ? "green" : "amber"}>{entity.image_count || 0} images</Badge>
              </div>
              <div className="mt-3 flex flex-wrap gap-2"><Badge tone="blue">{entity.entity_type}</Badge><Badge>{entity.prompt_count || 0} prompts</Badge><Badge tone={toneFor(entity.render_status)}>{entity.render_status || "not rendered"}</Badge></div>
            </a>
          )) : <EmptyState title="No visual assets found" />}
        </div>
      </Panel>
      <EntityInspector detail={detail} />
    </div>
  );
}

function EntityInspector({ detail }) {
  const navigate = useNavigate();
  const entity = detail.value?.entity;
  const prompts = detail.value?.prompts || [];
  const images = detail.value?.images || [];
  const [positive, setPositive] = useState("");
  const [saving, setSaving] = useState(false);

  const activePrompt = useMemo(() => prompts[0], [prompts]);
  async function savePrompt() {
    if (!entity?.id || !positive.trim()) return;
    setSaving(true);
    try {
      await runtimeApi.savePromptVersion(entity.id, { positive_prompt: positive, negative_prompt: activePrompt?.negative_prompt || "", source: "dashboard_edit", activate: true });
      await detail.reload();
      setPositive("");
    } finally {
      setSaving(false);
    }
  }
  async function renderEntity() {
    if (!entity?.id) return;
    try {
      const job = await runtimeApi.renderEntity(entity.id, { prompt_id: activePrompt?.id || "", overwrite: false });
      navigate(`/runs/${encodeURIComponent(job.id)}`);
    } catch (error) {
      alert(error.message);
    }
  }

  if (detail.loading) return <Panel title="Loading entity"><EmptyState title="Loading" /></Panel>;
  if (!entity) return <Panel title="Entity inspector"><EmptyState title="Select an entity" /></Panel>;
  return (
    <Panel title={entity.name} subtitle={`${entity.entity_type} - ${entity.book_title || entity.book_id}`} action={<Button onClick={renderEntity} variant="primary">Render entity</Button>}>
      <div className="space-y-4">
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Baseline traits">{text(entity.initial_physical_description || entity.typed_attributes)}</Field>
          <Field label="First appearance">{text(entity.first_appearance_profile)}</Field>
        </div>
        <Field label="Active prompt">{text(activePrompt?.positive_prompt || entity.baseline_visual_prompt)}</Field>
        <textarea value={positive} onChange={(event) => setPositive(event.target.value)} placeholder="Create a new prompt version..." className="min-h-[160px] w-full rounded-2xl border border-slate-800 bg-black/40 p-4 text-sm text-slate-100 outline-none focus:border-sky-500" />
        <Button onClick={savePrompt} disabled={saving || !positive.trim()}>{saving ? "Saving..." : "Save prompt version"}</Button>
        <div className="grid gap-4 md:grid-cols-2">
          {images.length ? images.map((image) => (
            <div key={image.id} className="rounded-2xl border border-slate-800 bg-black/25 p-3">
              {image.output_path ? <img src={`/runtime/file?path=${encodeURIComponent(image.output_path)}`} className="max-h-[420px] w-full rounded-xl object-contain" /> : null}
              <p className="mt-2 text-sm text-slate-400">{image.render_status || "status n/a"} - {image.workflow_name || "workflow n/a"}</p>
            </div>
          )) : <EmptyState title="No generated image versions" />}
        </div>
      </div>
    </Panel>
  );
}
