"""
Pixel art cleanup, encode, and decode tools.

Subcommands:
    vibegame art pixel process  - clean up pixel art via grid detection
    vibegame art pixel encode   - image -> color matrix text file
    vibegame art pixel decode   - color matrix text file -> image
"""

from pathlib import Path
from typing import Optional, Annotated

import cv2
import numpy as np
import typer

from perfect_pixel import get_perfect_pixel

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}

# Fixed color palettes for --palette option. RGB tuples.
PALETTES: dict[str, list[tuple[int, int, int]]] = {
    "pico8": [
        (0x00, 0x00, 0x00), (0x1D, 0x2B, 0x53), (0x7E, 0x25, 0x53), (0x00, 0x87, 0x51),
        (0xAB, 0x52, 0x36), (0x5F, 0x57, 0x4F), (0xC2, 0xC3, 0xC7), (0xFF, 0xF1, 0xE8),
        (0xFF, 0x00, 0x4D), (0xFF, 0xA3, 0x00), (0xFF, 0xEC, 0x27), (0x00, 0xE4, 0x36),
        (0x29, 0xAD, 0xFF), (0x83, 0x76, 0x9C), (0xFF, 0x77, 0xA8), (0xFF, 0xCC, 0xAA),
    ],
}

pixel_app = typer.Typer(help="Pixel art tools: process / encode / decode")


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def pixel_clean(
    img_bgra: np.ndarray,
    method: str = "center",
    grid_size: Optional[tuple] = None,
    refine_intensity: float = 0.3,
    keep_size: bool = True,
    palette: Optional[str] = None,
) -> np.ndarray:
    """Clean pixel art by grid detection, resampling, and alpha binarization.

    Args:
        img_bgra: input BGRA image
        method: sampling method - center|median|majority
        grid_size: manual (grid_w, grid_h), None for auto-detect
        refine_intensity: edge refinement strength [0, 0.5]
        keep_size: upscale back to original dimensions
        palette: name of a fixed palette in PALETTES; if None, colors are untouched
    """
    h, w = img_bgra.shape[:2]
    alpha = img_bgra[:, :, 3]

    rgb = cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2RGB)

    pw, ph, pixel_rgb = get_perfect_pixel(
        rgb,
        sample_method=method,
        grid_size=grid_size,
        refine_intensity=refine_intensity,
    )

    if pw is None:
        print("Grid detection failed, returning original")
        return img_bgra

    pixel_alpha = _sample_alpha(alpha, pw, ph, method)

    result = cv2.cvtColor(pixel_rgb, cv2.COLOR_RGB2BGRA)
    result[:, :, 3] = pixel_alpha

    if palette is not None:
        result = _apply_palette(result, palette)

    if keep_size and (pw != w or ph != h):
        result = cv2.resize(result, (w, h), interpolation=cv2.INTER_NEAREST)

    return result


def _apply_palette(img_bgra: np.ndarray, palette_name: str) -> np.ndarray:
    """Snap each opaque pixel to nearest palette color (L2 distance in RGB)."""
    # int32 so squared per-channel diffs (max 255^2 = 65025) do not overflow.
    palette = np.array(PALETTES[palette_name], dtype=np.int32)  # (K, 3) RGB
    out = img_bgra.copy()
    mask = out[:, :, 3] > 128
    if not mask.any():
        return out
    bgr = out[mask][:, :3].astype(np.int32)
    rgb = bgr[:, ::-1]                                          # (N, 3)
    d = np.sum((rgb[:, None, :] - palette[None, :, :]) ** 2, axis=2)
    idx = np.argmin(d, axis=1)
    chosen_bgr = palette[idx].astype(np.uint8)[:, ::-1]
    out[mask, :3] = chosen_bgr
    return out


