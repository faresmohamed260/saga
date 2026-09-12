import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { sha256Hex } from "../src/ingestion/hash.js";
import type { LocalLiteraryAnalysisInput, LocalLiteraryEvidenceBundle } from "../src/local-analysis/types.js";
import {
  LocalLiteraryProviderError,
  SubprocessLocalLiteraryEvidenceProvider,
  sanitizedSubprocessEnvironment,
} from "../src/local-analysis/subprocess-provider.js";
import { validateLocalLiteraryEvidenceBundle } from "../src/local-analysis/validation.js";

const fixturePath = fileURLToPath(new URL("./fixtures/local-literary-provider-fixture.mjs", import.meta.url));
const descriptor = { name: "fixture-local", model: null, revision: "v1" } as const;
const configurationFingerprint = "c".repeat(64);
const text = "😀 Alice said, “Hi.” Bob waved.";

function codePointLength(value: string) {
  return Array.from(value).length;
}

function sourceSpan(surface: string, occurrence = 0) {
  let from = 0;
  let codeUnitStart = -1;
  for (let index = 0; index <= occurrence; index += 1) {
    codeUnitStart = text.indexOf(surface, from);
    assert.notEqual(codeUnitStart, -1);
    from = codeUnitStart + surface.length;
  }
  const startOffset = codePointLength(text.slice(0, codeUnitStart));
  return { startOffset, endOffset: startOffset + codePointLength(surface) };
}

const source: LocalLiteraryAnalysisInput = {
  normalizedInputFingerprint: sha256Hex(text),
  normalizedText: text,
  sections: [
    {
      stable_key: "document:0",
      ordinal: 0,
      section_kind: "document",
      title: null,
      source_locator: "fixture:local-literary",
      start_offset: 0,
      end_offset: codePointLength(text),
      normalized_text: text,
    },
  ],
};

function provider(
  mode = "success",
  overrides: {
    timeoutMs?: number;
    maxStdinBytes?: number;
    maxStdoutBytes?: number;
    maxStderrBytes?: number;
    executable?: string;
  } = {},
) {
  return new SubprocessLocalLiteraryEvidenceProvider({
    executable: overrides.executable ?? process.execPath,
    args: [fixturePath, mode],
    descriptor,
    configurationFingerprint,
    ...(overrides.timeoutMs === undefined ? {} : { timeoutMs: overrides.timeoutMs }),
    ...(overrides.maxStdinBytes === undefined ? {} : { maxStdinBytes: overrides.maxStdinBytes }),
    ...(overrides.maxStdoutBytes === undefined ? {} : { maxStdoutBytes: overrides.maxStdoutBytes }),
    ...(overrides.maxStderrBytes === undefined ? {} : { maxStderrBytes: overrides.maxStderrBytes }),
  });
}

async function expectProviderError(
  promise: Promise<unknown>,
  code: string,
  retryable: boolean,
) {
  await assert.rejects(promise, (error: unknown) => {
    assert.ok(error instanceof LocalLiteraryProviderError);
    assert.equal(error.code, code);
    assert.equal(error.retryable, retryable);
    return true;
  });
}

test("subprocess provider health and analyze round-trip through versioned JSON", async () => {
  const local = provider();
  assert.deepEqual(await local.health(), {
    status: "ok",
    provider: descriptor,
    protocolVersion: "saga-local-literary-subprocess-v1",
    configurationFingerprint,
  });
  const evidence = await local.analyze(source);
  assert.deepEqual(evidence.provider, descriptor);
  assert.equal(evidence.normalizedInputFingerprint, source.normalizedInputFingerprint);
  assert.deepEqual(evidence.identityEvidence.mentions, []);
  assert.deepEqual(evidence.entities, []);
  assert.deepEqual(evidence.quotes, []);
  assert.deepEqual(evidence.eventTriggers, []);
});

