import {
  DeleteObjectCommand,
  GetObjectCommand,
  HeadObjectCommand,
  PutObjectCommand,
  S3Client,
} from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

import type {
  CreateReadUrlInput,
  CreateUploadUrlInput,
  ObjectMetadata,
  ObjectStorage,
  SignedObjectUrl,
} from "./types";

type B2RuntimeConfig = {
  bucket: string;
  endpoint: string;
  region: string;
  applicationKeyId: string;
  applicationKey: string;
};

function requireB2RuntimeConfig(): B2RuntimeConfig {
  const bucket = process.env.SAGA_B2_BUCKET?.trim();
  const endpoint = process.env.SAGA_B2_ENDPOINT?.trim();
  const region = process.env.SAGA_B2_REGION?.trim();
  const applicationKeyId = process.env.SAGA_B2_APPLICATION_KEY_ID?.trim();
  const applicationKey = process.env.SAGA_B2_APPLICATION_KEY?.trim();

  if (!bucket || !endpoint || !region || !applicationKeyId || !applicationKey) {
    throw new Error("Backblaze B2 runtime storage configuration is incomplete.");
  }

  const parsedEndpoint = new URL(endpoint);
  if (parsedEndpoint.protocol !== "https:") {
    throw new Error("Backblaze B2 runtime endpoint must use HTTPS.");
  }

  return {
    bucket,
    endpoint: parsedEndpoint.toString().replace(/\/$/, ""),
    region,
    applicationKeyId,
    applicationKey,
  };
}

function safeDownloadFilename(value: string) {
  return value.replace(/["\r\n]/g, "_");
}

class BackblazeB2Storage implements ObjectStorage {
  readonly #config: B2RuntimeConfig;
  readonly #client: S3Client;

  constructor(config: B2RuntimeConfig = requireB2RuntimeConfig()) {
    this.#config = config;
    this.#client = new S3Client({
      region: config.region,
      endpoint: config.endpoint,
      credentials: {
        accessKeyId: config.applicationKeyId,
        secretAccessKey: config.applicationKey,
      },
    });
  }

  async createUploadUrl(input: CreateUploadUrlInput): Promise<SignedObjectUrl> {
    const expiresInSeconds = input.expiresInSeconds ?? 300;
    const url = await getSignedUrl(
      this.#client,
      new PutObjectCommand({
        Bucket: this.#config.bucket,
        Key: input.key,
        ContentType: input.contentType,
        Metadata: input.metadata,
      }),
      { expiresIn: expiresInSeconds },
    );

    return { url, expiresInSeconds };
  }

  async createReadUrl(input: CreateReadUrlInput): Promise<SignedObjectUrl> {
    const expiresInSeconds = input.expiresInSeconds ?? 300;
    const url = await getSignedUrl(
      this.#client,
      new GetObjectCommand({
        Bucket: this.#config.bucket,
        Key: input.key,
        ResponseContentDisposition: input.downloadFilename
          ? `attachment; filename="${safeDownloadFilename(input.downloadFilename)}"`
          : undefined,
      }),
      { expiresIn: expiresInSeconds },
    );

    return { url, expiresInSeconds };
  }

  async head(key: string): Promise<ObjectMetadata | null> {
    try {
      const response = await this.#client.send(
        new HeadObjectCommand({ Bucket: this.#config.bucket, Key: key }),
      );
      return {
        key,
        sizeBytes: Number(response.ContentLength ?? 0),
        contentType: response.ContentType ?? null,
        etag: response.ETag?.replace(/^"|"$/g, "") ?? null,
        metadata: response.Metadata ?? {},
      };
    } catch (error) {
      const status = (error as { $metadata?: { httpStatusCode?: number } }).$metadata?.httpStatusCode;
      if (status === 404) return null;
      throw error;
    }
  }

  async delete(key: string): Promise<void> {
    await this.#client.send(
      new DeleteObjectCommand({ Bucket: this.#config.bucket, Key: key }),
    );
  }
}

export function createBackblazeB2Storage(): ObjectStorage {
  return new BackblazeB2Storage();
}
