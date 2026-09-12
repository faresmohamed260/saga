import { requireCurrentSagaAccount } from "@/server/account/account-access";
import { createSupabaseServerClient } from "@/server/supabase/server";
import { SagaStoryOperationError } from "./story-data";

export type SagaIdentityMention = {
  id: string;
  characterId: string | null;
  surfaceText: string;
  startOffset: number;
  endOffset: number;
  structuralLocator: string | null;
  mentionKind: "proper_name" | "nominal" | "pronoun";
  resolutionState: "linked" | "unresolved" | "quarantined";
  evidenceTier: "canonical_seed" | "attachment" | "quarantined";
  decisionReason: string;
};

export type SagaIdentityCharacter = {
  id: string;
  canonicalName: string;
  admissionTier: "canonical_seed" | "stabilized";
  evidenceCount: number;
  aliases: Array<{ surfaceForm: string; evidenceCount: number }>;
  mentions: SagaIdentityMention[];
};

export type SagaIdentityRun = {
  id: string;
  sourceId: string;
  sourceDisplayName: string;
  resolverVersion: string;
  providerName: string;
  providerModel: string | null;
  providerRevision: string;
  outputFingerprint: string;
  completedAt: string;
  characters: SagaIdentityCharacter[];
  unresolvedMentions: SagaIdentityMention[];
  quarantinedMentions: SagaIdentityMention[];
};

type Row = Record<string, unknown>;

