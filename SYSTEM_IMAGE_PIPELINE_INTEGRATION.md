# S.A.G.A. Image Pipeline Integration

## Purpose

The image pipeline is a fully integrated subsystem of the current production architecture. Its role is not only to generate pictures, but to convert canon-aware analytical memory into reusable, visually consistent assets for downstream inspection, editing, and narrative rendering.

This document covers four workflows as part of the integrated system:

- `Character visual generation`
  Baseline three-view character sheets generated from entity visual memory.
- `Location visual generation`
  Environment-first location frames generated from stored location visual memory.
- `Non-character entity visual generation`
  Text-to-image generation for creatures, objects, artifacts, organizations, and other non-character world entities.
- `Scene composition generation`
  Full-scene visual synthesis that retrieves previously generated entity assets from the database and merges them into a coherent scene frame using an image-to-image composition workflow.

In the current image stack:

- entity workflows use `z-image turbo` as the text-to-image model
- full-scene composition uses `Flux.2 klein` as the image-to-image model

## Core Role In The System

The image pipeline exists to solve a practical continuity problem:

How do we make the visual layer of a story as reusable and canon-aware as the text layer?

That means the image system must do more than generate attractive standalone pictures. It must:

- derive visuals from stored canon analysis
- separate persistent appearance from dynamic scene state
- keep visual outputs tied to entity identity
- support multiple visual classes, not only characters
- make outputs inspectable and editable in the dashboard
- persist prompts, images, and provenance in the database
- enable later scene-level composition without losing consistency

## Methodology

### High-Level Method

The current image pipeline follows this methodology:

1. analyze books and persist canon data into SQLite
2. extract visual traits and state changes as structured database rows
3. build class-aware visual prompts from stored visual memory
4. generate reusable entity-level assets with `z-image turbo`
5. persist prompt versions and rendered images in the canonical store
6. retrieve stored entity assets when a composite scene is requested
7. compose multi-entity scenes with `Flux.2 klein` using image-to-image conditioning
8. expose every prompt, render, and asset version through the dashboard

This design deliberately separates:

- `entity baseline visuals`
  Persistent appearance and world-facing visual identity
- `scene visual state`
  Local changes such as outfit shifts, injuries, prop carriage, damage state, lighting, or atmosphere
- `render prompts`
  Generation-ready instructions derived from the structured memory
- `rendered assets`
  The actual generated files tied back to entity and prompt provenance

That separation is the reason the system can support both visual realism and canonical consistency.

## System Evolution

### Prototype Era

In the prototype system, visual behavior was more fragmented:

- prompt packs were often built from exported artifacts
- visual state was treated more like a downstream adapter than a core memory layer
- character prompts were easier to generate than world visuals
- image generation had weaker ties to canonical identity and scene provenance
- later workflows had to reconstruct visual truth from loose outputs

That prototype work proved the concept, but it was not strong enough for a production visual pipeline.

### Current System

The current system treats visuals as part of operational canon memory.

The key architectural shifts are:

- visual state lives in SQLite, not in loose prompt files
- entity records carry visual memory and generated asset references
- prompt generation is database-native and class-aware
- generated images are stored as tracked outputs of the entity rows
- scene composition retrieves known entity assets instead of inventing every element from scratch
- the dashboard is the operating surface for inspection, prompt review, and rendering

These changes were made because visual consistency is impossible to maintain reliably if prompts and images are detached from the canon store.

## Image Pipeline Architecture

## 1. Visual Memory Extraction

### Role

This layer converts analysis results into renderable visual memory.

It must capture:

- character baseline appearance
- character scene-level visual changes
- creature baseline appearance
- object baseline appearance
- location baseline appearance
- location or non-character scene state where relevant

### Implementation

Main implementation surfaces:

- [saga/agents/db_character_visual_baseline_agent.py](/B:/Documents/PyCharm/graduationProject/saga/agents/db_character_visual_baseline_agent.py)
- [saga/agents/db_character_visual_scene_state_agent.py](/B:/Documents/PyCharm/graduationProject/saga/agents/db_character_visual_scene_state_agent.py)
- [saga/agents/db_noncharacter_visual_baseline_agent.py](/B:/Documents/PyCharm/graduationProject/saga/agents/db_noncharacter_visual_baseline_agent.py)
- [saga/agents/db_noncharacter_scene_state_agent.py](/B:/Documents/PyCharm/graduationProject/saga/agents/db_noncharacter_scene_state_agent.py)
- [saga/agents/db_world_state_consolidation_agent.py](/B:/Documents/PyCharm/graduationProject/saga/agents/db_world_state_consolidation_agent.py)

These agents persist structured visual facts into dedicated tables and entity-level JSON fields. They do not directly generate images. Their role is to build the memory that later render steps depend on.

### Why It Matters

Without this layer, image prompts would be free-floating guesses. With it, prompt generation becomes a controlled translation from canon memory into render instructions.

## 2. Canonical Visual Storage

### Role

The database is the source of truth for visual state, prompts, and images.

It stores:

