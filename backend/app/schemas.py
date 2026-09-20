from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Domain = Literal["energy", "minerals", "emissions", "freshwater"]


class HealthResponse(BaseModel):
    status: str


class MetricResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    display_name: str
    domain: Domain
    unit: str
    cadence: str


class DataPointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: date
    value: float


class DomainSummaryResponse(MetricResponse):
    timestamp: date
    value: float
    description: str | None = None
    source_name: str
    source_url: str


class GeographyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    type: Literal["global", "region", "country"]


class MetricMapPoint(BaseModel):
    code: str
    name: str
    timestamp: date
    value: float


class MetricMapResponse(BaseModel):
    metric_key: str
    display_name: str
    unit: str
    points: list[MetricMapPoint]


class IndexWeights(BaseModel):
    energy: float = Field(ge=0, le=1)
    minerals: float = Field(ge=0, le=1)
    emissions: float = Field(ge=0, le=1)
    freshwater: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "IndexWeights":
        total = self.energy + self.minerals + self.emissions + self.freshwater
        if abs(total - 1.0) > 0.01:
            raise ValueError("Index weights must sum to approximately 1.0.")
        return self


class IndexDomainScores(BaseModel):
    energy: float
    minerals: float
    emissions: float
    freshwater: float


class IndexResponse(BaseModel):
    composite_score: float
    domain_scores: IndexDomainScores
    weights: IndexWeights


class ProjectionRequest(BaseModel):
    rate_of_change_pct: float = Field(ge=-50, le=50)
    target_year: int | None = Field(default=None, ge=2020, le=2500)


class ProjectionPoint(BaseModel):
    year: int
    value: float


class ProjectionResponse(BaseModel):
    projection_id: int
    metric_key: str
    projection_type: Literal["finite_resource", "trend"]
    scenario_label: str
    assumption_pct_change_per_year: float
    baseline_year: int
    baseline_value: float
    baseline_extraction_rate: float | None
    target_year: int | None
    projected_value: float | None
    projected_depletion_year: int | None
    beyond_modeled_horizon: bool
    unit: str
    series: list[ProjectionPoint]
    result_summary: str
    methodology_note: str
    computed_at: datetime
