"""Seedance video generation CLI.

Usage
    # Env: VIDEO_API_KEY (required)
    #      VIDEO_BASE_URL (optional; defaults to the official seedance endpoint)
    # Loaded by priority: shell > <game_project_git_root>/.env > <source_code_git_root>/.env

    vibegame gen video -t "<text>" -i <image> [-i <image>...] -o <output.mp4>
    vibegame gen video -t prompt.txt -i <image> -o <output.mp4> --mode first_last
    vibegame gen video --query <task_id>            # resume polling + download
    vibegame gen video --query                      # list pending tasks, error out

    # Standalone (debug):
    python videogen.py -t "..." -o out.mp4
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

import requests
import typer

# Let 'python videogen.py' work standalone by adding src/ to sys.path
_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from util.prompt import UnsupportedPromptFileFormat, load_prompt


# === Defaults ===

DEFAULTS = {
    "model": "seedance-2.0",
    "mode": "reference",
    "resolution": "720p",
    "ratio": "adaptive",
    "duration": 5,
    "generate_audio": True,
    "watermark": False,
    "seed": -1,
    "save_last_frame": True,
    "poll_interval_sec": 10,
    "progress_every_n_polls": 6,  # 6 * 10s = 1 min
}

MODEL_MAP = {
    "seedance-2.0": "doubao-seedance-2-0-260128",
    "seedance-2.0-fast": "doubao-seedance-2-0-fast-260128",
}

MODE_IMAGE_COUNTS = {
    "reference": (1, 9),       # min, max
    "first_last": (1, 2),
}

SIZE_LIMIT_PER_IMAGE_MB = 30
SIZE_LIMIT_REQUEST_MB = 64

DEFAULT_VIDEO_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"

_QUERY_LIST_SENTINEL = "__LIST_PENDING__"

app = typer.Typer(add_completion=False)


# === Env, paths ===

def _load_env():
    from util.env import load_unified_env
    load_unified_env()


def _vibegame_root() -> Path:
    from util.env import get_vibegame_root
    root = get_vibegame_root()
    if root is None:
        print("Not inside a git repo, and source code root not resolvable. "
              "Cannot locate .vibegame/logs directory.")
        raise typer.Exit(1)
    return root


def _logs_dir() -> Path:
    p = _vibegame_root() / ".vibegame" / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _jsonl_path() -> Path:
    return _logs_dir() / "videogen.jsonl"


def _jsonl_append(entry: dict):
    with _jsonl_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _jsonl_latest_by_id(task_id: str) -> Optional[dict]:
    p = _jsonl_path()
    if not p.exists():
        return None
    latest = None
    for raw in p.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if e.get("task_id") == task_id:
            latest = e
    return latest


def _jsonl_list_pending() -> list[dict]:
    p = _jsonl_path()
    if not p.exists():
        return []
    latest: dict[str, dict] = {}
    for raw in p.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(raw)
        except json.JSONDecodeError:
            continue
        tid = e.get("task_id")
        if tid:
            latest[tid] = e
    terminal = {"succeeded", "failed", "expired"}
    return [e for e in latest.values() if e.get("status") not in terminal]


# === Image handling ===

def _mime(path: str) -> str:
    suffix = Path(path).suffix.lower().lstrip(".")
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "bmp": "image/bmp",
        "tiff": "image/tiff",
        "gif": "image/gif",
    }.get(suffix, "image/png")


def _encode_image(path: str) -> str:
    """Return data URL for a local image; fails loudly on size limit."""
    p = Path(path)
    if not p.is_file():
        print(f"Image not found: {path}")
        raise typer.Exit(1)
    size = p.stat().st_size
    if size > SIZE_LIMIT_PER_IMAGE_MB * 1024 * 1024:
        print(f"Image {path} is {size / 1024 / 1024:.1f}MB, "
              f"exceeds seedance single-image limit {SIZE_LIMIT_PER_IMAGE_MB}MB")
        raise typer.Exit(1)
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"data:{_mime(str(p))};base64,{b64}"


def _build_content(text: Optional[str], images: list[str], mode: str) -> list[dict]:
    content: list[dict] = []
    if text:
        content.append({"type": "text", "text": text})

    lo, hi = MODE_IMAGE_COUNTS[mode]
    if not (lo <= len(images) <= hi):
        print(f"--mode {mode} requires {lo}-{hi} images, got {len(images)}")
        raise typer.Exit(1)

    if mode == "reference":
        for img in images:
            content.append({
                "type": "image_url",
                "image_url": {"url": _encode_image(img)},
                "role": "reference_image",
            })
    elif mode == "first_last":
        content.append({
            "type": "image_url",
            "image_url": {"url": _encode_image(images[0])},
            "role": "first_frame",
        })
        if len(images) == 2:
            content.append({
                "type": "image_url",
                "image_url": {"url": _encode_image(images[1])},
                "role": "last_frame",
            })

    if not content:
        print("Need at least -t/--text or -i/--input")
        raise typer.Exit(1)
    return content


def _check_request_size(payload: dict):
    size = len(json.dumps(payload).encode("utf-8"))
    if size > SIZE_LIMIT_REQUEST_MB * 1024 * 1024:
        print(f"Request body {size / 1024 / 1024:.1f}MB exceeds seedance "
              f"request limit {SIZE_LIMIT_REQUEST_MB}MB")
        raise typer.Exit(1)


# === API ===

def _api_base_and_key() -> tuple[str, str]:
    base = (os.environ.get("VIDEO_BASE_URL") or DEFAULT_VIDEO_BASE_URL).rstrip("/")
    key = os.environ.get("VIDEO_API_KEY", "")
    if not key:
        print("VIDEO_API_KEY not set")
        raise typer.Exit(1)
    return base, key


def _api_submit(payload: dict) -> tuple[Optional[str], Optional[str]]:
    """Returns (task_id, error). On success: (task_id, None). On failure: (None, error_message)."""
    base, key = _api_base_and_key()
    resp = requests.post(
        base,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=None,
    )
    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code} | body={resp.text[:500]}"
    body = resp.json()
    task_id = body.get("id")
    if not task_id:
        return None, f"submit returned no task id: {body}"
    return task_id, None


def _api_query(task_id: str) -> dict:
    base, key = _api_base_and_key()
    url = f"{base}/{task_id}"
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {key}"},
        timeout=None,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Query HTTP {resp.status_code} | body={resp.text[:500]}")
    return resp.json()


def _download(url: str, dest: Path):
    print(f"Downloading to {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=None, stream=True)
    if resp.status_code != 200:
        print(f"Download failed: HTTP {resp.status_code}")
        raise typer.Exit(1)
    with dest.open("wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
    print(f"Saved: {dest}")


# === Polling ===

def _poll_and_finalize(task_id: str, output: Path, save_last_frame: bool):
    print(f"Polling task {task_id} (every {DEFAULTS['poll_interval_sec']}s)...")
    t0 = time.time()
    polls = 0
    while True:
        polls += 1
        try:
            result = _api_query(task_id)
        except Exception as e:
            print(f"[warn] {e}; retrying in {DEFAULTS['poll_interval_sec']}s")
            time.sleep(DEFAULTS["poll_interval_sec"])
            continue

        status = result.get("status")
        elapsed = int(time.time() - t0)

        if status == "succeeded":
            content = result.get("content") or {}
            video_url = content.get("video_url")
            last_frame_url = content.get("last_frame_url")
            usage = result.get("usage")
            _jsonl_append({
                "task_id": task_id,
                "status": "succeeded",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "video_url": video_url,
                "last_frame_url": last_frame_url,
                "usage": usage,
                "output": str(output),
                "save_last_frame": save_last_frame,
            })
            print(f"Task succeeded in {elapsed}s")
            if not video_url:
                print("API returned no video_url")
                raise typer.Exit(1)
            _download(video_url, output)
            if save_last_frame:
                if last_frame_url:
                    lf = output.with_name(output.stem + "_last_frame.png")
                    _download(last_frame_url, lf)
                else:
                    print("[warn] --save-last-frame requested but API returned no last_frame_url")
            return

        if status in ("failed", "expired"):
            err = result.get("error")
            _jsonl_append({
                "task_id": task_id,
                "status": status,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "error": err,
                "output": str(output),
            })
            print(f"Task {status}: {err}")
            raise typer.Exit(1)

        # queued or running
        if polls % DEFAULTS["progress_every_n_polls"] == 0:
            print(f"Waiting for {elapsed} seconds... (status={status})")
        time.sleep(DEFAULTS["poll_interval_sec"])


# === CLI ===

def cmd_video(
    output: Annotated[Optional[Path], typer.Option("-o", "--output",
            help="Output .mp4 path (required for submit).")] = None,
    text: Annotated[Optional[str], typer.Option("-t", "--text",
            help="Prompt text or path to a .txt/.md file")] = None,
    input_images: Annotated[list[str], typer.Option("-i", "--input",
            help="Reference image path (repeat for multiple).")] = [],
    model: Annotated[str, typer.Option("-m", "--model",
            help=f"One of: {list(MODEL_MAP.keys())}")] = DEFAULTS["model"],
    mode: Annotated[str, typer.Option("--mode",
            help=f"One of: {list(MODE_IMAGE_COUNTS.keys())}. "
                 f"reference: 1-9 images. first_last: 1 (first only) or 2 (first+last).")] = DEFAULTS["mode"],
    resolution: Annotated[str, typer.Option("--resolution",
            help="480p | 720p | 1080p")] = DEFAULTS["resolution"],
    ratio: Annotated[str, typer.Option("--ratio",
            help="16:9 | 4:3 | 1:1 | 3:4 | 9:16 | 21:9 | adaptive")] = DEFAULTS["ratio"],
    duration: Annotated[int, typer.Option("--duration",
            help="Seconds, [4,15] for seedance 2.0, or -1 for auto")] = DEFAULTS["duration"],
    generate_audio: Annotated[bool, typer.Option("--generate-audio/--no-generate-audio")] = DEFAULTS["generate_audio"],
    watermark: Annotated[bool, typer.Option("--watermark/--no-watermark")] = DEFAULTS["watermark"],
    seed: Annotated[int, typer.Option("--seed",
            help="-1 for random")] = DEFAULTS["seed"],
    save_last_frame: Annotated[bool, typer.Option("--save-last-frame/--no-save-last-frame",
            help="Also download the video's last frame as <output>_last_frame.png")] = DEFAULTS["save_last_frame"],
    query: Annotated[Optional[str], typer.Option("--query",
            help="Resume polling an existing task by id. Pass '--query' alone to list pending.")] = None,
):
    """Submit a video generation task, poll until done, download result.

    With --query <task_id>, resume polling a previously submitted task instead.
    """
    _load_env()

    # --- Query / resume mode ---
    if query is not None:
        if query == _QUERY_LIST_SENTINEL:
            pending = _jsonl_list_pending()
            if not pending:
                print("No pending tasks in videogen.jsonl")
                raise typer.Exit(1)
            print("--query requires a task id. Pending tasks:")
            for e in pending:
                print(f"  {e['task_id']:40s} status={e.get('status')} "
                      f"output={e.get('output')}")
            raise typer.Exit(1)

        entry = _jsonl_latest_by_id(query)
        if entry is None:
            print(f"Task id not found in {_jsonl_path()}: {query}")
            raise typer.Exit(1)
        status = entry.get("status")
        if status in ("succeeded", "failed", "expired"):
            print(f"Task {query} is already terminal (status={status}); nothing to do")
            raise typer.Exit(0 if status == "succeeded" else 1)
        out = Path(entry["output"])
        slf = bool(entry.get("save_last_frame", DEFAULTS["save_last_frame"]))
        _poll_and_finalize(query, out, slf)
        return

    # --- Submit mode ---
    if output is None:
        print("--output is required when submitting")
        raise typer.Exit(1)
    if output.suffix.lower() != ".mp4":
        print(f"--output must end with .mp4, got '{output.suffix}'")
        raise typer.Exit(1)

    # Resolve prompt (auto-detects file path vs literal text)
    if text:
        try:
            text = load_prompt(text)
        except UnsupportedPromptFileFormat as e:
            print(f"Error: {e}")
            raise typer.Exit(1)

    if model not in MODEL_MAP:
        print(f"Unknown --model '{model}'. Supported: {list(MODEL_MAP.keys())}")
        raise typer.Exit(1)
    if mode not in MODE_IMAGE_COUNTS:
        print(f"Unknown --mode '{mode}'. Supported: {list(MODE_IMAGE_COUNTS.keys())}")
        raise typer.Exit(1)

    if not text and not input_images:
        print("Provide at least -t/--text or -i/--input")
        raise typer.Exit(1)
    if not input_images:
        print("Video generation requires at least 1 reference image (-i). Pure text-to-video is not supported.")
        raise typer.Exit(1)

    content = _build_content(text, list(input_images), mode)
    payload = {
        "model": MODEL_MAP[model],
        "content": content,
        "resolution": resolution,
        "ratio": ratio,
        "duration": duration,
        "generate_audio": generate_audio,
        "watermark": watermark,
        "seed": seed,
        "return_last_frame": save_last_frame,
    }
    _check_request_size(payload)

    out_abs = output.resolve()
    request_record = {
        "model": MODEL_MAP[model],
        "mode": mode,
        "prompt": text,
        "images": [str(Path(p).resolve()) for p in input_images],
        "resolution": resolution,
        "ratio": ratio,
        "duration": duration,
        "generate_audio": generate_audio,
        "watermark": watermark,
        "seed": seed,
    }

    task_id, err = _api_submit(payload)
    if err is not None:
        _jsonl_append({
            "task_id": None,
            "status": "submit_failed",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "output": str(out_abs),
            "save_last_frame": save_last_frame,
            "request": request_record,
            "error": err,
        })
        print(f"Submit failed: {err}")
        raise typer.Exit(1)

    print(f"Submitted: {task_id}")
    _jsonl_append({
        "task_id": task_id,
        "status": "submitted",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "output": str(out_abs),
        "save_last_frame": save_last_frame,
        "request": request_record,
        "error": None,
    })

    _poll_and_finalize(task_id, output, save_last_frame)


def _preprocess_argv():
    """Allow '--query' with no value to trigger the listing hint.

    Runs at import time so it works both standalone and when registered under
    a parent typer app (vibegame art videogen).
    """
    argv = sys.argv
    for i, a in enumerate(argv):
        if a == "--query":
            if i + 1 == len(argv) or argv[i + 1].startswith("-"):
                argv.insert(i + 1, _QUERY_LIST_SENTINEL)
            break


_preprocess_argv()

app.command()(cmd_video)


if __name__ == "__main__":
    app()
