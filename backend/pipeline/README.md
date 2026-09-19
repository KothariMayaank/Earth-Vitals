# Data ingestion pipelines

## OpenAQ PM2.5 ingestion

`openaq_ingest.py` requests the latest PM2.5 reading for every sensor that has
reported to OpenAQ during the preceding 24 hours, calculates a sensor-weighted
global mean, and stores one daily `data_points` row. Re-running it on the same UTC
date updates that row instead of inserting a duplicate.

The metric key is `reporting_station_pm25_mean_ug_m3` because the value is PM2.5
mass concentration in `µg/m³`, not a dimensionless air-quality index. This simple mean
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

The script reads 11 annual series covering total and renewable generation,
clean/fossil/renewable shares, coal, gas, solar, wind, nuclear, and combined wind
and solar for `World` plus every country or economy with a three-letter ISO code.
It creates geography records, stores January 1 as the representative date for
each reporting year, and inserts or updates matching metric/geography/date data
points. Missing files,
unexpected CSV columns, duplicate annual records, and database errors are logged
clearly and return a non-zero exit status without a traceback.

The CSV is not committed to Git. Until downloading is automated in a later phase,
manually replace the local file with Ember's newest release before re-running the
pipeline.

## Global mineral reserves ingestion

`minerals_ingest.py` loads a reviewed annual CSV containing reserves and production
for oil, lithium, copper, cobalt, and nickel. It also derives a static
reserves-to-production ratio for each commodity. These metrics use two sources:

- Oil: OPEC's Annual Statistical Bulletin. EIA's API is free but requires a key,
  and its former global crude-oil reserve series currently returns no data.
- Lithium, copper, cobalt, and nickel: the USGS Mineral Commodity Summaries.

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
script validates every required source metric, rejects duplicate metric/year records,
and inserts or updates the matching `data_points` rows.

There is no stable single API that supplies both requested reserve metrics. When
new annual editions are published, manually refresh the oil values from the
[OPEC Annual Statistical Bulletin](https://www.opec.org/opec_web/en/publications/202.htm)
and the lithium value from the
[USGS Mineral Commodity Summaries](https://www.usgs.gov/centers/national-minerals-information-center/mineral-commodity-summaries)
before rerunning the pipeline. Nickel reserves are explicitly stored as a lower
bound because USGS reports the current world total as greater than 140 million tonnes.

## NOAA atmospheric CO2 ingestion

`atmosphere_ingest.py` downloads NOAA Global Monitoring Laboratory's global
marine-surface monthly CO2 CSV. It stores the monthly mean concentration and
derives an annual mean year-over-year growth series.

Run it from the repository root:

```shell
python -m backend.pipeline.atmosphere_ingest
```

The NOAA download does not require an API key. Recent observations can be
preliminary and may be revised by NOAA after quality control; rerunning the
pipeline updates matching dates instead of creating duplicates.
