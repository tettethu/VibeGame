"""
Mini-agent for automatic background removal.

Usage:
    vibegame art rmbg xxx.png --agent -o output.png

Pipeline:
    tools = [rmbg, analyze, finish]
    Each round: responses.create(instructions, origin_image, current_image, action_history)
    Agent decides tool calls until finish or max iterations.

Uses OpenAI Response API with native tool calling.
Working dir: <git_root>/.vibegame/logs/rmbg/<session_id>.*
"""

import json
import os
import shutil
import subprocess
import uuid
import base64
from pathlib import Path
from typing import Optional

from openai import OpenAI

from .rmbg import remove_bg
from .analyze import analyze_image


DEFAULT_MODEL = "gpt-5.5"
MAX_ITERATIONS = 15

SYSTEM_PROMPT = """\
You are a background removal specialist for game sprite assets.

Goal: Remove the solid background color from the input image, producing a transparent-background PNG.

## Tools
- analyze: Get color distribution. Use once at start, and once after rmbg to verify.
- rmbg: Remove background. Operates on the current working image.
- finish: Declare done. Call as soon as the large background regions are removed.

## Strategy (follow this order)
1. analyze — identify the dominant background color and its RGB value
2. rmbg with seeds=["corner"], ONE color center, tolerance 40-55, metric=rgb — flood fill removes the main connected background
3. LOOK at the current image carefully. Do NOT call analyze again — it only sees visible pixels, so after removal it misleadingly reports "no background".
   Visually check for ANY remaining colored patches, especially:
   - Shadows under sprites (darker shade of background color)
   - Background "islands" trapped inside VFX (e.g. magenta visible through gaps in a swirl/wave/explosion effect)
   - Grid cell backgrounds in sprite sheets
   If clean → finish. If patches remain → cleanup pass:
   → rmbg with colors=[bg_color] + seeds=["match:10"] + tolerance 50-80 + metric=hsv
   match:T finds near-background pixels as flood seeds, then flood fills connected regions ONLY.
   This is SAFE: foreground pixels that share the background hue (pink tongue, skin tones, colored clothing) are preserved because they are not connected to background regions.
   Do NOT use global replace (no seeds) with hsv — it deletes ANY pixel matching the hue regardless of position, destroying foreground content.
4. Look at image again → finish, or one more targeted pass → finish.

## Rules
- **PRIORITY: Preserving sprite content > removing all background.** A few residual background pixels at edges are acceptable. Destroying foreground pixels (skin, tongue, clothing, weapons, FX) is NOT acceptable. When in doubt, use lower tolerance and leave minor residue.
- Use ONE representative color with sufficient tolerance. Do NOT list multiple similar RGB values.
- Call analyze ONCE at the start. After that, judge by looking at the images.
- After the first rmbg, do a cleanup pass with match:T if you see remaining patches. But do NOT over-clean — if the cleanup would risk eating into foreground, skip it and finish.
- Typical budget: 3-5 steps (analyze → rmbg corner → rmbg cleanup → finish).

## rmbg modes
- seeds=["corner"] (default): sample color from 4 corners, flood fill connected regions — best for solid backgrounds
- colors only (no seeds): global replace — removes ALL matching pixels regardless of position
- colors + seeds=["match"]: use color-matching pixels as flood seeds — good for fragmented backgrounds

## Image context
Each round you see: original input (never changes) + current working state (updated after rmbg).
"""


def _build_system_prompt(tips: str | None = None) -> str:
    tips = (tips or "").strip()
    if not tips:
        return SYSTEM_PROMPT
    return f"{SYSTEM_PROMPT.rstrip()}\n\n## Extra tips\n{tips}\n"


TOOLS = [
    {
        "type": "function",
        "name": "rmbg",
        "description": "Remove background colors by making them transparent. Operates on the current working image.",
        "parameters": {
            "type": "object",
            "properties": {
                "tolerance": {
                    "type": "integer",
                    "description": "Color distance tolerance (0=exact match). Start low (10-20), increase if needed.",
                },
                "colors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Target colors as 'R,G,B' strings (e.g. '255,0,255'). Omit to sample from seeds.",
                },
                "seeds": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Seed points: 'corner' (all 4 corners), 'tl'/'tr'/'bl'/'br', 'x,y', 'match' (exact color pixels as flood seeds, requires colors), 'match:T' (pixels within tolerance T of color as flood seeds — good for cleaning isolated patches with color variation). Default: corner.",
                },
                "metric": {
                    "type": "string",
                    "enum": ["rgb", "hsv", "cosine"],
                    "description": "Color distance metric. rgb=euclidean (default), hsv=hue-dominant, cosine=angular (ignores brightness).",
                },
                "defringe": {
                    "type": "integer",
                    "description": "Fix edge color fringe within N pixels after removal. 0=disabled.",
                },
            },
        },
    },
    {
        "type": "function",
        "name": "analyze",
        "description": "Analyze color distribution of the current working image. Returns dominant colors, background guess, and transparency info.",
        "parameters": {
            "type": "object",
            "properties": {
                "top": {
                    "type": "integer",
                    "description": "Number of dominant colors to report. Default 10.",
                },
            },
        },
    },
    {
        "type": "function",
        "name": "finish",
        "description": "Declare background removal complete. Call only when the background has been fully removed.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
]


def _git_root() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return os.getcwd()


