export function normalizeProviderEntries(providers) {
  if (Array.isArray(providers)) {
    return providers.map((payload) => [payload.provider_name || payload.name || "provider", payload]);
  }
  return Object.entries(providers || {});
}
