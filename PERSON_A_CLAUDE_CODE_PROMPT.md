# Claude Code — Person A Instructions (AI Pipeline & Data Ingestion)

Read `CLAUDE.md` before doing anything. It is the single source of truth for this project.

## Who You Are Building For

You are Person A on a 3-person hackathon team building "Muthuwella Works Dispatch" — a web app that helps Maya (Works Coordinator) triage 240 resident reports into prioritized, crew-tagged incidents each morning.

## Your Scope — ONLY These Parts

You own the **Data Ingestion and AI Processing Pipeline**. This means:

1. CSV loading — parse all 3 source files into Supabase
2. Data normalization — clean dates, whitespace, nulls
3. Location normalization — resolve messy location text to known road names from assets
4. AI report classification — call Claude API to extract work_type, severity, hazards, category from free text
5. Duplicate detection — group reports into clusters that describe the same real-world problem
6. Incident creation — merge each cluster into one incident record
7. AI incident summarization — generate one actionable summary per incident
8. Pipeline orchestrator — chain all the above into one triggerable flow

## What You Do NOT Build

- Crew mapping (work_type → crew) — Person B owns this, deterministic rules, no AI
- Priority scoring — Person B owns this, deterministic rules, no AI
- Jobs history check — Person B owns this, DB lookup
- Asset enrichment (ward, road_class, facility) — Person B owns this
- API endpoints — Person B owns this
- Frontend / React UI — Person C owns this

After you create incidents in the database, call Person B's `enrich_incident()` function to add priority scores, crew mapping, and asset context. If Person B's enrichment function is not ready yet, just create the incidents without enrichment — Person B can run `enrich_all_incidents()` later.

## Database

Supabase (PostgreSQL) is already connected. The schema has these tables:

- `raw_reports` — where you load reports.csv rows
- `assets` — where you load assets.csv rows
- `jobs_history` — where you load jobs-history.csv rows
- `incidents` — where you write deduplicated, classified incidents
- `incident_reports` — many-to-many link (which reports belong to which incident)
- `assignments` — Person B manages this
- `overrides` — Person B manages this

Use the Supabase Python client with the service role key from environment variables:

```python
from supabase import create_client
import os

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
```

## AI Model

Use the Anthropic Claude API. Model: `claude-sonnet-4-20250514` (or whichever model the provided API key supports).

```python
from anthropic import Anthropic
import os

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
```

Always use structured JSON output. Always validate responses with Pydantic before using them. Never crash the pipeline on a bad AI response — mark the report as `needs_review = true` and continue.

## Source Data — What You're Working With

### reports.csv (240 rows)
```
Columns: report_id, channel, received_at, reporter_name, reporter_contact,
         location_text, latitude, longitude, description, category, urgency,
         photo, status
```

Key facts about this data:
- 4 channels: web_form (93), mobile_app (59), phone (55), email (33)
- Only 97 of 240 have a category filled in — the other 143 are blank
- Only 80 of 240 have an urgency value
- Only 56 of 240 have lat/lon coordinates
- 7 reports have completely empty descriptions
- Dates are inconsistent: some `2026-09-08T08:38:07`, some `08/09/2026 09:28`
- Location text is messy: "Temple Ln", "the lane behind the school", "Baeline extension", "Reid Ave", "near the temple on the main road"
- Descriptions vary from short ("kerb loose") to long paragraphs with email signatures
- 224 are status "new", 8 "triaged", 8 "open"

### assets.csv (184 rows)
```
Columns: road_name, also_known_as, road_class, ward, asset_type, asset_id,
         nearest_facility, facility_distance_m
```

Key facts:
- 60 unique road names
- 10 `also_known_as` aliases (e.g., "the road by the temple" → "Temple Lane", "r a de mel mawatha" → "Duplication Road")
- 4 road classes: residential (70), bus route (57), main road (37), lane (20)
- 4 asset types: bus shelter (48), drain (47), footpath (47), streetlight (42)
- Multiple rows per road (one per asset type)

### jobs-history.csv (90 rows)
```
Columns: job_id, completed_date, crew, work_type, road_name, notes
```

Key facts:
- 3 crews: Drainage (35), Road Surface (29), Lighting & Street Furniture (26)
- 15 distinct work types
- Date range: 2026-08-24 to 2026-09-07
- Notes are simple: "Completed.", "Closed.", "Partial, returned next day."

