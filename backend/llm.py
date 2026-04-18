import json
import logging
import re
from typing import Any

import httpx

from .settings import Settings

logger = logging.getLogger(__name__)


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if m:
        text = m.group(1).strip()
    try:
        out = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned non-JSON: {e}") from e
    if not isinstance(out, dict):
        raise ValueError("LLM JSON root must be an object")
    return out


async def chat_json(
    settings: Settings,
    *,
    model: str,
    system: str,
    user: str,
    timeout: float = 120.0,
) -> dict[str, Any]:
    base, api_key, json_response = settings.resolve_llm()
    url = f"{base}/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if json_response:
        payload["response_format"] = {"type": "json_object"}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code >= 400:
            logger.warning("LLM HTTP %s: %s", r.status_code, r.text[:500])
            r.raise_for_status()
        data = r.json()
    content = data["choices"][0]["message"]["content"]
    return _extract_json_object(content)


async def generate_image_url(
    settings: Settings,
    *,
    prompt: str,
    timeout: float = 120.0,
) -> str | None:
    """Optional DALL-E style call; returns None if unsupported or misconfigured."""
    # Butterbase 当前仅暴露 chat/completions；仅 Butterbase 密钥时不要打 OpenAI 生图端点
    if settings.uses_butterbase_llm() and not settings.openai_api_key:
        return None
    if not settings.openai_api_key:
        return None
    url = settings.openai_base_url.rstrip("/") + "/images/generations"
    body: dict[str, Any] = {
        "prompt": prompt[:4000],
        "n": 1,
        "size": "1024x1024",
    }
    if settings.image_model:
        body["model"] = settings.image_model
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, headers=headers, json=body)
        if r.status_code >= 400:
            logger.info("Image API skipped: %s %s", r.status_code, r.text[:200])
            return None
        data = r.json()
    arr = data.get("data") or []
    if not arr:
        return None
    item = arr[0]
    return item.get("url") or (item.get("b64_json") and None)
