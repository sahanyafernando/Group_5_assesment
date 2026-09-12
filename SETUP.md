# Setup Guide

This guide assumes Windows PowerShell and VS Code.

## 1. Prerequisites

Install:

- Python **3.11+**
- Node.js compatible with Vite 8 (**20.19+ or 22.12+**)
- Git
- VS Code
- A Supabase account/project
- A Claude API key

Check:

```powershell
python --version
node --version
npm --version
git --version
```

---

# 2. Open the project

```powershell
cd D:\
cd muthuwella-works-dispatch
code .
```

Use two VS Code terminals.

---

# 3. Backend setup

## Terminal 1

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Open:

```text
backend/.env
```

Initially you can leave Supabase and Claude credentials blank because:

```env
DEMO_MODE=true
```

Run:

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

Test:

```text
http://localhost:8000/api/health
http://localhost:8000/docs
```

---

# 4. Frontend setup

## Terminal 2

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open:

```text
http://localhost:5173
```

The frontend only needs:

```env
VITE_API_BASE_URL=http://localhost:8000/api
```

Do NOT put the Claude API key or Supabase server secret in the frontend.

---

# 5. Supabase setup

Create a Supabase project.

Then open:

```text
Supabase Dashboard
→ SQL Editor
→ New query
```

Copy all SQL from:

```text
supabase/schema.sql
```

and run it.

The schema creates:

- `raw_reports`
- `assets`
- `jobs_history`
- `incidents`
- `incident_reports`
- `assignments`
- `overrides`

RLS is enabled and the starter does not create anonymous/public write policies.

---

# 6. Get Supabase credentials

In Supabase find:

```text
Project Settings / API
```

You need:

```text
Project URL
Server-side secret/service key
```

Put them ONLY in:

```text
backend/.env
```

Example:

```env
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_KEY=YOUR_SERVER_SIDE_SECRET
```

Depending on the Supabase dashboard, the server credential may be shown as a secret key or legacy service-role key.

Never place that key in:

```text
frontend/.env
```

The architecture is:

```text
React
  ↓
FastAPI
  ↓
Supabase
```

not:

```text
React → secret Supabase admin key
```

---

# 7. Claude API setup

Put your API key in:

```text
backend/.env
```

```env
ANTHROPIC_API_KEY=YOUR_KEY
CLAUDE_MODEL=claude-haiku-4-5
```

The starter uses Claude for language understanding only.

Claude may:

- classify work type
- extract hazards
- extract location hints
- identify uncertainty
- produce incident summaries
- verify semantic duplicates later

Claude must NOT decide:

- final crew
- final priority score
- final dispatch assignment

---

# 8. Import the supplied datasets to Supabase

After Supabase is configured and `schema.sql` has been run:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m scripts.import_source_data --data-dir ..\data\source
```

Expected files:

```text
data/source/reports.csv
data/source/assets.csv
data/source/jobs-history.csv
```

The importer preserves raw values and source row numbers.

Then change:

```env
DEMO_MODE=false
```

Restart FastAPI.

---

# 9. Verify Supabase data

In Supabase Table Editor, check:

```text
raw_reports
assets
jobs_history
```

Expected source dataset sizes:

```text
reports.csv       240 rows
assets.csv        184 rows
jobs-history.csv   90 rows
```

The source report ID is intentionally NOT used as the database primary key because duplicated source IDs exist in the input.

---

# 10. Run tests

From `backend`:

```powershell
pytest
```

The starter includes tests for:

- supported crew mapping
- unsupported work type handling
- deterministic priority scoring
- priority explanation consistency

---

# 11. Recommended development workflow

Create a branch:

```powershell
git checkout -b feature/incident-dashboard
```

Make small commits:

```powershell
git add .
git commit -m "chore: scaffold React FastAPI Supabase starter"
```

Then implement one feature at a time.

Suggested order:

```text
1. Supabase schema/import
2. Raw report listing
3. Location normalization
4. Claude report analysis
5. Duplicate candidate grouping
6. Semantic duplicate confirmation
7. Incident creation
8. Priority scoring
9. Crew recommendation
10. Dispatch actions
11. Manual overrides
12. UI polish/tests
```

---

# 12. Common errors

## CORS error

Make sure backend `.env` contains:

```env
CORS_ORIGINS=http://localhost:5173
```

Restart FastAPI after editing `.env`.

## Frontend says API unavailable

Check FastAPI is running:

```text
http://localhost:8000/api/health
```

and frontend `.env` contains:

```env
VITE_API_BASE_URL=http://localhost:8000/api
```

Restart `npm run dev` after changing Vite environment variables.

## Supabase configured but app still shows demo data

Set:

```env
DEMO_MODE=false
```

then restart FastAPI.

## Claude endpoint unavailable

Check:

```env
ANTHROPIC_API_KEY=...
```

and restart FastAPI.

## Never commit keys

Before commit:

```powershell
git status
```

Confirm no real `.env` file is staged.
