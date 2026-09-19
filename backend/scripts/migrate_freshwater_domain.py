"""Allow freshwater metrics in an existing Earth Vitals database.

The project adopted this small idempotent migration before introducing a full
migration framework. New databases receive the updated constraint directly
from SQLAlchemy metadata.
"""

import sys
from pathlib import Path

from sqlalchemy import text


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.database import get_engine  # noqa: E402
from backend.app.models import Base  # noqa: E402


def main() -> None:
    engine = get_engine()
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE metrics DROP CONSTRAINT IF EXISTS ck_metrics_domain"))
            connection.execute(
                text(
                    "ALTER TABLE metrics ADD CONSTRAINT ck_metrics_domain "
                    "CHECK (domain IN ('energy', 'minerals', 'emissions', 'freshwater'))"
                )
            )
    Base.metadata.create_all(engine)
    print("Freshwater domain migration complete.")


if __name__ == "__main__":
    main()
