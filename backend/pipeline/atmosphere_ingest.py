"""Ingest NOAA's global monthly atmospheric carbon-dioxide record."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from io import StringIO

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.database import REPO_ROOT, get_engine
from backend.app.models import DataPoint, Metric, Source


LOGGER = logging.getLogger(__name__)
NOAA_CO2_CSV_URL = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_gl.csv"
NOAA_SOURCE_URL = "https://gml.noaa.gov/ccgg/trends/gl_data.html"
REQUEST_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class MetricDefinition:
    key: str
    display_name: str
    unit: str
    cadence: str
    description: str


@dataclass(frozen=True)
class NormalizedAtmosphereRow:
    metric_key: str
    timestamp: date
    value: float


METRICS = {
    "global_atmospheric_co2_ppm": MetricDefinition(
        key="global_atmospheric_co2_ppm",
        display_name="Global Atmospheric CO₂",
        unit="ppm",
        cadence="monthly",
        description=(
            "NOAA marine-surface global monthly mean atmospheric carbon dioxide. "
            "Recent values may be preliminary and can be revised after quality control."
        ),
    ),
    "global_atmospheric_co2_growth_ppm_per_year": MetricDefinition(
        key="global_atmospheric_co2_growth_ppm_per_year",
        display_name="Atmospheric CO₂ Annual Growth",
        unit="ppm/year",
        cadence="annual",
        description=(
            "Year-over-year change in the annual mean of NOAA's global monthly "
            "atmospheric carbon-dioxide series."
        ),
    ),
}


class AtmosphereIngestionError(RuntimeError):
    """An expected error that should stop this ingestion run cleanly."""


def fetch_noaa_csv() -> str:
    try:
        response = requests.get(NOAA_CO2_CSV_URL, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        raise AtmosphereIngestionError(f"NOAA CO2 download failed: {exc}") from exc


def normalize_noaa_co2(csv_text: str) -> list[NormalizedAtmosphereRow]:
    try:
        frame = pd.read_csv(StringIO(csv_text), comment="#")
    except (ValueError, pd.errors.ParserError) as exc:
        raise AtmosphereIngestionError(f"NOAA returned an invalid CSV: {exc}") from exc

    required = {"year", "month", "average"}
    missing = required.difference(frame.columns)
    if missing:
        raise AtmosphereIngestionError(
            "NOAA CSV is missing required columns: " + ", ".join(sorted(missing))
        )

    for column in required:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=list(required))
    frame = frame[frame["average"] > 0].copy()
    if frame.empty:
        raise AtmosphereIngestionError("NOAA CSV contains no valid CO2 observations.")

    rows = [
        NormalizedAtmosphereRow(
            metric_key="global_atmospheric_co2_ppm",
            timestamp=date(int(record.year), int(record.month), 1),
            value=float(record.average),
        )
        for record in frame.sort_values(["year", "month"]).itertuples(index=False)
    ]

    annual_summary = frame.groupby("year", as_index=False).agg(
        average=("average", "mean"), month_count=("month", "nunique")
    )
    # A partial calendar year has a seasonal bias, so annual growth is only
    # published after all 12 monthly means are present.
    annual_means = annual_summary[annual_summary["month_count"] == 12].copy()
    annual_means["growth"] = annual_means["average"].diff()
    for record in annual_means.dropna(subset=["growth"]).itertuples(index=False):
        rows.append(
            NormalizedAtmosphereRow(
                metric_key="global_atmospheric_co2_growth_ppm_per_year",
                timestamp=date(int(record.year), 1, 1),
                value=float(record.growth),
            )
        )
    return rows


def _get_or_create_source(session: Session) -> Source:
    source = session.scalar(select(Source).where(Source.name == "NOAA GML"))
    if source is None:
        source = Source(
            name="NOAA GML",
            url=NOAA_SOURCE_URL,
            notes="Global Monitoring Laboratory marine-surface atmospheric CO2 record.",
        )
        session.add(source)
        session.flush()
    return source


def _get_or_create_metrics(session: Session) -> dict[str, Metric]:
    metrics: dict[str, Metric] = {}
    for definition in METRICS.values():
        metric = session.scalar(select(Metric).where(Metric.key == definition.key))
        if metric is None:
            metric = Metric(key=definition.key)
            session.add(metric)
        metric.display_name = definition.display_name
        metric.domain = "emissions"
        metric.unit = definition.unit
        metric.cadence = definition.cadence
        metric.description = definition.description
        session.flush()
        metrics[definition.key] = metric
    return metrics


def store_atmosphere_rows(rows: list[NormalizedAtmosphereRow]) -> tuple[int, int]:
    engine = get_engine()
    with Session(engine) as session:
        try:
            source = _get_or_create_source(session)
            metrics = _get_or_create_metrics(session)
            inserted = 0
            updated = 0
            for row in rows:
                metric = metrics[row.metric_key]
                data_point = session.scalar(
                    select(DataPoint).where(
                        DataPoint.metric_id == metric.id,
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
                        )
                    )
                    inserted += 1
                else:
                    data_point.value = row.value
                    data_point.source_id = source.id
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
        rows = normalize_noaa_co2(fetch_noaa_csv())
        inserted, updated = store_atmosphere_rows(rows)
    except (AtmosphereIngestionError, SQLAlchemyError, RuntimeError) as exc:
        LOGGER.error("NOAA atmosphere ingestion stopped: %s", exc)
        return 1

    LOGGER.info("Loaded %d NOAA CO2 observations for %d metrics.", len(rows), len(METRICS))
    print(
        f"NOAA atmosphere ingestion complete: {inserted} row(s) inserted, "
        f"{updated} row(s) updated."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
