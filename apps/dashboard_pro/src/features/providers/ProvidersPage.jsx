import React, { useEffect, useState } from "react";

import { runtimeApi } from "../../api/runtimeApi";
import { ProviderHealthPanel } from "../../components/provider-cards/ProviderHealthPanel.jsx";
import { Badge, Button, EmptyState, Field, Metric, Panel, TextInput, toneFor } from "../../components/primitives/index.js";
import { useAsync } from "../../hooks/useAsync";

const EMPTY_ACCOUNT = { label: "", token_id: "", token_secret: "", app_name_override: "" };

function ModalComfyUIEditor({ onSaved }) {
  const config = useAsync(() => runtimeApi.inferenceProvider("modal_comfyui"), []);
  const [form, setForm] = useState({
    provider_name: "modal_comfyui",
    app_name: "saga-image-runtime",
    api_url: "",
    health_url: "",
    ui_url: "",
    hf_token: "",
    request_timeout_seconds: 600,
    accounts: [{ ...EMPTY_ACCOUNT }],
    has_hf_token: false,
  });
  const [saveState, setSaveState] = useState({ saving: false, error: "", message: "" });

  useEffect(() => {
    const payload = config.value?.provider;
    if (!payload) return;
    setForm({
      provider_name: "modal_comfyui",
      app_name: payload.app_name || "saga-image-runtime",
      api_url: payload.api_url || "",
      health_url: payload.health_url || "",
      ui_url: payload.ui_url || "",
      hf_token: "",
      request_timeout_seconds: payload.request_timeout_seconds || 600,
      accounts: payload.accounts?.length
        ? payload.accounts.map((account) => ({
            label: account.label || "",
            token_id: "",
            token_secret: "",
            app_name_override: account.app_name_override || "",
            has_token_id: !!account.has_token_id,
            has_token_secret: !!account.has_token_secret,
          }))
        : [{ ...EMPTY_ACCOUNT }],
      has_hf_token: !!payload.has_hf_token,
    });
  }, [config.value]);

  function updateField(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function updateAccount(index, key, value) {
    setForm((current) => ({
      ...current,
      accounts: current.accounts.map((account, accountIndex) => (accountIndex === index ? { ...account, [key]: value } : account)),
    }));
  }

  function addAccount() {
    setForm((current) => ({ ...current, accounts: [...current.accounts, { ...EMPTY_ACCOUNT }] }));
  }

  async function save() {
    setSaveState({ saving: true, error: "", message: "" });
    try {
      const payload = {
        ...form,
        accounts: form.accounts.filter((account) => account.label || account.token_id || account.token_secret || account.app_name_override),
      };
      await runtimeApi.saveInferenceProvider("modal_comfyui", payload);
      await config.reload();
      if (onSaved) await onSaved();
      setSaveState({ saving: false, error: "", message: "Saved Modal ComfyUI settings." });
    } catch (exc) {
      setSaveState({ saving: false, error: exc.message || String(exc), message: "" });
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        <label className="space-y-1.5 text-sm text-slate-200">
          <span className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">App Name</span>
          <TextInput value={form.app_name} onChange={(event) => updateField("app_name", event.target.value)} />
        </label>
        <label className="space-y-1.5 text-sm text-slate-200">
          <span className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Timeout Seconds</span>
          <TextInput type="number" min="30" value={form.request_timeout_seconds} onChange={(event) => updateField("request_timeout_seconds", Number(event.target.value || 600))} />
        </label>
        <label className="space-y-1.5 text-sm text-slate-200 md:col-span-2">
          <span className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Hugging Face Token</span>
          <TextInput type="password" value={form.hf_token} onChange={(event) => updateField("hf_token", event.target.value)} placeholder={form.has_hf_token ? "Token already stored. Enter a new value to replace it." : "hf_..."} />
        </label>
        <label className="space-y-1.5 text-sm text-slate-200">
          <span className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">API URL</span>
          <TextInput value={form.api_url} onChange={(event) => updateField("api_url", event.target.value)} />
        </label>
        <label className="space-y-1.5 text-sm text-slate-200">
          <span className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Health URL</span>
          <TextInput value={form.health_url} onChange={(event) => updateField("health_url", event.target.value)} />
        </label>
      </div>

      <div className="space-y-3">
        {form.accounts.map((account, index) => (
          <Field key={`${account.label || "account"}-${index}`} label={`Modal Account ${index + 1}`}>
            <div className="grid gap-3 md:grid-cols-2">
              <TextInput value={account.label} onChange={(event) => updateAccount(index, "label", event.target.value)} placeholder="member-01" />
              <TextInput value={account.app_name_override || ""} onChange={(event) => updateAccount(index, "app_name_override", event.target.value)} placeholder="Optional app override" />
              <TextInput value={account.token_id} onChange={(event) => updateAccount(index, "token_id", event.target.value)} placeholder={account.has_token_id ? "Token ID already stored. Enter a new value to replace it." : "Modal token id"} />
              <TextInput type="password" value={account.token_secret} onChange={(event) => updateAccount(index, "token_secret", event.target.value)} placeholder={account.has_token_secret ? "Token secret already stored. Enter a new value to replace it." : "Modal token secret"} />
            </div>
          </Field>
        ))}
      </div>

      <div className="flex flex-wrap gap-3">
        <Button onClick={addAccount}>Add Modal account</Button>
        <Button onClick={save} variant="primary" disabled={saveState.saving}>{saveState.saving ? "Saving..." : "Save Modal ComfyUI"}</Button>
      </div>
      {saveState.error ? <p className="text-sm text-rose-300">{saveState.error}</p> : null}
      {saveState.message ? <p className="text-sm text-emerald-300">{saveState.message}</p> : null}
    </div>
  );
}

function InferenceHealthSummary({ providers }) {
  const modalComfy = providers?.modal_comfyui;
  const modalStatuses = modalComfy?.statuses || [];
  if (!modalStatuses.length) return null;
  return (
    <Field label="Modal ComfyUI Runtime">
      <div className="flex flex-wrap gap-2">
        {modalStatuses.map((row) => (
          <React.Fragment key={row.label || row.provider_name}>
            <Badge tone={toneFor(row.probe_status)}>{row.label || "account"}</Badge>
            <Badge tone={toneFor(row.probe_status)}>{row.probe_status || "unknown"}</Badge>
          </React.Fragment>
        ))}
      </div>
    </Field>
  );
}

function UsageGovernancePanel() {
  const usage = useAsync(() => runtimeApi.usageSummary(), []);
  const summary = usage.value?.summary || {};
  const providers = usage.value?.by_provider || [];
  const unpriced = Number(summary.unpriced_charge_count || 0);

  return (
    <Panel
      title="Usage & Cost Governance"
      subtitle="Immutable provider charges, versioned pricing coverage, and active budget policy state."
      action={<Button onClick={usage.reload}>Refresh usage</Button>}
    >
      {usage.error ? <p className="text-sm text-rose-300">{usage.error}</p> : null}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Provider requests" value={summary.request_count || 0} detail="ledger" tone="blue" />
        <Metric label="Tracked cost USD" value={Number(summary.cost_usd || 0).toFixed(4)} detail="priced" tone="green" />
        <Metric label="Unpriced charges" value={unpriced} detail={unpriced ? "action required" : "covered"} tone={unpriced ? "red" : "green"} />
        <Metric label="Active budgets" value={usage.value?.policies?.length || 0} detail="enforced" tone="amber" />
      </div>
      {providers.length ? (
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {providers.map((row) => (
            <div key={row.provider} className="rounded-xl border border-white/10 bg-slate-950/35 p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="font-bold text-white">{row.provider}</p>
                <Badge tone={row.unpriced_charge_count ? "red" : "green"}>{row.charge_count} charges</Badge>
              </div>
              <p className="mt-2 text-sm text-slate-400">
                {Number(row.input_tokens || 0).toLocaleString()} input tokens | {Number(row.output_tokens || 0).toLocaleString()} output tokens | ${Number(row.cost_usd || 0).toFixed(4)}
              </p>
            </div>
          ))}
        </div>
      ) : <EmptyState title="No provider usage recorded" />}
    </Panel>
  );
}

export function ProvidersPage() {
  const statuses = useAsync(() => runtimeApi.providerStatuses(false), []);

  async function refresh() {
    await runtimeApi.providerStatuses(true);
    await statuses.reload();
  }

  const providers = statuses.value?.providers || {};

  return (
    <div className="space-y-6">
      <ProviderHealthPanel providers={providers} onRefresh={refresh} />
      <UsageGovernancePanel />
      <Panel
        title="Modal ComfyUI Config"
        subtitle="Persist the shared Hugging Face token and Modal account pool in the database, then redeploy from the same stored config."
      >
        <div className="space-y-4">
          <InferenceHealthSummary providers={providers} />
          <ModalComfyUIEditor onSaved={refresh} />
        </div>
      </Panel>
      {!Object.keys(providers).length ? <EmptyState title="No providers configured" /> : null}
    </div>
  );
}
