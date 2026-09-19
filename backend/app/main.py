from collections.abc import Generator
from datetime import date
from functools import lru_cache
import os
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.app.database import REPO_ROOT, get_engine
from backend.app.index_service import (
    IndexUnavailableError,
    compute_current_index,
    update_index_weights,
)
from backend.app.geographies import WORLD_CODE
from backend.app.models import DataPoint, Geography, Metric, Source
from backend.app.projection_service import ProjectionInputError, create_projection
from backend.app.schemas import (
    DataPointResponse,
    Domain,
    DomainSummaryResponse,
    HealthResponse,
    GeographyResponse,
    IndexResponse,
    IndexWeights,
    MetricResponse,
    MetricMapPoint,
    MetricMapResponse,
    ProjectionRequest,
    ProjectionResponse,
)


from dotenv import load_dotenv


load_dotenv(REPO_ROOT / ".env")

app = FastAPI(
    title="Earth Vitals",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

cors_origins = ["http://localhost:3000"]
if frontend_origin := os.getenv("FRONTEND_ORIGIN"):
    cors_origins.append(frontend_origin.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache
def get_api_engine() -> Engine:
    return get_engine()


def get_session() -> Generator[Session, None, None]:
    with Session(get_api_engine()) as session:
        yield session


SessionDependency = Annotated[Session, Depends(get_session)]


def get_metric_or_404(session: Session, metric_key: str) -> Metric:
    metric = session.scalar(select(Metric).where(Metric.key == metric_key))
    if metric is None:
        raise HTTPException(status_code=404, detail=f"Metric '{metric_key}' not found.")
    return metric


def get_geography_or_404(session: Session, geography_code: str) -> Geography:
    geography = session.scalar(
        select(Geography).where(Geography.code == geography_code.upper())
    )
    if geography is None:
        raise HTTPException(
            status_code=404, detail=f"Geography '{geography_code}' not found."
        )
    return geography


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/metrics", response_model=list[MetricResponse])
def list_metrics(session: SessionDependency) -> list[Metric]:
    return list(session.scalars(select(Metric).order_by(Metric.key)))


@app.get(
    "/metrics/{metric_key}/history",
    response_model=list[DataPointResponse],
)
def metric_history(
    metric_key: str,
    session: SessionDependency,
    start: Annotated[date | None, Query()] = None,
    end: Annotated[date | None, Query()] = None,
) -> list[DataPoint]:
    if start is not None and end is not None and start > end:
        raise HTTPException(status_code=422, detail="start must be on or before end.")

    metric = get_metric_or_404(session, metric_key)
    world = get_geography_or_404(session, WORLD_CODE)
    statement = select(DataPoint).where(
        DataPoint.metric_id == metric.id,
        DataPoint.geography_id == world.id,
    )
    if start is not None:
        statement = statement.where(DataPoint.timestamp >= start)
    if end is not None:
        statement = statement.where(DataPoint.timestamp <= end)
    return list(session.scalars(statement.order_by(DataPoint.timestamp)))


@app.get(
    "/metrics/{metric_key}/latest",
    response_model=DataPointResponse,
)
def metric_latest(metric_key: str, session: SessionDependency) -> DataPoint:
    metric = get_metric_or_404(session, metric_key)
    world = get_geography_or_404(session, WORLD_CODE)
    data_point = session.scalar(
        select(DataPoint)
        .where(
            DataPoint.metric_id == metric.id,
            DataPoint.geography_id == world.id,
        )
        .order_by(DataPoint.timestamp.desc(), DataPoint.id.desc())
        .limit(1)
    )
    if data_point is None:
        raise HTTPException(
            status_code=404,
            detail=f"Metric '{metric_key}' has no data points.",
        )
    return data_point


def _summary_for_geography(
    session: Session, geography: Geography, domain: Domain | None = None
) -> list[DomainSummaryResponse]:
    latest_dates = (
        select(
            DataPoint.metric_id.label("metric_id"),
            func.max(DataPoint.timestamp).label("latest_timestamp"),
        )
        .where(DataPoint.geography_id == geography.id)
        .group_by(DataPoint.metric_id)
        .subquery()
    )
    statement = (
        select(Metric, DataPoint, Source)
        .join(latest_dates, latest_dates.c.metric_id == Metric.id)
        .join(
            DataPoint,
            (DataPoint.metric_id == latest_dates.c.metric_id)
            & (DataPoint.timestamp == latest_dates.c.latest_timestamp),
        )
        .join(Source, Source.id == DataPoint.source_id)
        .where(DataPoint.geography_id == geography.id)
        .order_by(Metric.key)
    )
    if domain is not None:
        statement = statement.where(Metric.domain == domain)
    rows = session.execute(statement).all()
    return [
        DomainSummaryResponse(
            id=metric.id,
            key=metric.key,
            display_name=metric.display_name,
            domain=metric.domain,
            unit=metric.unit,
            cadence=metric.cadence,
            timestamp=data_point.timestamp,
            value=data_point.value,
            description=metric.description,
            source_name=source.name,
            source_url=source.url,
        )
        for metric, data_point, source in rows
    ]


@app.get(
    "/domains/{domain}/summary",
    response_model=list[DomainSummaryResponse],
)
def domain_summary(domain: Domain, session: SessionDependency) -> list[DomainSummaryResponse]:
    world = get_geography_or_404(session, WORLD_CODE)
    return _summary_for_geography(session, world, domain)


@app.get("/geographies", response_model=list[GeographyResponse])
def list_geographies(
    session: SessionDependency,
    geography_type: Annotated[Literal["global", "region", "country"] | None, Query(alias="type")] = None,
) -> list[Geography]:
    statement = select(Geography).order_by(Geography.name)
    if geography_type is not None:
        statement = statement.where(Geography.type == geography_type)
    return list(session.scalars(statement))


@app.get("/countries/{country_code}", response_model=GeographyResponse)
def country_detail(country_code: str, session: SessionDependency) -> Geography:
    geography = get_geography_or_404(session, country_code)
    if geography.type != "country":
        raise HTTPException(status_code=404, detail=f"Country '{country_code}' not found.")
    return geography


@app.get(
    "/countries/{country_code}/summary",
    response_model=list[DomainSummaryResponse],
)
def country_summary(
    country_code: str,
    session: SessionDependency,
    domain: Annotated[Domain | None, Query()] = None,
) -> list[DomainSummaryResponse]:
    geography = get_geography_or_404(session, country_code)
    if geography.type != "country":
        raise HTTPException(status_code=404, detail=f"Country '{country_code}' not found.")
    return _summary_for_geography(session, geography, domain)


@app.get(
    "/countries/{country_code}/metrics/{metric_key}/history",
    response_model=list[DataPointResponse],
)
def country_metric_history(
    country_code: str,
    metric_key: str,
    session: SessionDependency,
    start: date | None = None,
    end: date | None = None,
) -> list[DataPoint]:
    if start is not None and end is not None and start > end:
        raise HTTPException(status_code=422, detail="start must be on or before end.")
    geography = get_geography_or_404(session, country_code)
    if geography.type != "country":
        raise HTTPException(status_code=404, detail=f"Country '{country_code}' not found.")
    metric = get_metric_or_404(session, metric_key)
    statement = select(DataPoint).where(
        DataPoint.metric_id == metric.id,
        DataPoint.geography_id == geography.id,
    )
    if start is not None:
        statement = statement.where(DataPoint.timestamp >= start)
    if end is not None:
        statement = statement.where(DataPoint.timestamp <= end)
    return list(session.scalars(statement.order_by(DataPoint.timestamp)))


@app.get("/metrics/{metric_key}/map", response_model=MetricMapResponse)
def metric_map(
    metric_key: str,
    session: SessionDependency,
    observation_date: Annotated[date | None, Query(alias="date")] = None,
) -> MetricMapResponse:
    metric = get_metric_or_404(session, metric_key)
    latest_statement = select(
        DataPoint.geography_id.label("geography_id"),
        func.max(DataPoint.timestamp).label("latest_timestamp"),
    ).where(DataPoint.metric_id == metric.id)
    if observation_date is not None:
        latest_statement = latest_statement.where(DataPoint.timestamp <= observation_date)
    latest_dates = latest_statement.group_by(DataPoint.geography_id).subquery()
    rows = session.execute(
        select(Geography, DataPoint)
        .join(latest_dates, latest_dates.c.geography_id == Geography.id)
        .join(
            DataPoint,
            (DataPoint.metric_id == metric.id)
            & (DataPoint.geography_id == latest_dates.c.geography_id)
            & (DataPoint.timestamp == latest_dates.c.latest_timestamp),
        )
        .where(Geography.type == "country")
        .order_by(Geography.name)
    ).all()
    return MetricMapResponse(
        metric_key=metric.key,
        display_name=metric.display_name,
        unit=metric.unit,
        points=[
            MetricMapPoint(
                code=geography.code,
                name=geography.name,
                timestamp=data_point.timestamp,
                value=data_point.value,
            )
            for geography, data_point in rows
        ],
    )


@app.get("/index/current", response_model=IndexResponse)
def current_index(session: SessionDependency) -> IndexResponse:
    try:
        return compute_current_index(session)
    except IndexUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.put("/index/weights", response_model=IndexResponse)
def put_index_weights(
    weights: IndexWeights, session: SessionDependency
) -> IndexResponse:
    try:
        return update_index_weights(session, weights)
    except IndexUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/projections/{metric_key}", response_model=ProjectionResponse)
def post_projection(
    metric_key: str,
    request: ProjectionRequest,
    session: SessionDependency,
) -> ProjectionResponse:
    try:
        return create_projection(session, metric_key, request)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ProjectionInputError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
