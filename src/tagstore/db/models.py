from datetime import datetime
from typing import List

from sqlalchemy import Column, ForeignKey, String
from sqlmodel import Field, Relationship, SQLModel

_SCHEMA = "tagstore"
_SHARED_TABLE_ARGS = {"schema": _SCHEMA}


class ClusterMapping(SQLModel, table=True):
    address: str = Field(primary_key=True)
    network: str = Field(primary_key=True)
    gs_cluster_id: int
    gs_cluster_def_addr: str
    gs_cluster_no_addr: int | None


class ActorPack(SQLModel, table=True):
    __tablename__ = "actorpack"
    __table_args__ = _SHARED_TABLE_ARGS

    id: str | None = Field(default=None, primary_key=True)  # noqa
    title: str
    creator: str
    description: str
    is_public: bool
    uri: str | None
    lastmod: datetime


class Actor(SQLModel, table=True):
    __tablename__ = "actor"
    __table_args__ = _SHARED_TABLE_ARGS

    id: str | None = Field(default=None, primary_key=True)  # noqa
    uri: str | None
    label: str
    context: str
    lastmod: datetime

    # FK data
    actorpack_id: str = Field(
        sa_column=Column("actorpack", String, ForeignKey(f"{_SCHEMA}.actorpack.id"))
    )
    actorpack: ActorPack = Relationship()


class Confidence(SQLModel, table=True):
    __tablename__ = "confidence"
    __table_args__ = _SHARED_TABLE_ARGS

    id: str | None = Field(default=None, primary_key=True)  # noqa
    label: str
    description: str
    level: int


class Concept(SQLModel, table=True):
    __tablename__ = "concept"
    __table_args__ = _SHARED_TABLE_ARGS

    id: str = Field(primary_key=True)  # noqa
    label: str
    source: str
    description: str
    taxonomy: str


class TagPack(SQLModel, table=True):
    __tablename__ = "tagpack"
    __table_args__ = _SHARED_TABLE_ARGS

    id: int | None = Field(default=None, primary_key=True)  # noqa
    uri: str
    creator: str
    acl_group: str


class Tag(SQLModel, table=True):
    __tablename__ = "tag"
    __table_args__ = _SHARED_TABLE_ARGS

    id: int | None = Field(default=None, primary_key=True)  # noqa
    label: str
    source: str | None
    context: str | None
    is_cluster_definer: bool | None = Field(default=False)
    lastmod: datetime
    identifier: str
    asset: str | None
    network: str

    # FK data
    confidence_id: str = Field(
        sa_column=Column("confidence", String, ForeignKey(f"{_SCHEMA}.confidence.id"))
    )
    confidence: Confidence = Relationship()
    tagpack_id: str = Field(
        sa_column=Column("tagpack", String, ForeignKey(f"{_SCHEMA}.tagpack.id"))
    )
    tagpack: TagPack = Relationship()
    actor_id: str = Field(
        sa_column=Column("actor", String, ForeignKey(f"{_SCHEMA}.actor.id"))
    )
    actor: Actor = Relationship()
    concepts: List["TagConcept"] = Relationship(
        sa_relationship_kwargs={"lazy": "subquery"}
    )


class TagConcept(SQLModel, table=True):
    __tablename__ = "tag_concept"
    __table_args__ = _SHARED_TABLE_ARGS

    id: int | None = Field(default=None, primary_key=True)  # noqa
    tag_id: int = Field(foreign_key=f"{_SCHEMA}.tag.id")
    concept_type: str

    # FK data
    concept_id: str = Field(foreign_key=f"{_SCHEMA}.concept.id")
    concept: Concept = Relationship()
