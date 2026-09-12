# DECISIONS.md

Complete this during the hackathon.

## D1 — Separate Report from Incident

**Decision:** One resident report is not treated as one job. Multiple reports can link to one incident.

**Why:** The source data can contain multiple reports about the same underlying problem.

**Driven by:** _team member_

---

## D2 — AI for language, rules for operations

**Decision:** Claude handles classification, semantic interpretation and summarization. Priority and crew mapping remain deterministic.

**Why:** Free text is ambiguous, but operational decisions must be explainable and reproducible.

**Driven by:** _team member_

---

## D3 — Crew mapping from supplied history

**Decision:** Only work types supported by supplied crew history are mapped automatically. Unsupported work goes to Manual Review.

**Why:** Inventing a crew capability could waste a limited crew slot.

**Driven by:** _team member_

---

## D4 — Supabase persistence

**Decision:** Persist incidents, report links, assignments and overrides in Supabase Postgres.

**Why:** Team actions must survive refresh/restart and remain visible on later days.

**Driven by:** _team member_

---

## D5 — Human override

**Decision:** Coordinator overrides take precedence over model suggestions.

**Why:** The application is decision support, not autonomous dispatch.

**Driven by:** _team member_

---

## AI usage

### AI used for
- report work-type classification
- hazard/impact extraction
- location hints
- semantic duplicate verification
- actionable incident summaries

### AI deliberately not used for
- final crew mapping
- final priority score
- final dispatch decision
- database truth

Add specific prompts/model choices and contributors before submission.
