"""
Sprite cutting and action collation tools.

Usage:
    vibegame art cut <image>
    vibegame art cut <image> -o output_dir
    vibegame art collate <img1> <img2> -o output_dir
"""

import cv2
import json
import numpy as np
import os
import tempfile
from pathlib import Path
from typing import List, Tuple, Optional, Annotated, Literal
import shutil

import typer

app = typer.Typer(name="cut", help="Sprite cutting and collation", add_completion=False, rich_markup_mode=None, pretty_exceptions_enable=False)


# ============ Config ============


class CutConfig:
    MIN_AREA = 5000
    ALPHA_THRESHOLD = 10
    NAME_ORDER = "row"
    TIGHT = None
    CROP_EDGE = None


# ============ Manifest Helpers ============


def _load_manifest(manifest_path: Path) -> dict:
    """Load per-folder manifest.json. Missing file yields {} (first write);
    an unreadable or malformed file raises — returning {} there would let the
    caller write back an empty manifest and wipe every existing entry."""
    if not manifest_path.exists():
        return {}
    text = manifest_path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed manifest {manifest_path}: {e}") from e
    if not isinstance(data, dict):
        raise ValueError(
            f"Malformed manifest {manifest_path}: top level must be an object, "
            f"got {type(data).__name__}"
        )
    return data


