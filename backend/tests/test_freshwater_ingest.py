import unittest
from contextlib import redirect_stdout
from datetime import date
from io import StringIO
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.app.models import Base, DataPoint, Geography, Metric, Source
from backend.pipeline import freshwater_ingest


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.payload


class FakeHttp:
    def get(self, url: str, **_: object) -> FakeResponse:
        if url.endswith("/country"):
            return FakeResponse(
                [
                    {"page": 1},
                    [
                        {"id": "IND", "name": "India", "region": {"id": "SAS"}},
                        {"id": "AFE", "name": "Aggregate", "region": {"id": "NA"}},
                        {"id": "WLD", "name": "World", "region": {"id": "NA"}},
                    ],
                ]
            )
        indicator_code = url.rsplit("/", 1)[-1]
        return FakeResponse(
            [
                {"page": 1},
                [
                    {
                        "countryiso3code": "WLD",
                        "date": "2022",
                        "value": 100.0,
                        "indicator": {"id": indicator_code},
                    },
                    {
                        "countryiso3code": "IND",
                        "date": "2022",
                        "value": 50.0,
                        "indicator": {"id": indicator_code},
                    },
                    {"countryiso3code": "AFE", "date": "2022", "value": 75.0},
                    {"countryiso3code": "IND", "date": "2021", "value": None},
                ],
            ]
        )


class FreshwaterIngestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_fetch_normalizes_world_and_countries_only(self) -> None:
        rows = freshwater_ingest.fetch_freshwater_rows(FakeHttp())  # type: ignore[arg-type]
        self.assertEqual(len(rows), len(freshwater_ingest.METRICS) * 2)
        self.assertEqual({row.geography_code for row in rows}, {"WORLD", "IND"})
        self.assertEqual({row.timestamp for row in rows}, {date(2022, 1, 1)})

    def test_main_is_idempotent(self) -> None:
        rows = freshwater_ingest.fetch_freshwater_rows(FakeHttp())  # type: ignore[arg-type]
        output = StringIO()
        with (
            patch.object(freshwater_ingest, "get_engine", return_value=self.engine),
            patch.object(freshwater_ingest, "fetch_freshwater_rows", return_value=rows),
            redirect_stdout(output),
        ):
            self.assertEqual(freshwater_ingest.main(), 0)
            self.assertEqual(freshwater_ingest.main(), 0)

        row_count = len(rows)
        self.assertIn(f"{row_count} inserted, 0 updated", output.getvalue())
        self.assertIn(f"0 inserted, {row_count} updated", output.getvalue())
        with Session(self.engine) as session:
            self.assertEqual(session.scalar(select(func.count(Source.id))), 1)
            self.assertEqual(session.scalar(select(func.count(Metric.id))), len(freshwater_ingest.METRICS))
            self.assertEqual(session.scalar(select(func.count(Geography.id))), 2)
            self.assertEqual(session.scalar(select(func.count(DataPoint.id))), row_count)


if __name__ == "__main__":
    unittest.main()
