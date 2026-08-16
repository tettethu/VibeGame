"""
Annotation overlay tool — draw bbox / x-line / y-line on a source image so
the artist can show the result to a VLM and ask "is this framed precisely
on the visible <feature>?".

Decoupled from manifest.json on purpose: this CLI is a dumb visualizer.
The artist iterates values inline (-x / -y / --bbox), asks the VLM,
adjusts, repeats. Once converged, the final numbers are written into
manifest.json's `landmark` block by hand — this tool does not read or
write manifests.

Usage:
    vibegame art label assets/levels/forest-arena.png \\
      -y 840:ground \\
      --bbox "430,630,260,30:left-ledge" \\
      --bbox "1180,600,300,35:right-ledge" \\
      -x 60:left-bound \\
      -x 1860:right-bound \\
      -o /tmp/preview.png

All flags are repeatable. Each entry may carry an optional `:label`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from PIL import Image, ImageDraw, ImageFont


# Visual conventions (kept in sync with rastermap.md docs)
BBOX_COLOR = (255, 32, 32, 255)     # red
MARK_Y_COLOR = (32, 200, 32, 255)   # green
MARK_X_COLOR = (32, 96, 255, 255)   # blue
LINE_WIDTH = 3
LABEL_PAD = 4


def _load_font(size: int) -> ImageFont.ImageFont:
    # Try a handful of common system fonts; fall back to PIL default.
    for name in (
        "DejaVuSans-Bold.ttf",
        "Arial Bold.ttf",
        "Arial.ttf",
        "Helvetica.ttc",
    ):
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _parse_label(raw: str) -> tuple[str, Optional[str]]:
    """Split 'value' or 'value:label' into (value, label_or_None)."""
    if ":" in raw:
        value, label = raw.split(":", 1)
        return value.strip(), label.strip() or None
    return raw.strip(), None


def _parse_int(raw: str, *, flag: str) -> int:
    try:
        return int(raw)
    except ValueError as exc:
        raise typer.BadParameter(f"{flag} expects an integer, got '{raw}'") from exc


def _parse_bbox(raw: str) -> tuple[int, int, int, int]:
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 4:
        raise typer.BadParameter(
            f"--bbox expects 'x,y,w,h' (got '{raw}' with {len(parts)} fields)"
        )
    try:
        return tuple(int(p) for p in parts)  # type: ignore[return-value]
    except ValueError as exc:
        raise typer.BadParameter(f"--bbox values must be integers, got '{raw}'") from exc


def _validate_normalize_output(output: Path) -> None:
    if output.suffix.lower() != ".json":
        raise typer.BadParameter(
            f"--normalize output must use a .json path, got '{output}'"
        )


def _draw_label_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    anchor_xy: tuple[int, int],
    color: tuple[int, int, int, int],
    font: ImageFont.ImageFont,
) -> None:
    x, y = anchor_xy
    bbox = draw.textbbox((x, y), text, font=font)
    pad = LABEL_PAD
    bg_rect = (bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad)
    draw.rectangle(bg_rect, fill=(0, 0, 0, 200))
    draw.text((x, y), text, fill=color, font=font)


def render_label(
    image_path: Path,
    output_path: Path,
    bbox_specs: list[str],
    mark_x_specs: list[str],
    mark_y_specs: list[str],
) -> tuple[int, int]:
    if not image_path.is_file():
        raise typer.BadParameter(f"image not found: {image_path}")

    img = Image.open(image_path).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = img.size

    # Pick font size relative to image height for readability across resolutions.
    font_size = max(14, height // 60)
    font = _load_font(font_size)

    # Draw bboxes
    for raw in bbox_specs:
        value, label = _parse_label(raw)
        x, y, w, h = _parse_bbox(value)
        draw.rectangle(
            (x, y, x + w, y + h),
            outline=BBOX_COLOR,
            width=LINE_WIDTH,
        )
        text = label if label else f"bbox {x},{y},{w}x{h}"
        anchor = (x + LABEL_PAD * 2, y + LABEL_PAD * 2)
        _draw_label_box(draw, text, anchor, BBOX_COLOR, font)

    # Draw vertical (markX) lines
    for raw in mark_x_specs:
        value, label = _parse_label(raw)
        x = _parse_int(value, flag="-x")
        draw.line([(x, 0), (x, height - 1)], fill=MARK_X_COLOR, width=LINE_WIDTH)
        text = f"x={x}" if not label else f"{label} (x={x})"
        anchor = (x + LABEL_PAD * 2, LABEL_PAD * 2)
        _draw_label_box(draw, text, anchor, MARK_X_COLOR, font)

    # Draw horizontal (markY) lines
    for raw in mark_y_specs:
        value, label = _parse_label(raw)
        y = _parse_int(value, flag="-y")
        draw.line([(0, y), (width - 1, y)], fill=MARK_Y_COLOR, width=LINE_WIDTH)
        text = f"y={y}" if not label else f"{label} (y={y})"
        # Right-side anchor; estimate label width to keep it on-canvas.
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        anchor = (max(0, width - text_w - LABEL_PAD * 4), y + LABEL_PAD)
        _draw_label_box(draw, text, anchor, MARK_Y_COLOR, font)

    composed = Image.alpha_composite(img, overlay)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    composed.save(output_path)
    return width, height


def cmd_label(
    image: Annotated[str, typer.Argument(help="Source image (PNG). For --normalize mode, use 'path:x,y,w,h' syntax to specify the frame.")],
    output: Annotated[Path, typer.Option("-o", "--output", help="Output PNG path (or JSON path for agent modes)")],
    bbox: Annotated[
        Optional[list[str]],
        typer.Option("--bbox", help="Red rectangle: 'x,y,w,h' or 'x,y,w,h:label'. Repeatable."),
    ] = None,
    mark_x: Annotated[
        Optional[list[str]],
        typer.Option("-x", help="Blue vertical line at x: 'N' or 'N:label'. Repeatable."),
    ] = None,
    mark_y: Annotated[
        Optional[list[str]],
        typer.Option("-y", help="Green horizontal line at y: 'N' or 'N:label'. Repeatable."),
    ] = None,
    normalize: Annotated[bool, typer.Option("--normalize", help="Use normalize mini-agent: compare target frame to --gt reference, output scale factor.")] = False,
    gt: Annotated[Optional[str], typer.Option("--gt", help="Ground-truth reference for --normalize: 'path:x,y,w,h'.")] = None,
    preview: Annotated[bool, typer.Option("--preview", help="Save preview PNG next to output (agent modes only).")] = False,
    model: Annotated[Optional[str], typer.Option("--model", help="Override agent model.")] = None,
    max_iter: Annotated[Optional[int], typer.Option("--max-iter", help="Max agent iterations (--normalize). Omit to use the agent's own default.")] = None,
):
    """Draw bbox / x-line / y-line annotations on an image for VLM verification.

    Iterate inline (no JSON file). Once values are confirmed by VLM, persist
    them into the asset's `landmark` block in manifest.json by hand — this
    tool does not read or write manifests.

    Examples:
      vibegame art label scene.png -y 840:ground -o /tmp/p.png
      vibegame art label scene.png -y 840:ground -y 600:ceiling -o /tmp/p.png
      vibegame art label scene.png --bbox "430,630,260,30:left-ledge" -o /tmp/p.png
      vibegame art label scene.png \\
        -y 840:ground \\
        --bbox "430,630,260,30:left-ledge" \\
        -x 60:left-bound \\
        -o /tmp/p.png
    """
    def _find_manifest(image_path: Path) -> Optional[Path]:
        """Walk up from image_path's parent looking for manifest.json."""
        for parent in [image_path.parent, *image_path.parent.parents]:
            for name in ("manifest.json", "assets/manifest.json"):
                candidate = parent / name
                if candidate.is_file():
                    return candidate
        return None

    def _lookup_bbox_from_manifest(image_path: Path) -> Optional[list[int]]:
        """Find this image in a nearby manifest.json and return its first-frame bbox."""
        import json as _json
        manifest_path = _find_manifest(image_path)
        if manifest_path is None:
            return None
        try:
            manifest = _json.loads(manifest_path.read_text())
        except Exception:
            return None
        img_abs = image_path.resolve()
        manifest_dir = manifest_path.parent.resolve()
        for _, entry in manifest.items():
            if not isinstance(entry, dict):
                continue
            entry_path = entry.get("path")
            if not entry_path:
                continue
            entry_abs = (manifest_dir / entry_path).resolve()
            if entry_abs != img_abs:
                continue
            if entry.get("type") != "atlas":
                continue
            sprites = entry.get("sprites") or {}
            if not sprites:
                continue
            first = next(iter(sprites.values()))
            bb = first.get("bbox")
            if isinstance(bb, list) and len(bb) == 4:
                return [int(v) for v in bb]
        return None

    def _split_image_bbox(spec: str) -> tuple[str, list[int]]:
        """Parse 'path:x,y,w,h'; if no bbox suffix, auto-load first-frame bbox from a nearby manifest.json."""
        idx = spec.rfind(":")
        if idx >= 0:
            # Heuristic: split if everything after ':' parses as bbox
            tail = spec[idx + 1:]
            if "," in tail:
                try:
                    bb = list(_parse_bbox(tail))
                    return spec[:idx], bb
                except typer.BadParameter:
                    pass
        # No bbox in spec — try manifest lookup
        bb = _lookup_bbox_from_manifest(Path(spec))
        if bb is None:
            raise typer.BadParameter(
                f"No bbox in '{spec}' and no manifest.json entry found. "
                f"Use 'path:x,y,w,h' explicitly."
            )
        return spec, bb

    if normalize:
        from .normalize_agent import run_normalize_agent
        _validate_normalize_output(output)
        if not gt:
            print("--normalize requires --gt 'path:x,y,w,h'")
            raise typer.Exit(1)
        try:
            target_path, target_bbox = _split_image_bbox(image)
            gt_path, gt_bbox = _split_image_bbox(gt)
        except typer.BadParameter as e:
            print(f"Error: {e}")
            raise typer.Exit(1)
        try:
            kwargs = {"model": model, "save_preview": preview}
            if max_iter is not None:
                kwargs["max_iterations"] = max_iter
            result = run_normalize_agent(target_path, target_bbox, gt_path, gt_bbox, str(output), **kwargs)
            print(f"Result: scale={result.scale:.4f} -> {output}")
        except (RuntimeError, ValueError) as e:
            print(f"Agent error: {e}")
            raise typer.Exit(1)
        return

    bbox_specs = list(bbox or [])
    mark_x_specs = list(mark_x or [])
    mark_y_specs = list(mark_y or [])

    if not (bbox_specs or mark_x_specs or mark_y_specs):
        print("No annotations given. Use --bbox / -x / -y at least once.")
        raise typer.Exit(1)

    try:
        w, h = render_label(
            image_path=Path(image),
            output_path=output,
            bbox_specs=bbox_specs,
            mark_x_specs=mark_x_specs,
            mark_y_specs=mark_y_specs,
        )
    except typer.BadParameter as exc:
        print(f"Error: {exc}")
        raise typer.Exit(1)
    except Exception as exc:
        print(f"Error: {exc}")
        raise typer.Exit(1)

    print("=== Label Result ===")
    print(f"Source: {image} ({w}x{h})")
    print(f"Output: {output}")
    print(
        f"Drew: {len(bbox_specs)} bbox / {len(mark_x_specs)} x-line / {len(mark_y_specs)} y-line"
    )
