import type { ReactNode } from "react";
import { redirect } from "next/navigation";

import { AppShell } from "@/components/shell/app-shell";
import { getCurrentSagaAccountState } from "@/server/account/current";

export default async function ApplicationLayout({ children }: { children: ReactNode }) {
  const state = await getCurrentSagaAccountState();
  if (state.status !== "active") redirect("/login");

  return (
    <AppShell email={state.identity.email} role={state.access.role}>
      {children}
    </AppShell>
  );
}
