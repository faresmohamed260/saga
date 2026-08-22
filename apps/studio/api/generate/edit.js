import { Readable } from 'node:stream';
import { executeWorkflow } from '../_providers.js';
import { getWorkflow } from '../_workflows.js';

export const config = { maxDuration: 300 };

const WORKFLOW_ID = 'flux2-klein-image-edit';

async function parseMultipart(req) {
  const headers = new Headers();
  for (const [name, value] of Object.entries(req.headers || {})) {
    if (Array.isArray(value)) value.forEach((entry) => headers.append(name, entry));
    else if (value != null) headers.set(name, String(value));
  }

  const request = new Request('http://saga.local/api/generate/edit', {
    method: 'POST',
    headers,
    body: Readable.toWeb(req),
    duplex: 'half',
  });
  return request.formData();
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const workflow = getWorkflow(WORKFLOW_ID);
    if (!workflow) return res.status(503).json({ error: 'Image edit workflow is not registered' });

    const form = await parseMultipart(req);
    const imageFile = form.get('image_file');
    const prompt = String(form.get('prompt') || '').trim();
    const negativePrompt = String(form.get('negative_prompt') || '');
    const seed = Number.parseInt(String(form.get('seed') || workflow.defaults.seed), 10);
    const steps = Number(form.get('steps') || workflow.defaults.steps);
    const cfg = Number(form.get('cfg') || workflow.defaults.cfg);
    const megapixels = Number(form.get('megapixels') || workflow.defaults.megapixels);

    if (!imageFile || typeof imageFile.arrayBuffer !== 'function') {
      return res.status(400).json({ error: 'image_file is required' });
    }
    if (!String(imageFile.type || '').startsWith('image/')) {
      return res.status(415).json({ error: 'image_file must be an image' });
    }

    const sourceBytes = Buffer.from(await imageFile.arrayBuffer());
    const result = await executeWorkflow(workflow, {
      sourceBytes,
      sourceContentType: imageFile.type || 'image/png',
      sourceFilename: imageFile.name || 'input.png',
      prompt,
      negativePrompt,
      seed,
      steps,
      cfg,
      megapixels,
    });

    res.setHeader('Content-Type', result.contentType || workflow.outputMimeType);
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('X-Saga-Workflow', workflow.id);
    res.setHeader('X-Saga-Provider', workflow.provider);
    return res.status(200).send(result.bytes);
  } catch (error) {
    console.error('Server-side image edit adapter failed', error);
    return res.status(error?.statusCode || 500).json({ error: error?.message || 'Image edit failed' });
  }
}