def _flatten_to_bg(path: str, bg_color: tuple[int, int, int] = (255, 255, 255)) -> bytes:
    """Composite RGBA onto solid color so transparent pixels don't leak residual BGR. bg_color is (B, G, R)."""
    import cv2
    import numpy as np
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is not None and len(img.shape) == 3 and img.shape[2] == 4:
        alpha = img[:, :, 3:4] / 255.0
        bgr = img[:, :, :3]
        bg = np.full_like(bgr, 0)
        bg[:, :, 0] = bg_color[0]
        bg[:, :, 1] = bg_color[1]
        bg[:, :, 2] = bg_color[2]
        flat = (bgr * alpha + bg * (1 - alpha)).astype(np.uint8)
        _, buf = cv2.imencode(".png", flat)
        return buf.tobytes()
    with open(path, "rb") as f:
        return f.read()


def _image_content(path: str, bg_color: tuple[int, int, int] = (255, 255, 255)) -> dict:
    data = _flatten_to_bg(path, bg_color)
    b64 = base64.b64encode(data).decode()
    return {
        "type": "input_image",
        "image_url": f"data:image/png;base64,{b64}",
    }


def _build_input(raw_path: str, now_path: str, history: list[dict]) -> list:
    history_text = "Action history:\n"
    if not history:
        history_text += "(none yet — this is the first step)\n"
    else:
        for entry in history:
            history_text += f"- Step {entry['step']}: {entry['tool']}({json.dumps(entry['args'], ensure_ascii=False)}) -> {entry['result_summary']}\n"

    return [{
        "role": "user",
        "content": [
            {"type": "input_text", "text": history_text},
            {"type": "input_text", "text": "Original input image:"},
            _image_content(raw_path),
            {"type": "input_text", "text": "Current working image:"},
            _image_content(now_path),
        ],
    }]


def _execute_rmbg(now_path: str, last_path: str, args: dict) -> str:
    shutil.copy2(now_path, last_path)
    try:
        remove_bg(
            image_path=now_path,
            tolerance=args.get("tolerance", 0),
            colors=args.get("colors"),
            seeds=args.get("seeds"),
            metric=args.get("metric", "rgb"),
            defringe=args.get("defringe", 0),
            inplace=True,
        )
        return "Applied. Check current image for result."
    except Exception as e:
        shutil.copy2(last_path, now_path)
        return f"Error: {e}"


def _execute_analyze(now_path: str, args: dict) -> str:
    try:
        result = analyze_image(
            image_path=now_path,
            top=args.get("top", 10),
        )
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return f"Error: {e}"


def run_rmbg_agent(
    image_path: str,
    output_path: str,
    model: str | None = None,
    max_iterations: int = MAX_ITERATIONS,
    tips: str | None = None,
) -> str:
    from util.env import load_unified_env
    load_unified_env()

    model = model or os.environ.get("RMBG_AGENT_MODEL") or os.environ.get("VLM_MODEL") or DEFAULT_MODEL
    api_key = os.environ.get("VLM_API_KEY")
    base_url = os.environ.get("VLM_BASE_URL")
    if not api_key:
        raise ValueError("VLM_API_KEY not set")
    if not base_url:
        raise ValueError("VLM_BASE_URL not set")

    root = _git_root()
    log_dir = Path(root) / ".vibegame" / "logs" / "rmbg"
    log_dir.mkdir(parents=True, exist_ok=True)

    session_id = uuid.uuid4().hex[:12]
    raw_path = str(log_dir / f"{session_id}.raw.png")
    last_path = str(log_dir / f"{session_id}.last.png")
    now_path = str(log_dir / f"{session_id}.now.png")
    log_path = str(log_dir / f"{session_id}.jsonl")

    shutil.copy2(image_path, raw_path)
    shutil.copy2(image_path, now_path)

    client = OpenAI(api_key=api_key, base_url=base_url)
    history: list[dict] = []
    system_prompt = _build_system_prompt(tips)

    print(f"rmbg-agent session={session_id} model={model} max_iter={max_iterations}")
    print(f"  transcript: {log_path}")
    print(f"  raw (input copy): {raw_path}")
    print(f"  now (updated each rmbg): {now_path}")
    print(f"  last (previous step backup): {last_path}")
    print(f"  transcript: {log_path}")

    for step in range(1, max_iterations + 1):
        print(f"  step {step}/{max_iterations}...")

        input_list = _build_input(raw_path, now_path, history)

        try:
            response = client.responses.create(
                model=model,
                instructions=system_prompt,
                tools=TOOLS,
                input=input_list,
            )
        except Exception as e:
            print(f"    API error: {e}")
            raise

        if not hasattr(response, "output"):
            print(f"    unexpected response type: {type(response)}")
            raise RuntimeError(f"Response API returned {type(response).__name__} instead of Response object")

        # Take the first function_call from the response
        call = None
        for item in response.output:
            if item.type == "function_call":
                call = item
                break

        if call is None:
            text = getattr(response, "output_text", "")
            print(f"    (no tool call: {text[:120]})")
            continue

        tool_name = call.name
        args = json.loads(call.arguments) if call.arguments else {}

        if tool_name == "finish":
            entry = {"step": step, "tool": "finish", "args": {}, "result_summary": "done"}
            history.append(entry)
            with open(log_path, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(now_path, output_path)
            print(f"  done at step {step} -> {output_path}")
            return output_path

        if tool_name == "rmbg":
            result_summary = _execute_rmbg(now_path, last_path, args)
        elif tool_name == "analyze":
            result_summary = _execute_analyze(now_path, args)
        else:
            result_summary = f"Unknown tool: {tool_name}"

        entry = {"step": step, "tool": tool_name, "args": args, "result_summary": result_summary}
        history.append(entry)
        with open(log_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        print(f"    {tool_name}({json.dumps(args)}) -> {result_summary[:100]}")

    raise RuntimeError(f"rmbg-agent exceeded {max_iterations} iterations without finishing")
