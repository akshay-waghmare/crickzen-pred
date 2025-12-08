# Feature Specification: Initial Data Ingestion & Processing Pipeline (BBL)

**Feature Branch**: `001-bbl-data-pipeline`
**Created**: 2025-12-09
**Status**: Draft
**Input**: User description: "Implement the initial data ingestion and processing pipeline for the Big Bash League (BBL) model. The system must ingest Cricsheet data (YAML) from the bbl_male_json_dataset folder. It must implement a modular pipeline architecture (ingestion -> cleaning -> feature engineering). It must include an entity resolution layer to normalize player, team, and venue names to a canonical format. It must be designed for rapid retraining and support versioning of data and models. The output should be a clean, validated dataset ready for model training, with a focus on ensuring data integrity and consistency as per the Constitution."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ingest Historical BBL Data (Priority: P1)

As a Data Scientist, I want to ingest the entire history of BBL matches from Cricsheet **JSON** files so that I have a comprehensive dataset for model training.

**Why this priority**: This is the foundation of the entire project. Without data, no modeling can occur.

**Independent Test**: Can be tested by running the ingestion command on the `bbl_male_json_dataset` folder and verifying that the output file (e.g., `bbl_matches.parquet`) contains the expected number of matches and rows.

**Acceptance Scenarios**:

1. **Given** the `bbl_male_json_dataset` folder contains valid **JSON** files, **When** the ingestion pipeline is run, **Then** a structured dataset (Parquet) is created containing all match data.
2. **Given** the dataset contains some corrupted or non-standard files, **When** the ingestion pipeline is run, **Then** the valid files are processed, invalid ones are skipped, **and a summary report (matches ingested, skipped, errors) is generated**.
3. **Given** the pipeline has already run, **When** it is run again with no new data, **Then** it should detect that no processing is needed (or run very quickly).

---

### User Story 2 - Normalize Entity Names (Priority: P1)

As a System, I want to normalize player, team, and venue names to a canonical format so that the model treats "Maxwell, G" and "Glenn Maxwell" as the same entity, ensuring data consistency.

**Why this priority**: Critical for model accuracy and "Data Integrity & Entity Consistency" constitution principle.

**Independent Test**: Create a test dataset with known name variations. Run the entity resolution module. Verify that all variations map to the single canonical ID/name.

**Acceptance Scenarios**:

1. **Given** a match record with venue "The Gabba", **When** processed, **Then** the venue is mapped to the canonical ID for "Brisbane Cricket Ground, Woolloongabba".
2. **Given** a player name "G. Maxwell" in one file and "Glenn Maxwell" in another, **When** processed, **Then** both are mapped to the same unique player ID.
3. **Given** a completely new/unknown player, **When** processed, **Then** the system **attempts fuzzy matching against known entities; if ambiguous, it logs for manual review; otherwise, it assigns a provisional ID**.

---

### User Story 3 - Rapid Retraining Workflow (Priority: P2)

As a Data Scientist, I want to easily update the dataset with new match files and retrain the pipeline so that the model stays current with the latest tournament trends.

**Why this priority**: Mandated by "Pipeline-Driven Architecture & Rapid Retraining" constitution principle.

**Independent Test**: Add a dummy "new match" file to the dataset. Run the update command. Verify that the new match appears in the processed dataset within a reasonable time.

**Acceptance Scenarios**:

1. **Given** a new **JSON** file is added to `bbl_male_json_dataset`, **When** the pipeline update command is executed, **Then** the new data is incrementally added to the processed dataset.
2. **Given** the pipeline is triggered, **When** it completes, **Then** a versioned artifact of the dataset is produced.

---

## Clarifications

