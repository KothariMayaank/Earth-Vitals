from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import DataPoint, Metric, Projection
from backend.app.projection_config import (
    DEFAULT_TREND_HORIZON_YEARS,
    DEPLETION_THRESHOLD_FRACTION,
    MAX_PROJECTION_YEARS,
    PROJECTION_RULES,
    ProjectionRule,
)
from backend.app.schemas import ProjectionPoint, ProjectionRequest, ProjectionResponse


METHODOLOGY_CAVEAT = (
    "This is a simplified exploratory scenario, not an IPCC-grade forecast. "
    "It holds the selected percentage-change assumption constant, omits policy, "
    "technology, price, discovery, recycling, feedback, and uncertainty effects, "
    "and should not be used for operational or investment decisions."
)


class ProjectionInputError(ValueError):
    pass


@dataclass(frozen=True)
class ProjectionCalculation:
    projection_type: str
    scenario_label: str
    baseline_year: int
    baseline_value: float
    baseline_extraction_rate: float | None
    target_year: int | None
    projected_value: float | None
    projected_depletion_year: int | None
    beyond_modeled_horizon: bool
    series: list[ProjectionPoint]
    result_summary: str
    methodology_note: str


def _linear_reserve_depletion_rate(points: list[DataPoint]) -> float | None:
    """Return annual reserve decline from a least-squares trend, if declining.

    Reserve changes are net changes: extraction can be offset by discoveries or
    reserve revisions. A non-declining trend therefore cannot provide a positive
    depletion rate and deliberately falls back to production data.
    """
    recent = points[-6:]
    if len(recent) < 2:
        return None
    first_year = recent[0].timestamp.year
    years = [point.timestamp.year - first_year for point in recent]
    values = [point.value for point in recent]
    mean_year = sum(years) / len(years)
    mean_value = sum(values) / len(values)
    denominator = sum((year - mean_year) ** 2 for year in years)
    if denominator == 0:
        return None
    slope = sum(
        (year - mean_year) * (value - mean_value)
        for year, value in zip(years, values, strict=True)
    ) / denominator
    return -slope if slope < 0 else None


def _finite_resource_projection(
    metric: Metric,
    points: list[DataPoint],
    rule: ProjectionRule,
    request: ProjectionRequest,
) -> ProjectionCalculation:
    latest = points[-1]
    depletion_rate = _linear_reserve_depletion_rate(points)
    if depletion_rate is not None:
        rate_method = (
            "The baseline extraction proxy is the annual decline from a linear fit "
            "over up to the six most recent reserve observations."
        )
    else:
        depletion_rate = rule.fallback_annual_extraction
        if depletion_rate is None:
            raise ProjectionInputError(
                "At least two declining reserve observations are required for this metric."
            )
        rate_method = (
            "The reserve series does not yet contain enough declining history to derive "
            f"extraction, so the baseline uses {depletion_rate:,.2f} {metric.unit}/year "
            f"from {rule.fallback_source}."
        )

    threshold = latest.value * DEPLETION_THRESHOLD_FRACTION
    extraction = depletion_rate
    remaining = latest.value
    growth_factor = 1 + request.rate_of_change_pct / 100.0
    series = [ProjectionPoint(year=latest.timestamp.year, value=round(remaining, 6))]
    depletion_year: int | None = None

    # This is a deliberately simple stock-and-flow loop. Each year subtracts
    # that year's extraction, then compounds extraction for the following year.
    for offset in range(1, MAX_PROJECTION_YEARS + 1):
        year = latest.timestamp.year + offset
        remaining = max(0.0, remaining - extraction)
        series.append(ProjectionPoint(year=year, value=round(remaining, 6)))
        if remaining <= threshold:
            depletion_year = year
            break
        extraction *= growth_factor

    beyond_horizon = depletion_year is None
    if beyond_horizon:
        result = (
            f"At this rate, {metric.display_name.lower()} remain above the 1% "
            f"threshold beyond the {MAX_PROJECTION_YEARS}-year modeled horizon."
        )
    else:
        result = (
            f"At this rate, {metric.display_name.lower()} are projected to fall below "
            f"1% of the current reserve level by {depletion_year}."
        )

    return ProjectionCalculation(
        projection_type="finite_resource",
        scenario_label=(
            f"Extraction changes {request.rate_of_change_pct:+.2f}% per year"
        ),
        baseline_year=latest.timestamp.year,
        baseline_value=latest.value,
        baseline_extraction_rate=depletion_rate,
        target_year=None,
        projected_value=None if beyond_horizon else series[-1].value,
        projected_depletion_year=depletion_year,
        beyond_modeled_horizon=beyond_horizon,
        series=series,
        result_summary=result,
        methodology_note=f"{rate_method} {METHODOLOGY_CAVEAT}",
    )


