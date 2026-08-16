"""
VLM (Vision Language Model) query tool.

Uses the openai-compatible SDK. Works with any provider that exposes an
OpenAI chat completions endpoint with vision support.

Environment variables (read from .env):
    VLM_BASE_URL    - API endpoint (e.g. https://api.openai.com/v1)
    VLM_API_KEY     - API key
    VLM_MODEL       - default model id (optional)
"""

from openai import OpenAI
import base64
import os
import tempfile
from pathlib import Path
from typing import List, Optional, Annotated

import typer
from PIL import Image

from util.prompt import load_prompt

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

DEFAULT_MODEL = "gemini-3-flash-preview"

BACKGROUND_COLORS: dict[str, tuple[int, int, int]] = {
    "white": (255, 255, 255),
    "black": (0, 0, 0),
    "magenta": (255, 0, 255),
    "green": (0, 255, 0),
    "cyan": (0, 255, 255),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _image_url(path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    return f"data:image/{p.suffix[1:]};base64,{_encode_image(path)}"


def _expand_paths(paths: List[str]) -> List[str]:
    result = []
    for p in paths:
        if p.startswith("http://") or p.startswith("https://"):
            result.append(p)
        elif Path(p).is_dir():
            result.extend(sorted(
                str(f) for f in Path(p).iterdir()
                if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
            ))
        else:
            result.append(p)
    return result


def _parse_background_color(value: str) -> tuple[int, int, int]:
    raw = value.strip()
    name = raw.lower()
    if name in BACKGROUND_COLORS:
        return BACKGROUND_COLORS[name]

    if raw.startswith("#") and len(raw) == 7:
        try:
            return tuple(int(raw[i:i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]
        except ValueError as exc:
            raise ValueError(f"Invalid background color: {value}") from exc

    parts = [p.strip() for p in raw.split(",")]
    if len(parts) == 3:
        try:
            rgb = tuple(int(p) for p in parts)
        except ValueError as exc:
            raise ValueError(f"Invalid background color: {value}") from exc
        if all(0 <= c <= 255 for c in rgb):
            return rgb  # type: ignore[return-value]

    raise ValueError(
        "Invalid --add-background value. Use white, black, magenta, green, cyan, #RRGGBB, or R,G,B."
    )


def _flatten_image_background(path: str, color: tuple[int, int, int], out_dir: Path) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        raise ValueError("--add-background only supports local image paths and folders, not image URLs")

    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    with Image.open(src) as image:
        frame = image.convert("RGBA")
        background = Image.new("RGBA", frame.size, (*color, 255))
        flattened = Image.alpha_composite(background, frame).convert("RGB")
        out_path = out_dir / f"{src.stem}_bg{len(list(out_dir.iterdir()))}.png"
        flattened.save(out_path)
        return str(out_path)


def _prepare_image_paths(paths: List[str], add_background: str | None, tmp_dir: Path | None = None) -> List[str]:
    expanded = _expand_paths(paths) if paths else []
    if not add_background:
        return expanded

    if tmp_dir is None:
        raise ValueError("tmp_dir is required when add_background is set")

    color = _parse_background_color(add_background)
    return [_flatten_image_background(p, color, tmp_dir) for p in expanded]



# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def ask_vlm(
    image_paths: List[str],
    prompt: str,
    system: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: int = 120,
    add_background: str | None = None,
) -> str:
    """Ask a VLM about images using any OpenAI-compatible endpoint.

    Args:
        image_paths: Local paths, URLs, or folder paths (folders are expanded).
        prompt: User question text, or path to a .txt/.md file.
        system: Optional system prompt (role, format, persona). Also supports file path.
        model: Model id. Defaults to VLM_MODEL env var or DEFAULT_MODEL.
        api_key: Defaults to VLM_API_KEY env var.
        base_url: Defaults to VLM_BASE_URL env var.
        timeout: HTTP timeout in seconds.
        add_background: Optional background color for compositing local images
            before sending them to the VLM. Useful for checking transparent assets.
    """
    from util.env import load_unified_env
    load_unified_env()

    prompt = load_prompt(prompt, label="prompt")
    if system:
        system = load_prompt(system, label="system prompt")
    model = model or os.environ.get("VLM_MODEL") or DEFAULT_MODEL
    api_key = api_key or os.environ.get("VLM_API_KEY")
    base_url = base_url or os.environ.get("VLM_BASE_URL")

    if not api_key:
        raise ValueError("VLM_API_KEY not set")
    if not base_url:
        raise ValueError("VLM_BASE_URL not set")

    temp_context = tempfile.TemporaryDirectory() if add_background else None

    from openai.types.chat import (
        ChatCompletionMessageParam,
        ChatCompletionSystemMessageParam,
        ChatCompletionUserMessageParam,
        ChatCompletionContentPartParam,
        ChatCompletionContentPartTextParam,
        ChatCompletionContentPartImageParam,
    )

    content: list[ChatCompletionContentPartParam] = [
        ChatCompletionContentPartTextParam(type="text", text=prompt)
    ]
    try:
        temp_path = Path(temp_context.name) if temp_context else None
        paths = _prepare_image_paths(image_paths, add_background, temp_path)

        for p in paths:
            content.append(ChatCompletionContentPartImageParam(
                type="image_url",
                image_url={"url": _image_url(p)},
            ))

        messages: list[ChatCompletionMessageParam] = []
        if system:
            messages.append(ChatCompletionSystemMessageParam(role="system", content=system))
        messages.append(ChatCompletionUserMessageParam(role="user", content=content))

        client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=4096,
        )
        return response.choices[0].message.content
    finally:
        if temp_context:
            temp_context.cleanup()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_vlm(
    images: Annotated[List[str], typer.Option("-i", "--image", help="Image path, URL, or folder (repeatable)")] = [],
    text: Annotated[str, typer.Option("-t", "--text", help="User prompt text or path to a .txt/.md file")] = "",
    system: Annotated[Optional[str], typer.Option("-s", "--system", help="System prompt: role/format/persona (text or file path)")] = None,
    model: Annotated[Optional[str], typer.Option("-m", "--model", help="Model id (default: VLM_MODEL or gemini-3-flash-preview)")] = None,
    add_background: Annotated[Optional[str], typer.Option("--add-background", help="Composite local images onto a background before sending: white, black, magenta, #RRGGBB, or R,G,B")] = None,
):
    """Ask a VLM (text-only or with images).

    Requires env vars VLM_BASE_URL and VLM_API_KEY (any OpenAI-compatible endpoint).

    Examples:
      vibegame vlm -t "what is the best pixel size for a platformer sprite?"
      vibegame vlm -s "You are a pixel art reviewer. Always reply in Chinese." -i sprite.png -t "critique this"
      vibegame vlm -i frame_0.png -i frame_1.png -t "what changed between frames?"
      vibegame vlm -i frames/ -t "summarize the animation sequence"
      vibegame vlm -i sprite.png --add-background magenta -t "is any white halo visible?"
    """
    if not text:
        print("Error: -t/--text prompt is required")
        raise typer.Exit(1)

    try:
        result = ask_vlm(
            image_paths=list(images),
            prompt=text,
            system=system,
            model=model,
            add_background=add_background,
        )
        print(result)
    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(1)
