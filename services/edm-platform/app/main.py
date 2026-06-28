import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.database import Base, engine
from app.modules.core.exceptions import EdmError

# Import every module's models so Base.metadata is fully populated before create_all().
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.catalog import models as catalog_models  # noqa: F401
from app.modules.job import models as job_models  # noqa: F401
from app.modules.metadata import models as metadata_models  # noqa: F401
from app.modules.pipeline import models as pipeline_models  # noqa: F401
from app.modules.source import models as source_models  # noqa: F401
from app.modules.workspace import models as workspace_models  # noqa: F401

from app.modules.auth.router import router as auth_router
from app.modules.catalog.router import router as catalog_router
from app.modules.ingestion.router import router as ingestion_router
from app.modules.job.router import router as job_router
from app.modules.pipeline.router import router as pipeline_router
from app.modules.query.router import router as query_router
from app.modules.source.router import router as source_router
from app.modules.workspace.router import router as workspace_router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="EDM Platform", version="0.1.0", lifespan=lifespan)

API_PREFIX = "/api/v1"
for router in (
    auth_router,
    workspace_router,
    source_router,
    ingestion_router,
    pipeline_router,
    job_router,
    catalog_router,
    query_router,
):
    app.include_router(router, prefix=API_PREFIX)


@app.exception_handler(EdmError)
def handle_edm_error(request: Request, exc: EdmError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.get("/health")
def health():
    return {"status": "ok"}
