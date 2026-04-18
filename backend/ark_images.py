"""ModelArk synchronous image generation (定妆), separate from Seedance video tasks."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def generate_image_url_sync(
    client: Any,
    *,
    model: str,
    prompt: str,
    size: str | None = None,
    timeout: float = 120.0,
) -> str | None:
    """Call Ark ``images.generate``; return first image HTTPS URL or None."""
    try:
        resp = client.images.generate(
            model=model,
            prompt=prompt,
            sequential_image_generation="disabled",
            size=size,
            timeout=timeout,
        )
    except Exception as e:
        logger.warning("Ark images.generate failed: %s", e)
        return None
    items = getattr(resp, "data", None) or []
    if not items:
        err = getattr(resp, "error", None)
        if err is not None:
            msg = getattr(err, "message", None) or str(err)
            logger.warning("Ark images response error: %s", msg)
        return None
    first = items[0]
    url = getattr(first, "url", None) or (
        isinstance(first, dict) and first.get("url")
    )
    if url:
        return str(url)
    return None
