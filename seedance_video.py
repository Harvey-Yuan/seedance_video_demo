#!/usr/bin/env python3
"""Generate videos using Seedance 2.0 via BytePlus ModelArk SDK."""

import argparse
import os
import sys
import time

import httpx
from byteplussdkarkruntime import Ark


def generate_video(client, prompt, model="dreamina-seedance-2-0-260128", ratio="16:9",
                   duration=5, resolution=None):
    print(f"Submitting video generation request...")
    print(f"  Prompt:      {prompt}")
    print(f"  Model:       {model}")
    print(f"  Resolution:  {resolution or 'default'}")
    print(f"  Duration:    {duration}s")
    print(f"  Ratio:       {ratio}")
    print()

    kwargs = dict(
        model=model,
        content=[{"type": "text", "text": prompt}],
        ratio=ratio,
        duration=duration,
    )
    if resolution:
        kwargs["resolution"] = resolution

    task = client.content_generation.tasks.create(**kwargs)
    task_id = task.id
    print(f"Task created: {task_id}")

    # Poll for completion
    while True:
        result = client.content_generation.tasks.get(task_id=task_id)
        status = result.status

        if status == "succeeded":
            video_url = result.content.video_url
            print(f"\nVideo ready: {video_url}")
            return video_url

        if status == "failed":
            err = result.error
            print(f"\nFailed: {err.code} - {err.message}", file=sys.stderr)
            sys.exit(1)

        if status == "cancelled":
            print("\nTask was cancelled.", file=sys.stderr)
            sys.exit(1)

        print(f"  Status: {status}...")
        time.sleep(10)


def download_video(url, output_path):
    print(f"Downloading to {output_path}...")
    with httpx.stream("GET", url, follow_redirects=True) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(output_path, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    print(f"\r  Progress: {pct}%", end="", flush=True)
    print(f"\nSaved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate video with Seedance 2.0")
    parser.add_argument("prompt", help="Text prompt describing the video")
    parser.add_argument("-o", "--output", default="output.mp4",
                        help="Output file path (default: output.mp4)")
    parser.add_argument("-r", "--resolution", default=None,
                        choices=["720p", "1080p", "2k"],
                        help="Video resolution (default: API default)")
    parser.add_argument("-d", "--duration", type=int, default=5,
                        help="Duration in seconds (default: 5)")
    parser.add_argument("-a", "--aspect-ratio", default="16:9",
                        choices=["16:9", "9:16", "4:3", "3:4", "1:1"],
                        help="Aspect ratio (default: 16:9)")
    parser.add_argument("-m", "--model", default="dreamina-seedance-2-0-260128",
                        help="Model ID (default: dreamina-seedance-2-0-260128)")
    parser.add_argument("--no-download", action="store_true",
                        help="Only print the video URL, don't download")

    args = parser.parse_args()

    api_key = os.environ.get("SEEDANCE_2_0_API")
    if not api_key:
        print("Error: SEEDANCE_2_0_API environment variable not set.", file=sys.stderr)
        print("Run: source ~/.zshrc", file=sys.stderr)
        sys.exit(1)

    client = Ark(
        base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
        api_key=api_key,
    )

    video_url = generate_video(
        client=client,
        prompt=args.prompt,
        model=args.model,
        ratio=args.aspect_ratio,
        duration=args.duration,
        resolution=args.resolution,
    )

    if not args.no_download:
        download_video(video_url, args.output)


if __name__ == "__main__":
    main()
