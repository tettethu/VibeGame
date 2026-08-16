"""AI Image Generation CLI - discovers providers from artist/providers/."""

from pathlib import Path
import json
import os
from datetime import datetime, timezone
from typing import Optional, List

import typer
from typing import Annotated

from .providers import PROVIDERS
from util.prompt import UnsupportedPromptFileFormat, load_prompt


# === JSONL log ===

def _jsonl_path() -> Path:
    from util.env import get_vibegame_root
    root = get_vibegame_root() or Path.cwd()
    p = root / ".vibegame" / "logs" / "imagegen.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _jsonl_append(entry: dict) -> None:
    with _jsonl_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# === Config ===

def _load_env():
    from util.env import load_unified_env
    load_unified_env()


def _get_config() -> dict:
    raw = os.environ.get("IMAGE_PROVIDER", "Openai")
    provider = _match_provider(raw) or raw
    mod = PROVIDERS.get(provider)
    default_url = getattr(mod, "BASE_URL", "") if mod else ""
    env_url = os.environ.get("IMAGE_BASE_URL", "")
    return {
        "provider": provider,
        "model": os.environ.get("IMAGE_MODEL", ""),
        "api_key": os.environ.get("IMAGE_API_KEY", ""),
        "base_url": env_url.rstrip("/") if env_url else default_url,
    }


def _resolve_model(provider: str, model: str) -> str:
    mod = PROVIDERS.get(provider)
    if not mod:
        return model
    return getattr(mod, "MODEL_MAP", {}).get(model, model)


def _match_provider(name: str) -> str:
    """Case-insensitive provider lookup. Returns canonical name or empty string."""
    if name in PROVIDERS:
        return name
    lower = name.lower()
    for key in PROVIDERS:
        if key.lower() == lower:
            return key
    return ""


def _supported_models(provider: str) -> set:
    mod = PROVIDERS.get(provider)
    return getattr(mod, "SUPPORTED_MODELS", set()) if mod else set()


# === CLI ===

def cmd_list():
    """Show current provider/model config."""
    _load_env()
    cfg = _get_config()
    provider = cfg["provider"]
    model = cfg["model"]
    image_key = cfg["api_key"]

    print("[Image]")
    if image_key:
        print(f"Provider: {provider}")
        print(f"Base URL: {cfg['base_url']}")
        print(f"API Key: {'*' * 8}{image_key[-4:]}")
        print(f"Default Model: {model or '(not set)'}")
        print()
        supported = sorted(_supported_models(provider))
        if supported:
            print(f"Supported models ({provider}):")
            gpt = [m for m in supported if m.startswith("gpt-image")]
            nb = [m for m in supported if m.startswith("nano-banana")]
            other = [m for m in supported if not m.startswith("gpt-image") and not m.startswith("nano-banana")]
            if gpt:
                for m in gpt:
                    marker = " <- default" if m == model else ""
                    print(f"  {m}  (--size + --quality){marker}")
            if nb:
                for m in nb:
                    marker = " <- default" if m == model else ""
                    print(f"  {m}  (--aspect + --resolution){marker}")
            for m in other:
                marker = " <- default" if m == model else ""
                print(f"  {m}{marker}")
        print()
        if model:
            if model.startswith("gpt-image-1"):
                print("Workflow: direct transparent PNG generation")
            else:
                print("Workflow: white background -> GDC pipeline (decompose -> cut -> replace)")
    else:
        print("Not configured (set IMAGE_API_KEY)")

    print()
    print("[Video]")
    from artist.videogen import DEFAULT_VIDEO_BASE_URL
    video_key = os.environ.get("VIDEO_API_KEY", "")
    video_base = os.environ.get("VIDEO_BASE_URL", DEFAULT_VIDEO_BASE_URL)
    if video_key:
        print(f"Base URL: {video_base}")
        print(f"API Key: {'*' * 8}{video_key[-4:]}")
        print("Model: seedance-2.0 (default)")
    else:
        print("Not configured (set VIDEO_API_KEY)")


