import { redirect } from "next/navigation";
import { ShieldCheck } from "lucide-react";

import { AccountManager } from "@/features/admin/account-manager";
import { InvitationManager } from "@/features/admin/invitation-manager";
import type { SagaAdminAccountSummary, SagaInvitationSummary } from "@/lib/api/admin";
import { getCurrentSagaAccountState, isActiveSagaAdmin } from "@/server/account/current";
import { listSagaAdminAccounts } from "@/server/admin/accounts";
import { listPendingSagaInvitations } from "@/server/admin/invitations";

export default async function AdminPage() {
  const state = await getCurrentSagaAccountState();
  if (!isActiveSagaAdmin(state)) redirect("/app");

  let invitations: SagaInvitationSummary[] = [];
  let accounts: SagaAdminAccountSummary[] = [];
  try {
    [invitations, accounts] = await Promise.all([
      listPendingSagaInvitations(),
      listSagaAdminAccounts(),
    ]);
  } catch {
    // Keep the bounded operator surface available enough to explain unavailable live configuration.
  }

  return (
    <section>
      <div className="max-w-3xl">
        <ShieldCheck className="text-violet-200" size={24} />
        <h1 className="mt-5 text-3xl font-semibold tracking-[-0.035em]">Demo access</h1>
        <p className="mt-4 max-w-2xl text-sm leading-7 text-zinc-500">
          S.A.G.A. is invitation-only. Account admission and admin operations are server-authorized; email delivery depends on the configured Supabase Auth mail service.
        </p>
      </div>

      <div className="mt-10 flex flex-col gap-12">
        <InvitationManager initialInvitations={invitations} />
        <AccountManager initialAccounts={accounts} currentUserId={state.identity.id} />
      </div>
    </section>
  );
}
