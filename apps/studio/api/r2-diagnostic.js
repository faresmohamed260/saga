import { DeleteObjectCommand, GetObjectCommand, ListObjectsV2Command, PutObjectCommand, S3Client } from '@aws-sdk/client-s3';
import { randomUUID } from 'node:crypto';

const bucket = String(process.env.R2_BUCKET_NAME || 'saga-studio-media').trim();
function cfg() {
  const accountId = String(process.env.R2_ACCOUNT_ID || '').trim();
  const accessKeyId = String(process.env.R2_ACCESS_KEY_ID || '').trim();
  const secretAccessKey = String(process.env.R2_SECRET_ACCESS_KEY || '').trim();
  return { accountId, accessKeyId, secretAccessKey, endpoint: accountId ? `https://${accountId}.r2.cloudflarestorage.com` : '' };
}
function safeError(e) { return { name: e?.name || 'Error', code: e?.Code || e?.code || null, message: e?.message || 'Unknown R2 error', httpStatusCode: e?.$metadata?.httpStatusCode || null, requestId: e?.$metadata?.requestId || null }; }
async function bodyToString(body) { if (!body) return ''; if (typeof body.transformToString === 'function') return body.transformToString(); const chunks=[]; for await (const chunk of body) chunks.push(Buffer.from(chunk)); return Buffer.concat(chunks).toString('utf8'); }

export default async function handler(req, res) {
  if (req.method !== 'GET' && req.method !== 'POST') { res.setHeader('Allow','GET, POST'); return res.status(405).json({error:'Method not allowed'}); }
  const c=cfg();
  if (!c.accountId || !c.accessKeyId || !c.secretAccessKey || !bucket) return res.status(503).json({ok:false,stage:'config',configured:{accountId:!!c.accountId,accessKeyId:!!c.accessKeyId,secretAccessKey:!!c.secretAccessKey,bucket:!!bucket}});
  const client=new S3Client({region:'auto',endpoint:c.endpoint,credentials:{accessKeyId:c.accessKeyId,secretAccessKey:c.secretAccessKey}});
  const key=`diagnostics/r2-${Date.now()}-${randomUUID()}.txt`; const payload=`saga-r2-diagnostic:${key}`;
  const result={ok:false,endpoint:c.endpoint,bucket,accessKeySuffix:c.accessKeyId.slice(-4),stages:{}};
  try { const x=await client.send(new ListObjectsV2Command({Bucket:bucket,MaxKeys:1})); result.stages.list={ok:true,keyCount:x.KeyCount??null}; } catch(e){ result.stages.list={ok:false,error:safeError(e)}; return res.status(e?.$metadata?.httpStatusCode||500).json(result); }
  try { await client.send(new PutObjectCommand({Bucket:bucket,Key:key,Body:payload,ContentType:'text/plain; charset=utf-8'})); result.stages.put={ok:true}; } catch(e){ result.stages.put={ok:false,error:safeError(e)}; return res.status(e?.$metadata?.httpStatusCode||500).json(result); }
  try { const x=await client.send(new GetObjectCommand({Bucket:bucket,Key:key})); const received=await bodyToString(x.Body); if(received!==payload) throw new Error('Read-back payload did not match'); result.stages.get={ok:true}; } catch(e){ result.stages.get={ok:false,error:safeError(e)}; try{await client.send(new DeleteObjectCommand({Bucket:bucket,Key:key}));}catch{} return res.status(e?.$metadata?.httpStatusCode||500).json(result); }
  try { await client.send(new DeleteObjectCommand({Bucket:bucket,Key:key})); result.stages.delete={ok:true}; } catch(e){ result.stages.delete={ok:false,error:safeError(e)}; return res.status(e?.$metadata?.httpStatusCode||500).json(result); }
  result.ok=true; return res.status(200).json(result);
}
