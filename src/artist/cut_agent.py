"""
Mini-agent for automatic sprite detection and bbox extraction.

Usage:
    vibegame art cut xxx.png --agent -o output.json

Pipeline:
    tools = [cut_detect, label_bbox, finish, fail]
    Each round: responses.create(instructions, original_image, preview_image, bbox_data)
    Agent adjusts min_area or manually specifies bboxes until correct, then finish or fail.

Overlap detection: if any two sprite bboxes overlap, agent reports fail (sprite bleed).
"""

import json
import os
import shutil
import subprocess
import uuid
import base64
import cv2
import numpy as np
from pathlib import Path
from typing import Optional

from openai import OpenAI

from .cut import SpriteCutter
from .label import render_label


DEFAULT_MODEL = "gpt-5.5"
MAX_ITERATIONS = 15

SYSTEM_PROMPT = """\
You are a sprite detection specialist for game sprite sheets.

Goal: Identify all individual sprites/frames in the image and output their bounding boxes. Detect if any sprites have overlapping bboxes (sprite bleed).

## Tools
- cut_detect: Auto-detect sprites using connected components with adjustable min_area. Sets current bboxes + generates labeled preview.
- label_bbox: Update current bboxes. Provide ALL bboxes (keep unchanged ones as-is, modify the ones that need fixing). Generates new preview.
- finish: Submit current bboxes as final answer. Takes no arguments — submits whatever the current bboxes are. System auto-checks for overlap; if rejected, adjust via label_bbox.
- fail: Report sprite bleed — two sprites' bboxes overlap and cannot be cleanly separated. Tells upstream to regenerate.

## Workflow — DO NOT skip step 2
1. cut_detect → sets initial bboxes, generates preview
2. **CRITICAL: After cut_detect, you MUST do at least one verification step before finish.** Never go straight from cut_detect to finish. Either:
   - call label_bbox to re-render the preview for inspection (even with the same bboxes — this forces you to visually examine each bbox), OR
   - call fail if you spot bleed
   The agent that goes cut_detect → finish in 2 steps has FAILED its job.
3. Look at the new preview. If bboxes need fixing → label_bbox with corrections. Repeat as needed.
4. **Pre-finish checklist (run through every item EVERY time)**:
   - (a) Does each frame have exactly one bbox? Matches expected count?
   - (b) Does each bbox contain only ONE frame's content?
   - (c) **Edge-bleed check**: Scan the boundary between every pair of adjacent bboxes. Look at the sprite content right next to the edge. Common bleed patterns:
       - A sword tip from frame A pokes into frame B's bbox
       - An extended arm/leg from frame A reaches into frame B's bbox
       - Hair/cloak/FX trail crosses the bbox boundary
       - Look especially when bboxes are very close (small gap) — connected components cuts at transparent gaps, so a sword crossing a 2px gap WILL be split into two halves, leaving one half visible in frame B's bbox
   - (d) If any "yes" to bleed → call fail with reason "frame #N's [weapon/arm/leg/hair] extends into frame #M's bbox region"
   - (e) If bleed is fixable by merging same-frame components → label_bbox to merge
5. Only after running through the checklist explicitly → finish

## Strategy
- Start with cut_detect at default min_area (5000).
- If fragments (small FX pieces as separate sprites): increase min_area and re-run cut_detect
- If sprites merged into one bbox: decrease min_area and re-run cut_detect
- If two nearby components belong to the SAME frame (character + kicked ball, character + detached FX): use label_bbox to merge into one bbox
- If bboxes don't tightly fit the sprites: use label_bbox to adjust
- If different frames truly overlap and cannot be separated → call fail

## How to identify frames in a sprite sheet
A sprite sheet arranges frames in a grid or row. Components in the same grid cell belong to the same frame, even if disconnected (separate connected components). Clues:
- Components that are vertically aligned and close together → same frame
- Components whose bboxes overlap or nearly touch, in the same column/row region → same frame
- The expected frame count matches the visual grid layout (e.g. 3 columns = 3 frames, 2x2 grid = 4 frames)

When merging: compute the union bbox that covers ALL components in the frame's region — including small scattered FX particles and fragments. The merged bbox must contain every visible pixel in that frame's grid cell. Example: if component A is at (100,200,50,80) and component B is at (130,300,60,40), the merged bbox is (100,200,90,140).

After merging, verify the bbox by checking the cut_detect results: every detected component whose center falls within a frame's grid region must be inside that frame's bbox. If any component is partially outside, expand the bbox.

## Rules
- Each animation frame gets exactly ONE bbox (may contain multiple disconnected parts).
- For single-sprite images, detect 1 bbox and finish quickly.
- **Bbox precision**: bboxes MUST be pixel-tight to sprite content — no extra padding, not even 1px gap. When merging, compute the exact union. When adjusting, ensure the bbox tightly wraps all visible pixels of that frame.
- cut_detect gives a good starting point but is not always perfect — sometimes you need to expand a bbox to include missed FX fragments, or merge overlapping components. Use label_bbox to adjust.
- Finish auto-checks for overlap. If rejected, adjust via label_bbox (merge same-frame bboxes) or call fail (true bleed).
- NEVER shrink a bbox to resolve overlap — that cuts off sprite content. Either merge (same frame) or fail (true bleed).

## Two kinds of sprite bleed (both call fail)
1. **BBox overlap**: two frames' bboxes literally share pixel area. Caught by the finish auto-check.
2. **Content cross-bbox**: bboxes do NOT overlap, but one frame's content (sword, weapon, extended arm, kicking leg, flowing hair) physically extends into another frame's bbox region. This means: after cutting along the bbox, the adjacent frame's image would contain leftover pixels from the previous frame.
   - **You MUST visually check this before finish.** Look at each bbox edge in the preview:
     - Is there any sprite content (weapon, arm, leg, hair, FX) at the bbox edge?
     - Does that content visibly extend beyond the bbox into the neighbor's bbox area?
   - If yes → call fail with reason like "frame #N's [weapon/arm/leg] extends into frame #M's bbox region".
   - Connected-components cuts at transparent gaps, but if a sword crosses a 2px transparent gap, both halves get detected — making the bboxes "not overlap" while content clearly bleeds.

## True sprite bleed
Content from different frames physically overlaps OR extends across bbox boundaries so cutting will produce dirty frames. Both cases require regeneration — call fail.

## Image context
Each round you see: original image + latest preview (with bbox annotations drawn on it).
If no preview exists yet (first round), only the original image is shown.

## Expected frame count
{expected_frames_hint}
"""


