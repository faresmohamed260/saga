import assert from "node:assert/strict";
import test from "node:test";

import { sha256Hex } from "../src/ingestion/hash.js";
import type { NormalizedSection } from "../src/ingestion/types.js";
import {
  GLINER_RAW_ENTITY_SCHEMA,
  GLINER_TYPED_ENTITY_CONFIG,
  GLINER_TYPED_ENTITY_PROVIDER,
  glinerTypedEntityConfigurationFingerprint,
  normalizeGlinerEntityOutput,
  typedEntityEvidenceFingerprint,
  validateTypedEntityEvidenceSource,
  type GlinerRawEntityOutput,
} from "../src/local-analysis/typed-entity-evidence.js";

const text = "Éowyn left Cairo for the Citadel in a Ford.";
const fingerprint = sha256Hex(text);
const section: NormalizedSection = {
  stable_key: "fixture",
  ordinal: 0,
  section_kind: "document",
  title: null,
  source_locator: "fixture:source",
  start_offset: 0,
  end_offset: Array.from(text).length,
  normalized_text: text,
};

function span(surface: string) {
  const start = text.indexOf(surface);
  assert.ok(start >= 0);
  const prefix = Array.from(text.slice(0, start)).length;
  return { startOffset: prefix, endOffset: prefix + Array.from(surface).length };
}

function raw(detections: GlinerRawEntityOutput["detections"]): GlinerRawEntityOutput {
  return {
    schemaVersion: GLINER_RAW_ENTITY_SCHEMA,
    configuration: GLINER_TYPED_ENTITY_CONFIG,
    normalizedInputFingerprint: fingerprint,
    detections,
  };
}

test("GLiNER typed entity normalizer maps supported labels and preserves Unicode code-point offsets", () => {
  const cairo = span("Cairo");
  const citadel = span("Citadel");
  const ford = span("Ford");
  const result = normalizeGlinerEntityOutput({
    normalizedText: text,
    normalizedInputFingerprint: fingerprint,
    sections: [section],
    raw: raw([
      { ...cairo, surfaceText: "Cairo", label: "geopolitical entity", score: 0.91 },
      { ...citadel, surfaceText: "Citadel", label: "facility", score: 0.88 },
      { ...ford, surfaceText: "Ford", label: "vehicle", score: 0.83 },
    ]),
  });

  assert.deepEqual(result.provider, GLINER_TYPED_ENTITY_PROVIDER);
  assert.equal(result.configurationFingerprint, glinerTypedEntityConfigurationFingerprint());
  assert.deepEqual(result.entities.map((entity) => entity.category), ["geopolitical", "facility", "vehicle"]);
  assert.equal(result.entities[0]!.surfaceText, "Cairo");
  assert.equal(result.entities[0]!.structuralLocator, "fixture:fixture:source");
  assert.equal(result.entities.every((entity) => entity.boundaryQuality === "clean"), true);
  validateTypedEntityEvidenceSource(result);
});

test("GLiNER typed entity normalizer maps person/location/organization and deduplicates exact overlap deterministically", () => {
  const eowyn = span("Éowyn");
  const cairo = span("Cairo");
  const result = normalizeGlinerEntityOutput({
    normalizedText: text,
    normalizedInputFingerprint: fingerprint,
    sections: [section],
    raw: raw([
      { ...eowyn, surfaceText: "Éowyn", label: "person", score: 0.9 },
      { ...cairo, surfaceText: "Cairo", label: "location", score: 0.8 },
      { ...cairo, surfaceText: "Cairo", label: "location", score: 0.7 },
      { ...cairo, surfaceText: "Cairo", label: "organization", score: 0.6 },
    ]),
  });

  assert.equal(result.entities.length, 3);
  assert.deepEqual(result.entities.map((entity) => entity.category), ["person", "location", "organization"]);
  assert.equal(new Set(result.entities.map((entity) => entity.evidenceId)).size, 3);
});

test("GLiNER typed entity normalizer fails closed on configuration, fingerprint, source, label, score and section drift", () => {
  const cairo = span("Cairo");
  const base = raw([{ ...cairo, surfaceText: "Cairo", label: "location", score: 0.8 }]);

  assert.throws(
    () => normalizeGlinerEntityOutput({
      normalizedText: text,
      normalizedInputFingerprint: fingerprint,
      sections: [section],
      raw: { ...base, normalizedInputFingerprint: "f".repeat(64) },
    }),
    /gliner_input_fingerprint_mismatch/u,
  );

  assert.throws(
    () => normalizeGlinerEntityOutput({
      normalizedText: text,
      normalizedInputFingerprint: fingerprint,
      sections: [section],
      raw: { ...base, configuration: { ...GLINER_TYPED_ENTITY_CONFIG, threshold: 0.4 } },
    }),
    /gliner_configuration_mismatch/u,
  );

  assert.throws(
    () => normalizeGlinerEntityOutput({
      normalizedText: text,
      normalizedInputFingerprint: fingerprint,
      sections: [section],
      raw: raw([{ ...cairo, surfaceText: "Wrong", label: "location", score: 0.8 }]),
    }),
    /gliner_source_mismatch/u,
  );

  assert.throws(
    () => normalizeGlinerEntityOutput({
      normalizedText: text,
      normalizedInputFingerprint: fingerprint,
      sections: [section],
      raw: raw([{ ...cairo, surfaceText: "Cairo", label: "artifact", score: 0.8 }]),
    }),
    /gliner_unknown_label:artifact/u,
  );

  assert.throws(
    () => normalizeGlinerEntityOutput({
      normalizedText: text,
      normalizedInputFingerprint: fingerprint,
      sections: [section],
      raw: raw([{ ...cairo, surfaceText: "Cairo", label: "location", score: 1.2 }]),
    }),
    /gliner_invalid_score/u,
  );

  assert.throws(
    () => normalizeGlinerEntityOutput({
      normalizedText: text,
      normalizedInputFingerprint: fingerprint,
      sections: [],
      raw: base,
    }),
    /gliner_section_missing/u,
  );
});

test("typed entity evidence source validation detects semantic fingerprint tampering", () => {
  const cairo = span("Cairo");
  const result = normalizeGlinerEntityOutput({
    normalizedText: text,
    normalizedInputFingerprint: fingerprint,
    sections: [section],
    raw: raw([{ ...cairo, surfaceText: "Cairo", label: "location", score: 0.8 }]),
  });
  const tampered = {
    ...result,
    entities: [{ ...result.entities[0]!, category: "facility" as const }],
  };
  assert.throws(() => validateTypedEntityEvidenceSource(tampered), /typed_entity_output_fingerprint_mismatch/u);

  const repaired = {
    ...tampered,
    outputFingerprint: typedEntityEvidenceFingerprint({
      schemaVersion: tampered.schemaVersion,
      provider: tampered.provider,
      normalizedInputFingerprint: tampered.normalizedInputFingerprint,
      configurationFingerprint: tampered.configurationFingerprint,
      entities: tampered.entities,
    }),
  };
  validateTypedEntityEvidenceSource(repaired);
});
