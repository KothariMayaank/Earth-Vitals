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
from backend.pipeline import minerals_ingest


class MineralsIngestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.temp_dir.name) / "minerals.csv"
        lines = ["metric_key,year,value,source_name,source_url,source_notes"]
        for index, key in enumerate(minerals_ingest.RAW_METRICS):
            source = "OPEC" if "oil" in key else "USGS"
            lines.append(
                f"{key},2025,{1000 + index},{source},https://example.com/{source.lower()},Test data"
            )
        self.csv_path.write_text("\n".join(lines), encoding="utf-8")
        self.original_csv_path = os.environ.get("MINERALS_DATA_CSV_PATH")
        os.environ["MINERALS_DATA_CSV_PATH"] = str(self.csv_path)

    def tearDown(self) -> None:
        self.engine.dispose()
        self.temp_dir.cleanup()
        if self.original_csv_path is None:
            os.environ.pop("MINERALS_DATA_CSV_PATH", None)
        else:
            os.environ["MINERALS_DATA_CSV_PATH"] = self.original_csv_path

    def test_load_mineral_rows_validates_required_metrics(self) -> None:
        rows = minerals_ingest.load_mineral_rows(self.csv_path)

        self.assertEqual(len(rows), len(minerals_ingest.METRICS))
        self.assertEqual(
            {row.metric_key for row in rows},
            set(minerals_ingest.METRICS),
        )

    def test_main_inserts_then_updates_rows(self) -> None:
        output = StringIO()
        with (
            patch.object(minerals_ingest, "get_engine", return_value=self.engine),
            redirect_stdout(output),
        ):
            self.assertEqual(minerals_ingest.main(), 0)
            self.assertEqual(minerals_ingest.main(), 0)

        row_count = len(minerals_ingest.METRICS)
        self.assertIn(f"{row_count} row(s) inserted, 0 row(s) updated", output.getvalue())
        self.assertIn(f"0 row(s) inserted, {row_count} row(s) updated", output.getvalue())

        with Session(self.engine) as session:
            self.assertEqual(session.scalar(select(func.count(Source.id))), 2)
            self.assertEqual(session.scalar(select(func.count(Metric.id))), row_count)
            self.assertEqual(session.scalar(select(func.count(DataPoint.id))), row_count)


if __name__ == "__main__":
    unittest.main()
