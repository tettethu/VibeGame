"""
Animation preview and frame-to-video export tool.

Usage:
    vibegame art animation <folder_or_image>
    vibegame art animation <image> --fps 12 --row 4
    vibegame art f2v <folder> -o output.mp4 --fps 24
"""

import cv2
import numpy as np
import re
from pathlib import Path
from typing import List, Tuple, Optional, Annotated, Literal
import subprocess
import tempfile
import shutil

import typer

app = typer.Typer(name="animation", help="Animation preview and video export", add_completion=False, rich_markup_mode=None, pretty_exceptions_enable=False)


# ============ Config ============


class AnimationConfig:
    FPS = 24.0


# ============ AnimationPlayer ============


class AnimationPlayer:
    """Animation player - preview sprite frame animation."""

    def __init__(self, fps: float = AnimationConfig.FPS, place: str = "center") -> None:
        self.fps = fps
        self.spf = 1.0 / fps
        self.place = place

    def _load_frames(self, frames_dir: str) -> List[tuple]:
        """Load frame images with naming priority: _cX, _X, pure X."""
        frames_path = Path(frames_dir)
        if not frames_path.exists():
            raise ValueError(f"Directory not found: {frames_dir}")

        frames = []
        pattern_name = None

        pattern_c = re.compile(r"_c(\d+)\.(\w+)$")
        for file in frames_path.iterdir():
            if file.is_file():
                match = pattern_c.search(file.name)
                if match:
                    frame_idx = int(match.group(1))
                    ext = match.group(2)
                    img = cv2.imread(str(file), cv2.IMREAD_UNCHANGED)
                    if img is not None:
                        frames.append((frame_idx, file, img, ext))
        if frames:
            pattern_name = "_cX"

        if not frames:
            pattern_underscore = re.compile(r"_(\d+)\.(\w+)$")
            for file in frames_path.iterdir():
                if file.is_file():
                    match = pattern_underscore.search(file.name)
                    if match:
                        frame_idx = int(match.group(1))
                        ext = match.group(2)
                        img = cv2.imread(str(file), cv2.IMREAD_UNCHANGED)
                        if img is not None:
                            frames.append((frame_idx, file, img, ext))
            if frames:
                pattern_name = "_X"

        if not frames:
            pattern_pure = re.compile(r"^(\d+)\.(\w+)$")
            for file in frames_path.iterdir():
                if file.is_file():
                    match = pattern_pure.match(file.name)
                    if match:
                        frame_idx = int(match.group(1))
                        ext = match.group(2)
                        img = cv2.imread(str(file), cv2.IMREAD_UNCHANGED)
                        if img is not None:
                            frames.append((frame_idx, file, img, ext))
            if frames:
                pattern_name = "X"

        if not frames:
            # Fallback: natural filename sort
            pattern_name = "natural"
            img_exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".tif"}
            for file in sorted(frames_path.iterdir(), key=lambda f: f.name):
                if file.is_file() and file.suffix.lower() in img_exts:
                    img = cv2.imread(str(file), cv2.IMREAD_UNCHANGED)
                    if img is not None:
                        frames.append((len(frames), file, img, file.suffix.lstrip(".")))
            if not frames:
                raise ValueError(f"No image frames found in: {frames_dir}")

        if pattern_name != "natural":
            frames.sort(key=lambda x: x[0])

            extensions = set(f[3] for f in frames)
            if len(extensions) > 1:
                raise ValueError(f"Inconsistent frame extensions: {extensions}")

            indices = [f[0] for f in frames]
            expected = list(range(indices[0], indices[0] + len(indices)))
            if indices != expected:
                missing = set(expected) - set(indices)
                raise ValueError(
                    f"Non-consecutive frame indices, missing: {sorted(missing)} (rule: {pattern_name})"
                )

        return [(f[0], f[1], f[2]) for f in frames]

    def play(self, frames_dir: str, window_name: str = "Animation",
             bg_color: tuple = (50, 50, 50), startf: int = 0) -> None:
        frames = self._load_frames(frames_dir)
        sprites = [img for _, _, img in frames]
        self.play_from_sprites(sprites, window_name=window_name, bg_color=bg_color, startf=startf)

    def play_from_sprites(self, sprites: List[np.ndarray], window_name: str = "Animation",
                          bg_color: tuple = (50, 50, 50), startf: int = 0) -> None:
        if not sprites:
            raise ValueError("Empty sprite list")

        if startf < 0 or startf >= len(sprites):
            raise ValueError(f"Start frame {startf} out of range [0, {len(sprites)-1}]")

        print(f"Loaded {len(sprites)} frames")
        print(f"Starting from frame {startf}")
        print("Press 'q' or ESC to exit, space to pause/resume, '<'/'>' to adjust speed")

        max_h = max(img.shape[0] for img in sprites)
        max_w = max(img.shape[1] for img in sprites)

        display_frames = []
        for img in sprites:
            canvas = np.full((max_h, max_w, 3), bg_color, dtype=np.uint8)
            h, w = img.shape[:2]

            if self.place == "down-center":
                y_offset = max_h - h
                x_offset = (max_w - w) // 2
            else:
                y_offset = (max_h - h) // 2
                x_offset = (max_w - w) // 2

            if len(img.shape) == 3 and img.shape[2] == 4:
                bgr = img[:, :, :3]
                alpha = img[:, :, 3:4] / 255.0
                roi = canvas[y_offset:y_offset + h, x_offset:x_offset + w]
                blended = (bgr * alpha + roi * (1 - alpha)).astype(np.uint8)
                canvas[y_offset:y_offset + h, x_offset:x_offset + w] = blended
            else:
                canvas[y_offset:y_offset + h, x_offset:x_offset + w] = img

            display_frames.append(canvas)

        delay_ms = int(self.spf * 1000)
        paused = False
        current_frame = startf

        while True:
            cv2.imshow(window_name, display_frames[current_frame])
            key = cv2.waitKey(delay_ms) & 0xFF
            key = cv2.waitKey(delay_ms) & 0xFF

            if key == ord("q") or key == 27:
                break
            elif key == ord(" "):
                paused = not paused
                print("Paused" if paused else "Resumed")
            elif key == ord(",") or key == ord("<"):
                self.spf = min(1.0, self.spf + 0.02)
                delay_ms = int(self.spf * 1000)
                print(f"SPF: {self.spf:.2f}s")
            elif key == ord(".") or key == ord(">"):
                self.spf = max(0.02, self.spf - 0.02)
                delay_ms = int(self.spf * 1000)
                print(f"SPF: {self.spf:.2f}s")

            if not paused:
                current_frame = (current_frame + 1) % len(display_frames)

        cv2.destroyAllWindows()

    def export_video(
        self,
        frames_dir: str,
        output_path: str,
        fps: Optional[float] = None,
        bg_color: tuple = (50, 50, 50),
        codec: str = "mp4v",
        resize_width: Optional[int] = None,
        resize_height: Optional[int] = None,
        keep_aspect: bool = True,
        background: str = "white",
    ) -> Tuple[Path, Tuple[int, int]]:
        frames = self._load_frames(frames_dir)
        sprites = [img for _, _, img in frames]
        return self.export_video_from_sprites(
            sprites, output_path, fps=fps, bg_color=bg_color, codec=codec,
            resize_width=resize_width, resize_height=resize_height,
            keep_aspect=keep_aspect, background=background,
        )

    def export_video_from_sprites(
        self,
        sprites: List[np.ndarray],
        output_path: str,
        fps: Optional[float] = None,
        bg_color: tuple = (50, 50, 50),
        codec: str = "mp4v",
        resize_width: Optional[int] = None,
        resize_height: Optional[int] = None,
        keep_aspect: bool = True,
        background: str = "white",
    ) -> Tuple[Path, Tuple[int, int]]:
        if not sprites:
            raise ValueError("Empty sprite list")

        if fps is None:
            fps = 1.0 / self.spf

        max_h = max(img.shape[0] for img in sprites)
        max_w = max(img.shape[1] for img in sprites)

        display_frames = []
        for img in sprites:
            canvas = np.full((max_h, max_w, 3), bg_color, dtype=np.uint8)
            h, w = img.shape[:2]

            if self.place == "down-center":
                y_offset = max_h - h
                x_offset = (max_w - w) // 2
            else:
                y_offset = (max_h - h) // 2
                x_offset = (max_w - w) // 2

            if len(img.shape) == 3 and img.shape[2] == 4:
                bgr = img[:, :, :3]
                alpha = img[:, :, 3:4] / 255.0
                roi = canvas[y_offset:y_offset + h, x_offset:x_offset + w]
                blended = (bgr * alpha + roi * (1 - alpha)).astype(np.uint8)
                canvas[y_offset:y_offset + h, x_offset:x_offset + w] = blended
            else:
                canvas[y_offset:y_offset + h, x_offset:x_offset + w] = img

            display_frames.append(canvas)

        output_w, output_h = max_w, max_h
        if resize_width is not None or resize_height is not None:
            if keep_aspect:
                target_w = resize_width if resize_width is not None else max_w
                target_h = resize_height if resize_height is not None else max_h
                scale_w = target_w / max_w
                scale_h = target_h / max_h
                scale = min(scale_w, scale_h)
                scaled_w = int(max_w * scale)
                scaled_h = int(max_h * scale)
                pad_bgr = (255, 255, 255)
                output_w, output_h = target_w, target_h

                resized_frames = []
                for frame in display_frames:
                    scaled = cv2.resize(frame, (scaled_w, scaled_h), interpolation=cv2.INTER_AREA)
                    padded = np.full((target_h, target_w, 3), pad_bgr, dtype=np.uint8)
                    y_off = (target_h - scaled_h) // 2
                    x_off = (target_w - scaled_w) // 2
                    padded[y_off:y_off + scaled_h, x_off:x_off + scaled_w] = scaled
                    resized_frames.append(padded)
                display_frames = resized_frames

                print(f"Resize (keep aspect): {max_w}x{max_h} -> {output_w}x{output_h}")
            else:
                if resize_width is not None and resize_height is None:
                    scale = resize_width / max_w
                    output_w = resize_width
                    output_h = int(max_h * scale)
                elif resize_height is not None and resize_width is None:
                    scale = resize_height / max_h
                    output_h = resize_height
                    output_w = int(max_w * scale)
                else:
                    output_w = resize_width
                    output_h = resize_height

                resized_frames = [
                    cv2.resize(f, (output_w, output_h), interpolation=cv2.INTER_AREA)
                    for f in display_frames
                ]
                display_frames = resized_frames
                print(f"Resize (stretch): {max_w}x{max_h} -> {output_w}x{output_h}")

        # H.264 requires even dimensions
        if output_w % 2 != 0 or output_h % 2 != 0:
            new_w = output_w + (output_w % 2)
            new_h = output_h + (output_h % 2)
            if new_w != output_w or new_h != output_h:
                print(f"Adjusting to even dimensions: {output_w}x{output_h} -> {new_w}x{new_h}")
                pad_bgr = (255, 255, 255) if (resize_width or resize_height) else bg_color
                adjusted = []
                for frame in display_frames:
                    new_canvas = np.full((new_h, new_w, 3), pad_bgr, dtype=np.uint8)
                    new_canvas[0:output_h, 0:output_w] = frame
                    adjusted.append(new_canvas)
                display_frames = adjusted
                output_w, output_h = new_w, new_h

        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg not found in PATH, please install ffmpeg")

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            for i, frame in enumerate(display_frames):
                cv2.imwrite(str(temp_path / f"frame_{i:06d}.png"), frame)

            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-framerate", str(fps),
                "-i", str(temp_path / "frame_%06d.png"),
                "-c:v", "libx264",
                "-preset", "slow",
                "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(output_file),
            ]

            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg failed: {result.stderr}")

        print(f"Video exported! {len(display_frames)} frames, {fps:.2f} FPS, {output_w}x{output_h}")
        print(f"Output: {output_file}")
        return output_file, (output_w, output_h)


