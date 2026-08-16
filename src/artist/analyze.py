"""
Color analysis and asset inspection tool.

Usage:
    vibegame art analyze <image>
    vibegame art analyze <image> --region 0,0,100,100 --top 5
    vibegame art tree <directory>
"""

import json
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, List, Annotated

import typer

app = typer.Typer(name="analyze", help="Color analysis and asset inspection", add_completion=False, rich_markup_mode=None, pretty_exceptions_enable=False)


# ============ Core Functions ============


def check_transparency(img: np.ndarray) -> str:
    """Detect image transparency type.

    Returns: "opaque" | "binary_alpha" | "pseudo_translucent" | "translucent"
    """
    if len(img.shape) < 3 or img.shape[2] != 4:
        return "opaque"

    alpha = img[:, :, 3]
    if np.all(alpha == 255):
        return "opaque"

    has_partial = np.any((alpha > 0) & (alpha < 255))
    if not has_partial:
        return "binary_alpha"

    transparent_pixels = img[alpha == 0]
    if len(transparent_pixels) > 0:
        unique_colors = len(np.unique(transparent_pixels[:, :3].reshape(-1, 3), axis=0))
        if unique_colors <= 4:
            return "pseudo_translucent"
    return "translucent"


def check_asset(image_path: str) -> dict:
    """Check image asset properties: dimensions, transparency, format, file size."""
    path = Path(image_path)
    if not path.exists():
        raise ValueError(f"File not found: {image_path}")

    result = {
        "path": str(path),
        "name": path.name,
        "format": path.suffix.lower().lstrip("."),
        "file_size": path.stat().st_size,
    }

    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        result["error"] = "Cannot read image"
        return result

    h, w = img.shape[:2]
    channels = img.shape[2] if len(img.shape) == 3 else 1
    result["width"] = w
    result["height"] = h
    result["channels"] = channels
    result["has_alpha"] = channels == 4
    result["transparency"] = check_transparency(img)
    return result


def analyze_image(image_path: str, region: Optional[str] = None, top: int = 10) -> dict:
    """Analyze image color structure.

    Args:
        image_path: path to image
        region: optional "x,y,w,h" sub-region
        top: number of dominant colors to report

    Returns:
        JSON-serializable dict with analysis results
    """
    path = Path(image_path)
    if not path.exists():
        raise ValueError(f"File not found: {image_path}")

    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Cannot read image: {image_path}")

    # Crop to region if specified
    if region:
        parts = [int(x) for x in region.split(",")]
        if len(parts) != 4:
            raise ValueError("region must be x,y,w,h")
        rx, ry, rw, rh = parts
        img = img[ry:ry + rh, rx:rx + rw]

    h, w = img.shape[:2]
    channels = img.shape[2] if len(img.shape) == 3 else 1
    transparency = check_transparency(img)
    color_result = _analyze_colors(img, top)

    return {
        "size": [w, h],
        "channels": channels,
        "transparency": transparency,
        **color_result,
    }


def _analyze_colors(img: np.ndarray, top: int = 10) -> dict:
    """Color analysis only (slow part). Returns unique_colors, background_guess, dominant/rarest colors."""
    h, w = img.shape[:2]
    channels = img.shape[2] if len(img.shape) == 3 else 1

    if channels == 1:
        img_rgba = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif channels == 3:
        img_rgba = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        img_rgba[:, :, 3] = 255
    else:
        img_rgba = img.copy()

    alpha_mask = img_rgba[:, :, 3] > 0
    visible_pixels = img_rgba[alpha_mask][:, :3]  # BGR

    if len(visible_pixels) == 0:
        return {"unique_colors": 0, "background_guess": None, "dominant_colors": [], "rarest_colors": []}

    unique_bgr = np.unique(visible_pixels.reshape(-1, 3), axis=0)
    unique_colors = len(unique_bgr)

    total_pixels = w * h
    edge_pixels, transparent_ratio = _sample_edge_pixels(img_rgba)
    background_guess = _guess_background(edge_pixels, transparent_ratio)
    dominant_colors = _top_colors(visible_pixels, top, total_pixels)
    rarest_colors = _bottom_colors(visible_pixels, 10, total_pixels)

    return {
        "unique_colors": unique_colors,
        "background_guess": background_guess,
        "dominant_colors": dominant_colors,
        "rarest_colors": rarest_colors,
    }


