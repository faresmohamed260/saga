const SUPABASE_URL = (process.env.SUPABASE_URL || 'https://rashyleshocuvpgcooxy.supabase.co').replace(/\/$/, '');
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_PUBLISHABLE_KEY || 'sb_publishable_Erz_UUs49DgHHDkFoXfztA_m6CbHTqw';

export async function supabaseRequest(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set('apikey', SUPABASE_KEY);
  headers.set('Authorization', `Bearer ${SUPABASE_KEY}`);
  if (options.body != null && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');

  const response = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const text = await response.text();
    const error = new Error(`Supabase request failed (${response.status})${text ? `: ${text.slice(0, 500)}` : ''}`);
    error.statusCode = response.status;
    throw error;
  }

  if (response.status === 204) return null;
  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

export async function insertGeneration(record) {
  const rows = await supabaseRequest('studio_generations?select=*', {
    method: 'POST',
    headers: { Prefer: 'return=representation' },
    body: JSON.stringify(record),
  });
  return Array.isArray(rows) ? rows[0] : rows;
}
