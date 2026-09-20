"""Reviewable normalization assumptions for the Planetary Health Index.

Every rule maps one raw metric onto a 0-100 score using two endpoints:
``concerning`` maps to 0 and ``healthy`` maps to 100. Values between the
endpoints are interpolated linearly and values outside them are clamped. The
endpoints may be descending, which naturally handles metrics where lower is
better.

These rules are policy choices, not scientific findings. They are deliberately
centralized here so they can be reviewed, cited, versioned, and replaced with
expert-approved thresholds without changing any API or calculation code.
"""

from dataclasses import dataclass
from typing import Literal


Domain = Literal["energy", "minerals", "emissions", "freshwater"]


@dataclass(frozen=True)
class NormalizationRule:
    domain: Domain
    concerning: float
    healthy: float
    rationale: str


NORMALIZATION_RULES: dict[str, NormalizationRule] = {
    "global_renewable_share_pct": NormalizationRule(
        domain="energy",
        concerning=20.0,
        healthy=60.0,
        rationale=(
            "Higher renewable penetration is treated as healthier. Twenty percent "
            "represents a fossil-heavy electricity mix; sixty percent is an ambitious "
            "but attainable transition benchmark. This scores generation share, not "
            "total-energy decarbonization or grid reliability."
        ),
    ),
    "global_electricity_generation_twh": NormalizationRule(
        domain="energy",
        concerning=40_000.0,
        healthy=20_000.0,
        rationale=(
            "Until the MVP has demand efficiency and energy-access metrics, lower total "
            "generation is used as a rough proxy for lower material and ecological "
            "pressure. This is the weakest assumption in the index: electricity access "
            "is beneficial and clean generation has lower impact. It should be replaced "
            "by carbon intensity or per-capita demand when those data are ingested."
        ),
    ),
    "global_oil_reserves_billion_barrels": NormalizationRule(
        domain="minerals",
        concerning=1_800.0,
        healthy=800.0,
        rationale=(
            "A larger proved-oil inventory is treated as greater potential future carbon "
            "lock-in, so lower is scored better. Reserves also fall through extraction, "
            "which is not itself healthy; this proxy should eventually be paired with "
            "production and demand data."
        ),
    ),
    "global_lithium_reserves_tonnes": NormalizationRule(
        domain="minerals",
        concerning=20_000_000.0,
        healthy=50_000_000.0,
        rationale=(
            "Larger identified lithium reserves are treated as healthier for transition "
            "security because they reduce near-term scarcity risk for storage and "
            "electrification. The score does not yet account for mining impacts, reserve "
            "quality, geographic concentration, or recycling."
        ),
    ),
    "reporting_station_pm25_mean_ug_m3": NormalizationRule(
        domain="emissions",
        concerning=35.0,
        healthy=5.0,
        rationale=(
            "Lower PM2.5 concentration is healthier: "
            "5 µg/m³ reflects the WHO annual guideline and 35 µg/m³ represents clearly "
            "unhealthy chronic exposure. This availability-based reporting-station mean "
            "is not population weighted and can hide both coverage gaps and local extremes."
        ),
    ),
    "global_atmospheric_co2_ppm": NormalizationRule(
        domain="emissions",
        concerning=450.0,
        healthy=350.0,
        rationale=(
            "Lower atmospheric CO2 is scored better. The 350–450 ppm range is an "
            "explicit communication scale rather than a claim of a sharp physical safety "
            "boundary; the index is exploratory and should be read alongside the raw trend."
        ),
    ),
    "freshwater_resources_per_capita_m3": NormalizationRule(
        domain="freshwater",
        concerning=500.0,
        healthy=1_700.0,
        rationale=(
            "Higher renewable freshwater availability per person is scored better. "
            "FAO describes less than 500 m³/person/year as absolute water stress and "
            "1,700 m³/person/year or less as moderate scarcity. These thresholds are "
            "national-scale screening values: they do not capture seasonality, basin-level "
            "distribution, groundwater depletion, infrastructure, or water quality."
        ),
    ),
    "freshwater_withdrawals_pct_resources": NormalizationRule(
        domain="freshwater",
        concerning=100.0,
        healthy=25.0,
        rationale=(
            "Lower withdrawal pressure is scored better. The 25% healthy endpoint and "
            "100% concerning endpoint mirror the UN-Water/FAO water-stress severity "
            "bands (no stress below 25%; critical above 100%). This WDI series uses "
            "internal renewable resources and is not identical to SDG 6.4.2 because it "
            "does not deduct environmental flow requirements."
        ),
    ),
    "safe_drinking_water_access_pct": NormalizationRule(
        domain="freshwater",
        concerning=50.0,
        healthy=100.0,
        rationale=(
            "Higher safely managed drinking-water coverage is scored better. One hundred "
            "percent reflects SDG 6.1's universal-access objective. Fifty percent is an "
            "explicit index floor, not an official UN threshold: at that point at least "
            "half the population lacks a service that is on premises, available when "
            "needed, and free from priority contamination."
        ),
    ),
}
