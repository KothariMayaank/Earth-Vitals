import unittest
from datetime import date

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.index_config import NORMALIZATION_RULES
from backend.app.index_service import (
    compute_current_index,
    normalize_metric,
    seed_default_index_weights,
    update_index_weights,
)
from backend.app.models import Base, DataPoint, Geography, Metric, Source
from backend.app.schemas import IndexWeights


CURRENT_VALUES = {
    "global_renewable_share_pct": 40.0,
    "global_electricity_generation_twh": 30_000.0,
    "global_oil_reserves_billion_barrels": 1_300.0,
    "global_lithium_reserves_tonnes": 35_000_000.0,
    "reporting_station_pm25_mean_ug_m3": 20.0,
    "global_atmospheric_co2_ppm": 400.0,
}


class IndexServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            source = Source(name="Test", url="https://example.com")
            world = Geography(code="WORLD", name="World", type="global")
            for key, value in CURRENT_VALUES.items():
                rule = NORMALIZATION_RULES[key]
                session.add(
                    Metric(
                        key=key,
                        display_name=key,
                        domain=rule.domain,
                        unit="test",
                        cadence="annual",
                        data_points=[
                            DataPoint(
                                timestamp=date(2025, 1, 1),
                                value=value,
                                source=source,
                                geography=world,
                            )
                        ],
                    )
                )
            seed_default_index_weights(session)
            session.commit()

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_normalization_endpoints_and_clamping(self) -> None:
        for rule in NORMALIZATION_RULES.values():
            self.assertEqual(normalize_metric(rule.concerning, rule), 0.0)
            self.assertEqual(normalize_metric(rule.healthy, rule), 100.0)
            beyond_healthy = rule.healthy + (rule.healthy - rule.concerning)
            self.assertEqual(normalize_metric(beyond_healthy, rule), 100.0)

    def test_equal_weights_compute_domain_and_composite_scores(self) -> None:
        with Session(self.engine) as session:
            result = compute_current_index(session)

        self.assertEqual(result.domain_scores.energy, 50.0)
        self.assertEqual(result.domain_scores.minerals, 50.0)
        self.assertEqual(result.domain_scores.emissions, 50.0)
        self.assertEqual(result.composite_score, 50.0)

    def test_weight_update_recomputes_and_persists(self) -> None:
        with Session(self.engine) as session:
            result = update_index_weights(
                session,
                IndexWeights(energy=0.5, minerals=0.3, emissions=0.2),
            )
            persisted = compute_current_index(session)

        self.assertEqual(result.weights.energy, 0.5)
        self.assertEqual(persisted.weights.emissions, 0.2)

    def test_weights_require_valid_range_and_sum(self) -> None:
        with self.assertRaises(ValidationError):
            IndexWeights(energy=0.7, minerals=0.7, emissions=-0.4)
        with self.assertRaises(ValidationError):
            IndexWeights(energy=0.2, minerals=0.2, emissions=0.2)


if __name__ == "__main__":
    unittest.main()
