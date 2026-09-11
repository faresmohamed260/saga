const INTERNAL_ORIGIN = "https://saga.invalid";

export const DEFAULT_POST_AUTH_PATH = "/home";

/**
 * Accept only same-origin relative application paths from untrusted query/form
 * state. Auth confirmation itself is never a valid post-auth destination.
 */
export function safeNextPath(
  value: string | null | undefined,
  fallback = DEFAULT_POST_AUTH_PATH,
): string {
  if (!value) {
    return fallback;
  }

  const candidateValue = value.trim();
  if (
    !candidateValue.startsWith("/") ||
    candidateValue.startsWith("//") ||
    candidateValue.includes("\\") ||
    /[\u0000-\u001f\u007f]/.test(candidateValue)
  ) {
    return fallback;
  }

  try {
    const base = new URL(INTERNAL_ORIGIN);
    const candidate = new URL(candidateValue, base);

    if (candidate.origin !== base.origin) {
      return fallback;
    }

    if (
      candidate.pathname === "/auth/confirm" ||
      candidate.pathname.startsWith("/auth/confirm/")
    ) {
      return fallback;
    }

    return `${candidate.pathname}${candidate.search}${candidate.hash}`;
  } catch {
    return fallback;
  }
}
