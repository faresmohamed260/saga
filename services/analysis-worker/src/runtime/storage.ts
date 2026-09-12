import { GetObjectCommand, S3Client } from "@aws-sdk/client-s3";

import type { WorkerRuntimeConfig } from "./config.js";

export type SourceObject = {
  bytes: Uint8Array;
  contentType: string | null;
};

export interface SourceObjectReader {
  read(key: string, expectedBytes: number): Promise<SourceObject>;
}

export function createB2SourceObjectReader(config: WorkerRuntimeConfig): SourceObjectReader {
  const client = new S3Client({
    region: config.b2Region,
    endpoint: config.b2Endpoint,
    credentials: {
      accessKeyId: config.b2ApplicationKeyId,
      secretAccessKey: config.b2ApplicationKey,
    },
  });

  return {
    async read(key: string, expectedBytes: number) {
      const response = await client.send(
        new GetObjectCommand({
          Bucket: config.b2Bucket,
          Key: key,
        }),
      );

      const observedLength = Number(response.ContentLength ?? -1);
      if (observedLength !== expectedBytes) {
        throw new Error(
          `source_object_size_mismatch: expected ${expectedBytes}, observed ${observedLength}`,
        );
      }
      if (!response.Body) throw new Error("source_object_body_missing");

      const bytes = await response.Body.transformToByteArray();
      if (bytes.byteLength !== expectedBytes) {
        throw new Error(
          `source_object_size_mismatch: expected ${expectedBytes}, read ${bytes.byteLength}`,
        );
      }
      return {
        bytes,
        contentType: response.ContentType ?? null,
      };
    },
  };
}
