"""Ingest global and country annual electricity metrics from Ember's CSV."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.database import REPO_ROOT, get_engine
from backend.app.geographies import get_or_create_geography, get_or_create_world_geography
from backend.app.models import DataPoint, Geography, Metric, Source


LOGGER = logging.getLogger(__name__)

EMBER_SOURCE_URL = "https://ember-energy.org/data/yearly-electricity-data/"
REQUIRED_COLUMNS = {
    "Area",
    "ISO 3 code",
    "Year",
    "Area type",
    "Category",
    "Variable",
    "Unit",
    "Value",
}


@dataclass(frozen=True)
class MetricDefinition:
    key: str
    display_name: str
    variable: str
    unit: str
    description: str


@dataclass(frozen=True)
class NormalizedEnergyRow:
    metric_key: str
    geography_code: str
    geography_name: str
    geography_type: str
    timestamp: date
    value: float


METRICS = (
    MetricDefinition(
        key="global_renewable_share_pct",
        display_name="Global Renewable Electricity Share",
        variable="Renewables",
        unit="%",
        description="Renewables as a share of global electricity generation.",
    ),
    MetricDefinition(
        key="global_electricity_generation_twh",
        display_name="Global Electricity Generation",
        variable="Total Generation",
        unit="TWh",
        description="Total annual electricity generation worldwide.",
    ),
    MetricDefinition(
        key="global_clean_electricity_share_pct",
        display_name="Global Clean Electricity Share",
        variable="Clean",
        unit="%",
        description="Wind, solar, hydro, bioenergy, other renewables, and nuclear as a share of global electricity generation.",
    ),
    MetricDefinition(
        key="global_fossil_electricity_share_pct",
        display_name="Global Fossil Electricity Share",
        variable="Fossil",
        unit="%",
        description="Coal, gas, and other fossil fuels as a share of global electricity generation.",
    ),
    MetricDefinition(
        key="global_renewable_generation_twh",
        display_name="Global Renewable Electricity Generation",
        variable="Renewables",
        unit="TWh",
        description="Annual global electricity generation from renewable sources.",
    ),
    MetricDefinition(
        key="global_coal_generation_twh",
        display_name="Global Coal Electricity Generation",
        variable="Coal",
        unit="TWh",
        description="Annual global electricity generation from coal.",
    ),
    MetricDefinition(
        key="global_gas_generation_twh",
        display_name="Global Gas Electricity Generation",
        variable="Gas",
        unit="TWh",
        description="Annual global electricity generation from fossil gas.",
    ),
    MetricDefinition(
        key="global_solar_generation_twh",
        display_name="Global Solar Electricity Generation",
        variable="Solar",
        unit="TWh",
        description="Annual global electricity generation from solar power.",
    ),
    MetricDefinition(
        key="global_wind_generation_twh",
        display_name="Global Wind Electricity Generation",
        variable="Wind",
        unit="TWh",
        description="Annual global electricity generation from wind power.",
    ),
    MetricDefinition(
        key="global_nuclear_generation_twh",
        display_name="Global Nuclear Electricity Generation",
        variable="Nuclear",
        unit="TWh",
        description="Annual global electricity generation from nuclear power.",
    ),
    MetricDefinition(
        key="global_wind_solar_share_pct",
        display_name="Global Wind and Solar Share",
        variable="Wind and Solar",
        unit="%",
        description="Wind and solar combined as a share of global electricity generation.",
    ),
)


class EnergyIngestionError(RuntimeError):
    """An expected error that should stop this ingestion run cleanly."""


def resolve_csv_path(configured_path: str) -> Path:
    path = Path(configured_path).expanduser()
    return path if path.is_absolute() else REPO_ROOT / path


def load_energy_rows(csv_path: Path) -> list[NormalizedEnergyRow]:
    try:
        frame = pd.read_csv(csv_path, usecols=lambda column: column in REQUIRED_COLUMNS)
    except FileNotFoundError as exc:
        raise EnergyIngestionError(f"Ember CSV file was not found: {csv_path}") from exc
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        raise EnergyIngestionError(f"Could not read Ember CSV {csv_path}: {exc}") from exc

    missing_columns = REQUIRED_COLUMNS.difference(frame.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise EnergyIngestionError(f"Ember CSV is missing required columns: {missing}")

    frame["Year"] = pd.to_numeric(frame["Year"], errors="coerce")
    frame["Value"] = pd.to_numeric(frame["Value"], errors="coerce")
    generation = frame[frame["Category"] == "Electricity generation"].copy()
    generation["geography_code"] = generation["ISO 3 code"].fillna("")
    generation.loc[generation["Area"] == "World", "geography_code"] = "WORLD"
    generation = generation[
        (generation["Area"] == "World")
        | (
            (generation["Area type"] == "Country or economy")
            & generation["geography_code"].str.fullmatch(r"[A-Z]{3}")
        )
    ]

    rows: list[NormalizedEnergyRow] = []
    for definition in METRICS:
        selected = generation[
            (generation["Variable"] == definition.variable)
            & (generation["Unit"] == definition.unit)
        ].dropna(subset=["Year", "Value"])

        duplicate_years = selected[
            selected.duplicated(subset=["geography_code", "Year"], keep=False)
        ]
        if not duplicate_years.empty:
            raise EnergyIngestionError(
                f"Ember CSV contains duplicate geography/{definition.variable}/"
                f"{definition.unit} rows for the same year."
            )
        if selected[selected["geography_code"] == "WORLD"].empty:
            raise EnergyIngestionError(
                f"Ember CSV has no World/{definition.variable}/{definition.unit} rows."
            )

        rows.extend(
            NormalizedEnergyRow(
                metric_key=definition.key,
                geography_code=record.geography_code,
                geography_name=record.Area,
                geography_type="global" if record.geography_code == "WORLD" else "country",
                timestamp=date(int(record.Year), 1, 1),
                value=float(record.Value),
            )
            for record in selected.sort_values(["geography_code", "Year"]).itertuples(index=False)
        )

    return rows


def _get_or_create_source(session: Session) -> Source:
    source = session.scalar(select(Source).where(Source.name == "Ember"))
    if source is None:
        source = Source(
            name="Ember",
            url=EMBER_SOURCE_URL,
            notes="Free annual global electricity generation and power-sector data.",
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
                domain="energy",
                unit=definition.unit,
                cadence="annual",
                description=definition.description,
            )
            session.add(metric)
            session.flush()
        metrics[definition.key] = metric
    return metrics


def store_energy_rows(rows: list[NormalizedEnergyRow]) -> tuple[int, int]:
    engine = get_engine()
    with Session(engine) as session:
        try:
            source = _get_or_create_source(session)
            metrics = _get_or_create_metrics(session)
            geographies: dict[str, Geography] = {}
            for row in rows:
                if row.geography_code in geographies:
                    continue
                if row.geography_code == "WORLD":
                    geography = get_or_create_world_geography(session)
                else:
                    geography = get_or_create_geography(
                        session,
                        code=row.geography_code,
                        name=row.geography_name,
                        geography_type=row.geography_type,
                    )
                geographies[row.geography_code] = geography

            metric_ids = [metric.id for metric in metrics.values()]
            geography_ids = [geography.id for geography in geographies.values()]
            existing_points = {
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
                data_point = existing_points.get(
                    (metric.id, geography.id, row.timestamp)
                )
                if data_point is None:
                    data_point = DataPoint(
                        metric_id=metric.id,
                        geography_id=geography.id,
                        timestamp=row.timestamp,
                        value=row.value,
                        source_id=source.id,
                    )
                    session.add(data_point)
                    existing_points[(metric.id, geography.id, row.timestamp)] = data_point
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
    configured_path = os.getenv("ENERGY_DATA_CSV_PATH")
    if not configured_path:
        LOGGER.error(
            "ENERGY_DATA_CSV_PATH is required. Add the Ember CSV path to the root .env file."
        )
        return 1

    csv_path = resolve_csv_path(configured_path)
    try:
        rows = load_energy_rows(csv_path)
        inserted, updated = store_energy_rows(rows)
    except (EnergyIngestionError, SQLAlchemyError, RuntimeError) as exc:
        LOGGER.error("Ember energy ingestion stopped: %s", exc)
        return 1

    years = sorted({row.timestamp.year for row in rows})
    LOGGER.info(
        "Loaded %d Ember rows for %d metrics and %d geographies covering %d–%d.",
        len(rows),
        len(METRICS),
        len({row.geography_code for row in rows}),
        years[0],
        years[-1],
    )
    print(
        f"Ember ingestion complete: {inserted} row(s) inserted, "
        f"{updated} row(s) updated."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