def _sample_edge_pixels(img_rgba: np.ndarray) -> tuple[np.ndarray, float]:
    """Sample visible (alpha > 0) edge pixels. Returns (visible_bgr, transparent_ratio)."""
    h, w = img_rgba.shape[:2]
    top = img_rgba[0, :, :]
    bottom = img_rgba[h - 1, :, :]
    left = img_rgba[:, 0, :]
    right = img_rgba[:, w - 1, :]
    all_edges = np.vstack([top, bottom, left, right])
    transparent_ratio = float(np.sum(all_edges[:, 3] == 0)) / len(all_edges)
    visible = all_edges[all_edges[:, 3] > 0][:, :3]
    return visible, transparent_ratio


def _guess_background(edge_samples: np.ndarray, transparent_ratio: float = 0.0) -> Optional[dict]:
    """Estimate background color from visible edge samples."""
    if len(edge_samples) == 0 or transparent_ratio > 0.5:
        return None

    colors, counts = np.unique(edge_samples.reshape(-1, 3), axis=0, return_counts=True)
    best_idx = np.argmax(counts)
    best_color = colors[best_idx]
    confidence = float(counts[best_idx]) / len(edge_samples)

    # best_color is BGR, convert to RGB for output
    return {
        "color": [int(best_color[2]), int(best_color[1]), int(best_color[0])],
        "confidence": round(confidence, 4),
        "edge_sample_count": len(edge_samples),
    }


def _top_colors(visible_bgr: np.ndarray, top: int, total_pixels: int) -> List[dict]:
    """Return top N colors by frequency among visible pixels."""
    if len(visible_bgr) == 0:
        return []

    colors, counts = np.unique(visible_bgr.reshape(-1, 3), axis=0, return_counts=True)
    order = np.argsort(-counts)
    results = []
    for i in order[:top]:
        bgr = colors[i]
        results.append({
            "color": [int(bgr[2]), int(bgr[1]), int(bgr[0])],  # BGR -> RGB
            "count": int(counts[i]),
            "ratio": round(float(counts[i]) / total_pixels, 4),
        })
    return results


def _bottom_colors(visible_bgr: np.ndarray, bottom: int, total_pixels: int) -> List[dict]:
    """Return bottom N rarest colors by frequency among visible pixels."""
    if len(visible_bgr) == 0:
        return []

    colors, counts = np.unique(visible_bgr.reshape(-1, 3), axis=0, return_counts=True)
    order = np.argsort(counts)  # ascending
    results = []
    for i in order[:bottom]:
        bgr = colors[i]
        results.append({
            "color": [int(bgr[2]), int(bgr[1]), int(bgr[0])],
            "count": int(counts[i]),
            "ratio": round(float(counts[i]) / total_pixels, 6),
        })
    return results


# ============ SpriteTree (Optimized) ============

