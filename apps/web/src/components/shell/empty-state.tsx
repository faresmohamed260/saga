import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

type EmptyStateProps = Readonly<{
  icon: LucideIcon;
  title: string;
  description: string;
  action?: ReactNode;
}>;

export function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <section
      className="flex min-h-64 flex-col items-start justify-center border-y border-[var(--app-separator)] py-12"
      aria-labelledby={`empty-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
    >
      <div className="mb-5 flex size-10 items-center justify-center rounded-full border border-[var(--app-separator)] bg-[var(--app-surface)] text-[var(--app-muted)]">
        <Icon aria-hidden="true" className="size-[18px]" strokeWidth={1.8} />
      </div>
      <h2
        id={`empty-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
        className="text-base font-semibold tracking-[-0.01em] text-[var(--app-text)]"
      >
        {title}
      </h2>
      <p className="mt-2 max-w-xl text-sm leading-6 text-[var(--app-muted)]">{description}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </section>
  );
}
