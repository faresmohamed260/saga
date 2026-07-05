import { Link } from "react-router-dom";
import { studioPreviewRows } from "../public/publicContent";

export function AuthLayout({ title, subtitle, children, footer }) {
  return (
    <main className="relative min-h-screen overflow-hidden px-5 py-6 text-slate-100 md:px-7">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_12%_8%,rgba(16,185,129,0.12),transparent_24%),radial-gradient(circle_at_82%_18%,rgba(34,211,238,0.1),transparent_22%),linear-gradient(180deg,rgba(5,10,16,0.98),rgba(4,8,14,1))]" />
      <div className="absolute inset-y-0 left-[16%] w-px bg-white/[0.04]" />
      <div className="absolute inset-y-0 right-[14%] w-px bg-white/[0.04]" />

      <div className="relative mx-auto grid min-h-[calc(100vh-3rem)] max-w-6xl overflow-hidden rounded-[30px] border border-white/10 bg-slate-950/55 shadow-[0_30px_120px_rgba(0,0,0,0.4)] lg:grid-cols-[1.02fr_0.98fr]">
        <section className="relative hidden border-r border-white/10 bg-[linear-gradient(180deg,rgba(6,16,24,0.96),rgba(6,12,20,0.98))] p-10 lg:block">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(20,184,166,0.12),transparent_32%),linear-gradient(135deg,rgba(14,116,144,0.08),transparent_38%)]" />
          <div className="relative flex h-full flex-col justify-between">
            <div>
              <Link to="/" className="text-sm font-black tracking-[0.3em] text-slate-50">
                S.A.G.A.
              </Link>
              <div className="mt-16 inline-flex rounded-full border border-cyan-300/18 bg-cyan-300/[0.06] px-4 py-2 text-[11px] font-black uppercase tracking-[0.22em] text-cyan-100">
                Narrative production workspace
              </div>
              <h2 className="mt-8 max-w-lg text-5xl font-black tracking-[-0.03em] text-white">One studio for every story production stage.</h2>
              <p className="mt-5 max-w-lg text-base leading-8 text-slate-400">
                Keep source imports, canon memory, generated stories, visual assets, providers, and audiobook outputs close to the same operational center.
              </p>
            </div>

            <div className="rounded-[24px] border border-white/10 bg-slate-950/68 p-5 shadow-xl shadow-black/25">
              <div className="mb-5 flex items-center justify-between">
                <div>
                  <p className="text-[11px] font-black uppercase tracking-[0.2em] text-cyan-200">Workspace</p>
                  <p className="mt-2 text-xl font-black text-white">Production ready</p>
                </div>
                <span className="rounded-full border border-emerald-300/35 bg-emerald-400/10 px-3 py-1 text-[11px] font-black uppercase tracking-[0.16em] text-emerald-100">
                  Live
                </span>
              </div>
              <div className="space-y-3">
                {studioPreviewRows.slice(0, 3).map((row) => (
                  <div key={row.label} className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3">
                    <span className="text-sm font-bold text-slate-200">{row.label}</span>
                    <span className="text-[11px] font-black uppercase tracking-[0.16em] text-slate-500">{row.detail}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="relative flex flex-col justify-center p-6 sm:p-8 lg:p-12">
          <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(3,8,18,0.86),rgba(5,9,18,0.94))]" />
          <div className="relative mb-10 flex items-center justify-between lg:hidden">
            <Link to="/" className="text-sm font-black tracking-[0.3em] text-slate-50">
              S.A.G.A.
            </Link>
            <Link to="/overview" className="text-sm font-bold text-slate-400 transition hover:text-white">
              View studio
            </Link>
          </div>
          <div className="relative mx-auto w-full max-w-md">
            <div className="rounded-[28px] border border-white/10 bg-[linear-gradient(180deg,rgba(9,14,24,0.94),rgba(5,8,16,0.98))] p-7 shadow-2xl shadow-black/25 sm:p-8">
              <p className="text-[11px] font-black uppercase tracking-[0.22em] text-cyan-200">Access</p>
              <h1 className="mt-4 text-4xl font-black tracking-[-0.03em] text-white">{title}</h1>
              <p className="mt-3 text-sm leading-7 text-slate-400">{subtitle}</p>
              <div className="mt-8">{children}</div>
            </div>
            {footer ? <div className="mt-6">{footer}</div> : null}
          </div>
        </section>
      </div>
    </main>
  );
}
