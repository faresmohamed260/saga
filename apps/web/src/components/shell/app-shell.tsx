import Link from "next/link";
import type { ReactNode } from "react";
import { Sparkles } from "lucide-react";

import { AppNavigation } from "./app-navigation";
import { SignOutButton } from "@/features/account/sign-out-button";
import type { SagaAccessRole } from "@/lib/api/admin";

export function AppShell({
  children,
  email,
  role,
}: {
  children: ReactNode;
  email: string | null;
  role: SagaAccessRole;
}) {
  return (
    <div className="min-h-screen bg-[var(--background)] text-white lg:grid lg:grid-cols-[216px_minmax(0,1fr)]">
      <aside className="hidden min-h-screen border-r border-white/8 bg-[#090d14]/90 p-4 lg:flex lg:flex-col">
        <Link href="/app" className="flex h-12 items-center gap-3 px-2" aria-label="S.A.G.A. application home">
          <span className="flex size-8 items-center justify-center rounded-lg border border-violet-300/20 bg-violet-400/10 text-violet-200">
            <Sparkles size={16} strokeWidth={1.8} />
          </span>
          <span className="text-sm font-semibold tracking-[0.2em]">S.A.G.A.</span>
        </Link>
        <div className="mt-5 flex-1">
          <AppNavigation role={role} />
        </div>
        <div className="border-t border-white/8 pt-4">
          <p className="truncate px-2 text-xs text-zinc-500">{email ?? "Account"}</p>
          <div className="mt-2"><SignOutButton compact /></div>
        </div>
      </aside>

      <div className="min-w-0 pb-24 lg:pb-0">
        <header className="flex h-16 items-center justify-between border-b border-white/8 px-5 lg:hidden">
          <Link href="/app" className="flex items-center gap-2 text-sm font-semibold tracking-[0.18em]">
            <Sparkles size={16} className="text-violet-200" />
            S.A.G.A.
          </Link>
          <Link href="/app/settings" className="text-xs text-zinc-400">Account</Link>
        </header>
        <main className="mx-auto w-full max-w-[1440px] px-5 py-7 sm:px-8 lg:px-10 lg:py-9">{children}</main>
      </div>
    </div>
  );
}
