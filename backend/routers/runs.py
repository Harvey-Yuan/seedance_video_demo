import logging

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from .. import db
from ..api_schemas import CreateRunBody, CreateRunResponse
from ..contracts import Layer2Output, MakeupOutput
from ..pipeline_agents import (
    run_director_agent,
    run_full_pipeline,
    run_makeup_agent,
    run_seedance_merge_background,
    run_writer_agent,
)
from ..settings import get_settings

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


def _seedance_job_running(row: dict) -> bool:
    if row.get("status") != "layer3_running":
        return False
    job = row.get("seedance_job") or {}
    return job.get("phase") in ("queued", "generating", "merging", "uploading")


async def _seedance_task_safe(run_id: str):
    try:
        await run_seedance_merge_background(run_id)
    except Exception:
        logger.exception("seedance background crashed")
        db.update_run(
            run_id,
            status="failed",
            error_code="INTERNAL",
            error_message="seedance background crashed",
        )
        row = db.get_run(run_id)
        job = dict(row.get("seedance_job") or {}) if row else {}
        job["phase"] = "failed"
        job["error_message"] = "seedance background crashed"
        db.update_run(run_id, seedance_job=job)


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
    """Create run (draft) only; does not auto-run pipeline—call writer / makeup / director / seedance in order."""
    if not body.drama.strip():
        raise HTTPException(status_code=400, detail="drama must not be empty")
    run_id = db.create_run(body.drama.strip(), user_id=None)
    return CreateRunResponse(id=run_id, status="draft")


@router.post("/runs/{run_id}/pipeline")
async def create_run_pipeline(run_id: str, background_tasks: BackgroundTasks):
    """
    Optional one-shot: run four steps in the background (same as four separate API calls from the client).
    Requires status=draft and empty stage outputs; 202 means queued only.
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


@router.get("/runs/{run_id}/seedance/status")
def seedance_status(run_id: str):
    """Poll Seedance job: per-segment URLs, merge/upload progress, final video_url."""
    row = _run_row(run_id)
    job = row.get("seedance_job")
    l3 = row.get("layer3_output")
    if l3 and row.get("status") == "done":
        meta = l3.get("meta") or {}
        return {
            "phase": "done",
            "total_segments": len(meta.get("segment_urls") or []),
            "segment_urls": meta.get("segment_urls"),
            "video_url": l3.get("video_url"),
            "run_status": row.get("status"),
            "layer3": l3,
        }
    if not job:
        return {
            "phase": "idle",
            "run_status": row.get("status"),
            "message": "No job yet; POST /api/runs/{id}/seedance first",
        }
    out = dict(job)
    out["run_status"] = row.get("status")
    return out


@router.post("/runs/{run_id}/seedance")
async def step_seedance(run_id: str, background_tasks: BackgroundTasks):
    """
    Accepts work and returns **202**; background generates segments, merges, uploads.
    Poll GET /api/runs/{id}/seedance/status until phase=done, then GET /api/runs/{id} for full run.
    """
    row = _run_row(run_id)
    if not row.get("layer2_output") or not row.get("makeup_output"):
        raise HTTPException(
            400,
            detail="requires layer2_output (director) and makeup_output (makeup)",
        )
    if row.get("layer3_output"):
        raise HTTPException(409, detail="layer3_output already exists")
    if _seedance_job_running(row):
        raise HTTPException(409, detail="seedance job already running")

    settings = get_settings()
    makeup = MakeupOutput.model_validate(row["makeup_output"])
    char_urls = [u for u in (makeup.character_image_urls or []) if u and str(u).strip()]
    if not char_urls:
        raise HTTPException(
            400,
            detail="makeup_output.character_image_urls must be non-empty before seedance",
        )
    layer2 = Layer2Output.model_validate(row["layer2_output"])
    if not layer2.seedance_prompts:
        raise HTTPException(
            400,
            detail="layer2_output.seedance_prompts must be non-empty before seedance",
        )
    layer2_dict = dict(row["layer2_output"])
    layer2_dict["character_image_urls"] = char_urls
    n = len(layer2.seedance_prompts)
    init_job = {
        "phase": "queued",
        "total_segments": n,
        "segment_urls": [],
        "current_segment_index": -1,
        "model": settings.seedance_video_model,
    }
    db.update_run(
        run_id,
        status="layer3_running",
        layer2_output=layer2_dict,
        seedance_job=init_job,
        clear_errors=True,
    )
    background_tasks.add_task(_seedance_task_safe, run_id)
    return JSONResponse(
        status_code=202,
        content={
            "accepted": True,
            "run_id": run_id,
            "status_url": f"/api/runs/{run_id}/seedance/status",
            "poll_hint": "GET status_url every 2–5s until phase is done or failed",
        },
    )


@router.get("/runs/{run_id}/merged-video")
async def merged_video_proxy(run_id: str):
    """
    Stream final MP4 through this API so the browser can play it (some Ark/CDN URLs block
    cross-origin playback or need headers; same-origin URL fixes <video> issues).
    """
    row = _run_row(run_id)
    l3 = row.get("layer3_output") or {}
    url = l3.get("video_url")
    if not url or not isinstance(url, str):
        raise HTTPException(404, detail="no merged video")

    async def stream():
        async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
            async with client.stream(
                "GET",
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; SeedanceStudio/1.0)"},
            ) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes(chunk_size=64 * 1024):
                    yield chunk

    return StreamingResponse(stream(), media_type="video/mp4")


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    return _run_row(run_id)
