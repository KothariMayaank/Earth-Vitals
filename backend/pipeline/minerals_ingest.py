"""Ingest annual global oil and lithium reserves from a normalized CSV."""

from __future__ import annotations

import logging
import math
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
from backend.app.models import DataPoint, Metric, Source


LOGGER = logging.getLogger(__name__)

REQUIRED_COLUMNS = {
    "metric_key",
    "year",
    "value",
    "source_name",
    "source_url",
    "source_notes",
}


@dataclass(frozen=True)
class MetricDefinition:
    key: str
    display_name: str
    unit: str
    description: str
    derived: bool = False


@dataclass(frozen=True)
class NormalizedMineralRow:
    metric_key: str
    timestamp: date
    value: float
    source_name: str
    source_url: str
    source_notes: str


RAW_METRICS = {
    "global_oil_reserves_billion_barrels": MetricDefinition(
        key="global_oil_reserves_billion_barrels",
        display_name="Global Proven Crude Oil Reserves",
        unit="billion barrels",
        description="Year-end global proven crude oil reserves.",
    ),
    "global_lithium_reserves_tonnes": MetricDefinition(
        key="global_lithium_reserves_tonnes",
        display_name="Global Lithium Reserves",
        unit="tonnes",
        description="Year-end global lithium reserves measured as lithium content.",
    ),
    "global_oil_production_billion_barrels": MetricDefinition(
        key="global_oil_production_billion_barrels",
        display_name="Global Crude Oil Production",
        unit="billion barrels/year",
        description="Annualized global crude oil production.",
    ),
    "global_lithium_production_tonnes": MetricDefinition(
        key="global_lithium_production_tonnes",
        display_name="Global Lithium Mine Production",
        unit="tonnes/year",
        description="Annual world mine production measured as lithium content; the USGS total excludes withheld U.S. production.",
    ),
    "global_copper_reserves_tonnes": MetricDefinition(
        key="global_copper_reserves_tonnes",
        display_name="Global Copper Reserves",
        unit="tonnes",
        description="Estimated global copper reserves measured as contained copper.",
    ),
    "global_copper_production_tonnes": MetricDefinition(
        key="global_copper_production_tonnes",
        display_name="Global Copper Mine Production",
        unit="tonnes/year",
        description="Annual global copper mine production measured as contained copper.",
    ),
    "global_cobalt_reserves_tonnes": MetricDefinition(
        key="global_cobalt_reserves_tonnes",
        display_name="Global Cobalt Reserves",
        unit="tonnes",
        description="Estimated global cobalt reserves measured as contained cobalt.",
    ),
    "global_cobalt_production_tonnes": MetricDefinition(
        key="global_cobalt_production_tonnes",
        display_name="Global Cobalt Mine Production",
        unit="tonnes/year",
        description="Annual global cobalt mine production measured as contained cobalt.",
    ),
    "global_nickel_reserves_tonnes": MetricDefinition(
        key="global_nickel_reserves_tonnes",
        display_name="Global Nickel Reserves (Lower Bound)",
        unit="tonnes",
        description="Conservative lower bound for global nickel reserves; USGS reports the total as greater than this value.",
    ),
    "global_nickel_production_tonnes": MetricDefinition(
        key="global_nickel_production_tonnes",
        display_name="Global Nickel Mine Production",
        unit="tonnes/year",
        description="Annual global nickel mine production measured as contained nickel.",
    ),
}

RESERVE_LIFE_PAIRS = {
    "oil": (
        "global_oil_reserves_billion_barrels",
        "global_oil_production_billion_barrels",
    ),
    "lithium": ("global_lithium_reserves_tonnes", "global_lithium_production_tonnes"),
    "copper": ("global_copper_reserves_tonnes", "global_copper_production_tonnes"),
    "cobalt": ("global_cobalt_reserves_tonnes", "global_cobalt_production_tonnes"),
    "nickel": ("global_nickel_reserves_tonnes", "global_nickel_production_tonnes"),
}

DERIVED_METRICS = {
    f"global_{commodity}_reserve_life_years": MetricDefinition(
        key=f"global_{commodity}_reserve_life_years",
        display_name=f"Global {commodity.title()} Static Reserve Life",
        unit="years",
        description=(
            "Static reserves-to-production ratio using the latest reported reserve and "
            "annual mine-production values. It is a snapshot, not a depletion forecast."
        ),
        derived=True,
    )
    for commodity in RESERVE_LIFE_PAIRS
}

METRICS = {**RAW_METRICS, **DERIVED_METRICS}


class MineralsIngestionError(RuntimeError):
    """An expected error that should stop this ingestion run cleanly."""


def resolve_csv_path(configured_path: str) -> Path:
    path = Path(configured_path).expanduser()
    return path if path.is_absolute() else REPO_ROOT / path


