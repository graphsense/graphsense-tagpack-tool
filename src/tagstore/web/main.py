from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ..db.database import get_db_engine_async
from .dependencies import _gs_tagstore_settings
from .routers.admin import router as admin_router
from .routers.base import router as base_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    global background_executor
    settings = _gs_tagstore_settings()
    app.state.db_engine = get_db_engine_async(settings.db_url)
    yield


app = FastAPI(
    title="Web API for the GraphSense Tagstore",
    lifespan=lifespan,
    contact={"email": "contact@ikna.io"},
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1234"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(base_router, prefix="/api")
app.include_router(admin_router, prefix="/api/admin", include_in_schema=True)

app.mount("/", StaticFiles(packages=["tagstore.web"], html=True), name="static")
