# Scheduled ingestion jobs

These workflows keep the shared Earth Vitals database current:

- `openaq-ingestion.yml`: daily at 05:17 UTC, because OpenAQ readings change daily.
- `energy-ingestion.yml`: monthly on the 3rd at 06:23 UTC. Ember's source is annual; the workflow downloads the current published CSV before ingesting it.
- `minerals-ingestion.yml`: monthly on the 15th at 06:41 UTC. OPEC and USGS reserve figures are annual and the normalized source CSV is reviewed in this repository.

The deliberately staggered, non-round start times avoid common scheduled-job traffic peaks. Each workflow can also be started manually with `workflow_dispatch`.

Repository secrets required:

- `SUPABASE_DB_URL` for every workflow.
- `OPENAQ_API_KEY` for the OpenAQ workflow.
