"""
Sprite concatenation and canvas drawing tools.

Usage:
    vibegame art concat <img1> <img2> -o output.png
    vibegame art concat folder/ -o output.png --layout square
    vibegame art canvas img1.png img2.png -o out.png --mode lr
"""

import cv2
import json
import numpy as np
import re
from pathlib import Path
from typing import List, Tuple, Optional, Annotated, Literal, Union
from PIL import Image
import shutil

import typer

from .cut import _load_manifest, _save_manifest

app = typer.Typer(name="compose", help="Sprite concatenation and canvas drawing", add_completion=False, rich_markup_mode=None, pretty_exceptions_enable=False)


# ============ Config ============


class ComposeConfig:
    CROP = False
    PADDING = 0
    SPACING = 0
    LAYOUT = "row"
    BACKGROUND = "transparent"


# ============ SpriteCanvas (internal) ============


class SpriteCanvas:
    """Canvas drawing utility - places images at specified positions.

    Internal class, no CLI exposure.
    """

    def __init__(self) -> None:
        pass

    def _load_images(self, image_paths):
        images = []
        for path in image_paths:
            try:
                if isinstance(path, Image.Image):
                    images.append(path.convert("RGBA"))
                    continue
                img = Image.open(path)
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                images.append(img)
            except Exception as e:
                raise ValueError(f"Cannot read image: {path}, {e}")
        return images

    def draw(
        self,
        canvas_size: Union[List, Tuple],
        image_paths: List[Union[str, Image.Image]],
        locations: List[Tuple],
        anchor: Literal["center", "leftup"] = "leftup",
        background: Literal["white", "transparent"] = "transparent",
    ):
        """Draw images onto a canvas at specified positions.

        Args:
            canvas_size: [width, height]
            image_paths: list of image paths or PIL Images
            locations: list of (x, y) coordinates per image
            anchor: 'center' or 'leftup'
            background: 'transparent' or 'white'

        Returns:
            PIL.Image
        """
        assert len(image_paths) == len(locations), "Image count must match location count"
        assert len(canvas_size) == 2, "canvas_size must be [width, height]"

        canvas_width, canvas_height = canvas_size[0], canvas_size[1]
        images = self._load_images(image_paths=image_paths)

        if background == "white":
            canvas = Image.new("RGBA", (canvas_width, canvas_height), (255, 255, 255, 255))
        else:
            canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))

        for img, (x, y) in zip(images, locations):
            w, h = img.size

            if anchor == "center":
                x = x - w // 2
                y = y - h // 2

            x_end = min(x + w, canvas_width)
            y_end = min(y + h, canvas_height)

            if x_end <= x or y_end <= y:
                continue

            if x >= 0 and y >= 0 and x + w <= canvas_width and y + h <= canvas_height:
                canvas.paste(img, (x, y))
            else:
                cropped = img.crop((0, 0, x_end - x, y_end - y))
                canvas.paste(cropped, (x, y))

        return canvas

    def draw_lr(self, image_paths: List, empty_ratio: int,
                background: Literal["white", "transparent"] = "transparent"):
        """Place images on left and right of a canvas."""
        images = self._load_images(image_paths=image_paths)
        assert len(images) == 2

        print(images[0].size)
        width1, height1 = images[0].size
        width2, height2 = images[1].size
        width = (width1 + width2) / 2
        height = (height1 + height2) / 2

        canvas_width = int(width * (2 + empty_ratio))
        canvas_height = int(max(height1, height2) + 100)

        locations = [
            (0, (canvas_height - height1) // 2),
            (canvas_width - width2, (canvas_height - height2) // 2),
        ]
        return self.draw(
            canvas_size=[canvas_width, canvas_height],
            image_paths=images,
            locations=locations,
            anchor="leftup",
            background=background,
        )

    def draw_interpolation(self, image_paths: List,
                           background: Literal["white", "transparent"] = "transparent"):
        """Place images with interpolation spacing."""
        images = self._load_images(image_paths=image_paths)
        widths = [img.size[0] for img in images]
        heights = [img.size[1] for img in images]
        canvas_height = max(heights) + 100

        curr_x = 0
        locations = []
        for i, img in enumerate(images):
            locations.append((curr_x, (canvas_height - heights[i]) // 2))
            curr_x += widths[i] * 2 + 50

        canvas_width = curr_x - widths[-1]
        return self.draw(
            canvas_size=(canvas_width, canvas_height),
            image_paths=images,
            locations=locations,
            anchor="leftup",
            background=background,
        )

    def draw_left(self, image_paths: List, empty_ratio: int = 5,
                  background: Literal["white", "transparent"] = "transparent"):
        """Single image left-aligned."""
        assert len(image_paths) == 1
        images = self._load_images(image_paths=image_paths)
        width, height = images[0].size
        canvas_width = width * (1 + empty_ratio)
        canvas_height = height + 100
        locations = [(0, (canvas_height - height) // 2)]
        return self.draw(
            canvas_size=(canvas_width, canvas_height),
            image_paths=images,
            locations=locations,
            anchor="leftup",
            background=background,
        )

    def draw_leftup(self, image_paths: List, empty_ratio: int = 4,
                    background: Literal["white", "transparent"] = "transparent"):
        """Place single image top-left, remaining space for n*n-1 images."""
        assert len(image_paths) == 1, "draw_leftup takes exactly one image"
        images = self._load_images(image_paths=image_paths)
        img_width, img_height = images[0].size
        canvas_width = img_width * empty_ratio
        canvas_height = img_height * empty_ratio
        locations = [(0, 0)]
        return self.draw(
            canvas_size=(canvas_width, canvas_height),
            image_paths=images,
            locations=locations,
            anchor="leftup",
            background=background,
        )

    def draw_body(self, shape: Literal["square", "rectangle"],
                  background: Literal["white", "transparent"], **kwargs):
        """Draw a geometric solid body on a canvas."""
        from PIL import ImageDraw

        if shape == "square":
            edge = int(kwargs["edge"])
            canvas_width = int(kwargs.get("canvas_width", edge * 2))
            canvas_height = int(kwargs.get("canvas_height", edge * 2))
            body_color = kwargs.get("body_color", "black")

            if background == "white":
                canvas = Image.new("RGBA", (canvas_width, canvas_height), (255, 255, 255, 255))
            else:
                canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))

            x = (canvas_width - edge) // 2
            y = (canvas_height - edge) // 2
            draw = ImageDraw.Draw(canvas)
            draw.rectangle([x, y, x + edge, y + edge], fill=body_color)
            return canvas

        elif shape == "rectangle":
            width = int(kwargs["width"])
            height = int(kwargs["height"])
            canvas_width = int(kwargs.get("canvas_width", width * 2))
            canvas_height = int(kwargs.get("canvas_height", height * 2))
            body_color = kwargs.get("body_color", "black")

            if background == "white":
                canvas = Image.new("RGBA", (canvas_width, canvas_height), (255, 255, 255, 255))
            else:
                canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))

            x = (canvas_width - width) // 2
            y = (canvas_height - height) // 2
            draw = ImageDraw.Draw(canvas)
            draw.rectangle([x, y, x + width, y + height], fill=body_color)
            return canvas


# ============ SpriteConcater ============


class SpriteConcater:
    """Concatenate multiple images into one large image."""

    def __init__(
        self,
        crop: bool = ComposeConfig.CROP,
        padding: int = ComposeConfig.PADDING,
        spacing: int = ComposeConfig.SPACING,
        background: Literal["transparent", "white"] = ComposeConfig.BACKGROUND,
    ):
        self.default_crop = crop
        self.default_padding = padding
        self.default_spacing = spacing
        self.default_background = background

    def _natural_sort_key(self, path: Path) -> List:
        text = path.stem
        return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", text)]

    def _load_sprites_from_folder(self, folder: str) -> List[str]:
        folder_path = Path(folder)
        supported_exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
        files = [
            f for f in folder_path.iterdir()
            if f.is_file() and f.suffix.lower() in supported_exts
        ]
        return [str(f) for f in sorted(files, key=self._natural_sort_key)]

    def concat_and_save(
        self,
        image_paths: List[str] | str,
        output_path: Optional[str] = None,
        layout: str = "row",
        crop: Optional[bool] = None,
        padding: Optional[int] = None,
        spacing: Optional[int] = None,
        tileset: bool = False,
        background: Optional[Literal["transparent", "white"]] = None,
    ) -> Path:
        # Expand folder/prefix paths
        if isinstance(image_paths, str):
            image_paths = [image_paths]
        supported_exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
        _images = []
        for image in image_paths:
            p = Path(image)
            if p.is_dir():
                folder_images = self._load_sprites_from_folder(str(image))
                if not folder_images:
                    raise ValueError(f"No images found in folder: {image}")
                _images.extend(folder_images)
            elif p.is_file():
                _images.append(image)
            else:
                # Treat as filename prefix: match parent/<name>*
                matches = sorted(
                    [f for f in p.parent.glob(p.name + "*") if f.is_file() and f.suffix.lower() in supported_exts],
                    key=self._natural_sort_key,
                )
                if not matches:
                    raise ValueError(f"Path not found and no matching files for prefix: {image}")
                _images.extend(str(f) for f in matches)
        image_paths = _images

        if not image_paths:
            raise ValueError("No images found")
        if len(image_paths) < 2:
            raise ValueError(f"Need at least 2 images, got {len(image_paths)}: {image_paths[0]}")

        grid_cols, grid_rows = None, None
        if "x" in layout and layout not in ["row", "column", "square"]:
            parts = layout.split("x", 1)
            if len(parts) == 2:
                r_str, c_str = parts  # NxM = N rows x M cols
                grid_rows = int(r_str) if r_str != "-" else None
                grid_cols = int(c_str) if c_str != "-" else None
                if grid_cols is None and grid_rows is None:
                    raise ValueError("layout 'axb': a and b cannot both be '-'")
                layout = "grid"
        if layout not in ["row", "column", "square", "grid"]:
            raise ValueError(
                f"Unsupported layout: {layout}, supported: row/column/square or axb (e.g. 3x5)"
            )

        crop = crop if crop is not None else self.default_crop
        padding = padding if padding is not None else self.default_padding
        spacing = spacing if spacing is not None else self.default_spacing
        background = background if background is not None else self.default_background

        images = []
        for path in image_paths:
            img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
            if img is None:
                raise ValueError(f"Cannot read image: {path}")
            images.append(img)

        if tileset:
            images = self._process_tileset(images, padding)
            images = self._normalize_size(images, mode="resize")
            print(f"tile size: {images[0].shape[:2]}")
        else:
            if crop:
                images = [self._crop_content(img, padding) for img in images]

        if layout == "grid":
            result, bboxes = self._concat_grid(images, grid_cols, grid_rows, spacing, background)
        elif layout == "row":
            result, bboxes = self._concat_row(images, spacing, background)
        elif layout == "column":
            result, bboxes = self._concat_column(images, spacing, background)
        else:  # square
            result, bboxes = self._concat_square(images, spacing, background)

        if not output_path:
            raise ValueError("output_path cannot be empty")

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_file), result)

        sprites = {}
        for idx, (path, (x, y, w, h)) in enumerate(zip(image_paths, bboxes)):
            stem = Path(path).stem
            sprites[stem] = {"bbox": [x, y, w, h]}

        manifest_path = output_file.parent / "manifest.json"
        manifest = _load_manifest(manifest_path)
        manifest[output_file.stem] = {
            "type": "atlas",
            "path": output_file.name,
            "sprites": sprites,
        }
        _save_manifest(manifest_path, manifest)

        print(f"Atlas: {output_file.name} ({result.shape[1]}x{result.shape[0]}, {len(sprites)} sprites)")
        for name, info in sprites.items():
            x, y, w, h = info["bbox"]
            print(f"  {name}: [{x}, {y}, {w}, {h}]")
        print(f"Manifest: {manifest_path}")
        return output_file

    def _crop_content(self, img: np.ndarray, padding: int = 0) -> np.ndarray:
        if len(img.shape) == 3 and img.shape[2] == 4:
            mask = (img[:, :, 3] > 10).astype(np.uint8) * 255
        else:
            if len(img.shape) == 2:
                gray = img
            else:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, mask = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return img

        x_min, y_min = img.shape[1], img.shape[0]
        x_max, y_max = 0, 0

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            x_min = min(x_min, x)
            y_min = min(y_min, y)
            x_max = max(x_max, x + w)
            y_max = max(y_max, y + h)

        x_min = max(0, x_min - padding)
        y_min = max(0, y_min - padding)
        x_max = min(img.shape[1], x_max + padding)
        y_max = min(img.shape[0], y_max + padding)

        return img[y_min:y_max, x_min:x_max]

    def _normalize_size(self, images: List[np.ndarray], mode: str = "padding") -> List[np.ndarray]:
        if not images:
            return images

        max_w = max(img.shape[1] for img in images)
        max_h = max(img.shape[0] for img in images)

        normalized = []
        for img in images:
            h, w = img.shape[:2]
            if h == max_h and w == max_w:
                normalized.append(img)
                continue

            if mode == "resize":
                normalized.append(cv2.resize(img, (max_w, max_h), interpolation=cv2.INTER_AREA))
            else:
                if len(img.shape) == 3 and img.shape[2] == 4:
                    canvas = np.zeros((max_h, max_w, 4), dtype=np.uint8)
                else:
                    canvas = np.zeros((max_h, max_w, 3), dtype=np.uint8)
                x_offset = (max_w - w) // 2
                y_offset = (max_h - h) // 2
                canvas[y_offset:y_offset + h, x_offset:x_offset + w] = img
                normalized.append(canvas)

        return normalized

    def _process_tileset(self, images: List[np.ndarray], padding: int = 0) -> List[np.ndarray]:
        cropped_images = [self._crop_content(img, padding) for img in images]
        max_w = max(img.shape[1] for img in cropped_images)
        max_h = max(img.shape[0] for img in cropped_images)
        edge = max(max_w, max_h)

        tiles = []
        for img in cropped_images:
            h, w = img.shape[:2]

            if w >= 2 * edge or h >= 2 * edge:
                if w >= 2 * edge:
                    new_w = (w // edge) * edge
                    scale = new_w / w
                    new_h = int(h * scale)
                    img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                    h, w = img.shape[:2]

                if h >= 2 * edge:
                    new_h = (h // edge) * edge
                    scale = new_h / h
                    new_w = int(w * scale)
                    img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                    h, w = img.shape[:2]

                for y in range(0, h, edge):
                    for x in range(0, w, edge):
                        tile = img[y:min(y + edge, h), x:min(x + edge, w)]
                        if tile.shape[0] != edge or tile.shape[1] != edge:
                            tile = cv2.resize(tile, (edge, edge), interpolation=cv2.INTER_AREA)
                        tiles.append(tile)
            else:
                tiles.append(cv2.resize(img, (edge, edge), interpolation=cv2.INTER_AREA))

        return tiles

    def _add_alpha_channel(self, img: np.ndarray) -> np.ndarray:
        if len(img.shape) == 2:
            return cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
        elif img.shape[2] == 3:
            bgra = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
            bgra[:, :, 3] = 255
            return bgra
        return img

    def _concat_row(self, images: List[np.ndarray], spacing: int = 0, background: str = "transparent") -> tuple:
        max_h = max(img.shape[0] for img in images)
        has_alpha = any(len(img.shape) == 3 and img.shape[2] == 4 for img in images)
        channels = 4 if has_alpha else 3
        total_width = sum(img.shape[1] for img in images) + spacing * (len(images) - 1)

        if background == "white":
            canvas = np.full((max_h, total_width, channels),
                             [255, 255, 255, 255] if channels == 4 else 255, dtype=np.uint8)
        else:
            canvas = np.zeros((max_h, total_width, channels), dtype=np.uint8)

        bboxes = []
        x_offset = 0
        for img in images:
            h, w = img.shape[:2]
            if has_alpha and (len(img.shape) == 2 or img.shape[2] == 3):
                img = self._add_alpha_channel(img)
            y_offset = (max_h - h) // 2
            canvas[y_offset:y_offset + h, x_offset:x_offset + w] = img
            bboxes.append((x_offset, y_offset, w, h))
            x_offset += w + spacing

        return canvas, bboxes

    def _concat_column(self, images: List[np.ndarray], spacing: int = 0, background: str = "transparent") -> tuple:
        max_w = max(img.shape[1] for img in images)
        has_alpha = any(len(img.shape) == 3 and img.shape[2] == 4 for img in images)
        channels = 4 if has_alpha else 3
        total_height = sum(img.shape[0] for img in images) + spacing * (len(images) - 1)

        if background == "white":
            canvas = np.full((total_height, max_w, channels),
                             [255, 255, 255, 255] if channels == 4 else 255, dtype=np.uint8)
        else:
            canvas = np.zeros((total_height, max_w, channels), dtype=np.uint8)

        bboxes = []
        y_offset = 0
        for img in images:
            h, w = img.shape[:2]
            if has_alpha and (len(img.shape) == 2 or img.shape[2] == 3):
                img = self._add_alpha_channel(img)
            x_offset = (max_w - w) // 2
            canvas[y_offset:y_offset + h, x_offset:x_offset + w] = img
            bboxes.append((x_offset, y_offset, w, h))
            y_offset += h + spacing

        return canvas, bboxes

    def _concat_grid(self, images: List[np.ndarray], cols, rows, spacing: int = 0, background: str = "transparent") -> tuple:
        n = len(images)
        if cols is not None and rows is not None:
            capacity = cols * rows
            min_needed = (rows - 1) * cols + 1
            if n > capacity:
                raise ValueError(f"Too many images ({n}) for {rows}x{cols} grid (max {capacity})")
            if n < min_needed:
                raise ValueError(f"Too few images ({n}) for {rows}x{cols} grid (need {min_needed}-{capacity}, only last row may be partial)")
        elif cols is not None:
            rows = int(np.ceil(n / cols))
        else:
            cols = int(np.ceil(n / rows))
        return self._concat_to_grid(images, cols, rows, spacing, background)

    def _concat_square(self, images: List[np.ndarray], spacing: int = 0, background: str = "transparent") -> tuple:
        n = len(images)
        cols = int(np.ceil(np.sqrt(n)))
        rows = int(np.ceil(n / cols))
        return self._concat_to_grid(images, cols, rows, spacing, background)

    def _concat_to_grid(self, images: List[np.ndarray], cols: int, rows: int, spacing: int = 0, background: str = "transparent") -> tuple:
        max_w = max(img.shape[1] for img in images)
        max_h = max(img.shape[0] for img in images)
        has_alpha = any(len(img.shape) == 3 and img.shape[2] == 4 for img in images)
        channels = 4 if has_alpha else 3

        total_width = cols * max_w + spacing * (cols - 1)
        total_height = rows * max_h + spacing * (rows - 1)

        if background == "white":
            canvas = np.full((total_height, total_width, channels),
                             [255, 255, 255, 255] if channels == 4 else 255, dtype=np.uint8)
        else:
            canvas = np.zeros((total_height, total_width, channels), dtype=np.uint8)

        bboxes = []
        for idx, img in enumerate(images):
            row = idx // cols
            col = idx % cols
            h, w = img.shape[:2]

            y_cell = row * (max_h + spacing)
            x_cell = col * (max_w + spacing)
            y_start = y_cell + (max_h - h) // 2
            x_start = x_cell + (max_w - w) // 2

            if has_alpha and (len(img.shape) == 2 or img.shape[2] == 3):
                img = self._add_alpha_channel(img)

            canvas[y_start:y_start + h, x_start:x_start + w] = img
            bboxes.append((x_start, y_start, w, h))

        return canvas, bboxes


# ============ CLI Commands ============


@app.command("concat")
def cmd_concat(
    images: Annotated[List[str], typer.Argument(help="Input image paths or folder")],
    output: Annotated[str, typer.Option("-o", "--output", help="Output file path")],
    layout: Annotated[str, typer.Option("-l", "--layout", help="Layout: row/column/square/axb")] = ComposeConfig.LAYOUT,
    crop: Annotated[bool, typer.Option("-c", "--crop", help="Auto-crop blank areas")] = ComposeConfig.CROP,
    padding: Annotated[int, typer.Option("-p", "--padding", help="Padding after crop")] = ComposeConfig.PADDING,
    spacing: Annotated[int, typer.Option("-s", "--spacing", help="Spacing between images")] = ComposeConfig.SPACING,
    background: Annotated[str, typer.Option("-b", "--background", help="Background: transparent/white")] = ComposeConfig.BACKGROUND,
    tileset: Annotated[bool, typer.Option("--tileset/--no-tileset", help="Tileset mode: normalize to square tiles")] = False,
):
    """Concatenate multiple images into one."""
    concater = SpriteConcater(crop=crop, padding=padding, spacing=spacing, background=background)
    output_file = concater.concat_and_save(images, output, layout, tileset=tileset)

    img = cv2.imread(str(output_file), cv2.IMREAD_UNCHANGED)
    h, w = img.shape[:2]

    print("=== Concat Result ===")
    print("Done!")
    print(f"Output: {output_file.absolute()}")
    print(f"Size: {w}x{h}")
    print(f"Layout: {layout}")
    print(f"Tileset: {'Yes' if tileset else 'No'}")
    print(f"Auto-crop: {'Yes' if crop else 'No'}")
    print(f"Spacing: {spacing}px")


@app.command("canvas")
def cmd_canvas(
    images: Annotated[Optional[List[str]], typer.Argument(help="Input image paths (not needed for body mode)")] = None,
    output: Annotated[str, typer.Option("-o", "--output", help="Output file path")] = "",
    mode: Annotated[Literal["custom", "lr", "interpolation", "left", "leftup", "body"], typer.Option("--mode")] = "custom",
    empty_ratio: Annotated[Optional[int], typer.Option("--empty-ratio")] = 4,
    canvas_width: Annotated[Optional[int], typer.Option("--canvas-width")] = None,
    canvas_height: Annotated[Optional[int], typer.Option("--canvas-height")] = None,
    locations: Annotated[Optional[str], typer.Option("--locations", help="Positions: x1,y1;x2,y2;...")] = None,
    anchor: Annotated[Literal["center", "leftup"], typer.Option("--anchor")] = "leftup",
    background: Annotated[Literal["white", "transparent"], typer.Option("--background")] = "transparent",
    shape: Annotated[Optional[Literal["square", "rectangle"]], typer.Option("--shape")] = None,
    edge: Annotated[Optional[int], typer.Option("--edge")] = None,
    width: Annotated[Optional[int], typer.Option("--width")] = None,
    height: Annotated[Optional[int], typer.Option("--height")] = None,
    body_color: Annotated[str, typer.Option("--body-color")] = "black",
):
    """Draw images on a canvas at specified positions, or draw geometric shapes."""
    canvas = SpriteCanvas()

    try:
        if not output:
            print("Need output path -o/--output")
            raise typer.Exit(1)

        if mode != "body" and (images is None or len(images) == 0):
            print("Need image paths (except for body mode)")
            raise typer.Exit(1)

        output_file = Path(output)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if mode == "lr":
            if len(images) != 2:
                print("lr mode needs exactly 2 images")
                raise typer.Exit(1)
            result = canvas.draw_lr(image_paths=images, empty_ratio=empty_ratio, background=background)
            result.save(str(output_file))

        elif mode == "custom":
            if canvas_width is None or canvas_height is None or locations is None:
                print("custom mode needs --canvas-width, --canvas-height, --locations")
                raise typer.Exit(1)
            try:
                loc_list = [tuple(int(v) for v in loc_str.split(",")) for loc_str in locations.split(";")]
            except Exception as e:
                print(f"Location format error: {e}")
                raise typer.Exit(1)
            if len(images) != len(loc_list):
                print(f"Image count ({len(images)}) must match location count ({len(loc_list)})")
                raise typer.Exit(1)
            result = canvas.draw(
                canvas_size=[canvas_width, canvas_height],
                image_paths=images,
                locations=loc_list,
                anchor=anchor,
                background=background,
            )
            result.save(str(output_file))

        elif mode == "interpolation":
            result = canvas.draw_interpolation(image_paths=images, background=background)
            result.save(str(output_file))

        elif mode == "left":
            if len(images) != 1:
                print("left mode needs exactly 1 image")
                raise typer.Exit(1)
            result = canvas.draw_left(image_paths=images, empty_ratio=empty_ratio, background=background)
            result.save(str(output_file))

        elif mode == "leftup":
            if len(images) != 1:
                print("leftup mode needs exactly 1 image")
                raise typer.Exit(1)
            result = canvas.draw_leftup(image_paths=images, background=background, empty_ratio=empty_ratio)
            result.save(str(output_file))

        elif mode == "body":
            if shape is None:
                print("body mode needs --shape (square/rectangle)")
                raise typer.Exit(1)
            kwargs = {}
            if shape == "square":
                if edge is None:
                    print("square shape needs --edge")
                    raise typer.Exit(1)
                kwargs["edge"] = edge
            elif shape == "rectangle":
                if width is None or height is None:
                    print("rectangle shape needs --width and --height")
                    raise typer.Exit(1)
                kwargs["width"] = width
                kwargs["height"] = height
            if canvas_width is not None:
                kwargs["canvas_width"] = canvas_width
            if canvas_height is not None:
                kwargs["canvas_height"] = canvas_height
            kwargs["body_color"] = body_color
            result = canvas.draw_body(shape=shape, background=background, **kwargs)
            result.save(str(output_file))

        print("=== Canvas Result ===")
        print(f"Done! Output: {output_file}, Size: {result.size[0]}x{result.size[1]}")

    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(1)
