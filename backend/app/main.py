from collections.abc import Generator
from datetime import date
from functools import lru_cache
import os
from typing import Annotated

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
from backend.app.models import DataPoint, Metric, Source
from backend.app.projection_service import ProjectionInputError, create_projection
from backend.app.schemas import (
    DataPointResponse,
    Domain,
    DomainSummaryResponse,
    HealthResponse,
    IndexResponse,
    IndexWeights,
    MetricResponse,
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
    statement = select(DataPoint).where(DataPoint.metric_id == metric.id)
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
    data_point = session.scalar(
        select(DataPoint)
        .where(DataPoint.metric_id == metric.id)
        .order_by(DataPoint.timestamp.desc(), DataPoint.id.desc())
        .limit(1)
    )
    if data_point is None:
        raise HTTPException(
            status_code=404,
            detail=f"Metric '{metric_key}' has no data points.",
        )
    return data_point


@app.get(
    "/domains/{domain}/summary",
    response_model=list[DomainSummaryResponse],
)
def domain_summary(domain: Domain, session: SessionDependency) -> list[DomainSummaryResponse]:
    latest_dates = (
        select(
            DataPoint.metric_id.label("metric_id"),
            func.max(DataPoint.timestamp).label("latest_timestamp"),
        )
        .group_by(DataPoint.metric_id)
        .subquery()
    )
    rows = session.execute(
        select(Metric, DataPoint, Source)
        .join(latest_dates, latest_dates.c.metric_id == Metric.id)
        .join(
            DataPoint,
            (DataPoint.metric_id == latest_dates.c.metric_id)
            & (DataPoint.timestamp == latest_dates.c.latest_timestamp),
        )
        .join(Source, Source.id == DataPoint.source_id)
        .where(Metric.domain == domain)
        .order_by(Metric.key)
    ).all()
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
