# Employer Menu Routing Fix

Fixed the frontend route dispatch so these sidebar menus now actually render their dedicated pages:

- Jobs & Hiring -> `renderDemand()`
- Skill Requirements -> `renderEmployerSkills()`
- Candidate Pool -> `renderCandidates()`
- Training Partnership -> `renderTrainingPartnership()`
- Hiring Outcomes -> `renderHiringOutcomes()`

Previously, the sidebar buttons were present and the page functions existed, but `renderPage()` did not dispatch these four employer routes, so clicking them could leave the dashboard unchanged and generate no corresponding API request. This fix adds the missing route mappings.
