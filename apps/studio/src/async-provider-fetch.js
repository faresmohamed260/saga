const nativeFetch = window.fetch.bind(window);
let activeGenerationJobId = null;
const completedJobs = new Map();

function requestUrl(input) {
  if (typeof input === 'string') return input;
  if (input instanceof URL) return input.toString();
  return input?.url || '';
}

function requestMethod(input, init) {
  return String(init?.method || input?.method || 'GET').toUpperCase();
}

function sameOriginPath(value) {
  try {
    const url = new URL(value, window.location.origin);
    return url.origin === window.location.origin ? url.pathname : '';
  } catch {
    return '';
  }
}

function headerValue(headers, name) {
  if (!headers) return '';
  if (headers instanceof Headers) return headers.get(name) || '';
  const key = Object.keys(headers).find((entry) => entry.toLowerCase() === name.toLowerCase());
  return key ? String(headers[key] || '') : '';
}

async function rememberGenerationJob(response) {
  try {
    const payload = await response.clone().json();
    if (payload?.job?.id) activeGenerationJobId = payload.job.id;
  } catch {}
}

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}

function timeoutResponse(message) {
  return jsonResponse({ error: message, detail: message }, 504);
}

window.fetch = async function sagaFetch(input, init = undefined) {
  const url = requestUrl(input);
  const method = requestMethod(input, init);
  const path = sameOriginPath(url);

  if (path === '/api/jobs' && method === 'POST') {
    const response = await nativeFetch(input, init);
    if (response.ok) await rememberGenerationJob(response);
    return response;
  }

  if (path === '/api/generate/edit' && method === 'POST' && init?.body instanceof FormData) {
    const form = init.body;
    if (!form.has('job_id') && activeGenerationJobId) form.append('job_id', activeGenerationJobId);

    const submit = await nativeFetch(input, { ...init, body: form });
    if (submit.status !== 202) return submit;

    let payload = null;
    try { payload = await submit.clone().json(); } catch {}
    const jobId = payload?.jobId || activeGenerationJobId;
    if (!jobId) return timeoutResponse('Generation submit did not return a job id.');

    const deadline = Date.now() + 30 * 60 * 1000;
    while (Date.now() < deadline) {
      await new Promise((resolve) => window.setTimeout(resolve, 2000));
      const result = await nativeFetch(`/api/generate/result?jobId=${encodeURIComponent(jobId)}`, {
        method: 'GET',
        headers: { Accept: 'application/json' },
        cache: 'no-store',
      });
      if (result.status === 202) continue;
      if (!result.ok) return result;

      let completed = null;
      try { completed = await result.clone().json(); } catch {}
      if (!completed?.persisted || !completed?.mediaUrl) {
        return jsonResponse({ error: 'Generation completed without persisted media.' }, 502);
      }
      completedJobs.set(jobId, completed);
      const media = await nativeFetch(completed.mediaUrl, { cache: 'no-store' });
      if (!media.ok) return media;
      return media;
    }

    return timeoutResponse('Generation is still running after 30 minutes.');
  }

  if (path === '/api/media' && method === 'POST') {
    const jobId = headerValue(init?.headers, 'X-Saga-Job-Id');
    const completed = completedJobs.get(jobId);
    if (completed?.persisted && completed?.mediaUrl) {
      completedJobs.delete(jobId);
      return jsonResponse({
        key: null,
        url: completed.mediaUrl,
        thumbnailKey: null,
        thumbnailUrl: completed.thumbnailUrl || null,
        persisted: true,
        generationId: completed.generationId || jobId,
        historyPersisted: true,
        jobId,
        orchestrated: true,
      }, 201);
    }
  }

  return nativeFetch(input, init);
};
