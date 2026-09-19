"""Configuration for simplified, exploratory projection models.

These settings are not forecasts and are not IPCC-grade models. They make a
small set of assumptions explicit so the UI can help users explore a scenario.
Finite-resource models prefer a depletion rate derived from observed reserve
decline. Until the reserves datasets contain at least two declining years, the
configured official production figures are used as transparent fallbacks.
"""

from dataclasses import dataclass
from typing import Literal


ProjectionKind = Literal["finite_resource", "trend"]


@dataclass(frozen=True)
class ProjectionRule:
    kind: ProjectionKind
    minimum_value: float = 0.0
    maximum_value: float | None = None
    fallback_annual_extraction: float | None = None
    fallback_source: str | None = None


MAX_PROJECTION_YEARS = 200
DEPLETION_THRESHOLD_FRACTION = 0.01
DEFAULT_TREND_HORIZON_YEARS = 25


PROJECTION_RULES: dict[str, ProjectionRule] = {
    "global_oil_reserves_billion_barrels": ProjectionRule(
        kind="finite_resource",
        # OPEC ASB 2026 reports 74.85 million barrels/day of world crude output
        # in 2025: 74.85 * 365 / 1000 = 27.32025 billion barrels/year.
        fallback_annual_extraction=27.32025,
        fallback_source=(
            "OPEC Annual Statistical Bulletin 2026 world crude production "
            "(74.85 million barrels/day in 2025)"
        ),
    ),
    "global_lithium_reserves_tonnes": ProjectionRule(
        kind="finite_resource",
        # USGS Mineral Commodity Summaries 2026 reports estimated 2025 world
        # mine production of 290,000 tonnes of lithium content.
        fallback_annual_extraction=290_000.0,
        fallback_source="USGS Mineral Commodity Summaries 2026",
    ),
    "global_copper_reserves_tonnes": ProjectionRule(
        kind="finite_resource",
        fallback_annual_extraction=23_000_000.0,
        fallback_source="USGS Mineral Commodity Summaries 2026",
    ),
    "global_cobalt_reserves_tonnes": ProjectionRule(
        kind="finite_resource",
        fallback_annual_extraction=310_000.0,
        fallback_source="USGS Mineral Commodity Summaries 2026",
    ),
    "global_nickel_reserves_tonnes": ProjectionRule(
        kind="finite_resource",
        fallback_annual_extraction=3_900_000.0,
        fallback_source="USGS Mineral Commodity Summaries 2026 (reserve value is a lower bound)",
    ),
    "global_renewable_share_pct": ProjectionRule(
        kind="trend",
        minimum_value=0.0,
        maximum_value=100.0,
    ),
    "global_electricity_generation_twh": ProjectionRule(
        kind="trend",
        minimum_value=0.0,
    ),
    "global_clean_electricity_share_pct": ProjectionRule(
        kind="trend", minimum_value=0.0, maximum_value=100.0
    ),
    "global_fossil_electricity_share_pct": ProjectionRule(
        kind="trend", minimum_value=0.0, maximum_value=100.0
    ),
    "global_wind_solar_share_pct": ProjectionRule(
        kind="trend", minimum_value=0.0, maximum_value=100.0
    ),
    "reporting_station_pm25_mean_ug_m3": ProjectionRule(
        kind="trend",
        minimum_value=0.0,
    ),
    "global_atmospheric_co2_ppm": ProjectionRule(
        kind="trend",
        minimum_value=0.0,
    ),
    "global_atmospheric_co2_growth_ppm_per_year": ProjectionRule(
        kind="trend",
    ),
    # Supported for the original Phase 1 sample metric if it is present.
    "sample_global_co2_ppm": ProjectionRule(
        kind="trend",
        minimum_value=0.0,
    ),
}
