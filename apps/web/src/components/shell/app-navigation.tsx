"use client";

import { BookOpen, FolderKanban, Home, LogOut, Menu, Settings, ShieldCheck, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Dialog } from "radix-ui";

import { signOutAction } from "@/features/auth/actions";

type AppNavigationProps = Readonly<{
  email: string;
  isAdmin: boolean;
}>;

type NavigationItem = Readonly<{
  href: string;
  label: string;
  icon: typeof Home;
}>;

const primaryItems: readonly NavigationItem[] = [
  { href: "/home", label: "Home", icon: Home },
  { href: "/library", label: "Library", icon: BookOpen },
  { href: "/projects", label: "Projects", icon: FolderKanban },
];

const settingsItem: NavigationItem = { href: "/settings", label: "Settings", icon: Settings };
const adminItem: NavigationItem = { href: "/admin", label: "Admin", icon: ShieldCheck };

function accountItems(isAdmin: boolean): readonly NavigationItem[] {
  return isAdmin ? [adminItem, settingsItem] : [settingsItem];
}

function isCurrentRoute(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function NavigationLink({ item, pathname, onNavigate }: Readonly<{
  item: NavigationItem;
  pathname: string;
  onNavigate?: () => void;
}>) {
  const current = isCurrentRoute(pathname, item.href);
  const Icon = item.icon;

  return (
    <Link
      href={item.href}
      aria-current={current ? "page" : undefined}
      onClick={onNavigate}
      className={`group relative flex min-h-11 items-center gap-3 rounded-lg px-3 text-sm transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--app-rail)] ${
        current
          ? "bg-white/[0.075] font-semibold text-[var(--app-text)]"
          : "font-medium text-[var(--app-muted)] hover:bg-white/[0.045] hover:text-[var(--app-text)]"
      }`}
    >
      {current ? (
        <span aria-hidden="true" className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-[var(--app-accent)]" />
      ) : null}
      <Icon aria-hidden="true" className="size-[18px] shrink-0" strokeWidth={1.8} />
      <span>{item.label}</span>
    </Link>
  );
}

function ProductMark() {
  return (
    <Link
      href="/home"
      className="inline-flex items-center gap-2.5 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
      aria-label="S.A.G.A. Home"
    >
      <span className="flex size-7 items-center justify-center rounded-md border border-[var(--app-separator)] bg-[var(--app-surface)] text-[0.68rem] font-bold tracking-[-0.04em] text-[var(--app-text)]">
        S
      </span>
      <span className="text-sm font-semibold tracking-[0.18em] text-[var(--app-text)]">S.A.G.A.</span>
    </Link>
  );
}

export function DesktopNavigation({ email, isAdmin }: AppNavigationProps) {
  const pathname = usePathname();
  const secondaryItems = accountItems(isAdmin);

  return (
    <aside className="fixed inset-y-0 left-0 hidden w-56 border-r border-[var(--app-separator)] bg-[var(--app-rail)] px-3 py-5 md:flex md:flex-col lg:w-[14.5rem]">
      <div className="px-2 pb-7"><ProductMark /></div>

      <nav aria-label="Primary" className="flex flex-col gap-1">
        {primaryItems.map((item) => <NavigationLink key={item.href} item={item} pathname={pathname} />)}
      </nav>

      <div className="mt-auto flex flex-col gap-4">
        <nav aria-label="Account" className="flex flex-col gap-1 border-t border-[var(--app-separator)] pt-4">
          {secondaryItems.map((item) => <NavigationLink key={item.href} item={item} pathname={pathname} />)}
        </nav>

        <div className="border-t border-[var(--app-separator)] px-2 pt-4">
          <p className="truncate text-xs font-medium text-[var(--app-text)]" title={email}>{email}</p>
          <form action={signOutAction} className="mt-2">
            <button type="submit" className="-ml-2 inline-flex min-h-10 items-center gap-2 rounded-md px-2 text-xs font-medium text-[var(--app-muted)] transition-colors hover:text-[var(--app-text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]">
              <LogOut aria-hidden="true" className="size-4" strokeWidth={1.8} />
              Sign out
            </button>
          </form>
        </div>
      </div>
    </aside>
  );
}

export function MobileNavigation({ email, isAdmin }: AppNavigationProps) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const secondaryItems = accountItems(isAdmin);
  const currentItem = [...primaryItems, ...secondaryItems].find((item) => isCurrentRoute(pathname, item.href));

  return (
    <div className="md:hidden">
      <header className="fixed inset-x-0 top-0 z-30 flex h-14 items-center justify-between border-b border-[var(--app-separator)] bg-[var(--app-rail)] px-4">
        <ProductMark />
        <span className="max-w-[35vw] truncate text-xs font-medium text-[var(--app-muted)]">{currentItem?.label ?? "Workspace"}</span>
        <Dialog.Root open={open} onOpenChange={setOpen}>
          <Dialog.Trigger asChild>
            <button type="button" aria-label="Open navigation" className="flex size-11 items-center justify-center rounded-lg text-[var(--app-text)] transition-colors hover:bg-white/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]">
              <Menu aria-hidden="true" className="size-5" strokeWidth={1.8} />
            </button>
          </Dialog.Trigger>

          <Dialog.Portal>
            <Dialog.Overlay className="saga-nav-overlay fixed inset-0 z-40 bg-black/60" />
            <Dialog.Content className="saga-portal-theme saga-nav-sheet fixed inset-y-0 left-0 z-50 flex w-[min(86vw,22rem)] flex-col border-r border-[var(--app-separator)] bg-[var(--app-rail)] p-4 shadow-2xl focus:outline-none">
              <div className="flex min-h-11 items-center justify-between px-1">
                <Dialog.Title className="text-sm font-semibold tracking-[0.16em] text-[var(--app-text)]">S.A.G.A.</Dialog.Title>
                <Dialog.Description className="sr-only">Navigate the S.A.G.A. workspace.</Dialog.Description>
                <Dialog.Close asChild>
                  <button type="button" aria-label="Close navigation" className="flex size-11 items-center justify-center rounded-lg text-[var(--app-muted)] hover:bg-white/[0.05] hover:text-[var(--app-text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]">
                    <X aria-hidden="true" className="size-5" strokeWidth={1.8} />
                  </button>
                </Dialog.Close>
              </div>

              <nav aria-label="Primary" className="mt-6 flex flex-col gap-1">
                {primaryItems.map((item) => (
                  <NavigationLink key={item.href} item={item} pathname={pathname} onNavigate={() => setOpen(false)} />
                ))}
              </nav>

              <div className="mt-auto flex flex-col gap-4">
                <nav aria-label="Account" className="flex flex-col gap-1 border-t border-[var(--app-separator)] pt-4">
                  {secondaryItems.map((item) => (
                    <NavigationLink key={item.href} item={item} pathname={pathname} onNavigate={() => setOpen(false)} />
                  ))}
                </nav>
                <div className="border-t border-[var(--app-separator)] px-2 pt-4">
                  <p className="truncate text-xs font-medium text-[var(--app-text)]" title={email}>{email}</p>
                  <form action={signOutAction} className="mt-2">
                    <button type="submit" className="-ml-2 inline-flex min-h-11 items-center gap-2 rounded-md px-2 text-sm font-medium text-[var(--app-muted)] hover:text-[var(--app-text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]">
                      <LogOut aria-hidden="true" className="size-4" strokeWidth={1.8} />
                      Sign out
                    </button>
                  </form>
                </div>
              </div>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
      </header>
    </div>
  );
}
