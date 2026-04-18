"""
Four orchestration steps callable independently (triggered from FastAPI routes).
Suggested order: writer → makeup → director → Seedance merge (visual refs before prompts consumed by merge).
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
from typing import Any, Callable

ProgressCb = Callable[[dict[str, Any]], None] | None

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
    MakeupPlanSceneItem,
    SeedancePromptSegment,
)
from .llm import chat_json
from .settings import get_settings

logger = logging.getLogger(__name__)

LAYER1_SYSTEM = """You are a film storyboard writer. The user provides a personal drama (short story / emotional beat).

Hard requirements (invalid if violated):
1) Aim for **~1 minute** of finished video (speakable density; few, precise shots).
2) Keep the storyboard **small**; each duration_hint_sec must be **at most 15** (decimals allowed).
3) Overall tone: **playful, abstract, lightly satirical or absurd**; visuals must be concrete, shootable, live-action film (not anime).
4) Output **strict JSON** only (no Markdown), keys:
   - storyboard: array of { shot_id, visual, duration_hint_sec, camera_notes? }
   - script: single string (voiceover + dialogue interleaved)
   - characters: array of { name, description, voice_notes? }
   - dialogue: array of { speaker, line, shot_ref? } (shot_ref matches shot_id)

Match the user's input language. Keep implied storyboard duration sum roughly in the 55–75s range."""

MAKEUP_PLAN_SYSTEM = """You are a film makeup / look coordinator and location stills planner. Input is Layer1 JSON (characters and storyboard).
Output **strict JSON** only (no Markdown):
{
  "items": [ { "character_key": "stable English key aligned with character name", "prompt_en": "English makeup still prompt" }, ... ],
  "scene_items": [ { "shot_id": "must match a storyboard shot_id", "prompt_en": "English wide establishing / environment still, photoreal cinematic, no anime" }, ... ]
}

Rules:
1) **items**: **1–6** entries; each prompt_en is a **photorealistic cinematic portrait** still for a character, **no anime / cartoon / 3D doll**.
2) **scene_items**: **1–3** entries for key storyboard beats — **environment / wide location** shots (café, bedroom, street), minimal or no faces; match shot_id from Layer1 storyboard; no text in frame.
3) Simple lighting; consistent look for later I2V.
4) No URLs; JSON only."""

# Director consumes writer JSON only (makeup is another step; no makeup URLs here).
LAYER2_SYSTEM_SOLO = """You are a live-action film director and Seedance prompt engineer.

Inputs:
1) The user's personal drama text;
2) Layer1 JSON (storyboard / script / characters / dialogue).

Output **strict JSON** only (no Markdown):
{
  "director_notes": "optional: tone tags from drama+Layer1 (e.g. humor, romance, twist tension)",
  "seedance_prompts": [ ... ]
}

seedance_prompts: **at least 1, at most 6** (prefer **2–3** for cost/runtime). Each entry must have:
- segment_id: stable English id
- prompt: **English** Seedance video description; **photorealistic cinematic live-action**; **no anime**.
- segment_goal / camera_notes / duration_sec / ratio / resolution / generate_audio / camera_fixed / seed: optional, same meaning as Seedance API.

**Do not** output character_image_urls, image_refs, or image_roles (makeup URLs are produced later; backend aligns I2V with makeup in merge)."""


def _fail(run_id: str, code: str, message: str) -> None:
    db.update_run(
        run_id,
        status="failed",
        error_code=code,
        error_message=message,
    )


