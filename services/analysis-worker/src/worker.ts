import { setTimeout as sleep } from "node:timers/promises";

import { createConfiguredIdentityEvidenceProvider } from "./identity/provider-config.js";
import { processOneCharacterIdentityJob } from "./identity-processor.js";
import { processOneSourceIngestionJob } from "./processor.js";
import { requireWorkerRuntimeConfig } from "./runtime/config.js";
import { WorkerDatabase } from "./runtime/database.js";
import { createB2SourceObjectReader } from "./runtime/storage.js";

async function main() {
  const config = requireWorkerRuntimeConfig();
  const database = new WorkerDatabase(config);
  const storage = createB2SourceObjectReader(config);
  const identityProvider = createConfiguredIdentityEvidenceProvider();
  const runOnce = process.env.SAGA_WORKER_ONCE === "1";

  for (;;) {
    const ingestion = await processOneSourceIngestionJob({
      database,
      storage,
      workerId: `${config.workerId}:ingestion`,
      leaseSeconds: config.leaseSeconds,
    });

    console.log(
      JSON.stringify({
        event: "source_ingestion_iteration",
        workerId: config.workerId,
        ...ingestion,
      }),
    );

    const identity = identityProvider
      ? await processOneCharacterIdentityJob({
          database,
          provider: identityProvider,
          workerId: `${config.workerId}:identity`,
          leaseSeconds: config.leaseSeconds,
        })
      : { status: "no_work" as const };

    console.log(
      JSON.stringify({
        event: "character_identity_iteration",
        workerId: config.workerId,
        providerConfigured: Boolean(identityProvider),
        ...identity,
      }),
    );

    if (runOnce) return;
    if (ingestion.status === "no_work" && identity.status === "no_work") {
      await sleep(config.idlePollMilliseconds);
    }
  }
}

main().catch((error) => {
  console.error(
    JSON.stringify({
      event: "analysis_worker_fatal",
      error: error instanceof Error ? error.message : String(error),
    }),
  );
  process.exitCode = 1;
});
