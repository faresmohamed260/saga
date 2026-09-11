"use server";

import { redirect } from "next/navigation";

import { safeNextPath } from "@/lib/auth/redirect";
import { getFreshSagaIdentity } from "@/server/account/identity";
import { resolveCurrentSagaAccount } from "@/server/account/account-access";
import { createSupabaseServerClient } from "@/server/supabase/server";

function field(formData: FormData, name: string): string {
  const value = formData.get(name);
  return typeof value === "string" ? value.trim() : "";
}

function redirectForAccessState(
  state: Awaited<ReturnType<typeof resolveCurrentSagaAccount>>["state"],
  next: string,
): never {
  switch (state) {
    case "active":
      redirect(next);
    case "not_admitted":
      redirect("/access/not-admitted");
    case "suspended":
      redirect("/access/suspended");
    case "unavailable":
      redirect("/access/unavailable");
    case "unauthenticated":
      redirect(`/sign-in?error=session&next=${encodeURIComponent(next)}`);
  }
}

export async function signInAction(formData: FormData): Promise<never> {
  const email = field(formData, "email");
  const password = field(formData, "password");
  const next = safeNextPath(field(formData, "next"));

  if (!email || !password) {
    redirect(`/sign-in?error=invalid&next=${encodeURIComponent(next)}`);
  }

  try {
    const supabase = await createSupabaseServerClient();
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      redirect(`/sign-in?error=invalid&next=${encodeURIComponent(next)}`);
    }
  } catch {
    redirect(`/sign-in?error=unavailable&next=${encodeURIComponent(next)}`);
  }

  const resolution = await resolveCurrentSagaAccount();
  redirectForAccessState(resolution.state, next);
}

export async function setPasswordAction(formData: FormData): Promise<never> {
  const password = field(formData, "password");
  const confirmation = field(formData, "passwordConfirmation");
  const next = safeNextPath(field(formData, "next"));

  if (password.length < 10 || password !== confirmation) {
    redirect(`/set-password?error=invalid&next=${encodeURIComponent(next)}`);
  }

  let identity;
  try {
    identity = await getFreshSagaIdentity();
  } catch {
    redirect(`/set-password?error=unavailable&next=${encodeURIComponent(next)}`);
  }

  if (!identity) {
    redirect(`/sign-in?error=session&next=${encodeURIComponent("/set-password")}`);
  }

  try {
    const supabase = await createSupabaseServerClient();
    const { error } = await supabase.auth.updateUser({ password });
    if (error) {
      redirect(`/set-password?error=update&next=${encodeURIComponent(next)}`);
    }
  } catch {
    redirect(`/set-password?error=unavailable&next=${encodeURIComponent(next)}`);
  }

  const resolution = await resolveCurrentSagaAccount();
  redirectForAccessState(resolution.state, next);
}

export async function signOutAction(): Promise<never> {
  try {
    const supabase = await createSupabaseServerClient();
    await supabase.auth.signOut();
  } finally {
    redirect("/sign-in?signedOut=1");
  }
}