test("subprocess environment inherits runtime essentials but strips worker secrets", async () => {
  assert.deepEqual(
    sanitizedSubprocessEnvironment({
      PATH: "/fixture/bin",
      HOME: "/fixture/home",
      SAGA_SUPABASE_SERVICE_ROLE_KEY: "secret",
      SAGA_B2_APPLICATION_KEY: "secret-b2",
    }),
    { PATH: "/fixture/bin", HOME: "/fixture/home" },
  );

  const previous = process.env.SAGA_SUPABASE_SERVICE_ROLE_KEY;
  process.env.SAGA_SUPABASE_SERVICE_ROLE_KEY = "must-not-reach-child";
  const local = provider("fail-if-secret");
  if (previous === undefined) delete process.env.SAGA_SUPABASE_SERVICE_ROLE_KEY;
  else process.env.SAGA_SUPABASE_SERVICE_ROLE_KEY = previous;
  await local.health();
});

test("subprocess provider rejects protocol, provider, fingerprint, and source-evidence drift", async () => {
  await expectProviderError(provider("bad-provider").health(), "local_provider_descriptor_mismatch", false);
  await expectProviderError(provider("bad-request-id").health(), "local_provider_protocol_mismatch", false);
  await expectProviderError(provider("bad-protocol").health(), "local_provider_protocol_mismatch", false);
  await expectProviderError(provider("bad-fingerprint").analyze(source), "local_provider_input_fingerprint_mismatch", false);
  await expectProviderError(
    provider("bad-surface").analyze(source),
    "local_provider_invalid_evidence:local_entity_source_mismatch:fixture:entity:1",
    false,
  );
});

test("provider-reported failures preserve explicit retryability", async () => {
  await expectProviderError(
    provider("reported-retryable").health(),
    "local_provider_reported:model_temporarily_unavailable",
    true,
  );
  await expectProviderError(
    provider("reported-terminal").health(),
    "local_provider_reported:invalid_provider_configuration",
    false,
  );
});

test("subprocess resource guards distinguish timeout, output overflow, crash, and spawn configuration", async () => {
  await expectProviderError(provider("sleep", { timeoutMs: 1_000 }).health(), "local_provider_timeout", true);
  await expectProviderError(
    provider("oversize", { maxStdoutBytes: 1_024 }).health(),
    "local_provider_stdout_limit_exceeded",
    false,
  );
  await expectProviderError(
    provider("oversize-stderr", { maxStderrBytes: 1_024 }).health(),
    "local_provider_stderr_limit_exceeded",
    false,
  );
  await expectProviderError(provider("invalid-json").health(), "local_provider_invalid_json", false);
  await expectProviderError(provider("exit").health(), "local_provider_exit:7", true);
  await expectProviderError(
    provider("success", { executable: "__saga_missing_local_provider_executable__" }).health(),
    "local_provider_spawn_failed",
    false,
  );
});

test("subprocess provider bounds serialized source input before launch", async () => {
  const largeText = "x".repeat(2_000);
  const largeSource: LocalLiteraryAnalysisInput = {
    normalizedInputFingerprint: sha256Hex(largeText),
    normalizedText: largeText,
    sections: [
      {
        stable_key: "document:large",
        ordinal: 0,
        section_kind: "document",
        title: null,
        source_locator: "fixture:large",
        start_offset: 0,
        end_offset: codePointLength(largeText),
        normalized_text: largeText,
      },
    ],
  };
  await expectProviderError(
    provider("success", { maxStdinBytes: 1_024 }).analyze(largeSource),
    "local_provider_stdin_limit_exceeded",
    false,
  );
});

