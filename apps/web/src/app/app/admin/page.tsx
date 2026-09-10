import { redirect } from "next/navigation";
import { ShieldCheck } from "lucide-react";

import { InvitationManager } from "@/features/admin/invitation-manager";
import type { SagaInvitationSummary } from "@/lib/api/admin";
import { getCurrentSagaAccountState, isActiveSagaAdmin } from "@/server/account/current";
import { listPendingSagaInvitations } from "@/server/admin/invitations";

export default async function AdminPage() {
  const state = await getCurrentSagaAccountState();
  if (!isActiveSagaAdmin(state)) redirect("/app");

  let invitations: SagaInvitationSummary[] = [];
  try {
    invitations = await listPendingSagaInvitations();
  } catch {
    // The page remains usable enough to explain configuration while live admin storage is unavailable.
  }

  return (
    <section>
      <div className="max-w-3xl">
        <ShieldCheck className="text-violet-200" size={24} />
        <h1 className="mt-5 text-3xl font-semibold tracking-[-0.035em]">Demo access</h1>
        <p className="mt-4 max-w-2xl text-sm leading-7 text-zinc-500">
          S.A.G.A. is invitation-only. Admin operations are server-authorized and email delivery depends on the configured Supabase Auth mail service.
        </p>
      </div>
      <div className="mt-10"><InvitationManager initialInvitations={invitations} /></div>
    </section>
  );
}
