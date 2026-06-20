const DASHBOARD_RUNTIME_ORIGIN =
  process.env.NARRAVERSE_DASHBOARD_RUNTIME_ORIGIN || "http://127.0.0.1:8675";

function buildTargetUrl(slug, requestUrl) {
  const path = Array.isArray(slug) ? slug.join("/") : "";
  const incoming = new URL(requestUrl);
  const target = new URL(`/runtime/${path}`, DASHBOARD_RUNTIME_ORIGIN);
  target.search = incoming.search;
  return target;
}

async function proxy(request, context) {
  const params = await context.params;
  const targetUrl = buildTargetUrl(params?.slug || [], request.url);
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("content-length");
  headers.delete("expect");

  const init = {
    method: request.method,
    headers,
    redirect: "manual",
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }

  const upstream = await fetch(targetUrl, init);
  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("transfer-encoding");
  responseHeaders.delete("connection");

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export { proxy as GET, proxy as POST, proxy as PATCH, proxy as DELETE, proxy as PUT, proxy as HEAD };
