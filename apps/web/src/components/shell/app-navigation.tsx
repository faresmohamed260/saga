"use client";

import Link from "next/link";
import { Activity, BookOpenText, FolderKanban, LayoutDashboard, Settings, ShieldCheck } from "lucide-react";
import { usePathname } from "next/navigation";

import type { SagaAccessRole } from "@/lib/api/admin";
import { cn } from "@/lib/utils";

const primary = [
  { href: "/app", label: "Home", icon: LayoutDashboard },
  { href: "/app/library", label: "Library", icon: BookOpenText },
  { href: "/app/projects", label: "Projects", icon: FolderKanban },
  { href: "/app/activity", label: "Activity", icon: Activity },
];

function isActive(pathname: string, href: string) {
  if (href === "/app") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppNavigation({ role }: { role: SagaAccessRole }) {
  const pathname = usePathname();
  const items = role === "admin"
    ? [...primary, { href: "/app/admin", label: "Admin", icon: ShieldCheck }]
    : primary;

  return (
    <>
      <nav className="hidden flex-col gap-1 lg:flex" aria-label="Primary">
        {items.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex h-10 items-center gap-3 rounded-lg px-3 text-sm transition",
              isActive(pathname, href)
                ? "bg-white/[0.08] text-white"
                : "text-zinc-400 hover:bg-white/[0.045] hover:text-zinc-100",
            )}
          >
            <Icon size={17} strokeWidth={1.8} />
            {label}
          </Link>
        ))}
        <Link
          href="/app/settings"
          className={cn(
            "mt-4 flex h-10 items-center gap-3 rounded-lg px-3 text-sm transition",
            isActive(pathname, "/app/settings")
              ? "bg-white/[0.08] text-white"
              : "text-zinc-400 hover:bg-white/[0.045] hover:text-zinc-100",
          )}
        >
          <Settings size={17} strokeWidth={1.8} />
          Settings
        </Link>
      </nav>

      <nav
        className="fixed inset-x-3 bottom-3 z-40 grid grid-cols-4 rounded-2xl border border-white/10 bg-[#0c1119]/95 p-1.5 shadow-2xl backdrop-blur-xl lg:hidden"
        aria-label="Mobile primary"
      >
        {primary.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex min-h-12 flex-col items-center justify-center gap-1 rounded-xl text-[11px] transition",
              isActive(pathname, href) ? "bg-white/[0.08] text-white" : "text-zinc-500",
            )}
          >
            <Icon size={18} strokeWidth={1.8} />
            {label}
          </Link>
        ))}
      </nav>
    </>
  );
}