def _append_extra_tips(prompt: str, tips: str | None) -> str:
    tips = (tips or "").strip()
    if not tips:
        return prompt
    return f"{prompt.rstrip()}\n\n## Extra tips\n{tips}\n"


def _build_system_prompt(expected_frames: int | None, tips: str | None = None) -> str:
    if expected_frames is not None:
        hint = f"Expected frames: {expected_frames}. Your final bbox count MUST match this number. If auto-detect finds a different count, adjust (merge or split) until the count matches."
    else:
        hint = "Not specified — you need to decide the frame count yourself based on the visual layout."
    return _append_extra_tips(SYSTEM_PROMPT.format(expected_frames_hint=hint), tips)

TOOLS = [
    {
        "type": "function",
        "name": "cut_detect",
        "description": "Auto-detect sprites using connected components. Returns detected bboxes as JSON and saves a preview with numbered green bboxes on the image.",
        "parameters": {
            "type": "object",
            "properties": {
                "min_area": {
                    "type": "integer",
                    "description": "Minimum pixel area for a component to count as a sprite. Default 900. Increase to merge fragments, decrease to catch small sprites.",
                },
            },
        },
    },
    {
        "type": "function",
        "name": "label_bbox",
        "description": "Adjust bboxes based on cut_detect results. Provide ALL bboxes: keep correct ones unchanged, modify the ones that need fixing (merge, expand, etc.). Draws them on the image for verification.",
        "parameters": {
            "type": "object",
            "properties": {
                "bboxes": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 4,
                        "maxItems": 4,
                        "description": "[x, y, w, h]",
                    },
                    "description": "List of bounding boxes as [x, y, w, h] arrays.",
                },
                "reason": {
                    "type": "string",
                    "description": "Why this adjustment is needed (e.g. 'merge #2 and #3 — same frame', 'expand #1 to include missed FX particles').",
                },
            },
            "required": ["bboxes", "reason"],
        },
    },
    {
        "type": "function",
        "name": "finish",
        "description": "Submit the current bboxes as final answer. The system will verify no overlap — if overlap is found, finish is rejected and you must adjust via label_bbox.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "type": "function",
        "name": "fail",
        "description": "Report sprite bleed — sprites overlap and cannot be cleanly separated. Signals upstream to regenerate the image.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Which sprites overlap and how.",
                },
            },
            "required": ["reason"],
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
    """Composite RGBA onto solid color for LLM consumption. bg_color is (B, G, R)."""
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is not None and len(img.shape) == 3 and img.shape[2] == 4:
        flat = _flatten_rgba(img, bg_color)
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


