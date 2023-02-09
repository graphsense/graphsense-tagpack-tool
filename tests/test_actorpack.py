from datetime import date

import pytest

from tagpack.actorpack import ActorPack
from tagpack.actorpack_schema import ActorPackSchema
from tagpack.taxonomy import Taxonomy


@pytest.fixture
def schema(monkeypatch):
    tagpack_schema = ActorPackSchema()

    return tagpack_schema


@pytest.fixture
def taxonomies():
    tax_entity = Taxonomy("entity", "http://example.com/entity")
    tax_entity.add_concept("exchange", "Exchange", None, "Some description")

    tax_abuse = Taxonomy("abuse", "http://example.com/abuse")
    tax_abuse.add_concept("bad_coding", "Bad coding", None, "Really bad")

    country = Taxonomy("country", "http://example.com/abuse")
    country.add_concept("AT", "Austria", None, "nice for vacations")
    country.add_concept("BE", "Belgium", None, "nice for vacations")

    taxonomies = {"entity": tax_entity, "abuse": tax_abuse, "country": country}
    return taxonomies


@pytest.fixture
def actorpack(schema, taxonomies):
    return ActorPack(
        "http://example.com",
        {
            "title": "ETH Defilama Actors",
            "creator": "GraphSense Team",
            "lastmod": date.fromisoformat("2021-04-21"),
            "categories": ["exchange"],
            "actors": [
                {
                    "id": "0xnodes",
                    "label": "0x nodes",
                    "uri": "https://0xnodes.io/",
                    "jurisdictions": ["AT", "BE"],
                    "context": "{'blub': 1234}",
                },  # inherits all header fields
            ],
        },
        schema,
        taxonomies,
    )


def test_context_there(actorpack):
    assert actorpack.actors[0].contents["context"] == "{'blub': 1234}"


def test_validate(actorpack):
    assert actorpack.validate()
