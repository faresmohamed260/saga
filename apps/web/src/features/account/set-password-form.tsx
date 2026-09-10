"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { createSupabaseBrowserClient } from "@/lib/supabase/browser";

const MIN_PASSWORD_LENGTH = 10;

export function SetPasswordForm() {
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);

    if (password.length < MIN_PASSWORD_LENGTH) {
      setMessage(`Use at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    if (password !== confirmation) {
      setMessage("Passwords do not match.");
      return;
    }

    const supabase = createSupabaseBrowserClient();
    if (!supabase) {
      setMessage("Account setup is not configured yet.");
      return;
    }

    setBusy(true);
    const { error } = await supabase.auth.updateUser({ password });
    setBusy(false);

    if (error) {
      setMessage("Your password could not be saved. Request a fresh invitation link if this session has expired.");
      return;
    }

    window.location.assign("/app");
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-5">
      <Field>
        <FieldLabel htmlFor="new-password">Create password</FieldLabel>
        <Input
          id="new-password"
          name="new-password"
          type="password"
          autoComplete="new-password"
          minLength={MIN_PASSWORD_LENGTH}
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <FieldDescription>Use at least {MIN_PASSWORD_LENGTH} characters.</FieldDescription>
      </Field>
      <Field>
        <FieldLabel htmlFor="confirm-password">Confirm password</FieldLabel>
        <Input
          id="confirm-password"
          name="confirm-password"
          type="password"
          autoComplete="new-password"
          minLength={MIN_PASSWORD_LENGTH}
          required
          value={confirmation}
          onChange={(event) => setConfirmation(event.target.value)}
        />
      </Field>
      {message ? <p role="status" className="text-sm leading-6 text-amber-100">{message}</p> : null}
      <Button type="submit" size="lg" disabled={busy}>
        {busy ? "Saving…" : "Finish account setup"}
      </Button>
    </form>
  );
}