def _sample_alpha(alpha: np.ndarray, pw: int, ph: int, method: str) -> np.ndarray:
    """Sample alpha using the same grid dimensions detected from RGB."""
    h, w = alpha.shape
    cell_w = w / pw
    cell_h = h / ph

    result = np.zeros((ph, pw), dtype=np.uint8)
    for gy in range(ph):
        for gx in range(pw):
            x0 = int(gx * cell_w)
            y0 = int(gy * cell_h)
            x1 = int((gx + 1) * cell_w)
            y1 = int((gy + 1) * cell_h)
            cell = alpha[y0:y1, x0:x1]

            if method == "center":
                val = cell[cell.shape[0] // 2, cell.shape[1] // 2]
            elif method == "median":
                val = int(np.median(cell))
            else:  # majority
                opaque = np.sum(cell > 128)
                total = cell.size
                val = 255 if opaque > total / 2 else 0

            result[gy, gx] = 255 if val > 128 else 0
    return result


def _process_single(
    input_path: Path,
    output_path: Path,
    method: str,
    grid_size: Optional[tuple],
    refine_intensity: float,
    keep_size: bool,
    palette: Optional[str] = None,
) -> dict:
    img = cv2.imread(str(input_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Cannot read: {input_path}")

    channels = img.shape[2] if len(img.shape) == 3 else 1
    if channels == 1:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif channels == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)

    result = pixel_clean(img, method, grid_size, refine_intensity, keep_size, palette)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), result)

    vis = result[:, :, 3] > 0
    unique_colors = len(np.unique(result[vis, :3].reshape(-1, 3), axis=0)) if np.any(vis) else 0
    return {"output": str(output_path), "size": f"{result.shape[1]}x{result.shape[0]}", "colors": unique_colors}


# ---------------------------------------------------------------------------
# Matrix encode / decode
# ---------------------------------------------------------------------------

def image_to_matrix(img_bgra: np.ndarray) -> list[list[str]]:
    """Convert BGRA image to 2D list of '#RRGGBB' or '.' for transparent."""
    h, w = img_bgra.shape[:2]
    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            b, g, r, a = img_bgra[y, x]
            if a < 128:
                row.append(".")
            else:
                row.append(f"#{r:02X}{g:02X}{b:02X}")
        rows.append(row)
    return rows


def matrix_to_image(matrix: list[list[str]], pixel_size: int = 1) -> np.ndarray:
    """Convert color matrix back to BGRA image. Each cell becomes pixel_size x pixel_size."""
    ph = len(matrix)
    pw = len(matrix[0]) if ph > 0 else 0
    h = ph * pixel_size
    w = pw * pixel_size
    img = np.zeros((h, w, 4), dtype=np.uint8)

    for gy, row in enumerate(matrix):
        for gx, cell in enumerate(row):
            y0, y1 = gy * pixel_size, (gy + 1) * pixel_size
            x0, x1 = gx * pixel_size, (gx + 1) * pixel_size
            if cell.strip() == "." or cell.strip() == "":
                pass  # leave transparent
            else:
                hex_val = cell.strip().lstrip("#")
                if len(hex_val) == 6:
                    r = int(hex_val[0:2], 16)
                    g = int(hex_val[2:4], 16)
                    b = int(hex_val[4:6], 16)
                    img[y0:y1, x0:x1] = [b, g, r, 255]
    return img


def write_matrix(matrix: list[list[str]], path: Path):
    """Write color matrix to text file."""
    h = len(matrix)
    w = len(matrix[0]) if h > 0 else 0
    with open(path, "w") as f:
        f.write(f"# {w}x{h}\n")
        for row in matrix:
            f.write(" ".join(row) + "\n")


def read_matrix(path: Path) -> list[list[str]]:
    """Read color matrix from text file. Lines starting with '# ' are metadata comments."""
    matrix = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("# "):
                continue
            matrix.append(line.split())
    return matrix


# ---------------------------------------------------------------------------
# CLI subcommands
# ---------------------------------------------------------------------------

@pixel_app.command("process")
def cmd_pixel_process(
    input_path: Annotated[str, typer.Argument(help="Image file or directory")],
    output: Annotated[Optional[str], typer.Option("-o", "--output", help="Output file or directory")] = None,
    method: Annotated[str, typer.Option("--method", "-m", help="Sampling: center|median|majority")] = "center",
    grid_size: Annotated[Optional[str], typer.Option("--grid-size", help="Manual grid WxH (e.g. 62x56)")] = None,
    refine_intensity: Annotated[float, typer.Option("--refine", help="Edge refinement [0,0.5]")] = 0.3,
    raw: Annotated[bool, typer.Option("--raw", help="Output tiny pixel art without upscale")] = False,
    inplace: Annotated[bool, typer.Option("--inplace", help="Overwrite original")] = False,
    palette: Annotated[Optional[str], typer.Option(
        "--palette",
        help=f"Snap colors to fixed palette (available: {', '.join(PALETTES)})",
    )] = None,
):
    """Clean up pixel art via grid detection and resampling."""
    if method not in ("center", "median", "majority"):
        print("--method must be center, median, or majority")
        raise typer.Exit(1)

    if palette is not None and palette not in PALETTES:
        print(f"Unknown palette '{palette}'. Available: {', '.join(PALETTES)}")
        raise typer.Exit(1)

    gs = None
    if grid_size:
        parts = grid_size.lower().split("x")
        if len(parts) != 2:
            print("--grid-size must be WxH (e.g. 62x56)")
            raise typer.Exit(1)
        gs = (int(parts[0]), int(parts[1]))

    keep_size = not raw
    src = Path(input_path)
    if not src.exists():
        print(f"Not found: {input_path}")
        raise typer.Exit(1)

    try:
        if src.is_file():
            if inplace:
                out = src
            elif output:
                out = Path(output)
            else:
                print("Must specify -o/--output or --inplace")
                raise typer.Exit(1)
            stats = _process_single(src, out, method, gs, refine_intensity, keep_size, palette)
            print(f"Done! {stats['output']} ({stats['size']}, {stats['colors']} colors)")

        elif src.is_dir():
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
            results = []
            for img_path in images:
                out_file = img_path if inplace else out_dir / img_path.name
                try:
                    stats = _process_single(img_path, out_file, method, gs, refine_intensity, keep_size, palette)
                    results.append(stats)
                except Exception as e:
                    print(f"Failed {img_path.name}: {e}")
            print(f"Processed {len(results)} images:")
            for r in results:
                print(f"  {Path(r['output']).name}: {r['size']}, {r['colors']} colors")

    except typer.Exit:
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(1)


