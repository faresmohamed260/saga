export function countFor(view, key) {
  const counts = view?.counts || {};
  if (key === "scenes") return counts.resolved_scene_analyses || 0;
  if (key === "entities") return counts.entity_registry || 0;
  if (key === "events") return counts.event_ledger || 0;
  if (key === "timeline") return counts.timeline || 0;
  if (key === "states") return counts.stable_character_states || 0;
  if (key === "world") return counts.scene_world_state || 0;
  return counts.visual_inventory || 0;
}

export function searchableLabelFor(section, row) {
  if (!row || typeof row !== "object") return "";
  if (section === "entities" || section === "visuals") {
    return row.name || row.entity_name || row.canonical_name || "";
  }
  if (section === "events") {
    return row.title || row.event_title || row.summary || row.description || row.event_id || "";
  }
  if (section === "scenes" || section === "world") {
    return row.title || row.scene_title || row.scene_summary || row.summary || "";
  }
  if (section === "states") {
    return row.character_name || row.name || row.entity_name || "";
  }
  if (section === "timeline") {
    return row.title || row.summary || row.description || row.event || "";
  }
  return JSON.stringify(row);
}
