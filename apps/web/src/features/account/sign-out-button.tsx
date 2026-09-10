"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { createSupabaseBrowserClient } from "@/lib/supabase/browser";

export function SignOutButton({ compact = false }: { compact?: boolean }) {
  const [busy, setBusy] = useState(false);

  async function signOut() {
    const supabase = createSupabaseBrowserClient();
    if (!supabase) return;
    setBusy(true);
    await supabase.auth.signOut();
    window.location.assign("/");
  }

  return (
    <Button type="button" variant="ghost" size={compact ? "sm" : "md"} disabled={busy} onClick={signOut}>
      {busy ? "Signing out…" : "Sign out"}
    </Button>
  );
}
