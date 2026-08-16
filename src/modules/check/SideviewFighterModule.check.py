"""
SideviewFighterModule node check + visual preview.

Called by `vibegame check` when it detects a node.json with script: SideviewFighterModule.

Generates preview images in assets/artifacts/module-check/:
  - <name>_idle_collider.png: idle sprite with collider overlay
  - <name>_<attack>_hitbox.png: attack frames with hitbox overlay
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw


def _load_manifest(project: Path) -> dict:
    for name in ["assets/manifest.json"]:
        p = project / name
        if p.exists():
            return json.loads(p.read_text())
    return {}


def _crop_frame(project: Path, manifest: dict, texture: str, frame: str) -> Image.Image | None:
    entry = manifest.get(texture)
    if not entry or "sprites" not in entry:
        return None
    sprite = entry["sprites"].get(frame)
    if not sprite:
        return None
    x, y, w, h = sprite["bbox"]
    img_path = project / "assets" / entry["path"]
    if not img_path.exists():
        return None
    img = Image.open(img_path).convert("RGBA")
    return img.crop((x, y, x + w, y + h))


def _clip_texture(clip: dict, default_texture: str) -> str:
    return clip.get("source", {}).get("texture", default_texture)


def _draw_box(draw: ImageDraw.ImageDraw, x, y, w, h, color, label=""):
    draw.rectangle([x, y, x + w, y + h], outline=color, width=2)
    if label:
        draw.text((x + 2, y + 2), label, fill=color)


def check_sideview_fighter(project: Path, node_path: Path, opts: dict | None = None) -> list[str]:
    """Validate a SideviewFighterModule node and generate preview images.

    opts merges on top of node.config.check. Supported keys:
      - preview_dir: Path | str — output directory for preview images (default: assets/artifacts/module-check)
      - preview: bool — generate preview images (default: True)
      - states: list[str] — only preview these attack states (default: all in config.attacks)
      - scale: float — override preview scale (default: from visual.ratio or visual.width/height)
    Returns list of error/warning/preview strings."""
    node = json.loads(node_path.read_text())
    manifest = _load_manifest(project)
    messages = []

    # Merge: node.config.check (defaults) <- opts (overrides)
    check_cfg = {**(node.get("config", {}).get("check", {})), **(opts or {})}

    config = node.get("config", {})
    animator = node.get("animator", {})
    animations = node.get("animations", {})
    clips = animations.get("clips", {})
    states = animator.get("states", {})
    params = animator.get("parameters", {})
    children = {c["name"]: c for c in node.get("children", []) if "name" in c}
    visual = node.get("visual", {})
    default_texture = visual.get("texture", "")
    node_name = node.get("name", node_path.stem)

    # --- Static checks ---
    if not animator:
        messages.append("ERROR: no animator defined")
    else:
        for s in ["idle", "walk"]:
            if s not in states:
                messages.append(f'ERROR: animator missing required state "{s}"')
        for p in ["moving", "grounded"]:
            if p not in params:
                messages.append(f'ERROR: animator missing required parameter "{p}"')
        for sname, sdef in states.items():
            clip_name = sdef.get("clip")
            if clip_name and clip_name not in clips:
                messages.append(f'ERROR: state "{sname}" clip "{clip_name}" not in animations.clips')

    if not node.get("collider"):
        messages.append("ERROR: no collider defined")

    attacks = config.get("attacks", {})
    for state_name, adef in attacks.items():
        hb = adef.get("hitbox", "")
        if hb not in children:
            messages.append(f'ERROR: attacks.{state_name}.hitbox "{hb}" child not found')
        if not adef.get("activeFrames"):
            messages.append(f"WARN: attacks.{state_name}.activeFrames is empty")

    for clip_name, clip_def in clips.items():
        tex = _clip_texture(clip_def, default_texture)
        if tex and tex not in manifest:
            messages.append(f'ERROR: clip "{clip_name}" texture "{tex}" not in manifest')

    # --- Visual preview ---
    if not check_cfg.get("preview", True):
        if not any(m.startswith("ERROR") for m in messages):
            messages.insert(0, "PASS: static check passed")
        return messages

    out_dir = Path(check_cfg.get("preview_dir", project / "assets" / "artifacts" / "module-check"))
    out_dir.mkdir(parents=True, exist_ok=True)
    preview_states = check_cfg.get("states")
    override_scale = check_cfg.get("scale")

    visual_ratio = visual.get("ratio")
    visual_w = visual.get("width")
    visual_h = visual.get("height")

    def _game_scale(src_w, src_h):
        """Scale factor used in-game (ratio or width/height)."""
        if visual_ratio:
            return float(visual_ratio)
        if visual_h:
            return float(visual_h) / src_h
        return 1.0

    # Preview renders at higher resolution for readability.
    # Default: render sprites at original size (scale=1). Override with --scale.
    preview_scale = float(override_scale) if override_scale else 1.0

    # Idle + collider
    idle_clip = clips.get("idle", {})
    idle_tex = _clip_texture(idle_clip, default_texture)
    idle_frames = idle_clip.get("frames", [])
    if idle_frames and idle_tex:
        first = _crop_frame(project, manifest, idle_tex, idle_frames[0])
        if first:
            sw, sh = first.size
            gs = _game_scale(sw, sh)
            dw, dh = int(sw * preview_scale), int(sh * preview_scale)
            # Collider dimensions in game pixels, scaled to preview
            collider = node.get("collider", {})
            col_w_game = collider.get("width") or (sw * gs)
            col_h_game = collider.get("height") or (sh * gs)
            col_ox_game = collider.get("offsetX", 0)
            col_oy_game = collider.get("offsetY", 0)
            # Collider pivot: explicit > visual pivot > default [0.5, 1]
            pivot = collider.get("pivot") or visual.get("pivot") or [0.5, 1]
            # Convert game-pixel collider to preview-pixel
            ratio = preview_scale / gs
            col_w = col_w_game * ratio
            col_h = col_h_game * ratio
            col_ox = col_ox_game * ratio
            col_oy = col_oy_game * ratio

            pad = 40
            cw, ch = int(dw + pad * 2), int(dh + pad * 2)
            canvas = Image.new("RGBA", (cw, ch), (30, 30, 30, 255))
            resized = first.resize((dw, dh), Image.LANCZOS)
            sx, sy = pad, pad
            canvas.paste(resized, (sx, sy), resized)

            draw = ImageDraw.Draw(canvas)
            # anchor = sprite origin (bottom-center for pivot [0.5,1])
            origin_x = sx + dw * 0.5
            origin_y = sy + dh
            # Collider rect: same formula as dashboard drawCollider
            cx = origin_x + col_ox - col_w * pivot[0]
            cy = origin_y + col_oy - col_h * pivot[1]

            _draw_box(draw, cx, cy, col_w, col_h, "#00FF00", "collider")
            draw.ellipse([origin_x - 4, origin_y - 4, origin_x + 4, origin_y + 4], fill="#FFFF00")
            draw.text((origin_x + 6, origin_y - 12), "origin", fill="#FFFF00")

            p = out_dir / f"{node_name}_idle_collider.png"
            canvas.save(p)
            messages.append(f"PREVIEW: {p.relative_to(project)}")

    # Attack frame strips
    for state_name, adef in attacks.items():
        if preview_states and state_name not in preview_states:
            continue
        clip_def = clips.get(state_name, {})
        tex = _clip_texture(clip_def, default_texture)
        frames = clip_def.get("frames", [])
        if not frames or not tex:
            continue

        active_set = set(adef.get("activeFrames", []))
        hb_child = children.get(adef.get("hitbox", ""), {})
        hb_col = hb_child.get("collider", {})
        hb_w_game = hb_col.get("width", 40)
        hb_h_game = hb_col.get("height", 40)
        hb_ox_game = hb_col.get("offsetX", 0)
        hb_oy_game = hb_col.get("offsetY", 0)

        imgs = []
        for fid in frames:
            img = _crop_frame(project, manifest, tex, fid)
            if img:
                imgs.append(img)

        if not imgs:
            continue

        sw0, sh0 = imgs[0].size
        gs = _game_scale(sw0, sh0)
        ratio = preview_scale / gs

        hb_w = hb_w_game * ratio
        hb_h = hb_h_game * ratio
        hb_ox = hb_ox_game * ratio
        hb_oy = hb_oy_game * ratio

        gap = 8
        cells = []
        max_h = 0
        max_w = 0
        for img in imgs:
            sw, sh = img.size
            dw, dh = int(sw * preview_scale), int(sh * preview_scale)
            max_h = max(max_h, dh)
            max_w = max(max_w, dw)
            cells.append((img, dw, dh))

        cell_w = max_w + int(hb_w)
        total_w = cell_w * len(cells) + gap * (len(cells) - 1) + 20
        total_h = int(max_h + hb_h + 60)
        canvas = Image.new("RGBA", (total_w, total_h), (30, 30, 30, 255))
        draw = ImageDraw.Draw(canvas)

        cx = 10
        for i, (img, dw, dh) in enumerate(cells):
            resized = img.resize((dw, dh), Image.LANCZOS)
            ground_y = total_h - 30
            sy = ground_y - dh
            # Center sprite within fixed-width cell
            sprite_x = cx + (cell_w - dw) // 2
            canvas.paste(resized, (sprite_x, sy), resized)

            is_active = i in active_set
            label_color = "#FF4444" if is_active else "#666666"
            draw.text((cx + cell_w // 2 - 10, total_h - 22), f"f{i:02d}", fill=label_color)

            if is_active:
                # Hitbox relative to cell center (= physicsObject origin, fixed for all frames)
                cell_center_x = cx + cell_w * 0.5
                hb_pivot = hb_col.get("pivot", [0.5, 0.5])
                hx = cell_center_x + hb_ox - hb_w * hb_pivot[0]
                hy = ground_y + hb_oy - hb_h * hb_pivot[1]
                _draw_box(draw, hx, hy, hb_w, hb_h, "#FF4444", adef.get("hitbox", ""))
            cx += cell_w + gap

        p = out_dir / f"{node_name}_{state_name}_hitbox.png"
        canvas.save(p)
        messages.append(f"PREVIEW: {p.relative_to(project)}")

    if not any(m.startswith("ERROR") for m in messages):
        messages.insert(0, "PASS: static check passed")

    return messages


def check_sideview_fighter_anim(project: Path, node_path: Path, opts: dict) -> list[str]:
    """--anim mode: frame strip with hitbox overlay on active frames."""
    node = json.loads(node_path.read_text())
    manifest = _load_manifest(project)
    messages = []

    anim_name = opts.get("anim", "")
    visual = node.get("visual", {})
    config = node.get("config", {})
    animations = node.get("animations", {})
    clips = animations.get("clips", {})
    clip = clips.get(anim_name)
    node_name = node.get("name", node_path.stem)
    children = {c["name"]: c for c in node.get("children", []) if "name" in c}

    if not clip:
        available = ", ".join(clips.keys()) if clips else "(none)"
        messages.append(f'ERROR: clip "{anim_name}" not found. Available: {available}')
        return messages

    default_texture = visual.get("texture", "")
    tex = _clip_texture(clip, default_texture)
    frames = clip.get("frames", [])
    if not frames:
        messages.append(f'ERROR: clip "{anim_name}" has no frames')
        return messages

    override_scale = opts.get("scale")
    out_path = opts.get("o")

    # Find attack def for this anim (if any)
    attacks = config.get("attacks", {})
    attack_def = attacks.get(anim_name)

    # Load frames
    imgs = []
    for fid in frames:
        img = _crop_frame(project, manifest, tex, fid)
        if img:
            imgs.append(img)

    if not imgs:
        messages.append("ERROR: no frames could be loaded")
        return messages

    sw0, sh0 = imgs[0].size
    gs = _game_scale(sw0, sh0) if visual else 1.0
    preview_scale = float(override_scale) if override_scale else 1.0
    ratio = preview_scale / gs if gs > 0 else 1.0

    # Hitbox info
    hb_w = hb_h = hb_ox = hb_oy = 0
    hb_col = {}
    active_set = set()
    if attack_def:
        active_set = set(attack_def.get("activeFrames", []))
        hb_child = children.get(attack_def.get("hitbox", ""), {})
        hb_col = hb_child.get("collider", {})
        hb_w = (hb_col.get("width") or 32) * ratio
        hb_h = (hb_col.get("height") or 32) * ratio
        hb_ox = hb_col.get("offsetX", 0) * ratio
        hb_oy = hb_col.get("offsetY", 0) * ratio

    # Build strip
    gap = 8
    cells = []
    max_h = 0
    max_w = 0
    for img in imgs:
        sw, sh = img.size
        dw, dh = int(sw * preview_scale), int(sh * preview_scale)
        max_h = max(max_h, dh)
        max_w = max(max_w, dw)
        cells.append((img, dw, dh))

    cell_w = max_w + (int(hb_w) if attack_def else 0)
    total_w = cell_w * len(cells) + gap * (len(cells) - 1) + 20
    total_h = int(max_h + (hb_h if attack_def else 0) + 40)
    canvas = Image.new("RGBA", (total_w, total_h), (30, 30, 30, 255))
    draw = ImageDraw.Draw(canvas)

    cx = 10
    ground_y = total_h - 20
    for i, (img, dw, dh) in enumerate(cells):
        resized = img.resize((dw, dh), Image.LANCZOS)
        sy = ground_y - dh
        sprite_x = cx + (cell_w - dw) // 2
        canvas.paste(resized, (sprite_x, sy), resized)

        is_active = i in active_set
        label_color = "#FF4444" if is_active else "#AAAAAA"
        draw.text((cx + cell_w // 2 - 10, total_h - 16), f"f{i:02d}", fill=label_color)

        if is_active and attack_def:
            cell_center_x = cx + cell_w * 0.5
            hb_pivot = hb_col.get("pivot", [0.5, 0.5])
            hx = cell_center_x + hb_ox - hb_w * hb_pivot[0]
            hy = ground_y + hb_oy - hb_h * hb_pivot[1]
            _draw_box(draw, hx, hy, hb_w, hb_h, "#FF4444", attack_def.get("hitbox", ""))

        cx += cell_w + gap

    if out_path:
        save_path = Path(out_path)
    else:
        out_dir = Path(opts.get("preview_dir", project / "assets" / "artifacts" / "module-check"))
        out_dir.mkdir(parents=True, exist_ok=True)
        save_path = out_dir / f"{node_name}_{anim_name}.png"

    canvas.save(save_path)
    messages.append(f"PREVIEW: {save_path}")
    messages.insert(0, "PASS: anim check complete")
    return messages


def _game_scale(sw, sh):
    """Placeholder — actual visual def needed. Called from anim check."""
    return 1.0


def check(project: Path, node_path: Path, opts: dict | None = None) -> list[str]:
    """Unified entry point. Routes to anim or full check."""
    opts = opts or {}
    if opts.get("anim"):
        # Need visual info for game_scale — patch _game_scale with real data
        node = json.loads(node_path.read_text())
        visual = node.get("visual", {})
        global _game_scale
        def _game_scale(sw, sh):
            r = visual.get("ratio")
            if r: return float(r)
            h = visual.get("height")
            if h: return float(h) / sh
            return 1.0
        return check_sideview_fighter_anim(project, node_path, opts)
    return check_sideview_fighter(project, node_path, opts)


USAGE = """SideviewFighterModule check

Usage: vibegame check <node.json> [options]

Options:
  --anim=clip_name           Show animation frame sequence (with hitbox on attack clips)
  --states=attack1,attack2   Only preview these attack states (default: all)
  --scale=2.0                Preview render scale (default: 1.0)
  --preview=false            Skip preview image generation
  -o, --preview_dir=path     Output directory
"""
