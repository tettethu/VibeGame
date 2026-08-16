"""
Background removal tool - make target colors transparent.

Modes:
  --seed only      sample color from seed points, flood fill from those seeds
  -c only          global color replace (no flood fill)
  -c + --seed      explicit color center + flood fill from seeds
                   --seed match      = use pixels exactly equal to -c as seeds
                   --seed match:T    = use pixels within tolerance T of -c as seeds

Usage:
    vibegame art rmbg <image> --tolerance 20 -o <output>             # default: seed=corner
    vibegame art rmbg <image> --seed tl --seed tr -t 15 -o <output>
    vibegame art rmbg <image> -c 255,255,255 -t 10 -o <output>       # global replace
    vibegame art rmbg <image> -c 255,255,255 --seed match -t 20 -o <output>
    vibegame art rmbg <image> -c 255,0,255 --seed match:5 -t 40 -o <output>  # loose seed
    vibegame art rmbg <image> --where
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, List, Annotated, Tuple

import typer

app = typer.Typer(name="rmbg", help="Background removal by color + flood fill", add_completion=False, rich_markup_mode=None, pretty_exceptions_enable=False)


# ============ Color Spec Parsing ============


def _parse_color_spec(spec: str, default_tolerance: int) -> Tuple[Tuple[int, int, int], int]:
    """Parse 'R,G,B' or 'R,G,B:T' into ((r,g,b), tolerance)."""
    if ":" in spec:
        color_part, tol_part = spec.rsplit(":", 1)
        tol = int(tol_part.strip())
    else:
        color_part = spec
        tol = default_tolerance
    parts = [int(x.strip()) for x in color_part.split(",")]
    if len(parts) != 3:
        raise ValueError(f"Color must be R,G,B or R,G,B:T, got: {spec}")
    return (parts[0], parts[1], parts[2]), tol


# ============ Seed Parsing ============


def _parse_seeds(seed_strs: List[str], h: int, w: int) -> List[Tuple[int, int]]:
    """Parse geometric seed specs into (x, y) list.

    Accepted: "corner", "tl/tr/bl/br", "x,y"
    "match" is NOT handled here — caller must filter it out first.
    """
    result = []
    for s in seed_strs:
        s = s.strip().lower()
        if s in ("corner", "corners"):
            result += [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
        elif s == "tl":
            result.append((0, 0))
        elif s == "tr":
            result.append((w - 1, 0))
        elif s == "bl":
            result.append((0, h - 1))
        elif s == "br":
            result.append((w - 1, h - 1))
        elif s == "match" or s.startswith("match:"):
            raise ValueError("--seed match[:T] requires -c/--color to also be specified")
        else:
            parts = s.split(",")
            if len(parts) != 2:
                raise ValueError(f"Seed must be x,y | tl/tr/bl/br | corner | match, got: {s!r}")
            x, y = int(parts[0].strip()), int(parts[1].strip())
            if not (0 <= x < w and 0 <= y < h):
                raise ValueError(f"Seed {x},{y} is out of image bounds ({w}x{h})")
            result.append((x, y))
    return result


def _extract_match_tols(seeds: List[str]) -> Tuple[List[str], List[int]]:
    """Split seed list into (geometric_seeds, match_tolerances).

    'match' -> tol 0 (exact). 'match:T' -> tol T (flexible).
    """
    geometric: List[str] = []
    match_tols: List[int] = []
    for s in seeds:
        s_clean = s.strip().lower()
        if s_clean == "match":
            match_tols.append(0)
        elif s_clean.startswith("match:"):
            tol_str = s_clean.split(":", 1)[1].strip()
            try:
                match_tols.append(int(tol_str))
            except ValueError:
                raise ValueError(f"--seed match:T expects integer T, got: {s!r}")
        else:
            geometric.append(s)
    return geometric, match_tols


def _sample_colors_from_seeds(bgr: np.ndarray, seed_pts: List[Tuple[int, int]], tolerance: int) -> List[Tuple[Tuple[int, int, int], int]]:
    """Sample one color spec per unique seed pixel color."""
    seen: set = set()
    specs = []
    for (sx, sy) in seed_pts:
        b, g, r = int(bgr[sy, sx, 0]), int(bgr[sy, sx, 1]), int(bgr[sy, sx, 2])
        color = (r, g, b)
        if color not in seen:
            seen.add(color)
            specs.append((color, tolerance))
    return specs


# ============ Region Masking ============


def _parse_rect(s: str) -> Tuple[int, int, int, int]:
    parts = [int(x.strip()) for x in s.split(",")]
    if len(parts) != 4:
        raise ValueError(f"Region must be x,y,w,h, got: {s}")
    return tuple(parts)


def _region_mask(shape: Tuple[int, int], rects: List[Tuple], region_shape: str) -> np.ndarray:
    h, w = shape
    mask = np.zeros((h, w), dtype=bool)
    for (rx, ry, rw, rh) in rects:
        if region_shape == "circle":
            cx, cy = rx + rw // 2, ry + rh // 2
            r = min(rw, rh) // 2
            Y, X = np.ogrid[:h, :w]
            mask |= (X - cx) ** 2 + (Y - cy) ** 2 <= r ** 2
        elif region_shape == "hollow-rect":
            sub = np.zeros((h, w), dtype=bool)
            sub[ry:ry + rh, rx:rx + rw] = True
            inner = np.zeros((h, w), dtype=bool)
            b = 2
            inner[ry + b:ry + rh - b, rx + b:rx + rw - b] = True
            mask |= sub & ~inner
        elif region_shape == "hollow-circle":
            cx, cy = rx + rw // 2, ry + rh // 2
            r_outer = min(rw, rh) // 2
            r_inner = max(r_outer - 3, 0)
            Y, X = np.ogrid[:h, :w]
            d2 = (X - cx) ** 2 + (Y - cy) ** 2
            mask |= (d2 <= r_outer ** 2) & (d2 > r_inner ** 2)
        else:
            mask[ry:ry + rh, rx:rx + rw] = True
    return mask


# ============ Core Logic ============


def _build_color_mask(
    bgr: np.ndarray,
    color_specs: List[Tuple[Tuple[int, int, int], int]],
    metric: str = "rgb",
) -> np.ndarray:
    """Union mask of all pixels matching any color spec under the chosen metric.

    metric:
      rgb     — euclidean distance in BGR space (default). tol ∈ [0, ~441].
      hsv     — hue circular diff + half-weighted sat diff + half-weighted val diff.
                Hue dominates ordering, but brightness still matters — so a dark
                colour along the target hue (e.g. enemy shadow with a purple tint
                vs a bright magenta background) does NOT match. tol roughly 0..400.
      cosine  — angle between BGR vectors (treats colours as rays from origin).
                Brightness is ignored entirely — dark and bright pixels along the
                same direction match equally. Useful only when that is the goal.
                tol scales angular distance to 0..255 (0..180 degrees).
    """
    h, w = bgr.shape[:2]
    mask = np.zeros((h, w), dtype=bool)

    if metric == "rgb":
        bgr_i16 = bgr.astype(np.int16)
        for (r, g, b), tol in color_specs:
            target = np.array([b, g, r], dtype=np.int16)
            diff = bgr_i16 - target
            dist_sq = np.sum(diff.astype(np.int32) ** 2, axis=2)
            mask |= (dist_sq == 0) if tol == 0 else (dist_sq <= tol * tol)
        return mask

    if metric == "hsv":
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.int32)
        for (r, g, b), tol in color_specs:
            target_bgr_px = np.array([[[b, g, r]]], dtype=np.uint8)
            t = cv2.cvtColor(target_bgr_px, cv2.COLOR_BGR2HSV)[0, 0].astype(np.int32)
            dh_raw = np.abs(hsv[:, :, 0] - t[0])
            dh = np.minimum(dh_raw, 180 - dh_raw)        # circular, 0..90 (OpenCV hue scale)
            dh_scaled = dh * 255 // 90                   # 0..255 — full weight
            ds = np.abs(hsv[:, :, 1] - t[1]) // 2        # 0..127 — half weight
            dv = np.abs(hsv[:, :, 2] - t[2]) // 2        # 0..127 — half weight
            dist_sq = dh_scaled ** 2 + ds ** 2 + dv ** 2
            mask |= (dist_sq == 0) if tol == 0 else (dist_sq <= tol * tol)
        return mask

    if metric == "cosine":
        bgr_f = bgr.astype(np.float32)
        norms = np.linalg.norm(bgr_f, axis=2)
        safe_norms = np.maximum(norms, 1e-6)
        for (r, g, b), tol in color_specs:
            target = np.array([b, g, r], dtype=np.float32)
            t_norm = float(np.linalg.norm(target))
            if t_norm < 1e-6:
                # Black target — angle undefined; match only near-black pixels.
                mask |= norms < 1.0
                continue
            t_unit = target / t_norm
            cos_sim = np.clip((bgr_f * t_unit).sum(axis=2) / safe_norms, -1.0, 1.0)
            angle = np.arccos(cos_sim)                   # radians, 0..pi
            dist = angle * (255.0 / np.pi)               # 0..255
            mask |= (dist <= float(tol))
        return mask

    raise ValueError(f"Unknown metric: {metric!r} (expected rgb|hsv|cosine)")


def _flood_connected_mask(
    color_mask: np.ndarray,
    seed_pts: Optional[List[Tuple[int, int]]] = None,
    seed_mask: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Keep only color_mask pixels in connected components touched by seeds.

    Seeds can be geometric points (seed_pts) or a boolean mask (seed_mask), or both.
    """
    _, labels = cv2.connectedComponents(color_mask.astype(np.uint8), connectivity=8)
    result = np.zeros(color_mask.shape, dtype=bool)
    seen: set = set()

    if seed_mask is not None:
        for label_id in np.unique(labels[seed_mask]):
            if label_id > 0:
                result |= labels == label_id
                seen.add(label_id)

    if seed_pts:
        for (sx, sy) in seed_pts:
            label_id = int(labels[sy, sx])
            if label_id > 0 and label_id not in seen:
                seen.add(label_id)
                result |= labels == label_id

    return result


