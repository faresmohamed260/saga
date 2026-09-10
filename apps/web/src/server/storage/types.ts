export type SignedObjectUrl = {
  url: string;
  expiresInSeconds: number;
};

export type ObjectMetadata = {
  key: string;
  sizeBytes: number;
  contentType: string | null;
  etag: string | null;
};

export type CreateUploadUrlInput = {
  key: string;
  contentType: string;
  expiresInSeconds?: number;
};

export type CreateReadUrlInput = {
  key: string;
  expiresInSeconds?: number;
  downloadFilename?: string;
};

export interface ObjectStorage {
  createUploadUrl(input: CreateUploadUrlInput): Promise<SignedObjectUrl>;
  createReadUrl(input: CreateReadUrlInput): Promise<SignedObjectUrl>;
  head(key: string): Promise<ObjectMetadata | null>;
  delete(key: string): Promise<void>;
}