## Development Order — Build STEP BY STEP

Wait for me to say "next step" or "build step N" before proceeding. After each step:
1. Show me what was created/changed
2. Tell me how to test it
3. Tell me what the next step will be

---

### STEP 1 — CSV Loader Service

Create `services/csv_loader.py`.

Load all 3 CSV files into their respective Supabase tables.

**reports.csv → raw_reports table:**
- Map CSV columns to DB columns:
  - `report_id` → `source_report_id`
  - `channel` → `channel`
  - `received_at` → `received_at` (MUST normalize to ISO 8601 timestamptz — see date handling below)
  - `reporter_name` → `reporter_name`
  - `reporter_contact` → `reporter_contact`
  - `location_text` → `location_text`
  - `latitude` → `latitude` (parse to float, null if empty)
  - `longitude` → `longitude` (parse to float, null if empty)
  - `description` → `description`
  - `category` → `category` (null if empty)
  - `urgency` → `urgency` (null if empty)
  - `photo` → `photo` (null if empty)
  - `status` → `source_status`
  - Store the entire raw row as JSON in `raw_payload`
  - Set `source_row_number` from the CSV row index (1-based)
  - Set `source_file` = "reports.csv"

**Date normalization is critical.** The `received_at` field has at least two formats:
  - ISO: `2026-09-08T08:38:07`
  - DD/MM/YYYY: `08/09/2026 09:28`
  
  Parse both and convert to ISO 8601 with timezone (assume local time if no timezone given). If parsing fails, store as-is and set `needs_review = true`.

**assets.csv → assets table:**
- Direct column mapping, straightforward
- Store raw row in `raw_payload`
- Set `source_row_number` and `source_file`

**jobs-history.csv → jobs_history table:**
- Map `job_id` → `source_job_id`
- Map `completed_date` → `completed_date` (already clean YYYY-MM-DD format)
- Direct mapping for crew, work_type, road_name, notes
- Store raw row in `raw_payload`

**Important behaviors:**
- Use upsert logic based on `(source_file, source_row_number)` unique constraint — so re-running the loader doesn't create duplicates
- Strip whitespace from all text fields
- Replace empty strings with null
- Log how many rows were loaded per table
- Do NOT modify the original CSV files

**Function signatures:**
```python
def load_reports(supabase, csv_path: str) -> dict:
    """Returns {"loaded": int, "skipped": int, "errors": int}"""

def load_assets(supabase, csv_path: str) -> dict:
    """Returns {"loaded": int, "skipped": int, "errors": int}"""

def load_jobs_history(supabase, csv_path: str) -> dict:
    """Returns {"loaded": int, "skipped": int, "errors": int}"""

def load_all(supabase, data_dir: str) -> dict:
    """Loads all 3 files. Returns combined stats."""
```

---

### STEP 2 — Location Normalization Service

Create `services/location_matcher.py`.

Resolve the messy `location_text` from reports to a canonical road name from the assets table.

**Matching strategy (in order of preference):**

1. **Exact match** — location_text contains a known road name exactly (case-insensitive)
2. **Alias match** — location_text matches an `also_known_as` value from assets
3. **Abbreviation expansion** — expand common abbreviations then re-match:
   ```python
   ABBREVIATIONS = {
       "rd": "road", "rd.": "road",
       "st": "street", "st.": "street",
       "ave": "avenue", "ave.": "avenue",
       "ln": "lane", "ln.": "lane",
       "pl": "place", "pl.": "place",
       "cr": "crescent", "cr.": "crescent",
       "mw": "mawatha", "mw.": "mawatha",
       "dr": "drive", "dr.": "drive",
   }
   ```
4. **Fuzzy match** — for typos like "Belanthara" vs "Bellanthara", "Baeline" vs "Baseline". Use simple string similarity (e.g., `difflib.SequenceMatcher`). Accept only if similarity > 0.75.
5. **AI fallback** — for remaining unmatched locations, send the location text + the list of known road names to Claude and ask it to pick the best match. This handles landmark-based descriptions like "near the temple on the main road" that rules can't catch.
6. **Unresolved** — if nothing matches, set `normalized_location = null` and `needs_review = true`

