"""
Sprite editing tools - convert, flip, resize, rotate, padding.

Usage:
    vibegame art edit image.png -m convert -o output.webp
    vibegame art edit image.png -m hflip -o output.png
    vibegame art edit image.png -m resize -s 0.5 -o output.png
    vibegame art edit image.png -m rotate --angle 90 -o output.png
    vibegame art edit image.png -m padding --aspect 1:1 -o output.png
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, Annotated, Literal, NamedTuple

import typer
from PIL import Image

from .cut import _load_manifest, _save_manifest

app = typer.Typer(
    name="edit",
    help="Sprite editing - convert, flip, resize, rotate, padding",
    add_completion=False,
    rich_markup_mode=None,
    pretty_exceptions_enable=False,
)


# ============ Config ============


class EditConfig:
    RESIZE_SCALE = 1.0
    RESIZE_WIDTH = None
    RESIZE_HEIGHT = None


class SyncReport(NamedTuple):
    manifest_path: Path
    key: str
    frames: int


class EditResult(NamedTuple):
    output_path: Path
    original_size: Tuple[int, int]
    new_size: Tuple[int, int]
    sync: Optional[SyncReport] = None


# ============ Edit Functions ============


_ROTSPRITE_SCALE = 8  # Aseprite-style oversampling factor for --pixel rotation.

_CARDINAL_ROTATE = {
    90: cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
}

EDIT_MODES = ("convert", "hflip", "vflip", "resize", "rotate", "padding")


def _write_image(
    output_path: Path,
    image: np.ndarray,
    quality: Optional[int] = None,
) -> None:
    """Write an image using the encoder selected by its file extension."""
    suffix = output_path.suffix.lower()
    if quality is not None:
        if suffix != ".webp":
            raise ValueError("--quality is only supported for WebP output")
        if not 1 <= quality <= 100:
            raise ValueError("--quality must be between 1 and 100")

    if suffix == ".webp":
        if image.ndim == 2:
            encoded = Image.fromarray(image)
        elif image.shape[2] == 3:
            encoded = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        elif image.shape[2] == 4:
            encoded = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA))
        else:
            raise ValueError(f"Unsupported channel count: {image.shape[2]}")

        options = {"format": "WEBP", "method": 6, "exact": True}
        if quality is None:
            options.update({"lossless": True, "quality": 100})
        else:
            options.update({"lossless": False, "quality": quality})
        encoded.save(output_path, **options)
        return

    if not suffix or not cv2.haveImageWriter(suffix):
        raise ValueError(f"Unsupported output format: {suffix or '(none)'}")
    if not cv2.imwrite(str(output_path), image):
        raise OSError(f"Failed to write image: {output_path}")


def _max_edge_size(width: int, height: int, max_edge: int) -> tuple[int, int]:
    """Fit dimensions within max_edge without upscaling."""
    if max_edge <= 0:
        raise ValueError("--max-edge must be greater than 0")
    if max(width, height) <= max_edge:
        return width, height
    if width >= height:
        return max_edge, max(1, round(height * max_edge / width))
    return max(1, round(width * max_edge / height)), max_edge


def _rotate_smooth(img: np.ndarray, angle: float) -> np.ndarray:
    """Standard image rotation: cardinal angles use cv2.rotate (lossless);
    arbitrary angles use bilinear warpAffine with bbox expansion and transparent border."""
    if angle in _CARDINAL_ROTATE:
        return cv2.rotate(img, _CARDINAL_ROTATE[angle])

    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)

    h, w = img.shape[:2]
    # Negate angle so CW is positive (matches cv2.ROTATE_90_CLOCKWISE convention).
    M = cv2.getRotationMatrix2D((w / 2, h / 2), -angle, 1.0)
    cos = abs(M[0, 0])
    sin = abs(M[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)
    M[0, 2] += new_w / 2 - w / 2
    M[1, 2] += new_h / 2 - h / 2
    return cv2.warpAffine(
        img, M, (new_w, new_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )


def _rotate_pixel(img: np.ndarray, angle: float, scale: int = _ROTSPRITE_SCALE) -> np.ndarray:
    """Simplified RotSprite: NEAREST upscale -> NEAREST rotate (bbox expand) -> NEAREST downscale.

    Output contains no mixed colors; canvas grows to fit rotated bbox; outside area is transparent.
    """
    # Cardinal angles are bit-exact via cv2.rotate; skip the upscale dance
    # (also avoids floating-point shift in getRotationMatrix2D at exact 90/180/270
    # that would otherwise drop the rotated content out of the downscale sample grid).
    if angle in _CARDINAL_ROTATE:
        return cv2.rotate(img, _CARDINAL_ROTATE[angle])

    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)

    h, w = img.shape[:2]
    big_w, big_h = w * scale, h * scale
    big = cv2.resize(img, (big_w, big_h), interpolation=cv2.INTER_NEAREST)

    # Negate angle: OpenCV's getRotationMatrix2D treats CCW as positive, but
    # the non-pixel rotate path uses cv2.ROTATE_90_CLOCKWISE — keep both paths
    # CW-positive so --angle 90 behaves the same with or without --pixel.
    M = cv2.getRotationMatrix2D((big_w / 2, big_h / 2), -angle, 1.0)
    cos = abs(M[0, 0])
    sin = abs(M[0, 1])
    new_big_w = int(big_h * sin + big_w * cos)
    new_big_h = int(big_h * cos + big_w * sin)
    M[0, 2] += new_big_w / 2 - big_w / 2
    M[1, 2] += new_big_h / 2 - big_h / 2

    rotated = cv2.warpAffine(
        big, M, (new_big_w, new_big_h),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )

    out_w = max(1, new_big_w // scale)
    out_h = max(1, new_big_h // scale)
    return cv2.resize(rotated, (out_w, out_h), interpolation=cv2.INTER_NEAREST)


# ============ Manifest bbox sync ============
#
# One pure function per mode, signature (bboxes, old_size, new_size) -> bboxes,
# registered in BBOX_SYNC. Adding a mode means writing a function and one table
# entry. No mode needs extra parameters: every mapping is derivable from the old
# and new image sizes alone.


def _sync_resize(bboxes: dict, old_size: tuple, new_size: tuple) -> dict:
    """Scale by the image's *actual* ratio (new/old), never the requested --scale.
    Rounding makes them differ slightly, and using --scale would drift the bboxes
    away from the pixels they describe."""
    sx = new_size[0] / old_size[0]
    sy = new_size[1] / old_size[1]
    return {
        name: [round(x * sx), round(y * sy), round(w * sx), round(h * sy)]
        for name, (x, y, w, h) in bboxes.items()
    }


def _sync_hflip(bboxes: dict, old_size: tuple, new_size: tuple) -> dict:
    width = new_size[0]
    return {name: [width - x - w, y, w, h] for name, (x, y, w, h) in bboxes.items()}


def _sync_vflip(bboxes: dict, old_size: tuple, new_size: tuple) -> dict:
    height = new_size[1]
    return {name: [x, height - y - h, w, h] for name, (x, y, w, h) in bboxes.items()}


def _sync_padding(bboxes: dict, old_size: tuple, new_size: tuple) -> dict:
    """Padding centers the source on a bigger canvas, so bboxes shift by that offset.
    Mirrors the x_off / y_off computed in the padding branch below."""
    dx = (new_size[0] - old_size[0]) // 2
    dy = (new_size[1] - old_size[1]) // 2
    return {name: [x + dx, y + dy, w, h] for name, (x, y, w, h) in bboxes.items()}


BBOX_SYNC = {
    "resize": _sync_resize,
    "hflip": _sync_hflip,
    "vflip": _sync_vflip,
    "padding": _sync_padding,
}


def _find_atlas_entry(manifest_path: Path, image_path: Path) -> Tuple[dict, str, dict]:
    """Locate the atlas entry whose path resolves to image_path. Exact match only.

    Returns (manifest_data, key, entry).
    """
    if not manifest_path.exists():
        raise ValueError(f"Manifest not found: {manifest_path}")

    data = _load_manifest(manifest_path)
    target = image_path.resolve()
    base = manifest_path.parent
    matches = [
        (key, entry)
        for key, entry in data.items()
        if isinstance(entry, dict)
        and entry.get("path")
        and (base / entry["path"]).resolve() == target
    ]

    if not matches:
        atlases = sorted(
            entry["path"]
            for entry in data.values()
            if isinstance(entry, dict)
            and entry.get("type") == "atlas"
            and entry.get("path")
        )
        listing = "\n  ".join(atlases) if atlases else "(none)"
        raise ValueError(
            f"No entry in {manifest_path} points at {target}\n"
            f"Atlas entries in this manifest:\n  {listing}"
        )
    if len(matches) > 1:
        keys = ", ".join(key for key, _ in matches)
        raise ValueError(
            f"{manifest_path} registers {target} under {len(matches)} keys ({keys}). "
            f"Fix the manifest so each image is registered once."
        )

    key, entry = matches[0]
    entry_type = entry.get("type")
    if entry_type != "atlas":
        raise ValueError(
            f'{manifest_path}: entry "{key}" has type "{entry_type}", not "atlas". '
            f"--sync-bbox only syncs atlas bboxes."
        )
    sprites = entry.get("sprites")
    if not isinstance(sprites, dict) or not sprites:
        raise ValueError(f'{manifest_path}: atlas "{key}" has no sprites to sync')
    return data, key, entry


def _read_bboxes(entry: dict, size: tuple, where: str) -> dict:
    """Extract and validate the entry's bboxes against the source image.

    A bbox already outside the image means the manifest and the image are out of
    sync before we touch anything — syncing on top of that would bake in the error.
    """
    width, height = size
    bboxes = {}
    for name, sprite in entry["sprites"].items():
        if not isinstance(sprite, dict) or "bbox" not in sprite:
            raise ValueError(f'{where} frame "{name}" has no bbox')
        bbox = sprite["bbox"]
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError(f'{where} frame "{name}" bbox must be [x, y, w, h], got {bbox!r}')
        if not all(isinstance(v, int) for v in bbox):
            raise ValueError(f'{where} frame "{name}" bbox must be integers, got {bbox!r}')
        x, y, w, h = bbox
        if w < 1 or h < 1:
            raise ValueError(f'{where} frame "{name}" bbox {bbox} has non-positive size')
        if x < 0 or y < 0 or x + w > width or y + h > height:
            raise ValueError(
                f'{where} frame "{name}" bbox {bbox} falls outside the source image '
                f"{width}x{height}. The manifest is already inconsistent with the "
                f"image; fix it before syncing."
            )
        bboxes[name] = bbox
    return bboxes


def _fit_bboxes(bboxes: dict, size: tuple, mode: str) -> dict:
    """Absorb 1px rounding drift; anything larger means the mode's mapping is wrong.

    Bound: with the source bbox inside the image, x+w drifts at most +1.0 from the
    true value and the image width at most -0.5, so overflow is <= 1px. A larger
    overflow cannot come from rounding.
    """
    width, height = size
    fitted = {}
    for name, (x, y, w, h) in bboxes.items():
        if w < 1 or h < 1:
            raise ValueError(
                f'frame "{name}" collapses to {w}x{h} at the new size; '
                f"the transform is too small to keep this frame"
            )
        over_x = x + w - width
        over_y = y + h - height
        if x < 0 or y < 0 or over_x > 1 or over_y > 1:
            raise RuntimeError(
                f'internal error: "{mode}" mapped frame "{name}" to {[x, y, w, h]}, '
                f"which does not fit image {width}x{height}. The bbox mapping for "
                f"this mode is wrong."
            )
        fitted[name] = [x, y, w - max(over_x, 0), h - max(over_y, 0)]
    return fitted


def edit_image(
    mode: Literal["convert", "hflip", "vflip", "resize", "rotate", "padding"],
    image_path: str,
    save_path: Optional[str] = None,
    inplace: bool = False,
    sync_bbox: Optional[str] = None,
    **kwargs,
) -> EditResult:
    """Convert or edit an image.

    Args:
        mode: convert | hflip | vflip | resize | rotate | padding
        image_path: input image
        save_path: output path (exclusive with inplace)
        inplace: overwrite original
        sync_bbox: manifest.json whose atlas bboxes follow this edit (requires inplace)
        **kwargs:
            resize: scale, width, height, max_edge
            rotate: angle (90/180/270)
            padding: aspect ("W:H"), background ("transparent"/"white")
            output: quality (WebP only)

    Returns:
        EditResult(output_path, original_size(w,h), new_size(w,h), sync)
    """
    if save_path is None and not inplace:
        raise ValueError("Must specify save_path or inplace=True")
    if save_path is not None and inplace:
        raise ValueError("Cannot specify both save_path and inplace=True")
    if mode != "resize" and kwargs.get("max_edge") is not None:
        raise ValueError("--max-edge requires resize mode")

    if sync_bbox is not None:
        if not inplace:
            raise ValueError(
                "--sync-bbox requires --inplace: the manifest entry points at the "
                "source image, so writing the edit elsewhere would leave the "
                "manifest describing a file it does not reference"
            )
        if mode not in BBOX_SYNC:
            supported = ", ".join(sorted(BBOX_SYNC))
            raise ValueError(
                f"--sync-bbox does not support mode '{mode}' (supported: {supported}). "
                f"Re-run `vibegame art cut` to regenerate bboxes after this edit."
            )

    frame_count = cv2.imcount(image_path)
    if frame_count > 1:
        raise ValueError(
            f"Animated or multi-page images are not supported: {frame_count} frames"
        )

    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Cannot read image: {image_path}")

    original_h, original_w = img.shape[:2]
    original_size = (original_w, original_h)

    manifest_data = manifest_key = source_bboxes = None
    if sync_bbox is not None:
        manifest_path = Path(sync_bbox)
        manifest_data, manifest_key, entry = _find_atlas_entry(
            manifest_path, Path(image_path)
        )
        source_bboxes = _read_bboxes(
            entry, original_size, f'{manifest_path}: atlas "{manifest_key}"'
        )

    if mode == "convert":
        result = img.copy()

    elif mode == "hflip":
        result = cv2.flip(img, 1)

    elif mode == "vflip":
        result = cv2.flip(img, 0)

    elif mode == "resize":
        width = kwargs.get("width")
        height = kwargs.get("height")
        scale = kwargs.get("scale", EditConfig.RESIZE_SCALE)
        max_edge = kwargs.get("max_edge")

        if max_edge is not None:
            if width is not None or height is not None or scale != EditConfig.RESIZE_SCALE:
                raise ValueError(
                    "--max-edge cannot be combined with --width, --height, or --scale"
                )
            new_w, new_h = _max_edge_size(original_w, original_h, max_edge)
        elif width is not None or height is not None:
            if width is not None and height is not None:
                new_w, new_h = width, height
            elif width is not None:
                ratio = width / original_w
                new_w = width
                new_h = round(original_h * ratio)
            else:
                ratio = height / original_h
                new_h = height
                new_w = round(original_w * ratio)
        else:
            new_w = round(original_w * scale)
            new_h = round(original_h * scale)

        if new_w <= 0 or new_h <= 0:
            raise ValueError(f"Invalid target size: {new_w}x{new_h}")

        if (new_w, new_h) == original_size:
            result = img.copy()
        else:
            result = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    elif mode == "rotate":
        angle = kwargs.get("angle", 90)
        pixel = kwargs.get("pixel", False)
        if pixel:
            result = _rotate_pixel(img, float(angle))
        else:
            result = _rotate_smooth(img, float(angle))

    elif mode == "padding":
        aspect = kwargs.get("aspect")
        bg = kwargs.get("background", "transparent")
        if aspect is None:
            raise ValueError("padding mode requires aspect parameter, e.g. '1:1'")

        parts = aspect.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid aspect format: {aspect}, expected 'W:H' e.g. '1:1'")
        aspect_w, aspect_h = int(parts[0]), int(parts[1])

        target_ratio = aspect_w / aspect_h
        current_ratio = original_w / original_h

        if current_ratio > target_ratio:
            new_w = original_w
            new_h = int(original_w / target_ratio)
        elif current_ratio < target_ratio:
            new_h = original_h
            new_w = int(original_h * target_ratio)
        else:
            new_w, new_h = original_w, original_h

        channels = img.shape[2] if len(img.shape) == 3 else 1
        if bg == "white":
            if channels == 4:
                canvas = np.full((new_h, new_w, 4), [255, 255, 255, 255], dtype=np.uint8)
            else:
                canvas = np.full((new_h, new_w, channels), 255, dtype=np.uint8)
        else:
            if channels < 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA) if channels == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
                channels = 4
            canvas = np.zeros((new_h, new_w, 4), dtype=np.uint8)

        x_off = (new_w - original_w) // 2
        y_off = (new_h - original_h) // 2
        canvas[y_off:y_off + original_h, x_off:x_off + original_w] = img
        result = canvas

    else:
        raise ValueError(f"Unsupported mode: {mode}")

    new_h, new_w = result.shape[:2]
    new_size = (new_w, new_h)

    if inplace:
        output_path = Path(image_path)
    else:
        output_path = Path(save_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Compute and validate bboxes before anything is written, so a rejected sync
    # leaves both the image and the manifest untouched.
    sync = None
    if sync_bbox is not None:
        synced = _fit_bboxes(
            BBOX_SYNC[mode](source_bboxes, original_size, new_size), new_size, mode
        )
        for name, bbox in synced.items():
            manifest_data[manifest_key]["sprites"][name]["bbox"] = bbox
        sync = SyncReport(Path(sync_bbox), manifest_key, len(synced))

    _write_image(output_path, result, quality=kwargs.get("quality"))
    if sync is not None:
        _save_manifest(sync.manifest_path, manifest_data)
    return EditResult(output_path, original_size, new_size, sync)


# ============ CLI Commands ============


@app.command("edit")
def cmd_edit(
    image: Annotated[str, typer.Argument(help="Input image path")],
    mode: Annotated[
        str,
        typer.Option(
            "-m",
            "--mode",
            help="Mode: convert/hflip/vflip/resize/rotate/padding",
        ),
    ],
    output: Annotated[Optional[str], typer.Option("-o", "--output", help="Output file path")] = None,
    inplace: Annotated[bool, typer.Option("--inplace", help="Overwrite original")] = False,
    scale: Annotated[float, typer.Option("-s", "--scale", help="resize: scale factor")] = EditConfig.RESIZE_SCALE,
    width: Annotated[Optional[int], typer.Option("-w", "--width", help="resize: target width")] = None,
    height: Annotated[Optional[int], typer.Option("-h", "--height", help="resize: target height")] = None,
    max_edge: Annotated[
        Optional[int],
        typer.Option("--max-edge", help="resize: maximum width or height, never upscale"),
    ] = None,
    angle: Annotated[float, typer.Option("--angle", help="rotate: angle in degrees, clockwise. Any float; cardinal angles (90/180/270) are lossless, others use bilinear (or NEAREST with --pixel)")] = 90.0,
    pixel: Annotated[bool, typer.Option("--pixel", help="rotate: simplified RotSprite for pixel art (NEAREST throughout, no mixed colors)")] = False,
    aspect: Annotated[Optional[str], typer.Option("--aspect", help="padding: aspect ratio W:H e.g. 1:1")] = None,
    background: Annotated[str, typer.Option("--background", "--bg", help="padding: background transparent/white")] = "transparent",
    quality: Annotated[
        Optional[int],
        typer.Option(
            "--quality",
            help="WebP lossy quality from 1 to 100; omit for lossless WebP",
        ),
    ] = None,
    sync_bbox: Annotated[
        Optional[str],
        typer.Option(
            "--sync-bbox",
            help=(
                "manifest.json whose atlas bboxes follow this edit. Requires "
                "--inplace. Modes: resize/hflip/vflip/padding"
            ),
        ),
    ] = None,
):
    """Convert, flip, resize, rotate, or pad an image.

    Examples:
      vibegame art edit input.png -m convert -o output.webp
      vibegame art edit input.png -m convert -o output.webp --quality 82
      vibegame art edit input.png -m hflip -o output.png
      vibegame art edit input.png -m vflip --inplace
      vibegame art edit input.png -m resize -s 0.5 -o output.png
      vibegame art edit input.png -m resize -w 200 -o output.png
      vibegame art edit input.png -m resize --max-edge 1280 -o output.webp
      vibegame art edit input.png -m rotate --angle 90 -o output.png
      vibegame art edit input.png -m rotate --angle 45 --pixel -o output.png
      vibegame art edit input.png -m padding --aspect 1:1 -o output.png
      vibegame art edit sheet.png -m resize -s 0.85 --inplace --sync-bbox assets/manifest.json
    """
    if mode not in EDIT_MODES:
        print(f"Unsupported mode: {mode}")
        print(f"Supported: {', '.join(EDIT_MODES)}")
        raise typer.Exit(1)

    if output is None and not inplace:
        print("Need -o/--output or --inplace")
        raise typer.Exit(1)

    if output is not None and inplace:
        print("Cannot specify both -o/--output and --inplace")
        raise typer.Exit(1)

    try:
        input_bytes = Path(image).stat().st_size
        print(f"Applying {mode}...")
        output_file, original_size, new_size, sync = edit_image(
            mode=mode,
            image_path=image,
            save_path=output,
            inplace=inplace,
            sync_bbox=sync_bbox,
            scale=scale,
            width=width,
            height=height,
            max_edge=max_edge,
            angle=angle,
            pixel=pixel,
            aspect=aspect,
            background=background,
            quality=quality,
        )
        output_bytes = output_file.stat().st_size
        delta_bytes = output_bytes - input_bytes
        delta_percent = (
            delta_bytes / input_bytes * 100 if input_bytes else 0.0
        )

        print("=== Edit Result ===")
        print("Done!")
        print(f"Output: {output_file}")
        print(f"Mode: {mode}")
        print(
            f"Original: {original_size[0]}x{original_size[1]}, "
            f"{input_bytes} bytes"
        )
        print(f"New: {new_size[0]}x{new_size[1]}, {output_bytes} bytes")
        print(f"Size change: {delta_bytes:+d} bytes ({delta_percent:+.1f}%)")
        if sync is not None:
            print(
                f'Synced: {sync.frames} bbox(es) of atlas "{sync.key}" '
                f"in {sync.manifest_path}"
            )

    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(1)
