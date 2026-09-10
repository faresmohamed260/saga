export type SagaAccessRole = "member" | "admin";

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
