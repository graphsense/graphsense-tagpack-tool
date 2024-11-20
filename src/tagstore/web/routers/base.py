from typing import List

from fastapi import APIRouter

from ....tagpack import __version__
from ...db import TagPublic, Taxonomies, TaxonomiesPublic
from ..dependencies import TsACLGroupsParam, TsDbParam, TsIdentifierParam, TsPagingParam

router = APIRouter()


@router.get("/version/", tags=["General"])
async def get_version() -> str:
    return __version__


@router.get(
    "/taxonomy/", tags=["General"], name="Get a labels and description for id values."
)
async def get_taxonomies(db: TsDbParam) -> TaxonomiesPublic:
    """
    Loads taxonomies (meta information and descriptions) used in this API.
    """
    return await db.get_taxonomies(
        {
            Taxonomies.CONFIDENCE,
            Taxonomies.CONCEPT,
            Taxonomies.COUTRY,
            Taxonomies.TAG_SUBJECT,
            Taxonomies.TAG_TYPE,
        }
    )


@router.get(
    "/tag/{identifier}",
    tags=["Tags"],
    name="Get all tags for an identifier (e.g. and address or transaction)",
)
async def get_tags(
    identifier: TsIdentifierParam,
    page: TsPagingParam,
    groups: TsACLGroupsParam,
    db: TsDbParam,
) -> List[TagPublic]:
    """
    Loads tags by identifier
    """
    return await db.get_tags_by_id(identifier, page.offset, page.limit, groups)


@router.get("/tag/by_label/{label}", tags=["Tags"], name="Get all tags for a label")
async def get_tags_by_label(
    label: str, page: TsPagingParam, groups: TsACLGroupsParam, db: TsDbParam
) -> List[TagPublic]:
    """
    Loads tags by label
    """
    return await db.get_tags_by_label(label, page.offset, page.limit, groups)
