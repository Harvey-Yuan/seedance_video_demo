"""
四个可独立调用的编排步骤（由 FastAPI 路由分别触发）。
默认顺序建议：编剧 → 导演 → 定妆 → Seedance 成片（与前端调度一致）。
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seedance_video import SeedanceTaskError, download_video, generate_video, make_ark_client

from . import db
from .ark_images import generate_image_url_sync
from .butterbase_storage import upload_file_and_get_download_url
from .contracts import (
    Layer1Output,
    Layer2Output,
    Layer3Output,
    MakeupOutput,
    MakeupPlan,
    SeedancePromptSegment,
)
from .llm import chat_json
from .settings import get_settings

logger = logging.getLogger(__name__)

LAYER1_SYSTEM = """你是影视分镜编剧。用户会提供 personal drama（个人故事/情绪片段）。

硬性要求（否则视为不合格输出）：
1) 叙事体量对应 **约 1 分钟** 成片（口语密度可拍、镜头少而准）。
2) storyboard **条目要少**；每条 duration_hint_sec **不得超过 15**（可小数）。
3) 整体气质：**有趣、抽象、带一点讽刺或荒诞感**；visual 要具体、可拍、偏真人电影画面（不要写 anime）。
4) 仍输出 **严格 JSON**（不要 Markdown），键为:
   - storyboard: 数组，每项含 shot_id, visual, duration_hint_sec, camera_notes(可选)
   - script: 完整旁白/对白混排脚本字符串
   - characters: 数组，每项含 name, description, voice_notes(可选)
   - dialogue: 数组，每项含 speaker, line, shot_ref(可选，对应 shot_id)

语言与用户输入一致。分镜时长暗示之和请控制在约 55～75 秒范围内。"""

MAKEUP_PLAN_SYSTEM = """你是影视定妆统筹。输入为 Layer1 的 JSON（角色与分镜）。
请输出 **严格 JSON**（不要 Markdown）:
{ "items": [ { "character_key": "与角色 name 对应或稳定英文键", "prompt_en": "英文定妆图 prompt" }, ... ] }

要求：
1) items **1～6 条**，优先覆盖主要角色；每条 prompt_en 适合 **真人写实电影定妆照**（photorealistic cinematic portrait），**禁止 anime / cartoon / 3D doll**。
2) 背景简洁、光线明确、便于后续 I2V 一致；不要包含画面内文字。
3) 不要输出 URL；只输出 JSON。"""

# 导演仅消费编剧 JSON（定妆在后端另一步，此处不传入定妆图 URL）
LAYER2_SYSTEM_SOLO = """你是真人电影导演 + Seedance 视频提示词工程师。

输入包含：
1) 用户的 personal drama 原文；
2) Layer1 的 JSON（分镜/脚本/角色/对白）。

请输出 **严格 JSON**（不要 Markdown）:
{
  "director_notes": "可选：从 drama+Layer1 归纳整体气质（如幽默/浪漫/反转张力等多标签）",
  "seedance_prompts": [ ... ]
}

seedance_prompts：**至少 1 条、至多 6 条**（建议 **2～3 条** 以控制生成时长与费用）。每条必须含:
- segment_id: 稳定英文 id
- prompt: **英文** Seedance 视频描述；强调 **photorealistic cinematic live-action**；**禁止 anime**。
- segment_goal / camera_notes / duration_sec / ratio / resolution / generate_audio / camera_fixed / seed: 可选，含义同 Seedance 参数。

