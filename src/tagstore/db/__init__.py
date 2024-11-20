from enum import IntEnum
from typing import List, Set

from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from .database import get_db_engine_async
from .models import Concept, Confidence, Country, Tag, TagPack, TagSubject, TagType


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


class TagPublic(BaseModel):
    identifier: str
    label: str
    source: str
    creator: str
    confidence: str
    confidence_level: int
    tag_subject: str
    tag_type: str
    main_concept: str | None
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
            main_concept=mainc.concept_id if mainc else None,
            additional_concepts=[x.concept_id for x in c if x != mainc],
            network=t.network,
            lastmod=t.lastmod.timestamp(),
            group=tp.acl_group,
        )


# Statements
def _get_tags_by_id_stmt(
    identifier: str, offset: int, page_size: int, groups: List[str]
):
    return (
        select(Tag, TagPack)
        .where(Tag.identifier == identifier)
        .where(Tag.tagpack_id == TagPack.id)
        .where(TagPack.acl_group.in_(groups))
        .offset(offset)
        .limit(page_size)
    )


def _get_tags_by_label_stmt(label: str, offset: int, page_size: int, groups: List[str]):
    return (
        select(Tag, TagPack)
        .where(Tag.label.like(f"%{label}%"))
        .where(Tag.tagpack_id == TagPack.id)
        .where(TagPack.acl_group.in_(groups))
        .offset(offset)
        .limit(page_size)
    )


# Facades


class TagstoreDbAsync:

    engine = None

    def __init__(self, engine):
        self.engine = engine

    @staticmethod
    def from_engine(db_url):
        return TagstoreDbAsync(get_db_engine_async(db_url))

    # Get Tags by Id

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

    async def get_tags_by_id(
        self,
        identifier: str,
        offset: int,
        page_size: int,
        groups: List[str],
        session=None,
    ) -> List[TagPublic]:
        async with session or AsyncSession(self.engine) as session:
            results = await self._get_tags_by_id(
                identifier, offset, page_size, groups, session
            )
            return [TagPublic.fromDB(t, tp) for t, tp in results]

    # Get Tags by Label

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

    async def get_tags_by_label(
        self,
        label: str,
        offset: int,
        page_size: int,
        groups: List[str],
        session=None,
    ) -> List[TagPublic]:
        async with session or AsyncSession(self.engine) as session:
            results = await self._get_tags_by_label(
                label, offset, page_size, groups, session
            )
            return [TagPublic.fromDB(t, tp) for t, tp in results]

    async def get_taxonomies(
        self, include: Set[Taxonomies], session=None
    ) -> TaxonomiesPublic:
        async with session or AsyncSession(self.engine) as session:
            return TaxonomiesPublic(
                confidences=(
                    None
                    if Taxonomies.CONFIDENCE not in include
                    else (
                        [
                            ConfidencePublic(**(x.model_dump()))
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
