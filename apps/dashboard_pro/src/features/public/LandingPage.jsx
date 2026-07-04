import { Link } from "react-router-dom";

export function LandingPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col px-5 py-5">
      <nav className="flex items-center justify-between">
        <Link to="/" className="text-sm font-black tracking-[0.24em] text-cyan-100">
          S.A.G.A.
        </Link>
        <div className="flex items-center gap-3">
          <Link to="/signin" className="text-sm font-bold text-slate-300 hover:text-white">
            Sign in
          </Link>
          <Link to="/signup" className="rounded-lg border border-emerald-300/45 bg-emerald-400/15 px-4 py-2 text-sm font-bold text-emerald-50">
            Sign up
          </Link>
        </div>
      </nav>
      <section className="grid flex-1 place-items-center py-20 text-center">
        <div>
          <h1 className="text-5xl font-black tracking-tight text-white">Story Production Studio</h1>
          <p className="mx-auto mt-5 max-w-3xl text-lg leading-8 text-slate-300">
            Import books, inspect canon memory, manage visual assets, generate stories, and produce audiobooks from one connected workspace.
          </p>
          <div className="mt-8 flex justify-center gap-3">
            <Link to="/signup" className="rounded-lg border border-emerald-300/45 bg-emerald-400/15 px-5 py-3 text-sm font-bold text-emerald-50">
              Start building
            </Link>
            <Link to="/overview" className="rounded-lg border border-white/10 bg-white/[0.04] px-5 py-3 text-sm font-bold text-slate-100">
              View studio
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
