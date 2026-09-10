import { Settings } from "lucide-react";

import { SignOutButton } from "@/features/account/sign-out-button";
import { getCurrentSagaAccountState } from "@/server/account/current";

export default async function SettingsPage() {
  const state = await getCurrentSagaAccountState();
  if (state.status !== "active") return null;

  return (
    <section className="max-w-3xl">
      <Settings className="text-violet-200" size={24} />
      <h1 className="mt-5 text-3xl font-semibold tracking-[-0.035em]">Account</h1>
      <div className="mt-8 divide-y divide-white/8 overflow-hidden rounded-2xl border border-white/8 bg-white/[0.02]">
        <div className="grid gap-2 px-5 py-5 sm:grid-cols-[160px_1fr]">
          <span className="text-sm text-zinc-500">Email</span>
          <span className="text-sm text-zinc-100">{state.identity.email ?? "Unavailable"}</span>
        </div>
        <div className="grid gap-2 px-5 py-5 sm:grid-cols-[160px_1fr]">
          <span className="text-sm text-zinc-500">Role</span>
          <span className="text-sm capitalize text-zinc-100">{state.access.role}</span>
        </div>
        <div className="grid gap-2 px-5 py-5 sm:grid-cols-[160px_1fr]">
          <span className="text-sm text-zinc-500">Access</span>
          <span className="text-sm capitalize text-zinc-100">{state.access.status}</span>
        </div>
      </div>
      <div className="mt-6"><SignOutButton /></div>
    </section>
  );
}
