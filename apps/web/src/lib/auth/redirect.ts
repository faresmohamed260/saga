const SAFE_ORIGIN = "https://saga.invalid";

export function safeNextPath(value: unknown, fallback = "/home"): string {
  if (typeof value !== "string") {
    return fallback;
  }

  const candidate = value.trim();
  if (!candidate.startsWith("/") || candidate.startsWith("//") || candidate.includes("\\")) {
    return fallback;
  }

  try {
    const parsed = new URL(candidate, SAFE_ORIGIN);
    if (parsed.origin !== SAFE_ORIGIN || !parsed.pathname.startsWith("/")) {
      return fallback;
    }

    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return fallback;
  }
}
