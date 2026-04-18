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

LAYER2_SYSTEM = """你是真人电影导演 + Seedance 视频提示词工程师（不是画师，不负责出图 URL）。

输入包含：
1) 用户的 personal drama 原文；
2) Layer1 的 JSON（分镜/脚本/角色/对白）；
3) makeup_output：定妆参考图 URL 列表（character_image_urls，按数组下标引用）。

请输出 **严格 JSON**（不要 Markdown）:
{
  "director_notes": "可选：从 drama+Layer1 归纳整体气质（如幽默/浪漫/反转张力等多标签），用简短中文或中英混合",
  "seedance_prompts": [ ... ]
}

seedance_prompts：**至少 1 条、至多 6 条**多段短片计划，与 Layer1 时间预算大致对齐。每条必须含:
- segment_id: 稳定英文 id
- prompt: **英文** Seedance 视频描述；强调 **photorealistic cinematic live-action**；**禁止 anime**。
- segment_goal: 可选，英文或中文短语，概括该段情绪/冲突推进（**不要硬编码具体台词**，可用「情绪节拍」替代）。
- camera_notes: 可选，镜头/调度备注（英文为佳）。
- image_refs: 可选，整数数组，引用 makeup_output.character_image_urls 的下标（本段 I2V 用哪些定妆图）。
- image_roles: 可选，与 image 数量一致或 1 条作用于全部（模型支持时使用）。
- duration_sec: 可选整数 1～60（每段时长，需合理）。
- ratio: 可选，如 "16:9" / "9:16"。
- resolution: 可选，如 "720p" / "1080p" / "2k"。
- generate_audio / camera_fixed: 可选布尔。
- seed: 可选整数。

**不要**在 prompt 里写死对白文本；不要输出 character_image_urls（定妆已单独提供）。"""


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
) -> tuple[list[str] | None, list[str] | None]:
    refs = seg.image_refs
    if not refs or not all_urls:
        return None, None
    urls: list[str] = []
    for i in refs:
        if isinstance(i, int) and 0 <= i < len(all_urls):
            urls.append(all_urls[i])
    if not urls:
        return None, None
    roles = seg.image_roles
    if roles and len(roles) == 1 and len(urls) > 1:
        roles = roles * len(urls)
    if roles and len(roles) != len(urls):
        roles = None
    return urls, roles


async def run_pipeline(run_id: str) -> None:
    settings = get_settings()
    row = db.get_run(run_id)
    if not row:
        logger.error("run not found: %s", run_id)
        return
    drama = row["drama_input"]
    stage = "init"

    try:
        # --- 编剧 Layer1 ---
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
        err1 = _validate_layer1_timing(layer1)
        if err1:
            _fail(run_id, "LAYER1_PARSE", err1)
            return
        layer1_dict = layer1.model_dump()
        db.update_run(
            run_id,
            status="layer1_done",
            layer1_output=layer1_dict,
        )

        # --- 定妆 Makeup ---
        stage = "makeup"
        db.update_run(run_id, status="makeup_running")
        if not settings.seedance_api_key:
            _fail(
                run_id,
                "MAKEUP_CONFIG",
                "请配置 SEEDANCE_2_0_API（与 ModelArk 图像/视频共用密钥）。可选覆盖 MAKEUP_IMAGE_MODEL（默认 seedream-4-0-250828）。",
            )
            return
        if not settings.makeup_image_model:
            _fail(
                run_id,
                "MAKEUP_CONFIG",
                "MAKEUP_IMAGE_MODEL 为空；请设为控制台可用的图模 id（默认 seedream-4-0-250828，见 BytePlus Seedream 4.0 文档）。",
            )
            return

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
        except ValueError as e:
            _fail(run_id, "MAKEUP_ARK", str(e))
            return
        except Exception as e:
            logger.exception("makeup ark")
            _fail(run_id, "MAKEUP_ARK", str(e))
            return

        if not makeup.character_image_urls:
            _fail(run_id, "MAKEUP_ARK", "未能生成任何定妆图 URL，请检查模型 id 与密钥权限。")
            return

        makeup_dict = makeup.model_dump()
        db.update_run(
            run_id,
            status="makeup_done",
            makeup_output=makeup_dict,
        )

        # --- 导演 Layer2 ---
        stage = "layer2"
        db.update_run(run_id, status="layer2_running")
        director_user = json.dumps(
            {
                "drama": drama,
                "layer1": layer1_dict,
                "makeup_output": makeup_dict,
            },
            ensure_ascii=False,
            indent=2,
        )
        raw2 = await chat_json(
            settings,
            model=settings.layer2_model,
            system=LAYER2_SYSTEM,
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
        layer2_dict["character_image_urls"] = list(makeup.character_image_urls)
        db.update_run(
            run_id,
            status="layer2_done",
            layer2_output=layer2_dict,
        )

        # --- 成片 Layer3：多段 Seedance + ffmpeg + Storage ---
        stage = "layer3"
        db.update_run(run_id, status="layer3_running")
        model_id = settings.seedance_video_model
        char_urls = list(makeup.character_image_urls)
        default_res = settings.seedance_resolution or None
        if default_res == "":
            default_res = None

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
                    res = seg.resolution if seg.resolution else default_res
                    if res == "":
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
                    meta["upload_error"] = "未配置 Butterbase，跳过 Storage 上传；video_url 暂用末段 Seedance URL。"
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
            _fail(
                run_id,
                "LAYER3_FFMPEG",
                (e.stderr or str(e))[:800],
            )
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
    except asyncio.CancelledError:
        raise
    except ValidationError as e:
        if stage == "layer1":
            code = "LAYER1_PARSE"
        elif stage == "makeup":
            code = "MAKEUP_PARSE"
        else:
            code = "LAYER2_PARSE"
        _fail(run_id, code, str(e))
    except ValueError as e:
        if stage == "layer1":
            _fail(run_id, "LAYER1_PARSE", str(e))
        elif stage == "makeup":
            _fail(run_id, "MAKEUP_LLM", str(e))
        elif stage == "layer2":
            _fail(run_id, "LAYER2_PARSE", str(e))
        else:
            _fail(run_id, "INTERNAL", str(e))
    except Exception as e:
        logger.exception("pipeline failed")
        if stage == "layer1":
            code = "LAYER1_LLM"
        elif stage == "makeup":
            code = "MAKEUP_LLM"
        elif stage == "layer2":
            code = "LAYER2_LLM"
        elif stage == "layer3":
            code = "LAYER3_SEEDANCE"
        else:
            code = "INTERNAL"
        _fail(run_id, code, str(e))
