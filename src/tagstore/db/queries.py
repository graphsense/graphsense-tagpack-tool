import json
import logging
from enum import IntEnum
from functools import wraps
from json import JSONDecodeError
from typing import Dict, List, Set

from pydantic import BaseModel
from sqlalchemy import desc, distinct, func
from sqlalchemy.orm import selectinload
from sqlmodel import select, text
from sqlmodel.ext.asyncio.session import AsyncSession

from .database import get_db_engine_async
from .models import (
    Actor,
    AddressClusterMapping,
    BestClusterTagView,
    Concept,
    Confidence,
    Country,
    Tag,
    TagCountByClusterView,
    TagPack,
    TagSubject,
    TagType,
)

logger = logging.getLogger("uvicorn.error")


class Taxonomies(IntEnum):
    CONCEPT = 1
    CONFIDENCE = 2
    COUNTRY = 3
    TAG_SUBJECT = 4
    TAG_TYPE = 5


_ALL_TAXONOMIES = {
    Taxonomies.CONFIDENCE,
    Taxonomies.CONCEPT,
    Taxonomies.COUNTRY,
    Taxonomies.TAG_SUBJECT,
    Taxonomies.TAG_TYPE,
}

# Output Classes


class HumanReadableId(BaseModel):
    id: str  # noqa
    label: str


class ItemDescriptionPublic(HumanReadableId):
    description: str
    source: str | None
    taxonomy: str


class LabelSearchResultPublic(BaseModel):
    actor_labels: List[HumanReadableId]
    tag_labels: List[HumanReadableId]


class ConfidencePublic(ItemDescriptionPublic):
    level: int


class ConceptsPublic(ItemDescriptionPublic):
    parent: str | None


class TaxonomiesPublic(BaseModel):
    confidence: List[ConfidencePublic] | None
    country: List[ItemDescriptionPublic] | None
    tag_subject: List[ItemDescriptionPublic] | None
    tag_type: List[ItemDescriptionPublic] | None
    concept: List[ConceptsPublic] | None


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
    github_organisations: List[str]
    legal_name: str | None

    @classmethod
    def fromDB(cls, a: Actor, tag_count: int | None = None) -> "TagPublic":
        additional_uris = []
        image_links = []
        online_references = []
        coingecko_ids = []
        defilama_ids = []
        twitter_handles = []
        gh_handles = []
        legal_name = None

        try:
            data = json.loads(a.context)

            # muliple twitter handles are string concatendated at the moment
            twitter_handles_t = [
                x.strip()
                for x in data.get("twitter_handle", "").split(",")
                if x.strip()
            ]

            # muliple gh orgas are string concatendated at the moment
            gh_orgas = [
                x.strip()
                for x in data.get("github_organisation", "").split(",")
                if x.strip()
            ]

            additional_uris.extend(data.get("uris", []))
            image_links.extend(data.get("images", []))
            online_references.extend(data.get("refs", []))
            coingecko_ids.extend(data.get("coingecko_ids", []))
            defilama_ids.extend(data.get("defilama_ids", []))
            twitter_handles.extend(twitter_handles_t)
            gh_handles.extend(gh_orgas)
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
            github_organisations=gh_handles,
            legal_name=legal_name,
            nr_tags=tag_count,
        )


class NetworkStatisticsPublic(BaseModel):
    nr_tags: int
    nr_identifiers_explicit: int
    nr_identifiers_implicit: int | None
    nr_labels: int


class TagstoreStatisticsPublic(BaseModel):
    by_network: Dict[str, NetworkStatisticsPublic]


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
    is_cluster_definer: bool
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
            is_cluster_definer=t.is_cluster_definer,
            network=t.network,
            lastmod=int(round(t.lastmod.timestamp())),
            group=tp.acl_group,
        )


# Statements


