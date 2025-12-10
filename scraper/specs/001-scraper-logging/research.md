# Research Notes: Scraper Logging Recovery

## Decision Log

### 1. Structured Logging Stack
- **Decision**: Adopt Python `structlog` layered over the built-in `logging` module to emit JSON objects aligned with FR-001 keys.
- **Rationale**: `structlog` simplifies key/value enrichment, preserves compatibility with existing handlers, and supports both synchronous scrapes and background jobs without major refactors.
- **Alternatives Considered**:
  - Pure `logging` with custom JSON formatter – higher maintenance cost for context injection.
  - OpenTelemetry logger – adds external dependency footprint not yet standardized across the project.

### 2. Diagnostic Artifact Storage & Retention
- **Decision**: Store artifacts (HTML, screenshots, serialized state) locally under `artifacts/<correlation_id>/` with optional S3 sync, enforcing 14-day retention via nightly cleanup.
- **Rationale**: Local storage ensures artifacts survive transient network outages; retention limit satisfies governance and disk constraints outlined in plan constraints.
- **Alternatives Considered**:
  - Immediate cloud-only storage – brittle when incident occurs during outbound outage.
  - Unlimited retention – conflicts with disk quota and data governance obligations.

### 3. Sensitive Data Redaction Strategy
- **Decision**: Implement redaction filters that mask tokens, session IDs, and user-provided secrets before logs leave the process, leveraging regex-based scrubbing plus allow-listed metadata fields.
- **Rationale**: Upholds constitution logging principle (no sensitive data) while preserving actionable context for on-call engineers.
- **Alternatives Considered**:
  - Post-processing redaction – risk of sensitive data briefly landing in log buffer.
  - Manual developer discipline – unreliable and violates governance requirements.

### 4. Log Shipping Integration Pattern
- **Decision**: Expose logs via standard stdout/stderr for container deployments while providing optional FileHandler integration with rotation at 250MB, delegating shipping to existing Fluent Bit agents.
- **Rationale**: Aligns with current deployment pipeline, avoids reinventing shipping layer, and satisfies rotation/retention constraints without blocking local debugging.
- **Alternatives Considered**:
  - Custom TCP log forwarder – adds operational overhead.
  - Direct cloud logging SDK – couples scraper to vendor-specific APIs not yet mandated.
