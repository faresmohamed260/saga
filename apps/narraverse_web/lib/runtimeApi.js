async function request(path, options = {}) {
  const headers =
    options.body instanceof FormData
      ? {}
      : { "Content-Type": "application/json" };
  const response = await fetch(path, {
    ...options,
    headers: { ...headers, ...(options.headers || {}) },
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json().catch(() => ({}))
    : await response.text();
  if (!response.ok) {
    const detail = typeof payload === "object" ? payload?.detail : payload;
    throw new Error(detail || response.statusText || `Request failed: ${path}`);
  }
  return payload;
}

function toQuery(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  });
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const runtimeApi = {
  assetSeriesSummary: () => request("/api/runtime/assets/series-summary"),
  assets: (params = {}) =>
    request(`/api/runtime/assets/entities${toQuery(params)}`),
  asset: (entityId) =>
    request(`/api/runtime/assets/entities/${encodeURIComponent(entityId)}`),
  previewRenderEntity: (entityId, payload) =>
    request(
      `/api/runtime/assets/entities/${encodeURIComponent(
        entityId,
      )}/preview-render`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  saveRenderedEntity: (entityId, payload) =>
    request(
      `/api/runtime/assets/entities/${encodeURIComponent(entityId)}/save-render`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  renderEntity: (entityId, payload = {}) =>
    request(`/api/runtime/assets/entities/${encodeURIComponent(entityId)}/render`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

export function runtimeFileUrl(path) {
  if (!path) {
    return "";
  }
  return `/api/runtime/file${toQuery({ path })}`;
}