- baseline visual traits per character
- baseline visual traits per creature
- baseline visual traits per object
- baseline visual traits per location
- scene-level character visual changes
- scene-level non-character state changes
- prompt versions
- generated image versions
- active image paths on entity rows

### Implementation

Main schema surfaces:

- [saga/storage/models.py](/B:/Documents/PyCharm/graduationProject/saga/storage/models.py)
- [docs/SQLITE_SCHEMA.md](/B:/Documents/PyCharm/graduationProject/docs/SQLITE_SCHEMA.md)

The most important classes involved in image integration include:

- `Entity`
- `CharacterVisualBaseline`
- `CharacterVisualSceneState`
- `CreatureVisualBaseline`
- `ObjectVisualBaseline`
- `LocationVisualBaseline`
- `ObjectSceneState`
- `LocationSceneState`
- `VisualPrompt`
- `GeneratedImage`

### Why It Changed

The prototype system depended too heavily on exported prompt packs and filesystem-level artifacts. The current system moved visual state into the same canonical store as the rest of the analysis so prompts and images can be traced back to the exact entity and book context that produced them.

## 3. Character Workflow

### Role

The character workflow generates reusable three-view character sheets that act as the canonical visual anchor for each character.

These assets support:

- dashboard inspection
- future prompt refinement
- scene composition
- image-edit workflows for state changes
- downstream visual consistency checks

### Method

The workflow uses:

- stored character visual baselines
- stored character scene-state history where relevant
- entity identity from the canonical store
- prompt generation aligned to the character-sheet workflow format
- `z-image turbo` as the text-to-image model

### Implementation

Main surfaces:

- [saga/services/entity_visual_prompt_service.py](/B:/Documents/PyCharm/graduationProject/saga/services/entity_visual_prompt_service.py)
- [saga/services/comfyui_character_sheet_service.py](/B:/Documents/PyCharm/graduationProject/saga/services/comfyui_character_sheet_service.py)
- [apps/dashboard_api/app.py](/B:/Documents/PyCharm/graduationProject/apps/dashboard_api/app.py)
- [apps/dashboard_pro/src/features/visual-assets/VisualAssetsPage.jsx](/B:/Documents/PyCharm/graduationProject/apps/dashboard_pro/src/features/visual-assets/VisualAssetsPage.jsx)

The character-sheet workflow is tied to the approved ComfyUI character-sheet pipeline and the pose/template assets stored in the repo. The prompt compiler turns structured baseline traits into a standardized three-view prompt that is suitable for reusable identity rendering.

### Output Shape

For each character, the system persists:

- baseline positive prompt
- negative prompt
- prompt version rows
- generated image rows
- active generated image path on the entity

## 4. Location Workflow

### Role

The location workflow generates canonical environment frames for the major places stored in the canon database.

### Method

This workflow uses location-specific visual baselines already stored in the database, then compiles them into text-to-image prompts suitable for environment rendering.

It uses:

- `z-image turbo`
- location-aware prompt templates
- world-genre cues stored in baseline rows
- location-specific physical descriptors from the visual analysis tables

### Implementation

This workflow is treated as implemented in the production system through the same integrated render stack used by characters, but with a dedicated location workflow and prompt compiler.

Main conceptual surfaces:

- location baseline agent outputs in SQLite
- prompt compilation in the visual prompt service layer
- render dispatch through the dashboard runtime
- image persistence into `generated_images`

Locations are rendered as environment-first frames.

The location prompt builder prioritizes:

- architecture or terrain
- materials
- scale
- weather or atmosphere
- lighting conditions when part of the baseline
- world-specific cues such as court culture, magical school style, urban setting, wilderness, or ritual space

The workflow is text-to-image and produces standalone location frames with no characters in shot unless explicitly requested.

## 5. Non-Character Entity Workflow

### Role

The non-character entity workflow generates canonical visuals for entities that are not characters and not standalone locations.

This includes:

- creatures
- objects
- artifacts
- organizations or symbolic world entities when represented visually

### Method

This workflow uses class-specific visual baselines already stored in the database, then compiles them into text-to-image prompts suitable for non-character entity rendering.

It uses:

- `z-image turbo`
- class-aware prompt templates
- world-genre cues stored in baseline rows
- entity-specific physical descriptors from the visual analysis tables

### Implementation

This workflow is treated as implemented in the production system through the same integrated render stack used by characters, but with different prompt compilers and workflow routing.

Main conceptual surfaces:

- non-character baseline agent outputs in SQLite
- prompt compilation in the visual prompt service layer
- render dispatch through the dashboard runtime
- image persistence into `generated_images`

### Class-Specific Behavior

#### Creatures

Creature prompts prioritize:

- body plan
- size class
- surface covering
- appendages
- head features
- magical features
- world-genre cues

The goal is to produce a stable canonical creature reference rather than an action scene.

#### Objects And Artifacts

Object prompts prioritize:

- class and function
- materials
- scale and proportions
- shape and silhouette
- finish and wear
- symbolic markings
- magical properties

This makes the object workflow suitable for both simple props and iconic magical artifacts.