def _trend_projection(
    metric: Metric,
    points: list[DataPoint],
    rule: ProjectionRule,
    request: ProjectionRequest,
) -> ProjectionCalculation:
    latest = points[-1]
    target_year = request.target_year or (
        latest.timestamp.year + DEFAULT_TREND_HORIZON_YEARS
    )
    if target_year <= latest.timestamp.year:
        raise ProjectionInputError(
            f"target_year must be later than the latest data year ({latest.timestamp.year})."
        )
    if target_year > latest.timestamp.year + MAX_PROJECTION_YEARS:
        raise ProjectionInputError(
            f"target_year cannot be more than {MAX_PROJECTION_YEARS} years after the baseline."
        )

    growth_factor = 1 + request.rate_of_change_pct / 100.0
    value = latest.value
    series = [ProjectionPoint(year=latest.timestamp.year, value=round(value, 6))]
    for year in range(latest.timestamp.year + 1, target_year + 1):
        value *= growth_factor
        value = max(rule.minimum_value, value)
        if rule.maximum_value is not None:
            value = min(rule.maximum_value, value)
        series.append(ProjectionPoint(year=year, value=round(value, 6)))

    result = (
        f"At {request.rate_of_change_pct:+.2f}% per year, {metric.display_name.lower()} "
        f"is projected to reach {value:,.2f} {metric.unit} in {target_year}."
    )
    bounds_note = (
        " Values are constrained to the metric's physical range."
        if rule.maximum_value is not None
        else " Values are constrained to remain non-negative."
    )
    return ProjectionCalculation(
        projection_type="trend",
        scenario_label=f"Value changes {request.rate_of_change_pct:+.2f}% per year",
        baseline_year=latest.timestamp.year,
        baseline_value=latest.value,
        baseline_extraction_rate=None,
        target_year=target_year,
        projected_value=round(value, 6),
        projected_depletion_year=None,
        beyond_modeled_horizon=False,
        series=series,
        result_summary=result,
        methodology_note=(
            "The latest observed value is compounded annually at the selected constant "
            f"rate through {target_year}.{bounds_note} {METHODOLOGY_CAVEAT}"
        ),
    )


def create_projection(
    session: Session, metric_key: str, request: ProjectionRequest
) -> ProjectionResponse:
    metric = session.scalar(select(Metric).where(Metric.key == metric_key))
    if metric is None:
        raise LookupError(f"Metric '{metric_key}' not found.")
    rule = PROJECTION_RULES.get(metric_key)
    if rule is None:
        raise ProjectionInputError(f"Metric '{metric_key}' has no projection model.")
    points = list(
        session.scalars(
            select(DataPoint)
            .where(DataPoint.metric_id == metric.id)
            .order_by(DataPoint.timestamp, DataPoint.id)
        )
    )
    if not points:
        raise ProjectionInputError(f"Metric '{metric_key}' has no data points.")

    calculation = (
        _finite_resource_projection(metric, points, rule, request)
        if rule.kind == "finite_resource"
        else _trend_projection(metric, points, rule, request)
    )
    projection = Projection(
        metric_id=metric.id,
        scenario_label=calculation.scenario_label,
        assumption_pct_change_per_year=request.rate_of_change_pct,
        projected_depletion_year=calculation.projected_depletion_year,
    )
    session.add(projection)
    session.commit()
    session.refresh(projection)

    return ProjectionResponse(
        projection_id=projection.id,
        metric_key=metric.key,
        projection_type=calculation.projection_type,
        scenario_label=calculation.scenario_label,
        assumption_pct_change_per_year=request.rate_of_change_pct,
        baseline_year=calculation.baseline_year,
        baseline_value=calculation.baseline_value,
        baseline_extraction_rate=calculation.baseline_extraction_rate,
        target_year=calculation.target_year,
        projected_value=calculation.projected_value,
        projected_depletion_year=calculation.projected_depletion_year,
        beyond_modeled_horizon=calculation.beyond_modeled_horizon,
        unit=metric.unit,
        series=calculation.series,
        result_summary=calculation.result_summary,
        methodology_note=calculation.methodology_note,
        computed_at=projection.computed_at,
    )
