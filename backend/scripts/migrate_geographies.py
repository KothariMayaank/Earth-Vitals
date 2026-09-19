"""Add geography support and backfill existing observations to World.

This idempotent migration exists because the original MVP used ``create_all``
before adopting a migration tool. New installations receive the final schema
directly from SQLAlchemy metadata; existing Postgres databases can run this once.
"""

import sys
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.database import get_engine  # noqa: E402
from backend.app.geographies import get_or_create_world_geography  # noqa: E402
from backend.app.models import Base, Geography  # noqa: E402


def main() -> None:
    engine = get_engine()
    Geography.__table__.create(engine, checkfirst=True)

    columns = {column["name"] for column in inspect(engine).get_columns("data_points")}
    if "geography_id" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE data_points ADD COLUMN geography_id INTEGER "
                    "REFERENCES geographies(id)"
                )
            )

    with Session(engine) as session:
        world = get_or_create_world_geography(session)
        session.execute(
            text("UPDATE data_points SET geography_id = :world_id WHERE geography_id IS NULL"),
            {"world_id": world.id},
        )
        session.commit()

    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE data_points ALTER COLUMN geography_id SET NOT NULL")
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "uq_data_points_metric_geography_timestamp "
                    "ON data_points (metric_id, geography_id, timestamp)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_data_points_metric_geography_timestamp "
                    "ON data_points (metric_id, geography_id, timestamp)"
                )
            )

    Base.metadata.create_all(engine)
    print("Geography migration complete; existing observations are assigned to World.")


if __name__ == "__main__":
    main()