**不要**输出 character_image_urls；**不要**输出 image_refs 或 image_roles（定妆图在后续步骤生成，成片阶段由后端把 I2V 图与定妆 URL 对齐）。"""


def _fail(run_id: str, code: str, message: str) -> None:
    db.update_run(
        run_id,
        status="failed",
        error_code=code,
        error_message=message,
    )


def _validate_layer1_timing(layer1: Layer1Output) -> str | None:
    if not layer1.storyboard:
        return "storyboard 不能为空"
    total = sum(float(s.duration_hint_sec) for s in layer1.storyboard)
    if total > 95:
        return (
            f"storyboard duration_hint_sec 之和为 {total:.1f}s，超过约 1 分钟体量上限，"
            "请压缩分镜或缩短每条时长。"
        )
    return None


def _ffmpeg_concat(ffmpeg_bin: str, segment_paths: list[Path], out_path: Path) -> None:
    if len(segment_paths) == 1:
        shutil.copyfile(segment_paths[0], out_path)
        return
    lst = out_path.with_suffix(".ffconcat.txt")
    lines: list[str] = ["ffconcat version 1.0"]
    for p in segment_paths:
        ap = p.resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{ap}'")
    lst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cmd = [
        ffmpeg_bin,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(lst),
        "-c",
        "copy",
        str(out_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        logger.warning("ffmpeg -c copy failed, re-encoding: %s", e.stderr[:300] if e.stderr else e)
        cmd2 = [
            ffmpeg_bin,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(lst),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
        subprocess.run(cmd2, check=True, capture_output=True, text=True)


def _segment_image_urls(
    seg: SeedancePromptSegment, all_urls: list[str]
) -> tuple[list[str] | None, None]:
    """只传 URL；不传 image_roles（LLM 自定义 role 易导致 Ark InvalidParameter）。"""
    refs = seg.image_refs
    if not refs or not all_urls:
        return None, None
    urls: list[str] = []
    for i in refs:
        if isinstance(i, int) and 0 <= i < len(all_urls):
            urls.append(all_urls[i])
    if not urls:
        return None, None
    return urls, None


async def run_writer_agent(run_id: str) -> None:
    settings = get_settings()
    row = db.get_run(run_id)
    if not row:
        raise ValueError("run not found")
    drama = row["drama_input"]
    db.update_run(run_id, status="layer1_running", clear_errors=True)
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
    err1 = _validate_layer1_timing(layer1)
    if err1:
        _fail(run_id, "LAYER1_PARSE", err1)
        return
    db.update_run(
        run_id,
        status="layer1_done",
        layer1_output=layer1.model_dump(),
    )


async def run_director_agent(run_id: str) -> None:
    settings = get_settings()
    row = db.get_run(run_id)
    if not row or not row.get("layer1_output"):
        raise ValueError("需要先有 layer1_output")
    drama = row["drama_input"]
    layer1_dict = row["layer1_output"]
    db.update_run(run_id, status="layer2_running", clear_errors=True)
    director_user = json.dumps(
        {"drama": drama, "layer1": layer1_dict},
        ensure_ascii=False,
        indent=2,
    )
    raw2 = await chat_json(
        settings,
        model=settings.layer2_model,
        system=LAYER2_SYSTEM_SOLO,
        user=director_user,
    )
    try:
        layer2 = Layer2Output.model_validate(raw2)
    except ValidationError as e:
        _fail(run_id, "LAYER2_PARSE", str(e))
        return
    if not layer2.seedance_prompts:
        _fail(run_id, "LAYER2_PARSE", "seedance_prompts 不能为空")
        return
    if len(layer2.seedance_prompts) > 6:
        _fail(run_id, "LAYER2_PARSE", "seedance_prompts 至多 6 段")
        return
    layer2_dict = layer2.model_dump()
    layer2_dict["character_image_urls"] = layer2_dict.get("character_image_urls") or []
    db.update_run(
        run_id,
        status="layer2_done",
        layer2_output=layer2_dict,
    )


async def run_makeup_agent(run_id: str) -> None:
    settings = get_settings()
    row = db.get_run(run_id)
    if not row or not row.get("layer1_output"):
        raise ValueError("需要先有 layer1_output")
    if not settings.seedance_api_key or not settings.makeup_image_model:
        _fail(run_id, "MAKEUP_CONFIG", "请配置 SEEDANCE_2_0_API 与 MAKEUP_IMAGE_MODEL。")
        return
    layer1_dict = row["layer1_output"]
    db.update_run(run_id, status="makeup_running", clear_errors=True)
    raw_plan = await chat_json(
        settings,
        model=settings.layer2_model,
        system=MAKEUP_PLAN_SYSTEM,
        user=json.dumps(layer1_dict, ensure_ascii=False, indent=2),
    )
    try:
        plan = MakeupPlan.model_validate(raw_plan)
    except ValidationError as e:
        _fail(run_id, "MAKEUP_PARSE", str(e))
        return

    img_base = settings.ark_image_base_url or None

    def _makeup_sync() -> MakeupOutput:
        client = make_ark_client(
            api_key=settings.seedance_api_key,
            base_url=img_base,
        )
        urls: list[str] = []
        prompts_used: list[str] = []
        for it in plan.items:
            u = generate_image_url_sync(
                client,
                model=settings.makeup_image_model,
                prompt=it.prompt_en,
            )
            if u:
                urls.append(u)
                prompts_used.append(it.prompt_en)
        return MakeupOutput(
            character_image_urls=urls,
            makeup_prompts=prompts_used,
            meta={
                "model": settings.makeup_image_model,
                "character_keys": [it.character_key for it in plan.items],
            },
        )

    try:
        makeup = await asyncio.to_thread(_makeup_sync)
    except Exception as e:
        logger.exception("makeup ark")
        _fail(run_id, "MAKEUP_ARK", str(e))
        return
    if not makeup.character_image_urls:
        _fail(run_id, "MAKEUP_ARK", "未能生成任何定妆图 URL。")
        return
    db.update_run(
        run_id,
        status="makeup_done",
        makeup_output=makeup.model_dump(),
    )


async def run_seedance_merge_agent(run_id: str) -> None:
    settings = get_settings()
    row = db.get_run(run_id)
    if not row:
        raise ValueError("run not found")
    if not row.get("layer2_output") or not row.get("makeup_output"):
        raise ValueError("需要 layer2_output 与 makeup_output")
    if not settings.seedance_api_key:
        _fail(run_id, "LAYER3_SEEDANCE", "未配置 SEEDANCE_2_0_API")
        return
    layer2 = Layer2Output.model_validate(row["layer2_output"])
    makeup = MakeupOutput.model_validate(row["makeup_output"])
    char_urls = list(makeup.character_image_urls)
    layer2_dict = row["layer2_output"]
    layer2_dict["character_image_urls"] = char_urls

    db.update_run(
        run_id,
        status="layer3_running",
        layer2_output=layer2_dict,
        clear_errors=True,
    )
    model_id = settings.seedance_video_model

    def _render_and_merge() -> tuple[str, float, dict[str, Any]]:
        client = make_ark_client(api_key=settings.seedance_api_key)
        segment_urls: list[str] = []
        tmpdir = Path(tempfile.mkdtemp(prefix="seedance_run_"))
        seg_files: list[Path] = []
        total_dur = 0.0
        try:
            for seg in layer2.seedance_prompts:
                iu, ir = _segment_image_urls(seg, char_urls)
                dur = int(seg.duration_sec or settings.seedance_duration)
                ratio = seg.ratio or settings.seedance_ratio
                # 多段/I2V 与全局默认组合时 resolution 易触发 Ark InvalidParameter，成片统一交模型默认
                res = None
                url = generate_video(
                    client,
                    seg.prompt,
                    model=model_id,
                    ratio=ratio,
                    duration=dur,
                    resolution=res,
                    image_urls=iu,
                    image_roles=ir,
                    generate_audio=seg.generate_audio,
                    camera_fixed=seg.camera_fixed,
                    seed=seg.seed,
                    verbose=False,
                    on_status=lambda s, tid: logger.info(
                        "seedance seg %s %s %s", seg.segment_id, tid, s
                    ),
                )
                segment_urls.append(url)
                total_dur += float(dur)
                out_seg = tmpdir / f"seg_{len(seg_files):03d}.mp4"
                download_video(url, str(out_seg), verbose=False)
                seg_files.append(out_seg)

            merged = tmpdir / "merged.mp4"
            ff = settings.ffmpeg_path.strip() or "ffmpeg"
            ff_exe = ff if Path(ff).is_file() else (shutil.which(ff) or shutil.which("ffmpeg"))
            if not ff_exe:
                raise FileNotFoundError(
                    "ffmpeg 未安装或不在 PATH 中；请安装 ffmpeg 或设置 FFMPEG_PATH。"
                )
            _ffmpeg_concat(ff_exe, seg_files, merged)

            meta: dict[str, Any] = {
                "segment_urls": segment_urls,
                "merged_bytes": merged.stat().st_size,
                "product_note": settings.product_note_zh,
            }
            video_url = segment_urls[0]
            if settings.uses_butterbase_llm():
                try:
                    dl, oid = upload_file_and_get_download_url(
                        settings,
                        merged,
                        remote_filename=f"{run_id}_merged.mp4",
                        content_type="video/mp4",
                        public=True,
                    )
                    video_url = dl
                    meta["storage_object_id"] = oid
                except Exception as ex:
                    logger.warning("Butterbase upload failed: %s", ex)
                    meta["upload_error"] = str(ex)
                    meta["upload_skipped"] = True
                    video_url = segment_urls[-1]
            else:
                meta["upload_skipped"] = True
                meta["upload_error"] = "未配置 Butterbase，跳过 Storage 上传。"
                video_url = segment_urls[-1]

            return video_url, total_dur, meta
        finally:
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass

    try:
        video_url, total_dur, meta = await asyncio.to_thread(_render_and_merge)
    except SeedanceTaskError as e:
        _fail(run_id, "LAYER3_SEEDANCE", str(e))
        return
    except FileNotFoundError as e:
        _fail(run_id, "LAYER3_FFMPEG", str(e))
        return
    except subprocess.CalledProcessError as e:
        _fail(run_id, "LAYER3_FFMPEG", (e.stderr or str(e))[:800])
        return
    except ValueError as e:
        _fail(run_id, "LAYER3_SEEDANCE", str(e))
        return
    except Exception as e:
        logger.exception("layer3")
        _fail(run_id, "LAYER3_SEEDANCE", str(e))
        return

    layer3 = Layer3Output(
        video_url=video_url,
        model=model_id,
        duration_sec=total_dur,
        meta=meta,
    )
    db.update_run(
        run_id,
        status="done",
        layer3_output=layer3.model_dump(),
    )


async def run_full_pipeline(run_id: str) -> None:
    """顺序执行四步（兼容旧「一键」行为，可由路由 pipeline 调用）。"""
    await run_writer_agent(run_id)
    row = db.get_run(run_id)
    if row and row["status"] == "failed":
        return
    await run_director_agent(run_id)
    row = db.get_run(run_id)
    if row and row["status"] == "failed":
        return
    await run_makeup_agent(run_id)
    row = db.get_run(run_id)
    if row and row["status"] == "failed":
        return
    await run_seedance_merge_agent(run_id)