# ============ CLI Commands ============


@app.command("animation")
def cmd_animation(
    path: Annotated[str, typer.Argument(help="Frame directory or single sprite image")],
    fps: Annotated[float, typer.Option("--fps", help="Frames per second")] = AnimationConfig.FPS,
    padding: Annotated[int, typer.Option("-p", "--padding", help="Cut padding (for single image)")] = 0,
    min_area: Annotated[int, typer.Option("-m", "--min-area", help="Min sprite area (for single image)")] = 900,
    place: Annotated[str, typer.Option("--place", help="Alignment: center/down-center")] = "center",
    background: Annotated[str, typer.Option("--background", "--bg", help="Background: white/transparent")] = "white",
    startf: Annotated[int, typer.Option("--startf", help="Start frame index")] = 0,
):
    """Preview animation from folder or sprite sheet."""
    path_obj = Path(path)

    if not path_obj.exists():
        print(f"Path not found: {path}")
        raise typer.Exit(1)

    if place not in ["center", "down-center"]:
        print(f"Unsupported alignment: {place}")
        raise typer.Exit(1)

    if startf < 0:
        print(f"Start frame cannot be negative: {startf}")
        raise typer.Exit(1)

    player = AnimationPlayer(fps=fps, place=place)

    try:
        if path_obj.is_dir():
            player.play(path, startf=startf)
        elif path_obj.is_file():
            print("Detected image file, cutting into animation frames...")
            from .cut import SpriteCutter
            cutter = SpriteCutter(min_area=min_area)

            print("Cutting sprites...")
            sprites = cutter.cut(path)

            if not sprites:
                print("No sprites detected")
                raise typer.Exit(1)

            print(f"Cut done! Detected {len(sprites)} frames\n")
            player.play_from_sprites(sprites, startf=startf)
        else:
            print(f"Unsupported path type: {path}")
            raise typer.Exit(1)
    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(1)


