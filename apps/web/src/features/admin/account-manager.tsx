"use client";

import { useState } from "react";
import { ShieldCheck, UserRound } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import type {
  SagaAccessRole,
  SagaAccessStatus,
  SagaAdminAccountSummary,
} from "@/lib/api/admin";

export function AccountManager({
  initialAccounts,
  currentUserId,
}: {
  initialAccounts: SagaAdminAccountSummary[];
  currentUserId: string;
}) {
  const [accounts, setAccounts] = useState(initialAccounts);
  const [pendingUserId, setPendingUserId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function updateAccount(
    userId: string,
    update: { role?: SagaAccessRole; status?: SagaAccessStatus },
  ) {
    setMessage(null);
    setPendingUserId(userId);
    const response = await fetch(`/api/admin/accounts/${userId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(update),
    });
    const payload = (await response.json()) as { account?: SagaAdminAccountSummary; error?: string };
    setPendingUserId(null);

    if (!response.ok || !payload.account) {
      setMessage(payload.error ?? "The account could not be updated.");
      return;
    }

    setAccounts((current) => current.map((account) => account.userId === userId ? payload.account! : account));
    setMessage("Account access updated.");
  }

  return (
    <section>
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Admitted accounts</h2>
          <p className="mt-1 text-sm text-zinc-500">Roles and demo admission state are S.A.G.A.-owned, not browser/Auth metadata.</p>
        </div>
        <span className="text-xs text-zinc-600">{accounts.length} accounts</span>
      </div>

      {message ? <p role="status" className="mb-4 text-sm leading-6 text-amber-100">{message}</p> : null}

      <div className="overflow-hidden rounded-2xl border border-white/8">
        {accounts.length === 0 ? (
          <div className="bg-white/[0.02] px-5 py-10 text-center text-sm text-zinc-500">No admitted accounts.</div>
        ) : accounts.map((account) => {
          const isSelf = account.userId === currentUserId;
          const busy = pendingUserId === account.userId;
          return (
            <div key={account.userId} className="grid gap-4 border-b border-white/8 bg-white/[0.02] px-4 py-4 last:border-b-0 sm:px-5 lg:grid-cols-[minmax(0,1fr)_150px_150px] lg:items-center">
              <div className="flex min-w-0 items-center gap-3">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-white/8 bg-white/[0.03] text-zinc-400">
                  {account.role === "admin" ? <ShieldCheck size={16} /> : <UserRound size={16} />}
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-zinc-100">{account.email ?? account.userId}</p>
                  <p className="mt-1 text-xs text-zinc-600">{isSelf ? "Current account" : account.userId}</p>
                </div>
              </div>

              <Select
                aria-label={`Role for ${account.email ?? account.userId}`}
                value={account.role}
                disabled={busy || isSelf}
                onChange={(event) => updateAccount(account.userId, { role: event.target.value as SagaAccessRole })}
              >
                <option value="member">Member</option>
                <option value="admin">Admin</option>
              </Select>

              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant={account.status === "active" ? "secondary" : "primary"}
                  size="sm"
                  disabled={busy || isSelf}
                  onClick={() => updateAccount(account.userId, { status: account.status === "active" ? "suspended" : "active" })}
                >
                  {busy ? "Updating…" : account.status === "active" ? "Suspend" : "Reactivate"}
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