function stringValue(row: Row, key: string) {
  const value = row[key];
  return typeof value === "string" ? value : null;
}
function numberValue(row: Row, key: string) {
  const value = row[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function mapMention(row: Row): SagaIdentityMention | null {
  const id = stringValue(row, "id");
  const surfaceText = stringValue(row, "surface_text");
  const startOffset = numberValue(row, "start_offset");
  const endOffset = numberValue(row, "end_offset");
  const mentionKind = stringValue(row, "mention_kind");
  const resolutionState = stringValue(row, "resolution_state");
  const evidenceTier = stringValue(row, "evidence_tier");
  const decisionReason = stringValue(row, "decision_reason");
  if (
    !id || !surfaceText || startOffset === null || endOffset === null || !decisionReason ||
    !["proper_name", "nominal", "pronoun"].includes(mentionKind ?? "") ||
    !["linked", "unresolved", "quarantined"].includes(resolutionState ?? "") ||
    !["canonical_seed", "attachment", "quarantined"].includes(evidenceTier ?? "")
  ) return null;
  return {
    id,
    characterId: stringValue(row, "character_id"),
    surfaceText,
    startOffset,
    endOffset,
    structuralLocator: stringValue(row, "structural_locator"),
    mentionKind: mentionKind as SagaIdentityMention["mentionKind"],
    resolutionState: resolutionState as SagaIdentityMention["resolutionState"],
    evidenceTier: evidenceTier as SagaIdentityMention["evidenceTier"],
    decisionReason,
  };
}

export async function getSagaProjectIdentityEvidence(projectId: string): Promise<SagaIdentityRun[]> {
  const account = await requireCurrentSagaAccount();
  const supabase = await createSupabaseServerClient();

  const [{ data: jobData, error: jobError }, { data: sourceData, error: sourceError }] = await Promise.all([
    supabase
      .from("saga_analysis_jobs")
      .select("id,source_id")
      .eq("project_id", projectId)
      .eq("owner_user_id", account.userId)
      .eq("kind", "character_identity")
      .eq("status", "succeeded"),
    supabase
      .from("saga_sources")
      .select("id,display_name")
      .eq("project_id", projectId)
      .eq("owner_user_id", account.userId),
  ]);
  if (jobError || sourceError || !jobData || !sourceData) throw new SagaStoryOperationError("unavailable", 503);
  if (jobData.length === 0) return [];

  const jobIds = jobData.map((row) => String((row as Row).id));
  const { data: runData, error: runError } = await supabase
    .from("saga_analysis_runs")
    .select("id,job_id,source_id,engine_version,provider_name,provider_model,provider_revision,output_fingerprint,completed_at")
    .eq("project_id", projectId)
    .eq("owner_user_id", account.userId)
    .eq("status", "succeeded")
    .in("job_id", jobIds)
    .order("completed_at", { ascending: false });
  if (runError || !runData) throw new SagaStoryOperationError("unavailable", 503);

  const latestBySource = new Map<string, Row>();
  for (const raw of runData) {
    const row = raw as Row;
    const sourceId = stringValue(row, "source_id");
    if (sourceId && !latestBySource.has(sourceId)) latestBySource.set(sourceId, row);
  }
  if (latestBySource.size === 0) return [];

  const runIds = [...latestBySource.values()].map((row) => stringValue(row, "id")!).filter(Boolean);
  const [charactersResult, aliasesResult, mentionsResult] = await Promise.all([
    supabase
      .from("saga_characters")
      .select("id,run_id,canonical_name,admission_tier,evidence_count")
      .in("run_id", runIds)
      .eq("project_id", projectId)
      .eq("owner_user_id", account.userId),
    supabase
      .from("saga_character_aliases")
      .select("character_id,run_id,surface_form,evidence_count")
      .in("run_id", runIds)
      .eq("project_id", projectId)
      .eq("owner_user_id", account.userId),
    supabase
      .from("saga_character_mentions")
      .select("id,character_id,run_id,surface_text,start_offset,end_offset,structural_locator,mention_kind,resolution_state,evidence_tier,decision_reason")
      .in("run_id", runIds)
      .eq("project_id", projectId)
      .eq("owner_user_id", account.userId)
      .order("start_offset", { ascending: true }),
  ]);
  if (charactersResult.error || aliasesResult.error || mentionsResult.error) {
    throw new SagaStoryOperationError("unavailable", 503);
  }

  const sourceNames = new Map(sourceData.map((row) => [String((row as Row).id), String((row as Row).display_name)]));
  const aliases = aliasesResult.data ?? [];
  const rawMentions = mentionsResult.data ?? [];
  const mappedMentions = rawMentions.map((row) => ({ row: row as Row, mention: mapMention(row as Row) }));
  if (mappedMentions.some(({ mention }) => !mention)) throw new SagaStoryOperationError("unavailable", 503);

  const runs: SagaIdentityRun[] = [];
  for (const [sourceId, row] of latestBySource) {
    const runId = stringValue(row, "id");
    const resolverVersion = stringValue(row, "engine_version");
    const providerName = stringValue(row, "provider_name");
    const providerRevision = stringValue(row, "provider_revision");
    const outputFingerprint = stringValue(row, "output_fingerprint");
    const completedAt = stringValue(row, "completed_at");
    if (!runId || !resolverVersion || !providerName || !providerRevision || !outputFingerprint || !completedAt) {
      throw new SagaStoryOperationError("unavailable", 503);
    }

    const runMentions = mappedMentions
      .filter(({ row: mentionRow }) => stringValue(mentionRow, "run_id") === runId)
      .map(({ mention }) => mention!);
    const characters: SagaIdentityCharacter[] = [];
    for (const rawCharacter of charactersResult.data ?? []) {
      const characterRow = rawCharacter as Row;
      if (stringValue(characterRow, "run_id") !== runId) continue;
      const id = stringValue(characterRow, "id");
      const canonicalName = stringValue(characterRow, "canonical_name");
      const admissionTier = stringValue(characterRow, "admission_tier");
      const evidenceCount = numberValue(characterRow, "evidence_count");
      if (!id || !canonicalName || evidenceCount === null || !["canonical_seed", "stabilized"].includes(admissionTier ?? "")) {
        throw new SagaStoryOperationError("unavailable", 503);
      }
      characters.push({
        id,
        canonicalName,
        admissionTier: admissionTier as SagaIdentityCharacter["admissionTier"],
        evidenceCount,
        aliases: aliases
          .filter((alias) => stringValue(alias as Row, "character_id") === id)
          .map((alias) => ({
            surfaceForm: stringValue(alias as Row, "surface_form") ?? "",
            evidenceCount: numberValue(alias as Row, "evidence_count") ?? 0,
          }))
          .filter((alias) => alias.surfaceForm.length > 0)
          .sort((a, b) => b.evidenceCount - a.evidenceCount || a.surfaceForm.localeCompare(b.surfaceForm)),
        mentions: runMentions.filter((mention) => mention.characterId === id).slice(0, 8),
      });
    }
    characters.sort((a, b) => b.evidenceCount - a.evidenceCount || a.canonicalName.localeCompare(b.canonicalName));

    runs.push({
      id: runId,
      sourceId,
      sourceDisplayName: sourceNames.get(sourceId) ?? "Story source",
      resolverVersion,
      providerName,
      providerModel: stringValue(row, "provider_model"),
      providerRevision,
      outputFingerprint,
      completedAt,
      characters,
      unresolvedMentions: runMentions.filter((mention) => mention.resolutionState === "unresolved"),
      quarantinedMentions: runMentions.filter((mention) => mention.resolutionState === "quarantined"),
    });
  }
  return runs;
}