@app.command("f2v")
def cmd_f2v(
    path: Annotated[str, typer.Argument(help="Frame directory or single sprite image")],
    output: Annotated[str, typer.Option("-o", "--output", help="Output video path")],
    fps: Annotated[float, typer.Option("--fps", help="Frames per second")] = AnimationConfig.FPS,
    padding: Annotated[int, typer.Option("-p", "--padding", help="Cut padding")] = 0,
    min_area: Annotated[int, typer.Option("-m", "--min-area", help="Min sprite area")] = 100,
    place: Annotated[str, typer.Option("--place", help="Alignment: center/down-center")] = "center",
    codec: Annotated[str, typer.Option("--codec", help="Video codec: mp4v/avc1/XVID")] = "mp4v",
    resizew: Annotated[Optional[int], typer.Option("--resizew", help="Output width")] = None,
    resizeh: Annotated[Optional[int], typer.Option("--resizeh", help="Output height")] = None,
    not_keep_aspect: Annotated[bool, typer.Option("--not-keep-aspect", help="Stretch instead of pad")] = False,
    background: Annotated[str, typer.Option("--background", "--bg", help="Background: white/transparent")] = "white",
):
    """Export frame sequence to MP4 video."""
    path_obj = Path(path)

    if not path_obj.exists():
        print(f"Path not found: {path}")
        raise typer.Exit(1)

    if not output:
        print("Need output path -o/--output")
        raise typer.Exit(1)

    if place not in ["center", "down-center"]:
        print(f"Unsupported alignment: {place}")
        raise typer.Exit(1)

    player = AnimationPlayer(fps=fps, place=place)

    try:
        if path_obj.is_dir():
            print("Exporting video...")
            output_file, resolution = player.export_video(
                path, output, fps=fps, codec=codec,
                resize_width=resizew, resize_height=resizeh,
                keep_aspect=not not_keep_aspect, background=background,
            )

        elif path_obj.is_file():
            print("Detected image file, cutting into animation frames...")
            from .cut import SpriteCutter
            cutter = SpriteCutter(min_area=min_area)

            print("Cutting sprites...")
            sprites = cutter.cut(path)

            if not sprites:
                print("No sprites detected")
                raise typer.Exit(1)

            print(f"Cut done! Detected {len(sprites)} frames")

            print("Exporting video...")
            output_file, resolution = player.export_video_from_sprites(
                sprites, output, fps=fps, codec=codec,
                resize_width=resizew, resize_height=resizeh,
                keep_aspect=not not_keep_aspect, background=background,
            )
        else:
            print(f"Unsupported path type: {path}")
            raise typer.Exit(1)

        print("=== Video Export Result ===")
        print("Done!")
        print(f"Output: {output_file}")
        print(f"Resolution: {resolution[0]}x{resolution[1]}")
        print(f"FPS: {fps:.2f}")
        print(f"Codec: {codec}")

    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(1)
