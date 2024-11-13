from datetime import datetime

from sqlmodel import Field, SQLModel


class Tag(SQLModel, table=True):

    __table_args__ = {"schema": "tagstore"}

    id: int | None = Field(default=None, primary_key=True)  # noqa
    label: str
    source: str | None
    context: str | None
    is_cluster_definer: bool = Field(default=False)
    lastmod: datetime
    identifier: str
    asset: str | None
    network: str
    confidence: str = Field(foreign_key="concept.id")
    tagpack: str = Field(foreign_key="tagpack.id")
    actor: str = Field(foreign_key="actor.id")
