"""Image generation provider auto-discovery and shared utilities."""

import base64
import glob
import importlib
from dataclasses import dataclass
from pathlib import Path

TIMEOUT = 600


@dataclass
class GenResult:
    ok: bool
    error: str = ""
    elapsed: float = 0.0


def _mime(path: str) -> str:
    suffix = Path(path).suffix.lower().lstrip(".")
    return {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(suffix, "image/png")


def encode_image(path: str) -> tuple[str, str]:
    """Return (base64, mime_type)"""
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return data, _mime(path)


def save_image(b64: str, output: str) -> bool:
    """Save base64 to file, handles data URL prefix and padding. Raises on failure."""
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    if b64.startswith("data:"):
        b64 = b64.split(",", 1)[1]
    pad = len(b64) % 4
    if pad:
        b64 += "=" * (4 - pad)
    Path(output).write_bytes(base64.b64decode(b64))
    return True


def download_image(url: str, output: str) -> bool:
    """Download image from URL to file. Raises on failure."""
    import requests
    r = requests.get(url, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Download failed: {r.status_code}")
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_bytes(r.content)
    return True


def resolve_openai_response(resp_json: dict, output: str) -> bool:
    """Extract image from OpenAI-format response (data[0].b64_json or data[0].url)"""
    try:
        img = resp_json["data"][0]
    except (KeyError, IndexError):
        return False
    if "b64_json" in img:
        return save_image(img["b64_json"], output)
    if "url" in img:
        return download_image(img["url"], output)
    return False


def expand_paths(paths: list[str], max_count: int = 3) -> list[str]:
    """Expand paths, supports directories"""
    result = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
                result.extend(sorted(glob.glob(str(path / ext))))
        elif path.is_file():
            result.append(p)
        else:
            print(f"Warning: path not found: {p}")
    if len(result) > max_count:
        print(f"{len(result)} images, using first {max_count}")
        result = result[:max_count]
    return result


def _discover():
    """Auto-discover provider modules in this directory."""
    registry = {}
    providers_dir = Path(__file__).parent
    for p in sorted(providers_dir.glob("*.py")):
        if p.name.startswith("_"):
            continue
        mod = importlib.import_module(f".{p.stem}", package=__package__)
        name = getattr(mod, "PROVIDER_NAME", p.stem)
        registry[name] = mod
    return registry


PROVIDERS = _discover()
