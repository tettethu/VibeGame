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
        try:
            inline = resp.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
        except (KeyError, IndexError, TypeError):
            return GenResult(False, error=f"No image in response:\n{resp.text}", elapsed=elapsed)
        save_image(inline["data"], output)
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
        try:
            inline = resp.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
        except (KeyError, IndexError, TypeError):
            return GenResult(False, error=f"No image in response:\n{resp.text}", elapsed=elapsed)
        save_image(inline["data"], output)
        return GenResult(True, elapsed=elapsed)
    except Exception as e:
        return GenResult(False, error=str(e), elapsed=time.time() - t0)
