import { hostname } from "node:os";

export type WorkerRuntimeConfig = {
  supabaseUrl: string;
  supabaseServiceRoleKey: string;
  b2Bucket: string;
  b2Endpoint: string;
  b2Region: string;
  b2ApplicationKeyId: string;
  b2ApplicationKey: string;
  workerId: string;
  leaseSeconds: number;
  idlePollMilliseconds: number;
};

function required(name: string) {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`Missing required worker configuration: ${name}`);
  return value;
}

function boundedInteger(name: string, fallback: number, min: number, max: number) {
  const raw = process.env[name]?.trim();
  if (!raw) return fallback;
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value < min || value > max) {
    throw new Error(`Invalid worker configuration: ${name}`);
  }
  return value;
}

export function requireWorkerRuntimeConfig(): WorkerRuntimeConfig {
  const endpoint = new URL(required("SAGA_B2_ENDPOINT"));
  if (endpoint.protocol !== "https:") throw new Error("SAGA_B2_ENDPOINT must use HTTPS.");

  const supabaseUrl = new URL(required("SAGA_SUPABASE_URL"));
  if (supabaseUrl.protocol !== "https:") throw new Error("SAGA_SUPABASE_URL must use HTTPS.");

  return {
    supabaseUrl: supabaseUrl.toString().replace(/\/$/, ""),
    supabaseServiceRoleKey: required("SAGA_SUPABASE_SERVICE_ROLE_KEY"),
    b2Bucket: required("SAGA_B2_BUCKET"),
    b2Endpoint: endpoint.toString().replace(/\/$/, ""),
    b2Region: required("SAGA_B2_REGION"),
    b2ApplicationKeyId: required("SAGA_B2_APPLICATION_KEY_ID"),
    b2ApplicationKey: required("SAGA_B2_APPLICATION_KEY"),
    workerId:
      process.env.SAGA_WORKER_ID?.trim() ||
      `source-ingestion:${hostname()}:${process.pid}`,
    leaseSeconds: boundedInteger("SAGA_WORKER_LEASE_SECONDS", 600, 30, 3600),
    idlePollMilliseconds: boundedInteger("SAGA_WORKER_IDLE_POLL_MS", 2000, 250, 60000),
  };
}