@pixel_app.command("encode")
def cmd_pixel_encode(
    input_path: Annotated[str, typer.Argument(help="Image file (should be processed pixel art)")],
    output: Annotated[Optional[str], typer.Option("-o", "--output", help="Output .txt path (default: <input>.txt)")] = None,
    grid_size: Annotated[Optional[str], typer.Option("--grid-size", help="Manual grid WxH for process step")] = None,
    method: Annotated[str, typer.Option("--method", "-m", help="Sampling: center|median|majority")] = "center",
    no_process: Annotated[bool, typer.Option("--no-process", help="Skip pixel cleanup, encode image as-is")] = False,
):
    """Convert image to editable color matrix text file.

    Each pixel is written as #RRGGBB, transparent pixels as '.'.
    Runs pixel cleanup first (use --no-process to skip).

    Examples:
      vibegame art pixel encode sprite.png -o sprite.txt
      vibegame art pixel encode sprite.png --grid-size 62x56 -o sprite.txt
      vibegame art pixel encode tiny.png --no-process -o matrix.txt
    """
    src = Path(input_path)
    if not src.exists():
        print(f"Not found: {input_path}")
        raise typer.Exit(1)

    img = cv2.imread(str(src), cv2.IMREAD_UNCHANGED)
    if img is None:
        print(f"Cannot read: {src}")
        raise typer.Exit(1)

    channels = img.shape[2] if len(img.shape) > 2 else 1
    if channels == 1:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif channels == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)

    if not no_process:
        gs = None
        if grid_size:
            parts = grid_size.lower().split("x")
            if len(parts) != 2:
                print("--grid-size must be WxH")
                raise typer.Exit(1)
            gs = (int(parts[0]), int(parts[1]))
        img = pixel_clean(img, method, gs, keep_size=False)  # get tiny version

    h, w = img.shape[:2]
    matrix = image_to_matrix(img)

    out_path = Path(output) if output else src.with_suffix(".txt")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_matrix(matrix, out_path)
    print(f"Encoded {w}x{h} -> [{out_path}]({out_path})")


@pixel_app.command("decode")
def cmd_pixel_decode(
    input_path: Annotated[str, typer.Argument(help="Color matrix .txt file")],
    output: Annotated[Optional[str], typer.Option("-o", "--output", help="Output image path")] = None,
    size: Annotated[int, typer.Option("-s", "--size", help="Pixel size: each cell becomes NxN actual pixels")] = 1,
):
    """Convert color matrix text file back to image.

    Each cell in the matrix becomes --size x --size pixels in the output.

    Examples:
      vibegame art pixel decode sprite.txt -o sprite.png
      vibegame art pixel decode sprite.txt -s 6 -o sprite_6x.png
    """
    src = Path(input_path)
    if not src.exists():
        print(f"Not found: {input_path}")
        raise typer.Exit(1)

    matrix = read_matrix(src)
    if not matrix:
        print("Empty matrix")
        raise typer.Exit(1)

    img = matrix_to_image(matrix, pixel_size=size)

    out_path = Path(output) if output else src.with_suffix(".png")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), img)

    h, w = img.shape[:2]
    print(f"Decoded -> [{out_path}]({out_path}) ({w}x{h}, pixel_size={size})")


# Backwards-compatible: expose cmd_pixel as alias for process
cmd_pixel = cmd_pixel_process