test("literary evidence validator accepts all current evidence families with Unicode code-point spans", () => {
  const alice = sourceSpan("Alice");
  const quote = sourceSpan("“Hi.”");
  const waved = sourceSpan("waved");
  const locator = "document:0:fixture:local-literary";
  const evidence: LocalLiteraryEvidenceBundle = {
    provider: descriptor,
    normalizedInputFingerprint: source.normalizedInputFingerprint,
    identityEvidence: {
      provider: descriptor,
      normalizedInputFingerprint: source.normalizedInputFingerprint,
      mentions: [
        {
          evidenceId: "fixture:identity:alice",
          surfaceText: "Alice",
          startOffset: alice.startOffset,
          endOffset: alice.endOffset,
          structuralLocator: locator,
          mentionKind: "proper_name",
          entityType: "person",
          personEvidence: "strong",
          boundaryQuality: "clean",
          providerClusterId: "fixture:alice",
        },
      ],
    },
    entities: [
      {
        evidenceId: "fixture:entity:alice",
        surfaceText: "Alice",
        startOffset: alice.startOffset,
        endOffset: alice.endOffset,
        structuralLocator: locator,
        mentionKind: "proper_name",
        category: "person",
        providerClusterId: "fixture:alice",
        boundaryQuality: "clean",
      },
    ],
    quotes: [
      {
        evidenceId: "fixture:quote:1",
        quoteText: "“Hi.”",
        startOffset: quote.startOffset,
        endOffset: quote.endOffset,
        structuralLocator: locator,
        speakerSurfaceText: "Alice",
        speakerStartOffset: alice.startOffset,
        speakerEndOffset: alice.endOffset,
        speakerProviderClusterId: "fixture:alice",
      },
    ],
    eventTriggers: [
      {
        evidenceId: "fixture:event:waved",
        surfaceText: "waved",
        lemma: "wave",
        startOffset: waved.startOffset,
        endOffset: waved.endOffset,
        structuralLocator: locator,
        sentenceId: 1,
        tokenId: 8,
        dependencyRelation: "ROOT",
        syntacticHeadTokenId: 8,
      },
    ],
  };

  assert.deepEqual(
    validateLocalLiteraryEvidenceBundle({ evidence, source, expectedProvider: descriptor }),
    evidence,
  );
});

test("literary evidence validator fails closed on duplicate IDs and partial speaker spans", () => {
  const alice = sourceSpan("Alice");
  const base = {
    provider: descriptor,
    normalizedInputFingerprint: source.normalizedInputFingerprint,
    identityEvidence: {
      provider: descriptor,
      normalizedInputFingerprint: source.normalizedInputFingerprint,
      mentions: [
        {
          evidenceId: "duplicate",
          surfaceText: "Alice",
          startOffset: alice.startOffset,
          endOffset: alice.endOffset,
          structuralLocator: "document:0",
          mentionKind: "proper_name",
          entityType: "person",
          personEvidence: "strong",
          boundaryQuality: "clean",
          providerClusterId: null,
        },
        {
          evidenceId: "duplicate",
          surfaceText: "Alice",
          startOffset: alice.startOffset,
          endOffset: alice.endOffset,
          structuralLocator: "document:0",
          mentionKind: "proper_name",
          entityType: "person",
          personEvidence: "strong",
          boundaryQuality: "clean",
          providerClusterId: null,
        },
      ],
    },
    entities: [],
    quotes: [],
    eventTriggers: [],
  };
  assert.throws(
    () => validateLocalLiteraryEvidenceBundle({ evidence: base, source, expectedProvider: descriptor }),
    /duplicate_local_identity_evidence_id:duplicate/u,
  );

  const quote = sourceSpan("“Hi.”");
  assert.throws(
    () => validateLocalLiteraryEvidenceBundle({
      evidence: {
        ...base,
        identityEvidence: { ...base.identityEvidence, mentions: [] },
        quotes: [
          {
            evidenceId: "fixture:partial-speaker",
            quoteText: "“Hi.”",
            startOffset: quote.startOffset,
            endOffset: quote.endOffset,
            structuralLocator: "document:0",
            speakerSurfaceText: "Alice",
            speakerStartOffset: null,
            speakerEndOffset: null,
            speakerProviderClusterId: null,
          },
        ],
      },
      source,
      expectedProvider: descriptor,
    }),
    /local_quote_partial_speaker_span/u,
  );
});