def _get_tags_by_subjectid_stmt(
    identifier: str,
    offset: int | None,
    page_size: int | None,
    groups: List[str],
    network: str | None,
):
    q = (
        select(Tag, TagPack)
        .options(selectinload(Tag.confidence))
        .where(Tag.identifier == identifier)
        .where(Tag.tagpack_id == TagPack.id)
        .where(TagPack.acl_group.in_(groups))
        .offset(offset)
        .limit(page_size)
    )

    if network is not None:
        q = q.where(Tag.network == network)
    return q


def _get_tag_by_id_stmt(tag_id: int, groups: List[str]):
    return (
        select(Tag, TagPack)
        .options(selectinload(Tag.confidence))
        .where(Tag.id == tag_id)
        .where(Tag.tagpack_id == TagPack.id)
        .where(TagPack.acl_group.in_(groups))
        .limit(1)
    )


def _get_best_cluster_tag_stmt(cluster_id: int, network: str, groups: List[str]):
    return (
        select(Tag, TagPack, BestClusterTagView)
        .options(selectinload(Tag.confidence))
        .where(BestClusterTagView.cluster_id == cluster_id)
        .where(BestClusterTagView.network == network)
        .where(Tag.tagpack_id == TagPack.id)
        .where(BestClusterTagView.tag_id == Tag.id)
        .where(TagPack.acl_group.in_(groups))
        .limit(1)
    )


def _get_tags_by_actorid_stmt(
    actor: str,
    offset: int | None,
    page_size: int | None,
    groups: List[str],
    network: str | None,
):
    q = (
        select(Tag, TagPack)
        .options(selectinload(Tag.confidence))
        .where(Tag.actor_id == actor)
        .where(Tag.tagpack_id == TagPack.id)
        .where(TagPack.acl_group.in_(groups))
        .offset(offset)
        .limit(page_size)
    )
    if network is not None:
        q = q.where(Tag.network == network)
    return q


def _get_tags_by_clusterid_stmt(
    cluster_id: int,
    network: str,
    offset: int | None,
    page_size: int | None,
    groups: List[str],
):
    return (
        select(Tag, TagPack, AddressClusterMapping)
        .options(selectinload(Tag.confidence))
        .where(AddressClusterMapping.gs_cluster_id == cluster_id)
        .where(AddressClusterMapping.address == Tag.identifier)
        .where(AddressClusterMapping.network == network)
        .where(Tag.tagpack_id == TagPack.id)
        .where(TagPack.acl_group.in_(groups))
        .offset(offset)
        .limit(page_size)
    )


def _get_tags_by_label_stmt(
    label: str,
    offset: int | None,
    page_size: int | None,
    groups: List[str],
    network: str | None,
):
    q = (
        select(Tag, TagPack)
        .options(selectinload(Tag.confidence))
        .where(Tag.label.like(f"%{label}%"))
        .where(Tag.tagpack_id == TagPack.id)
        .where(TagPack.acl_group.in_(groups))
        .offset(offset)
        .limit(page_size)
    )
    if network is not None:
        q = q.where(Tag.network == network)
    return q


def _get_actor_by_id_stmt(actor: str):
    return select(Actor).where(Actor.id == actor)


def _get_actor_tag_count_stmt(actor: str):
    return select(func.count()).select_from(Tag).where(Tag.actor_id == actor)


def _get_per_network_statistics_stmt():
    return select(
        Tag.network,
        func.count(Tag.identifier),
        func.count(distinct(Tag.identifier)),
        func.count(distinct(Tag.label)),
    ).group_by(Tag.network)


def _get_per_network_statistics_cached_stmt():
    return text(
        "select network, nr_labels, nr_tags, nr_identifiers_explicit, nr_identifiers_implicit from statistics"
    )


def _get_count_by_cluster_stmt(cluster_id: int, network: str, groups: List[str]):
    return (
        select(TagCountByClusterView)
        .where(TagCountByClusterView.network == network)
        .where(TagCountByClusterView.gs_cluster_id == cluster_id)
        .where(TagCountByClusterView.acl_group.in_(groups))
    )