### Session 2025-12-09
- Q: What should be the canonical identifier for entities (players, teams, venues)? → A: **Cricsheet IDs**: Use Cricsheet's registry IDs as the primary key; generate provisional IDs only for missing entities.
- Q: What is the preferred output format for the processed dataset? → A: **Parquet**: High performance, compression, schema enforcement. Best for ML training.
- Q: What is the validation strategy for ingested data? → A: **Strict Schema (Pydantic/Pandera)**: Define explicit types and constraints. Fail fast on invalid data. Best for robustness.
- Q: How should Super Over data be handled? → A: **Exclude from Main Stats**: Parse and store separately to preserve the integrity of main match averages.
- Q: How should the output dataset be structured? → A: **Partition by Season**: Organize data into season-based folders (e.g., `season=2023`) for efficient querying and updates.

## Functional Requirements

### Ingestion Module
*   **REQ-1**: The system MUST parse Cricsheet **JSON** files (version 0.9 or later).
*   **REQ-2**: The system MUST extract ball-by-ball data, match metadata (dates, teams, venue), and player registries.
*   **REQ-3**: The system MUST support bulk ingestion from a local directory path.
*   **REQ-12**: The system MUST generate a detailed ingestion summary report including count of matches, errors, duplicates, **processing time, and error rates** to monitor pipeline health.

### Entity Resolution Layer
*   **REQ-4**: The system MUST use a configuration-based mapping layer (e.g., `entity_map.yaml` or JSON) to resolve names.
*   **REQ-5**: The system MUST normalize Player Names, Team Names, and Venue Names.
*   **REQ-6**: The mapping layer MUST be extensible (allow adding new mappings without code changes).
*   **REQ-13**: The system MUST implement a fallback mechanism (e.g., fuzzy matching) for unknown entities before assigning new IDs.
*   **REQ-15**: The system MUST use **Cricsheet Registry IDs** as the primary canonical identifier for all entities.

### Data Processing & Validation
*   **REQ-7**: The system MUST enforce a **strict schema** (using tools like Pydantic or Pandera) for all ingested data, rejecting records that do not match defined types and constraints.
*   **REQ-8**: The system MUST handle missing values according to a **configurable** strategy (e.g., drop rows, fill default, flag).
*   **REQ-18**: The system MUST implement a **configurable error-handling policy** (e.g., skip file, skip record, flag for review) for invalid data, ensuring salvageable data is not lost unnecessarily.
*   **REQ-9**: The output format MUST be a column-oriented binary format (**Parquet**) for performance.
*   **REQ-17**: The output dataset MUST be **partitioned by Season** (e.g., hive-style partitioning) to optimize time-based querying and incremental updates.
*   **REQ-19**: The system MUST implement file compaction or sizing rules for Parquet partitions to avoid the "small file problem" and optimize I/O.
*   **REQ-14**: The output dataset MUST include provenance metadata (source files, ingestion timestamp, mapping version, **schema version**).
*   **REQ-16**: The system MUST separate Super Over data from main match data, ensuring it does not affect standard player averages.

### Pipeline Architecture
*   **REQ-10**: The pipeline MUST be modular, with distinct steps for Ingestion, Resolution, and Validation.
*   **REQ-11**: The pipeline MUST be executable via a single standard CLI command.
*   **REQ-20**: The system MUST support **incremental ingestion**, processing only new or modified JSON files (based on hash/timestamp) to avoid full re-processing.
*   **REQ-21**: The pipeline MUST include a comprehensive suite of **automated unit and integration tests** covering schema validation, entity normalization, and edge cases.

## Success Criteria

*   **Completeness**: 100% of valid matches in `bbl_male_json_dataset` are present in the output dataset.
*   **Consistency**: Zero duplicate entities found in the processed dataset (verified by unique constraints on canonical IDs).
*   **Performance**: Full ingestion and processing of the current BBL history takes less than 5 minutes on a standard developer machine.
*   **Usability**: A new match can be ingested and ready for training with a single command.

## Assumptions

*   The `bbl_male_json_dataset` contains standard Cricsheet **JSON** files.
*   We will use **Pandas** for data manipulation and **Parquet** for storage.
*   We will use a simple YAML/JSON file for the initial entity mapping registry.
*   The "canonical" names will be based on Cricsheet's own registry or a manual master list we create.
