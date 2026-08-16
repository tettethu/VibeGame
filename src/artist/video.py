"""
Video to frames extraction tool.

Usage:
    vibegame art v2f video.mp4 -o frames/
    vibegame art v2f video.mp4 -o frames/ --fps 10
    vibegame art v2f video.mp4 --start 5 --end 10
    vibegame art v2f video.mp4 --sample all
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, Annotated, Literal

import typer

app = typer.Typer(name="video", help="Video to frames extraction", add_completion=False, rich_markup_mode=None, pretty_exceptions_enable=False)


# ============ Video2Frames ============


class Video2Frames:
    """Extract frame sequences from video."""

    def __init__(self):
        pass

    def extract_frames(
        self,
        video_path: str,
        output_dir: str = None,
        fps: Optional[float] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        prefix: str = "frame",
        sample: str = "diff",
        preview: bool = False,
        loop: bool = False,
        diff_threshold: Optional[float] = None,
    ) -> Tuple[int, str]:
        """Extract frame sequence from video.

        Args:
            video_path: input video path
            output_dir: output directory
            fps: extraction frame rate (None = extract all)
            start_time: start time in seconds
            end_time: end time in seconds
            prefix: output filename prefix
            sample: 'all' or 'diff' (keep only frames with above-average diff)
            preview: preview animation before saving

        Returns:
            (frame_count, output_dir_path)
        """
        video_path_obj = Path(video_path)
        if not video_path_obj.exists():
            raise ValueError(f"Video file not found: {video_path}")

        if not output_dir:
            output_dir = video_path_obj.parent / "frames" / video_path_obj.stem
        output_path = Path(output_dir)

        if output_path.exists():
            for old_frame in output_path.glob(f"{prefix}_*.png"):
                old_frame.unlink()

        output_path.mkdir(parents=True, exist_ok=True)

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        try:
            video_fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            frame_interval = 1 if fps is None else max(1, int(video_fps / fps))

            start_frame = int(start_time * video_fps) if start_time is not None else 0
            end_frame = int(end_time * video_fps) if end_time is not None else total_frames

            start_frame = max(0, min(start_frame, total_frames - 1))
            end_frame = max(start_frame + 1, min(end_frame, total_frames))

            temp_frames = []
            frame_diffs = []
            current_frame = 0
            prev_frame = None

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if current_frame < start_frame:
                    current_frame += 1
                    continue
                if current_frame >= end_frame:
                    break

                if (current_frame - start_frame) % frame_interval == 0:
                    if prev_frame is not None:
                        diff = np.mean(np.abs(frame.astype(float) - prev_frame.astype(float)))
                        frame_diffs.append(diff)
                    else:
                        frame_diffs.append(0)

                    temp_frames.append(frame.copy())
                    prev_frame = frame.copy()

                current_frame += 1

            # --loop: compute per-frame diff to frame 0, find local minima
            loop_minima = set()
            if loop and len(temp_frames) > 1:
                first = temp_frames[0].astype(float)
                loop_diffs = np.array([
                    np.mean(np.abs(temp_frames[i].astype(float) - first))
                    for i in range(len(temp_frames))
                ])
                # local minima: frame i where diff[i] < diff[i-1] and diff[i] < diff[i+1]
                for i in range(1, len(loop_diffs) - 1):
                    if loop_diffs[i] < loop_diffs[i - 1] and loop_diffs[i] < loop_diffs[i + 1]:
                        loop_minima.add(i)
                print(f"[loop] diff-to-frame0 minima at: {sorted(loop_minima)}")
                print(f"[loop] diffs: {', '.join(f'{loop_diffs[i]:.1f}' for i in sorted(loop_minima))}")

            # sample: diff filter, but protect loop minima from being dropped
            frames_to_save = []
            saved_indices = []
            if sample == "diff":
                threshold = diff_threshold if diff_threshold is not None else (np.mean(frame_diffs) if frame_diffs else 0)
                for i, (frame, diff) in enumerate(zip(temp_frames, frame_diffs)):
                    if i == 0 or diff > threshold or i in loop_minima:
                        frames_to_save.append(frame)
                        saved_indices.append(i)
            else:
                frames_to_save = temp_frames
                saved_indices = list(range(len(temp_frames)))

            # re-check loop minima against saved frames
            if loop and loop_minima and saved_indices:
                surviving = [saved_indices.index(m) for m in sorted(loop_minima) if m in saved_indices]
                if surviving:
                    print(f"[loop] surviving minima (0-based in output): {surviving}")

            if preview and frames_to_save:
                print("\nPreview mode: playing animation...")
                print("Press Ctrl+C to stop\n")

                window_name = "Video Preview (Press 'q' to stop)"
                cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

                try:
                    frame_delay = int(1000 / video_fps) if video_fps > 0 else 33
                    while True:
                        for frame in frames_to_save:
                            cv2.imshow(window_name, frame)
                            key = cv2.waitKey(frame_delay)
                            if key == ord("q") or key == 27:
                                raise KeyboardInterrupt
                            elif key != -1:
                                break
                        else:
                            continue
                        break
                except KeyboardInterrupt:
                    pass
                finally:
                    cv2.destroyAllWindows()

                print("\nSave these frames? (Enter to confirm, Ctrl+C to cancel)")
                try:
                    input()
                except KeyboardInterrupt:
                    print("\nCancelled")
                    return 0, str(output_path)

            frame_count = 0
            total_to_save = len(frames_to_save)
            num_digits = len(str(total_to_save - 1)) if total_to_save > 0 else 1

            for frame in frames_to_save:
                output_file = output_path / f"{prefix}_{frame_count:0{num_digits}d}.png"
                cv2.imwrite(str(output_file), frame)
                frame_count += 1

            # Report sample stats
            if sample == "diff" and frame_diffs:
                total = len(temp_frames)
                dropped = sum(1 for i, d in enumerate(frame_diffs) if i > 0 and d <= threshold)
                source = f"user={diff_threshold}" if diff_threshold is not None else f"auto={threshold:.2f}"
                print(f"[sample] threshold({source}), {dropped}/{total} frames dropped (diff <= threshold)")

            return frame_count, str(output_path)

        finally:
            cap.release()


# ============ CLI Commands ============


@app.command("v2f")
def cmd_v2f(
    video: Annotated[str, typer.Argument(help="Input video path")],
    output: Annotated[str, typer.Option("-o", "--output", help="Output directory")] = None,
    fps: Annotated[Optional[float], typer.Option("--fps", help="Extraction frame rate (default: all frames)")] = None,
    start: Annotated[Optional[float], typer.Option("--start", help="Start time in seconds")] = None,
    end: Annotated[Optional[float], typer.Option("--end", help="End time in seconds")] = None,
    prefix: Annotated[str, typer.Option("--prefix", help="Output filename prefix")] = "frame",
    sample: Annotated[Literal["all", "diff"], typer.Option("--sample", "--sa", help="Sampling mode")] = "diff",
    diff_threshold: Annotated[Optional[float], typer.Option("--diff-threshold", "--dt", help="Sample threshold: drop frames with diff <= this value (default: auto mean)")] = None,
    loop: Annotated[bool, typer.Option("--loop", help="Compute diff-to-frame0 for each frame, report local minima as loop candidates")] = False,
    preview: Annotated[bool, typer.Option("--preview", "-p", help="Preview before saving")] = False,
):
    """Extract video to frame sequence.

    Examples:
      vibegame art v2f video.mp4 -o frames/
      vibegame art v2f video.mp4 -o frames/ --fps 10
      vibegame art v2f video.mp4 -o frames/ --start 5 --end 10
      vibegame art v2f video.mp4 -o frames/ --sample all
      vibegame art v2f video.mp4 -o frames/ --preview
      vibegame art v2f video.mp4 -o frames/ --loop
    """
    video_path = Path(video)
    if not video_path.exists():
        print(f"Video file not found: {video}")
        raise typer.Exit(1)

    converter = Video2Frames()

    try:
        print("Extracting video frames...")
        frame_count, output_dir = converter.extract_frames(
            video_path=video,
            output_dir=output,
            fps=fps,
            start_time=start,
            end_time=end,
            prefix=prefix,
            sample=sample,
            diff_threshold=diff_threshold,
            loop=loop,
            preview=preview,
        )

        print("=== Video to Frames Result ===")
        print("Done!")
        print(f"Output: {output_dir}")
        print(f"Frames extracted: {frame_count}")
        print(f"Prefix: {prefix}")

    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(1)
