# KaushalPulse — District Admin Workspace

The District Admin navigation is implemented as nine separate working modules. Each module has its own frontend route and backend data flow.

## Modules
1. Dashboard — district command centre with employers, jobs, training capacity, trainers, equipment gaps, commitments, placements, priority skill gaps and recommendations.
2. District Job Board — searchable/sortable open employer demand with job detail evidence.
3. Active Recruiters — employer relationship view with open postings and openings.
4. Course Health Score — health scoring, missing demand skills, status and evidence drill-down.
5. Curated Course Library — provider/course catalogue with duration, seats, mapped skills and placement evidence.
6. Employment Guarantee Board — employer commitments, fulfilment %, editable hired slots and persisted updates.
7. District Training Plan — evidence-to-action planning view with persisted plan save.
8. Employer Feedback — feedback review workflow with new/reviewed/actioned/dismissed statuses and admin notes.
9. Placement Outcomes — verified placement records, aggregate fill rate, provider/course/employer evidence.

## Role access
The demo District Admin account is `DEMO-ADMIN-001` and is tenant-scoped to its assigned district.

## Run
Start `run_backend.bat`, then open `OPEN_THIS_FIRST.html` (or `frontend/index.html` from a local HTTP server). Use Quick Demo → District Admin.

## Validation
- Python backend syntax checked.
- Frontend JavaScript syntax checked with `node --check`.
- Existing `tests/full_regression_v8.py` passed.
- District Admin endpoint regression passed for all nine modules plus feedback review, guarantee update and plan save.
- ZIP archive integrity checked with `unzip -t`.
