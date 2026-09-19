import sys
from pathlib import Path

from sqlalchemy.orm import Session


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.database import get_engine  # noqa: E402
from backend.app.index_service import seed_default_index_weights  # noqa: E402
from backend.app.geographies import get_or_create_world_geography  # noqa: E402
from backend.app.models import Base  # noqa: E402


def main() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        get_or_create_world_geography(session)
        seed_default_index_weights(session)
        session.commit()
    print("Earth Vitals database tables created and index weights seeded successfully.")


if __name__ == "__main__":
    main()
