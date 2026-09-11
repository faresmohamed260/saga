export const SAGA_ACCOUNT_ROLES = ["member", "admin"] as const;
export const SAGA_ACCOUNT_STATUSES = ["active", "suspended"] as const;

export type SagaAccountRole = (typeof SAGA_ACCOUNT_ROLES)[number];
export type SagaAccountStatus = (typeof SAGA_ACCOUNT_STATUSES)[number];

export type SagaIdentity = {
  userId: string;
  email: string;
  emailNormalized: string;
};

export type SagaAccount = SagaIdentity & {
  role: SagaAccountRole;
  status: SagaAccountStatus;
  invitedBy: string | null;
  acceptedAt: string;
};

export function isSagaAccountRole(value: unknown): value is SagaAccountRole {
  return typeof value === "string" && SAGA_ACCOUNT_ROLES.includes(value as SagaAccountRole);
}

export function isSagaAccountStatus(value: unknown): value is SagaAccountStatus {
  return (
    typeof value === "string" &&
    SAGA_ACCOUNT_STATUSES.includes(value as SagaAccountStatus)
  );
}
