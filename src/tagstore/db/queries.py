import json
import logging
from enum import IntEnum
from functools import wraps
from json import JSONDecodeError
from typing import List, Set

from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from .database import get_db_engine_async
from .models import (
    Actor,
    AddressClusterMapping,
    Concept,
    Confidence,
    Country,
    Tag,
    TagPack,
    TagSubject,
    TagType,
)

logger = logging.getLogger("uvicorn.error")


class Taxonomies(IntEnum):
    CONCEPT = 1
    CONFIDENCE = 2
    COUTRY = 3
    TAG_SUBJECT = 4
    TAG_TYPE = 5


# Output Classes


class ItemDescriptionPublic(BaseModel):
    id: str  # noqa
    label: str
    description: str
    source: str | None
    taxonomy: str


class ConfidencePublic(ItemDescriptionPublic):
    level: int


class ConceptsPublic(ItemDescriptionPublic):
    parent: str | None


class TaxonomiesPublic(BaseModel):
    confidences: List[ConfidencePublic] | None
    coutries: List[ItemDescriptionPublic] | None
    tag_subjects: List[ItemDescriptionPublic] | None
    tag_types: List[ItemDescriptionPublic] | None
    concepts: List[ConceptsPublic] | None


class ActorPublic(BaseModel):
    id: str  # noqa
    label: str
    primary_uri: str
    nr_tags: int | None
    concepts: List[str]
    jurisdictions: List[str]
    additional_uris: List[str]
    image_links: List[str]
    online_references: List[str]
    coingecko_ids: List[str]
    defilama_ids: List[str]
    twitter_handles: List[str]
    legal_name: str | None

    @classmethod
    def fromDB(cls, a: Actor, tag_count: int | None = None) -> "TagPublic":
        additional_uris = []
        image_links = []
        online_references = []
        coingecko_ids = []
        defilama_ids = []
        twitter_handles = []
        legal_name = None

        try:
            data = json.loads(a.context)

            # muliple twitter handles are string concatendated at the moment
            twitter_handles = [
                x.strip()
                for x in data.get("twitter_handle", "").split(",")
                if x.strip()
            ]

            additional_uris.extend(data.get("uris", []))
            image_links.extend(data.get("images", []))
            online_references.extend(data.get("refs", []))
            coingecko_ids.extend(data.get("coingecko_ids", []))
            defilama_ids.extend(data.get("defilama_ids", []))
            twitter_handles.extend(twitter_handles)
            legal_name = data.get("legal_name", None)

        except JSONDecodeError:
            logger.error(f"Could not decode actor context: {a.context}")

        return cls(
            id=a.id,
            label=a.label,
            primary_uri=a.uri,
            concepts=[c.concept_id for c in a.concepts],
            jurisdictions=[c.country_id for c in a.jurisdictions],
            additional_uris=additional_uris,
            image_links=image_links,
            online_references=online_references,
            coingecko_ids=coingecko_ids,
            defilama_ids=defilama_ids,
            twitter_handles=twitter_handles,
            legal_name=legal_name,
            nr_tags=tag_count,
        )


class TagPublic(BaseModel):
    identifier: str
    label: str
    source: str
    creator: str
    confidence: str
    confidence_level: int
    tag_subject: str
    tag_type: str
    actor: str | None
    primary_concept: str | None
    additional_concepts: List[str]
    network: str
    lastmod: int
    group: str

    @classmethod
    def fromDB(cls, t: Tag, tp: TagPack) -> "TagPublic":
        c = t.concepts
        mainc = next(
            (x for x in c if x.concept_relation_annotation_id == "primary"), None
        )
        return cls(
            identifier=t.identifier,
            label=t.label,
            source=t.source,
            creator=tp.creator,
            confidence=t.confidence_id,
            confidence_level=t.confidence.level,
            tag_subject=t.tag_subject_id,
            tag_type=t.tag_type_id,
            actor=t.actor_id,
            primary_concept=mainc.concept_id if mainc else None,
            additional_concepts=[x.concept_id for x in c if x != mainc],
            network=t.network,
            lastmod=int(round(t.lastmod.timestamp())),
            group=tp.acl_group,
        )


# Statements
def _get_tags_by_id_stmt(
    identifier: str, offset: int, page_size: int, groups: List[str]
):
    return (
        select(Tag, TagPack)
        .options(selectinload(Tag.confidence))
        .where(Tag.identifier == identifier)
        .where(Tag.tagpack_id == TagPack.id)
        .where(TagPack.acl_group.in_(groups))
        .offset(offset)
        .limit(page_size)
    )


def _get_tags_by_actorid_stmt(
    actor: str, offset: int, page_size: int, groups: List[str]
):
    return (
        select(Tag, TagPack)
        .where(Tag.actor_id == actor)
        .where(Tag.tagpack_id == TagPack.id)
        .where(TagPack.acl_group.in_(groups))
        .offset(offset)
        .limit(page_size)
    )


def _get_tags_by_clusterid_stmt(
    cluster_id: int, offset: int, page_size: int, groups: List[str]
):
    return (
        select(Tag, TagPack, AddressClusterMapping)
        .options(selectinload(Tag.confidence))
        .where(AddressClusterMapping.gs_cluster_id == cluster_id)
        .where(AddressClusterMapping.address == Tag.identifier)
        .where(Tag.tagpack_id == TagPack.id)
        .where(TagPack.acl_group.in_(groups))
        .offset(offset)
        .limit(page_size)
    )


def _get_tags_by_label_stmt(label: str, offset: int, page_size: int, groups: List[str]):
    return (
        select(Tag, TagPack)
        .options(selectinload(Tag.confidence))
        .where(Tag.label.like(f"%{label}%"))
        .where(Tag.tagpack_id == TagPack.id)
        .where(TagPack.acl_group.in_(groups))
        .offset(offset)
        .limit(page_size)
    )


