"""Orchestration and integration status (no secrets; for frontend / ops probes)."""

import shutil
from pathlib import Path

from fastapi import APIRouter

from ..settings import get_settings

router = APIRouter(tags=["Meta"])


def _ffmpeg_resolved() -> tuple[bool, str | None]:
    s = get_settings()
    raw = (s.ffmpeg_path or "ffmpeg").strip() or "ffmpeg"
    exe = raw if Path(raw).is_file() else (shutil.which(raw) or shutil.which("ffmpeg"))
    return (exe is not None, exe)


@router.get("/meta")
def api_meta():
    """
    Butterbase LLM, ModelArk image/video, and Storage are invoked **by this service** inside
    `POST /api/runs/.../writer|director|makeup|seedance` or optional `.../pipeline`.
    Clients call only this API; do not send API keys to the browser for direct Ark calls.
    """
    s = get_settings()
    ffmpeg_ok, ffmpeg_exe = _ffmpeg_resolved()
    llm_kind = (
        "butterbase"
        if s.uses_butterbase_llm()
        else ("openai" if s.openai_api_key else "none")
    )
    return {
        "orchestration": {
            "service": "seedance-backend",
            "description": (
                "POST /api/runs only creates draft; then POST "
                "/api/runs/{id}/writer → /makeup → /director → /seedance (seedance returns 202, "
                "poll seedance/status); or POST /api/runs/{id}/pipeline to run all four in the background."
            ),
            "steps": [
                "POST /api/runs/{run_id}/writer",
                "POST /api/runs/{run_id}/makeup",
                "POST /api/runs/{run_id}/director",
                "POST /api/runs/{run_id}/seedance",
            ],
            "poll_run": "GET /api/runs/{run_id}",
            "poll_seedance": "GET /api/runs/{run_id}/seedance/status (after POST seedance returns 202)",
        },
        "integrations": {
            "llm_chat": {
                "provider": llm_kind,
                "layer1_model": s.layer1_model,
                "layer2_model": s.layer2_model,
                "json_mode_request": s.butterbase_json_response
                if s.uses_butterbase_llm()
                else True,
            },
            "byteplus_modelark": {
                "api_key_configured": bool(s.seedance_api_key),
                "video_model": s.seedance_video_model,
                "makeup_image_model": s.makeup_image_model,
                "ark_video_base_env": "SEEDANCE_ARK_BASE_URL",
                "ark_image_base_env": "ARK_IMAGE_BASE_URL",
            },
            "ffmpeg": {
                "available": ffmpeg_ok,
                "resolved_executable": ffmpeg_exe,
                "config_env": "FFMPEG_PATH",
            },
            "butterbase_storage": {
                "will_upload_after_merge": s.uses_butterbase_llm(),
                "uses_same_app_and_key_as_llm": True,
            },
        },
    }
