"""
Mini-agent for cross-action sprite size normalization.

Goal: Given a target character frame and a ground-truth reference frame of the
same character, determine the scale factor needed to make the target match the
reference's visual size.

Usage:
    vibegame art label <target>.png:x,y,w,h --gt <ref>.png:x,y,w,h --normalize -o out.json [--preview]

Workflow: side-by-side comparison → agent calls set_scale(s) → framework
re-renders target at new size → agent verifies or adjusts → finish.
"""

import json
import os
import shutil
import subprocess
import time
import uuid
import base64
import cv2
import numpy as np
from pathlib import Path

from openai import OpenAI


DEFAULT_MODEL = "gpt-5.5"
MAX_ITERATIONS = 20
SEPARATOR_WIDTH = 6  # gap between gt and target in composite

SYSTEM_PROMPT = """\
You are a sprite size normalization specialist.

## Layout (memorize this)
The composite image is split into two halves by a vertical gray separator:
- **LEFT half: GT (ground truth / reference)** — DO NOT change. This is the target size we want to match.
- **RIGHT half: TARGET** — the sprite you adjust via rescale() to match GT's size.

Both are labeled at the top of their respective halves ("GT" left, "TARGET" right) and bottom-aligned (feet at the same baseline).

Goal: They are the SAME character drawn for different actions. The TARGET may have been generated at a different scale. Determine the cumulative rescale factor needed for the TARGET character body to visually match the GT character body.

## Tools
- rescale(ratio): Try a new scale ratio (multiplied to the target's CURRENT size, where 1.0 = no change, >1 = enlarge, <1 = shrink). Cumulative across calls.
- finish: Confirm that the target now matches the reference's size.

## How to compare — CRITICAL
The two sprites are bottom-aligned (feet on the same baseline).

**Compare the CHARACTER BODY ONLY, from top of the hair / head to bottom of the feet.**

**IGNORE these completely** (they make the frame bbox bigger but are NOT part of character size):
- Weapons / swords / arrows / staffs that extend above the head, below the feet, or to the sides.
- Extended arms reaching out (attack pose, casting, blocking high).
- Raised legs (kicking, jumping animation).
- Flowing capes, banners, hair tails, FX trails.
- The frame edges themselves — the frame bbox often has extra room for animation envelope.

**Reliable anchors** (use these to judge size):
- Head: top of hair/skull to chin.
- Torso: shoulder line to waist.
- Hip-to-foot distance.
- Shoulder width.

If you measure full body height (top of head to feet), make sure you are seeing the HEAD, not a weapon tip. Walking pose has feet roughly at the canvas bottom; kneeling/crouching pose has knees as the visible top of leg, but head should still be visible.

The body posture differs between actions, but the underlying character size (skeleton scale) should be consistent. A "1.5x bigger sword" doesn't mean a 1.5x bigger character — same character, different weapon extension.

## Pose vs intrinsic size — DO NOT confuse them
Different poses naturally produce different head-to-foot heights, even at the same character scale. Ordered from tallest to shortest:

standing straight > slightly bent knees (combat stance) > bent waist > crouching / rolling

So if GT and TARGET are in different poses, their head-to-foot heights WILL differ even at equal scale. Do not equalize them blindly.

For pose-affected comparisons, prefer HEAD size (head is pose-invariant) or SHOULDER WIDTH over full body height.

## Workflow
1. Look at the side-by-side composite.
2. Estimate the ratio: how much bigger / smaller is target compared to reference?
   - "Target looks 1.3x too big" → call rescale(0.77)  (≈ 1/1.3)
   - "Target looks 0.8x too small" → call rescale(1.25)
3. After rescale, look at the new composite to verify.
4. Fine-tune if still off; finish when the two visually match.

## Rules
- LLMs are bad at exact numerical estimation. Start with rough estimates (0.5, 0.7, 0.85, 1.0, 1.2, 1.5), then refine.
- Multiple iterations are expected: rough estimate → see new composite → refine → finish.
- Ignore pose differences. Focus on intrinsic character size.
- The rescale ratio is MULTIPLIED to the current target. So if you rescale 1.5 then 0.9, the cumulative scale is 1.35. The composite always reflects the cumulative scale.
- Pixel-perfect alignment is impossible; aim for "look the same height".

## Image context
Each round you see:
- The side-by-side composite: REFERENCE (left, unchanged) + SEPARATOR + TARGET (right, scaled by cumulative factor).
- The cumulative scale factor as text.
"""

