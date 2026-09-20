from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.index_config import Domain, NORMALIZATION_RULES, NormalizationRule
from backend.app.geographies import WORLD_CODE
from backend.app.models import DataPoint, Geography, IndexWeight, Metric
from backend.app.schemas import IndexDomainScores, IndexResponse, IndexWeights


DOMAINS: tuple[Domain, ...] = ("energy", "minerals", "emissions", "freshwater")
DEFAULT_WEIGHT = 0.25


class IndexUnavailableError(RuntimeError):
    pass


def seed_default_index_weights(session: Session) -> None:
    existing_domains = set(session.scalars(select(IndexWeight.domain)))
    for domain in DOMAINS:
        if domain not in existing_domains:
            session.add(IndexWeight(domain=domain, weight=DEFAULT_WEIGHT))


def normalize_metric(value: float, rule: NormalizationRule) -> float:
    """Linearly map a configured raw value to 0-100 and clamp outliers."""
    span = rule.healthy - rule.concerning
    if span == 0:
        raise ValueError("Healthy and concerning endpoints must differ.")
    unbounded_score = (value - rule.concerning) / span * 100.0
    return max(0.0, min(100.0, unbounded_score))


def _current_domain_scores(session: Session) -> dict[Domain, float]:
    scores: defaultdict[Domain, list[float]] = defaultdict(list)
    for metric_key, rule in NORMALIZATION_RULES.items():
        row = session.execute(
            select(Metric, DataPoint)
            .join(DataPoint, DataPoint.metric_id == Metric.id)
            .join(Geography, Geography.id == DataPoint.geography_id)
            .where(Metric.key == metric_key, Geography.code == WORLD_CODE)
            .order_by(DataPoint.timestamp.desc(), DataPoint.id.desc())
            .limit(1)
        ).first()
        if row is not None:
            _, data_point = row
            scores[rule.domain].append(normalize_metric(data_point.value, rule))

    missing_domains = [domain for domain in DOMAINS if not scores[domain]]
    if missing_domains:
        raise IndexUnavailableError(
            "No configured current metrics are available for: "
            + ", ".join(missing_domains)
        )

    return {
        domain: sum(scores[domain]) / len(scores[domain])
        for domain in DOMAINS
    }


def compute_current_index(session: Session) -> IndexResponse:
    domain_scores = _current_domain_scores(session)
    weight_rows = list(session.scalars(select(IndexWeight)))
    weight_by_domain = {row.domain: row.weight for row in weight_rows}
    missing_weights = [domain for domain in DOMAINS if domain not in weight_by_domain]
    if missing_weights:
        raise IndexUnavailableError(
            "Index weights are missing for: " + ", ".join(missing_weights)
        )

    weight_total = sum(weight_by_domain[domain] for domain in DOMAINS)
    if weight_total <= 0:
        raise IndexUnavailableError("Index weights must have a positive total.")
    composite_score = sum(
        domain_scores[domain] * weight_by_domain[domain] for domain in DOMAINS
    ) / weight_total

    return IndexResponse(
        composite_score=round(composite_score, 2),
        domain_scores=IndexDomainScores(
            **{domain: round(domain_scores[domain], 2) for domain in DOMAINS}
        ),
        weights=IndexWeights(
            **{domain: weight_by_domain[domain] for domain in DOMAINS}
        ),
    )


def update_index_weights(session: Session, weights: IndexWeights) -> IndexResponse:
    values = weights.model_dump()
    rows = list(session.scalars(select(IndexWeight)))
    by_domain = {row.domain: row for row in rows}
    for domain in DOMAINS:
        row = by_domain.get(domain)
        if row is None:
            session.add(IndexWeight(domain=domain, weight=values[domain]))
        else:
            row.weight = values[domain]
    session.commit()
    return compute_current_index(session)
