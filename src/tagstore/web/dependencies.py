from typing import Annotated

from fastapi import Depends, Request
from sqlmodel import Session

from ..config import TagstoreSettings


def _get_session(request: Request):
    engine = request.app.state.db_engine
    with Session(engine) as session:
        yield session


def _gs_tagstore_settings() -> TagstoreSettings:
    return TagstoreSettings()


async def _db(request: Request):
    return request.app.state.db


TsSettingsParam = Annotated[TagstoreSettings, Depends(_gs_tagstore_settings)]

TsDbSessionParam = Annotated[Session, Depends(_get_session)]
