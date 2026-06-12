function summarizeContract(payload) {
  const outputs = payload.outputs || {};
  const scenes = outputs.resolved_scene_analyses || outputs.scene_analyses || [];
  return {
    artifactType: "contract",
    bookTitle: payload.metadata?.book_title || payload.book_title || payload.title || "",
    sceneCount: scenes.length,
    timelineCount: (outputs.timeline || []).length,
    eventLedgerCount: (outputs.event_ledger || []).length,
    entityRegistryCount: (outputs.entity_registry || []).length,
    characterProfileCount: (outputs.character_profiles || []).length,
    stableCharacterStateCount: (outputs.stable_character_states || []).length,
    runStatus: payload.run_status || payload.metadata?.run_status || "",
    identityProvider: payload.configuration?.identity_provider || payload.metadata?.identity_provider || "",
    chapterCount: (outputs.chapters || []).length || payload.metadata?.chapter_count || 0,
  };
}

function summarizeRunStatus(payload) {
  const books = payload.books || [];
  return {
    artifactType: "run_status",
    seriesId: payload.series_id || "",
    seriesTitle: payload.series_title || "",
    runStatus: payload.status || "",
    bookCount: books.length || payload.summary?.total_requested || 0,
    completedBooks: payload.summary?.completed || books.filter((book) => book.status === "completed").length,
    failedBooks: payload.summary?.failed || books.filter((book) => book.status === "failed").length,
    totalScenes: books.reduce((sum, book) => sum + Number(book.total_scenes || 0), 0),
    failedScenes: books.reduce((sum, book) => sum + Number(book.failed_scenes || 0), 0),
    analysisModel: payload.configuration?.analysis_model || "",
    identityProvider: payload.configuration?.identity_provider || "",
  };
}

function summarizeIdentity(payload) {
  return {
    artifactType: "identity",
    characterCount: (payload.characters || []).length,
    aliasCount: Object.keys(payload.alias_index || payload.alias_map || {}).length,
    narratorCount: Array.isArray(payload.narrators) ? payload.narrators.length : payload.narrator ? 1 : 0,
    referenceEntityCount: (payload.reference_entities || []).length,
    suppressedClusterCount: (payload.suppressed_clusters || []).length,
  };
}

function summarizeCharacterState(payload) {
  return {
    artifactType: "character_state",
    targetMode: payload.target_point?.mode || payload.target_mode || "",
    characterCount: (payload.character_states || payload.characters || []).length,
    confidenceCount: (payload.confidence_distribution || []).length,
  };
}

function summarizeVisualState(payload) {
  return {
    artifactType: "visual_world_state",
    targetMode: payload.target_point?.mode || payload.target_mode || "",
    characterVisualCount: (payload.character_visual_states || []).length,
    entityVisualCount: (payload.entity_visual_states || []).length,
    locationVisualCount: (payload.location_visual_states || []).length,
    sceneVisualCount: (payload.scene_visual_states || []).length,
  };
}

function summarizePromptPack(payload) {
  return {
    artifactType: "prompt_pack",
    characterPromptCount: (payload.character_prompts || []).length,
    locationPromptCount: (payload.location_prompts || []).length,
    objectPromptCount: (payload.object_prompts || payload.entity_prompts || []).length,
    scenePromptCount: (payload.scene_prompts || []).length,
    suppressedCount: (payload.suppressed_entries || []).length,
  };
}

function summarizeRetrievalContext(payload) {
  return {
    artifactType: "retrieval_context",
    defaultStatus: payload.default_context?.status || "",
    targetStatus: payload.target_context?.status || "",
    focusCoverageCount: (payload.focus_character_coverage || []).length,
    relationshipCoverageCount: (payload.relationship_coverage || []).length,
    unresolvedThreadCount: (payload.unresolved_plot_threads || []).length,
  };
}

function summarizeValidation(payload) {
  return {
    artifactType: "validation",
    validationMode: payload.validation_mode || "",
    identityProvider: payload.identity_provider || "",
    rootCause: payload.root_cause?.classification || "",
    sceneCount: payload.scene_schema?.scene_count || 0,
    timelineCount: payload.artifact_snapshot?.timeline?.count || 0,
    profileCount: payload.artifact_snapshot?.character_profiles?.count || 0,
  };
}

function summarizeOtherJson(payload) {
  return {
    artifactType: "other_json",
    topLevelKeys: typeof payload === "object" && payload ? Object.keys(payload).length : 0,
  };
}

function summarizePayload(type, payload) {
  switch (type) {
    case "contract":
      return summarizeContract(payload);
    case "run_status":
      return summarizeRunStatus(payload);
    case "identity":
      return summarizeIdentity(payload);
    case "character_state":
      return summarizeCharacterState(payload);
    case "visual_world_state":
      return summarizeVisualState(payload);
    case "prompt_pack":
      return summarizePromptPack(payload);
    case "retrieval_context":
      return summarizeRetrievalContext(payload);
    case "validation":
      return summarizeValidation(payload);
    default:
      return summarizeOtherJson(payload);
  }
}

self.onmessage = (event) => {
  const { id, action, text, artifactType } = event.data;
  try {
    const payload = JSON.parse(text);
    if (action === "parse") {
      self.postMessage({ id, ok: true, payload });
      return;
    }
    const summary = summarizePayload(artifactType, payload);
    self.postMessage({ id, ok: true, summary });
  } catch (error) {
    self.postMessage({ id, ok: false, error: error instanceof Error ? error.message : String(error) });
  }
};
