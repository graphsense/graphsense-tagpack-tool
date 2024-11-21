from typing import List

from fastapi import APIRouter

from ....tagpack import __version__
from ...db import ActorPublic, TagPublic, Taxonomies, TaxonomiesPublic
from ..dependencies import TsACLGroupsParam, TsDbParam, TsPagingParam, TsTagsQueryParam

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
    "/tags",
    tags=["Tags"],
    name="Get all tags for an query",
)
async def get_tags(
    query: TsTagsQueryParam,
    page: TsPagingParam,
    groups: TsACLGroupsParam,
    db: TsDbParam,
) -> List[TagPublic]:
    """
    Loads tags for a tx hash, address (subject_id),
      label (label), actor (actor_id) or cluster id (cluster_id)
    """
    if query.label is not None:
        return await db.get_tags_by_label(query.label, page.offset, page.limit, groups)
    elif query.actor_id is not None:
        return await db.get_tags_by_actorid(
            query.actor_id, page.offset, page.limit, groups
        )
    elif query.subject_id is not None:
        return await db.get_tags_by_id(
            query.subject_id, page.offset, page.limit, groups
        )
    elif query.cluster_id is not None:
        return await db.get_tags_by_clusterid(
            query.cluster_id, page.offset, page.limit, groups
        )


@router.get("/actor/{actor}", tags=["Actor"], name="Get an Actor by its id.")
async def get_actor_by_id(
    actor: str, db: TsDbParam, include_tag_count: bool = False
) -> ActorPublic | None:
    """
    Loads actor by id
    """
    return await db.get_actor_by_id(actor, include_tag_count)
