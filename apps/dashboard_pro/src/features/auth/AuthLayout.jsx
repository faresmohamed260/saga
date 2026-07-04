import { Link } from "react-router-dom";
import { studioPreviewRows } from "../public/publicContent";

export function AuthLayout({ title, subtitle, children, footer }) {
  return (
    <main className="min-h-screen px-5 py-6 text-slate-100 md:px-7">
      <div className="mx-auto grid min-h-[calc(100vh-3rem)] max-w-6xl overflow-hidden rounded-lg border border-white/10 bg-slate-950/55 shadow-2xl shadow-black/25 lg:grid-cols-[0.95fr_1.05fr]">
        <section className="relative hidden border-r border-white/10 bg-slate-950/70 p-8 lg:block">
          <div className="absolute inset-0 bg-[linear-gradient(135deg,rgba(20,184,166,0.12),transparent_36%),linear-gradient(215deg,rgba(8,47,73,0.18),transparent_52%)]" />
          <div className="relative flex h-full flex-col justify-between">
            <div>
              <Link to="/" className="text-sm font-black tracking-[0.24em] text-cyan-100">
                S.A.G.A.
              </Link>
              <h2 className="mt-12 max-w-md text-4xl font-black tracking-tight text-white">One studio for every story production stage.</h2>
              <p className="mt-4 max-w-md text-sm leading-6 text-slate-400">
                Keep source imports, canon memory, generated stories, visual assets, providers, and audiobook outputs close to the same operational center.
              </p>
            </div>

            <div className="rounded-lg border border-white/10 bg-slate-950/65 p-4 shadow-xl shadow-black/20">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <p className="text-xs font-black uppercase tracking-[0.18em] text-cyan-200">Workspace</p>
                  <p className="mt-1 text-lg font-black text-white">Production ready</p>
                </div>
                <span className="rounded-lg border border-emerald-300/35 bg-emerald-400/10 px-3 py-1 text-xs font-black uppercase tracking-[0.14em] text-emerald-100">
                  Live
                </span>
              </div>
              <div className="space-y-3">
                {studioPreviewRows.slice(0, 3).map((row) => (
                  <div key={row.label} className="flex items-center justify-between rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
                    <span className="text-sm font-bold text-slate-200">{row.label}</span>
                    <span className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">{row.detail}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="flex flex-col justify-center p-6 sm:p-8 lg:p-12">
          <div className="mb-10 flex items-center justify-between lg:hidden">
            <Link to="/" className="text-sm font-black tracking-[0.24em] text-cyan-100">
              S.A.G.A.
            </Link>
            <Link to="/overview" className="text-sm font-bold text-slate-400 transition hover:text-white">
              View studio
            </Link>
          </div>
          <div className="mx-auto w-full max-w-md">
            <h1 className="text-3xl font-black tracking-tight text-white">{title}</h1>
            <p className="mt-3 text-sm leading-6 text-slate-400">{subtitle}</p>
            <div className="mt-7">{children}</div>
            {footer ? <div className="mt-6">{footer}</div> : null}
          </div>
        </section>
      </div>
    </main>
  );
}
