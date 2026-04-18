import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException

from .. import db
from ..api_schemas import CreateRunBody, CreateRunResponse
from ..pipeline_agents import (
    run_director_agent,
    run_full_pipeline,
    run_makeup_agent,
    run_seedance_merge_agent,
    run_writer_agent,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Runs"])


def _run_row(run_id: str) -> dict:
    row = db.get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return row


def _envelope(run_id: str) -> dict:
    row = _run_row(run_id)
    return {"ok": row["status"] != "failed", "run": row}


async def _run_safe_full(run_id: str):
    try:
        await run_full_pipeline(run_id)
    except Exception:
        logger.exception("background full pipeline crashed")
        db.update_run(
            run_id,
            status="failed",
            error_code="INTERNAL",
            error_message="Unhandled background error",
        )


@router.post("/runs", response_model=CreateRunResponse)
async def create_run(body: CreateRunBody):
    """仅创建任务（draft），不自动跑流水线；请依次调用 writer / director / makeup / seedance。"""
    if not body.drama.strip():
        raise HTTPException(status_code=400, detail="drama must not be empty")
    run_id = db.create_run(body.drama.strip(), user_id=None)
    return CreateRunResponse(id=run_id, status="draft")


@router.post("/runs/{run_id}/pipeline")
async def create_run_pipeline(run_id: str, background_tasks: BackgroundTasks):
    """
    可选「一键」：后台顺序执行四步（与前端连调四个 API 等价）。
    需当前为 draft 且无各阶段输出；返回 202 仅表示已排队。
    """
    row = _run_row(run_id)
    if row["status"] != "draft":
        raise HTTPException(409, detail="pipeline requires status=draft")
    if any(
        row.get(k)
        for k in ("layer1_output", "layer2_output", "makeup_output", "layer3_output")
    ):
        raise HTTPException(409, detail="outputs must be empty to start pipeline")
    background_tasks.add_task(_run_safe_full, run_id)
    return {"accepted": True, "run_id": run_id, "note": "poll GET /api/runs/{id} for progress"}


@router.post("/runs/{run_id}/writer")
async def step_writer(run_id: str):
    row = _run_row(run_id)
    if row.get("layer1_output"):
        raise HTTPException(409, detail="layer1_output already exists")
    if row.get("status") == "layer1_running":
        raise HTTPException(409, detail="writer already in progress")
    if row.get("layer3_output"):
        raise HTTPException(409, detail="run already finished with layer3")
    try:
        await run_writer_agent(run_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _envelope(run_id)


@router.post("/runs/{run_id}/director")
async def step_director(run_id: str):
    row = _run_row(run_id)
    if not row.get("layer1_output"):
        raise HTTPException(400, detail="requires layer1_output from writer first")
    if row.get("layer3_output"):
        raise HTTPException(409, detail="run already has layer3_output")
    if row.get("status") == "layer2_running":
        raise HTTPException(409, detail="director already in progress")
    try:
        await run_director_agent(run_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _envelope(run_id)


@router.post("/runs/{run_id}/makeup")
async def step_makeup(run_id: str):
    row = _run_row(run_id)
    if not row.get("layer1_output"):
        raise HTTPException(400, detail="requires layer1_output from writer first")
    if row.get("layer3_output"):
        raise HTTPException(409, detail="run already has layer3_output")
    if row.get("status") == "makeup_running":
        raise HTTPException(409, detail="makeup already in progress")
    try:
        await run_makeup_agent(run_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _envelope(run_id)


@router.post("/runs/{run_id}/seedance")
async def step_seedance(run_id: str):
    row = _run_row(run_id)
    if not row.get("layer2_output") or not row.get("makeup_output"):
        raise HTTPException(
            400,
            detail="requires layer2_output (director) and makeup_output (makeup)",
        )
    if row.get("layer3_output"):
        raise HTTPException(409, detail="layer3_output already exists")
    if row.get("status") == "layer3_running":
        raise HTTPException(409, detail="seedance already in progress")
    try:
        await run_seedance_merge_agent(run_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _envelope(run_id)


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    return _run_row(run_id)
