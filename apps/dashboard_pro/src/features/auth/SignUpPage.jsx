import { Link } from "react-router-dom";
import { AuthLayout } from "./AuthLayout";

export function SignUpPage() {
  return (
    <AuthLayout
      title="Create account"
      subtitle="Start a connected workspace for canon-aware production."
      footer={<p className="text-sm text-slate-500">Already have an account? <Link to="/signin" className="font-bold text-cyan-200 hover:text-cyan-100">Sign in</Link></p>}
    >
      <div className="rounded-lg border border-white/10 bg-slate-950/60 p-5 text-sm text-slate-400">
        Account creation form loading.
      </div>
    </AuthLayout>
  );
}
