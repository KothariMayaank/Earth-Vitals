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


SAMPLE_CSV = """Area,Year,Category,Variable,Unit,Value
World,2023,Electricity generation,Renewables,%,30.0
World,2024,Electricity generation,Renewables,%,32.0
World,2023,Electricity generation,Total Generation,TWh,29000.0
World,2024,Electricity generation,Total Generation,TWh,30000.0
France,2024,Electricity generation,Renewables,%,25.0
"""


class EnergyIngestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.temp_dir.name) / "ember.csv"
        self.csv_path.write_text(SAMPLE_CSV, encoding="utf-8")
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

        self.assertEqual(len(rows), 4)
        self.assertEqual({row.timestamp.year for row in rows}, {2023, 2024})
        self.assertEqual(
            {row.metric_key for row in rows},
            {
                "global_renewable_share_pct",
                "global_electricity_generation_twh",
            },
        )

    def test_main_inserts_then_updates_annual_rows(self) -> None:
        output = StringIO()
        with (
            patch.object(energy_ingest, "get_engine", return_value=self.engine),
            redirect_stdout(output),
        ):
            self.assertEqual(energy_ingest.main(), 0)
            self.assertEqual(energy_ingest.main(), 0)

        self.assertIn("4 row(s) inserted, 0 row(s) updated", output.getvalue())
        self.assertIn("0 row(s) inserted, 4 row(s) updated", output.getvalue())

        with Session(self.engine) as session:
            self.assertEqual(session.scalar(select(func.count(Source.id))), 1)
            self.assertEqual(session.scalar(select(func.count(Metric.id))), 2)
            self.assertEqual(session.scalar(select(func.count(DataPoint.id))), 4)


if __name__ == "__main__":
    unittest.main()
