import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import type { NormalizedSection } from "../ingestion/types.js";
import type { IdentityProviderDescriptor } from "../identity/types.js";
import type { LiteraryEntityCategory, LiteraryEntityEvidence } from "./types.js";

export const TYPED_ENTITY_EVIDENCE_SCHEMA = "saga-typed-entity-evidence-v1";
export const GLINER_RAW_ENTITY_SCHEMA = "saga-gliner-raw-entity-output-v1";

export type GlinerTypedEntityConfiguration = {
  package: string;
  packageVersion: string;
  model: string;
  modelRevision: string;
  labels: readonly string[];
  threshold: number;
  windowCodePoints: number;
  overlapCodePoints: number;
  batchSize: number;
};

export const GLINER_TYPED_ENTITY_CONFIG = {
  package: "gliner",
  packageVersion: "0.2.24",
  model: "urchade/gliner_small-v2.1",
  modelRevision: "f23104c107e3c57f5c7aa36d53a9667c67b4b866",
  labels: [
    "person",
    "location",
    "facility",
    "geopolitical entity",
    "organization",
    "vehicle",
  ],
  threshold: 0.5,
  windowCodePoints: 1400,
  overlapCodePoints: 180,
  batchSize: 12,
} as const satisfies GlinerTypedEntityConfiguration;

export const GLINER_TYPED_ENTITY_PROVIDER: IdentityProviderDescriptor = {
  name: "gliner_typed_entity",
  model: GLINER_TYPED_ENTITY_CONFIG.model,
  revision: `${GLINER_TYPED_ENTITY_CONFIG.package}@${GLINER_TYPED_ENTITY_CONFIG.packageVersion}:model@${GLINER_TYPED_ENTITY_CONFIG.modelRevision}`,
};

export type TypedEntityEvidenceSource = {
  schemaVersion: typeof TYPED_ENTITY_EVIDENCE_SCHEMA;
  provider: IdentityProviderDescriptor;
  normalizedInputFingerprint: string;
  configurationFingerprint: string;
  entities: LiteraryEntityEvidence[];
  outputFingerprint: string;
};

export type GlinerRawDetection = {
  startOffset: number;
  endOffset: number;
  surfaceText: string;
  label: string;
  score: number;
};

export type GlinerRawEntityOutput = {
  schemaVersion: typeof GLINER_RAW_ENTITY_SCHEMA;
  configuration: GlinerTypedEntityConfiguration;
  normalizedInputFingerprint: string;
  detections: GlinerRawDetection[];
};

const LABEL_TO_CATEGORY: Readonly<Record<string, LiteraryEntityCategory>> = {
  person: "person",
  location: "location",
  facility: "facility",
  "geopolitical entity": "geopolitical",
  organization: "organization",
  vehicle: "vehicle",
};

function validateFingerprint(value: string, errorCode: string) {
  if (!/^[0-9a-f]{64}$/u.test(value)) throw new Error(errorCode);
}

function codePointLength(value: string) {
  return Array.from(value).length;
}

function codePointSlice(value: string, startOffset: number, endOffset: number) {
  return Array.from(value).slice(startOffset, endOffset).join("");
}

function structuralLocatorForSpan(
  sections: NormalizedSection[],
  startOffset: number,
  endOffset: number,
) {
  const matches = sections
    .filter((section) => section.start_offset <= startOffset && section.end_offset >= endOffset)
    .sort((left, right) =>
      (left.end_offset - left.start_offset) - (right.end_offset - right.start_offset)
      || left.ordinal - right.ordinal
    );
  const section = matches[0];
  return section ? `${section.stable_key}:${section.source_locator}` : null;
}

function mentionKind(surfaceText: string): LiteraryEntityEvidence["mentionKind"] {
  const firstLetter = surfaceText.match(/\p{L}/u)?.[0];
  return firstLetter && firstLetter === firstLetter.toLocaleUpperCase("en-US")
    ? "proper_name"
    : "nominal";
}

function entityKey(entity: Pick<LiteraryEntityEvidence, "startOffset" | "endOffset" | "category">) {
  return `${entity.startOffset}:${entity.endOffset}:${entity.category}`;
}

export function glinerTypedEntityConfigurationFingerprint() {
  return sha256Hex(canonicalJson(GLINER_TYPED_ENTITY_CONFIG));
}

export function typedEntityEvidenceFingerprint(
  input: Omit<TypedEntityEvidenceSource, "outputFingerprint">,
) {
  return sha256Hex(canonicalJson(input));
}

