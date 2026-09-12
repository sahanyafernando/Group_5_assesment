# Muthuwella Works Dispatch

Decision-support dashboard for Muthuwella Municipal Council's Public Works coordinator.

The application turns messy daily resident reports into a smaller set of actionable incidents, ranks them transparently, recommends the correct specialist crew, and lets the coordinator confirm or override the recommendation.

## Stack

- **Frontend:** React + TypeScript + Vite
- **Backend:** FastAPI + Python
- **Database:** Supabase Postgres
- **AI:** Claude API through the FastAPI backend only
- **Data:** `reports.csv`, `assets.csv`, `jobs-history.csv`

## Core design rule

> Claude understands messy resident language. Deterministic application rules make priority and crew decisions. Maya retains final authority.

## Architecture

```text
reports.csv
    |
    v
FastAPI ingestion / normalization
    |
    +--> Claude: classification, hazards, location hints
    |
    v
assets.csv canonical location matching
    |
    v
candidate duplicate grouping
    |
    +--> Claude: semantic duplicate verification
    |
    v
consolidated incidents
    |
    +--> Claude: actionable incident summary
    |
    +--> jobs-history.csv recent-work check
    |
    v
deterministic priority engine
    |
    v
deterministic crew mapping
    |
    v
Supabase Postgres
    |
    v
FastAPI REST API
    |
    v
React dashboard / dispatch view
```

## Crew mapping

| Work type | Crew |
|---|---|
| Pothole | Road Surface |
| Road surface damage | Road Surface |
| Pavement damage | Road Surface |
| Kerb | Road Surface |
| Road marking | Road Surface |
| Blocked drain | Drainage |
| Gully | Drainage |
| Culvert | Drainage |
| Manhole | Drainage |
| Drainage flooding | Drainage |
| Streetlight | Lighting & Street Furniture |
| Sign post | Lighting & Street Furniture |
| Bus shelter | Lighting & Street Furniture |
| Bench | Lighting & Street Furniture |
| Unsupported / unknown | Manual Review |

## What is already included

- React dashboard starter UI
- Summary cards
- Ranked incident table
- Dispatch view grouped by crew
- Search/filter controls
- FastAPI REST API
- Supabase client wrapper
- Supabase SQL schema
- CSV import script for all three supplied datasets
- Claude report-analysis service
- Deterministic crew service
- Deterministic priority service
- Demo mode so the UI works before credentials are configured
- Unit tests for crew and priority rules
- `REQUIREMENTS.md`
- `SETUP.md`
- `CLAUDE.md`
- Hackathon `SCOPING.md` and `DECISIONS.md` starters

## Quick start

For the full setup, read **[SETUP.md](SETUP.md)**.

### Terminal 1 — Backend

Windows PowerShell:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload --port 8000
```

Backend:
- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

### Terminal 2 — Frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Frontend: `http://localhost:5173`

The starter defaults to `DEMO_MODE=true`, so the dashboard works without Supabase.

## Next recommended implementation order

1. Configure Supabase and run `supabase/schema.sql`.
2. Import the supplied CSVs.
3. Set `DEMO_MODE=false`.
4. Confirm raw data endpoints/database contents.
5. Implement canonical location matching.
6. Run Claude report classification only where useful.
7. Build candidate duplicate groups.
8. Use Claude for semantic duplicate verification.
9. Create incidents.
10. Apply deterministic priority and crew mapping.
11. Add manual overrides and assignments.
12. Polish the dashboard and demo flow.

Read `CLAUDE.md` before asking Claude Code to modify the repository.
