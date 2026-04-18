import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException

from .. import db
from ..api_schemas import CreateRunBody, CreateRunResponse
from ..pipeline import run_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Runs"])


@router.post("/runs", response_model=CreateRunResponse)
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


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    row = db.get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return row
