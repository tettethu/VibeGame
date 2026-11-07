"""Google Gemini native API provider.

Uses contents/parts structure with x-goog-api-key auth.
"""
import time

import requests

from . import TIMEOUT, GenResult, encode_image, expand_paths, save_image

PROVIDER_NAME = "Google"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
SUPPORTED_MODELS = {"nano-banana-pro", "nano-banana-2"}
MODEL_MAP = {
    "nano-banana-pro": "gemini-3-pro-image-preview",
    "nano-banana-2": "gemini-3.1-flash-image-preview",
}
OPTION_HELP = {
    "aspect": "1:1 | 4:3 | 3:4 | 16:9 | 9:16 | 2:3 | 3:2 | 4:5 | 5:4 | 21:9 | auto",
    "resolution": "1K | 2K | 4K | auto",
}


def _image_data(response: object) -> str | None:
    """Find the first output image in the first candidate, after any text."""
    if not isinstance(response, dict):
        return None
    candidates = response.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return None
    candidate = candidates[0]
    content = candidate.get("content") if isinstance(candidate, dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        return None
    for part in parts:
        if not isinstance(part, dict) or part.get("thought"):
            continue
        inline = part.get("inlineData")
        if not isinstance(inline, dict):
            continue
        mime = inline.get("mimeType", "image/png")
        data = inline.get("data")
        if (
            isinstance(mime, str) and mime.startswith("image/")
            and isinstance(data, str) and data.strip()
        ):
            return data
    return None


def t2i(base_url, api_key, prompt, output, model, *, size="", aspect_ratio="auto", resolution="auto", quality="auto"):
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": aspect_ratio, "imageSize": resolution.upper() if resolution and resolution != "auto" else "1K"},
        },
    }
    t0 = time.time()
    try:
        resp = requests.post(
            f"{base_url}/models/{model}:generateContent",
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json=payload, timeout=TIMEOUT,
        )
        elapsed = time.time() - t0
        if resp.status_code != 200:
            return GenResult(False, error=f"{resp.status_code}: {resp.text[:300]}", elapsed=elapsed)
        data = _image_data(resp.json())
        if data is None:
            return GenResult(False, error=f"No image in response:\n{resp.text}", elapsed=elapsed)
        save_image(data, output)
        return GenResult(True, elapsed=elapsed)
    except Exception as e:
        return GenResult(False, error=str(e), elapsed=time.time() - t0)


def i2i(base_url, api_key, prompt, images, output, model, *, size="", aspect_ratio="auto", resolution="auto", quality="auto"):
    parts = [
        {"inline_data": {"mime_type": mime, "data": b64}}
        for b64, mime in (encode_image(p) for p in expand_paths(images))
    ]
    parts.append({"text": prompt})
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": aspect_ratio, "imageSize": resolution.upper() if resolution and resolution != "auto" else "1K"},
        },
    }
    t0 = time.time()
    try:
        resp = requests.post(
            f"{base_url}/models/{model}:generateContent",
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json=payload, timeout=TIMEOUT,
        )
        elapsed = time.time() - t0
        if resp.status_code != 200:
            return GenResult(False, error=f"{resp.status_code}: {resp.text[:300]}", elapsed=elapsed)
        data = _image_data(resp.json())
        if data is None:
            return GenResult(False, error=f"No image in response:\n{resp.text}", elapsed=elapsed)
        save_image(data, output)
        return GenResult(True, elapsed=elapsed)
    except Exception as e:
        return GenResult(False, error=str(e), elapsed=time.time() - t0)
