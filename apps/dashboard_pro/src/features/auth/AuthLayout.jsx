import { Link } from "react-router-dom";
import { studioPreviewRows } from "../public/publicContent";

export function AuthLayout({ title, subtitle, children, footer }) {
  return (
    <main className="relative min-h-screen overflow-x-hidden text-slate-100">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_18%_8%,rgba(16,185,129,0.14),transparent_27%),radial-gradient(circle_at_78%_12%,rgba(34,211,238,0.12),transparent_24%),linear-gradient(180deg,rgba(6,11,18,0.96),rgba(5,8,14,1))]" />
      <div className="absolute inset-y-0 left-[12%] w-px bg-white/[0.045]" />
      <div className="absolute inset-y-0 right-[18%] w-px bg-white/[0.04]" />

      <div className="relative mx-auto grid min-h-screen max-w-7xl gap-10 px-5 py-8 md:px-7 lg:grid-cols-[0.92fr_1.08fr] lg:items-center lg:py-10">
        <section className="relative hidden min-h-[700px] flex-col justify-between border-r border-white/10 pr-10 lg:flex">
          <div>
            <Link to="/" className="text-sm font-black tracking-[0.3em] text-white">
              S.A.G.A.
            </Link>
          </div>

          <div className="max-w-xl">
            <h2 className="text-4xl font-black tracking-tight text-white xl:text-5xl xl:leading-[1.04]">One studio for every story production stage.</h2>
            <p className="mt-5 text-base leading-7 text-slate-300">
              Keep source imports, canon memory, generated stories, visual assets, providers, and audiobook outputs close to the same operational center.
            </p>
          </div>

          <div className="relative max-w-xl">
            <div className="absolute inset-x-10 top-4 h-36 bg-cyan-300/[0.08] blur-3xl" />
            <div className="relative rounded-lg border border-white/10 bg-slate-950/[0.64] p-5 shadow-2xl shadow-black/25 backdrop-blur">
              <div className="mb-5 flex items-center justify-between">
                <div>
                  <p className="text-[11px] font-black uppercase tracking-[0.18em] text-cyan-200">Workspace</p>
                  <p className="mt-2 text-lg font-black text-white">Production ready</p>
                </div>
                <span className="rounded-full border border-emerald-300/35 bg-emerald-300/[0.1] px-3 py-1 text-[11px] font-black uppercase tracking-[0.16em] text-emerald-100">
                  Live
                </span>
              </div>
              <div className="space-y-2.5">
                {studioPreviewRows.slice(0, 3).map((row) => (
                  <div key={row.label} className="grid grid-cols-[1fr_auto] items-center gap-3 rounded-lg border border-white/10 bg-white/[0.035] px-3.5 py-3">
                    <span className="text-sm font-bold text-slate-200">{row.label}</span>
                    <span className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">{row.detail}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="relative flex min-h-[calc(100vh-4rem)] flex-col justify-center">
          <div className="relative mb-8 flex items-center justify-between lg:hidden">
            <Link to="/" className="text-sm font-black tracking-[0.3em] text-white">
              S.A.G.A.
            </Link>
            <Link to="/overview" className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-bold text-slate-300 transition hover:border-cyan-300/30 hover:bg-cyan-300/[0.08] hover:text-white">
              View studio
            </Link>
          </div>

          <div className="relative mx-auto w-full max-w-[520px]">
            <div className="absolute inset-x-8 top-8 h-44 bg-emerald-300/[0.06] blur-3xl" />
            <div className="relative rounded-lg border border-white/10 bg-[linear-gradient(180deg,rgba(9,14,24,0.92),rgba(5,8,16,0.98))] p-6 shadow-2xl shadow-black/25 backdrop-blur sm:p-8">
              <p className="text-[11px] font-black uppercase tracking-[0.18em] text-cyan-200">Access</p>
              <h1 className="mt-3 text-3xl font-black tracking-tight text-white sm:text-4xl">{title}</h1>
              <p className="mt-3 text-sm leading-6 text-slate-400">{subtitle}</p>
              <div className="mt-7">{children}</div>
            </div>
            {footer ? <div className="mt-5">{footer}</div> : null}
          </div>
        </section>
      </div>
    </main>
  );
}