class SpriteTree:
    """Directory tree analyzer for image assets."""

    SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
    # Auto-excluded directories (like .gitignore for game projects)
    EXCLUDE_DIRS = {"artifacts", "decomposed", "cut", ".git", "__pycache__", "node_modules"}

    def tree(self, path: str) -> str:
        """Analyze folder structure or single image, return formatted string."""
        from PIL import Image

        root = Path(path)
        if not root.exists():
            raise ValueError(f"Path not found: {path}")

        lines = ["Listing all image shapes(width,height) and transparency"]

        if root.is_file():
            if root.suffix.lower() in self.SUPPORTED_EXTS:
                try:
                    with Image.open(root) as img:
                        w, h = img.size
                        trans = self._check_transparency_fast(img)
                        lines.append(f"- {root.name}: ({w},{h}) [{trans}]")
                except Exception:
                    lines.append(f"- {root.name}: (cannot read)")
            else:
                raise ValueError(f"Unsupported image format: {root.suffix}")
        else:
            # Collect all images first for progress bar
            all_images = list(self._collect_images(root))
            if not all_images:
                return "No images found."

            print("Scanning images...")
            self._build_tree_fast(root, lines, prefix="", all_images=all_images)

        return "\n".join(lines)

    def _collect_images(self, path: Path):
        """Yield all image file paths under directory, skipping EXCLUDE_DIRS."""
        for item in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
            if item.is_dir():
                if item.name not in self.EXCLUDE_DIRS:
                    yield from self._collect_images(item)
            elif item.suffix.lower() in self.SUPPORTED_EXTS:
                yield item

    def _check_transparency_fast(self, img) -> str:
        """Fast transparency check using PIL (no full pixel load)."""
        from PIL import Image

        mode = img.mode
        if mode != "RGBA":
            return "opaque"

        # Sample alpha channel (faster than loading all pixels)
        try:
            alpha = img.split()[-1]
            # Check corners and center (5 points) for quick detection
            w, h = img.size
            sample_points = [
                alpha.getpixel((0, 0)),
                alpha.getpixel((w - 1, 0)),
                alpha.getpixel((0, h - 1)),
                alpha.getpixel((w - 1, h - 1)),
                alpha.getpixel((w // 2, h // 2)),
            ]
            if all(p == 255 for p in sample_points):
                return "opaque"
            if all(p in (0, 255) for p in sample_points):
                return "binary_alpha"
            return "translucent"
        except Exception:
            return "opaque"

    def _has_assets(self, path: Path, all_images: set) -> bool:
        """Check if directory contains any images (uses pre-collected set)."""
        for img in all_images:
            if str(img).startswith(str(path) + "/"):
                return True
        return False

    def _build_tree_fast(self, path: Path, lines: List[str], prefix: str, all_images: list):
        """Build tree using pre-collected images."""
        from PIL import Image

        # Build set for fast lookup
        image_set = set(all_images)
        path_str = str(path)

        items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
        for item in items:
            if item.is_dir():
                if self._has_assets(item, image_set):
                    lines.append(f"{prefix}- {item.name}/")
                    self._build_tree_fast(item, lines, prefix + "  ", all_images)
            elif item.suffix.lower() in self.SUPPORTED_EXTS:
                try:
                    with Image.open(item) as img:
                        w, h = img.size
                        trans = self._check_transparency_fast(img)
                        lines.append(f"{prefix}- {item.name}: ({w},{h}) [{trans}]")
                except Exception:
                    lines.append(f"{prefix}- {item.name}: (error)")


# ============ CLI Commands ============


@app.command("analyze")
def cmd_analyze(
    image: Annotated[str, typer.Argument(help="Image path")],
    region: Annotated[Optional[str], typer.Option("--region", help="Sub-region x,y,w,h")] = None,
    top: Annotated[int, typer.Option("--top", help="Number of dominant colors")] = 10,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Human-readable output with color swatches")] = False,
):
    """Analyze image color structure, output JSON."""
    import sys
    try:
        # Phase 1: fast metadata (dimensions, channels, transparency)
        info = check_asset(image)
        if "error" in info:
            print(f"Error: {info['error']}")
            raise typer.Exit(1)

        img = cv2.imread(str(Path(image)), cv2.IMREAD_UNCHANGED)
        if region:
            parts = [int(x) for x in region.split(",")]
            if len(parts) != 4:
                raise ValueError("region must be x,y,w,h")
            rx, ry, rw, rh = parts
            img = img[ry:ry + rh, rx:rx + rw]

        h, w = img.shape[:2]
        channels = img.shape[2] if len(img.shape) == 3 else 1
        transparency = check_transparency(img)

        if verbose:
            print(f"\nSize: {w}x{h}  Channels: {channels}  Transparency: {transparency}")
        else:
            phase1 = {"size": [w, h], "channels": channels, "transparency": transparency}
            sys.stdout.write(json.dumps(phase1, ensure_ascii=False))
            sys.stdout.flush()

        # Phase 2: color analysis (slow for large images)
        if verbose:
            print("Analyzing colors...")
        color_result = _analyze_colors(img, top=top)

        if verbose:
            result = {"size": [w, h], "channels": channels, "transparency": transparency, **color_result}
            _print_verbose(result)
        else:
            full = {**phase1, **color_result}
            # Overwrite the partial JSON line with full result
            sys.stdout.write("\r" + " " * 200 + "\r")
            print(json.dumps(full, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(1)
def _print_verbose(result: dict):
    """Print analysis result as human-readable output."""
    w, h = result["size"]
    print(f"\nSize: {w}x{h}  Channels: {result['channels']}  Transparency: {result['transparency']}")
    print(f"Unique colors: {result['unique_colors']}")

    bg = result.get("background_guess")
    if bg:
        r, g, b = bg["color"]
        print(f"Background guess: rgb({r},{g},{b}) [{bg['confidence']:.0%} confidence]")

    print(f"\nTop {len(result['dominant_colors'])} colors:")
    for entry in result["dominant_colors"]:
        r, g, b = entry["color"]
        ratio = entry["ratio"]
        bar_len = max(1, int(ratio * 40))
        bar = "#" * bar_len
        print(
            f"  rgb({r},{g},{b})  "
            f"{ratio:6.1%}  ({entry['count']:,} px)  {bar}"
        )
    print()

    rare = result.get("rarest_colors", [])
    if rare:
        print(f"Rarest {len(rare)} colors (potential noise):")
        for entry in rare:
            r, g, b = entry["color"]
            count = entry["count"]
            print(f"  rgb({r},{g},{b})  {count} px")
        print()
@app.command("tree")
def cmd_tree(
    path: Annotated[str, typer.Argument(help="Directory or image path")],
):
    """List all images under directory with sizes and transparency."""
    tree = SpriteTree()
    try:
        result = tree.tree(path)
        print(result)
    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(1)
