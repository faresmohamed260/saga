export interface Env {
  MEDIA: R2Bucket;
}

const json = (data: unknown, init: ResponseInit = {}) =>
  Response.json(data, {
    ...init,
    headers: {
      "cache-control": "no-store",
      ...init.headers,
    },
  });

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/health") {
      return json({ service: "saga-studio-media", status: "ok" });
    }

    if (request.method === "GET" && url.pathname === "/storage") {
      const listing = await env.MEDIA.list({ limit: 1 });
      return json({
        bucket: "saga-studio-media",
        status: "ok",
        reachable: true,
        hasObjects: listing.objects.length > 0,
      });
    }

    return json(
      {
        error: "not_found",
        message: "SAGA Studio media service",
      },
      { status: 404 },
    );
  },
};
