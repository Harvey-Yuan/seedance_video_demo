import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import db
from .pipeline import run_pipeline
from .settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Seedance Multi-Agent Flow", lifespan=lifespan)

_settings = get_settings()
_origins = [o.strip() for o in _settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateRunBody(BaseModel):
    drama: str = Field(min_length=1, max_length=32000)


class CreateRunResponse(BaseModel):
    id: str
    status: str


@app.get("/api/health")
def health():
    return {"ok": True, "product_note": get_settings().product_note_zh}


@app.post("/api/runs", response_model=CreateRunResponse)
async def create_run(body: CreateRunBody, background_tasks: BackgroundTasks):
    if not body.drama.strip():
        raise HTTPException(status_code=400, detail="drama must not be empty")
    run_id = db.create_run(body.drama.strip(), user_id=None)
    background_tasks.add_task(_run_safe, run_id)
    return CreateRunResponse(id=run_id, status="draft")


async def _run_safe(run_id: str):
    try:
        await run_pipeline(run_id)
    except Exception:
        logger.exception("background pipeline crashed")
        db.update_run(
            run_id,
            status="failed",
            error_code="INTERNAL",
            error_message="Unhandled background error",
        )


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    row = db.get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return row
