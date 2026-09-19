import os
import unittest
from contextlib import redirect_stdout
from datetime import date
from io import StringIO
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.app.models import Base, DataPoint, Metric, Source
from backend.pipeline import openaq_ingest


SAMPLE_READINGS = [
    {
        "datetime": {"utc": "2026-09-14T08:00:00Z"},
        "value": 10.0,
        "sensorsId": 1,
        "locationsId": 1,
    },
    {
        "datetime": {"utc": "2026-09-14T09:00:00Z"},
        "value": 20.0,
        "sensorsId": 2,
        "locationsId": 2,
    },
]


class OpenAQIngestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.original_api_key = os.environ.get("OPENAQ_API_KEY")
        os.environ["OPENAQ_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        self.engine.dispose()
        if self.original_api_key is None:
            os.environ.pop("OPENAQ_API_KEY", None)
        else:
            os.environ["OPENAQ_API_KEY"] = self.original_api_key

    def test_normalize_readings_uses_latest_utc_date_and_mean(self) -> None:
        row = openaq_ingest.normalize_readings(SAMPLE_READINGS)

        self.assertEqual(row.timestamp, date(2026, 9, 14))
        self.assertEqual(row.value, 15.0)
        self.assertEqual(row.reading_count, 2)

    def test_main_inserts_then_updates_one_daily_row(self) -> None:
        output = StringIO()
        with (
            patch.object(openaq_ingest, "fetch_latest_pm25", return_value=SAMPLE_READINGS),
            patch.object(openaq_ingest, "get_engine", return_value=self.engine),
            redirect_stdout(output),
        ):
            self.assertEqual(openaq_ingest.main(), 0)
            self.assertEqual(openaq_ingest.main(), 0)

        self.assertIn("1 row(s) inserted, 0 row(s) updated", output.getvalue())
        self.assertIn("0 row(s) inserted, 1 row(s) updated", output.getvalue())

        with Session(self.engine) as session:
            self.assertEqual(session.scalar(select(func.count(Source.id))), 1)
            self.assertEqual(session.scalar(select(func.count(Metric.id))), 1)
            self.assertEqual(session.scalar(select(func.count(DataPoint.id))), 1)
            stored = session.scalar(select(DataPoint))
            self.assertIsNotNone(stored)
            self.assertEqual(stored.value, 15.0)
            metric = session.scalar(select(Metric))
            self.assertEqual(metric.key, "reporting_station_pm25_mean_ug_m3")


if __name__ == "__main__":
    unittest.main()
