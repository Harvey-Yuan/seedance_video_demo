"""编排与集成状态（不含密钥，供前端/运维探测）。"""

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
    说明：Butterbase LLM、ModelArk 图像/视频、Storage 均由 **本服务** 在
    `POST /api/runs/.../writer|director|makeup|seedance` 或可选 `.../pipeline` 内调用；
    客户端只打本 API，不应把密钥发到浏览器直连 Ark。
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
                "POST /api/runs 仅创建 draft；再依次 POST "
                "/api/runs/{id}/writer → /director → /makeup → /seedance；"
                "或 POST /api/runs/{id}/pipeline 后台一键跑四步。"
            ),
            "steps": [
                "POST /api/runs/{run_id}/writer",
                "POST /api/runs/{run_id}/director",
                "POST /api/runs/{run_id}/makeup",
                "POST /api/runs/{run_id}/seedance",
            ],
            "poll_run": "GET /api/runs/{run_id}",
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