def _get_similar_actors_stmt(query: str, limit: int):
    return (
        select(
            Actor.label,
            Actor.id,
            func.similarity(Actor.label, query).label("sim_score"),
        )
        .where(func.similarity(Actor.label, query) > 0.2)
        .order_by(desc("sim_score"))
        .limit(limit)
        .distinct()
    )


def _get_similar_tag_labels_stmt(query: str, limit: int, groups: List[str]):
    return (
        select(Tag.label, func.similarity(Tag.label, query).label("sim_score"))
        .where(func.similarity(Tag.label, query) > 0.2)
        .where(Tag.tagpack_id == TagPack.id)
        .where(TagPack.acl_group.in_(groups))
        .group_by(Tag.label, "sim_score")
        .order_by(desc("sim_score"), Tag.label)
        .limit(limit)
    )


def _get_actors_for_subject_stmt(subject_id: str, groups: List[str]):
    return (
        select(Actor.id, Actor.label)
        .where(Tag.identifier == subject_id)
        .where(Actor.id.isnot(None))
        .where(Actor.id == Tag.actor_id)
        .where(Tag.tagpack_id == TagPack.id)
        .where(TagPack.acl_group.in_(groups))
        .order_by(Actor.label)
        .distinct()
    )


def _get_actors_for_clusterid_stmt(cluster_id: int, network: int, groups: List[str]):
    return (
        select(Actor.id, Actor.label)
        .where(AddressClusterMapping.gs_cluster_id == cluster_id)
        .where(AddressClusterMapping.address == Tag.identifier)
        .where(AddressClusterMapping.network == network)
        .where(Actor.id.isnot(None))
        .where(Actor.id == Tag.actor_id)
        .where(Tag.tagpack_id == TagPack.id)
        .where(TagPack.acl_group.in_(groups))
        .order_by(Actor.label)
        .distinct()
    )


def _get_labels_by_subjectid_stmt(subject_id: str, groups: List[str]):
    return (
        select(Tag.label)
        .where(Tag.identifier == subject_id)
        .where(Tag.tagpack_id == TagPack.id)
        .where(TagPack.acl_group.in_(groups))
        .order_by(desc(Tag.label))
        .distinct()
    )


