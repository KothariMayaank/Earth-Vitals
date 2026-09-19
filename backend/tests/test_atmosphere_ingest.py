import unittest
from datetime import date
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.app.models import Base, DataPoint, Metric
from backend.pipeline import atmosphere_ingest


SAMPLE_CSV = "# NOAA test fixture\nyear,month,decimal,average,average_unc,trend,trend_unc\n" + "\n".join(
    f"{year},{month},{year + month / 12:.3f},{400 + (year - 2023) * 3 + month / 10},0.1,400,0.1"
    for year in (2023, 2024)
    for month in range(1, 13)
)


class AtmosphereIngestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_normalize_builds_monthly_values_and_annual_growth(self) -> None:
        rows = atmosphere_ingest.normalize_noaa_co2(SAMPLE_CSV)
        self.assertEqual(len(rows), 25)
        growth = next(
            row
            for row in rows
            if row.metric_key == "global_atmospheric_co2_growth_ppm_per_year"
        )
        self.assertEqual(growth.timestamp, date(2024, 1, 1))
        self.assertEqual(growth.value, 3.0)

    def test_store_is_idempotent(self) -> None:
        rows = atmosphere_ingest.normalize_noaa_co2(SAMPLE_CSV)
        with patch.object(atmosphere_ingest, "get_engine", return_value=self.engine):
            self.assertEqual(atmosphere_ingest.store_atmosphere_rows(rows), (25, 0))
            self.assertEqual(atmosphere_ingest.store_atmosphere_rows(rows), (0, 25))

        with Session(self.engine) as session:
            self.assertEqual(session.scalar(select(func.count(Metric.id))), 2)
            self.assertEqual(session.scalar(select(func.count(DataPoint.id))), 25)


if __name__ == "__main__":
    unittest.main()
