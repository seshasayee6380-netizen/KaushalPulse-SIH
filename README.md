# KaushalPulse — Disha for your skills

This package is a working local prototype with a FastAPI backend and SQLite database, with a national location-refresh integration and a shared evidence-driven intelligence engine. The frontend is served as a local HTML application and calls the backend on `http://127.0.0.1:8010`.

## Start
1. Run `run_backend.bat` and keep the terminal open.
2. Wait for `Uvicorn running on http://127.0.0.1:8010`.
3. Open `OPEN_THIS_FIRST.html`, then `frontend/index.html`.

## Training Provider workflow
The Training Provider workspace now has separate, functional pages for **My Centre, Courses, Skills Taught, Training Capacity, Trainers & Equipment, and Placements**. Each page uses provider-scoped backend data rather than reusing the student/academy page.

Provider demo actions include: create/update courses and skill mappings, review demand-versus-supply by skill, inspect capacity recommendations, add trainer and equipment records, and record verified placement outcomes. Provider writes are restricted to the signed-in provider and its registered district; browsing another district stays read-only.

Quick demo: sign in as **DEMO-TRAINER-001** from the Login screen.

## Core student workflow
Profile → 3-level assessment → **Career Alignment Hub (industry demand → personal skill gap → targeted local training → job match)** → resume upload/fitness → persisted 12-week skill path → milestone completion → verified skill update → recalculated readiness.

## SIH demo path
Open **Career Alignment Hub** from the Student workspace. It is the single judge-facing screen that connects the four evidence layers: local employer demand, the learner's target-role gaps, district training supply, and current job matches. Use **Build my 12-week path** to move from the identified highest-priority gap into a persisted learning path and complete a milestone to demonstrate that the verified skill state changes.

## Working product workflows
- Resume Fitness Score: real file upload, text/PDF extraction, skill extraction, role weighting, local job-level matching, next-skill projection.
- AI Skill-Path Navigator: generates and stores a 12-week path, local course suggestions and practical projects; completing a step updates the stored student skill and readiness.
- District Employment Guarantee Board: employer-declared commitments, hired-slot updates, remaining slots, reverse candidate matching and persisted interview invites.
- AI Mentor Marketplace: stored mentor requests with student goals and district context.
- Skill Obsolescence / Reskilling: compares stored previous demand snapshots with current district demand and stores reskilling actions.

## National location behavior
- Every workspace shows a State + District market selector.
- On an internet-connected machine, the application refreshes the local district master from the configured national district reference source when the bundled master is incomplete.
- The same source is cached in the browser for fast subsequent loads.
- Selecting any state/district provisions that district tenant in the local database if it is not already present.
- Read-only market views use the selected district; writes remain protected by the signed-in organisation tenant.
- The bundled SQLite file is an offline fallback, not a claim of a complete current government district list. Use the built-in refresh endpoint or `scripts/import_lgd_districts.py` with the latest source file to refresh it.
- Source references distinguish the Government of India LGD/OGD authority from the public bootstrap mirror; analytical records separately identify employer, training-provider, student and prototype-seeded evidence.

## Tenant behavior
The signed-in account has an immutable assigned tenant. State/district selection changes the read-only market context through `X-Market-District-ID`; it does not change the account's write tenant. This keeps national browsing separate from authorization.

## Shared intelligence engine
Major analytical outputs are derived from the same `8.0-national-unified-engine`: job demand, skill demand, demand/supply gaps, course health, student readiness/job fit, resume fitness, path prioritisation, course recommendations, curriculum suggestions, placement simulation and district planning. Each engine response carries a run identifier and evidence provenance.


## Honest AI boundary
The local prototype uses an explainable hybrid engine (rules + skill extraction) so it remains runnable without an external AI key. It is not presented as a trained model or as guaranteed placement prediction.


### Quick Demo Login
Use the Login page Demo ID field and enter one of the IDs in `DEMO_ACCOUNTS.txt`. Clicking `Sign in with Demo ID` authenticates against the backend demo-account table and opens the correct role workspace.

## National location behavior
KaushalPulse is not hard-coded to a single district. The State → District market selector is available throughout the application. The backend attempts to refresh the national district reference when internet access is available and falls back to the bundled national snapshot for offline use. Each known bundled district is provisioned with a clearly prototype-labelled local employer/job/training dataset so the workflow remains usable when a district has no user-submitted data yet.
