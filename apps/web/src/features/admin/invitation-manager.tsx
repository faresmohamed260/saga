"use client";

import { useState, type FormEvent } from "react";
import { MailPlus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type {
  SagaAccessRole,
  SagaInvitationCreateResponse,
  SagaInvitationSummary,
} from "@/lib/api/admin";

export function InvitationManager({ initialInvitations }: { initialInvitations: SagaInvitationSummary[] }) {
  const [invitations, setInvitations] = useState(initialInvitations);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<SagaAccessRole>("member");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function createInvitation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);

    const response = await fetch("/api/admin/invitations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, role }),
    });
    const payload = (await response.json()) as Partial<SagaInvitationCreateResponse> & { error?: string };
    setBusy(false);

    if (!response.ok || !payload.invitation) {
      setMessage(payload.error ?? "The invitation could not be created.");
      return;
    }

    setInvitations((current) => [payload.invitation!, ...current.filter((item) => item.id !== payload.invitation!.id)]);
    setEmail("");
    setMessage(payload.message ?? "Invitation recorded.");
  }

  async function revokeInvitation(invitationId: string) {
    setMessage(null);
    const response = await fetch(`/api/admin/invitations/${invitationId}`, { method: "DELETE" });
    if (!response.ok) {
      const payload = (await response.json()) as { error?: string };
      setMessage(payload.error ?? "The invitation could not be revoked.");
      return;
    }
    setInvitations((current) => current.filter((item) => item.id !== invitationId));
    setMessage("Invitation revoked.");
  }

  return (
    <div className="grid gap-8 xl:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
      <form onSubmit={createInvitation} className="rounded-2xl border border-white/8 bg-white/[0.025] p-5 sm:p-6">
        <div className="mb-6">
          <h2 className="text-lg font-semibold tracking-tight">Invite an account</h2>
          <p className="mt-2 text-sm leading-6 text-zinc-500">
            The invitation record is S.A.G.A. product truth. Email delivery is requested through the configured Supabase Auth provider.
          </p>
        </div>
        <div className="flex flex-col gap-5">
          <Field>
            <FieldLabel htmlFor="invite-email">Email</FieldLabel>
            <Input id="invite-email" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
          </Field>
          <Field>
            <FieldLabel htmlFor="invite-role">Role</FieldLabel>
            <Select id="invite-role" value={role} onChange={(event) => setRole(event.target.value as SagaAccessRole)}>
              <option value="member">Member</option>
              <option value="admin">Admin</option>
            </Select>
            <FieldDescription>Admin invitations grant access to the operator surface after claim.</FieldDescription>
          </Field>
          <Button type="submit" disabled={busy}>
            <MailPlus size={16} />
            {busy ? "Creating…" : "Create invitation"}
          </Button>
          {message ? <p role="status" className="text-sm leading-6 text-amber-100">{message}</p> : null}
        </div>
      </form>

      <section>
        <div className="mb-4 flex items-end justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">Pending invitations</h2>
            <p className="mt-1 text-sm text-zinc-500">Open, unclaimed, unrevoked invitations that have not expired.</p>
          </div>
          <span className="text-xs text-zinc-600">{invitations.length} pending</span>
        </div>
        <div className="overflow-hidden rounded-2xl border border-white/8">
          {invitations.length === 0 ? (
            <div className="bg-white/[0.02] px-5 py-10 text-center text-sm text-zinc-500">No pending invitations.</div>
          ) : (
            invitations.map((invitation) => (
              <div key={invitation.id} className="flex items-center gap-4 border-b border-white/8 bg-white/[0.02] px-4 py-4 last:border-b-0 sm:px-5">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-zinc-100">{invitation.email}</p>
                  <p className="mt-1 text-xs text-zinc-500">
                    {invitation.role} · expires {new Date(invitation.expiresAt).toLocaleString()}
                  </p>
                </div>
                <Button type="button" variant="ghost" size="sm" onClick={() => revokeInvitation(invitation.id)} aria-label={`Revoke invitation for ${invitation.email}`}>
                  <Trash2 size={15} />
                  <span className="hidden sm:inline">Revoke</span>
                </Button>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