def build_seed_mask(
    bgr: np.ndarray,
    seed_pts: List[Tuple[int, int]],
    tolerance: int,
    metric: str = "rgb",
) -> np.ndarray:
    """Build the connected removal mask for colors sampled at seed points."""
    if not seed_pts:
        raise ValueError("At least one seed point is required")

    h, w = bgr.shape[:2]
    for sx, sy in seed_pts:
        if not (0 <= sx < w and 0 <= sy < h):
            raise ValueError(f"Seed {sx},{sy} is out of image bounds ({w}x{h})")

    color_specs = _sample_colors_from_seeds(bgr, seed_pts, tolerance)
    color_mask = _build_color_mask(bgr, color_specs, metric=metric)
    return _flood_connected_mask(color_mask, seed_pts=seed_pts)


def apply_transparency_mask(
    bgra: np.ndarray,
    target_mask: np.ndarray,
    defringe: int = 0,
) -> np.ndarray:
    """Apply a removal mask to a BGRA image using the CLI defringe behavior."""
    if bgra.ndim != 3 or bgra.shape[2] != 4:
        raise ValueError("Expected a BGRA image")
    if target_mask.shape != bgra.shape[:2]:
        raise ValueError("Removal mask dimensions do not match the image")

    result = bgra.copy()
    result[target_mask, 3] = 0
    if defringe > 0:
        result = _apply_defringe(result, target_mask, defringe)
    return result


