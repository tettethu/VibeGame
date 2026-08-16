"""OpenAI Image API provider.

t2i: POST /images/generations (JSON)
i2i: POST /images/edits (multipart, binary upload)
"""
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import requests
from PIL import Image, ImageOps

from . import TIMEOUT, GenResult, _mime, resolve_openai_response

PROVIDER_NAME = "Openai"
BASE_URL = "https://api.openai.com/v1"
SUPPORTED_MODELS = {"gpt-image-1", "gpt-image-1.5", "gpt-image-2"}
MAX_UPLOAD_EDGE = 2048
MAX_UPLOAD_BYTES = 4 * 1024 * 1024


def _prepare_upload(path: Path, temp_dir: Path) -> Path:
    """Downsample oversized references before multipart upload.

    Image models do not consume an 11k-wide reference at native resolution,
    while sending it through an HTTP proxy/CDN can spend the whole request
    timeout before the API handler is reached. Small inputs remain untouched.
    """
    with Image.open(path) as source:
        width, height = source.size
        if path.stat().st_size <= MAX_UPLOAD_BYTES and max(width, height) <= MAX_UPLOAD_EDGE:
            return path

        image = ImageOps.exif_transpose(source)
        image.thumbnail((MAX_UPLOAD_EDGE, MAX_UPLOAD_EDGE), Image.Resampling.LANCZOS)
        prepared = temp_dir / f"{path.stem}-upload.png"
        image.save(prepared, format="PNG", optimize=True)
        print(
            f"Resized reference for upload: {width}x{height} "
            f"({path.stat().st_size / 1024 / 1024:.1f} MB) -> "
            f"{image.width}x{image.height} ({prepared.stat().st_size / 1024 / 1024:.1f} MB)"
        )
        return prepared


def t2i(base_url, api_key, prompt, output, model, *, size="", aspect_ratio="auto", resolution="auto", quality="auto"):
    payload = {"model": model, "prompt": prompt, "n": 1}
    if size:
        payload["size"] = size
    if quality and quality != "auto":
        payload["quality"] = quality
    t0 = time.time()
    try:
        resp = requests.post(
            f"{base_url}/images/generations",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload, timeout=TIMEOUT,
        )
        elapsed = time.time() - t0
        if resp.status_code != 200:
            return GenResult(False, error=f"{resp.status_code}: {resp.text[:300]}", elapsed=elapsed)
        if not resolve_openai_response(resp.json(), output):
            return GenResult(False, error=f"No image in response:\n{resp.text}", elapsed=elapsed)
        return GenResult(True, elapsed=elapsed)
    except Exception as e:
        return GenResult(False, error=str(e), elapsed=time.time() - t0)


def i2i(base_url, api_key, prompt, images, output, model, *, size="", aspect_ratio="auto", resolution="auto", quality="auto"):
    source_paths = [Path(p) for p in images if Path(p).is_file()]
    if not source_paths:
        return GenResult(False, error="No valid images")
    t0 = time.time()
    with TemporaryDirectory(prefix="vibegame-image-upload-") as temp:
        prepared_paths = [_prepare_upload(path, Path(temp)) for path in source_paths]
        opened = [path.open("rb") for path in prepared_paths]
        try:
            image_field = "image[]" if "api.openai.com" in base_url else "image"
            files = [
                (image_field, (path.name, file, _mime(path)))
                for path, file in zip(prepared_paths, opened)
            ]
            data = {"prompt": prompt, "model": model}
            if size:
                data["size"] = size
            if quality and quality != "auto":
                data["quality"] = quality

            resp = requests.post(
                f"{base_url}/images/edits",
                headers={"Authorization": f"Bearer {api_key}"},
                data=data, files=files, timeout=TIMEOUT,
            )
            elapsed = time.time() - t0
            if resp.status_code != 200:
                return GenResult(False, error=f"{resp.status_code}: {resp.text[:300]}", elapsed=elapsed)
            if not resolve_openai_response(resp.json(), output):
                return GenResult(False, error=f"No image in response:\n{resp.text}", elapsed=elapsed)
            return GenResult(True, elapsed=elapsed)
        except Exception as e:
            return GenResult(False, error=str(e), elapsed=time.time() - t0)
        finally:
            for file in opened:
                file.close()
