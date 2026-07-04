import { Link } from "react-router-dom";
import { AuthLayout } from "./AuthLayout";

export function SignInPage() {
  return (
    <AuthLayout
      title="Sign in"
      subtitle="Return to your story production workspace."
      footer={<p className="text-sm text-slate-500">New to S.A.G.A.? <Link to="/signup" className="font-bold text-cyan-200 hover:text-cyan-100">Create an account</Link></p>}
    >
      <div className="rounded-lg border border-white/10 bg-slate-950/60 p-5 text-sm text-slate-400">
        Account access form loading.
      </div>
    </AuthLayout>
  );
}
