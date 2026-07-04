import { Link } from "react-router-dom";

export function SignInPage() {
  return (
    <main className="grid min-h-screen place-items-center px-5 py-10">
      <section className="w-full max-w-md rounded-lg border border-white/10 bg-slate-950/70 p-6 shadow-2xl shadow-black/20">
        <Link to="/" className="text-xs font-black uppercase tracking-[0.22em] text-cyan-200">
          S.A.G.A.
        </Link>
        <h1 className="mt-5 text-3xl font-black text-white">Sign in</h1>
        <p className="mt-2 text-sm leading-6 text-slate-400">Return to your story production workspace.</p>
      </section>
    </main>
  );
}