def cmd_image(
    output: Annotated[Path, typer.Option("-o", "--output")],
    text: Annotated[Optional[str], typer.Option("-t", "--text", help="Prompt text or path to a .txt/.md file")] = None,
    input_images: Annotated[List[str], typer.Option("-i", "--input", help="Reference image path (repeatable). Presence enables i2i.")] = [],
    model: Annotated[str, typer.Option("-m", "--model", help="Model name. See 'vibegame art gen list' for supported models.")] = "",
    size: Annotated[str, typer.Option("--size", help="gpt-image: 1024x1024 | 1024x1536 | 1536x1024 (gpt-image-2: + 2560x1440 | 3840x2160)")] = "",
    quality: Annotated[str, typer.Option("-q", "--quality", help="gpt-image: high | medium | low | auto")] = "auto",
    aspect: Annotated[str, typer.Option("-a", "--aspect", help="nano-banana ratio: 1:1 | 4:3 | 3:4 | 16:9 | 9:16 | 2:3 | 3:2 | 4:5 | 5:4 | 21:9")] = "auto",
    resolution: Annotated[str, typer.Option("-s", "--resolution", help="nano-banana: 1K | 2K | 4K | auto")] = "auto",
):
    """Generate image. t2i by default, i2i when --input is provided."""
    _load_env()
    cfg = _get_config()
    provider = cfg["provider"]
    model = model or cfg["model"]

    if provider not in PROVIDERS:
        print(f"Unknown provider: {provider}. Available: {list(PROVIDERS.keys())}")
        raise typer.Exit(1)
    if model not in _supported_models(provider):
        print(f"{provider} does not support {model}")
        raise typer.Exit(1)

    is_gpt = model.startswith("gpt-image")
    is_nb = model.startswith("nano-banana")
    if is_gpt and size and "x" not in size:
        print(f"--size for {model} expects pixel size (e.g. 1024x1024), got '{size}'")
        raise typer.Exit(1)
    if is_gpt and resolution != "auto":
        print(f"{model} does not support --resolution (gpt uses --size)")
        raise typer.Exit(1)
    if is_nb and resolution and resolution not in ("auto", "1K", "2K", "4K"):
        print(f"Invalid --resolution '{resolution}' for {model}. Valid: 1K, 2K, 4K, auto")
        raise typer.Exit(1)
    if is_nb and size:
        print(f"{model} does not support --size (nb uses --resolution + --aspect)")
        raise typer.Exit(1)

    if not text:
        print("Need -t/--text (prompt text or path to a .txt/.md file)")
        raise typer.Exit(1)
    try:
        prompt = load_prompt(text)
    except UnsupportedPromptFileFormat as e:
        print(f"Error: {e}")
        raise typer.Exit(1)

    mod = PROVIDERS[provider]
    actual_model = _resolve_model(provider, model)
    base, key, out = cfg["base_url"], cfg["api_key"], str(output)
    kwargs = {"size": size, "quality": quality, "aspect_ratio": aspect, "resolution": resolution}

    if input_images:
        for img in input_images:
            if not Path(img).exists():
                print(f"Input not found: {img}")
                raise typer.Exit(1)
        print(f"Calling {actual_model} (i2i)...")
        result = mod.i2i(base, key, prompt, input_images, out, actual_model, **kwargs)
    else:
        print(f"Calling {actual_model}...")
        result = mod.t2i(base, key, prompt, out, actual_model, **kwargs)

    print(f"{result.elapsed:.1f}s")
    if result.ok:
        print(f"Saved: {out}")
    else:
        print(f"Error: {result.error}")

    _jsonl_append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "model": actual_model,
        "prompt": prompt,
        "images": list(input_images),
        "size": size,
        "quality": quality,
        "aspect": aspect,
        "resolution": resolution,
        "output": out,
        "error": None if result.ok else result.error,
    })
    raise typer.Exit(0 if result.ok else 1)
