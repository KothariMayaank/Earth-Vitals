import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.app.models import Base, DataPoint, Metric, Source
from backend.pipeline import energy_ingest


class EnergyIngestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.temp_dir.name) / "ember.csv"
        lines = ["Area,ISO 3 code,Year,Area type,Category,Variable,Unit,Value"]
        for index, definition in enumerate(energy_ingest.METRICS):
            for year in (2023, 2024):
                lines.append(
                    f"World,,{year},Region,Electricity generation,{definition.variable},"
                    f"{definition.unit},{100 + index + year - 2023}"
                )
        lines.append("France,FRA,2024,Country or economy,Electricity generation,Renewables,%,25.0")
        self.csv_path.write_text("\n".join(lines), encoding="utf-8")
        self.original_csv_path = os.environ.get("ENERGY_DATA_CSV_PATH")
        os.environ["ENERGY_DATA_CSV_PATH"] = str(self.csv_path)

    def tearDown(self) -> None:
        self.engine.dispose()
        self.temp_dir.cleanup()
        if self.original_csv_path is None:
            os.environ.pop("ENERGY_DATA_CSV_PATH", None)
        else:
            os.environ["ENERGY_DATA_CSV_PATH"] = self.original_csv_path

    def test_load_energy_rows_selects_world_metrics(self) -> None:
        rows = energy_ingest.load_energy_rows(self.csv_path)

        self.assertEqual(len(rows), len(energy_ingest.METRICS) * 2 + 1)
        self.assertEqual({row.timestamp.year for row in rows}, {2023, 2024})
        self.assertEqual(
            {row.metric_key for row in rows},
            {definition.key for definition in energy_ingest.METRICS},
        )

    def test_main_inserts_then_updates_annual_rows(self) -> None:
        output = StringIO()
        with (
            patch.object(energy_ingest, "get_engine", return_value=self.engine),
            redirect_stdout(output),
        ):
            self.assertEqual(energy_ingest.main(), 0)
            self.assertEqual(energy_ingest.main(), 0)

        row_count = len(energy_ingest.METRICS) * 2 + 1
        self.assertIn(f"{row_count} row(s) inserted, 0 row(s) updated", output.getvalue())
        self.assertIn(f"0 row(s) inserted, {row_count} row(s) updated", output.getvalue())

        with Session(self.engine) as session:
            self.assertEqual(session.scalar(select(func.count(Source.id))), 1)
            self.assertEqual(
                session.scalar(select(func.count(Metric.id))), len(energy_ingest.METRICS)
            )
            self.assertEqual(session.scalar(select(func.count(DataPoint.id))), row_count)


if __name__ == "__main__":
    unittest.main()
