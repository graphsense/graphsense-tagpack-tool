from typing import List

from fastapi import APIRouter
from sqlmodel import select

from tagpack import __version__

from ...db.models import Tag
from ..dependencies import TsDbSessionParam

router = APIRouter()


@router.get("/version/", tags=["General"])
async def get_version() -> str:
    return __version__


@router.get("/tag/{ident}", tags=["Tags"])
async def get_tags(ident: str, session: TsDbSessionParam) -> List[Tag]:
    """
    Loads tags
    """
    statement = select(Tag).limit(3)
    results = session.exec(statement)
    return results.all()