def _get_actor_by_id_stmt(actor: str):
    return select(Actor).where(Actor.id == actor)


def _get_actor_tag_count_stmt(actor: str):
    return select(func.count()).select_from(Tag).where(Tag.actor_id == actor)


# Facades
def _inject_session(f):
    @wraps(f)
    async def inner_f(self, *args, **kwargs):
        session = kwargs.get("session", None)

        if session is not None:
            return await f(self, *args, **kwargs)
        else:
            async with AsyncSession(self.engine) as session:
                kwargs["session"] = session
                return await f(self, *args, **kwargs)

    return inner_f


class TagstoreDbAsync:

    engine = None

    def __init__(self, engine):
        self.engine = engine

    @staticmethod
    def from_engine(db_url):
        return TagstoreDbAsync(get_db_engine_async(db_url))

    # Get Tags by Id
    @_inject_session
    async def _get_tags_by_id(
        self,
        identifier: str,
        offset: int,
        page_size: int,
        groups: List[str],
        session=None,
    ) -> List[Tag]:
        return await session.exec(
            _get_tags_by_id_stmt(identifier, offset, page_size, groups)
        )

    @_inject_session
    async def get_tags_by_id(
        self,
        identifier: str,
        offset: int,
        page_size: int,
        groups: List[str],
        session=None,
    ) -> List[TagPublic]:
        results = await self._get_tags_by_id(
            identifier, offset, page_size, groups, session=session
        )
        return [TagPublic.fromDB(t, tp) for t, tp in results]

    # Get Tags by Label
    @_inject_session
    async def _get_tags_by_label(
        self,
        label: str,
        offset: int,
        page_size: int,
        groups: List[str],
        session=None,
    ) -> List[Tag]:
        return await session.exec(
            _get_tags_by_label_stmt(label, offset, page_size, groups)
        )

    @_inject_session
    async def get_tags_by_label(
        self,
        label: str,
        offset: int,
        page_size: int,
        groups: List[str],
        session=None,
    ) -> List[TagPublic]:
        results = await self._get_tags_by_label(
            label, offset, page_size, groups, session=session
        )
        return [TagPublic.fromDB(t, tp) for t, tp in results]

    # Cluster

    @_inject_session
    async def _get_tags_by_clusterid(
        self,
        cluster_id: int,
        offset: int,
        page_size: int,
        groups: List[str],
        session=None,
    ) -> List[Tag]:
        return await session.exec(
            _get_tags_by_clusterid_stmt(cluster_id, offset, page_size, groups)
        )

    @_inject_session
    async def get_tags_by_clusterid(
        self,
        cluster_id: int,
        offset: int,
        page_size: int,
        groups: List[str],
        session=None,
    ) -> List[TagPublic]:
        results = await self._get_tags_by_clusterid(
            cluster_id, offset, page_size, groups, session=session
        )
        return [TagPublic.fromDB(t, tp) for t, tp, _ in results]

    # Actor

    @_inject_session
    async def get_actor_by_id(
        self, identifier: str, include_tag_count: bool, session=None
    ) -> ActorPublic | None:
        actor = (await session.exec(_get_actor_by_id_stmt(identifier))).first()

        tag_count = None
        if include_tag_count:
            tag_count = (
                await session.exec(_get_actor_tag_count_stmt(identifier))
            ).first()

        if actor is not None:
            return ActorPublic.fromDB(actor, tag_count=tag_count)

        return None

    @_inject_session
    async def _get_tags_by_actorid(
        self,
        actor: str,
        offset: int,
        page_size: int,
        groups: List[str],
        session=None,
    ) -> List[Tag]:
        return await session.exec(
            _get_tags_by_actorid_stmt(actor, offset, page_size, groups)
        )

    @_inject_session
    async def get_tags_by_actorid(
        self,
        actor: str,
        offset: int,
        page_size: int,
        groups: List[str],
        session=None,
    ) -> List[TagPublic]:
        results = await self._get_tags_by_actorid(
            actor, offset, page_size, groups, session=session
        )
        return [TagPublic.fromDB(t, tp) for t, tp in results]

    # Other
    @_inject_session
    async def get_taxonomies(
        self, include: Set[Taxonomies], session=None
    ) -> TaxonomiesPublic:
        return TaxonomiesPublic(
            confidences=(
                None
                if Taxonomies.CONFIDENCE not in include
                else (
                    [
                        ConfidencePublic(**{"source": None, **(x.model_dump())})
                        for x in (await session.exec(select(Confidence)))
                    ]
                )
            ),
            coutries=(
                None
                if Taxonomies.COUTRY not in include
                else (
                    [
                        ItemDescriptionPublic(**(x.model_dump()))
                        for x in (await session.exec(select(Country)))
                    ]
                )
            ),
            tag_subjects=(
                None
                if Taxonomies.TAG_SUBJECT not in include
                else (
                    [
                        ItemDescriptionPublic(**(x.model_dump()))
                        for x in (await session.exec(select(TagSubject)))
                    ]
                )
            ),
            tag_types=(
                None
                if Taxonomies.TAG_TYPE not in include
                else (
                    [
                        ItemDescriptionPublic(**(x.model_dump()))
                        for x in (await session.exec(select(TagType)))
                    ]
                )
            ),
            concepts=(
                None
                if Taxonomies.CONCEPT not in include
                else (
                    [
                        ConceptsPublic(**(x.model_dump()))
                        for x in (await session.exec(select(Concept)))
                    ]
                )
            ),
        )
