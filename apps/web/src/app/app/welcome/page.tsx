import { redirect } from "next/navigation";
import { KeyRound } from "lucide-react";

import { SetPasswordForm } from "@/features/account/set-password-form";
import { getCurrentSagaAccountState } from "@/server/account/current";

export default async function WelcomePage() {
  const state = await getCurrentSagaAccountState();
  if (state.status !== "active") redirect("/login");

  return (
    <section className="mx-auto max-w-2xl py-6 sm:py-10">
      <KeyRound className="text-violet-200" size={26} strokeWidth={1.7} />
      <h1 className="mt-5 text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">Finish your account setup.</h1>
      <p className="mt-4 max-w-xl text-sm leading-7 text-zinc-500 sm:text-base">
        Your invitation has been accepted for {state.identity.email ?? "this account"}. Set a password so you can return to the closed demo after this invitation session ends.
      </p>
      <div className="mt-8 rounded-2xl border border-white/8 bg-white/[0.025] p-5 sm:p-7">
        <SetPasswordForm />
      </div>
    </section>
  );
}
