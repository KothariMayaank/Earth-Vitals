# Earth Vitals API

Run the development server from the repository root:

```shell
python -m uvicorn backend.app.main:app --reload --port 8000
```

The API reads `SUPABASE_DB_URL` from the root `.env`. Browser requests from the
Next.js development origin, `http://localhost:3000`, are allowed by CORS.

## Health

`GET /health` checks that the API process is responding. It does not query the
database.

```json
{"status":"ok"}
```

## List metrics

`GET /metrics` returns every configured metric, ordered by key.

```json
[
  {
    "id": 1,
    "key": "reporting_station_pm25_mean_ug_m3",
    "display_name": "Reporting-Station PM2.5 Mean",
    "domain": "emissions",
    "unit": "µg/m³",
    "cadence": "daily"
  }
]
```

## Metric history

`GET /metrics/{metric_key}/history` returns timestamp/value pairs in ascending
date order. Optional inclusive filters are `start=YYYY-MM-DD` and
`end=YYYY-MM-DD`.

```text
GET /metrics/global_renewable_share_pct/history?start=2024-01-01&end=2025-12-31
```

```json
[
  {"timestamp":"2024-01-01","value":31.95},
  {"timestamp":"2025-01-01","value":33.78}
]
```

An unknown metric returns HTTP 404. A start date later than the end date returns
HTTP 422.

## Latest metric value

`GET /metrics/{metric_key}/latest` returns the most recent timestamp/value pair.

```text
GET /metrics/global_electricity_generation_twh/latest
```

```json
{"timestamp":"2025-01-01","value":31734.49}
```

An unknown metric, or a metric without data points, returns HTTP 404.

## Domain summary

`GET /domains/{domain}/summary` returns the latest value and metric metadata for
every populated metric in `energy`, `minerals`, or `emissions`.

```text
GET /domains/minerals/summary
```

```json
[
  {
    "id": 5,
    "key": "global_lithium_reserves_tonnes",
    "display_name": "Global Lithium Reserves",
    "domain": "minerals",
    "unit": "tonnes",
    "cadence": "annual",
    "timestamp": "2025-01-01",
    "value": 37000000.0,
    "description": "Year-end global lithium reserves measured as lithium content.",
    "source_name": "U.S. Geological Survey",
    "source_url": "https://doi.org/10.5066/P1WKQ63T"
  }
]
```

Unsupported domain names return HTTP 422.

Global metric routes and domain summaries explicitly read the `WORLD`
geography, so country observations cannot change the Planetary Health Index or
global dashboard values.

## Geographies and country electricity data

`GET /geographies?type=country` lists available country/economy geographies.

```json
[{"id":42,"code":"IND","name":"India","type":"country"}]
```

`GET /countries/{country_code}` returns one geography. Country codes are
case-insensitive ISO alpha-3 codes.

`GET /countries/{country_code}/summary?domain=energy` returns the latest value
and metadata for each populated metric in that country. The optional `domain`
query accepts `energy`, `minerals`, or `emissions`.

`GET /countries/{country_code}/metrics/{metric_key}/history` returns that
country's full time series in ascending order, with the same optional `start`
and `end` filters as the global history route.

`GET /metrics/{metric_key}/map?date=YYYY-MM-DD` returns one observation per
country for a choropleth. Without `date`, each country contributes its latest
observation; with `date`, the route returns the latest observation on or before
that date.

```json
{
  "metric_key":"global_renewable_share_pct",
  "display_name":"Global Renewable Electricity Share",
  "unit":"%",
  "points":[
    {"code":"IND","name":"India","timestamp":"2025-01-01","value":24.08}
  ]
}
```

The current country coverage comes from Ember's annual electricity dataset.
The minerals and emissions datasets remain global-only.

## Planetary Health Index

`GET /index/current` returns the current 0-100 composite, the normalized score
for each domain, and the weights used in the composite.

```json
{
  "composite_score": 29.6,
  "domain_scores": {"energy": 37.89, "minerals": 39.73, "emissions": 11.19},
  "weights": {"energy": 0.333, "minerals": 0.333, "emissions": 0.333}
}
```

`PUT /index/weights` accepts all three weights and returns the recomputed index.
Each value must be between 0 and 1, and the three values must sum to within 0.01
of 1.0.

```json
{"energy":0.5,"minerals":0.3,"emissions":0.2}
```

The subjective normalization endpoints and their detailed rationales live in
`backend/app/index_config.py`. A raw value is linearly interpolated between its
configured concerning endpoint (score 0) and healthy endpoint (score 100), then
clamped to that range. Domain scores are unweighted averages of their available
configured metrics; the composite is the weighted average of the three domains.

## Metric projections

`POST /projections/{metric_key}` creates and stores a simplified scenario. The
request accepts an annual percentage change and, for trend metrics, an optional
future target year.

```json
{"rate_of_change_pct": 1.5, "target_year": 2050}
```

Finite resource scenarios model annual extraction against current reserves. A
declining recent reserve series supplies the extraction proxy when available;
otherwise the response visibly identifies the configured official production
fallback. Trend scenarios compound the latest value at the selected rate. Both
model types stop at a 200-year horizon and return chart-ready annual points, a
plain-language result, and a visible `methodology_note` warning that the result
is an exploratory simplification rather than a forecast.
