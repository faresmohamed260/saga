export type SagaAccessRole = "member" | "admin";
export type SagaAccessStatus = "active" | "suspended";

export type SagaAdminAccountSummary = {
  userId: string;
  email: string | null;
  role: SagaAccessRole;
  status: SagaAccessStatus;
  createdAt: string;
  updatedAt: string;
};

export type SagaAdminAccountUpdate = {
  role?: SagaAccessRole;
  status?: SagaAccessStatus;
};

export type SagaInvitationSummary = {
  id: string;
  email: string;
  role: SagaAccessRole;
  expiresAt: string;
  createdAt: string;
};

export type SagaInvitationCreateResponse = {
  invitation: SagaInvitationSummary;
  deliveryStatus: "requested" | "not_confirmed";
  message: string;
};
