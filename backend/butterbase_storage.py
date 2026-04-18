"""Butterbase Storage: POST /storage/{app_id}/upload, GET /storage/{app_id}/download/{object_id} per docs."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx

from .settings import Settings

logger = logging.getLogger(__name__)


def _storage_headers(settings: Settings) -> dict[str, str]:
    key = settings.butterbase_api_key
    if not key:
        raise ValueError("BUTTERBASE_API_KEY is required for Storage upload")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def request_presigned_upload(
    settings: Settings,
    *,
    filename: str,
    content_type: str,
    size_bytes: int,
    public: bool = True,
) -> dict[str, Any]:
    app = settings.butterbase_app_id
    if not app:
        raise ValueError("BUTTERBASE_APP_ID is required for Storage upload")
    base = settings.butterbase_api_url.rstrip("/")
    url = f"{base}/storage/{app}/upload"
    body: dict[str, Any] = {
        "filename": filename,
        "contentType": content_type,
        "sizeBytes": int(size_bytes),
        "public": public,
    }
    with httpx.Client(timeout=60.0) as client:
        r = client.post(url, headers=_storage_headers(settings), json=body)
        if r.status_code >= 400:
            logger.warning("Storage upload URL HTTP %s: %s", r.status_code, r.text[:500])
            r.raise_for_status()
        return r.json()


def request_presigned_download(settings: Settings, *, object_id: str) -> dict[str, Any]:
    app = settings.butterbase_app_id
    if not app:
        raise ValueError("BUTTERBASE_APP_ID is required for Storage download URL")
    base = settings.butterbase_api_url.rstrip("/")
    url = f"{base}/storage/{app}/download/{object_id}"
    with httpx.Client(timeout=60.0) as client:
        r = client.get(url, headers=_storage_headers(settings))
        if r.status_code >= 400:
            logger.warning("Storage download URL HTTP %s: %s", r.status_code, r.text[:500])
            r.raise_for_status()
        return r.json()


def upload_file_and_get_download_url(
    settings: Settings,
    file_path: Path,
    *,
    remote_filename: str,
    content_type: str = "video/mp4",
    public: bool = True,
) -> tuple[str, str]:
    """
    PUT local file to presigned URL, then GET download URL.
    Returns (download_url, object_id).
    """
    path = Path(file_path)
    size_bytes = path.stat().st_size
    presign = request_presigned_upload(
        settings,
        filename=remote_filename,
        content_type=content_type,
        size_bytes=size_bytes,
        public=public,
    )
    upload_url = presign.get("uploadUrl") or presign.get("upload_url")
    object_id = presign.get("objectId") or presign.get("object_id")
    if not upload_url or not object_id:
        raise ValueError(f"Unexpected presign response keys: {list(presign.keys())}")
    with httpx.Client(timeout=300.0) as client:
        data = path.read_bytes()
        put = client.put(
            upload_url,
            content=data,
            headers={"Content-Type": content_type},
        )
        put.raise_for_status()
    dl = request_presigned_download(settings, object_id=str(object_id))
    download_url = dl.get("downloadUrl") or dl.get("download_url")
    if not download_url:
        raise ValueError(f"Unexpected download response keys: {list(dl.keys())}")
    return str(download_url), str(object_id)
