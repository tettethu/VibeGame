# Image Provider Extension API

How to add a new image generation provider to `vibegame art gen image`.

---

## File Location

Create a `.py` file under `src/artist/providers/`. It will be auto-discovered at import time.

```
src/artist/providers/
  __init__.py       # auto-discovery + shared utils
  openai.py         # existing
  your_provider.py  # add this
```

No other files need modification. The provider appears in `vibegame art gen list` automatically.

---

## Configuration

The image generation CLI reads these values from `.env`:

```sh
IMAGE_PROVIDER=Openai
IMAGE_API_KEY=...
IMAGE_MODEL=gpt-image-2

# Optional override for the selected image provider's endpoint.
IMAGE_BASE_URL=https://api.example.com/v1
```

`IMAGE_BASE_URL` overrides the selected provider module's `BASE_URL`. Omit it to use the provider default.

Only one image provider configuration is active at a time. The setup wizard
updates `IMAGE_PROVIDER`, `IMAGE_API_KEY`, `IMAGE_MODEL`, and the optional
`IMAGE_BASE_URL` as one group. Switching providers does not reuse the previous
provider's key or endpoint.

---

## Required Interface

Every provider module **must** expose these attributes:

```python
PROVIDER_NAME: str              # Unique name, used as IMAGE_PROVIDER env value
BASE_URL: str                   # Default API endpoint
SUPPORTED_MODELS: set[str]      # Canonical model names this provider supports
```

And these two functions:

```python
from . import GenResult

def t2i(base_url, api_key, prompt, output, model, *, size="", aspect_ratio="auto", resolution="auto", quality="auto") -> GenResult:
    """Text-to-image generation. Return GenResult."""
    ...

def i2i(base_url, api_key, prompt, images, output, model, *, size="", aspect_ratio="auto", resolution="auto", quality="auto") -> GenResult:
    """Image-to-image generation. Return GenResult."""
    ...
```

### Parameters

| Param | Type | Description |
|-------|------|-------------|
| `base_url` | str | API base URL (from config or `BASE_URL` default) |
| `api_key` | str | API key (from `IMAGE_API_KEY` env) |
| `prompt` | str | Text prompt |
| `output` | str | Output file path |
| `model` | str | **Already resolved** provider-specific model name. Map via `MODEL_MAP` if names differ. |
| `images` | list[str] | (i2i only) Input image file paths |
| `size` | str | gpt-image pixel size (`1024x1024`, `1536x1024`, etc.). Empty string if not set. Provider may convert to `resolution`+`aspect_ratio`. |
| `aspect_ratio` | str | `"auto"`, `"1:1"`, `"16:9"`, etc. Adapt `"auto"` to what the target API accepts. |
| `resolution` | str | `"1K"`, `"2K"`, `"4K"`, or `"auto"`. Adapt `"auto"` to what the target API accepts. |
| `quality` | str | gpt-image quality: `"high"`, `"medium"`, `"low"`, or `"auto"` |

### Return

A `GenResult` dataclass with fields:

| Field | Type | Description |
|-------|------|-------------|
| `ok` | bool | Whether generation succeeded |
| `error` | str | Error message on failure (empty on success) |
| `elapsed` | float | Request time in seconds |

Return success or failure through `GenResult`. The routing layer (`imagegen.py`) prints the request result and writes the JSONL record. Provider output should be limited to useful input-preparation messages, such as reporting that an oversized reference was resized before upload.

---

## Optional Attributes

```python
MODEL_MAP: dict[str, str]  # Canonical name -> provider-specific name
```

If your provider uses different model names than vibegame's canonical names, define `MODEL_MAP`. The routing layer resolves it before calling your functions.

Example:

```python
MODEL_MAP = {
    "gpt-image-2": "my-provider/gpt-image-2-latest",
    "nano-banana-pro": "gemini-3-pro-image-preview",
}
```

Without `MODEL_MAP`, the canonical model name passes through unchanged.

---

## Shared Utilities

Import from the providers package:

```python
from . import TIMEOUT, GenResult, encode_image, save_image, download_image, resolve_openai_response, expand_paths, _mime
```

| Function | Signature | Description |
|----------|-----------|-------------|
| `GenResult` | `dataclass(ok, error="", elapsed=0.0)` | Structured result for all provider returns |
| `encode_image` | `(path) -> (base64_str, mime_type)` | Read file, return base64 + mime |
| `save_image` | `(b64, output) -> bool` | Save base64 to file. Raises on failure. |
| `download_image` | `(url, output) -> bool` | Download URL to file. Raises on failure. |
| `resolve_openai_response` | `(resp_json, output) -> bool` | Extract image from `data[0].b64_json` or `data[0].url`. Returns False if no image found. |
| `expand_paths` | `(paths, max_count=3) -> list[str]` | Expand dirs to file list, enforce limit |
| `_mime` | `(path) -> str` | Get MIME type from file extension |
| `TIMEOUT` | `600` | Default request timeout in seconds |

If your provider returns OpenAI-format responses (`{"data": [{"b64_json": "..."}]}`), use `resolve_openai_response` to avoid duplicating save logic.

---

## Minimal Template

```python
"""My Provider - image generation via XYZ API."""
import time
import requests
from . import TIMEOUT, GenResult, save_image, resolve_openai_response

PROVIDER_NAME = "MyProvider"
BASE_URL = "https://api.example.com/v1"
SUPPORTED_MODELS = {"gpt-image-2", "nano-banana-pro"}
MODEL_MAP = {
    "gpt-image-2": "provider-gpt-image-2",
    "nano-banana-pro": "provider-nano-banana-pro",
}


def t2i(base_url, api_key, prompt, output, model, *, size="", aspect_ratio="auto", resolution="auto", quality="auto"):
    payload = {"model": model, "prompt": prompt}
    if size:
        payload["size"] = size
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
            return GenResult(False, error="No image in response", elapsed=elapsed)
        return GenResult(True, elapsed=elapsed)
    except Exception as e:
        return GenResult(False, error=str(e), elapsed=time.time() - t0)


def i2i(base_url, api_key, prompt, images, output, model, *, size="", aspect_ratio="auto", resolution="auto", quality="auto"):
    # Implement based on provider's i2i API format
    # Use encode_image() for base64, expand_paths() for file discovery
    ...
```

---

## Checklist

1. Create `src/artist/providers/your_provider.py`
2. Define `PROVIDER_NAME`, `BASE_URL`, `SUPPORTED_MODELS`
3. Optionally define `MODEL_MAP` if model names differ
4. Implement `t2i()` and `i2i()` — return the request result through `GenResult`
5. Adapt `"auto"` values for `aspect_ratio` and `resolution` to the target API
6. Test: `vibegame art gen list` should show your provider and models
