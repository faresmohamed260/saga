import { canonicalJson, sha256Hex } from "../ingestion/hash.js";

export const BOOKNLP_BASE_COMMIT = "3d900fc2224e55960c3363826ae28539b77b4204";
export const BOOKNLP_COMPAT_COMMIT = "8875a1b616d764b7d13d1e30e9949cc21ca303c1";
export const BOOKNLP_EXPECTED_PACKAGE_VERSION = "1.0.7";
export const BOOKNLP_MODEL = "small";
export const BOOKNLP_PIPELINE = "entity,quote,event,coref";
export const BOOKNLP_PROVIDER_PROCESS_VERSION = "saga-booknlp-provider-v1";
export const BOOKNLP_SMALL_MODEL_FILES = [
  "entities_google_bert_uncased_L-4_H-256_A-4-v1.0.model",
  "coref_google_bert_uncased_L-2_H-256_A-4-v1.0.model",
  "speaker_google_bert_uncased_L-8_H-256_A-4-v1.0.1.model",
] as const;

export const BOOKNLP_SMALL_PROVIDER = {
  name: "booknlp-small",
  model: BOOKNLP_MODEL,
  revision: `booknlp-base:${BOOKNLP_BASE_COMMIT}|compat-pr25:${BOOKNLP_COMPAT_COMMIT}`,
} as const;

export const BOOKNLP_PROVIDER_BASE_CONFIGURATION_FINGERPRINT = sha256Hex(canonicalJson({
  adapterVersion: BOOKNLP_PROVIDER_PROCESS_VERSION,
  provider: BOOKNLP_SMALL_PROVIDER,
  packageVersion: BOOKNLP_EXPECTED_PACKAGE_VERSION,
  pipeline: BOOKNLP_PIPELINE,
  requiredModelFiles: BOOKNLP_SMALL_MODEL_FILES,
}));

export function bookNlpRuntimeConfigurationFingerprint(input: {
  runnerExecutable: string;
  runnerArgs: string[];
  modelPath: string;
}) {
  return sha256Hex(canonicalJson({
    baseConfigurationFingerprint: BOOKNLP_PROVIDER_BASE_CONFIGURATION_FINGERPRINT,
    runnerExecutable: input.runnerExecutable,
    runnerArgs: input.runnerArgs,
    modelPath: input.modelPath,
  }));
}
