import unittest
from datetime import date

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.app.models import Base, DataPoint, Metric, Projection, Source
from backend.app.projection_service import create_projection
from backend.app.schemas import ProjectionRequest


class ProjectionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            source = Source(name="Test", url="https://example.com")
            session.add_all(
                [
                    Metric(
                        key="global_oil_reserves_billion_barrels",
                        display_name="Oil reserves",
                        domain="minerals",
                        unit="billion barrels",
                        cadence="annual",
                        data_points=[
                            DataPoint(timestamp=date(2024, 1, 1), value=100, source=source),
                            DataPoint(timestamp=date(2025, 1, 1), value=90, source=source),
                        ],
                    ),
                    Metric(
                        key="global_renewable_share_pct",
                        display_name="Renewable share",
                        domain="energy",
                        unit="%",
                        cadence="annual",
                        data_points=[
                            DataPoint(timestamp=date(2025, 1, 1), value=50, source=source)
                        ],
                    ),
                ]
            )
            session.commit()

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_finite_projection_uses_observed_decline(self) -> None:
        with Session(self.engine) as session:
            result = create_projection(
                session,
                "global_oil_reserves_billion_barrels",
                ProjectionRequest(rate_of_change_pct=0),
            )

        self.assertEqual(result.baseline_extraction_rate, 10)
        self.assertEqual(result.projected_depletion_year, 2034)
        self.assertFalse(result.beyond_modeled_horizon)

    def test_trend_projection_compounds_to_target_year(self) -> None:
        with Session(self.engine) as session:
            result = create_projection(
                session,
                "global_renewable_share_pct",
                ProjectionRequest(rate_of_change_pct=10, target_year=2027),
            )
            projection_count = session.scalar(select(func.count(Projection.id)))

        self.assertEqual(result.projected_value, 60.5)
        self.assertEqual(result.target_year, 2027)
        self.assertEqual(projection_count, 1)


if __name__ == "__main__":
    unittest.main()
