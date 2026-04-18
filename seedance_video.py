#!/usr/bin/env python3
"""Generate videos using Seedance 2.0 via BytePlus ModelArk SDK."""

import argparse
import json
import os
import sys
import time

import httpx
from byteplussdkarkruntime import Ark

DEFAULT_ARK_BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3"


class SeedanceTaskError(Exception):
    """Raised when a Seedance content_generation task fails or is cancelled."""

    def __init__(self, message, *, code=None, status=None):
        super().__init__(message)
        self.code = code
        self.status = status


def make_ark_client(
    api_key=None,
    *,
    base_url=None,
):
    """Build an Ark client for Seedance. Reads ``SEEDANCE_2_0_API`` when api_key omitted."""
    key = api_key or os.environ.get("SEEDANCE_2_0_API")
    if not key:
        raise ValueError("SEEDANCE_2_0_API is not set and no api_key was provided.")
    url = base_url or os.environ.get("SEEDANCE_ARK_BASE_URL") or DEFAULT_ARK_BASE_URL
    return Ark(base_url=url, api_key=key)


def _clean_kwargs(**kwargs):
    """Omit None so the API receives only explicitly set optional fields."""
    return {k: v for k, v in kwargs.items() if v is not None}


def _build_content(prompt, image_urls=None, image_roles=None, draft_task_id=None):
    """Build the `content` list for content_generation.tasks.create."""
    content = [{"type": "text", "text": prompt}]
    image_urls = image_urls or []
    image_roles = image_roles or []

    if len(image_roles) == 1 and len(image_urls) > 1:
        image_roles = image_roles * len(image_urls)
    elif image_roles and len(image_roles) != len(image_urls):
        raise ValueError(
            "--image-role count must be 1 (apply to all), or match --image-url count."
        )

    for i, url in enumerate(image_urls):
        item = {"type": "image_url", "image_url": {"url": url}}
        if i < len(image_roles) and image_roles[i]:
            item["role"] = image_roles[i]
        content.append(item)

    if draft_task_id:
        content.append(
            {"type": "draft_task", "draft_task": {"id": draft_task_id}}
        )

    return content


def generate_video(
    client,
    prompt,
    model="dreamina-seedance-2-0-260128",
    ratio="16:9",
    duration=5,
    resolution=None,
    *,
    image_urls=None,
    image_roles=None,
    draft_task_id=None,
    safety_identifier=None,
    callback_url=None,
    return_last_frame=None,
    service_tier=None,
    execution_expires_after=None,
    generate_audio=None,
    draft=None,
    camera_fixed=None,
    watermark=None,
    seed=None,
    frames=None,
    create_timeout=None,
    extra_headers=None,
    extra_query=None,
    extra_body=None,
    poll_interval=10,
    verbose=True,
    on_status=None,
):
    image_urls = image_urls or []
    content = _build_content(
        prompt,
        image_urls=image_urls,
        image_roles=image_roles,
        draft_task_id=draft_task_id,
    )

    if verbose:
        print("Submitting video generation request...")
        print(f"  Prompt:       {prompt}")
        print(f"  Model:        {model}")
        print(f"  Resolution:   {resolution or 'default'}")
        print(f"  Duration:     {duration}s")
        print(f"  Ratio:        {ratio}")
        if image_urls:
            print(f"  Image URLs:   {len(image_urls)}")
        if draft_task_id:
            print(f"  Draft task:   {draft_task_id}")
        if seed is not None:
            print(f"  Seed:         {seed}")
        if frames is not None:
            print(f"  Frames:       {frames}")
        print()

    create_kwargs = _clean_kwargs(
        model=model,
        content=content,
        ratio=ratio,
        duration=duration,
        resolution=resolution,
        safety_identifier=safety_identifier,
        callback_url=callback_url,
        return_last_frame=return_last_frame,
        service_tier=service_tier,
        execution_expires_after=execution_expires_after,
        generate_audio=generate_audio,
        draft=draft,
        camera_fixed=camera_fixed,
        watermark=watermark,
        seed=seed,
        frames=frames,
        extra_headers=extra_headers,
        extra_query=extra_query,
        extra_body=extra_body,
        timeout=create_timeout,
    )

    task = client.content_generation.tasks.create(**create_kwargs)
    task_id = task.id
    if verbose:
        print(f"Task created: {task_id}")

    while True:
        result = client.content_generation.tasks.get(task_id=task_id)
        status = result.status
        if on_status:
            on_status(status, task_id)

        if status == "succeeded":
            video_url = result.content.video_url
            if verbose:
                print(f"\nVideo ready: {video_url}")
            return video_url

        if status == "failed":
            err = result.error
            msg = f"{err.code} - {err.message}" if err else "unknown error"
            if verbose:
                print(f"\nFailed: {msg}", file=sys.stderr)
            raise SeedanceTaskError(msg, code=getattr(err, "code", None), status=status)

        if status == "cancelled":
            msg = "Task was cancelled."
            if verbose:
                print(f"\n{msg}", file=sys.stderr)
            raise SeedanceTaskError(msg, status=status)

        if verbose:
            print(f"  Status: {status}...")
        time.sleep(poll_interval)


