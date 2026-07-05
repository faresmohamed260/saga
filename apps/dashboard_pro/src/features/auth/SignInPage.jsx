import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
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
  const navigate = useNavigate();
  const [form, setForm] = useState(initialForm);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState("");

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
      window.localStorage.setItem("saga-auth-user", JSON.stringify(payload.user));
      setForm(initialForm);
      navigate("/overview", { replace: true });
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
      footer={<p className="text-sm text-slate-500">New to S.A.G.A.? <Link to="/signup" className="font-bold text-cyan-200 transition hover:text-cyan-100">Create an account</Link></p>}
    >
      <form className="space-y-3.5" noValidate onSubmit={handleSubmit}>
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
        {serverError ? <div role="alert" className="rounded-lg border border-rose-300/25 bg-rose-300/[0.08] px-4 py-3 text-sm font-bold text-rose-100">{serverError}</div> : null}
        <button
          type="submit"
          disabled={submitting}
          className="inline-flex min-h-11 w-full items-center justify-center rounded-lg border border-cyan-300/30 bg-cyan-300/[0.1] px-4 py-2 text-sm font-bold text-cyan-50 transition hover:border-cyan-200/55 hover:bg-cyan-300/[0.18] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </AuthLayout>
  );
}
