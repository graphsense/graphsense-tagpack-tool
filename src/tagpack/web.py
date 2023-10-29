from typing import List, Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from tagpack.tagstore import TagStore


class Tag(BaseModel):
    label: str
    src: str


class WebSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="gs_tagpack_tool_")
    db_url: str = "localhost:5421"


tags_metadata = [
    {
        "name": "General",
        "description": "General.",
    },
    {
        "name": "Address",
        "description": "Address operations.",
    },
    {
        "name": "Entity",
        "description": "Entity operations.",
    },
    {
        "name": "Actor",
        "description": "Actor operations.",
    },
]


app = FastAPI(openapi_tags=tags_metadata)
settings = WebSettings()

db = TagStore(settings.db_url, "tagstore")


@app.get("/General/{General_string}", tags=["General"])
def General() -> List[Tag]:
    return [{"label": x["uri"], "src": x["uri"]} for x in db.tagstore_source_repos()]


@app.get("/info", tags=["General"])
def info():
    return {
        "db": settings.db_url,
    }


@app.get("/taxonomies", tags=["General"])
def get_taxonomies():
    return {"taxonomies": db.taxonomies()}


@app.get("/concepts/{taxonomy}", tags=["General"])
def get_concepts(taxonomy: str):
    return {"concepts": db.concepts(taxonomy)}


@app.get("/{General_string}/label", tags=["General"])
def get_matching_labels(
    General_string: str, private: Optional[bool] = False, limit: Optional[int] = 20
):
    return {"labels": db.labels(General_string, private, limit)}


@app.get("/{label}/tags", tags=["General"])
def get_address_tags(
    label: str,
    private: Optional[bool] = False,
    page: Optional[int] = 0,
    pagesize: Optional[int] = None,
):
    return {"tags": db.tags_by_label(label, private, page, pagesize)}


@app.get("/address/{address}/tags", tags=["Address"])
def get_tags_by_address(
    address: str,
    private: Optional[bool] = False,
    page: Optional[int] = 0,
    pagesize: Optional[int] = None,
):
    return {"tags": db.tags_by_address(address, private, page, pagesize)}


@app.get("/{network}/entity/{entity}", tags=["Entity"])
def list_tags_by_entity(
    network: str,
    entity: int,
    private: Optional[bool] = False,
    page: Optional[int] = 0,
    pagesize: Optional[int] = None,
):
    return {"tags": db.tags_by_entity(network, entity, private, page, pagesize)}


@app.get("/{network}/entity/{entity}/count", tags=["Entity"])
def count_labels_by_entity(network: str, entity: int):
    return {"counts": db.count_labels_by_entity(network, entity)}


@app.get("/{network}/count", tags=["General"])
def count_labels_for_networks(network: str):
    return {"counts": db.count_labels_by_network(network)}


@app.get("/{network}/entity/{entity}/best_tag", tags=["Entity"])
def get_best_entity_tag(network: str, entity: int, private: Optional[bool] = False):
    return {"tag": db.best_entity_tag(network, entity, private)}


@app.get("/{network}/tags/entities", tags=["Entity"])
def get_labels_for_entities(
    network: str, entities: list[int] = Query(), private: Optional[bool] = False
):
    return {"tags": db.tags_for_entities(network, entities, private)}


@app.get("/{network}/tags/addresses", tags=["Address"])
def get_labels_for_addresses(
    network: str, addresses: list[str] = Query(), private: Optional[bool] = False
):
    return {"tags": db.tags_for_addresses(network, addresses, private)}


@app.get("/{network}/actor/{address}", tags=["Actor"])
def get_actors_for_address(network: str, address: str, private: Optional[bool] = False):
    return {"actors": db.actors_for_address(network, address, private)}


@app.get("/{network}/actor/{entity}", tags=["Actor"])
def get_actors_for_entity(network: str, entity: int, private: Optional[bool] = False):
    return {"actors": db.actors_for_entity(network, entity, private)}


@app.get("/actor/{id}", tags=["Actor"])
def get_actor(id: str):
    return {"actor": db.get_actor(id)}


@app.get("/actor/{id}/categories", tags=["Actor"])
def get_actor_categories(id: str):
    return {"categories": db.get_actor_categories(id)}


@app.get("/actor/{id}/jurisdictions", tags=["Actor"])
def get_actor_jurisdictions(id: str):
    return {"jurisdictions": db.get_actor_jurisdictions(id)}


@app.get("/actor/{id}/tag_count", tags=["Actor"])
def get_number_of_tags_for_actor(id: str):
    return {"tag_count": db.get_nr_of_tags_by_actor(id)}


@app.get("/actor/{id}/tags", tags=["Actor"])
def get_tags_for_actor(
    id: str,
    private: Optional[bool] = False,
    page: Optional[int] = 0,
    pagesize: Optional[int] = None,
):
    return {"tags": db.get_tags_for_actor(id, private, page, pagesize)}
