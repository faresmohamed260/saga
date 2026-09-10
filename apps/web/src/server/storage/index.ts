import { createBackblazeB2Storage } from "./b2";

import type { ObjectStorage } from "./types";

export type { ObjectMetadata, ObjectStorage, SignedObjectUrl } from "./types";

export type StorageConfigurationStatus = {
  configured: boolean;
  provider: "backblaze-b2";
};

export function storageConfigurationStatus(): StorageConfigurationStatus {
  return {
    configured: Boolean(
      process.env.SAGA_B2_BUCKET?.trim() &&
        process.env.SAGA_B2_ENDPOINT?.trim() &&
        process.env.SAGA_B2_REGION?.trim() &&
        process.env.SAGA_B2_APPLICATION_KEY_ID?.trim() &&
        process.env.SAGA_B2_APPLICATION_KEY?.trim(),
    ),
    provider: "backblaze-b2",
  };
}

export function createObjectStorage(): ObjectStorage {
  return createBackblazeB2Storage();
}
