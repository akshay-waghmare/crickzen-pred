<!--
SYNC IMPACT REPORT
Version: 1.2.0 -> 1.3.0
Modified Principles:
- Refined PRINCIPLE_1 to explicitly mention robust handling of edge cases (rain, DLS, etc.).
- Refined PRINCIPLE_2 to include drift-based retraining triggers.
- Refined PRINCIPLE_5 to mandate separate calibration sets, uncertainty quantification, and live monitoring.
Added Sections: None
Removed Sections: None
Templates requiring updates: None
Follow-up TODOs: None
-->

# Big Bash Model Constitution

## Core Principles

### I. Scalability & Reusability
The architecture MUST be tournament-agnostic. While the initial focus is the Big Bash League (BBL), the codebase MUST be structured so that adding a new tournament (e.g., IPL) requires configuration changes rather than code rewrites. Hardcoding of tournament-specific logic should be minimized and isolated in configuration files or specific adapters. **The architecture MUST robustly handle edge cases (e.g., rain-outs, DLS method, super overs) through configurable business logic rather than ad-hoc fixes.**

### II. Pipeline-Driven Architecture & Rapid Retraining
All data processing and modeling steps MUST be implemented as modular pipelines using state-of-the-art libraries (e.g., scikit-learn pipelines, Kedro, or similar). Each stage (ingestion, cleaning, feature engineering, training, evaluation) MUST be a distinct, composable unit. **Crucially, the pipeline MUST be designed for rapid iteration. It MUST be possible to ingest new data (e.g., recent matches) and retrain the model with a single command. The system MUST support a "continuous learning" workflow where models are updated frequently (e.g., every few matches) OR triggered by automated detection of data drift or performance degradation.**

### III. Reproducibility & Versioning
All experiments, data versions, and model artifacts MUST be versioned. Training runs MUST be reproducible. We SHOULD use tools (like DVC, MLflow, or similar) to track data lineage and model parameters. A model result is only valid if it can be reproduced from the source code and versioned data.

### IV. Data Integrity & Entity Consistency
Data quality is paramount. Input data MUST be validated against strict schemas before entering the pipeline. **Crucially, all categorical entity identifiers (including but not limited to player names, team names, and venue names) MUST be normalized to a canonical format using a shared mapping layer. This ensures consistency between historical training data (e.g., Cricsheet) and live inference data (e.g., scraped feeds).** Feature engineering steps MUST include checks for outliers, missing values, and data drift. "Garbage in, garbage out" is a critical risk that must be mitigated through automated validation gates.

### V. Model Calibration & Observability
The system MUST provide comprehensive observability into model performance. **The supreme metric for model quality is PROBABILISTIC CALIBRATION. If the model predicts an event with 70% probability, it MUST occur approximately 70% of the time (e.g., 69-71%).**
*   **Strict Separation**: Calibration metrics MUST be calculated on a held-out evaluation set distinct from the set used to train or calibrate the model.
*   **Uncertainty Quantification**: The system SHOULD support uncertainty-aware models (e.g., ensembles, Bayesian methods) to provide robust probability distributions.
*   **Live Monitoring**: In production, all predictions MUST be logged against actual outcomes to track calibration drift and "model health" in real-time.

## Technical Constraints

### Technology Stack
- **Language**: Python (latest stable version recommended).
- **Core Libraries**: Scikit-learn, Pandas, NumPy (State-of-the-art versions).
- **Pipeline Orchestration**: Modular pipeline framework (e.g., Scikit-learn Pipeline, Kedro, or custom equivalent).
- **Containerization**: Docker for consistent environments across development and production.

### Code Quality
- All code MUST be typed (Python type hints).
- Unit tests are required for all utility functions and pipeline components.
- Documentation MUST explain the "why" and "how" of feature engineering decisions.

## Development Workflow

### Feature Development
1.  **Spec**: Define the feature or model improvement in a spec file.
2.  **Plan**: Create an implementation plan identifying necessary pipeline changes.
3.  **Implement**: Write code with tests.
4.  **Evaluate**: Run the pipeline and compare metrics against the baseline.

### Review Process
- Code reviews MUST verify that changes do not break the "tournament-agnostic" principle.
- Changes to the pipeline structure require a detailed impact analysis.

## Governance

### Amendments
This constitution is the supreme law of the project. Amendments require a Pull Request with a clear rationale and must be approved by the project owner.

### Versioning Policy
- **MAJOR**: Fundamental change to core principles (e.g., moving away from pipelines).
- **MINOR**: Adding a new principle or significant constraint.
- **PATCH**: Clarifications or wording changes.

### Compliance
All Pull Requests MUST be checked against these principles. Non-compliant code (e.g., hardcoded tournament logic, monolithic scripts) MUST be rejected.

**Version**: 1.3.0 | **Ratified**: 2025-12-09 | **Last Amended**: 2025-12-09