def _validate_layer1_timing(layer1: Layer1Output) -> str | None:
    if not layer1.storyboard:
        return "storyboard must not be empty"
    total = sum(float(s.duration_hint_sec) for s in layer1.storyboard)
    if total > 95:
        return (
            f"sum of storyboard duration_hint_sec is {total:.1f}s, above ~1 minute cap; "
            "shorten shots or reduce per-shot duration."
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


def _merge_seedance_job(run_id: str, patch: dict[str, Any]) -> None:
    row = db.get_run(run_id)
    if not row:
        return
    job = dict(row.get("seedance_job") or {})
    job.update(patch)
    db.update_run(run_id, seedance_job=job)


def _segment_image_urls(
    seg: SeedancePromptSegment, all_urls: list[str]
) -> tuple[list[str] | None, None]:
    """Pass URLs only; omit image_roles (LLM-defined roles often trigger Ark InvalidParameter)."""
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
        raise ValueError("layer1_output is required first")
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
        _fail(run_id, "LAYER2_PARSE", "seedance_prompts must not be empty")
        return
    if len(layer2.seedance_prompts) > 6:
        _fail(run_id, "LAYER2_PARSE", "seedance_prompts: at most 6 segments")
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
        raise ValueError("layer1_output is required first")
    if not settings.seedance_api_key or not settings.makeup_image_model:
        _fail(run_id, "MAKEUP_CONFIG", "Configure SEEDANCE_2_0_API and MAKEUP_IMAGE_MODEL.")
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

        scene_urls: list[str] = []
        scene_prompts_used: list[str] = []
        layer1_obj = Layer1Output.model_validate(layer1_dict)
        scene_items: list[MakeupPlanSceneItem] = list(plan.scene_items)
        if not scene_items and layer1_obj.storyboard:
            scene_items = [
                MakeupPlanSceneItem(
                    shot_id=s.shot_id,
                    prompt_en=(
                        "Photoreal cinematic wide establishing shot, natural light, no text in frame: "
                        + (s.visual or "")[:500]
                    ),
                )
                for s in layer1_obj.storyboard[:3]
            ]

        for si in scene_items:
            u = generate_image_url_sync(
                client,
                model=settings.makeup_image_model,
                prompt=si.prompt_en,
            )
            if u:
                scene_urls.append(u)
                scene_prompts_used.append(si.prompt_en)

        return MakeupOutput(
            character_image_urls=urls,
            makeup_prompts=prompts_used,
            scene_image_urls=scene_urls,
            scene_prompts=scene_prompts_used,
            meta={
                "model": settings.makeup_image_model,
                "character_keys": [it.character_key for it in plan.items],
                "scene_shot_ids": [si.shot_id for si in scene_items],
            },
        )

    try:
        makeup = await asyncio.to_thread(_makeup_sync)
    except Exception as e:
        logger.exception("makeup ark")
        _fail(run_id, "MAKEUP_ARK", str(e))
        return
    if not makeup.character_image_urls:
        _fail(run_id, "MAKEUP_ARK", "No makeup image URLs were generated.")
        return
    db.update_run(
        run_id,
        status="makeup_done",
        makeup_output=makeup.model_dump(),
    )


def execute_seedance_physical(run_id: str, on_progress: ProgressCb) -> None:
    """
    Synchronous path: multi-segment generate → download → ffmpeg → Storage.
    on_progress receives JSON-serializable patches per step (merged into seedance_job).
    """
    settings = get_settings()
    row = db.get_run(run_id)
    if not row:
        raise ValueError("run not found")
    if not row.get("layer2_output") or not row.get("makeup_output"):
        raise ValueError("layer2_output and makeup_output are required")
    if not settings.seedance_api_key:
        _merge_seedance_job(
            run_id,
            {"phase": "failed", "error_code": "LAYER3_SEEDANCE", "error_message": "SEEDANCE_2_0_API not configured"},
        )
        _fail(run_id, "LAYER3_SEEDANCE", "SEEDANCE_2_0_API not configured")
        return

    layer2 = Layer2Output.model_validate(row["layer2_output"])
    makeup = MakeupOutput.model_validate(row["makeup_output"])
    char_urls = list(makeup.character_image_urls)
    layer2_dict = dict(row["layer2_output"])
    layer2_dict["character_image_urls"] = char_urls
    model_id = settings.seedance_video_model
    total = len(layer2.seedance_prompts)

    if on_progress is None:
        db.update_run(
            run_id,
            status="layer3_running",
            layer2_output=layer2_dict,
            clear_errors=True,
        )

    def _emit(**patch: Any) -> None:
        if on_progress:
            on_progress(patch)

    tmpdir: Path | None = None
    try:
        _emit(
            phase="generating",
            total_segments=total,
            segment_urls=[],
            current_segment_index=-1,
            model=model_id,
        )

        client = make_ark_client(api_key=settings.seedance_api_key)
        segment_urls: list[str] = []
        tmpdir = Path(tempfile.mkdtemp(prefix="seedance_run_"))
        seg_files: list[Path] = []
        total_dur = 0.0

        for i, seg in enumerate(layer2.seedance_prompts):
            iu, ir = _segment_image_urls(seg, char_urls)
            dur = int(seg.duration_sec or settings.seedance_duration)
            ratio = seg.ratio or settings.seedance_ratio
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
                on_status=lambda s, tid, sid=seg.segment_id: logger.info(
                    "seedance seg %s %s %s", sid, tid, s
                ),
            )
            segment_urls.append(url)
            total_dur += float(dur)
            out_seg = tmpdir / f"seg_{len(seg_files):03d}.mp4"
            download_video(url, str(out_seg), verbose=False)
            seg_files.append(out_seg)
            _emit(
                phase="generating",
                total_segments=total,
                segment_urls=list(segment_urls),
                current_segment_index=i,
                model=model_id,
            )

        _emit(
            phase="merging",
            total_segments=total,
            segment_urls=list(segment_urls),
            current_segment_index=total - 1,
        )

        merged = tmpdir / "merged.mp4"
        ff = settings.ffmpeg_path.strip() or "ffmpeg"
        ff_exe = ff if Path(ff).is_file() else (shutil.which(ff) or shutil.which("ffmpeg"))
        if not ff_exe:
            raise FileNotFoundError(
                "ffmpeg not installed or not on PATH; install ffmpeg or set FFMPEG_PATH."
            )
        _ffmpeg_concat(ff_exe, seg_files, merged)

        _emit(
            phase="uploading",
            total_segments=total,
            segment_urls=list(segment_urls),
            merged_bytes=merged.stat().st_size,
        )

        meta: dict[str, Any] = {
            "segment_urls": segment_urls,
            "merged_bytes": merged.stat().st_size,
            "product_note": settings.product_note,
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
            meta["upload_error"] = "Butterbase not configured; skipping Storage upload."
            video_url = segment_urls[-1]

        layer3 = Layer3Output(
            video_url=video_url,
            model=model_id,
            duration_sec=total_dur,
            meta=meta,
        )
        layer3_dict = layer3.model_dump()
        db.update_run(
            run_id,
            status="done",
            layer3_output=layer3_dict,
            layer2_output=layer2_dict,
        )
        _emit(
            phase="done",
            total_segments=total,
            segment_urls=list(segment_urls),
            video_url=video_url,
            merged_bytes=meta.get("merged_bytes"),
            storage_object_id=meta.get("storage_object_id"),
            upload_skipped=meta.get("upload_skipped"),
            upload_error=meta.get("upload_error"),
        )
    except SeedanceTaskError as e:
        _merge_seedance_job(
            run_id,
            {"phase": "failed", "error_code": "LAYER3_SEEDANCE", "error_message": str(e)},
        )
        _fail(run_id, "LAYER3_SEEDANCE", str(e))
    except FileNotFoundError as e:
        _merge_seedance_job(
            run_id,
            {"phase": "failed", "error_code": "LAYER3_FFMPEG", "error_message": str(e)},
        )
        _fail(run_id, "LAYER3_FFMPEG", str(e))
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or str(e))[:800]
        _merge_seedance_job(
            run_id,
            {"phase": "failed", "error_code": "LAYER3_FFMPEG", "error_message": msg},
        )
        _fail(run_id, "LAYER3_FFMPEG", msg)
    except ValueError as e:
        _merge_seedance_job(
            run_id,
            {"phase": "failed", "error_code": "LAYER3_SEEDANCE", "error_message": str(e)},
        )
        _fail(run_id, "LAYER3_SEEDANCE", str(e))
    except Exception as e:
        logger.exception("layer3")
        _merge_seedance_job(
            run_id,
            {"phase": "failed", "error_code": "LAYER3_SEEDANCE", "error_message": str(e)},
        )
        _fail(run_id, "LAYER3_SEEDANCE", str(e))
    finally:
        if tmpdir is not None:
            shutil.rmtree(tmpdir, ignore_errors=True)


async def run_seedance_merge_agent(run_id: str) -> None:
    """Full pipeline helper: synchronous merge (no sub-status polling)."""
    await asyncio.to_thread(execute_seedance_physical, run_id, None)


def _seedance_progress_cb(run_id: str) -> Callable[[dict[str, Any]], None]:
    def cb(patch: dict[str, Any]) -> None:
        _merge_seedance_job(run_id, patch)

    return cb


async def run_seedance_merge_background(run_id: str) -> None:
    """HTTP 202 background task: writes progress into seedance_job."""
    cb = _seedance_progress_cb(run_id)
    await asyncio.to_thread(execute_seedance_physical, run_id, cb)


async def run_full_pipeline(run_id: str) -> None:
    """Run all four steps in order (legacy one-shot behavior; also used by /pipeline)."""
    await run_writer_agent(run_id)
    row = db.get_run(run_id)
    if row and row["status"] == "failed":
        return
    await run_makeup_agent(run_id)
    row = db.get_run(run_id)
    if row and row["status"] == "failed":
        return
    await run_director_agent(run_id)
    row = db.get_run(run_id)
    if row and row["status"] == "failed":
        return
    await run_seedance_merge_agent(run_id)
