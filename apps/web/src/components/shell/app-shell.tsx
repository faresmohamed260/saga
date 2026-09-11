import type { ReactNode } from "react";

import type { SagaAccount } from "@/server/account/types";

import { DesktopNavigation, MobileNavigation } from "./app-navigation";

type AppShellProps = Readonly<{
  account: SagaAccount;
  children: ReactNode;
}>;

export function AppShell({ account, children }: AppShellProps) {
  return (
    <div className="saga-app min-h-screen bg-[var(--app-canvas)] text-[var(--app-text)]">
      <DesktopNavigation email={account.email} />
      <MobileNavigation email={account.email} />
      <div className="min-h-screen pt-14 md:pl-56 md:pt-0 lg:pl-[14.5rem]">
        <main className="mx-auto w-full max-w-[96rem] px-4 py-7 sm:px-5 sm:py-9 md:px-7 lg:px-9 xl:px-10">
          {children}
        </main>
      </div>
    </div>
  );
}
