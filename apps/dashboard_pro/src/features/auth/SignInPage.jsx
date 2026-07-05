import { useState } from "react";
import { Link } from "react-router-dom";
import { authApi } from "../../api/authApi";
import { AuthField } from "./AuthField";
import { AuthLayout } from "./AuthLayout";

const initialForm = {
  email: "",
  password: "",
};

function validateSignInForm(form) {
  const errors = {};
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email.trim())) errors.email = "Enter a valid email.";
  if (!form.password) errors.password = "Enter your password.";
  return errors;
}

export function SignInPage() {
  const [form, setForm] = useState(initialForm);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState("");
  const [signedInUser, setSignedInUser] = useState(null);

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: "" }));
    setServerError("");
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const nextErrors = validateSignInForm(form);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;

    setSubmitting(true);
    setServerError("");
    try {
      const payload = await authApi.signIn({
        email: form.email.trim(),
        password: form.password,
      });
      setSignedInUser(payload.user);
      setForm(initialForm);
    } catch (exc) {
      setServerError(exc.message || "Could not sign in.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Sign in"
      subtitle="Return to your story production workspace."
      footer={<p className="text-sm text-slate-500">New to S.A.G.A.? <Link to="/signup" className="font-bold text-cyan-200 hover:text-cyan-100">Create an account</Link></p>}
    >
      {signedInUser ? (
        <div role="status" className="rounded-2xl border border-cyan-300/28 bg-cyan-300/[0.08] p-5">
          <p className="text-lg font-black text-white">Welcome back</p>
          <p className="mt-2 text-sm leading-6 text-cyan-100/80">
            {signedInUser.name} can continue in {signedInUser.workspace_name || "the S.A.G.A. workspace"}.
          </p>
          <Link to="/overview" className="mt-5 inline-flex min-h-11 items-center justify-center rounded-xl border border-cyan-200/55 bg-cyan-300/15 px-4 py-2 text-sm font-bold text-cyan-50 transition hover:bg-cyan-300/25">
            Open studio
          </Link>
        </div>
      ) : (
        <form className="space-y-4" noValidate onSubmit={handleSubmit}>
          <AuthField
            id="signin-email"
            label="Email"
            type="email"
            autoComplete="email"
            value={form.email}
            error={errors.email}
            onChange={(event) => updateField("email", event.target.value)}
          />
          <AuthField
            id="signin-password"
            label="Password"
            type="password"
            autoComplete="current-password"
            value={form.password}
            error={errors.password}
            onChange={(event) => updateField("password", event.target.value)}
          />
          {serverError ? <div role="alert" className="rounded-2xl border border-rose-300/25 bg-rose-300/[0.08] px-4 py-3 text-sm font-bold text-rose-100">{serverError}</div> : null}
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex min-h-12 w-full items-center justify-center rounded-xl border border-cyan-300/30 bg-cyan-300/[0.1] px-4 py-2 text-sm font-bold text-cyan-50 transition hover:border-cyan-200/55 hover:bg-cyan-300/[0.18] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "Signing in..." : "Sign in"}
          </button>
        </form>
      )}
    </AuthLayout>
  );
}
