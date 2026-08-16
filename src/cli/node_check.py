"""
Generic node.json visual check.

Draws initial frame + collider + children on a single preview image.
Used by `vibegame check xxx.node.json` when no module-specific .check.py exists.

Inheritance rules (from ColliderFactory.js):
  collider.pivot  = explicit || visual.origin (sourceGameObject) || [0.5, 0.5]
  collider.width  = explicit || visual.displayWidth
  collider.height = explicit || visual.displayHeight
  child.collider.pivot = explicit || [0.5, 0.5]  (no parent inheritance)
  child.collider.width = explicit || 32
  child.collider.height = explicit || 32
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw


def _load_manifest(project: Path) -> dict:
    p = project / "assets" / "manifest.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _crop_frame(project: Path, manifest: dict, texture: str, frame: str | None) -> Image.Image | None:
    entry = manifest.get(texture)
    if not entry:
        return None
    img_path = project / "assets" / entry["path"]
    if not img_path.exists():
        return None
    img = Image.open(img_path).convert("RGBA")
    if frame and "sprites" in entry:
        sprite = entry["sprites"].get(frame)
        if not sprite:
            return None
        x, y, w, h = sprite["bbox"]
        return img.crop((x, y, x + w, y + h))
    if entry.get("type") == "image":
        return img
    if "sprites" in entry:
        first = next(iter(entry["sprites"].values()), None)
        if first:
            x, y, w, h = first["bbox"]
            return img.crop((x, y, x + w, y + h))
    return img


def _visual_display_size(visual: dict, source_w: int, source_h: int) -> tuple[float, float]:
    """Compute game-pixel display size from visual def."""
    ratio = visual.get("ratio")
    if ratio:
        return source_w * float(ratio), source_h * float(ratio)
    w = visual.get("width")
    h = visual.get("height")
    if w and h:
        return float(w), float(h)
    if h:
        scale = float(h) / source_h
        return source_w * scale, float(h)
    if w:
        scale = float(w) / source_w
        return float(w), source_h * scale
    return float(source_w), float(source_h)


def _resolve_collider_pivot(collider: dict, visual: dict) -> list[float]:
    """Resolve collider pivot with inheritance: explicit > visual > [0.5, 0.5]."""
    p = collider.get("pivot")
    if p and len(p) == 2:
        return [float(p[0]), float(p[1])]
    vp = visual.get("pivot")
    if vp and len(vp) == 2:
        return [float(vp[0]), float(vp[1])]
    # Default: [0.5, 1] for box colliders (bottom-center, matching default sprite origin)
    return [0.5, 1]


def _draw_box(draw: ImageDraw.ImageDraw, x, y, w, h, color, label=""):
    draw.rectangle([x, y, x + w, y + h], outline=color, width=2)
    if label:
        draw.text((x + 3, y + 3), label, fill=color)


def check_node_generic(project: Path, node_path: Path, opts: dict | None = None) -> list[str]:
    """Generic node check: visual + collider + children preview."""
    node = json.loads(node_path.read_text())
    manifest = _load_manifest(project)
    opts = opts or {}
    messages = []

    visual = node.get("visual", {})
    collider = node.get("collider", {})
    children = node.get("children", [])
    node_name = node.get("name", node_path.stem)
    override_scale = opts.get("scale")
    out_path = opts.get("o")

    # Need at least visual or collider to draw anything
    if not visual and not collider:
        messages.append("WARN: node has no visual and no collider, nothing to preview")
        return messages

    # Load visual frame
    texture = visual.get("texture", "")
    frame = visual.get("frame")
    sprite_img = _crop_frame(project, manifest, texture, frame) if texture else None

    if not sprite_img and not collider:
        messages.append("WARN: could not load visual texture, nothing to preview")
        return messages

    # Source dimensions
    src_w = sprite_img.size[0] if sprite_img else 32
    src_h = sprite_img.size[1] if sprite_img else 32

    # Game scale (ratio or width/height)
    disp_w, disp_h = _visual_display_size(visual, src_w, src_h) if visual else (32.0, 32.0)
    game_scale = disp_w / src_w if src_w > 0 else 1.0

    # Preview renders at source resolution by default
    preview_scale = float(override_scale) if override_scale else 1.0
    ratio = preview_scale / game_scale if game_scale > 0 else 1.0

    # Canvas
    pw = int(src_w * preview_scale)
    ph = int(src_h * preview_scale)

    # Account for children colliders extending beyond visual
    extra_right = 0
    extra_up = 0
    for child in children:
        cc = child.get("collider", {})
        if not cc:
            continue
        cw = (cc.get("width") or 32) * ratio
        ch = (cc.get("height") or 32) * ratio
        cox = cc.get("offsetX", 0) * ratio
        coy = cc.get("offsetY", 0) * ratio
        extra_right = max(extra_right, cox + cw)
        extra_up = max(extra_up, -(coy - ch))

    pad = 50
    canvas_w = int(pw + extra_right + pad * 2)
    canvas_h = int(ph + extra_up + pad * 2)
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (30, 30, 30, 255))
    draw = ImageDraw.Draw(canvas)

    # Sprite position (bottom-center aligned)
    sx = pad + int(extra_right * 0.3)
    sy = pad + int(extra_up)

    # Draw visual
    if sprite_img:
        resized = sprite_img.resize((pw, ph), Image.LANCZOS)
        canvas.paste(resized, (sx, sy), resized)

    # Origin point (visual pivot, default [0.5, 1])
    vis_pivot = visual.get("pivot") or [0.5, 1]
    origin_x = sx + pw * vis_pivot[0]
    origin_y = sy + ph * vis_pivot[1]

    # Draw origin
    draw.ellipse([origin_x - 4, origin_y - 4, origin_x + 4, origin_y + 4], fill="#FFFF00")
    draw.text((origin_x + 6, origin_y - 12), "origin", fill="#FFFF00")

    # Draw collider (green)
    if collider:
        cpivot = _resolve_collider_pivot(collider, visual)
        cw_game = collider.get("width") or disp_w
        ch_game = collider.get("height") or disp_h
        cox_game = collider.get("offsetX", 0)
        coy_game = collider.get("offsetY", 0)

        cw = cw_game * ratio
        ch = ch_game * ratio
        cox = cox_game * ratio
        coy = coy_game * ratio

        cx = origin_x + cox - cw * cpivot[0]
        cy = origin_y + coy - ch * cpivot[1]
        _draw_box(draw, cx, cy, cw, ch, "#00FF00", "collider")

    # Draw children
    for child in children:
        child_name = child.get("name", "?")
        child_visual = child.get("visual", {})
        child_collider = child.get("collider", {})

        # Child visual (semi-transparent)
        if child_visual and child_visual.get("texture"):
            child_tex = child_visual.get("texture", "")
            child_frame = child_visual.get("frame")
            child_img = _crop_frame(project, manifest, child_tex, child_frame)
            if child_img:
                child_sw, child_sh = child_img.size
                child_disp_w, child_disp_h = _visual_display_size(child_visual, child_sw, child_sh)
                child_ratio = preview_scale / (child_disp_w / child_sw) if child_sw > 0 else 1.0
                child_pw = int(child_sw * preview_scale)
                child_ph = int(child_sh * preview_scale)
                child_resized = child_img.resize((child_pw, child_ph), Image.LANCZOS)
                # Make semi-transparent
                alpha = child_resized.split()[3]
                alpha = alpha.point(lambda p: int(p * 0.5))
                child_resized.putalpha(alpha)
                # Position: child follows parent origin
                child_x = int(origin_x - child_pw * 0.5)
                child_y = int(origin_y - child_ph)
                canvas.paste(child_resized, (child_x, child_y), child_resized)

        # Child collider (yellow)
        if child_collider:
            cc_pivot = [0.5, 0.5]  # children default pivot
            if child_collider.get("pivot"):
                cc_pivot = [float(x) for x in child_collider["pivot"]]
            cc_w = (child_collider.get("width") or 32) * ratio
            cc_h = (child_collider.get("height") or 32) * ratio
            cc_ox = child_collider.get("offsetX", 0) * ratio
            cc_oy = child_collider.get("offsetY", 0) * ratio

            cc_x = origin_x + cc_ox - cc_w * cc_pivot[0]
            cc_y = origin_y + cc_oy - cc_h * cc_pivot[1]
            _draw_box(draw, cc_x, cc_y, cc_w, cc_h, "#FFD166", child_name)

    # Save
    if out_path:
        save_path = Path(out_path)
    else:
        out_dir = project / "assets" / "artifacts" / "node-check"
        out_dir.mkdir(parents=True, exist_ok=True)
        save_path = out_dir / f"{node_name}.png"

    canvas.save(save_path)
    messages.append(f"PREVIEW: {save_path}")
    messages.insert(0, "PASS: node check complete")
    return messages


def check_node_anim(project: Path, node_path: Path, opts: dict | None = None) -> list[str]:
    """Extract animation frame sequence as horizontal strip."""
    node = json.loads(node_path.read_text())
    manifest = _load_manifest(project)
    opts = opts or {}
    messages = []

    anim_name = opts.get("anim", "")
    if not anim_name:
        messages.append("ERROR: --anim requires a clip name")
        return messages

    animations = node.get("animations", {})
    clips = animations.get("clips", {})
    clip = clips.get(anim_name)
    if not clip:
        available = ", ".join(clips.keys()) if clips else "(none)"
        messages.append(f'ERROR: clip "{anim_name}" not found. Available: {available}')
        return messages

    visual = node.get("visual", {})
    default_texture = visual.get("texture", "")
    node_name = node.get("name", node_path.stem)
    override_scale = opts.get("scale")
    out_path = opts.get("o")

    tex = clip.get("source", {}).get("texture", default_texture)
    frames = clip.get("frames", [])
    if not frames:
        messages.append(f'ERROR: clip "{anim_name}" has no frames')
        return messages

    # --child: overlay a child's visual/collider on each frame
    child_name = opts.get("child")
    children = {c["name"]: c for c in node.get("children", []) if "name" in c}
    child_def = None
    if child_name:
        child_def = children.get(child_name)
        if not child_def:
            available = ", ".join(children.keys()) if children else "(none)"
            messages.append(f'ERROR: child "{child_name}" not found. Available: {available}')
            return messages

    # Load all frame images
    imgs = []
    for fid in frames:
        img = _crop_frame(project, manifest, tex, fid)
        if img:
            imgs.append((fid, img))
        else:
            messages.append(f'WARN: frame "{fid}" from texture "{tex}" could not be loaded')

    if not imgs:
        messages.append("ERROR: no frames could be loaded")
        return messages

    # Scale
    src_w0, src_h0 = imgs[0][1].size
    preview_scale = float(override_scale) if override_scale else 1.0

    # Game scale for coordinate conversion
    disp_w, disp_h = _visual_display_size(visual, src_w0, src_h0) if visual else (float(src_w0), float(src_h0))
    game_scale = disp_w / src_w0 if src_w0 > 0 else 1.0
    ratio = preview_scale / game_scale if game_scale > 0 else 1.0

    # Child collider/visual info
    cc_w = cc_h = cc_ox = cc_oy = 0
    cc_pivot = [0.5, 0.5]
    child_visual_img = None
    if child_def:
        cc = child_def.get("collider", {})
        if cc:
            cc_w = (cc.get("width") or 32) * ratio
            cc_h = (cc.get("height") or 32) * ratio
            cc_ox = cc.get("offsetX", 0) * ratio
            cc_oy = cc.get("offsetY", 0) * ratio
            if cc.get("pivot"):
                cc_pivot = [float(x) for x in cc["pivot"]]
        cv = child_def.get("visual", {})
        if cv and cv.get("texture"):
            child_visual_img = _crop_frame(project, manifest, cv.get("texture", ""), cv.get("frame"))

    # Build strip: fixed cell width, bottom-aligned
    gap = 8
    cells = []
    max_h = 0
    max_w = 0
    for fid, img in imgs:
        sw, sh = img.size
        dw, dh = int(sw * preview_scale), int(sh * preview_scale)
        max_h = max(max_h, dh)
        max_w = max(max_w, dw)
        cells.append((fid, img, dw, dh))

    cell_w = max_w
    total_h = int(max_h + 40)
    total_w = cell_w * len(cells) + gap * (len(cells) - 1) + 20
    canvas = Image.new("RGBA", (total_w, total_h), (30, 30, 30, 255))
    draw = ImageDraw.Draw(canvas)

    cx = 10
    ground_y = total_h - 20
    for i, (fid, img, dw, dh) in enumerate(cells):
        resized = img.resize((dw, dh), Image.LANCZOS)
        sy = ground_y - dh
        sprite_x = cx + (cell_w - dw) // 2
        canvas.paste(resized, (sprite_x, sy), resized)
        draw.text((cx + cell_w // 2 - 10, total_h - 16), fid, fill="#AAAAAA")

        if child_def:
            cell_center_x = cx + cell_w * 0.5

            # Child visual (semi-transparent)
            if child_visual_img:
                csv, csh = child_visual_img.size
                cpw, cph = int(csv * preview_scale), int(csh * preview_scale)
                child_resized = child_visual_img.resize((cpw, cph), Image.LANCZOS)
                alpha = child_resized.split()[3]
                alpha = alpha.point(lambda p: int(p * 0.4))
                child_resized.putalpha(alpha)
                child_x = int(cell_center_x - cpw * 0.5)
                child_y = ground_y - cph
                canvas.paste(child_resized, (child_x, child_y), child_resized)

            # Child collider (yellow)
            if cc_w > 0 and cc_h > 0:
                hx = cell_center_x + cc_ox - cc_w * cc_pivot[0]
                hy = ground_y + cc_oy - cc_h * cc_pivot[1]
                _draw_box(draw, hx, hy, cc_w, cc_h, "#FFD166", child_name)

        cx += cell_w + gap

    # Save
    if out_path:
        save_path = Path(out_path)
    else:
        out_dir = project / "assets" / "artifacts" / "node-check"
        out_dir.mkdir(parents=True, exist_ok=True)
        suffix = f"_{child_name}" if child_name else ""
        save_path = out_dir / f"{node_name}_{anim_name}{suffix}.png"

    canvas.save(save_path)
    messages.append(f"PREVIEW: {save_path}")
    messages.insert(0, "PASS: anim check complete")
    return messages


USAGE = """Generic node check

Usage: vibegame check <node.json> [options]

Options:
  --anim=clip_name        Show animation frame sequence
  --child=child_name      Overlay child's visual/collider on --anim frames
  --scale=2.0             Preview render scale (default: 1.0)
  -o path                 Output image path
  --info                  Show this help
"""