def _build_input(raw_path: str, preview_path: str | None, current_bboxes: list, history: list[dict], bg_color: tuple[int, int, int] = (255, 255, 255)) -> list:
    history_text = "Action history:\n"
    if not history:
        history_text += "(none yet — first step)\n"
    else:
        for entry in history:
            history_text += f"- Step {entry['step']}: {entry['tool']}({json.dumps(entry['args'], ensure_ascii=False)}) -> {entry['result_summary'][:200]}\n"

    if current_bboxes:
        history_text += f"\nCurrent bboxes ({len(current_bboxes)}):\n"
        for i, bb in enumerate(current_bboxes):
            x, y, w, h = _unpack_bbox(bb)
            history_text += f"  #{i}: [{x}, {y}, {w}, {h}]\n"

    content = [
        {"type": "input_text", "text": history_text},
        {"type": "input_text", "text": "Original image (transparent areas shown as solid background):"},
        _image_content(raw_path, bg_color),
    ]

    if preview_path and Path(preview_path).exists():
        content.append({"type": "input_text", "text": "Current preview (with bbox annotations):"})
        content.append(_image_content(preview_path, bg_color))

    return [{"role": "user", "content": content}]


def _flatten_rgba(image: np.ndarray, bg_color: tuple[int, int, int] = (255, 255, 255)) -> np.ndarray:
    """Composite RGBA onto solid color, return BGR. bg_color is (B, G, R)."""
    if len(image.shape) == 3 and image.shape[2] == 4:
        alpha = image[:, :, 3:4] / 255.0
        bgr = image[:, :, :3]
        bg = np.full_like(bgr, 0)
        bg[:, :, 0] = bg_color[0]
        bg[:, :, 1] = bg_color[1]
        bg[:, :, 2] = bg_color[2]
        return (bgr * alpha + bg * (1 - alpha)).astype(np.uint8)
    return image[:, :, :3] if len(image.shape) == 3 else image


