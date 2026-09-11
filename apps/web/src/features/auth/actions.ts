"use server";

import { redirect } from "next/navigation";

import { safeNextPath } from "@/lib/auth/redirects";
import {
  resolveCurrentSagaAccount,
  SagaAccessError,
} from "@/server/account/account-access";
import { claimCurrentSagaInvitation } from "@/server/account/claim-invitation";
import { createSupabaseServerClient } from "@/server/supabase/server";

function readField(formData: FormData, name: string): string {
  const value = formData.get(name);
  return typeof value === "string" ? value : "";
}

function signInUrl(error: string, next: string): string {
  const params = new URLSearchParams({ error, next });
  return `/sign-in?${params.toString()}`;
}

function setPasswordUrl(error: string, next: string): string {
  const params = new URLSearchParams({ error, next });
  return `/set-password?${params.toString()}`;
}

function unavailableInvitationUrl(next: string): string {
  const params = new URLSearchParams({ retry: "invitation", next });
  return `/access/unavailable?${params.toString()}`;
}

function passwordSetupUrl(next: string): string {
  const params = new URLSearchParams({ next });
  return `/set-password?${params.toString()}`;
}

export async function signInAction(formData: FormData): Promise<void> {
  const next = safeNextPath(readField(formData, "next"));
  const email = readField(formData, "email").trim();
  const password = readField(formData, "password");

  if (!email || !password) {
    redirect(signInUrl("invalid_credentials", next));
  }

  let authError = false;
  try {
    const supabase = await createSupabaseServerClient();
    const result = await supabase.auth.signInWithPassword({ email, password });
    authError = Boolean(result.error);
  } catch {
    redirect(signInUrl("access_unavailable", next));
  }

  if (authError) {
    redirect(signInUrl("invalid_credentials", next));
  }

  const access = await resolveCurrentSagaAccount();
  switch (access.state) {
    case "active":
      redirect(next);
    case "suspended":
      redirect("/access/suspended");
    case "not_admitted":
      redirect("/access/not-admitted");
    case "unavailable":
      redirect("/access/unavailable");
    case "unauthenticated":
      redirect(signInUrl("invalid_credentials", next));
  }
}

export async function setPasswordAction(formData: FormData): Promise<void> {
  const next = safeNextPath(readField(formData, "next"));
  const password = readField(formData, "password");
  const confirmation = readField(formData, "password_confirmation");
  const access = await resolveCurrentSagaAccount();

  switch (access.state) {
    case "unauthenticated": {
      const returnTo = passwordSetupUrl(next);
      redirect(signInUrl("session_required", returnTo));
    }
    case "not_admitted":
      redirect("/access/not-admitted");
    case "unavailable":
      redirect("/access/unavailable");
    case "active":
    case "suspended":
      break;
  }

  if (password.length < 8 || password !== confirmation) {
    redirect(setPasswordUrl("password_invalid", next));
  }

  let updateFailed = false;
  try {
    const supabase = await createSupabaseServerClient();
    const result = await supabase.auth.updateUser({ password });
    updateFailed = Boolean(result.error);
  } catch {
    updateFailed = true;
  }

  if (updateFailed) {
    redirect(setPasswordUrl("password_update_failed", next));
  }

  if (access.state === "suspended") {
    redirect("/access/suspended?state=password_updated");
  }

  redirect(next);
}

export async function completeInvitationAction(formData: FormData): Promise<void> {
  const next = safeNextPath(readField(formData, "next"));
  let account;

  try {
    account = await claimCurrentSagaInvitation();
  } catch (error) {
    if (error instanceof SagaAccessError && error.code === "unauthenticated") {
      const returnTo = `/access/not-admitted?${new URLSearchParams({ next }).toString()}`;
      redirect(signInUrl("session_required", returnTo));
    }
    redirect(unavailableInvitationUrl(next));
  }

  if (!account) {
    const params = new URLSearchParams({ error: "no_pending_invitation", next });
    redirect(`/access/not-admitted?${params.toString()}`);
  }

  if (account.status === "suspended") {
    redirect("/access/suspended");
  }

  redirect(passwordSetupUrl(next));
}

export async function signOutAction(): Promise<void> {
  try {
    const supabase = await createSupabaseServerClient();
    await supabase.auth.signOut();
  } catch {
    // The destination remains public even if provider cleanup is unavailable.
  }

  redirect("/sign-in?state=signed_out");
}