def remove_bg(
    image_path: str,
    output_path: Optional[str] = None,
    tolerance: int = 0,
    colors: Optional[List[str]] = None,
    seeds: Optional[List[str]] = None,
    apply_regions: Optional[List[str]] = None,
    protect_regions: Optional[List[str]] = None,
    apply_shape: str = "rect",
    where: bool = False,
    defringe: int = 0,
    inplace: bool = False,
    metric: str = "rgb",
) -> str:
    """Remove background by making target colors transparent.

    Three modes depending on -c / --seed combination:
      --seed only:   sample color from seeds, flood fill
      -c only:       global color replace, no flood fill
      -c + --seed:   explicit color + flood fill (--seed match uses exact-color pixels as seeds)

    Default (no flags): equivalent to --seed corner.
    """
    path = Path(image_path)
    if not path.exists():
        raise ValueError(f"File not found: {image_path}")

    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Cannot read image: {image_path}")

    h, w = img.shape[:2]
    channels = img.shape[2] if len(img.shape) == 3 else 1

    if channels == 1:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif channels == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)

    img = img.copy()
    bgr = img[:, :, :3]

    has_color = bool(colors)
    has_seed = bool(seeds)

    # Default: seed=corner
    if not has_color and not has_seed:
        seeds = ["corner"]
        has_seed = True

    if has_color:
        color_specs = [_parse_color_spec(c, tolerance) for c in colors]

    if not has_seed:
        # -c only: global replace, no flood fill
        target_mask = _build_color_mask(bgr, color_specs, metric=metric)
        seed_pts_for_preview: List[Tuple[int, int]] = []

    elif not has_color:
        # --seed only: sample color from geometric seeds, flood fill
        seed_pts = _parse_seeds(seeds, h, w)
        target_mask = build_seed_mask(bgr, seed_pts, tolerance, metric=metric)
        seed_pts_for_preview = seed_pts

    else:
        # -c + --seed: explicit color + flood fill
        geometric, match_tols = _extract_match_tols(seeds)
        has_match = bool(match_tols)

        seed_pts = _parse_seeds(geometric, h, w) if geometric else []

        target_mask = _build_color_mask(bgr, color_specs, metric=metric)

        if has_match:
            # Pixels within match_tol of -c become flood seeds.
            # If multiple match:T given, use the largest (most permissive union).
            match_tol = max(match_tols)
            match_specs = [(spec[0], match_tol) for spec in color_specs]
            match_seed_mask = _build_color_mask(bgr, match_specs, metric=metric)
        else:
            match_seed_mask = None

        target_mask = _flood_connected_mask(target_mask, seed_pts=seed_pts or None, seed_mask=match_seed_mask)
        seed_pts_for_preview = seed_pts

    if apply_regions:
        apply_mask = _region_mask((h, w), [_parse_rect(s) for s in apply_regions], apply_shape)
        target_mask = target_mask & apply_mask

    if protect_regions:
        protect_mask = _region_mask((h, w), [_parse_rect(s) for s in protect_regions], apply_shape)
        target_mask = target_mask & ~protect_mask

    if where:
        return _render_where_preview(img, seed_pts_for_preview, apply_regions, protect_regions, apply_shape, output_path, image_path)

    result = apply_transparency_mask(img, target_mask, defringe=defringe)

    if inplace:
        out_path = path
    elif output_path:
        out_path = Path(output_path)
    else:
        raise ValueError("Must specify -o/--output or --inplace (or use --where for preview)")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), result)
    return str(out_path)


