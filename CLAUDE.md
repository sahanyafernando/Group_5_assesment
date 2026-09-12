# CLAUDE.md — Instructions for Claude Code

## Read this first

This repository is a hackathon project for **Muthuwella Municipal Council Works Dispatch**.

Before changing code, read:

1. `README.md`
2. `REQUIREMENTS.md`
3. `SETUP.md`
4. `supabase/schema.sql`

Do not redesign the product unless explicitly asked.

---

# 1. Goal

Build a decision-support dashboard that converts messy resident reports into actionable incidents.

The coordinator must quickly see:

- distinct underlying incidents
- why each incident is important
- which specialist crew matches the work
- what needs manual review
- what is assigned/completed

The coordinator remains the final decision maker.

---

# 2. Fixed stack

Do not replace these technologies unless explicitly requested:

```text
Frontend: React + TypeScript + Vite
Backend: FastAPI + Python
Database: Supabase Postgres
AI: Anthropic Claude API
```

Do not introduce Docker unless specifically asked.

Do not introduce LangChain/LangGraph unless a concrete requirement makes it necessary.

This application does not need a vector database for the MVP.

---

# 3. Repository boundaries

```text
frontend/          React application
backend/           FastAPI application
supabase/          database schema
data/source/       immutable supplied CSV copies
```

Raw source CSV files must never be modified.

---

# 4. Security rules

NEVER expose:

```text
ANTHROPIC_API_KEY
SUPABASE_KEY
```

to React.

Secrets belong only in:

```text
backend/.env
```

The browser calls FastAPI.

FastAPI calls Supabase and Claude.

Never commit `.env`.

Never print full secrets in logs.

---

# 5. AI boundary

Claude is a language-understanding component.

## Claude MAY

- classify work type from resident descriptions
- extract hazards/impact
- extract road/landmark hints
- identify ambiguity
- verify semantic duplicate candidates
- summarize grouped reports

## Claude MUST NOT

- calculate the final priority score
- choose the final crew directly
- claim an asset exists without `assets.csv`
- decide that a historical job definitely resolves a new report
- autonomously dispatch crews
- overwrite a manual coordinator decision

Use deterministic code for operational decisions.

Principle:

> AI understands messy language. Rules make operational decisions. Humans retain authority.

---

# 6. Allowed work types

Claude work-type output must be one of:

```text
Pothole
Road surface damage
Pavement damage
Kerb
Road marking
Blocked drain
Gully
Culvert
Manhole
Drainage flooding
Streetlight
Sign post
Bus shelter
Bench
Unsupported
```

Unknown values must become `Unsupported` or fail schema validation and go to manual review.

---

# 7. Fixed crew mapping

The final crew recommendation is made ONLY by `crew_service.py`.

```python
CREW_MAP = {
    "Pothole": "Road Surface",
    "Road surface damage": "Road Surface",
    "Pavement damage": "Road Surface",
    "Kerb": "Road Surface",
    "Road marking": "Road Surface",

    "Blocked drain": "Drainage",
    "Gully": "Drainage",
    "Culvert": "Drainage",
    "Manhole": "Drainage",
    "Drainage flooding": "Drainage",

    "Streetlight": "Lighting & Street Furniture",
    "Sign post": "Lighting & Street Furniture",
    "Bus shelter": "Lighting & Street Furniture",
    "Bench": "Lighting & Street Furniture",
}
```

Everything else:

```text
Manual Review
```

Do not silently extend this mapping.

---

# 8. Priority rule

The final score is deterministic.

Keep priority logic inside:

```text
backend/app/services/priority_service.py
```

Factors:

```text
Safety / severity        0-35
Road/public impact       0-20
Critical facility       0-15
Age/persistence         0-15
Multiple reports        0-10
Resident urgency         0-5
```

Every point added must produce an explanation string.

Same input must always produce the same score.

Claude may supply extracted severity evidence but never the final number.

---

# 9. Claude API implementation rules

Use the official `anthropic` Python package.

Claude is called from FastAPI only.

Default model is configurable through:

```env
CLAUDE_MODEL=claude-haiku-4-5
```

Do not hardcode API keys.

Prefer structured JSON output and validate it with Pydantic.

If Claude:

- times out
- returns malformed JSON
- returns unsupported work type
- fails schema validation

then:

```text
needs_review = true
```

and continue processing.

Never let one AI failure crash a whole batch.

Avoid unnecessary API calls.

Before semantic duplicate calls, reduce candidates using deterministic location/work-type/time filters.

