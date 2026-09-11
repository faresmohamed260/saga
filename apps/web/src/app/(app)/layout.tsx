import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { resolveCurrentSagaAccount } from "@/server/account/account-access";

export const dynamic = "force-dynamic";

export default async function PrivateAppLayout({ children }: Readonly<{ children: ReactNode }>) {
  const resolution = await resolveCurrentSagaAccount();

  switch (resolution.state) {
    case "active":
      return children;
    case "unauthenticated":
      redirect("/sign-in");
    case "not_admitted":
      redirect("/access/not-admitted");
    case "suspended":
      redirect("/access/suspended");
    case "unavailable":
      redirect("/access/unavailable");
  }
}
