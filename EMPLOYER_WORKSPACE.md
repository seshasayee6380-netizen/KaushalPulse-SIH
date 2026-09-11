# Employer Workspace

The Employer role is the demand, hiring, validation and training-partnership side of KaushalPulse.

## Sidebar

1. Dashboard — hiring snapshot, alerts and the employer impact loop.
2. My Company — company identity, profile and account-scoped hiring metrics.
3. Jobs & Hiring — create/close jobs and publish real hiring demand.
4. Skill Requirements — normalized skills behind open jobs, priority, openings and district training coverage.
5. Candidate Pool — skill-based candidate matches for the employer's own open jobs and interview invitations.
6. Training Partnership — submit curriculum, practical-training, internship, guest-faculty, trainer-upskilling, equipment and training-seat requests.
7. Employment Commitments — commit future hiring and track fulfilment.
8. Hiring Outcomes — move candidates through invited → interviewed → offered → hired → joined and view outcomes.
9. Employer Feedback — record candidate skill gaps and employer feedback for district action.

All employer write operations are tenant- and company-scoped. Employer requests and feedback are audit logged.

## SIH demo workflow

Recommended demo: sign in with the Employer demo account → post a vacancy → open Skill Requirements to see normalized demand → open Candidate Pool to review skill matches and invite a candidate → open Hiring Outcomes to move the candidate through interview/offer/hire/join → create an Employment Commitment → submit a Training Partnership request → submit Employer Feedback. Each write action persists to SQLite and is scoped to the employer company/tenant.

Retention and long-term salary outcomes are intentionally not fabricated in the demo; the Hiring Outcomes page states that production retention capture requires additional post-joining employer outcome fields.
