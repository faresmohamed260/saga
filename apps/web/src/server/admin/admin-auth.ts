import {
  requireCurrentSagaAccount,
  SagaAccessError,
} from "@/server/account/account-access";
import type { SagaAccount } from "@/server/account/types";

export async function requireCurrentSagaAdmin(): Promise<SagaAccount> {
  const account = await requireCurrentSagaAccount();
  if (account.role !== "admin") {
    throw new SagaAccessError("admin_required", 403);
  }
  return account;
}