Cache/reuse analysis where possible.

---

# 10. Supabase rules

Use Supabase as persistent Postgres storage.

Primary tables:

```text
raw_reports
assets
jobs_history
incidents
incident_reports
assignments
overrides
```

Do not use `source_report_id` as a unique database ID because the supplied data contains duplicate report IDs.

Preserve:

```text
source_file
source_row_number
raw_payload
```

for traceability.

RLS is enabled. The backend uses a server-side Supabase secret/service credential.

Do not create broad public write policies unless explicitly required.

---

# 11. React rules

Keep the UI optimized for Maya's one-hour morning dispatch workflow.

Prioritize:

1. ranked incidents
2. clear priority reasons
3. recommended crew
4. warnings / needs review
5. fast assignment/override actions

Do not turn the UI into a generic admin dashboard.

Use reusable components.

Keep TypeScript types aligned with FastAPI response schemas.

Do not access Supabase admin credentials from React.

Frontend API base URL comes from:

```env
VITE_API_BASE_URL
```

---

# 12. Backend structure

Keep responsibilities separate:

```text
app/
  core/
  db/
  routers/
  schemas/
  services/
```

Important separation:

```text
claude_service.py
    language understanding

crew_service.py
    deterministic crew mapping

priority_service.py
    deterministic priority calculation
```

Do not put all business logic into one LLM prompt or one route file.

---

# 13. Implementation phases

When asked to implement the project progressively, use these phases.

## Step 1 — Foundation
- verify backend starts
- verify frontend starts
- verify `/api/health`
- keep demo mode working

## Step 2 — Supabase
- apply schema
- import CSVs
- verify row counts
- expose basic raw-data queries if needed

## Step 3 — Report understanding
- Claude report analysis
- strict Pydantic schema
- failure handling
- cache/store AI output

## Step 4 — Location resolution
- exact road match
- alias match
- normalized/fuzzy match
- Claude location hints only as input
- store confidence

## Step 5 — Duplicate clustering
- deterministic candidate grouping
- semantic verification only for ambiguous candidates
- retain all report-to-incident links

## Step 6 — Incident construction
- canonical incident
- Claude summary
- asset enrichment
- job-history warning

## Step 7 — Operational rules
- deterministic priority
- deterministic crew mapping
- explanation output
- review state

## Step 8 — Workflow
- assignment
- status updates
- overrides
- audit history

## Step 9 — Frontend polish
- dashboard
- detail panel/page
- dispatch queues
- filters
- loading/error states

## Step 10 — Quality
- tests
- README updates
- DECISIONS.md
- demo preparation

If the user says "do step 4", do step 4 without unnecessarily rebuilding unrelated steps.

---

# 14. Coding rules

- Prefer simple, readable code.
- Keep functions small.
- Use type hints.
- Use Pydantic schemas at API boundaries.
- Validate LLM output before use.
- Avoid broad exception swallowing.
- Return useful HTTP errors.
- Add tests for deterministic business rules.
- Mock Claude in unit tests.
- Do not call external APIs from unit tests.
- Do not refactor unrelated files.
- Preserve runnable state after each meaningful change.

---

# 15. Tests that must exist

## Crew service

```text
Pothole -> Road Surface
Manhole -> Drainage
Streetlight -> Lighting & Street Furniture
Unsupported -> Manual Review
random unknown -> Manual Review
```

## Priority

- identical input gives identical score
- score never exceeds 100
- reasons add to the final score
- main road scores above lane for otherwise equal incident
- multiple reports increase score

## AI handling

Later add mocked tests:

- valid Claude JSON parses
- malformed JSON becomes review
- unsupported work type becomes review
- missing API key gives controlled error

## Import

Later add tests:

- duplicate source report IDs are preserved as separate raw rows
- NaN values become null
- source row number is retained

---

# 16. Git workflow

Prefer small commits, for example:

```text
chore: scaffold dashboard stack
feat: add Supabase source import
feat: add Claude report classifier
feat: add location resolver
feat: add duplicate clustering
feat: add priority and crew rules
feat: add dispatch workflow
test: cover incident business rules
docs: update demo instructions
```

Do not commit secrets.

---

# 17. Definition of done for MVP

A user can:

1. load/import today's reports
2. see consolidated incidents
3. understand why they are ranked
4. see the recommended specialist crew
5. inspect underlying reports
6. see warnings for uncertain/unsupported cases
7. assign/override a decision
8. refresh/restart and keep the state

The final demo must emphasize explainability and human control.