def _save_manifest(manifest_path: Path, data: dict) -> None:
    """Write manifest.json atomically (temp file in the same dir + os.replace)."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(manifest_path.parent), prefix=manifest_path.name, suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp_name, manifest_path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


# ============ SpriteCutter ============


class SpriteCutter:
    """Sprite sheet cutter - detects and cuts individual sprites."""

    def __init__(
        self,
        min_area: int = CutConfig.MIN_AREA,
        alpha_threshold: int = CutConfig.ALPHA_THRESHOLD,
        name_order: str = CutConfig.NAME_ORDER,
        tight: Optional[int] = CutConfig.TIGHT,
        crop_edge: Optional[int] = CutConfig.CROP_EDGE,
    ):
        self.default_min_area = min_area
        self.alpha_threshold = alpha_threshold
        self.name_order = name_order
        self.tight = tight
        self.crop_edge = crop_edge

    def _create_mask(self, image: np.ndarray) -> np.ndarray:
        if image.shape[2] == 4:
            alpha = image[:, :, 3]
            return (alpha > self.alpha_threshold).astype(np.uint8) * 255
        else:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            _, mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
            kernel = np.ones((3, 3), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            return cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    def _find_sprites(
        self, mask: np.ndarray, image: np.ndarray, min_area: int
    ) -> List[Tuple[int, int, int, int]]:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        bboxes = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w * h < min_area:
                continue
            bboxes.append((x, y, w, h))
        return self._sort_bboxes(bboxes, self.name_order)

    def _sort_bboxes(
        self, bboxes: List[Tuple[int, int, int, int]], order: str = "row"
    ) -> List[Tuple[int, int, int, int]]:
        if not bboxes:
            return bboxes

        centers = [(x + w / 2, y + h / 2, x, y, w, h) for x, y, w, h in bboxes]

        if order == "column":
            centers_sorted_by_x = sorted(centers, key=lambda c: c[0])
            avg_width = sum(w for _, _, _, _, w, _ in centers) / len(centers)
            col_threshold = avg_width * 0.6

            cols = []
            current_col = [centers_sorted_by_x[0]]
            for center in centers_sorted_by_x[1:]:
                if abs(center[0] - current_col[-1][0]) < col_threshold:
                    current_col.append(center)
                else:
                    cols.append(current_col)
                    current_col = [center]
            if current_col:
                cols.append(current_col)

            sorted_bboxes = []
            for col in cols:
                col_sorted = sorted(col, key=lambda c: c[1])
                sorted_bboxes.extend([(c[2], c[3], c[4], c[5]) for c in col_sorted])
        else:
            centers_sorted_by_y = sorted(centers, key=lambda c: c[1])
            avg_height = sum(h for _, _, _, _, _, h in centers) / len(centers)
            row_threshold = avg_height * 0.6

            rows = []
            current_row = [centers_sorted_by_y[0]]
            for center in centers_sorted_by_y[1:]:
                if abs(center[1] - current_row[-1][1]) < row_threshold:
                    current_row.append(center)
                else:
                    rows.append(current_row)
                    current_row = [center]
            if current_row:
                rows.append(current_row)

            sorted_bboxes = []
            for row in rows:
                row_sorted = sorted(row, key=lambda c: c[0])
                sorted_bboxes.extend([(c[2], c[3], c[4], c[5]) for c in row_sorted])

        return sorted_bboxes

    def _tight_crop(self, sprite: np.ndarray, threshold: int) -> np.ndarray:
        """Trim rows/cols where max alpha < threshold."""
        if len(sprite.shape) < 3 or sprite.shape[2] != 4:
            return sprite
        alpha = sprite[:, :, 3]
        h, w = alpha.shape

        top = 0
        while top < h and alpha[top, :].max() < threshold:
            top += 1
        bottom = h
        while bottom > top and alpha[bottom - 1, :].max() < threshold:
            bottom -= 1
        left = 0
        while left < w and alpha[:, left].max() < threshold:
            left += 1
        right = w
        while right > left and alpha[:, right - 1].max() < threshold:
            right -= 1

        if top >= bottom or left >= right:
            return sprite
        return sprite[top:bottom, left:right]

    def cut(
        self,
        image_path: str,
        min_area: Optional[int] = None,
    ) -> List[np.ndarray]:
        """Cut sprites, return list without saving."""
        image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if image is None:
            raise ValueError(f"Cannot read image: {image_path}")

        min_area = min_area if min_area is not None else self.default_min_area

        mask = self._create_mask(image)
        bboxes = self._find_sprites(mask, image, min_area)
        sprites = [image[y:y + h, x:x + w] for x, y, w, h in bboxes]

        if self.tight is not None and sprites:
            sprites = [self._tight_crop(s, self.tight) for s in sprites]

        if self.crop_edge is not None and self.crop_edge > 0 and sprites:
            n = self.crop_edge
            for i, s in enumerate(sprites):
                if s.shape[0] <= 2 * n or s.shape[1] <= 2 * n:
                    raise ValueError(
                        f"crop_edge={n} too large: sprite #{i} is {s.shape[1]}x{s.shape[0]}"
                    )
            sprites = [s[n:-n, n:-n] for s in sprites]

        return sprites

    def cut_and_save(
        self,
        image_path: str,
        output_path: Optional[str] = None,
        prefix: Optional[str] = None,
        min_area: Optional[int] = None,
    ) -> List[Path]:
        """Cut and save all sprites."""
        sprites = self.cut(
            image_path,
            min_area=min_area,
        )

        if not sprites:
            raise ValueError(f"No sprites detected: {image_path}")

        if prefix is None:
            prefix = Path(image_path).stem

        if not output_path:
            base_dir = Path(image_path).parent / "cut"
        else:
            base_dir = Path(output_path)
        output_dir = base_dir / Path(image_path).stem

        if output_dir.exists():
            print(f"WARNING: Overwriting existing directory: {output_dir.absolute()}")
            shutil.rmtree(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)

        saved_files = []
        for idx, sprite in enumerate(sprites):
            output_file = output_dir / f"{prefix}_c{idx}.png"
            cv2.imwrite(str(output_file), sprite)
            saved_files.append(output_file)

        return saved_files

    def preview(
        self,
        image_path: str,
        min_area: Optional[int] = None,
    ) -> np.ndarray:
        image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if image is None:
            raise ValueError(f"Cannot read image: {image_path}")

        min_area = min_area if min_area is not None else self.default_min_area

        mask = self._create_mask(image)
        bboxes = self._find_sprites(mask, image, min_area)

        preview = image.copy()

        for idx, (x, y, w, h) in enumerate(bboxes, 1):
            color = (0, 255, 0, 255) if preview.shape[2] == 4 else (0, 255, 0)
            cv2.rectangle(preview, (x, y), (x + w, y + h), color, 2)
            cv2.putText(preview, str(idx), (x + 5, y + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        return preview

    def label(
        self,
        image_path: str,
        output_path: Optional[str] = None,
        prefix: Optional[str] = None,
        min_area: Optional[int] = None,
    ) -> Path:
        """Extract sprite positions, write manifest.json."""
        image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if image is None:
            raise ValueError(f"Cannot read image: {image_path}")

        min_area = min_area if min_area is not None else self.default_min_area

        mask = self._create_mask(image)
        bboxes = self._find_sprites(mask, image, min_area)

        if prefix is None:
            prefix = Path(image_path).stem

        sprites = {}
        for idx, (x, y, w, h) in enumerate(bboxes):
            name = f"{prefix}_c{idx}"
            sprites[name] = {"bbox": [x, y, w, h]}

        img_path = Path(image_path)
        manifest_path = img_path.parent / "manifest.json"
        manifest = _load_manifest(manifest_path)
        manifest[prefix] = {
            "type": "atlas",
            "path": img_path.name,
            "sprites": sprites,
        }
        _save_manifest(manifest_path, manifest)
        return manifest_path

    def save_preview(self, image_path: str, save_path: str, **kwargs) -> Path:
        preview_img = self.preview(image_path, **kwargs)
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(save_path), preview_img)
        return save_path

    def __call__(self, *args, **kwargs):
        return self.cut_and_save(*args, **kwargs)


# ============ SpriteActionCollator ============


class SpriteActionCollator:
    """Collate multiple action frame sequences with unified scaling."""

    def __init__(
        self,
        min_area: int = CutConfig.MIN_AREA,
    ):
        self.cutter = SpriteCutter(min_area=min_area)

    def collate(
        self,
        image_paths: List[str],
        output_path: str,
        min_area: Optional[int] = None,
    ) -> List[Path]:
        if not image_paths:
            raise ValueError("Image path list cannot be empty")

        output_dir = Path(output_path)
        if output_dir.exists():
            print(f"WARNING: Overwriting existing directory: {output_dir.absolute()}")
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        all_sprites = []
        for img_path in image_paths:
            sprites = self.cutter.cut(img_path, min_area=min_area)
            if not sprites:
                raise ValueError(f"No sprites detected: {img_path}")
            all_sprites.append(sprites)

        idle_images = [sprites[0] for sprites in all_sprites]
        idle_areas = [img.shape[0] * img.shape[1] for img in idle_images]
        base_idx = idle_areas.index(min(idle_areas))
        base_image = idle_images[base_idx]
        base_h, base_w = base_image.shape[:2]

        print(f"Base image: #{base_idx}, size: {base_w}x{base_h}")

        scaled_sprites = []
        for idx, sprites in enumerate(all_sprites):
            idle_img = sprites[0]
            idle_h, idle_w = idle_img.shape[:2]
            scale = min(base_w / idle_w, base_h / idle_h)
            print(f"Image #{idx}: idle {idle_w}x{idle_h}, scale: {scale:.3f}")

            for sprite in sprites:
                h, w = sprite.shape[:2]
                new_w = int(w * scale)
                new_h = int(h * scale)
                if new_w > 0 and new_h > 0:
                    scaled = cv2.resize(sprite, (new_w, new_h), interpolation=cv2.INTER_AREA)
                    scaled_sprites.append(scaled)

        saved_files = []
        for idx, sprite in enumerate(scaled_sprites):
            output_file = output_dir / f"{idx}.png"
            cv2.imwrite(str(output_file), sprite)
            saved_files.append(output_file)

        print(f"Done! {len(saved_files)} frames saved to: {output_dir}")
        return saved_files


# ============ CLI Commands ============


@app.command("cut")
def cmd_cut(
    image: Annotated[str, typer.Argument(help="Input image path")],
    output: Annotated[Optional[str], typer.Option("-o", "--output", help="Output directory")] = None,
    prefix: Annotated[Optional[str], typer.Option("--prefix", help="Output filename prefix")] = None,
    min_area: Annotated[int, typer.Option("-m", "--min-area", help="Minimum sprite area")] = CutConfig.MIN_AREA,
    alpha_threshold: Annotated[int, typer.Option("--alpha-threshold", help="Alpha threshold for transparency")] = CutConfig.ALPHA_THRESHOLD,
    name_order: Annotated[str, typer.Option("--name-order", help="Numbering order: row / column")] = CutConfig.NAME_ORDER,
    tight: Annotated[Optional[int], typer.Option("--tight", help="Tight crop alpha threshold")] = CutConfig.TIGHT,
    crop_edge: Annotated[Optional[int], typer.Option("--crop-edge", help="Force-trim N pixels from each edge")] = CutConfig.CROP_EDGE,
    label: Annotated[bool, typer.Option("--label", help="Only extract positions, write manifest.json")] = False,
    save_preview: Annotated[Optional[str], typer.Option("--save-preview", help="Save preview image to path")] = None,
    preview: Annotated[bool, typer.Option("--preview", help="Show preview without saving")] = False,
    agent: Annotated[bool, typer.Option("--agent", help="Use mini-agent for automatic sprite detection")] = False,
    agent_model: Annotated[Optional[str], typer.Option("--agent-model", help="Model for agent (default: VLM_MODEL env or gpt-5.5)")] = None,
    tips: Annotated[Optional[str], typer.Option("--tips", help="Extra tips appended to the agent prompt")] = None,
    frames: Annotated[Optional[int], typer.Option("--frames", help="Expected frame count for agent (omit to auto-detect)")] = None,
    bg_color: Annotated[str, typer.Option("--bg-color", help="Background color for preview/LLM: white, black, green, or R,G,B")] = "white",
):
    """Cut sprites from a spritesheet."""
    if agent:
        from .cut_agent import run_cut_agent
        out = output or (str(Path(image).with_suffix(".bboxes.json")))
        try:
            bg_map = {"white": (255, 255, 255), "black": (0, 0, 0), "green": (0, 255, 0), "gray": (128, 128, 128)}
            if bg_color in bg_map:
                bg_bgr = bg_map[bg_color]
            else:
                parts = [int(x.strip()) for x in bg_color.split(",")]
                bg_bgr = (parts[2], parts[1], parts[0])  # RGB -> BGR
            result = run_cut_agent(image, out, model=agent_model, save_preview=save_preview is not None or preview, expected_frames=frames, bg_color=bg_bgr, tips=tips)
            if result.status == "fail":
                print(f"Agent FAIL: {result.reason}")
                Path(out).parent.mkdir(parents=True, exist_ok=True)
                Path(out).write_text(json.dumps({"_meta": {"status": "fail", "session": result.session_id, "reason": result.reason}}, ensure_ascii=False, indent=2))
                raise typer.Exit(2)
        except RuntimeError as e:
            print(f"Agent error: {e}")
            raise typer.Exit(1)
        return

    cutter = SpriteCutter(
        min_area=min_area,
        alpha_threshold=alpha_threshold, name_order=name_order,
        tight=tight, crop_edge=crop_edge,
    )

    if save_preview is not None:
        save_path = cutter.save_preview(image, save_preview)
        print("=== Preview Saved ===")
        print(f"Path: {save_path}")
    elif preview:
        preview_img = cutter.preview(image)
        if preview_img.shape[2] == 4:
            alpha = preview_img[:, :, 3:4] / 255.0
            bgr = preview_img[:, :, :3]
            white = np.full_like(bgr, 255)
            display_img = (bgr * alpha + white * (1 - alpha)).astype(np.uint8)
        else:
            display_img = preview_img
        cv2.imshow("Preview - Press any key to close", display_img)
        print("Press any key to close preview...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    elif label:
        meta_path = cutter.label(image, output_path=output, prefix=prefix)
        print("=== Label Result ===")
        print(f"Done! Saved to: {meta_path}")
    else:
        print("Cutting sprites...")
        saved_files = cutter.cut_and_save(
            image, output_path=output, prefix=prefix
            )

        output_dir = saved_files[0].parent if saved_files else "N/A"
        print("=== Cut Result ===")
        print(f"Done! Cut {len(saved_files)} sprites")
        print(f"Saved to: {output_dir}")


@app.command("collate")
def cmd_collate(
    images: Annotated[List[str], typer.Argument(help="Input image path list")],
    output: Annotated[str, typer.Option("-o", "--output", help="Output directory path")],
    min_area: Annotated[int, typer.Option("-m", "--min-area", help="Minimum sprite area")] = CutConfig.MIN_AREA,
):
    """Collate multiple action sequence images with unified scaling."""
    collator = SpriteActionCollator(min_area=min_area)

    try:
        print("Collating action sequences...")
        saved_files = collator.collate(images, output)

        print("=== Collate Result ===")
        print(f"Done! Processed {len(saved_files)} frames")
        print(f"Saved to: {output}")
    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(1)
