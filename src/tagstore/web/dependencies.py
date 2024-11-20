from typing import Annotated, List, Optional

from fastapi import Depends, Path, Query, Request
from pydantic import BaseModel
from sqlmodel import Session

from ..config import TagstoreSettings
from ..db import TagstoreDbAsync


def _get_session(request: Request):
    engine = request.app.state.db_engine
    with Session(engine) as session:
        yield session


def _get_tagstore_db_async(request: Request):
    return TagstoreDbAsync(request.app.state.db_engine)


class PageingState(BaseModel):
    page_nr: int
    page_size: int

    @property
    def offset(self) -> int:
        return self.page_nr * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


async def _paging_parameters(
    page_nr: Annotated[
        int,
        Query(alias="page_nr", description="Which page to serve"),
    ] = 0,
    page_size: Annotated[
        int,
        Query(
            alias="page_size",
            description="size of a page",
        ),
    ] = 1000,
) -> PageingState:
    return PageingState(page_nr=page_nr, page_size=page_size)


async def _acl_groups(
    groups: Annotated[
        Optional[List[str]],
        Query(alias="groups", description="Which groups of tags to consider."),
    ] = ["public"]
) -> Optional[List[str]]:
    return groups


def _gs_tagstore_settings() -> TagstoreSettings:
    return TagstoreSettings()


async def _db(request: Request):
    return request.app.state.db


TsSettingsParam = Annotated[TagstoreSettings, Depends(_gs_tagstore_settings)]

TsDbSessionParam = Annotated[Session, Depends(_get_session)]

TsDbParam = Annotated[TagstoreDbAsync, Depends(_get_tagstore_db_async)]

TsPagingParam = Annotated[PageingState, Depends(_paging_parameters)]

TsIdentifierParam = Annotated[
    str, Path(alias="identifier", description="Address or Transaction-hash")
]

TsACLGroupsParam = Annotated[Optional[List[str]], Depends(_acl_groups)]