TOOLS = [
    {
        "type": "function",
        "name": "rescale",
        "description": "Multiply the TARGET (right side) by this ratio. ONLY the right-side sprite changes; the GT (left side) is never modified. >1 enlarges target, <1 shrinks target. Cumulative across calls.",
        "parameters": {
            "type": "object",
            "properties": {
                "ratio": {
                    "type": "number",
                    "description": "Scale ratio relative to current size (e.g. 0.8, 1.0, 1.25).",
                },
                "reason": {
                    "type": "string",
                    "description": "Why this ratio? Anchor your judgment in specific body parts (e.g. 'gt head ~40px, target head ~52px → shrink to 40/52 ≈ 0.77'). Do NOT cite weapon/frame dimensions.",
                },
            },
            "required": ["ratio", "reason"],
        },
    },
    {
        "type": "function",
        "name": "finish",
        "description": "Confirm the current size matches the reference.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why finish now? State which body anchors confirm the match.",
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


def _flatten_rgba(image: np.ndarray, bg_color=(255, 255, 255)) -> np.ndarray:
    if len(image.shape) == 3 and image.shape[2] == 4:
        alpha = image[:, :, 3:4] / 255.0
        bgr = image[:, :, :3]
        bg = np.full_like(bgr, 0)
        bg[:, :, 0] = bg_color[0]
        bg[:, :, 1] = bg_color[1]
        bg[:, :, 2] = bg_color[2]
        return (bgr * alpha + bg * (1 - alpha)).astype(np.uint8)
    return image[:, :, :3] if len(image.shape) == 3 else image


def _crop_frame(image_path: str, bbox: list[int]) -> np.ndarray:
    src = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if src is None:
        raise ValueError(f"Cannot read image: {image_path}")
    H, W = src.shape[:2]
    x, y, w, h = bbox
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + w, W), min(y + h, H)
    return src[y0:y1, x0:x1].copy()


def _tight_crop_by_alpha(image: np.ndarray, alpha_threshold: int = 1) -> np.ndarray:
    """Trim transparent borders so the crop is the character's actual silhouette.

    The character-size ratio after rescale is determined by the visible content,
    not the original frame bbox dimensions. Without tight cropping, agents would
    align frame-bbox heights instead of character heights.
    """
    if len(image.shape) != 3 or image.shape[2] != 4:
        return image
    alpha = image[:, :, 3]
    mask = alpha > alpha_threshold
    if not mask.any():
        return image
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    y0, y1 = int(rows[0]), int(rows[-1]) + 1
    x0, x1 = int(cols[0]), int(cols[-1]) + 1
    return image[y0:y1, x0:x1].copy()


def _composite_side_by_side(gt_crop: np.ndarray, target_crop: np.ndarray, bg_color=(255, 255, 255)) -> np.ndarray:
    """Place gt and target side-by-side, bottom-aligned."""
    gt_bgr = _flatten_rgba(gt_crop, bg_color)
    tgt_bgr = _flatten_rgba(target_crop, bg_color)

    gh, gw = gt_bgr.shape[:2]
    th, tw = tgt_bgr.shape[:2]

    canvas_h = max(gh, th)
    canvas_w = gw + SEPARATOR_WIDTH + tw
    canvas = np.full((canvas_h, canvas_w, 3), bg_color, dtype=np.uint8)

    # bottom-align gt (left)
    gy = canvas_h - gh
    canvas[gy:gy + gh, 0:gw] = gt_bgr

    # separator (gray vertical line)
    canvas[:, gw:gw + SEPARATOR_WIDTH] = (128, 128, 128)

    # bottom-align target (right)
    ty = canvas_h - th
    canvas[ty:ty + th, gw + SEPARATOR_WIDTH:gw + SEPARATOR_WIDTH + tw] = tgt_bgr

    # Labels at top
    cv2.putText(canvas, "GT", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    cv2.putText(canvas, "TARGET", (gw + SEPARATOR_WIDTH + 8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

    return canvas


def _scale_image(image: np.ndarray, scale: float) -> np.ndarray:
    if scale == 1.0:
        return image.copy()
    h, w = image.shape[:2]
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    return cv2.resize(image, (new_w, new_h), interpolation=interp)


def _encode_image(path: str) -> dict:
    with open(path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    return {"type": "input_image", "image_url": f"data:image/png;base64,{b64}"}


def _build_input(composite_path: str, cumulative_scale: float, history: list) -> list:
    history_text = "Action history:\n"
    if not history:
        history_text += "(none yet — first step)\n"
    else:
        for entry in history[-8:]:
            history_text += f"- Step {entry['step']}: {entry['tool']}({json.dumps(entry['args'], ensure_ascii=False)}) -> {entry['result_summary'][:120]}\n"
    history_text += f"\nCumulative scale: {cumulative_scale:.4f}\n"

    return [{
        "role": "user",
        "content": [
            {"type": "input_text", "text": history_text},
            {"type": "input_text", "text": "Side-by-side comparison (GT left, TARGET right, bottom-aligned):"},
            _encode_image(composite_path),
        ],
    }]


class NormalizeAgentResult:
    def __init__(self, status: str, scale: float = 1.0, session_id: str = ""):
        self.status = status
        self.scale = scale
        self.session_id = session_id


def run_normalize_agent(
    target_image: str,
    target_bbox: list[int],
    gt_image: str,
    gt_bbox: list[int],
    output_path: str | None = None,
    model: str | None = None,
    max_iterations: int = MAX_ITERATIONS,
    save_preview: bool = False,
) -> NormalizeAgentResult:
    from util.env import load_unified_env
    load_unified_env()

    model = model or os.environ.get("NORMALIZE_AGENT_MODEL") or os.environ.get("VLM_MODEL") or DEFAULT_MODEL
    api_key = os.environ.get("VLM_API_KEY")
    base_url = os.environ.get("VLM_BASE_URL")
    if not api_key:
        raise ValueError("VLM_API_KEY not set")
    if not base_url:
        raise ValueError("VLM_BASE_URL not set")

    root = _git_root()
    log_dir = Path(root) / ".vibegame" / "logs" / "normalize"
    log_dir.mkdir(parents=True, exist_ok=True)

    session_id = uuid.uuid4().hex[:12]
    composite_path = str(log_dir / f"{session_id}.composite.png")
    log_path = str(log_dir / f"{session_id}.jsonl")

    gt_crop = _crop_frame(gt_image, gt_bbox)
    target_crop_orig = _crop_frame(target_image, target_bbox)

    client = OpenAI(api_key=api_key, base_url=base_url)
    history: list[dict] = []
    cumulative_scale = 1.0
    t_start = time.time()
    total_in_tokens = 0
    total_out_tokens = 0

    # Initial composite
    composite = _composite_side_by_side(gt_crop, target_crop_orig)
    cv2.imwrite(composite_path, composite)

    print(f"normalize-agent session={session_id} model={model} max_iter={max_iterations}")
    print(f"  transcript: {log_path}")
    print(f"  composite (updated each turn): {composite_path}")

    for step in range(1, max_iterations + 1):
        print(f"  step {step}/{max_iterations}...")

        input_list = _build_input(composite_path, cumulative_scale, history)

        try:
            response = client.responses.create(
                model=model,
                instructions=SYSTEM_PROMPT,
                tools=TOOLS,
                input=input_list,
            )
        except Exception as e:
            print(f"    API error: {e}")
            raise

        if not hasattr(response, "output"):
            raise RuntimeError(f"Response API returned {type(response).__name__} instead of Response object")

        usage = getattr(response, "usage", None)
        if usage is not None:
            total_in_tokens += getattr(usage, "input_tokens", 0) or 0
            total_out_tokens += getattr(usage, "output_tokens", 0) or 0

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
            entry = {"step": step, "tool": "finish", "args": {}, "result_summary": f"done, scale={cumulative_scale:.4f}"}
            history.append(entry)
            with open(log_path, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

            elapsed = time.time() - t_start
            if output_path:
                out = Path(output_path)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps({
                    "scale": cumulative_scale,
                    "target_image": target_image,
                    "target_bbox": target_bbox,
                    "gt_image": gt_image,
                    "gt_bbox": gt_bbox,
                    "_meta": {
                        "status": "success", "session": session_id, "turns": step, "model": model, "scale": cumulative_scale,
                        "elapsed_s": round(elapsed, 1),
                        "input_tokens": total_in_tokens, "output_tokens": total_out_tokens,
                    },
                }, indent=2, ensure_ascii=False))
                if save_preview:
                    preview_out = Path(output_path).with_suffix(".preview.png")
                    shutil.copy2(composite_path, str(preview_out))
                    print(f"  done at step {step} -> scale={cumulative_scale:.4f}, {elapsed:.1f}s, tokens={total_in_tokens}+{total_out_tokens}, preview: {preview_out}")
                else:
                    print(f"  done at step {step} -> scale={cumulative_scale:.4f}, {elapsed:.1f}s, tokens={total_in_tokens}+{total_out_tokens}")
            else:
                print(f"  done at step {step} -> scale={cumulative_scale:.4f}, {elapsed:.1f}s, tokens={total_in_tokens}+{total_out_tokens}")

            return NormalizeAgentResult(status="success", scale=cumulative_scale, session_id=session_id)

        if tool_name == "rescale":
            r = args.get("ratio")
            if not isinstance(r, (int, float)) or r <= 0:
                result_summary = f"REJECTED: ratio must be a positive number, got {r}"
            else:
                cumulative_scale *= float(r)
                scaled_target = _scale_image(target_crop_orig, cumulative_scale)
                composite = _composite_side_by_side(gt_crop, scaled_target)
                cv2.imwrite(composite_path, composite)
                result_summary = f"Applied ratio={r}, cumulative={cumulative_scale:.4f}, target now {scaled_target.shape[1]}x{scaled_target.shape[0]}"
        else:
            result_summary = f"Unknown tool: {tool_name}"

        entry = {"step": step, "tool": tool_name, "args": args, "result_summary": result_summary}
        history.append(entry)
        with open(log_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        print(f"    {tool_name}({json.dumps(args)}) -> {result_summary[:100]}")

    # Max iterations exceeded
    print(f"  max_iterations ({max_iterations}) exceeded, saving partial: scale={cumulative_scale:.4f}")
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "scale": cumulative_scale,
            "target_image": target_image,
            "target_bbox": target_bbox,
            "gt_image": gt_image,
            "gt_bbox": gt_bbox,
            "_meta": {"status": "partial", "session": session_id, "turns": max_iterations, "model": model, "scale": cumulative_scale, "reason": "max_iterations exceeded"},
        }, indent=2, ensure_ascii=False))
        if save_preview:
            preview_out = Path(output_path).with_suffix(".preview.png")
            shutil.copy2(composite_path, str(preview_out))
    return NormalizeAgentResult(status="partial", scale=cumulative_scale, session_id=session_id)
