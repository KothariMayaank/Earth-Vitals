import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import get_engine  # noqa: E402
from app.models import Base, DataPoint, Metric, Source  # noqa: E402


SAMPLE_METRIC_KEY = "sample_global_co2_ppm"


def main() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        existing_metric = session.scalar(
            select(Metric).where(Metric.key == SAMPLE_METRIC_KEY)
        )
        if existing_metric is not None:
            print(f'Sample metric "{SAMPLE_METRIC_KEY}" is already seeded.')
        else:
            source = Source(
                name="Sample Climate Observatory",
                url="https://example.com/earth-vitals-sample",
                notes="Fake source used only to verify the schema.",
            )
            metric = Metric(
                key=SAMPLE_METRIC_KEY,
                display_name="Sample Global CO2",
                domain="emissions",
                unit="ppm",
                cadence="daily",
                description="Fake metric used only to verify the schema.",
            )
            start_date = date(2026, 1, 1)
            metric.data_points = [
                DataPoint(
                    timestamp=start_date + timedelta(days=offset),
                    value=420.0 + offset * 0.25,
                    source=source,
                )
                for offset in range(5)
            ]
            session.add(metric)
            session.commit()
            print("Inserted one sample source, one sample metric, and five data points.")

        seeded_metric = session.scalar(
            select(Metric)
            .where(Metric.key == SAMPLE_METRIC_KEY)
            .options(selectinload(Metric.data_points).selectinload(DataPoint.source))
        )
        if seeded_metric is None:
            raise RuntimeError("Sample metric was not found after seeding.")

        print("\nSeeded rows:")
        sample_source = seeded_metric.data_points[0].source
        print(
            f"Source(id={sample_source.id}, name={sample_source.name!r}, "
            f"url={sample_source.url!r})"
        )
        print(
            f"Metric(id={seeded_metric.id}, key={seeded_metric.key!r}, "
            f"display_name={seeded_metric.display_name!r})"
        )
        for point in sorted(seeded_metric.data_points, key=lambda row: row.timestamp):
            print(
                f"DataPoint(id={point.id}, timestamp={point.timestamp}, "
                f"value={point.value}, source={point.source.name!r})"
            )


if __name__ == "__main__":
    main()
