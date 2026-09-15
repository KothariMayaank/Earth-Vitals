# Data ingestion pipelines

## OpenAQ PM2.5 ingestion

`openaq_ingest.py` requests the latest PM2.5 reading for every sensor that has
reported to OpenAQ during the preceding 24 hours, calculates a sensor-weighted
global mean, and stores one daily `data_points` row. Re-running it on the same UTC
date updates that row instead of inserting a duplicate.

Despite the metric's requested key (`global_pm25_aqi`), the value is PM2.5 mass
concentration in `µg/m³`, not a dimensionless air-quality index. This simple mean
is useful as an ingestion proof of concept; it is not population- or area-weighted
and should not be treated as an authoritative global exposure statistic.

OpenAQ v3 currently requires an API key for every request. Register for a free key
in the [OpenAQ Explorer](https://explore.openaq.org/register), then set both
`OPENAQ_API_KEY` and `SUPABASE_DB_URL` in the repository's root `.env` file.

From the repository root, run:

```shell
python -m backend.pipeline.openaq_ingest
```

The command logs the number of valid sensor readings used and prints whether the
daily database row was inserted or updated. API, response-format, and database
errors are logged clearly and return a non-zero exit status without a traceback.

## Ember annual electricity ingestion

Ember publishes its Yearly Electricity Data as a free CSV download rather than a
documented, stable public data API. Download
[`yearly_full_release_long_format.csv`](https://files.ember-energy.org/public-downloads/yearly_full_release_long_format.csv)
and set its local path in the repository's root `.env` file:

```dotenv
ENERGY_DATA_CSV_PATH=backend/data/yearly_full_release_long_format.csv
```

Run the pipeline from the repository root:

```shell
python -m backend.pipeline.energy_ingest
```

The script reads the `World` annual series for renewable electricity share and
total electricity generation, stores January 1 as the representative date for
each reporting year, and inserts or updates matching data points. Missing files,
unexpected CSV columns, duplicate annual records, and database errors are logged
clearly and return a non-zero exit status without a traceback.

The CSV is not committed to Git. Until downloading is automated in a later phase,
manually replace the local file with Ember's newest release before re-running the
pipeline.

## Global mineral reserves ingestion

`minerals_ingest.py` loads a small normalized annual CSV containing global proven
crude oil reserves and global lithium reserves. These metrics need two sources:

- Oil: OPEC's Annual Statistical Bulletin. EIA's API is free but requires a key,
  and its former global crude-oil reserve series currently returns no data.
- Lithium: the USGS Mineral Commodity Summaries data release, available as CSV
  through the free ScienceBase catalog without an API key.

Set the normalized file path in the root `.env`:

```dotenv
MINERALS_DATA_CSV_PATH=backend/data/minerals_reserves.csv
```

Then run:

```shell
python -m backend.pipeline.minerals_ingest
```

The normalized CSV must contain `metric_key`, `year`, `value`, `source_name`,
`source_url`, and `source_notes`. January 1 represents each reporting year. The
script validates both required metrics, rejects duplicate metric/year records,
and inserts or updates the matching `data_points` rows.

There is no stable single API that supplies both requested reserve metrics. When
new annual editions are published, manually refresh the oil value from the
[OPEC Annual Statistical Bulletin](https://www.opec.org/opec_web/en/publications/202.htm)
and the lithium value from the
[USGS Mineral Commodity Summaries](https://www.usgs.gov/centers/national-minerals-information-center/mineral-commodity-summaries)
before rerunning the pipeline.