**Known aliases from assets.csv (load these from the DB, don't hardcode):**
```
"the road by the temple" → "Temple Lane"
"r a de mel mawatha" → "Duplication Road"
"lester james peiris mw" → "Dickmans Road"
"the main road by the flyover" → "Thimbirigasyaya Road"
"baseline extension" → "Elvitigala Mawatha"
"sir ernest de silva mw" → "Gregorys Road"
"the road past the market" → "Polhengoda Road"
"templers rd (old church road)" → "Templers Road"
"the hospital road" → "Hospital Road"
"the lane behind the school" → "School Lane"
```

**Function signatures:**
```python
def load_known_roads(supabase) -> dict:
    """Load road names and aliases from assets table. Returns {name_lower: canonical_name, alias_lower: canonical_name}"""

def normalize_location(location_text: str, known_roads: dict) -> tuple[str | None, float]:
    """Returns (canonical_road_name, confidence). Confidence: 1.0=exact, 0.9=alias, 0.8=abbreviation, 0.7=fuzzy, 0.0=unresolved"""

async def normalize_location_ai(client, location_text: str, road_names: list[str]) -> tuple[str | None, float]:
    """AI fallback for locations that rules couldn't match. Returns (road_name, confidence)"""

def normalize_all_reports(supabase, client) -> dict:
    """Normalize locations for all reports. Updates raw_reports.normalized_location. Returns stats."""
```

**Important:**
- Try rules first (steps 1-4). Only call AI for reports that rules couldn't match (~30 of 240).
- Store the confidence in the report so downstream knows how reliable the match is.
- Update the `normalized_location` field in `raw_reports` table after matching.
- Do NOT overwrite the original `location_text` — keep raw data intact.

---

### STEP 3 — AI Report Classification Service

Create `services/ai_classifier.py`.

For each report, call Claude to extract structured information from the free text description.

**When AI is needed:**
- 143 of 240 reports have no category — AI must classify them
- Even reports WITH a category need work_type extraction (category "Roads" doesn't tell you if it's a pothole, kerb, or road surface damage)
- Severity and hazard extraction always needs AI — residents describe symptoms, not severity levels
- Reports with empty descriptions (7 total) should be marked `needs_review = true` without calling AI

**Claude prompt design:**

System prompt:
```
You are an incident triage assistant for Muthuwella Municipal Council Public Works division.

Your task is to extract and classify facts from resident reports about road, drain, lighting, and street furniture problems.

Rules:
- Choose work_type from ONLY these values: Pothole, Road surface damage, Pavement damage, Kerb, Road marking, Blocked drain, Gully, Culvert, Manhole, Drainage flooding, Streetlight, Sign post, Bus shelter, Bench, Unsupported
- Choose category from: Roads, Pavements, Drains, Street lighting, Street furniture, Trees, Waste, Other
- Choose severity from: critical, high, medium, low
- Do NOT invent facts not present in the report
- Do NOT invent locations or hazards
- If evidence is insufficient, lower confidence and set needs_review to true
- Return valid JSON only, no markdown, no explanation
```

User prompt (per report):
```
Report ID: {report_id}
Channel: {channel}
Location: {location_text}
Description: {description}
Category (if provided): {category}
Urgency (if provided): {urgency}

Extract the following as JSON:
{
  "work_type": "one of the allowed values",
  "category": "one of the allowed values",
  "severity": "critical|high|medium|low",
  "hazards": ["list of specific hazards mentioned or clearly implied"],
  "impact": ["list of impacts mentioned: road users, pedestrians, vehicles, property"],
  "location_hints": {"road_hint": "...", "landmark": "...", "house_number": "..."},
  "persistence": "any time indicators like 'for three weeks', 'since the weekend'",
  "confidence": 0.0 to 1.0,
  "needs_review": true or false
}
```

**Batch processing for efficiency:**
Do NOT call Claude once per report (240 API calls = slow + expensive). Instead, batch 5-8 reports per API call:

```
Analyze each of the following reports and return a JSON array with one result per report.

Report 1:
  ID: MR-121627
  Description: "Caller reports surface water on Havelock Road is not draining away."
  ...

Report 2:
  ID: MR-607800
  Description: ""
  ...

(up to 8 reports)

Return a JSON array: [{ report_id, work_type, category, ... }, ...]
```

This reduces API calls from 240 to ~30-35 calls.

**Response validation:**
```python
from pydantic import BaseModel, Field
from typing import Optional

class ReportAnalysis(BaseModel):
    report_id: str
    work_type: str
    category: str
    severity: str = "medium"
    hazards: list[str] = []
    impact: list[str] = []
    location_hints: dict = {}
    persistence: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    needs_review: bool = False

VALID_WORK_TYPES = [
    "Pothole", "Road surface damage", "Pavement damage", "Kerb", "Road marking",
    "Blocked drain", "Gully", "Culvert", "Manhole", "Drainage flooding",
    "Streetlight", "Sign post", "Bus shelter", "Bench", "Unsupported"
]
```

After parsing Claude's JSON response:
- Validate with the Pydantic model
- If `work_type` is not in VALID_WORK_TYPES → set to "Unsupported", `needs_review = true`
- If `confidence < 0.6` → force `needs_review = true`
- If parsing fails entirely → log the error, mark report `needs_review = true`, continue
- Store the full AI response in `raw_reports.ai_analysis` as JSONB
- Store confidence in `raw_reports.ai_confidence`

**Function signatures:**
```python
async def classify_report(client, report: dict) -> ReportAnalysis:
    """Classify a single report. Fallback for failed batch items."""

async def classify_reports_batch(client, reports: list[dict]) -> list[ReportAnalysis]:
    """Classify a batch of 5-8 reports in one API call."""

async def classify_all_reports(supabase, client) -> dict:
    """Classify all reports. Updates raw_reports.ai_analysis. Returns stats."""
```

---

### STEP 4 — Duplicate Detection / Clustering Service

Create `services/duplicate_detector.py`.

Group reports that describe the same real-world problem into clusters.

**Two-phase approach (CLAUDE.md §6, §7):**

**Phase 1 — Deterministic pre-grouping (no AI):**
Group reports by `(normalized_location, work_type)`. Reports on the same road with the same work type are CANDIDATES for being the same problem.

This reduces the comparison space massively. Instead of comparing all 240 reports against each other (28,680 pairs), you're only comparing within small groups (typically 2-6 reports per group).

Reports that are alone in their group (only report for that road+type) automatically become single-report incidents — no AI needed.

**Phase 2 — AI semantic duplicate verification (only within groups):**
For groups with 2+ reports, ask Claude whether they describe the SAME specific problem or different problems at the same location.

Example prompt for a group:
```
These reports are all about drain issues on Park Road.
Decide which reports describe the SAME specific problem.

Report MR-530299: "bad smell from drain, grating clogged outside property"
Report MR-991722: "blocked gully outside number 110"
Report MR-426517: "drain blocked, water backing up"
Report MR-131790: "floods when it rains"

Return JSON:
{
  "clusters": [
    {
      "cluster_id": "C1",
      "report_ids": ["MR-530299", "MR-991722", "MR-426517"],
      "reason": "All describe blocked drain/gully near #110, same specific location"
    },
    {
      "cluster_id": "C2",
      "report_ids": ["MR-131790"],
      "reason": "General road flooding, not tied to specific blocked drain"
    }
  ],
  "confidence": 0.85
}
```

**Important rules:**
- Do NOT do all-pairs comparison across all 240 reports
- Only use AI within pre-grouped candidates
- If AI confidence < 0.6 on a merge decision, keep reports separate (safer to have two incidents than wrongly merge)
- If a group has only 1 report, skip AI — it's automatically its own cluster
- Store `match_confidence` and `match_reason` in the `incident_reports` junction table

**Function signatures:**
```python
def pre_group_reports(reports: list[dict]) -> dict[str, list[dict]]:
    """Group by (normalized_location, work_type). Returns {group_key: [reports]}"""

async def detect_duplicates_in_group(client, group_key: str, reports: list[dict]) -> list[dict]:
    """AI duplicate detection within one group. Returns list of clusters."""

async def detect_all_duplicates(supabase, client) -> dict:
    """Run full duplicate detection. Returns {total_groups, total_clusters, ai_calls_made}"""
```

---

### STEP 5 — Incident Creation Service

Create `services/incident_builder.py`.

Convert each cluster from Step 4 into one incident record in the database.

**For each cluster:**

1. Generate a unique `incident_code` (e.g., "INC-001", "INC-002", auto-incrementing)
2. Pick the best values from the clustered reports:
   - `canonical_road` = the normalized location (should be the same for all reports in the cluster)
   - `work_type` = most common AI-classified work_type in the cluster (or the one with highest confidence)
   - `category` = most common category
   - `severity` = highest severity in the cluster (worst case wins)
   - `hazards` = union of all hazards from all reports
   - `impact` = union of all impacts
   - `report_count` = number of reports in the cluster
   - `first_reported_at` = earliest received_at in the cluster
   - `latest_reported_at` = latest received_at in the cluster
   - `classification_confidence` = average AI confidence across reports
   - `needs_review` = true if ANY report in the cluster has needs_review

3. Create a preliminary title from work_type + road:
   - e.g., "Blocked drain on Park Road"
   - This will be replaced/improved by AI summary in Step 6

4. Insert into `incidents` table
5. Insert links into `incident_reports` table with `match_confidence` and `match_reason`
6. Update each report's `incident_id` field in `raw_reports` (if the column exists, otherwise skip)

**Function signatures:**
```python
def generate_incident_code(supabase) -> str:
    """Generate next INC-NNN code."""

def build_incident_from_cluster(cluster: dict, reports: list[dict]) -> dict:
    """Merge cluster data into one incident dict ready for DB insert."""

async def create_all_incidents(supabase, clusters: list) -> dict:
    """Create all incidents from clusters. Returns {created: int, errors: int}"""
```

---

### STEP 6 — AI Incident Summarization

Create `services/ai_summarizer.py`.

For each incident, generate one actionable summary that Maya can work from without reading the source reports.

**Prompt design:**
```
You are writing a brief work summary for a municipal works coordinator.
She uses this summary to decide what to do, without reading the individual reports.

Incident: {work_type} on {canonical_road}
Number of reports: {report_count}
Time span: {first_reported_at} to {latest_reported_at}

Source reports:
1. "{description_1}"
2. "{description_2}"
3. "{description_3}"

Write:
1. A short title (under 10 words)
2. An actionable summary (2-3 sentences maximum)

The summary must:
- Describe what the problem is
- Mention the specific location details (house numbers, landmarks)
- Mention meaningful impact or hazard if reported
- Mention how long the problem has persisted if known
- NOT invent causes or details not in the reports
- NOT repeat every report individually

Return JSON:
{
  "title": "...",
  "summary": "..."
}
```

**Batch this:** Group 3-5 incidents per API call to reduce total calls.

**After getting the summary:**
- Update `incidents.title` with the AI-generated title
- Update `incidents.summary` with the AI-generated summary
- Store the prompt/response in `incidents.ai_metadata` for traceability

**Function signatures:**
```python
async def summarize_incident(client, incident: dict, reports: list[dict]) -> dict:
    """Generate title + summary for one incident. Returns {title, summary}"""

async def summarize_all_incidents(supabase, client) -> dict:
    """Summarize all incidents. Updates incidents table. Returns stats."""
```

---

### STEP 7 — Pipeline Orchestrator

Create `services/pipeline.py`.

This chains everything into one callable flow, triggered by `POST /api/pipeline/run`.

**Pipeline sequence:**
```python
async def run_full_pipeline(supabase, anthropic_client, data_dir: str) -> dict:
    """
    Full pipeline execution:
    
    1. Load CSVs → raw_reports, assets, jobs_history tables
    2. Normalize locations for all reports
    3. Classify all reports with AI
    4. Detect duplicates / cluster reports
    5. Create incidents from clusters
    6. Summarize incidents with AI
    7. Call Person B's enrichment (priority + crew + assets + history)
    8. Return pipeline stats
    """
```

**Important behaviors:**
- Log progress at each stage: "Step 1/7: Loading CSVs... done (240 reports)"
- If one step fails, log the error and continue where possible
- Track timing for each step (for DECISIONS.md and demo)
- Return a stats dict:
  ```python
  {
      "reports_loaded": 240,
      "locations_normalized": 211,
      "locations_unresolved": 29,
      "reports_classified": 233,
      "reports_needs_review": 14,
      "clusters_found": 52,
      "incidents_created": 52,
      "incidents_summarized": 52,
      "total_time_seconds": 45.2,
      "ai_calls_made": 38
  }
  ```

**Expose via Person B's API:**
Person B has a placeholder `POST /api/pipeline/run` endpoint. Wire this to call your `run_full_pipeline()`. Coordinate with Person B on how this endpoint should work (sync vs async). For a hackathon, synchronous is simpler — the frontend shows a loading spinner for 30-60 seconds.

**Function signatures:**
```python
async def run_full_pipeline(supabase, anthropic_client, data_dir: str) -> dict:
    """Run everything. Returns stats dict."""

async def run_classification_only(supabase, anthropic_client) -> dict:
    """Re-run just the AI classification step. Useful for testing."""

async def run_clustering_only(supabase, anthropic_client) -> dict:
    """Re-run just clustering. Useful for testing."""
```

---

### STEP 8 — Connect to Person B's Enrichment

After creating incidents, call Person B's enrichment service to add:
- Priority score (deterministic, from Person B's `priority_service`)
- Crew assignment (deterministic, from Person B's `crew_service`)
- Asset context (from Person B's `asset_service`)
- Jobs history warning (from Person B's `history_service`)

```python
# At the end of run_full_pipeline, after incidents are created and summarized:

from services.enrichment_pipeline import enrich_all_incidents  # Person B's code
await enrich_all_incidents(supabase)
```

If Person B's enrichment isn't ready yet, skip this step — Person B can run it independently later. Just make sure your incidents have the fields that Person B needs:
- `canonical_road` (for asset lookup and history check)
- `work_type` (for crew mapping)
- `severity` (for priority scoring)
- `hazards` (for priority scoring)
- `report_count` (for priority scoring)
- `first_reported_at` and `latest_reported_at` (for persistence scoring)

---

## AI Efficiency Rules (CLAUDE.md §11)

- Do NOT call Claude for deterministic transformations (crew mapping, priority scoring, date parsing)
- Do NOT do all-pairs duplicate comparison
- Batch reports into groups of 5-8 per API call
- Cache AI responses in the `ai_analysis` JSONB field — if you re-run the pipeline, check if a report already has an AI result before calling again
- Pre-group reports before semantic duplicate detection
- Total AI calls for 240 reports should be approximately:
  - Classification: ~30-35 calls (batches of 7-8)
  - Location fallback: ~5-10 calls (only unresolved locations)
  - Duplicate detection: ~10-15 calls (only multi-report groups)
  - Summarization: ~15-20 calls (batches of 3-5)
  - **Total: ~60-80 API calls**, NOT 240+

## Error Handling

- If Claude API returns invalid JSON → log it, mark report `needs_review = true`, continue
- If Claude API times out → retry once, then mark `needs_review = true`, continue
- If a report has no description → skip AI classification, mark `needs_review = true`
- If location can't be resolved → set `normalized_location = null`, `needs_review = true`
- NEVER crash the entire pipeline because of one bad report or one failed API call
- The pipeline must always produce SOME output, even if degraded

## Confidence Thresholds (CLAUDE.md §9)

```
>= 0.85      High confidence — accept as-is
0.60 - 0.84  Accept with warning — visible in UI but not flagged
< 0.60       Manual review — needs_review = true
```

## General Rules

- Use `async` functions for Supabase and Claude API calls
- Keep AI prompts short and deterministic
- Do NOT send database IDs or internal fields to Claude — only send report text and context
- Store all AI prompts and responses for traceability (in ai_analysis / ai_metadata JSONB fields)
- Test each step independently before chaining
- Commit after each working step with clear messages: "feat: add CSV loader", "feat: add AI classification"

## What Success Looks Like

When all 8 steps are done:
- 240 CSV rows are in `raw_reports` table
- 184 asset rows are in `assets` table
- 90 job history rows are in `jobs_history` table
- ~210+ reports have `normalized_location` filled
- All reports have `ai_analysis` with work_type, severity, hazards
- Reports are clustered into ~40-60 incidents
- Each incident has a title, summary, canonical_road, work_type, severity
- `incident_reports` links every report to its incident
- Person B's enrichment adds priority, crew, asset context, history warnings
- `POST /api/pipeline/run` triggers the entire flow and returns stats
