"""
Encapsulate some workflows for convenience

Usage
    uv run src/artist/workflow.py <workflow> *args **kwargs
"""


import cv2
from typing import Any, Annotated
import typer
from .video import Video2Frames
from .cut import SpriteCutter
from .compose import SpriteConcater

app = typer.Typer(
    name="workflow",
    help="Workflow tools - wraps common processing pipelines",
    add_completion=False,
    rich_markup_mode=None,
    pretty_exceptions_enable=False,
)


class Workflow:
    """Abstact base model"""
    def __init__(self) -> None:
        self.name = None

    def run(self, *args, **kwargs) -> Any:
        """
        Requires subclass implementation
        """
        pass

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.run(*args, **kwargs)

class Video2Animation(Workflow):
    def __init__(self) -> None:
        super().__init__()
        self.name = 'v2a'

    def run(self, video_path:str, output_path:str = None):
        """
        Extract animation frame sequence from Sora-generated video
            1. Extract frames from video_path (Video2Frames), sample=diff
            2. Cut each frame (don't save), assert len(sprites)==3, pick sprites[1] as the frame content
            3. concat
        """
        from pathlib import Path
        import tempfile
        import shutil

        # Create temp dir for intermediate results
        temp_dir = Path(tempfile.mkdtemp())

        try:
            # Step 1: Extract frames
            v2f = Video2Frames()
            frames_dir = temp_dir / "frames"
            frames_dir.mkdir(exist_ok=True)
            _, frames_output = v2f.extract_frames(
                video_path,
                str(frames_dir),
                sample='diff',
            )

            # Get all generated frame files
            frame_files = sorted(frames_dir.glob("*.png"))

            # Step 2: Cut each frame, pick the middle sprite
            cutter = SpriteCutter()
            selected_sprites = []

            for frame_file in sorted(frame_files):
                sprites = cutter.cut(str(frame_file))
                assert len(sprites) == 3, f"Expected 3 sprites, got {len(sprites)} from {frame_file}"
                # Pick the middle sprite (sprites[1])
                selected_sprites.append(sprites[1])

            # Step 3: Save selected sprites to temp files, then concat
            sprite_files = []
            sprites_dir = temp_dir / "sprites"
            sprites_dir.mkdir(exist_ok=True)

            for idx, sprite in enumerate(selected_sprites):
                sprite_path = sprites_dir / f"sprite_{idx:04d}.png"
                cv2.imwrite(str(sprite_path), sprite)
                sprite_files.append(str(sprite_path))

            # Concatenate all sprites
            if output_path is None:
                output_path = Path(video_path).stem + "_animation.png"

            concater = SpriteConcater()
            output_file = concater.concat_and_save(
                sprite_files,
                output_path,
                layout='row',
                tileset=True
            )

            print(f"Animation created: {output_file}")
            return output_file

        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

class ProcessRawSpritesheet(Workflow):
    """Decompose + cut an image. Uses layers=2 for decompose, cuts the xxx_d1.png output."""
    def __init__(self) -> None:
        super().__init__()
        self.name = "prs"

    def run(self, image_path:str, output_path:str = None):
        from pathlib import Path
        from .decompose import QwenImageLayeredClient

        # Step 1: Decompose with layers=2
        client = QwenImageLayeredClient()
        out_dir = client.decompose(image_path, layers=2, verbose=True)
        decomposed_files = sorted(out_dir.glob("*.png")) if out_dir else []

        # Step 2: Find xxx_d1.png file
        d1_file = None
        for file in decomposed_files:
            if "_d1.png" in str(file):
                d1_file = file
                break

        if d1_file is None:
            raise ValueError(f"Could not find _d1.png file in decomposed results: {decomposed_files}")

        # Step 3: Cut the d1 file
        cutter = SpriteCutter()

        if output_path is None:
            output_path = Path(image_path).stem + "_cut.png"

        output_file = cutter.cut_and_save(str(d1_file), output_path)

        print(f"Processed spritesheet: {output_file}")
        return output_file


@app.command("v2a")
def cmd_v2a(
    video_path: Annotated[str, typer.Argument(help="Input video file path")],
    output: Annotated[str, typer.Option("-o", "--output", help="Output file path")] = None,
):
    """Video2Animation - Generate animation frame sequence from video"""
    print("Processing video...")
    workflow = Video2Animation()
    output_file = workflow.run(video_path, output)

    print("=== Video2Animation ===")
    print("Done!")
    print(f"Output: {output_file}")


@app.command("prs")
def cmd_prs(
    image_path: Annotated[str, typer.Argument(help="Input image file path")],
    output: Annotated[str, typer.Option("-o", "--output", help="Output file path")] = None,
):
    """ProcessRawSpritesheet - Process raw spritesheet (decompose + cut)"""
    print("Processing spritesheet...")
    workflow = ProcessRawSpritesheet()
    output_file = workflow.run(image_path, output)

    print("=== ProcessRawSpritesheet ===")
    print("Done!")
    print(f"Output: {output_file}")


if __name__ == "__main__":
    app()
