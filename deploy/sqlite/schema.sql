PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS series (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS books (
    id TEXT PRIMARY KEY,
    series_id TEXT,
    book_index INTEGER,
    title TEXT NOT NULL,
    source_path TEXT,
    contract_path TEXT,
    identity_provider TEXT,
    identity_json_path TEXT,
    analysis_provider TEXT,
    analysis_model TEXT,
    run_status TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (series_id) REFERENCES series(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_books_series ON books(series_id, book_index);

CREATE TABLE IF NOT EXISTS encode_runs (
    run_id TEXT PRIMARY KEY,
    series_id TEXT,
    provider_mode TEXT,
    analysis_provider TEXT,
    analysis_model TEXT,
    identity_provider TEXT,
    identity_json_path TEXT,
    prompt_version TEXT,
    analyzer_version TEXT,
    scene_failure_policy TEXT,
    account_rotation_allowed INTEGER NOT NULL DEFAULT 0,
    cross_provider_fallback_allowed INTEGER NOT NULL DEFAULT 0,
    canonical_consistency_status TEXT,
    started_at TEXT,
    finished_at TEXT,
    status TEXT,
    metadata_json TEXT,
    FOREIGN KEY (series_id) REFERENCES series(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS run_books (
    run_id TEXT NOT NULL,
    book_id TEXT NOT NULL,
    PRIMARY KEY (run_id, book_id),
    FOREIGN KEY (run_id) REFERENCES encode_runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chapters (
    id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    chapter_index INTEGER NOT NULL,
    title TEXT,
    word_count INTEGER,
    chapter_text TEXT,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chapters_book ON chapters(book_id, chapter_index);

CREATE TABLE IF NOT EXISTS scenes (
    id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    chapter_id TEXT,
    chapter_index INTEGER,
    scene_index INTEGER,
    scene_key TEXT,
    word_count INTEGER,
    source_text TEXT,
    scene_summary TEXT,
    location_name TEXT,
    tension_score REAL,
    pov_character TEXT,
    analysis_provider TEXT,
    analysis_model TEXT,
    attempt_count INTEGER,
    final_status TEXT,
    error_category TEXT,
    last_error TEXT,
    analysis_duration_seconds REAL,
    metadata_json TEXT,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_scenes_book ON scenes(book_id, chapter_index, scene_index);
CREATE INDEX IF NOT EXISTS idx_scenes_status ON scenes(final_status);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    subtype TEXT,
    first_scene_id TEXT,
    first_chapter_index INTEGER,
    first_scene_index INTEGER,
    baseline_description TEXT,
    baseline_source TEXT,
    confidence TEXT,
    visual_prompt_baseline TEXT,
    notes TEXT,
    metadata_json TEXT,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (first_scene_id) REFERENCES scenes(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_entities_book ON entities(book_id, entity_type, canonical_name);

CREATE TABLE IF NOT EXISTS entity_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    alias TEXT NOT NULL,
    normalized_alias TEXT,
    alias_source TEXT,
    UNIQUE(entity_id, alias),
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entity_aliases_lookup ON entity_aliases(normalized_alias);

CREATE TABLE IF NOT EXISTS trait_definitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    trait_scope TEXT NOT NULL,
    trait_category TEXT NOT NULL,
    trait_key TEXT NOT NULL,
    UNIQUE(entity_type, trait_scope, trait_category, trait_key)
);

CREATE TABLE IF NOT EXISTS typed_attribute_definitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    typed_attribute_key TEXT NOT NULL,
    UNIQUE(entity_type, typed_attribute_key)
);

CREATE TABLE IF NOT EXISTS entity_traits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    scene_id TEXT,
    trait_scope TEXT NOT NULL,
    trait_category TEXT NOT NULL,
    trait_key TEXT NOT NULL,
    trait_value TEXT NOT NULL,
    is_baseline INTEGER NOT NULL DEFAULT 0,
    confidence TEXT,
    evidence_text TEXT,
    provenance_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_entity_traits_entity ON entity_traits(entity_id, trait_scope, trait_key);
CREATE INDEX IF NOT EXISTS idx_entity_traits_scene ON entity_traits(scene_id);

CREATE TABLE IF NOT EXISTS entity_state_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    scene_id TEXT NOT NULL,
    attribute_name TEXT NOT NULL,
    previous_state TEXT,
    new_state TEXT,
    change_type TEXT,
    evidence_text TEXT,
    confidence TEXT,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entity_state_changes_entity ON entity_state_changes(entity_id, scene_id);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    scene_id TEXT,
    event_index INTEGER,
    event_type TEXT,
    summary TEXT NOT NULL,
    reason TEXT,
    outcome TEXT,
    consequence TEXT,
    causal_parent_event_id TEXT,
    metadata_json TEXT,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE SET NULL,
    FOREIGN KEY (causal_parent_event_id) REFERENCES events(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_events_book ON events(book_id, scene_id, event_index);

CREATE TABLE IF NOT EXISTS event_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    role_in_event TEXT,
    UNIQUE(event_id, entity_id, role_in_event),
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS relationships (
    id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    entity_a_id TEXT NOT NULL,
    entity_b_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    current_state TEXT,
    first_scene_id TEXT,
    latest_scene_id TEXT,
    confidence TEXT,
    metadata_json TEXT,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (entity_a_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (entity_b_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (first_scene_id) REFERENCES scenes(id) ON DELETE SET NULL,
    FOREIGN KEY (latest_scene_id) REFERENCES scenes(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_relationships_book ON relationships(book_id, relationship_type);

CREATE TABLE IF NOT EXISTS relationship_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    relationship_id TEXT NOT NULL,
    scene_id TEXT NOT NULL,
    change_summary TEXT NOT NULL,
    previous_state TEXT,
    new_state TEXT,
    evidence_text TEXT,
    FOREIGN KEY (relationship_id) REFERENCES relationships(id) ON DELETE CASCADE,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS locations (
    entity_id TEXT PRIMARY KEY,
    location_kind TEXT,
    architecture_style TEXT,
    environment_type TEXT,
    atmosphere_baseline TEXT,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS visual_prompts (
    id TEXT PRIMARY KEY,
    entity_id TEXT,
    scene_id TEXT,
    prompt_scope TEXT NOT NULL,
    prompt_type TEXT NOT NULL,
    positive_prompt TEXT NOT NULL,
    negative_prompt TEXT,
    source_summary TEXT,
    renderer_target TEXT,
    readiness_score REAL,
    metadata_json TEXT,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_visual_prompts_lookup ON visual_prompts(entity_id, scene_id, prompt_scope, prompt_type);

CREATE TABLE IF NOT EXISTS render_outputs (
    id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL,
    workflow_name TEXT,
    workflow_mode TEXT,
    output_path TEXT,
    thumbnail_path TEXT,
    render_status TEXT,
    width INTEGER,
    height INTEGER,
    seed TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata_json TEXT,
    FOREIGN KEY (prompt_id) REFERENCES visual_prompts(id) ON DELETE CASCADE
);

