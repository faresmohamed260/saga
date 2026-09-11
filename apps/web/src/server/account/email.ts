const MAX_EMAIL_LENGTH = 320;

export function normalizeSagaEmail(value: string): string {
  return value.trim().toLowerCase();
}

export function validateSagaEmail(value: string): string {
  const normalized = normalizeSagaEmail(value);

  if (!normalized || normalized.length > MAX_EMAIL_LENGTH || /\s/.test(normalized)) {
    throw new Error("invalid_email");
  }

  const at = normalized.indexOf("@");
  if (at <= 0 || at !== normalized.lastIndexOf("@") || at === normalized.length - 1) {
    throw new Error("invalid_email");
  }

  return normalized;
}
