"""Ingest global and country freshwater indicators from the World Bank API."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import requests
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.database import REPO_ROOT, get_engine
from backend.app.geographies import get_or_create_geography, get_or_create_world_geography
from backend.app.models import DataPoint, Geography, Metric, Source


LOGGER = logging.getLogger(__name__)
API_BASE_URL = "https://api.worldbank.org/v2"
SOURCE_URL = "https://data.worldbank.org/topic/water"
REQUEST_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class MetricDefinition:
    key: str
    indicator_code: str
    display_name: str
    unit: str
    description: str


@dataclass(frozen=True)
class NormalizedFreshwaterRow:
    metric_key: str
    geography_code: str
    geography_name: str
    timestamp: date
    value: float


METRICS = (
    MetricDefinition(
        key="freshwater_resources_per_capita_m3",
        indicator_code="ER.H2O.INTR.PC",
        display_name="Renewable Freshwater per Person",
        unit="m³/person",
        description=(
            "Annual renewable internal freshwater resources divided by population. "
            "It describes natural availability, not household access or water quality."
        ),
    ),
    MetricDefinition(
        key="freshwater_withdrawals_billion_m3",
        indicator_code="ER.H2O.FWTL.K3",
        display_name="Freshwater Withdrawals",
        unit="billion m³",
        description="Annual freshwater withdrawn by agriculture, industry, and households.",
    ),
    MetricDefinition(
        key="freshwater_withdrawals_pct_resources",
        indicator_code="ER.H2O.FWTL.ZS",
        display_name="Withdrawals vs. Internal Resources",
        unit="%",
        description=(
            "Annual freshwater withdrawals as a percentage of renewable internal "
            "freshwater resources; values above 100% can reflect non-renewable use or imports."
        ),
    ),
    MetricDefinition(
        key="water_stress_pct",
        indicator_code="ER.H2O.FWST.ZS",
        display_name="Water Stress",
        unit="%",
        description=(
            "Freshwater withdrawal as a share of available freshwater resources after "
            "accounting for environmental flow requirements."
        ),
    ),
    MetricDefinition(
        key="safe_drinking_water_access_pct",
        indicator_code="SH.H2O.SMDW.ZS",
        display_name="Safely Managed Drinking Water Access",
        unit="% of population",
        description=(
            "Share of people using drinking water from an improved source that is "
            "accessible on premises, available when needed, and free from contamination."
        ),
    ),
)


class FreshwaterIngestionError(RuntimeError):
    """An expected source or validation failure."""


def _request_json(http: requests.Session, path: str, **params: object) -> list[object]:
    try:
        response = http.get(
            f"{API_BASE_URL}/{path}",
            params={"format": "json", **params},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise FreshwaterIngestionError(f"World Bank API request failed for {path}: {exc}") from exc
    if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
        raise FreshwaterIngestionError(f"World Bank API returned an unexpected response for {path}.")
    return payload


def fetch_country_catalog(http: requests.Session) -> dict[str, str]:
    payload = _request_json(http, "country", per_page=400)
    countries: dict[str, str] = {}
    for record in payload[1]:
        if not isinstance(record, dict):
            continue
        region = record.get("region")
        code = record.get("id")
        name = record.get("name")
        if (
            isinstance(region, dict)
            and region.get("id") != "NA"
            and isinstance(code, str)
            and len(code) == 3
            and isinstance(name, str)
        ):
            countries[code] = name
    countries["WLD"] = "World"
    return countries


def fetch_freshwater_rows(http: requests.Session | None = None) -> list[NormalizedFreshwaterRow]:
    owns_session = http is None
    client = http or requests.Session()
    try:
        catalog = fetch_country_catalog(client)
        rows: list[NormalizedFreshwaterRow] = []
        seen: set[tuple[str, str, date]] = set()
        for definition in METRICS:
            payload = _request_json(
                client,
                f"country/all/indicator/{definition.indicator_code}",
                per_page=20000,
            )
            for record in payload[1]:
                if not isinstance(record, dict):
                    continue
                code = record.get("countryiso3code")
                year = record.get("date")
                value = record.get("value")
                if code not in catalog or value is None:
                    continue
                try:
                    timestamp = date(int(str(year)), 1, 1)
                    numeric_value = float(value)
                except (TypeError, ValueError, OverflowError):
                    continue
                geography_code = "WORLD" if code == "WLD" else str(code)
                identity = (definition.key, geography_code, timestamp)
                if identity in seen:
                    raise FreshwaterIngestionError(
                        f"Duplicate World Bank row for {definition.key}/{geography_code}/{year}."
                    )
                seen.add(identity)
                rows.append(
                    NormalizedFreshwaterRow(
                        metric_key=definition.key,
                        geography_code=geography_code,
                        geography_name=catalog[str(code)],
                        timestamp=timestamp,
                        value=numeric_value,
                    )
                )
        missing_world = {
            definition.key for definition in METRICS
        }.difference(row.metric_key for row in rows if row.geography_code == "WORLD")
        if missing_world:
            LOGGER.warning(
                "World Bank publishes no World aggregate for: %s. Country observations will still be stored.",
                ", ".join(sorted(missing_world)),
            )
        return rows
    finally:
        if owns_session:
            client.close()


def _get_or_create_source(session: Session) -> Source:
    source = session.scalar(select(Source).where(Source.name == "World Bank WDI"))
    if source is None:
        source = Source(
            name="World Bank WDI",
            url=SOURCE_URL,
            notes=(
                "World Development Indicators water series sourced from FAO AQUASTAT "
                "and the WHO/UNICEF Joint Monitoring Programme."
            ),
        )
        session.add(source)
        session.flush()
    return source


def _get_or_create_metrics(session: Session) -> dict[str, Metric]:
    metrics: dict[str, Metric] = {}
    for definition in METRICS:
        metric = session.scalar(select(Metric).where(Metric.key == definition.key))
        if metric is None:
            metric = Metric(
                key=definition.key,
                display_name=definition.display_name,
                domain="freshwater",
                unit=definition.unit,
                cadence="annual",
                description=definition.description,
            )
            session.add(metric)
            session.flush()
        else:
            metric.display_name = definition.display_name
            metric.domain = "freshwater"
            metric.unit = definition.unit
            metric.cadence = "annual"
            metric.description = definition.description
        metrics[definition.key] = metric
    return metrics


def store_freshwater_rows(rows: list[NormalizedFreshwaterRow]) -> tuple[int, int]:
    engine = get_engine()
    with Session(engine) as session:
        try:
            source = _get_or_create_source(session)
            metrics = _get_or_create_metrics(session)
            geographies: dict[str, Geography] = {}
            for row in rows:
                if row.geography_code in geographies:
                    continue
                geography = (
                    get_or_create_world_geography(session)
                    if row.geography_code == "WORLD"
                    else get_or_create_geography(
                        session,
                        code=row.geography_code,
                        name=row.geography_name,
                        geography_type="country",
                    )
                )
                geographies[row.geography_code] = geography

            metric_ids = [metric.id for metric in metrics.values()]
            geography_ids = [geography.id for geography in geographies.values()]
            existing = {
                (point.metric_id, point.geography_id, point.timestamp): point
                for point in session.scalars(
                    select(DataPoint).where(
                        DataPoint.metric_id.in_(metric_ids),
                        DataPoint.geography_id.in_(geography_ids),
                    )
                )
            }
            inserted = 0
            updated = 0
            for row in rows:
                metric = metrics[row.metric_key]
                geography = geographies[row.geography_code]
                identity = (metric.id, geography.id, row.timestamp)
                point = existing.get(identity)
                if point is None:
                    point = DataPoint(
                        metric_id=metric.id,
                        geography_id=geography.id,
                        timestamp=row.timestamp,
                        value=row.value,
                        source_id=source.id,
                    )
                    session.add(point)
                    existing[identity] = point
                    inserted += 1
                else:
                    point.value = row.value
                    point.source_id = source.id
                    updated += 1
            session.commit()
            return inserted, updated
        except SQLAlchemyError:
            session.rollback()
            raise


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    load_dotenv(REPO_ROOT / ".env")
    try:
        rows = fetch_freshwater_rows()
        LOGGER.info(
            "Loaded %d freshwater rows for %d metrics and %d geographies.",
            len(rows),
            len(METRICS),
            len({row.geography_code for row in rows}),
        )
        inserted, updated = store_freshwater_rows(rows)
    except (FreshwaterIngestionError, SQLAlchemyError, RuntimeError) as exc:
        LOGGER.error("Freshwater ingestion stopped: %s", exc)
        return 1
    print(f"Freshwater ingestion complete: {inserted} inserted, {updated} updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
