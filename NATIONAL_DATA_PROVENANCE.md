# KaushalPulse National Data Provenance

## Administrative location master
KaushalPulse uses a national State → District reference model. The backend first attempts to refresh the national district directory from the configured reference URL and falls back to `data/national_locations.json` for offline operation.

Configured reference:
- Public reference: https://raw.githubusercontent.com/iaseth/data-for-india/master/data/readable/districts.json
- Official reference: https://igod.gov.in/sg/district/states

The application does **not** present the offline bundle as a live official feed. The UI/API source metadata distinguishes reference data from prototype-seeded market data.

## Prototype market data
For districts that have no employer/training records yet, KaushalPulse seeds deterministic **prototype market data** (companies, openings and course supply) so every district selector target remains functional offline. These records are explicitly treated as prototype-seeded data and are not government statistics.

## Analytical provenance
Core engine outputs expose an engine version, run identifier and evidence source metadata. Employer and training-provider submissions remain user-submitted and are not silently converted into official statistics.
