import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authApi } from "../../api/authApi";
import { AuthField } from "./AuthField";
import { AuthLayout } from "./AuthLayout";

const initialForm = {
  name: "",
  email: "",
  workspaceName: "",
  password: "",
  confirmPassword: "",
};

function validateSignUpForm(form) {
  const errors = {};
  if (form.name.trim().length < 2) errors.name = "Enter your name.";
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email.trim())) errors.email = "Enter a valid email.";
  if (form.password.length < 8) errors.password = "Use at least 8 characters.";
  if (form.confirmPassword !== form.password) errors.confirmPassword = "Passwords must match.";
  return errors;
}

export function SignUpPage() {
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
    const nextErrors = validateSignUpForm(form);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;

    setSubmitting(true);
    setServerError("");
    try {
      const payload = await authApi.signUp({
        name: form.name.trim(),
        email: form.email.trim(),
        password: form.password,
        workspace_name: form.workspaceName.trim(),
      });
      window.localStorage.setItem("saga-auth-user", JSON.stringify(payload.user));
      setForm(initialForm);
      navigate("/overview", { replace: true });
    } catch (exc) {
      setServerError(exc.message || "Could not create the account.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Create account"
      subtitle="Start a connected workspace for canon-aware production."
      footer={<p className="text-sm text-slate-500">Already have an account? <Link to="/signin" className="font-bold text-cyan-200 transition hover:text-cyan-100">Sign in</Link></p>}
    >
      <form className="space-y-3.5" noValidate onSubmit={handleSubmit}>
        <AuthField
          id="signup-name"
          label="Name"
          autoComplete="name"
          value={form.name}
          error={errors.name}
          onChange={(event) => updateField("name", event.target.value)}
        />
        <AuthField
          id="signup-email"
          label="Email"
          type="email"
          autoComplete="email"
          value={form.email}
          error={errors.email}
          onChange={(event) => updateField("email", event.target.value)}
        />
        <AuthField
          id="signup-workspace"
          label="Workspace name"
          autoComplete="organization"
          value={form.workspaceName}
          placeholder="Canon Studio"
          onChange={(event) => updateField("workspaceName", event.target.value)}
        />
        <div className="grid gap-3.5 sm:grid-cols-2">
          <AuthField
            id="signup-password"
            label="Password"
            type="password"
            autoComplete="new-password"
            value={form.password}
            error={errors.password}
            onChange={(event) => updateField("password", event.target.value)}
          />
          <AuthField
            id="signup-confirm-password"
            label="Confirm password"
            type="password"
            autoComplete="new-password"
            value={form.confirmPassword}
            error={errors.confirmPassword}
            onChange={(event) => updateField("confirmPassword", event.target.value)}
          />
        </div>
        {serverError ? <div role="alert" className="rounded-lg border border-rose-300/25 bg-rose-300/[0.08] px-4 py-3 text-sm font-bold text-rose-100">{serverError}</div> : null}
        <button
          type="submit"
          disabled={submitting}
          className="inline-flex min-h-11 w-full items-center justify-center rounded-lg border border-emerald-300/30 bg-emerald-300/[0.12] px-4 py-2 text-sm font-bold text-emerald-50 transition hover:border-emerald-200/55 hover:bg-emerald-300/[0.2] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "Creating account..." : "Create account"}
        </button>
      </form>
    </AuthLayout>
  );
}
