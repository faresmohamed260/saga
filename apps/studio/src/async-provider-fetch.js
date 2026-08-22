const nativeFetch = window.fetch.bind(window);
let activeGenerationJobId = null;

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

async function rememberGenerationJob(response) {
  try {
    const payload = await response.clone().json();
    if (payload?.job?.id) activeGenerationJobId = payload.job.id;
  } catch {}
}

function timeoutResponse(message) {
  return new Response(JSON.stringify({ error: message, detail: message }), {
    status: 504,
    headers: { 'Content-Type': 'application/json' },
  });
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
        headers: { Accept: 'image/*, application/json' },
        cache: 'no-store',
      });
      if (result.status === 202) continue;
      return result;
    }

    return timeoutResponse('Generation is still running after 30 minutes.');
  }

  return nativeFetch(input, init);
};
