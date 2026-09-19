"""Ingest a current global mean of OpenAQ PM2.5 sensor readings."""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from statistics import fmean

import requests
from dotenv import load_dotenv
from requests import Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.database import REPO_ROOT, get_engine
from backend.app.geographies import get_or_create_world_geography
from backend.app.models import DataPoint, Metric, Source


LOGGER = logging.getLogger(__name__)

OPENAQ_LATEST_PM25_URL = "https://api.openaq.org/v3/parameters/2/latest"
OPENAQ_SOURCE_URL = "https://openaq.org/"
METRIC_KEY = "reporting_station_pm25_mean_ug_m3"
LEGACY_METRIC_KEY = "global_pm25_aqi"
PAGE_SIZE = 1000
REQUEST_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class NormalizedDataPoint:
    timestamp: date
    value: float
    reading_count: int


class OpenAQIngestionError(RuntimeError):
    """An expected error that should stop this ingestion run cleanly."""


def _request_page(api_key: str, page: int, datetime_min: datetime) -> Response:
    response = requests.get(
        OPENAQ_LATEST_PM25_URL,
        headers={"X-API-Key": api_key},
        params={
            "limit": PAGE_SIZE,
            "page": page,
            "datetime_min": datetime_min.isoformat(),
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code in {401, 403}:
        raise OpenAQIngestionError(
            "OpenAQ rejected the API key. Set a valid OPENAQ_API_KEY in the "
            "root .env file."
        )
    response.raise_for_status()
    return response


def fetch_latest_pm25(api_key: str) -> list[dict]:
    """Fetch every page of PM2.5 sensors reporting during the last 24 hours."""
    datetime_min = datetime.now(timezone.utc) - timedelta(hours=24)
    readings: list[dict] = []
    page = 1

    try:
        while True:
            payload = _request_page(api_key, page, datetime_min).json()
            if not isinstance(payload, dict):
                raise OpenAQIngestionError(
                    "OpenAQ returned an unexpected response instead of a JSON object."
                )
            page_results = payload.get("results")
            if not isinstance(page_results, list):
                raise OpenAQIngestionError(
                    "OpenAQ returned an unexpected response without a results list."
                )

            readings.extend(page_results)
            meta = payload.get("meta", {})
            if not isinstance(meta, dict):
                raise OpenAQIngestionError(
                    "OpenAQ returned an unexpected response with invalid metadata."
                )
            found_value = meta.get("found")
            found = int(found_value) if found_value is not None else None
            if (
                not page_results
                or (found is not None and len(readings) >= found)
                or len(page_results) < PAGE_SIZE
            ):
                break
            page += 1
    except OpenAQIngestionError:
        raise
    except requests.RequestException as exc:
        raise OpenAQIngestionError(f"OpenAQ API request failed: {exc}") from exc
    except (TypeError, ValueError, requests.JSONDecodeError) as exc:
        raise OpenAQIngestionError(f"OpenAQ returned invalid JSON data: {exc}") from exc

    return readings


def normalize_readings(readings: list[dict]) -> NormalizedDataPoint:
    """Calculate one sensor-weighted global PM2.5 mean for the current UTC day."""
    values: list[float] = []
    newest_timestamp: datetime | None = None

    for reading in readings:
        try:
            value = float(reading["value"])
            utc_text = reading["datetime"]["utc"]
            measured_at = datetime.fromisoformat(utc_text.replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError, AttributeError):
            continue

        if not math.isfinite(value) or value < 0:
            continue
        if measured_at.tzinfo is None:
            measured_at = measured_at.replace(tzinfo=timezone.utc)
        values.append(value)
        if newest_timestamp is None or measured_at > newest_timestamp:
            newest_timestamp = measured_at

    if not values or newest_timestamp is None:
        raise OpenAQIngestionError(
            "OpenAQ returned no valid, non-negative PM2.5 readings from the last 24 hours."
        )

    return NormalizedDataPoint(
        timestamp=newest_timestamp.astimezone(timezone.utc).date(),
        value=fmean(values),
        reading_count=len(values),
    )


def _get_or_create_source(session: Session) -> Source:
    source = session.scalar(select(Source).where(Source.name == "OpenAQ"))
    if source is None:
        source = Source(
            name="OpenAQ",
            url=OPENAQ_SOURCE_URL,
            notes="Global open air-quality measurements aggregated from monitoring networks.",
        )
        session.add(source)
        session.flush()
    return source


def _get_or_create_metric(session: Session) -> Metric:
    metric = session.scalar(select(Metric).where(Metric.key == METRIC_KEY))
    if metric is None:
        # Preserve existing history while correcting the legacy key, which called
        # a physical concentration an AQI. OpenAQ reports µg/m³, not an AQI score.
        metric = session.scalar(select(Metric).where(Metric.key == LEGACY_METRIC_KEY))
        if metric is None:
            metric = Metric(key=METRIC_KEY)
            session.add(metric)
        else:
            metric.key = METRIC_KEY

        metric.display_name = "Reporting-Station PM2.5 Mean"
        metric.domain = "emissions"
        metric.unit = "µg/m³"
        metric.cadence = "daily"
        metric.description = (
            "Sensor-weighted mean of the latest valid PM2.5 measurements reported "
            "to OpenAQ during the preceding 24 hours. This is an availability-based "
            "monitoring-station mean, not a population-weighted global exposure estimate."
        )
        session.flush()
    return metric


def store_data_point(row: NormalizedDataPoint) -> tuple[int, int]:
    engine = get_engine()
    with Session(engine) as session:
        try:
            source = _get_or_create_source(session)
            metric = _get_or_create_metric(session)
            world = get_or_create_world_geography(session)
            data_point = session.scalar(
                select(DataPoint).where(
                    DataPoint.metric_id == metric.id,
                    DataPoint.geography_id == world.id,
                    DataPoint.timestamp == row.timestamp,
                )
            )

            if data_point is None:
                session.add(
                    DataPoint(
                        metric_id=metric.id,
                        timestamp=row.timestamp,
                        value=row.value,
                        source_id=source.id,
                        geography_id=world.id,
                    )
                )
                inserted, updated = 1, 0
            else:
                data_point.value = row.value
                data_point.source_id = source.id
                inserted, updated = 0, 1

            session.commit()
            return inserted, updated
        except SQLAlchemyError:
            session.rollback()
            raise


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    load_dotenv(REPO_ROOT / ".env")
    api_key = os.getenv("OPENAQ_API_KEY")
    if not api_key:
        LOGGER.error(
            "OPENAQ_API_KEY is required by the OpenAQ v3 API. Add it to the root .env file."
        )
        return 1

    try:
        readings = fetch_latest_pm25(api_key)
        row = normalize_readings(readings)
        LOGGER.info(
            "Pulled %d current PM2.5 readings; global mean for %s is %.3f µg/m³.",
            row.reading_count,
            row.timestamp,
            row.value,
        )
        inserted, updated = store_data_point(row)
    except (OpenAQIngestionError, SQLAlchemyError, RuntimeError) as exc:
        LOGGER.error("OpenAQ ingestion stopped: %s", exc)
        return 1

    print(f"OpenAQ ingestion complete: {inserted} row(s) inserted, {updated} row(s) updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