# ============ Preview & Defringe ============


def _render_where_preview(
    img: np.ndarray,
    seed_pts: List[Tuple[int, int]],
    apply_regions: Optional[List[str]],
    protect_regions: Optional[List[str]],
    apply_shape: str,
    output_path: Optional[str],
    source_path: str,
) -> str:
    h, w = img.shape[:2]
    bgr = img[:, :, :3].copy()
    alpha = img[:, :, 3:4] / 255.0
    white_bg = np.full((h, w, 3), 255, dtype=np.uint8)
    preview = (bgr * alpha + white_bg * (1 - alpha)).astype(np.uint8)

    for (sx, sy) in seed_pts:
        cv2.drawMarker(preview, (sx, sy), (0, 0, 255), cv2.MARKER_CROSS, 12, 2)

    if apply_regions:
        for region_str in apply_regions:
            rx, ry, rw, rh = _parse_rect(region_str)
            cv2.rectangle(preview, (rx, ry), (rx + rw, ry + rh), (0, 200, 0), 2)
            cv2.putText(preview, f"{rx},{ry}", (rx + 4, ry + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 0), 1)

    if protect_regions:
        for region_str in protect_regions:
            rx, ry, rw, rh = _parse_rect(region_str)
            cv2.rectangle(preview, (rx, ry), (rx + rw, ry + rh), (255, 100, 0), 2)
            cv2.putText(preview, f"{rx},{ry}", (rx + 4, ry + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 100, 0), 1)

    if output_path:
        out_path = Path(output_path)
    else:
        src = Path(source_path)
        out_path = src.parent / f"{src.stem}_where_preview.png"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), preview)
    return str(out_path)


def _apply_defringe(img: np.ndarray, removed_mask: np.ndarray, radius: int) -> np.ndarray:
    """Fix edge pixels within radius px using nearest interior color."""
    from scipy.spatial import cKDTree

    result = img.copy()
    removed_u8 = removed_mask.astype(np.uint8) * 255
    dilated = cv2.dilate(removed_u8, np.ones((2 * radius + 1, 2 * radius + 1), np.uint8))
    fringe_mask = (dilated > 0) & ~removed_mask & (img[:, :, 3] > 0)

    if not np.any(fringe_mask):
        return result

    interior_mask = ~removed_mask & (img[:, :, 3] > 0) & ~fringe_mask
    if not np.any(interior_mask):
        return result

    fringe_ys, fringe_xs = np.where(fringe_mask)
    interior_ys, interior_xs = np.where(interior_mask)
    fringe_pts = np.column_stack([fringe_ys, fringe_xs])
    interior_pts = np.column_stack([interior_ys, interior_xs])

    tree = cKDTree(interior_pts)
    _, nearest_idx = tree.query(fringe_pts, k=1)
    nearest_pts = interior_pts[nearest_idx]
    result[fringe_pts[:, 0], fringe_pts[:, 1]] = img[nearest_pts[:, 0], nearest_pts[:, 1]]

    return result


