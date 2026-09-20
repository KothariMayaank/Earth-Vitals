from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Float, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    data_points: Mapped[list["DataPoint"]] = relationship(back_populates="source")


class Geography(Base):
    __tablename__ = "geographies"
    __table_args__ = (
        CheckConstraint(
            "type IN ('global', 'region', 'country')",
            name="ck_geographies_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("geographies.id"), nullable=True)

    data_points: Mapped[list["DataPoint"]] = relationship(back_populates="geography")


class Metric(Base):
    __tablename__ = "metrics"
    __table_args__ = (
        CheckConstraint(
            "domain IN ('energy', 'minerals', 'emissions', 'freshwater')",
            name="ck_metrics_domain",
        ),
        CheckConstraint(
            "cadence IN ('daily', 'monthly', 'quarterly', 'annual')",
            name="ck_metrics_cadence",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(Text)
    cadence: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    data_points: Mapped[list["DataPoint"]] = relationship(back_populates="metric")
    projections: Mapped[list["Projection"]] = relationship(back_populates="metric")


class DataPoint(Base):
    __tablename__ = "data_points"
    __table_args__ = (
        Index("ix_data_points_metric_id_timestamp", "metric_id", "timestamp"),
        Index(
            "ix_data_points_metric_geography_timestamp",
            "metric_id",
            "geography_id",
            "timestamp",
        ),
        UniqueConstraint(
            "metric_id",
            "geography_id",
            "timestamp",
            name="uq_data_points_metric_geography_timestamp",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    metric_id: Mapped[int] = mapped_column(ForeignKey("metrics.id"))
    timestamp: Mapped[date] = mapped_column(Date)
    value: Mapped[float] = mapped_column(Float)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    geography_id: Mapped[int] = mapped_column(ForeignKey("geographies.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    metric: Mapped[Metric] = relationship(back_populates="data_points")
    source: Mapped[Source] = relationship(back_populates="data_points")
    geography: Mapped[Geography] = relationship(back_populates="data_points")


class IndexWeight(Base):
    __tablename__ = "index_weights"
    __table_args__ = (
        CheckConstraint(
            "domain IN ('energy', 'minerals', 'emissions', 'freshwater')",
            name="ck_index_weights_domain",
        ),
        CheckConstraint(
            "weight >= 0 AND weight <= 1",
            name="ck_index_weights_weight_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    domain: Mapped[str] = mapped_column(Text, unique=True)
    weight: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Projection(Base):
    __tablename__ = "projections"

    id: Mapped[int] = mapped_column(primary_key=True)
    metric_id: Mapped[int] = mapped_column(ForeignKey("metrics.id"))
    scenario_label: Mapped[str] = mapped_column(Text)
    assumption_pct_change_per_year: Mapped[float] = mapped_column(Float)
    projected_depletion_year: Mapped[int | None] = mapped_column(nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    metric: Mapped[Metric] = relationship(back_populates="projections")