export function validateTypedEntityEvidenceSource(source: TypedEntityEvidenceSource) {
  if (source.schemaVersion !== TYPED_ENTITY_EVIDENCE_SCHEMA) {
    throw new Error("unsupported_typed_entity_evidence_source");
  }
  if (!source.provider.name.trim() || !source.provider.revision.trim()) {
    throw new Error("invalid_typed_entity_evidence_provider");
  }
  validateFingerprint(source.normalizedInputFingerprint, "invalid_typed_entity_input_fingerprint");
  validateFingerprint(source.configurationFingerprint, "invalid_typed_entity_configuration_fingerprint");
  validateFingerprint(source.outputFingerprint, "invalid_typed_entity_output_fingerprint");

  const evidenceIds = new Set<string>();
  const exactEntities = new Set<string>();
  for (const entity of source.entities) {
    if (!entity.evidenceId.trim()) throw new Error("invalid_typed_entity_evidence_id");
    if (evidenceIds.has(entity.evidenceId)) {
      throw new Error(`duplicate_typed_entity_evidence_id:${entity.evidenceId}`);
    }
    evidenceIds.add(entity.evidenceId);
    if (
      !Number.isSafeInteger(entity.startOffset)
      || !Number.isSafeInteger(entity.endOffset)
      || entity.startOffset < 0
      || entity.endOffset <= entity.startOffset
    ) throw new Error(`invalid_typed_entity_span:${entity.evidenceId}`);
    if (!entity.surfaceText.length) throw new Error(`empty_typed_entity_surface:${entity.evidenceId}`);
    const key = entityKey(entity);
    if (exactEntities.has(key)) throw new Error(`duplicate_typed_entity_span:${key}`);
    exactEntities.add(key);
  }

  const expected = typedEntityEvidenceFingerprint({
    schemaVersion: source.schemaVersion,
    provider: source.provider,
    normalizedInputFingerprint: source.normalizedInputFingerprint,
    configurationFingerprint: source.configurationFingerprint,
    entities: source.entities,
  });
  if (expected !== source.outputFingerprint) throw new Error("typed_entity_output_fingerprint_mismatch");
}

export function normalizeGlinerEntityOutput(input: {
  normalizedText: string;
  normalizedInputFingerprint: string;
  sections: NormalizedSection[];
  raw: GlinerRawEntityOutput;
}): TypedEntityEvidenceSource {
  validateFingerprint(input.normalizedInputFingerprint, "invalid_gliner_input_fingerprint");
  if (input.raw.schemaVersion !== GLINER_RAW_ENTITY_SCHEMA) throw new Error("unsupported_gliner_raw_entity_output");
  if (input.raw.normalizedInputFingerprint !== input.normalizedInputFingerprint) {
    throw new Error("gliner_input_fingerprint_mismatch");
  }
  if (canonicalJson(input.raw.configuration) !== canonicalJson(GLINER_TYPED_ENTITY_CONFIG)) {
    throw new Error("gliner_configuration_mismatch");
  }

  const sourceLength = codePointLength(input.normalizedText);
  const seen = new Set<string>();
  const entities: LiteraryEntityEvidence[] = [];

  for (let index = 0; index < input.raw.detections.length; index += 1) {
    const detection = input.raw.detections[index]!;
    if (
      !Number.isSafeInteger(detection.startOffset)
      || !Number.isSafeInteger(detection.endOffset)
      || detection.startOffset < 0
      || detection.endOffset <= detection.startOffset
      || detection.endOffset > sourceLength
    ) throw new Error(`gliner_span_out_of_range:${index}`);
    if (!Number.isFinite(detection.score) || detection.score < 0 || detection.score > 1) {
      throw new Error(`gliner_invalid_score:${index}`);
    }
    const category = LABEL_TO_CATEGORY[detection.label];
    if (!category) throw new Error(`gliner_unknown_label:${detection.label}`);
    const surfaceText = codePointSlice(input.normalizedText, detection.startOffset, detection.endOffset);
    if (!surfaceText || !surfaceText.trim()) throw new Error(`gliner_empty_surface:${index}`);
    if (surfaceText !== detection.surfaceText) throw new Error(`gliner_source_mismatch:${index}`);
    const structuralLocator = structuralLocatorForSpan(
      input.sections,
      detection.startOffset,
      detection.endOffset,
    );
    if (structuralLocator === null) throw new Error(`gliner_section_missing:${index}`);

    const key = `${detection.startOffset}:${detection.endOffset}:${category}`;
    if (seen.has(key)) continue;
    seen.add(key);
    entities.push({
      evidenceId: `gliner-entity-${sha256Hex(`${key}:${surfaceText}`).slice(0, 20)}`,
      surfaceText,
      startOffset: detection.startOffset,
      endOffset: detection.endOffset,
      structuralLocator,
      mentionKind: mentionKind(surfaceText),
      category,
      providerClusterId: null,
      boundaryQuality: "clean",
    });
  }

  entities.sort((left, right) =>
    left.startOffset - right.startOffset
    || left.endOffset - right.endOffset
    || left.category.localeCompare(right.category)
    || left.evidenceId.localeCompare(right.evidenceId)
  );
  const semantic = {
    schemaVersion: TYPED_ENTITY_EVIDENCE_SCHEMA,
    provider: GLINER_TYPED_ENTITY_PROVIDER,
    normalizedInputFingerprint: input.normalizedInputFingerprint,
    configurationFingerprint: glinerTypedEntityConfigurationFingerprint(),
    entities,
  } satisfies Omit<TypedEntityEvidenceSource, "outputFingerprint">;
  const result = { ...semantic, outputFingerprint: typedEntityEvidenceFingerprint(semantic) };
  validateTypedEntityEvidenceSource(result);
  return result;
}
