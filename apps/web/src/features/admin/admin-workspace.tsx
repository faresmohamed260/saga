import { PageHeader } from "@/components/shell/page-header";
import type { SagaAdminAccount, SagaAdminInvitation } from "@/server/admin/admin-operations";

import {
  createInvitationAction,
  revokeInvitationAction,
  updateAccountAction,
} from "./actions";

const noticeCopy: Record<string, string> = {
  invitation_sent: "Invitation intent saved and the Auth provider accepted the delivery request.",
  invitation_saved: "Invitation intent saved.",
  delivery_failed: "Invitation intent is saved, but email delivery was not accepted. You can retry or revoke it safely.",
  invitation_revoked: "Pending invitation revoked.",
  invitation_expired: "The invitation was already expired.",
  account_updated: "Account access updated.",
  invalid_request: "That request was invalid.",
  conflict: "The request conflicts with existing S.A.G.A. access or invitation state.",
  forbidden: "That change is not allowed by the account safety rules.",
  not_found: "The requested S.A.G.A. record no longer exists.",
  unavailable: "Admin operations are temporarily unavailable.",
};

function formatWhen(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString("en", { dateStyle: "medium", timeStyle: "short" });
}

export function AdminWorkspace({
  currentUserId,
  invitations,
  accounts,
  notice,
}: Readonly<{
  currentUserId: string;
  invitations: SagaAdminInvitation[];
  accounts: SagaAdminAccount[];
  notice?: string;
}>) {
  const message = notice ? noticeCopy[notice] : undefined;
  const pendingInvitations = invitations.filter((invitation) => invitation.status === "pending");

  return (
    <div className="flex flex-col gap-10">
      <PageHeader
        eyebrow="Closed demo"
        title="Admin"
        description="Manage S.A.G.A.-owned invitations and admitted accounts. Identity credentials remain owned by Supabase Auth."
      />

      {message ? (
        <p role="status" className="max-w-4xl border-y border-[var(--app-separator)] py-3 text-sm leading-6 text-[var(--app-muted)]">
          {message}
        </p>
      ) : null}

      <section className="max-w-6xl" aria-labelledby="invite-heading">
        <div className="flex flex-col gap-6 border-b border-[var(--app-separator)] pb-7 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <h2 id="invite-heading" className="text-base font-semibold text-[var(--app-text)]">Invitations</h2>
            <p className="mt-1 text-sm leading-6 text-[var(--app-muted)]">
              Creating the same pending email and role again is a delivery retry, not a second invitation record.
            </p>
          </div>

          <form action={createInvitationAction} className="grid w-full gap-3 sm:grid-cols-[minmax(0,1fr)_8rem_auto] lg:max-w-2xl">
            <label className="grid gap-1 text-xs font-medium text-[var(--app-muted)]">
              Email
              <input
                required
                type="email"
                name="email"
                autoComplete="email"
                className="min-h-11 rounded-lg border border-[var(--app-separator)] bg-[var(--app-surface)] px-3 text-sm text-[var(--app-text)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
                placeholder="reader@example.com"
              />
            </label>
            <label className="grid gap-1 text-xs font-medium text-[var(--app-muted)]">
              Role
              <select name="role" defaultValue="member" className="min-h-11 rounded-lg border border-[var(--app-separator)] bg-[var(--app-surface)] px-3 text-sm text-[var(--app-text)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]">
                <option value="member">Member</option>
                <option value="admin">Admin</option>
              </select>
            </label>
            <button type="submit" className="min-h-11 self-end rounded-lg bg-[var(--app-text)] px-4 text-sm font-semibold text-[var(--app-canvas)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]">
              Invite
            </button>
          </form>
        </div>

        {pendingInvitations.length === 0 ? (
          <p className="border-b border-[var(--app-separator)] py-8 text-sm text-[var(--app-muted)]">No pending invitations.</p>
        ) : (
          <ul className="divide-y divide-[var(--app-separator)] border-b border-[var(--app-separator)]">
            {pendingInvitations.map((invitation) => (
              <li key={invitation.id} className="grid gap-4 py-5 lg:grid-cols-[minmax(0,1fr)_8rem_12rem_auto] lg:items-center">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-[var(--app-text)]">{invitation.emailDisplay}</p>
                  <p className="mt-1 text-xs text-[var(--app-muted)]">Invited {formatWhen(invitation.invitedAt)}</p>
                </div>
                <p className="text-sm capitalize text-[var(--app-muted)]">{invitation.intendedRole}</p>
                <p className="text-xs text-[var(--app-muted)]">Expires {formatWhen(invitation.expiresAt)}</p>
                <form action={revokeInvitationAction}>
                  <input type="hidden" name="invitationId" value={invitation.id} />
                  <button type="submit" className="min-h-11 rounded-lg border border-[var(--app-separator)] px-3 text-sm font-medium text-[var(--app-muted)] hover:text-[var(--app-text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]">
                    Revoke
                  </button>
                </form>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="max-w-6xl" aria-labelledby="accounts-heading">
        <div className="border-b border-[var(--app-separator)] pb-4">
          <h2 id="accounts-heading" className="text-base font-semibold text-[var(--app-text)]">Admitted accounts</h2>
          <p className="mt-1 text-sm leading-6 text-[var(--app-muted)]">
            This list begins from S.A.G.A. account-access rows. It does not enumerate the shared Auth user directory.
          </p>
        </div>

        <ul className="divide-y divide-[var(--app-separator)] border-b border-[var(--app-separator)]">
          {accounts.map((account) => {
            const isCurrent = account.userId === currentUserId;
            return (
              <li key={account.userId} className="grid gap-4 py-5 xl:grid-cols-[minmax(0,1fr)_9rem_9rem_auto] xl:items-center">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate text-sm font-semibold text-[var(--app-text)]">{account.email}</p>
                    {isCurrent ? <span className="text-[0.68rem] font-semibold uppercase tracking-[0.12em] text-[var(--app-accent)]">Current session</span> : null}
                  </div>
                  <p className="mt-1 text-xs text-[var(--app-muted)]">Accepted {formatWhen(account.acceptedAt)}</p>
                </div>

                {isCurrent ? (
                  <>
                    <p className="text-sm capitalize text-[var(--app-muted)]">{account.role}</p>
                    <p className="text-sm capitalize text-[var(--app-muted)]">{account.status}</p>
                    <p className="text-xs text-[var(--app-muted)]">Self-demotion and self-suspension are blocked.</p>
                  </>
                ) : (
                  <form action={updateAccountAction} className="contents">
                    <input type="hidden" name="userId" value={account.userId} />
                    <label className="grid gap-1 text-xs font-medium text-[var(--app-muted)]">
                      Role
                      <select name="role" defaultValue={account.role} className="min-h-11 rounded-lg border border-[var(--app-separator)] bg-[var(--app-surface)] px-2 text-sm capitalize text-[var(--app-text)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]">
                        <option value="member">Member</option>
                        <option value="admin">Admin</option>
                      </select>
                    </label>
                    <label className="grid gap-1 text-xs font-medium text-[var(--app-muted)]">
                      Status
                      <select name="status" defaultValue={account.status} className="min-h-11 rounded-lg border border-[var(--app-separator)] bg-[var(--app-surface)] px-2 text-sm capitalize text-[var(--app-text)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]">
                        <option value="active">Active</option>
                        <option value="suspended">Suspended</option>
                      </select>
                    </label>
                    <button type="submit" className="min-h-11 self-end rounded-lg border border-[var(--app-separator)] px-3 text-sm font-semibold text-[var(--app-text)] hover:bg-[var(--app-surface)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]">
                      Save
                    </button>
                  </form>
                )}
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}
