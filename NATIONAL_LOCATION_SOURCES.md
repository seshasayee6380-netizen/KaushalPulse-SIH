# National location data

KaushalPulse treats State/UT + District as a reusable market context across every workspace.

Primary government reference: Local Government Directory (LGD), Ministry of Panchayati Raj. The Open Government Data (OGD) Platform lists the LGD States and Districts datasets and states that they are updated monthly.

Official references:
- https://data.gov.in/resource/local-government-directory-lgd-districts
- https://data.gov.in/catalog/local-government-directory-lgd
- https://lgdirectory.gov.in/

Prototype bootstrap source:
- https://github.com/iaseth/data-for-india
- https://raw.githubusercontent.com/iaseth/data-for-india/master/data/readable/districts.json

Why two layers? The official OGD/LGD source is the intended production authority. The prototype's public JSON bootstrap makes local setup usable without an API key; the source URL is isolated in `backend/main.py` so it can be replaced by an official government API/feed when credentials and endpoint access are available.

## Coverage integrity
The runtime source is used to refresh the local master when internet access is available. The bundled database is an offline fallback and should not be described as a complete current national district list without a successful refresh. The UI/API expose the current local count and the refresh source so coverage is auditable.