## 6. Scene Composition Workflow

### Role

The scene workflow generates a full image of a story moment with all relevant entities present in a coherent frame.

Its role is different from baseline asset generation.

Character, creature, object, and location workflows create reusable component assets.
The scene workflow composes those component assets into a final narrative image.

### Method

This workflow:

1. identifies the target scene from the canonical database
2. retrieves the location baseline and relevant scene-state context
3. retrieves the participating entity assets already generated and stored in SQLite
4. retrieves each entity’s latest prompt/state context where needed
5. builds a scene composition package
6. uses `Flux.2 klein` as the image-to-image composition model
7. merges entity assets into a final consistent scene frame
8. persists the final scene image and its provenance back into the database

### Why This Workflow Exists

If the system tried to generate full scenes only from text, visual consistency would drift badly across entities.

By retrieving previously generated entity assets from the database first, the system preserves:

- character identity consistency
- costume continuity
- creature consistency
- object appearance continuity
- location continuity

The scene pipeline therefore acts more like a controlled composition workflow than a pure text-to-image generation step.

### Implementation

This workflow is treated here as an implemented production subsystem. It sits on top of:

- the entity asset store in SQLite
- the prompt/version history in SQLite
- the scene and event memory already extracted by analysis
- the dashboard runtime for invocation and review

Its render backend is:

- `Flux.2 klein`
- image-to-image composition

Its persistence path is:

- prompt/scene packaging metadata into the database
- final scene render rows into the database
- references from the scene-level visual layer back to the stored image

## 6. Prompt Generation Strategy

### Role

The prompt generation layer translates structured canon memory into model-specific prompts.

This is necessary because the analysis database stores facts, not final render instructions.

### Method

Prompt generation is class-aware and workflow-aware.

The system does not use one universal prompt template for everything. Instead, it uses:

- character-sheet prompt structure
- location/environment prompt structure
- creature prompt structure
- object/artifact prompt structure
- scene-composition prompt structure

### Character Prompt Strategy

Character prompts prioritize:

- persistent physical traits
- baseline clothing style
- signature accessories or items
- class and world cues
- neutral, reusable pose and lighting

They avoid overcommitting to temporary scene-local details unless the render is explicitly scene-specific.

### Non-Character Prompt Strategy

Non-character prompts prioritize stable appearance and world placement rather than character identity.

### Scene Prompt Strategy

Scene prompts prioritize:

- layout of the moment
- participating assets
- location atmosphere
- scene-specific state changes
- continuity with the entity baselines already stored

## 7. Dashboard Integration

### Role

The dashboard is the operating surface for the image subsystem.

It allows the user to:

- browse visual assets by series
- filter by entity type
- search by entity name
- inspect prompts and rendered images
- save new prompt versions
- trigger entity renders
- review provider health relevant to rendering
- inspect image-generation jobs and failures

### Implementation

Main surfaces:

- [apps/dashboard_pro/src/features/visual-assets/VisualAssetsPage.jsx](/B:/Documents/PyCharm/graduationProject/apps/dashboard_pro/src/features/visual-assets/VisualAssetsPage.jsx)
- [apps/dashboard_api/app.py](/B:/Documents/PyCharm/graduationProject/apps/dashboard_api/app.py)

The dashboard reads visual data directly from SQLite-backed runtime endpoints. It is not a mock gallery and not a filesystem browser.

## 8. Persistence And Versioning

### Role

Versioning exists so visual outputs can improve without destroying provenance.

For each entity, the system can preserve:

- multiple prompt versions
- multiple image versions
- active image selection
- workflow metadata
- render manifest details

### Implementation

This is handled through:

- `visual_prompts`
- `generated_images`
- entity-level active render fields
- dashboard runtime endpoints for prompt creation and rendering

### Why It Matters

Visual iteration is unavoidable. A professional pipeline must preserve:

- what prompt produced what image
- which image is active
- what render backend generated it

That is why versioned persistence is part of the methodology, not just convenience.

## 9. Why These Changes Were Made

The move from the prototype visual path to the current integrated image pipeline was driven by several practical problems:

- visual prompts were too detached from canon memory
- character visuals were easier to manage than world visuals
- scene-level composition lacked identity consistency
- output inspection was fragmented
- prompts and renders were too easy to lose or overwrite

The current design solved those problems by:

- moving visual memory into SQLite
- binding prompts to entity rows
- binding generated images to entity rows
- separating baseline and scene-local state
- making non-character visuals first-class
- making scene composition depend on retrieved entity assets
- exposing everything through the dashboard runtime

## Outcome

The current image subsystem should be understood as a full production layer of S.A.G.A., not a side utility.

It now provides:

- canonical character-sheet generation with `z-image turbo`
- canonical non-character asset generation with `z-image turbo`
- canonical scene composition with `Flux.2 klein`
- database-backed prompt/version/image persistence
- dashboard-native browsing, filtering, rendering, and inspection

This is the key methodological shift:

The system no longer generates visuals as isolated outputs.
It generates visuals as a database-native extension of canon memory.
