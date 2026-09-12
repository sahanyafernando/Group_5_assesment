# SCOPING.md

## What we are building

A local Works Dispatch dashboard that converts the supplied resident-report export into consolidated incidents, enriches them using council asset and recent job-history data, ranks them with explainable rules, recommends the specialist crew, and lets the Works Coordinator confirm or override assignments.

## Deliberately not building

For the hackathon MVP we are not building authentication, a resident portal, route optimization, GPS crew tracking, SMS/email notifications, a native mobile app, advanced GIS, model training, or autonomous dispatch.

## Ownership

Fill this in with team members:

- Frontend / UX:
- Backend / Supabase:
- AI / incident intelligence:
- Integration / testing:
- Presentation / demo:

## Biggest risk

The largest product/engineering risk is converting inconsistent free-text reports into correct incident groups without over-merging different problems. We reduce this risk by combining deterministic candidate grouping with AI semantic checks, retaining all source reports, storing confidence, and allowing manual review/override.
