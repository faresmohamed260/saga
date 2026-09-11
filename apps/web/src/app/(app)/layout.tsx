import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { AppShell } from "@/components/shell/app-shell";
import { resolveCurrentSagaAccount } from "@/server/account/account-access";

export default async function PrivateAppLayout({ children }: Readonly<{ children: ReactNode }>) {
  const access = await resolveCurrentSagaAccount();

  switch (access.state) {
    case "active":
      return <AppShell account={access.account}>{children}</AppShell>;
    case "unauthenticated":
      redirect("/sign-in?next=/home");
    case "not_admitted":
      redirect("/access/not-admitted");
    case "suspended":
      redirect("/access/suspended");
    case "unavailable":
      redirect("/access/unavailable");
  }
}
