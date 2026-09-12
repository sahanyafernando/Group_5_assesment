# Requirements — Muthuwella Works Dispatch

## 1. Product objective

Help the Works Coordinator turn hundreds of messy resident reports into a concise, explainable daily dispatch picture.

The system must answer:

1. What are the real underlying incidents?
2. Which incidents matter most?
3. Which specialist crew is appropriate?
4. What has already been assigned/completed?

The system supports the coordinator; it does not replace the coordinator.

---

## 2. Functional requirements

| ID | Requirement | Claude API |
|---|---|---|
| FR-01 | Import today's resident reports | No |
| FR-02 | Preserve raw report data | No |
| FR-03 | Normalize nulls, text, categories, urgency and timestamps | No |
| FR-04 | Classify missing/ambiguous report work type | Yes |
| FR-05 | Extract hazards, impact and location hints from free text | Yes |
| FR-06 | Resolve canonical road/location against assets | Claude hint + deterministic validation |
| FR-07 | Create candidate duplicate groups using location/type/time | No |
| FR-08 | Verify ambiguous semantic duplicates | Yes |
| FR-09 | Combine duplicate reports into one incident | No |
| FR-10 | Generate concise actionable incident summary | Yes |
| FR-11 | Enrich incidents with ward, road class, assets and facilities | No |
| FR-12 | Check recent work history for possible previous related jobs | No |
| FR-13 | Recommend required crew through fixed work-type mapping | No |
| FR-14 | Calculate explainable priority score | No |
| FR-15 | Display ranked incidents | No |
| FR-16 | Show priority reasons | No |
| FR-17 | Show AI/location confidence and manual-review warnings | Yes + code |
| FR-18 | Show underlying reports for each incident | No |
| FR-19 | Let coordinator override work type, crew, priority and grouping | No |
| FR-20 | Group incidents into crew dispatch queues | No |
| FR-21 | Assign an incident to a crew | No |
| FR-22 | Track New/Triaged/Assigned/In Progress/Completed/Needs Review | No |
| FR-23 | Persist assignments/status for future days | No |
| FR-24 | Search/filter by priority, crew, type, location, ward and status | No |
| FR-25 | Record manual overrides/audit history | No |

---

## 3. Supported work types

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

## 4. Deterministic crew mapping

```text
Pothole                -> Road Surface
Road surface damage    -> Road Surface
Pavement damage        -> Road Surface
Kerb                   -> Road Surface
Road marking           -> Road Surface

Blocked drain          -> Drainage
Gully                  -> Drainage
Culvert                -> Drainage
Manhole                -> Drainage
Drainage flooding      -> Drainage

Streetlight            -> Lighting & Street Furniture
Sign post              -> Lighting & Street Furniture
Bus shelter            -> Lighting & Street Furniture
Bench                  -> Lighting & Street Furniture

Unsupported            -> Manual Review
Unknown                -> Manual Review
```

Claude must not invent another crew.

---

## 5. Priority rule

Priority is deterministic and explainable.

Recommended maximum:

```text
Safety / severity        35
Road / public impact     20
Critical facility        15
Age / persistence        15
Multiple reports         10
Resident urgency          5
                         ---
                         100
```

### Starter scoring

Severity:

```text
critical  35
high      28
medium    18
low        8
unknown   10
```

Road class:

```text
main road    20
bus route    15
residential   8
lane          5
other         0
```

Facility distance:

```text
<= 100m   15
<= 200m   10
<= 300m    5
> 300m     0
```

Age:

```text
> 7 days   15
>= 3 days  10
>= 1 day    5
same day    0
```

Report count:

```text
1        0
2        3
3-4      6
5+      10
```

Resident urgency:

```text
high      5
medium    3
low       1
missing   0
```

These are starter rules and should be documented if changed.

---

## 6. AI requirements

Claude SHOULD be used for:

- free-text understanding
- work-type classification
- hazard/impact extraction
- location-hint extraction
- ambiguity detection
- semantic duplicate verification
- consolidated incident summaries

Claude MUST NOT be the authority for:

- final priority score
- final crew mapping
- canonical asset existence
- recent-job truth
- final dispatch assignment
- database state

### Expected report-analysis contract

```json
{
  "work_type": "Pothole",
  "category": "Roads",
  "incident_title": "Large pothole near pharmacy",
  "incident_summary": "Large pothole reported near the pharmacy.",
  "location": {
    "road_hint": "Kirula Road",
    "landmark": "pharmacy"
  },
  "severity": "high",
  "hazards": ["vehicle damage"],
  "impact": ["road users"],
  "confidence": 0.94,
  "needs_review": false
}
```

Low-confidence or malformed AI output must never crash batch processing.

---

## 7. Non-functional requirements

### NFR-01 Explainability
Every priority and crew recommendation must be explainable.

### NFR-02 Human control
All recommendations are overridable.

### NFR-03 Data integrity
Never delete/overwrite the supplied raw report values.

### NFR-04 Security
Claude and Supabase server secrets must stay in FastAPI environment variables.

### NFR-05 Reliability
Claude failure should mark an item for review rather than take down the application.

### NFR-06 Persistence
Assignments and overrides survive application restarts and future days.

### NFR-07 Performance
The system should comfortably handle hundreds of daily reports.

### NFR-08 Local execution
Frontend and backend must run locally from documented commands.

### NFR-09 Auditability
Store source-report links, AI result, priority reasons and manual overrides.

---

## 8. MVP screens

### Dashboard
- report count
- incident count
- high/critical count
- needs-review count
- ranked incident list
- search/filter

### Incident detail
- summary
- canonical location
- priority score/breakdown
- work type
- recommended crew
- AI confidence
- asset context
- recent-history warning
- original source reports
- override/assignment actions

### Dispatch view
Queues for:
- Road Surface
- Drainage
- Lighting & Street Furniture
- Manual Review

---

## 9. Out of scope for the hackathon MVP

- resident-facing portal
- GPS crew tracking
- route optimization
- SMS/email notifications
- native mobile app
- complex GIS
- custom model training
- autonomous dispatch
- unnecessary multi-agent architecture
