"""
Post-processing tool for individual sprites and tiles after background removal.

Usage:
    vibegame art perfectify <image> --mode tile -o <output>
    vibegame art perfectify <image> --mode tile --size 32x32 -o <output>
    vibegame art perfectify <image> --mode sprite --edge inward -o <output>
    vibegame art perfectify sprites_dir/ --mode sprite -o clean_dir/
    vibegame art perfectify <image> --mode tile --where
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, List, Annotated, Tuple, Literal
from scipy.spatial import cKDTree

import typer

app = typer.Typer(name="perfectify", help="Post-process sprites and tiles", add_completion=False, rich_markup_mode=None, pretty_exceptions_enable=False)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


# ============ Tile Mode ============


def perfectify_tile(
    img: np.ndarray,
    target_size: Optional[Tuple[int, int]] = None,
    edge_margin: int = 3,
) -> np.ndarray:
    """Force image into a clean rectangle, filling from deep interior outward.

    Strategy: pixels near transparent areas are "untrusted" (likely white remnants).
    Only deep interior pixels are trusted. Colors propagate outward from interior,
    overwriting both holes and untrusted edge pixels.

    Args:
        img: BGRA image
        target_size: (width, height) to force output to, or None for bbox-fit
        edge_margin: pixels within this distance of transparent are untrusted
    """
    h, w = img.shape[:2]
    alpha = img[:, :, 3]

    opaque = alpha > 0
    if not np.any(opaque):
        return img

    # Find content bounding box
    rows = np.any(opaque, axis=1)
    cols = np.any(opaque, axis=0)
    y0, y1 = np.where(rows)[0][[0, -1]]
    x0, x1 = np.where(cols)[0][[0, -1]]

    # Crop to bbox
    cropped = img[y0:y1 + 1, x0:x1 + 1].copy()

    # Fill from interior outward
    cropped = _fill_from_interior(cropped, edge_margin)

    # Note: alpha forcing is deferred to after all passes in _process_single

    if target_size is not None:
        tw, th = target_size
        cropped = cv2.resize(cropped, (tw, th), interpolation=cv2.INTER_AREA)

    return cropped


def _fill_from_interior(img: np.ndarray, edge_margin: int) -> np.ndarray:
    """Propagate colors outward from deep interior, overwriting holes and edge pixels.

    1. Distance transform: for each opaque pixel, compute distance to nearest transparent
    2. Trusted interior = opaque pixels with distance > edge_margin
    3. Iteratively expand from trusted region, filling neighbors with weighted average
    """
    result = img.copy()
    h, w = img.shape[:2]
    opaque = img[:, :, 3] > 0

    # Distance from each opaque pixel to nearest transparent pixel
    opaque_u8 = opaque.astype(np.uint8) * 255
    dist_to_edge = cv2.distanceTransform(opaque_u8, cv2.DIST_L2, 5)

    # Trusted: opaque pixels far enough from any transparent area
    trusted = opaque & (dist_to_edge > edge_margin)

    if not np.any(trusted):
        # Fallback: if no deep interior exists, trust all opaque pixels
        trusted = opaque.copy()

    # Everything not trusted needs to be (re)filled
    filled = trusted.copy()
    remaining = ~trusted
    kernel = np.ones((3, 3), np.uint8)
    k_avg = np.ones((3, 3), np.float64)

    max_iters = max(h, w)
    for _ in range(max_iters):
        if not np.any(remaining):
            break

        # Expand filled region by 1px
        filled_u8 = filled.astype(np.uint8) * 255
        dilated = cv2.dilate(filled_u8, kernel, iterations=1)
        border = remaining & (dilated > 0)

        if not np.any(border):
            break

        # Weighted average: only use filled neighbors
        weight = filled.astype(np.float64)
        sum_weight = cv2.filter2D(weight, -1, k_avg)

        for c in range(3):
            weighted_color = result[:, :, c].astype(np.float64) * weight
            sum_color = cv2.filter2D(weighted_color, -1, k_avg)
            valid = border & (sum_weight > 0)
            if np.any(valid):
                avg = sum_color / np.maximum(sum_weight, 1e-10)
                result[:, :, c] = np.where(valid, avg.astype(np.uint8), result[:, :, c])

        result[border, 3] = 255
        remaining[border] = False
        filled[border] = True

    return result


def _tile_where_preview(img: np.ndarray, edge_margin: int = 3) -> np.ndarray:
    """Generate tile preview showing what would be filled/overwritten.

    Blue = transparent holes to fill
    Yellow = untrusted edge pixels to overwrite (near-transparent, likely white remnants)
    Green = bbox border
    """
    h, w = img.shape[:2]
    alpha = img[:, :, 3]

    opaque = alpha > 0
    if not np.any(opaque):
        return img[:, :, :3].copy()

    rows = np.any(opaque, axis=1)
    cols = np.any(opaque, axis=0)
    y0, y1 = np.where(rows)[0][[0, -1]]
    x0, x1 = np.where(cols)[0][[0, -1]]

    # Distance to transparent
    opaque_u8 = opaque.astype(np.uint8) * 255
    dist_to_edge = cv2.distanceTransform(opaque_u8, cv2.DIST_L2, 5)
    untrusted = opaque & (dist_to_edge <= edge_margin)

    # Composite on white bg
    bgr = img[:, :, :3].copy()
    a = img[:, :, 3:4] / 255.0
    white = np.full((h, w, 3), 255, dtype=np.uint8)
    preview = (bgr * a + white * (1 - a)).astype(np.uint8)

    # Blue overlay on transparent holes inside bbox
    holes_in_bbox = np.zeros((h, w), dtype=bool)
    holes_in_bbox[y0:y1+1, x0:x1+1] = (alpha[y0:y1+1, x0:x1+1] == 0)
    blue = np.array([255, 100, 0], dtype=np.uint8)
    mask3 = np.stack([holes_in_bbox] * 3, axis=2)
    preview = np.where(mask3, (0.5 * preview + 0.5 * blue).astype(np.uint8), preview)

    # Yellow overlay on untrusted edge pixels
    yellow = np.array([0, 200, 255], dtype=np.uint8)
    mask3 = np.stack([untrusted] * 3, axis=2)
    preview = np.where(mask3, (0.5 * preview + 0.5 * yellow).astype(np.uint8), preview)

    cv2.rectangle(preview, (x0, y0), (x1, y1), (0, 200, 0), 1)

    holes_count = int(np.sum(holes_in_bbox))
    edge_count = int(np.sum(untrusted))
    cv2.putText(preview, f"holes: {holes_count}px, edge: {edge_count}px", (8, h - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)

    return preview


# ============ Sprite Mode ============


def _fill_sprite_holes(img: np.ndarray) -> np.ndarray:
    """Fill internal transparent holes, preserving external transparency."""
    h, w = img.shape[:2]
    alpha = img[:, :, 3]
    transparent = alpha == 0

    if not np.any(transparent):
        return img

    # Pad + flood fill from border to mark externally-connected transparent pixels
    transp_mask = transparent.astype(np.uint8) * 255
    padded = cv2.copyMakeBorder(transp_mask, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=255)
    flood_mask = np.zeros((padded.shape[0] + 2, padded.shape[1] + 2), dtype=np.uint8)
    cv2.floodFill(padded, flood_mask, (0, 0), 128, 0, 0, 4 | cv2.FLOODFILL_FIXED_RANGE)

    # After flood: 128 = external transparent, 255 = internal holes, 0 = opaque
    unpadded = padded[1:-1, 1:-1]
    holes = transparent & (unpadded == 255)

    if not np.any(holes):
        return img

    # Fill with nearest opaque pixel color (KD-tree)
    result = img.copy()
    opaque = alpha > 0
    hole_ys, hole_xs = np.where(holes)
    opaque_ys, opaque_xs = np.where(opaque)

    if len(opaque_ys) == 0:
        return result

    tree = cKDTree(np.column_stack([opaque_ys, opaque_xs]))
    _, idx = tree.query(np.column_stack([hole_ys, hole_xs]), k=1)

    result[hole_ys, hole_xs, :3] = img[opaque_ys[idx], opaque_xs[idx], :3]
    result[hole_ys, hole_xs, 3] = 255

    return result


def perfectify_sprite(
    img: np.ndarray,
    edge_mode: str = "inward",
    radius: int = 2,
    fill_holes: bool = False,
) -> np.ndarray:
    """Clean up sprite edges after background removal.

    Processes ALL opaque pixels within `radius` px of transparent areas.

    Args:
        img: BGRA image
        edge_mode: "inward" (copy interior color), "black" (black outline), "shrink" (make transparent)
        radius: edge band depth in px
        fill_holes: fill internal transparent holes with nearest opaque color
    """
    result = img.copy()

    if fill_holes:
        result = _fill_sprite_holes(result)

    alpha = result[:, :, 3]

    opaque = alpha > 0
    transparent_u8 = (~opaque).astype(np.uint8) * 255
    kernel = np.ones((3, 3), np.uint8)

    dilated = cv2.dilate(transparent_u8, kernel, iterations=radius)
    target = (dilated > 0) & opaque

    if not np.any(target):
        return result

    if edge_mode == "shrink":
        result[target, 3] = 0
    elif edge_mode == "black":
        result[target, :3] = 0
    elif edge_mode == "inward":
        interior = opaque & ~target
        if not np.any(interior):
            result[target, :3] = (result[target, :3].astype(np.float64) * 0.5).astype(np.uint8)
        else:
            result = _copy_nearest_interior(result, target, interior)

    return result


def _copy_nearest_interior(
    img: np.ndarray,
    fringe_mask: np.ndarray,
    interior_mask: np.ndarray,
) -> np.ndarray:
    """Replace fringe pixels with color from nearest interior pixel using KD-Tree."""
    result = img.copy()

    fringe_ys, fringe_xs = np.where(fringe_mask)
    interior_ys, interior_xs = np.where(interior_mask)

    if len(interior_ys) == 0 or len(fringe_ys) == 0:
        return result

    interior_pts = np.column_stack([interior_ys, interior_xs])
    fringe_pts = np.column_stack([fringe_ys, fringe_xs])

    # Build KD-Tree for O(n log m) nearest neighbor search
    tree = cKDTree(interior_pts)
    _, nearest_idx = tree.query(fringe_pts, k=1)
    nearest_pts = interior_pts[nearest_idx]

    result[fringe_pts[:, 0], fringe_pts[:, 1], :3] = img[nearest_pts[:, 0], nearest_pts[:, 1], :3]

    return result


def _sprite_where_preview(img: np.ndarray, radius: int) -> np.ndarray:
    """Generate sprite preview: red overlay on edge band pixels."""
    h, w = img.shape[:2]
    alpha = img[:, :, 3]

    bgr = img[:, :, :3].copy()
    a = img[:, :, 3:4] / 255.0
    white = np.full((h, w, 3), 255, dtype=np.uint8)
    preview = (bgr * a + white * (1 - a)).astype(np.uint8)

    opaque = alpha > 0
    transparent_u8 = (~opaque).astype(np.uint8) * 255
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(transparent_u8, kernel, iterations=radius)
    target = (dilated > 0) & opaque

    red = np.array([0, 0, 255], dtype=np.uint8)
    mask3 = np.stack([target] * 3, axis=2)
    preview = np.where(mask3, (0.5 * preview + 0.5 * red).astype(np.uint8), preview)

    affected = int(np.sum(target))
    cv2.putText(preview, f"edge: {affected}px (r={radius})", (8, h - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)

    return preview


# ============ Batch Processing ============


def _process_single(
    input_path: Path,
    output_path: Path,
    mode: str,
    target_size: Optional[Tuple[int, int]],
    edge_mode: str,
    radius: int,
    edge_margin: int,
    passes: int,
    fill_holes: bool,
    where: bool,
) -> str:
    """Process a single image file."""
    img = cv2.imread(str(input_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Cannot read: {input_path}")

    channels = img.shape[2] if len(img.shape) == 3 else 1
    if channels == 1:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif channels == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)

    if where:
        if mode == "tile":
            preview = _tile_where_preview(img, edge_margin)
        else:
            preview = _sprite_where_preview(img, radius)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), preview)
        return str(output_path)

    result = img
    for _ in range(passes):
        if mode == "tile":
            result = perfectify_tile(result, target_size, edge_margin)
        else:
            result = perfectify_sprite(result, edge_mode, radius, fill_holes)

    # Force all alpha to 255 after all passes (tile mode only)
    if mode == "tile" and len(result.shape) == 3 and result.shape[2] == 4:
        result[:, :, 3] = 255

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), result)
    return str(output_path)


# ============ CLI ============


@app.command("perfectify")
def cmd_perfectify(
    input_path: Annotated[str, typer.Argument(help="Image file or directory")],
    mode: Annotated[str, typer.Option("--mode", "-m", help="Processing mode: tile or sprite")] = "sprite",
    output: Annotated[Optional[str], typer.Option("-o", "--output", help="Output file or directory")] = None,
    size: Annotated[Optional[str], typer.Option("--size", help="Target size WxH for tile mode (e.g. 32x32)")] = None,
    edge: Annotated[str, typer.Option("--edge", help="Sprite edge mode: inward|black|shrink")] = "inward",
    radius: Annotated[int, typer.Option("--radius", help="Sprite: edge band depth in px")] = 2,
    edge_margin: Annotated[int, typer.Option("--edge-margin", help="Tile: distrust pixels within N px of transparent")] = 3,
    passes: Annotated[int, typer.Option("--passes", "-p", help="Number of passes (each re-evaluates from current state)")] = 1,
    where: Annotated[bool, typer.Option("--where", help="Preview mode: show what would be modified")] = False,
    fill_holes: Annotated[bool, typer.Option("--fill-holes", help="Sprite: fill internal transparent holes")] = False,
    inplace: Annotated[bool, typer.Option("--inplace", help="Overwrite original files")] = False,
):
    """Clean up individual sprites or tiles after background removal.

    Tile mode (--mode tile):
      Fill from deep interior outward. --edge-margin controls how deep "interior" is.
      --passes > 1 re-evaluates each round, pushing good colors further out.

    Sprite mode (--mode sprite):
      Clean edge fringe with --edge strategy:
        inward  - copy nearest interior color (natural, default)
        black   - replace with black outline (pixel art)
        shrink  - make fringe transparent (shrink boundary)
      --fill-holes fills internal transparent holes (holes enclosed by opaque pixels).
      --passes > 1 progressively cleans deeper fringe layers.

    Examples:
      vibegame art perfectify tile.png -m tile -o clean.png
      vibegame art perfectify tile.png -m tile --edge-margin 5 --passes 3 -o clean.png
      vibegame art perfectify char.png -m sprite --edge inward --passes 2 -o clean.png
      vibegame art perfectify sprites_dir/ -m sprite -o clean_dir/
    """
    if mode not in ("tile", "sprite"):
        print("--mode must be 'tile' or 'sprite'")
        raise typer.Exit(1)

    if edge not in ("inward", "black", "shrink"):
        print("--edge must be 'inward', 'black', or 'shrink'")
        raise typer.Exit(1)

    # Parse target size
    target_size = None
    if size:
        parts = size.lower().split("x")
        if len(parts) != 2:
            print("--size must be WxH (e.g. 32x32)")
            raise typer.Exit(1)
        target_size = (int(parts[0]), int(parts[1]))

    src = Path(input_path)
    if not src.exists():
        print(f"Not found: {input_path}")
        raise typer.Exit(1)

    try:
        if src.is_file():
            # Single file
            if where and output is None:
                out = src.parent / f"{src.stem}_where_preview.png"
            elif inplace:
                out = src
            elif output:
                out = Path(output)
            else:
                print("Must specify -o/--output, --inplace, or --where")
                raise typer.Exit(1)

            result = _process_single(src, out, mode, target_size, edge, radius, edge_margin, passes, fill_holes, where)
            if where:
                tag = "blue=fill" if mode == "tile" else "red=fringe"
                print(f"Preview: {result} ({tag})")
            else:
                print(f"Done! {result}")

        elif src.is_dir():
            # Batch: process all images in directory
            if output is None and not inplace:
                print("Must specify -o/--output or --inplace for directory")
                raise typer.Exit(1)

            out_dir = Path(output) if output else src
            out_dir.mkdir(parents=True, exist_ok=True)

            images = sorted(p for p in src.iterdir()
                            if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
            if not images:
                print(f"No images found in {src}")
                raise typer.Exit(0)

            count = 0
            for img_path in images:
                if inplace:
                    out_file = img_path
                elif where:
                    out_file = out_dir / f"{img_path.stem}_where_preview.png"
                else:
                    out_file = out_dir / img_path.name

                _process_single(img_path, out_file, mode, target_size, edge, radius, edge_margin, passes, fill_holes, where)
                count += 1

            print(f"Done! Processed {count} images -> {out_dir}")

    except typer.Exit:
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(1)
