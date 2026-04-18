import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seedance_video import SeedanceTaskError, generate_video, make_ark_client

from . import db
from .contracts import Layer1Output, Layer2Output, Layer3Output
from .llm import chat_json, generate_image_url
from .settings import get_settings

logger = logging.getLogger(__name__)

LAYER1_SYSTEM = """你是影视分镜编剧。用户会提供 personal drama（个人故事/情绪片段）。
请输出 **严格 JSON**（不要 Markdown），键为:
- storyboard: 数组，每项含 shot_id, visual, duration_hint_sec, camera_notes(可选)
- script: 完整旁白/对白混排脚本字符串，体量对应约 3 分钟视频的叙事密度（可分场，不必真的可拍满 180s）
- characters: 数组，每项含 name, description, voice_notes(可选)
- dialogue: 数组，每项含 speaker, line, shot_ref(可选，对应 shot_id)

语言与用户输入一致。visual 要具体、可画。"""

LAYER2_SYSTEM = """你是动漫角色设计师 + Seedance 视频提示词工程师。
输入为 Layer1 的 JSON。输出 **严格 JSON**:
- character_image_urls: 字符串数组，公开可访问的参考图 URL（若暂无真实 URL 用空数组）
- image_prompts_used: 可选，生成参考图时用过的英文 prompt 列表
- seedance_prompts: 数组，每项含 segment_id, prompt, image_refs(可选，为 character_image_urls 的下标列表)

要求:
1) prompt 为英文，适合文生/图生视频模型，包含风格词: anime style, cinematic lighting, consistent character design.
2) 至少 1 条 seedance_prompts；可将 storyboard 合并为 1 段 MVP 短片提示。"""


def _fail(run_id: str, code: str, message: str) -> None:
    db.update_run(
        run_id,
        status="failed",
        error_code=code,
        error_message=message,
    )


async def run_pipeline(run_id: str) -> None:
    settings = get_settings()
    row = db.get_run(run_id)
    if not row:
        logger.error("run not found: %s", run_id)
        return
    drama = row["drama_input"]
    stage = "init"

    try:
        # Layer 1
        stage = "layer1"
        db.update_run(run_id, status="layer1_running")
        raw1 = await chat_json(
            settings,
            model=settings.layer1_model,
            system=LAYER1_SYSTEM,
            user=drama,
        )
        try:
            layer1 = Layer1Output.model_validate(raw1)
        except ValidationError as e:
            _fail(run_id, "LAYER1_PARSE", str(e))
            return
        layer1_dict = layer1.model_dump()
        db.update_run(
            run_id,
            status="layer1_done",
            layer1_output=layer1_dict,
        )

        # Layer 2
        stage = "layer2"
        db.update_run(run_id, status="layer2_running")
        raw2 = await chat_json(
            settings,
            model=settings.layer2_model,
            system=LAYER2_SYSTEM,
            user=json.dumps(layer1_dict, ensure_ascii=False, indent=2),
        )
        try:
            layer2 = Layer2Output.model_validate(raw2)
        except ValidationError as e:
            _fail(run_id, "LAYER2_PARSE", str(e))
            return

        urls: list[str] = list(layer2.character_image_urls)
        img_prompts: list[str] = []
        if not urls and settings.openai_api_key:
            lead = layer1.characters[0] if layer1.characters else None
            if lead:
                ip = (
                    f"Anime character portrait, {lead.name}: {lead.description}. "
                    "Clean background, full upper body, studio lighting, high detail."
                )
                u = await generate_image_url(settings, prompt=ip)
                if u:
                    urls = [u]
                    img_prompts = [ip]
        layer2_dict = layer2.model_dump()
        layer2_dict["character_image_urls"] = urls
        if img_prompts:
            layer2_dict["image_prompts_used"] = (
                layer2_dict.get("image_prompts_used") or []
            ) + img_prompts

        db.update_run(
            run_id,
            status="layer2_done",
            layer2_output=layer2_dict,
        )

        # Layer 3 (blocking poll inside generate_video — run in thread)
        stage = "layer3"
        db.update_run(run_id, status="layer3_running")
        primary = layer2_dict["seedance_prompts"][0]["prompt"]
        model_id = "dreamina-seedance-2-0-260128"
        res = settings.seedance_resolution or None
        if res == "":
            res = None

        def _layer3_sync() -> str:
            client = make_ark_client(api_key=settings.seedance_api_key)
            return generate_video(
                client,
                primary,
                model=model_id,
                ratio=settings.seedance_ratio,
                duration=settings.seedance_duration,
                resolution=res,
                image_urls=urls or None,
                verbose=False,
                on_status=lambda s, tid: logger.info("seedance %s %s", tid, s),
            )

        try:
            video_url = await asyncio.to_thread(_layer3_sync)
        except SeedanceTaskError as e:
            _fail(run_id, "LAYER3_SEEDANCE", str(e))
            return
        except ValueError as e:
            _fail(run_id, "LAYER3_SEEDANCE", str(e))
            return

        layer3 = Layer3Output(
            video_url=video_url,
            model=model_id,
            duration_sec=float(settings.seedance_duration),
            meta={"product_note": settings.product_note_zh},
        )
        db.update_run(
            run_id,
            status="done",
            layer3_output=layer3.model_dump(),
        )
    except asyncio.CancelledError:
        raise
    except ValidationError as e:
        code = "LAYER1_PARSE" if stage == "layer1" else "LAYER2_PARSE"
        _fail(run_id, code, str(e))
    except ValueError as e:
        if stage == "layer1":
            _fail(run_id, "LAYER1_PARSE", str(e))
        elif stage == "layer2":
            _fail(run_id, "LAYER2_PARSE", str(e))
        else:
            _fail(run_id, "INTERNAL", str(e))
    except Exception as e:
        logger.exception("pipeline failed")
        if stage == "layer1":
            code = "LAYER1_LLM"
        elif stage == "layer2":
            code = "LAYER2_LLM"
        elif stage == "layer3":
            code = "LAYER3_SEEDANCE"
        else:
            code = "INTERNAL"
        _fail(run_id, code, str(e))
