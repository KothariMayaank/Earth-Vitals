from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Geography


WORLD_CODE = "WORLD"


def get_or_create_world_geography(session: Session) -> Geography:
    geography = session.scalar(select(Geography).where(Geography.code == WORLD_CODE))
    if geography is None:
        geography = Geography(code=WORLD_CODE, name="World", type="global")
        session.add(geography)
        session.flush()
    return geography


def get_or_create_geography(
    session: Session, *, code: str, name: str, geography_type: str
) -> Geography:
    geography = session.scalar(select(Geography).where(Geography.code == code))
    if geography is None:
        geography = Geography(code=code, name=name, type=geography_type)
        session.add(geography)
        session.flush()
    else:
        geography.name = name
        geography.type = geography_type
    return geography