def _get_labels_by_clusterid_stmt(cluster_id: str, groups: List[str]):
    return (
        select(Tag.label)
        .where(AddressClusterMapping.gs_cluster_id == cluster_id)
        .where(AddressClusterMapping.address == Tag.identifier)
        .where(Tag.tagpack_id == TagPack.id)
        .where(TagPack.acl_group.in_(groups))
        .order_by(desc(Tag.label))
        .distinct()
    )


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

    # get Tag by id

    # Get Tags by subject id
    @_inject_session
    async def _get_tag_by_id(
        self,
        tag_id: int,
        groups: List[str],
        session=None,
    ) -> Tag | None:
        return await session.exec(_get_tag_by_id_stmt(tag_id, groups)).first()

    @_inject_session
    async def get_tag_by_id(
        self,
        tag_id: str,
        groups: List[str],
        session=None,
    ) -> TagPublic | None:
        result = await self._get_tag_by_id(tag_id, groups, session=session)
        if result is not None:
            t, tp = result
            return TagPublic.fromDB(t, tp)

        return None

    # Get Tags by subject id
    @_inject_session
    async def _get_tags_by_subjectid(
        self,
        identifier: str,
        offset: int,
        page_size: int,
        groups: List[str],
        network: str | None = None,
        session=None,
    ) -> List[Tag]:
        return await session.exec(
            _get_tags_by_subjectid_stmt(
                identifier, offset, page_size, groups, network=network
            )
        )

    @_inject_session
    async def get_tags_by_subjectid(
        self,
        subject_id: str,
        offset: int | None,
        page_size: int | None,
        groups: List[str],
        network: str | None = None,
        session=None,
    ) -> List[TagPublic]:
        results = await self._get_tags_by_subjectid(
            subject_id,
            offset,
            page_size,
            groups,
            network=network,
            session=session,
        )
        return [TagPublic.fromDB(t, tp) for t, tp in results]

    @_inject_session
    async def get_actors_by_subjectid(
        self, subject_id: str, groups: List[str], session=None
    ) -> List[HumanReadableId]:
        results = await session.exec(_get_actors_for_subject_stmt(subject_id, groups))
        return [HumanReadableId(id=idt, label=lbl) for idt, lbl in results]

    @_inject_session
    async def get_labels_by_subjectid(
        self, subject_id: str, groups: List[str], session=None
    ) -> List[str]:
        results = await session.exec(_get_labels_by_subjectid_stmt(subject_id, groups))
        return [x for x in results]

    @_inject_session
    async def get_labels_by_clusterid(
        self, cluster_id: str, groups: List[str], session=None
    ) -> List[str]:
        results = await session.exec(_get_labels_by_clusterid_stmt(cluster_id, groups))
        return [x for x in results]

    # Get Tags by Label
    @_inject_session
    async def _get_tags_by_label(
        self,
        label: str,
        offset: int | None,
        page_size: int | None,
        groups: List[str],
        network: str | None = None,
        session=None,
    ) -> List[Tag]:
        return await session.exec(
            _get_tags_by_label_stmt(label, offset, page_size, groups, network=network)
        )

    @_inject_session
    async def get_tags_by_label(
        self,
        label: str,
        offset: int | None,
        page_size: int | None,
        groups: List[str],
        network: str | None = None,
        session=None,
    ) -> List[TagPublic]:
        results = await self._get_tags_by_label(
            label, offset, page_size, groups, network=network, session=session
        )
        return [TagPublic.fromDB(t, tp) for t, tp in results]

    # Cluster

    @_inject_session
    async def _get_tags_by_clusterid(
        self,
        cluster_id: int,
        network: str,
        offset: int | None,
        page_size: int | None,
        groups: List[str],
        session=None,
    ) -> List[Tag]:
        return await session.exec(
            _get_tags_by_clusterid_stmt(cluster_id, network, offset, page_size, groups)
        )

    @_inject_session
    async def get_tags_by_clusterid(
        self,
        cluster_id: int,
        network: str,
        offset: int | None,
        page_size: int | None,
        groups: List[str],
        session=None,
    ) -> List[TagPublic]:
        results = await self._get_tags_by_clusterid(
            cluster_id, network, offset, page_size, groups, session=session
        )
        return [TagPublic.fromDB(t, tp) for t, tp, _ in results]

    async def get_nr_tags_by_clusterid(
        self, cluster_id: int, network: str, groups: List[str], session=None
    ) -> int:
        results = await session.exec(
            _get_count_by_cluster_stmt(cluster_id, network, groups)
        )

        return sum(x.count for x in results)

    @_inject_session
    async def get_actors_by_clusterid(
        self, cluster_id: int, network: str, groups: List[str], session=None
    ) -> List[HumanReadableId]:
        results = await session.exec(
            _get_actors_for_clusterid_stmt(cluster_id, network, groups)
        )
        return [HumanReadableId(id=idt, label=lbl) for idt, lbl in results]

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
        offset: int | None,
        page_size: int | None,
        groups: List[str],
        network: str | None = None,
        session=None,
    ) -> List[Tag]:
        return await session.exec(
            _get_tags_by_actorid_stmt(actor, offset, page_size, groups, network=network)
        )

    @_inject_session
    async def get_tags_by_actorid(
        self,
        actor: str,
        offset: int | None,
        page_size: int | None,
        groups: List[str],
        network: str | None = None,
        session=None,
    ) -> List[TagPublic]:
        results = await self._get_tags_by_actorid(
            actor, offset, page_size, groups, network=network, session=session
        )
        return [TagPublic.fromDB(t, tp) for t, tp in results]

    # Other tag stuff

    @_inject_session
    async def get_best_cluster_tag(
        self, cluster_id: int, network: str, groups: List[str], session=False
    ) -> TagPublic | None:
        result = await session.exec(
            _get_best_cluster_tag_stmt(cluster_id, network, groups, session=session)
        ).first()
        if result is not None:
            t, tp, _ = result
            return TagPublic.fromDB(t, tp)

        return None

    # Other
    @_inject_session
    async def get_taxonomies(
        self, include: Set[Taxonomies] = _ALL_TAXONOMIES, session=None
    ) -> TaxonomiesPublic:
        return TaxonomiesPublic(
            confidence=(
                None
                if Taxonomies.CONFIDENCE not in include
                else (
                    [
                        ConfidencePublic(**{"source": None, **(x.model_dump())})
                        for x in (await session.exec(select(Confidence)))
                    ]
                )
            ),
            country=(
                None
                if Taxonomies.COUNTRY not in include
                else (
                    [
                        ItemDescriptionPublic(**(x.model_dump()))
                        for x in (await session.exec(select(Country)))
                    ]
                )
            ),
            tag_subject=(
                None
                if Taxonomies.TAG_SUBJECT not in include
                else (
                    [
                        ItemDescriptionPublic(**(x.model_dump()))
                        for x in (await session.exec(select(TagSubject)))
                    ]
                )
            ),
            tag_type=(
                None
                if Taxonomies.TAG_TYPE not in include
                else (
                    [
                        ItemDescriptionPublic(**(x.model_dump()))
                        for x in (await session.exec(select(TagType)))
                    ]
                )
            ),
            concept=(
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

    @_inject_session
    async def get_network_statistics(self, session=None) -> TagstoreStatisticsPublic:
        results = await session.exec(_get_per_network_statistics_stmt())
        return TagstoreStatisticsPublic(
            by_network={
                net.upper(): NetworkStatisticsPublic(
                    nr_tags=nr_tags,
                    nr_identifiers_explicit=nr_identifiers,
                    nr_labels=nr_labels,
                    nr_identifiers_implicit=None,
                )
                for net, nr_tags, nr_identifiers, nr_labels in results
            }
        )

    @_inject_session
    async def get_network_statistics_cached(
        self, session=None
    ) -> TagstoreStatisticsPublic:
        results = await session.exec(_get_per_network_statistics_cached_stmt())
        return TagstoreStatisticsPublic(
            by_network={
                net.upper(): NetworkStatisticsPublic(
                    nr_tags=nr_tags,
                    nr_identifiers_explicit=nr_i_explicit,
                    nr_identifiers_implicit=nr_i_impicit,
                    nr_labels=nr_labels,
                )
                for net, nr_labels, nr_tags, nr_i_explicit, nr_i_impicit in results
            }
        )

    @_inject_session
    async def search_tag_labels(
        self, label: str, limit: int, groups: List[str], session=None
    ) -> List[str]:
        results = await session.exec(_get_similar_tag_labels_stmt(label, limit, groups))
        return [a for a, _ in results]

    @_inject_session
    async def search_actor_labels(
        self, label: str, limit: int, session=None
    ) -> List[HumanReadableId]:
        results = await session.exec(_get_similar_actors_stmt(label, limit))
        return [HumanReadableId(id=itm, label=lbl) for lbl, itm, _ in results]

    @_inject_session
    async def search_labels(
        self, label: str, limit: int, groups: List[str], session=None
    ) -> LabelSearchResultPublic:
        return LabelSearchResultPublic(
            actor_labels=await self.search_actor_labels(label, limit, session=session),
            tag_labels=[
                HumanReadableId(id=x, label=x)
                for x in (
                    await self.search_tag_labels(label, limit, groups, session=session)
                )
            ],
        )
