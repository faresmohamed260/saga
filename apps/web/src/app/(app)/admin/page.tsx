import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { AdminWorkspace } from "@/features/admin/admin-workspace";
import { SagaAccessError } from "@/server/account/account-access";
import { requireCurrentSagaAdmin } from "@/server/admin/admin-auth";
import {
  listSagaAdminAccounts,
  listSagaAdminInvitations,
  SagaAdminOperationError,
} from "@/server/admin/admin-operations";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Admin",
};

export default async function AdminPage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ notice?: string }> }>) {
  let currentAdmin;
  try {
    currentAdmin = await requireCurrentSagaAdmin();
  } catch (error) {
    if (error instanceof SagaAccessError && error.code === "admin_required") {
      redirect("/home");
    }
    throw error;
  }

  let invitations;
  let accounts;
  try {
    [invitations, accounts] = await Promise.all([
      listSagaAdminInvitations(),
      listSagaAdminAccounts(),
    ]);
  } catch (error) {
    if (error instanceof SagaAdminOperationError && error.code === "unavailable") {
      redirect("/access/unavailable");
    }
    throw error;
  }

  const { notice } = await searchParams;
  return (
    <AdminWorkspace
      currentUserId={currentAdmin.userId}
      invitations={invitations}
      accounts={accounts}
      notice={notice}
    />
  );
}