def load_mineral_rows(csv_path: Path) -> list[NormalizedMineralRow]:
    try:
        frame = pd.read_csv(csv_path)
    except FileNotFoundError as exc:
        raise MineralsIngestionError(f"Minerals CSV file was not found: {csv_path}") from exc
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        raise MineralsIngestionError(f"Could not read minerals CSV {csv_path}: {exc}") from exc

    missing_columns = REQUIRED_COLUMNS.difference(frame.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise MineralsIngestionError(f"Minerals CSV is missing required columns: {missing}")

    unexpected_metrics = set(frame["metric_key"].dropna()).difference(RAW_METRICS)
    if unexpected_metrics:
        keys = ", ".join(sorted(unexpected_metrics))
        raise MineralsIngestionError(f"Minerals CSV contains unsupported metrics: {keys}")

    missing_metrics = set(RAW_METRICS).difference(frame["metric_key"].dropna())
    if missing_metrics:
        keys = ", ".join(sorted(missing_metrics))
        raise MineralsIngestionError(f"Minerals CSV is missing metrics: {keys}")

    frame["year"] = pd.to_numeric(frame["year"], errors="coerce")
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    required_values = list(REQUIRED_COLUMNS)
    if frame[required_values].isna().any(axis=None):
        raise MineralsIngestionError("Minerals CSV contains blank or invalid required values.")
    if frame.duplicated(subset=["metric_key", "year"]).any():
        raise MineralsIngestionError(
            "Minerals CSV contains duplicate metric/year rows."
        )

    rows: list[NormalizedMineralRow] = []
    for record in frame.sort_values(["metric_key", "year"]).itertuples(index=False):
        value = float(record.value)
        if not math.isfinite(value) or value < 0:
            raise MineralsIngestionError(
                f"Minerals CSV contains an invalid value for {record.metric_key}."
            )
        rows.append(
            NormalizedMineralRow(
                metric_key=record.metric_key,
                timestamp=date(int(record.year), 1, 1),
                value=value,
                source_name=record.source_name,
                source_url=record.source_url,
                source_notes=record.source_notes,
            )
        )

    # Reserve life is intentionally derived rather than copied from a source.
    # It assumes production remains constant and reserves receive no additions,
    # so it must not be interpreted as a forecasted exhaustion date.
    by_key_year = {(row.metric_key, row.timestamp.year): row for row in rows}
    for commodity, (reserve_key, production_key) in RESERVE_LIFE_PAIRS.items():
        years = {
            year
            for metric_key, year in by_key_year
            if metric_key == reserve_key and (production_key, year) in by_key_year
        }
        for year in sorted(years):
            reserve = by_key_year[(reserve_key, year)]
            production = by_key_year[(production_key, year)]
            if production.value <= 0:
                raise MineralsIngestionError(
                    f"Cannot derive reserve life for {commodity}: production must be positive."
                )
            rows.append(
                NormalizedMineralRow(
                    metric_key=f"global_{commodity}_reserve_life_years",
                    timestamp=date(year, 1, 1),
                    value=reserve.value / production.value,
                    source_name=reserve.source_name,
                    source_url=reserve.source_url,
                    source_notes=(
                        f"Derived by Earth Vitals from {commodity} reserves and annual "
                        "production reported by the cited source."
                    ),
                )
            )
    return rows


def _get_or_create_sources(
    session: Session, rows: list[NormalizedMineralRow]
) -> dict[str, Source]:
    sources: dict[str, Source] = {}
    for row in rows:
        if row.source_name in sources:
            continue
        source = session.scalar(select(Source).where(Source.name == row.source_name))
        if source is None:
            source = Source(
                name=row.source_name,
                url=row.source_url,
                notes=row.source_notes,
            )
            session.add(source)
            session.flush()
        sources[row.source_name] = source
    return sources


def _get_or_create_metrics(session: Session) -> dict[str, Metric]:
    metrics: dict[str, Metric] = {}
    for definition in METRICS.values():
        metric = session.scalar(select(Metric).where(Metric.key == definition.key))
        if metric is None:
            metric = Metric(
                key=definition.key,
                display_name=definition.display_name,
                domain="minerals",
                unit=definition.unit,
                cadence="annual",
                description=definition.description,
            )
            session.add(metric)
            session.flush()
        metrics[definition.key] = metric
    return metrics


def store_mineral_rows(rows: list[NormalizedMineralRow]) -> tuple[int, int]:
    engine = get_engine()
    with Session(engine) as session:
        try:
            sources = _get_or_create_sources(session, rows)
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
                            source_id=sources[row.source_name].id,
                        )
                    )
                    inserted += 1
                else:
                    data_point.value = row.value
                    data_point.source_id = sources[row.source_name].id
                    updated += 1

            session.commit()
            return inserted, updated
        except SQLAlchemyError:
            session.rollback()
            raise


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    load_dotenv(REPO_ROOT / ".env")
    configured_path = os.getenv("MINERALS_DATA_CSV_PATH")
    if not configured_path:
        LOGGER.error(
            "MINERALS_DATA_CSV_PATH is required. Add it to the root .env file."
        )
        return 1

    csv_path = resolve_csv_path(configured_path)
    try:
        rows = load_mineral_rows(csv_path)
        inserted, updated = store_mineral_rows(rows)
    except (MineralsIngestionError, SQLAlchemyError, RuntimeError) as exc:
        LOGGER.error("Minerals ingestion stopped: %s", exc)
        return 1

    LOGGER.info(
        "Loaded %d minerals rows covering %d source(s).",
        len(rows),
        len({row.source_name for row in rows}),
    )
    print(
        f"Minerals ingestion complete: {inserted} row(s) inserted, "
        f"{updated} row(s) updated."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
