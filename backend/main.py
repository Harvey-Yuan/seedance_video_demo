import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .routers import health, meta, runs
from .settings import get_settings

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="Seedance Multi-Agent Flow",
    description=(
        "对外统一 HTTP 编排：编剧/定妆/导演/多段 Seedance/ffmpeg/Butterbase Storage。"
        "下游 Butterbase Chat、BytePlus ModelArk、Storage 均由本进程调用，详见 `GET /api/meta`。"
    ),
    lifespan=lifespan,
)

_settings = get_settings()
_origins = [o.strip() for o in _settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(meta.router, prefix="/api")
app.include_router(runs.router, prefix="/api")
