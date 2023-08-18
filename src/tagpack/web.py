from typing import List

from fastapi import FastAPI
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from tagpack.tagstore import TagStore


class Tag(BaseModel):
    label: str
    src: str


class WebSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="gs_tagpack_tool_")
    db_url: str = "localhost:5421"


app = FastAPI()
settings = WebSettings()

db = TagStore(settings.db_url, "tagstore")


@app.get("/")
def root():
    return {"message": "Hello World"}


@app.get("/search/{search_string}")
def search() -> List[Tag]:
    return [{"label": x["uri"], "src": x["uri"]} for x in db.tagstore_source_repos()]


@app.get("/info")
def info():
    return {
        "db": settings.db_url,
    }
