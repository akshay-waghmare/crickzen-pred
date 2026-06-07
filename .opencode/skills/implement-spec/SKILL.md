---
name: implement-spec
description: Use ONLY when the user says "implement this spec" or "implement specs 0XX" for this project. Automates the spec-kit implementation workflow: find spec/plan/tasks, study existing code patterns, build in phases (service → context → routes → templates → tests), and run tests with the project-specific commands. Do not use for code review, bug fixes, or unrelated tasks.
---

# Implement Spec

Workflow for implementing feature specs from `specs/{NNN}-{name}/` in this CrickenZen dashboard + ML pipeline project.

## Project layout

| Area | Path | Test command |
|------|------|-------------|
| ML pipeline | `src/bbl_pipeline/` | `pytest tests/unit/analysis/test_*.py -q` (no PYTHONPATH needed — `tests/conftest.py` adds root) |
| Dashboard app | `dashboard/app/` | `$env:PYTHONPATH = "dashboard"; pytest dashboard/tests/test_*.py -v --noconftest` |
| Dashboard templates | `dashboard/templates/` | Jinja2 with Tailwind CSS + Alpine.js + htmx |
| Dashboard routes | `dashboard/app/routers/pages.py` | FastAPI HTMLResponse routes |
| Snapshot scripts | `scripts/` | `python scripts/build_*.py --league ipl --window all_available` |

Dashboard router patterns:
- Routes import from `app.*` not `dashboard.app.*`
- Templates use `dashboard/templates/base.html` as parent
- Visual language: `bg-slate-950`, `border-slate-800`, `bg-slate-900`, `text-emerald-300`, `text-slate-400`, `rounded-2xl`, `font-black`, `tracking-tight`
- Status colors: emerald = ready, amber = stale/upcoming, slate = not-ready

## Implementation workflow

### Phase 0: Discovery
1. Use the explore agent to find all files matching `specs/{NNN}*/**`
2. Read `spec.md`, `plan.md`, `tasks.md` in full
3. Read existing code referenced in the spec's Dependencies section for patterns

### Phase 1: Service/serializer module
- Create the data contract module first (`dashboard/app/{name}.py`)
- Use dataclasses for structured payloads
- Keep independent of `app.config` (no pydantic_settings dependency) — inline small utilities instead of importing from `app.public`
- If the module imports from `app.public`, break that dependency: copy needed helper functions (e.g. `_slugify`, `_match_title`) as private functions in the new module

### Phase 2: Page context builder
- Create `dashboard/app/{name}_page.py` with a `build_*_context()` function
- Normalize raw data into template-safe objects
- Derive status (ready/stale/partial/not-ready) here, not in templates

### Phase 3: Routes
- Add routes to `dashboard/app/routers/pages.py`
- Pattern: `@router.get("/route-name", response_class=HTMLResponse)`
- Include SEO metadata (title, description, canonical) in every route

### Phase 4: Templates
- Create templates extending `dashboard/templates/base.html`
- Use project's dark theme classes consistently
- Handle all states: ready, partial, stale, not-ready, empty
- Include CTAs linking to related surfaces

### Phase 5: Tests
- Create `dashboard/tests/test_{name}.py` for serializer/contract tests
- Create `dashboard/tests/test_{name}_page.py` for context/template rendering tests
- Template tests: use `jinja2.Environment(loader=FileSystemLoader(template_dir))` directly, not FastAPI TestClient
- CTA tests: read template HTML files with `Path.read_text()` and assert `href="/target-route"` presence

### Phase 6: Regression
- Run dashboard tests: `$env:PYTHONPATH = "dashboard"; pytest dashboard/tests/test_{name}.py dashboard/tests/test_{name}_page.py -v --noconftest`
- Run pipeline tests: `pytest tests/unit/analysis/test_*.py -q`
- Verify imports: `python -c "from dashboard.app.{name} import ..."`

## Anti-patterns to avoid

- Do NOT import from `app.public` in new service modules — it pulls in `app.config` → `pydantic_settings`. Inline small utilities.
- Do NOT use FastAPI TestClient in dashboard tests — it needs sqlalchemy which may not be installed. Use Jinja2 directly.
- Do NOT hardcode IPL-only labels in generic helpers. Default to IPL is fine in routes.
- Do NOT put route logic in templates — derive status in the context builder.
- Do NOT fabricate metric values when data is missing — use honest `not_ready` states.
- Keep probability and accuracy as separate metric families in proof contexts.
