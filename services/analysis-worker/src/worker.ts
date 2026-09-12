import { setTimeout as sleep } from "node:timers/promises";

import { processOneSourceIngestionJob } from "./processor.js";
import { requireWorkerRuntimeConfig } from "./runtime/config.js";
import { WorkerDatabase } from "./runtime/database.js";
import { createB2SourceObjectReader } from "./runtime/storage.js";

async function main() {
  const config = requireWorkerRuntimeConfig();
  const database = new WorkerDatabase(config);
  const storage = createB2SourceObjectReader(config);
  const runOnce = process.env.SAGA_WORKER_ONCE === "1";

  for (;;) {
    const result = await processOneSourceIngestionJob({
      database,
      storage,
      workerId: config.workerId,
      leaseSeconds: config.leaseSeconds,
    });

    console.log(
      JSON.stringify({
        event: "source_ingestion_iteration",
        workerId: config.workerId,
        ...result,
      }),
    );

    if (runOnce) return;
    if (result.status === "no_work") {
      await sleep(config.idlePollMilliseconds);
    }
  }
}

main().catch((error) => {
  console.error(
    JSON.stringify({
      event: "source_ingestion_worker_fatal",
      error: error instanceof Error ? error.message : String(error),
    }),
  );
  process.exitCode = 1;
});