def download_video(url, output_path, *, verbose=True):
    if verbose:
        print(f"Downloading to {output_path}...")
    with httpx.stream("GET", url, follow_redirects=True) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(output_path, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total and verbose:
                    pct = downloaded * 100 // total
                    print(f"\r  Progress: {pct}%", end="", flush=True)
    if verbose:
        print(f"\nSaved: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate video with Seedance 2.0 (BytePlus ModelArk)"
    )
    parser.add_argument("prompt", help="Text prompt describing the video")
    parser.add_argument(
        "-o", "--output", default="output.mp4",
        help="Output file path (default: output.mp4)",
    )
    parser.add_argument(
        "-r", "--resolution", default=None,
        choices=["720p", "1080p", "2k"],
        help="Video resolution (default: API default)",
    )
    parser.add_argument(
        "-d", "--duration", type=int, default=5,
        help="Duration in seconds (default: 5)",
    )
    parser.add_argument(
        "-a", "--aspect-ratio", default="16:9",
        choices=["16:9", "9:16", "4:3", "3:4", "1:1"],
        help="Aspect ratio (default: 16:9)",
    )
    parser.add_argument(
        "-m", "--model", default="dreamina-seedance-2-0-260128",
        help="Model ID (default: dreamina-seedance-2-0-260128)",
    )
    parser.add_argument(
        "--no-download", action="store_true",
        help="Only print the video URL, don't download",
    )

    # Multimodal content
    parser.add_argument(
        "--image-url", action="append", dest="image_urls", default=None,
        metavar="URL",
        help="Reference / I2V image URL (repeat for multiple images)",
    )
    parser.add_argument(
        "--image-role", action="append", dest="image_roles", default=None,
        metavar="ROLE",
        help="Role for each image: one value applies to all URLs, "
        "or one per --image-url (model-specific; see API docs)",
    )
    parser.add_argument(
        "--draft-task-id", default=None,
        help="Draft task id for type=draft_task content entry",
    )

    # Task options (content_generation.tasks.create)
    parser.add_argument(
        "--safety-identifier", default=None,
        help="Optional safety_identifier",
    )
    parser.add_argument(
        "--callback-url", default=None,
        help="Webhook URL when the task completes",
    )
    parser.add_argument(
        "--return-last-frame", action=argparse.BooleanOptionalAction,
        default=None,
        help="Request last frame in response when supported",
    )
    parser.add_argument(
        "--service-tier", default=None,
        help="e.g. flex tier for queue pricing (see API docs)",
    )
    parser.add_argument(
        "--execution-expires-after", type=int, default=None,
        help="Execution expiry (seconds; use with service tier as documented)",
    )
    parser.add_argument(
        "--generate-audio", action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable generated audio when supported",
    )
    parser.add_argument(
        "--draft", action=argparse.BooleanOptionalAction,
        default=None,
        help="Draft mode when supported",
    )
    parser.add_argument(
        "--camera-fixed", action=argparse.BooleanOptionalAction,
        default=None,
        help="Fix camera when supported",
    )
    parser.add_argument(
        "--watermark", action=argparse.BooleanOptionalAction,
        default=None,
        help="Watermark toggle when supported",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed",
    )
    parser.add_argument(
        "--frames", type=int, default=None,
        help="Frame count when supported by model",
    )

    # SDK / HTTP
    parser.add_argument(
        "--create-timeout", type=float, default=None,
        help="HTTP timeout (seconds) for the create request",
    )
    parser.add_argument(
        "--extra-headers", default=None,
        metavar="JSON",
        help="JSON object passed as SDK extra_headers on create",
    )
    parser.add_argument(
        "--extra-query", default=None,
        metavar="JSON",
        help="JSON object passed as SDK extra_query on create",
    )
    parser.add_argument(
        "--extra-body", default=None,
        metavar="JSON",
        help='JSON object merged into the create request (SDK extra_body)',
    )
    parser.add_argument(
        "--poll-interval", type=float, default=10.0,
        help="Seconds between status polls (default: 10)",
    )

    args = parser.parse_args()

    def _parse_json_obj(raw, flag_name):
        if not raw:
            return None
        try:
            val = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"Error: invalid {flag_name} JSON: {e}", file=sys.stderr)
            sys.exit(1)
        if not isinstance(val, dict):
            print(f"Error: {flag_name} must be a JSON object.", file=sys.stderr)
            sys.exit(1)
        return val

    extra_headers = _parse_json_obj(args.extra_headers, "--extra-headers")
    extra_query = _parse_json_obj(args.extra_query, "--extra-query")
    extra_body = _parse_json_obj(args.extra_body, "--extra-body")

    try:
        client = make_ark_client()
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        video_url = generate_video(
            client=client,
            prompt=args.prompt,
            model=args.model,
            ratio=args.aspect_ratio,
            duration=args.duration,
            resolution=args.resolution,
            image_urls=args.image_urls,
            image_roles=args.image_roles,
            draft_task_id=args.draft_task_id,
            safety_identifier=args.safety_identifier,
            callback_url=args.callback_url,
            return_last_frame=args.return_last_frame,
            service_tier=args.service_tier,
            execution_expires_after=args.execution_expires_after,
            generate_audio=args.generate_audio,
            draft=args.draft,
            camera_fixed=args.camera_fixed,
            watermark=args.watermark,
            seed=args.seed,
            frames=args.frames,
            create_timeout=args.create_timeout,
            extra_headers=extra_headers,
            extra_query=extra_query,
            extra_body=extra_body,
            poll_interval=args.poll_interval,
        )
    except (SeedanceTaskError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not args.no_download:
        download_video(video_url, args.output)


if __name__ == "__main__":
    main()