# ============ CLI ============


@app.command("rmbg")
def cmd_rmbg(
    image: Annotated[str, typer.Argument(help="Input image path")],
    output: Annotated[Optional[str], typer.Option("-o", "--output", help="Output file path")] = None,
    tolerance: Annotated[int, typer.Option("--tolerance", "-t", help="RGB distance tolerance (0=exact)")] = 0,
    color: Annotated[Optional[List[str]], typer.Option("-c", "--color", help="Color center R,G,B or R,G,B:T (repeatable). Omit to sample from seeds")] = None,
    seed: Annotated[Optional[List[str]], typer.Option("--seed", help="Seed: corner | tl/tr/bl/br | x,y | match[:T] (match requires -c; :T sets its own tolerance, default 0)")] = None,
    apply: Annotated[Optional[List[str]], typer.Option("--apply", help="Only replace within region x,y,w,h (repeatable)")] = None,
    protect: Annotated[Optional[List[str]], typer.Option("--protect", help="Skip this region x,y,w,h (repeatable)")] = None,
    apply_shape: Annotated[str, typer.Option("--apply-shape", help="Shape: rect|circle|hollow-rect|hollow-circle")] = "rect",
    where: Annotated[bool, typer.Option("--where", help="Preview: show affected pixels and seeds")] = False,
    defringe: Annotated[int, typer.Option("--defringe", help="Fix edge fringe within N px after removal")] = 0,
    inplace: Annotated[bool, typer.Option("--inplace", help="Overwrite original file")] = False,
    metric: Annotated[str, typer.Option("--metric", help="Color distance metric: rgb (default) | hsv (hue-dominant) | cosine (angular)")] = "rgb",
    agent: Annotated[bool, typer.Option("--agent", help="Use mini-agent for automatic background removal")] = False,
    agent_model: Annotated[Optional[str], typer.Option("--agent-model", help="Model for agent (default: VLM_MODEL env or gpt-5.5)")] = None,
    tips: Annotated[Optional[str], typer.Option("--tips", help="Extra tips appended to the agent prompt")] = None,
):
    """Remove background colors by making them transparent.

    Three modes:
      --seed only   sample color from seeds, flood fill (default: --seed corner)
      -c only       global color replace, no flood fill
      -c + --seed   explicit color + flood fill;
                    --seed match      uses exact-color pixels as seeds (tol=0)
                    --seed match:T    uses pixels within tolerance T of -c as seeds

    Examples:
      vibegame art rmbg image.png --where
      vibegame art rmbg image.png -t 20 -o out.png
      vibegame art rmbg image.png --seed tl --seed tr -t 15 -o out.png
      vibegame art rmbg image.png -c 255,255,255 -t 10 -o out.png
      vibegame art rmbg image.png -c 255,255,255 --seed match -t 20 -o out.png
      vibegame art rmbg image.png -c 255,0,255 --seed match:5 -t 40 --metric hsv -o out.png
      vibegame art rmbg image.png -c 255,255,255 --seed corner --seed match -t 20 -o out.png
    """
    if agent:
        from .rmbg_agent import run_rmbg_agent
        if not output:
            print("--agent requires -o/--output")
            raise typer.Exit(1)
        try:
            run_rmbg_agent(image, output, model=agent_model, tips=tips)
        except Exception as e:
            print(f"Agent error: {e}")
            raise typer.Exit(1)
        return

    if not where and output is None and not inplace:
        print("Must specify -o/--output, --inplace, or --where")
        raise typer.Exit(1)

    metric_lc = metric.strip().lower()
    if metric_lc not in ("rgb", "hsv", "cosine"):
        print(f"Error: --metric must be rgb|hsv|cosine, got: {metric!r}")
        raise typer.Exit(1)

    try:
        out_path = remove_bg(
            image_path=image,
            output_path=output,
            tolerance=tolerance,
            colors=color,
            seeds=seed,
            apply_regions=apply,
            protect_regions=protect,
            apply_shape=apply_shape,
            where=where,
            defringe=defringe,
            inplace=inplace,
            metric=metric_lc,
        )
        if where:
            print(f"Preview saved to: {out_path}")
            print("Magenta = affected, cyan cross = seed, green = apply, blue = protect")
        else:
            print(f"Done! Output: {out_path}")
    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(1)
