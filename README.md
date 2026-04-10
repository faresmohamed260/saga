# S.A.G.A.

Story Analysis, Generation, and Archives

![S.A.G.A. Logo](docs/assets/saga-logo.svg)

Production-oriented narrative intelligence system for extracting structured story knowledge from EPUB and PDF books, preserving canon, and preparing grounded inputs for future pre-canon, mid-canon, post-canon, and fanfiction authoring workflows.

The project ingests one or more books, splits them into scenes, analyzes each scene with LLM-backed extractors, and builds reusable narrative outputs such as:

- chapter rows
- scene analyses
- entity registry
- state transitions
- canon snapshots
- timeline events
- character timelines
- alias and identity decisions
- causal graph and metrics
- searchable story index

The main product surface is the Streamlit dashboard in [story_dashboard.py](/B:/Documents/PyCharm/graduationProject/story_dashboard.py).

## Main Features

- Unified series ingestion through EPUB and PDF processors
- Configurable scene sizing, including entire-chapter mode
- Parallel scene analysis and identity analysis
- Incremental alias-map updates during processing
- Deterministic downstream rebuilding after each scene
- JSON contract export from the dashboard
- Search across scenes, timeline, state, identities, and causal graph outputs

## Project Structure

- [story_dashboard.py](/B:/Documents/PyCharm/graduationProject/story_dashboard.py)
  Main Streamlit application.
- [services](/B:/Documents/PyCharm/graduationProject/services)
  Book ingestion and chapter extraction.
- [analysis](/B:/Documents/PyCharm/graduationProject/analysis)
  Scene splitting and per-scene LLM analysis.
- [entities](/B:/Documents/PyCharm/graduationProject/entities)
  Entity registry building.
- [state](/B:/Documents/PyCharm/graduationProject/state)
  State transitions and canon snapshots.
- [timeline](/B:/Documents/PyCharm/graduationProject/timeline)
  Timeline, character timeline, normalization, and causal graph services.
- [rag](/B:/Documents/PyCharm/graduationProject/rag)
  Searchable indexing services.
- [query](/B:/Documents/PyCharm/graduationProject/query)
  Story search/query services.
- [docs](/B:/Documents/PyCharm/graduationProject/docs)
  Project documentation.

## Running The Dashboard

From the project root:

```powershell
streamlit run story_dashboard.py
```

## Installation

Create a virtual environment, activate it, and install the project in editable mode:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -e .[dev]
```

## Dashboard Workflow

1. Upload one or more books, or use the default sample.
2. Choose:
   - scene analysis model
   - identity model
   - scene size
3. Click `Run Pipeline`.
4. Review outputs in the dashboard tabs.
5. Export the pipeline result using `Export JSON Contract`.

## JSON Export

The dashboard can export a full JSON contract containing:

- run metadata
- inputs
- chapters
- scene analyses
- resolved scene analyses
- entity registry
- state result
- canon snapshot
- timeline
- character timelines
- identity result
- causal graph result
- story index summary

See [docs/JSON_CONTRACT.md](/B:/Documents/PyCharm/graduationProject/docs/JSON_CONTRACT.md) for the contract description.

## Testing

The maintained regression coverage lives in [tests](/B:/Documents/PyCharm/graduationProject/tests).

Run the full suite:

```powershell
pytest tests
```

Run a single test module:

```powershell
pytest tests/test_scene_analyzer.py
```

## Documentation

- [docs/ARCHITECTURE.md](/B:/Documents/PyCharm/graduationProject/docs/ARCHITECTURE.md)
- [docs/JSON_CONTRACT.md](/B:/Documents/PyCharm/graduationProject/docs/JSON_CONTRACT.md)
- [docs/DASHBOARD.md](/B:/Documents/PyCharm/graduationProject/docs/DASHBOARD.md)
- [docs/TESTING.md](/B:/Documents/PyCharm/graduationProject/docs/TESTING.md)
