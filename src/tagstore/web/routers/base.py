from typing import List

from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import select

from ....tagpack import __version__
from ...db.models import Tag, TagPack
from ..dependencies import (
    TsACLGroupsParam,
    TsDbSessionParam,
    TsIdentifierParam,
    TsPagingParam,
)

router = APIRouter()


class TagPublic(BaseModel):
    identifier: str
    label: str
    source: str
    creator: str
    confidence: str
    confidence_level: int
    main_concept: str | None
    additional_concepts: List[str]
    network: str
    lastmod: int
    group: str

    @classmethod
    def fromDB(cls, t: Tag, tp: TagPack) -> "TagPublic":
        c = t.concepts
        mainc = next((x for x in c if x.concept_type == "category"), None)
        return cls(
            identifier=t.identifier,
            label=t.label,
            source=t.source,
            creator=tp.creator,
            confidence=t.confidence_id,
            confidence_level=t.confidence.level,
            main_concept=mainc.concept_id if mainc else None,
            additional_concepts=[x.concept_id for x in c if x != mainc],
            network=t.network,
            lastmod=t.lastmod.timestamp(),
            group=tp.acl_group,
        )


@router.get("/version/", tags=["General"])
async def get_version() -> str:
    return __version__


@router.get(
    "/tag/{identifier}",
    tags=["Tags"],
    name="Get all tags for an identifier (e.g. and address or transaction)",
)
async def get_tags(
    identifier: TsIdentifierParam,
    page: TsPagingParam,
    groups: TsACLGroupsParam,
    session: TsDbSessionParam,
) -> List[TagPublic]:
    """
    Loads tags by identifier
    """
    statement = (
        select(Tag, TagPack)
        .where(Tag.identifier == identifier)
        .offset(page.offset())
        .limit(page.limit())
    )
    results = session.exec(statement)
    return [TagPublic.fromDB(t, tp) for t, tp in results]


@router.get("/tag/by_label/{label}", tags=["Tags"], name="Get all tags for a label")
async def get_tags_by_label(
    label: str, page: TsPagingParam, groups: TsACLGroupsParam, session: TsDbSessionParam
) -> List[TagPublic]:
    """
    Loads tags by label
    """
    statement = (
        select(Tag, TagPack)
        .where(Tag.label.match(label))
        .offset(page.offset())
        .limit(page.limit())
    )
    results = session.exec(statement)
    return [TagPublic.fromDB(t, tp) for t, tp in results]
