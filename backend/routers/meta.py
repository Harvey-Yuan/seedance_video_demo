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
    说明：所有下游能力（LLM、Ark 图像/视频、Storage）均由 **本服务** 在
    `POST /api/runs` 触发的流水线内编排调用；客户端不应直连 Butterbase Chat
    或 BytePlus Ark，除非另行做安全与鉴权设计。
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
                "唯一编排入口：POST /api/runs 在后台依次调用 "
                "编剧(LLM)→定妆(ModelArk 图像)→导演(LLM)→多段 Seedance(视频)→"
                "ffmpeg 拼接→（可选）Butterbase Storage 上传。"
            ),
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