def _draw_preview(raw_path: str, preview_path: str, bboxes: list, bg_color: tuple[int, int, int] = (255, 255, 255), keep_alpha: bool = True):
    image = cv2.imread(raw_path, cv2.IMREAD_UNCHANGED)
    if image is None:
        return
    has_alpha = len(image.shape) == 3 and image.shape[2] == 4
    alpha_channel = image[:, :, 3].copy() if has_alpha else None

    preview = _flatten_rgba(image, bg_color)
    for idx, bb in enumerate(bboxes):
        x, y, w, h = _unpack_bbox(bb)
        cv2.rectangle(preview, (x, y), (x + w, y + h), (0, 200, 0), 2)
        cv2.putText(preview, f"#{idx}", (x + 4, y + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 2)

    if keep_alpha and alpha_channel is not None:
        preview_rgba = cv2.cvtColor(preview, cv2.COLOR_BGR2BGRA)
        # keep bbox stroke areas (drawn on the background color) opaque
        bbox_mask = np.zeros_like(alpha_channel)
        for bb in bboxes:
            x, y, w, h = _unpack_bbox(bb)
            cv2.rectangle(bbox_mask, (x, y), (x + w, y + h), 255, 2)
            cv2.putText(bbox_mask, f"#{0}", (x + 4, y + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, 255, 2)
        preview_rgba[:, :, 3] = np.maximum(alpha_channel, bbox_mask)
        cv2.imwrite(preview_path, preview_rgba)
    else:
        cv2.imwrite(preview_path, preview)


def _check_overlap(bboxes: list) -> list[tuple[int, int]]:
    overlaps = []
    for i in range(len(bboxes)):
        for j in range(i + 1, len(bboxes)):
            ax, ay, aw, ah = _unpack_bbox(bboxes[i])
            bx, by, bw, bh = _unpack_bbox(bboxes[j])
            if (ax < bx + bw and ax + aw > bx and
                ay < by + bh and ay + ah > by):
                overlaps.append((i, j))
    return overlaps


def _unpack_bbox(bb) -> tuple[int, int, int, int]:
    if isinstance(bb, (list, tuple)):
        return bb[0], bb[1], bb[2], bb[3]
    return bb["x"], bb["y"], bb["w"], bb["h"]


def _execute_cut_detect(raw_path: str, preview_path: str, args: dict, bg_color: tuple[int, int, int] = (255, 255, 255)) -> tuple[list, str]:
    min_area = args.get("min_area", 5000)
    cutter = SpriteCutter(min_area=min_area)

    image = cv2.imread(raw_path, cv2.IMREAD_UNCHANGED)
    if image is None:
        return [], f"Error: cannot read {raw_path}"

    mask = cutter._create_mask(image)
    bboxes_raw = cutter._find_sprites(mask, image, min_area)

    preview_img = _flatten_rgba(image, bg_color)
    for idx, (x, y, w, h) in enumerate(bboxes_raw):
        cv2.rectangle(preview_img, (x, y), (x + w, y + h), (0, 200, 0), 2)
        cv2.putText(preview_img, f"#{idx}", (x + 4, y + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 2)

    cv2.imwrite(preview_path, preview_img)

    bboxes = [[x, y, w, h] for x, y, w, h in bboxes_raw]
    summary = f"Detected {len(bboxes)} sprites (min_area={min_area}). Bboxes: {json.dumps(bboxes)}"
    return bboxes, summary


def _execute_label_bbox(raw_path: str, preview_path: str, args: dict) -> tuple[list, str]:
    bboxes = args.get("bboxes", [])
    bbox_specs = []
    for i, bb in enumerate(bboxes):
        x, y, w, h = _unpack_bbox(bb)
        bbox_specs.append(f"{x},{y},{w},{h}:#{i}")

    render_label(
        image_path=Path(raw_path),
        output_path=Path(preview_path),
        bbox_specs=bbox_specs,
        mark_x_specs=[],
        mark_y_specs=[],
    )

    return bboxes, f"Labeled {len(bboxes)} bboxes on preview."


class CutAgentResult:
    def __init__(self, status: str, bboxes: list[dict] | None = None, reason: str | None = None, session_id: str = ""):
        self.status = status
        self.bboxes = bboxes
        self.reason = reason
        self.session_id = session_id


DEFAULT_BG_COLOR = (255, 255, 255)  # white (BGR)

def run_cut_agent(
    image_path: str,
    output_path: str | None = None,
    model: str | None = None,
    max_iterations: int = MAX_ITERATIONS,
    save_preview: bool = False,
    expected_frames: int | None = None,
    bg_color: tuple[int, int, int] = DEFAULT_BG_COLOR,
    tips: str | None = None,
) -> CutAgentResult:
    from util.env import load_unified_env
    load_unified_env()

    model = model or os.environ.get("CUT_AGENT_MODEL") or os.environ.get("VLM_MODEL") or DEFAULT_MODEL
    api_key = os.environ.get("VLM_API_KEY")
    base_url = os.environ.get("VLM_BASE_URL")
    if not api_key:
        raise ValueError("VLM_API_KEY not set")
    if not base_url:
        raise ValueError("VLM_BASE_URL not set")

    root = _git_root()
    log_dir = Path(root) / ".vibegame" / "logs" / "cut"
    log_dir.mkdir(parents=True, exist_ok=True)

    session_id = uuid.uuid4().hex[:12]
    raw_path = str(log_dir / f"{session_id}.raw.png")
    preview_path = str(log_dir / f"{session_id}.preview.png")
    log_path = str(log_dir / f"{session_id}.jsonl")

    shutil.copy2(image_path, raw_path)

    client = OpenAI(api_key=api_key, base_url=base_url)
    history: list[dict] = []
    current_bboxes: list[dict] = []
    system_prompt = _build_system_prompt(expected_frames, tips)

    frames_hint = f"expected={expected_frames}" if expected_frames else "auto"
    print(f"cut-agent session={session_id} model={model} max_iter={max_iterations} frames={frames_hint}")
    print(f"  transcript: {log_path}")
    print(f"  raw (input copy): {raw_path}")
    print(f"  preview (updated each turn): {preview_path}")

    for step in range(1, max_iterations + 1):
        print(f"  step {step}/{max_iterations}...")

        preview_exists = Path(preview_path).exists()
        input_list = _build_input(raw_path, preview_path if preview_exists else None, current_bboxes, history, bg_color)

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
            raise RuntimeError(f"Response API returned {type(response).__name__} instead of Response object")

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
            if not current_bboxes:
                result_summary = "REJECTED: no bboxes to submit. Run cut_detect first."
                print(f"    finish REJECTED: empty")
                entry = {"step": step, "tool": "finish", "args": {}, "result_summary": result_summary}
                history.append(entry)
                with open(log_path, "a") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                continue

            overlaps = _check_overlap(current_bboxes)
            if overlaps:
                pairs = ", ".join(f"#{i} & #{j}" for i, j in overlaps)
                result_summary = f"REJECTED: overlap between {pairs}. Adjust via label_bbox or call fail."
                print(f"    finish REJECTED: overlap {pairs}")
                entry = {"step": step, "tool": "finish", "args": {}, "result_summary": result_summary}
                history.append(entry)
                with open(log_path, "a") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                continue

            entry = {"step": step, "tool": "finish", "args": {}, "result_summary": f"done, {len(current_bboxes)} bboxes"}
            history.append(entry)
            with open(log_path, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

            _draw_preview(raw_path, preview_path, current_bboxes, bg_color)

            if output_path:
                out = Path(output_path)
                out.parent.mkdir(parents=True, exist_ok=True)
                bboxes_out = {str(i): list(_unpack_bbox(b)) for i, b in enumerate(current_bboxes)}
                bboxes_out["_meta"] = {"status": "success", "session": session_id, "turns": step, "model": model, "bboxes": len(current_bboxes)}
                out.write_text(json.dumps(bboxes_out, indent=2, ensure_ascii=False))

            if save_preview and output_path:
                preview_out = Path(output_path).with_suffix(".preview.png")
                shutil.copy2(preview_path, str(preview_out))
                print(f"  done at step {step} -> {len(current_bboxes)} bboxes, preview: {preview_out}")
            else:
                print(f"  done at step {step} -> {len(current_bboxes)} bboxes")

            return CutAgentResult(status="success", bboxes=current_bboxes, session_id=session_id)

        if tool_name == "fail":
            reason = args.get("reason", "unknown")
            entry = {"step": step, "tool": "fail", "args": args, "result_summary": f"FAIL: {reason}"}
            history.append(entry)
            with open(log_path, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

            print(f"  FAIL at step {step}: {reason}")
            return CutAgentResult(status="fail", reason=reason, session_id=session_id)

        if tool_name == "cut_detect":
            current_bboxes, result_summary = _execute_cut_detect(raw_path, preview_path, args, bg_color)
        elif tool_name == "label_bbox":
            current_bboxes, result_summary = _execute_label_bbox(raw_path, preview_path, args)
        else:
            result_summary = f"Unknown tool: {tool_name}"

        entry = {"step": step, "tool": tool_name, "args": args, "result_summary": result_summary}
        history.append(entry)
        with open(log_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        print(f"    {tool_name}({json.dumps(args)[:80]}) -> {result_summary[:100]}")

    raise RuntimeError(f"cut-agent exceeded {max_iterations} iterations without finishing")
