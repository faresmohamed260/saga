import { GetObjectCommand, PutObjectCommand, S3Client } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

export const r2Bucket = String(process.env.R2_BUCKET_NAME || 'saga-studio-media').trim();

export function getR2Client() {
  const accountId = String(process.env.R2_ACCOUNT_ID || '').trim();
  const accessKeyId = String(process.env.R2_ACCESS_KEY_ID || '').trim();
  const secretAccessKey = String(process.env.R2_SECRET_ACCESS_KEY || '').trim();
  if (!accountId || !accessKeyId || !secretAccessKey) return null;
  return new S3Client({
    region: 'auto',
    endpoint: `https://${accountId}.r2.cloudflarestorage.com`,
    credentials: { accessKeyId, secretAccessKey },
    requestChecksumCalculation: 'WHEN_REQUIRED',
    responseChecksumValidation: 'WHEN_REQUIRED',
  });
}

export function isSourceKey(key) {
  return /^sources\/\d{4}\/\d{2}\/[0-9a-f-]{36}\.(png|jpg|jpeg|webp)$/i.test(String(key || ''));
}

export async function createSourceUploadUrl({ key, contentType, expiresIn = 300 }) {
  const client = getR2Client();
  if (!client) {
    const error = new Error('R2 storage is not configured');
    error.statusCode = 503;
    throw error;
  }
  const command = new PutObjectCommand({
    Bucket: r2Bucket,
    Key: key,
    ContentType: contentType,
  });
  return getSignedUrl(client, command, { expiresIn });
}

export async function readSourceObject(key, maxBytes) {
  if (!isSourceKey(key)) {
    const error = new Error('Invalid source key');
    error.statusCode = 400;
    throw error;
  }
  const client = getR2Client();
  if (!client) {
    const error = new Error('R2 storage is not configured');
    error.statusCode = 503;
    throw error;
  }
  const object = await client.send(new GetObjectCommand({ Bucket: r2Bucket, Key: key }));
  const length = Number(object.ContentLength || 0);
  if (maxBytes && length > maxBytes) {
    const error = new Error('Source object exceeds workflow limit');
    error.statusCode = 413;
    throw error;
  }
  const chunks = [];
  let total = 0;
  for await (const chunk of object.Body) {
    total += chunk.length;
    if (maxBytes && total > maxBytes) {
      const error = new Error('Source object exceeds workflow limit');
      error.statusCode = 413;
      throw error;
    }
    chunks.push(Buffer.from(chunk));
  }
  return {
    bytes: Buffer.concat(chunks),
    contentType: String(object.ContentType || 'application/octet-stream'),
  };
}
