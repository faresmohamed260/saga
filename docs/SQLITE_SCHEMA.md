# SQLite Canon Store

## Purpose

The SQLite layer is the local operational store for S.A.G.A. It is meant to hold the same canonical information that currently lands in JSON contracts, but in a form that is:

- queryable during and after encoding
- easier to reason over incrementally
- better for enforcing non-empty structured traits
- easier to drive dashboard views, retrieval, and visual generation from

This schema lives at:

- [deploy/sqlite/schema.sql](/B:/Documents/PyCharm/graduationProject/deploy/sqlite/schema.sql)

## Design Goals

- keep one row per durable entity per book
- keep scene-by-scene provenance for trait evidence and state changes
- separate persistent traits from dynamic traits
- keep event/entity consistency explicit through join tables
- allow visual prompts and render outputs to attach directly to canonical entities

## Core Tables

- `series`, `books`, `encode_runs`, `run_books`
  - run provenance and book-level metadata
- `chapters`, `scenes`
  - source text, summaries, scene counts, per-scene runtime status
- `entities`, `entity_aliases`
  - canonical entity rows plus alias lookup
- `trait_definitions`, `typed_attribute_definitions`
  - controlled vocabulary for canonical traits and currently used typed buckets
- `entity_traits`
  - actual extracted trait rows with provenance
- `entity_state_changes`
  - dynamic transitions tied to scenes
- `events`, `event_entities`
  - event ledger plus guaranteed entity linkage
- `relationships`, `relationship_changes`
  - relationship registry and evolution
- `visual_prompts`, `render_outputs`
  - one-to-one visual prompt tracking and generated images

## Persistent Vs Dynamic Traits

Persistent traits are meant to survive across most of the book unless contradicted:

- character:
  - identity, build, face, hair, eyes, skin, marks, fantasy features, signature clothing, role, affiliations
- creature:
  - species/kind, body structure, visible anatomy, baseline threat posture
- object:
  - object kind, material, shape, craftsmanship, symbolic role
- location:
  - location kind, architecture style, scale, materials, baseline atmosphere

Dynamic traits are scene-bound and can change repeatedly:

- character:
  - current outfit, injuries, fatigue, emotional display, body language, current location
- creature:
  - condition, aggression, movement, active behavior
- object:
  - owner, activation state, damage, current location, contained contents
- location:
  - occupancy, weather, damage, restoration, active effects, current atmosphere

The canonical taxonomy source is:

- [core/trait_taxonomy.py](/B:/Documents/PyCharm/graduationProject/core/trait_taxonomy.py)

## Why This Helps

This solves several recurring pipeline problems:

- entity information can be deduped and normalized in one place
- if an event references an entity, we can enforce a matching entity row
- baseline character visuals can be stored separately from later injuries/outfit changes
- the dashboard can render structured views without reparsing large JSON blobs
- visual generation can read directly from entity rows instead of lossy adapters

## Current Status

This schema is the first-class contract for a future persistent local store. The repo still primarily writes JSON contracts today, but the trait taxonomy and table layout now define the intended storage model for the next persistence pass.
