import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.main import (
    country_metric_history,
    country_summary,
    domain_summary,
    metric_map,
)
from backend.app.models import Base, DataPoint, Geography, Metric, Source


class GeographyApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            source = Source(name="Ember", url="https://example.com")
            world = Geography(code="WORLD", name="World", type="global")
            india = Geography(code="IND", name="India", type="country")
            metric = Metric(
                key="global_renewable_share_pct",
                display_name="Global Renewable Electricity Share",
                domain="energy",
                unit="%",
                cadence="annual",
                description="Test metric",
            )
            session.add_all([source, world, india, metric])
            session.flush()
            session.add_all(
                [
                    DataPoint(metric=metric, geography=world, source=source, timestamp=date(2025, 1, 1), value=33.0),
                    DataPoint(metric=metric, geography=india, source=source, timestamp=date(2024, 1, 1), value=21.0),
                    DataPoint(metric=metric, geography=india, source=source, timestamp=date(2025, 1, 1), value=24.0),
                ]
            )
            session.commit()

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_global_summary_does_not_mix_country_values(self) -> None:
        with Session(self.engine) as session:
            summary = domain_summary("energy", session)
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0].value, 33.0)

    def test_country_summary_history_and_map(self) -> None:
        with Session(self.engine) as session:
            summary = country_summary("IND", session, "energy")
            history = country_metric_history("IND", "global_renewable_share_pct", session)
            map_result = metric_map("global_renewable_share_pct", session, None)
        self.assertEqual(summary[0].value, 24.0)
        self.assertEqual([point.value for point in history], [21.0, 24.0])
        self.assertEqual(map_result.points[0].code, "IND")


if __name__ == "__main__":
    unittest.main()
