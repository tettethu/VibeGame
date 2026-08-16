"""Static check for ParallaxModule nodes.

Auto-discovered by `vibegame check` for any node with `"script": "ParallaxModule"`.
Asserts the layer texture is a real manifest key and (for atlas layers) the
declared frame exists — the two typos that otherwise fail silently at runtime.
"""
import json
from pathlib import Path


def _load_manifest_keys(project: Path) -> dict:
    """Merge every manifest listed in project.json.manifests into {key: entry}."""
    keys: dict = {}
    proj_file = project / "project.json"
    if not proj_file.exists():
        return keys
    try:
        proj = json.loads(proj_file.read_text())
    except Exception:
        return keys
    for rel in proj.get("manifests", []):
        mp = project / rel
        if not mp.exists():
            continue
        try:
            data = json.loads(mp.read_text())
        except Exception:
            continue
        if isinstance(data, dict):
            keys.update(data)
    return keys


def _frame_names(entry: dict):
    """Frame names an entry exposes, or None if it has no frames (plain image)."""
    if not isinstance(entry, dict):
        return None
    sprites = entry.get("sprites")
    if isinstance(sprites, dict):
        return {str(k) for k in sprites}
    frames = entry.get("frames")  # placeholder_atlas
    if isinstance(frames, list):
        return {str(f) for f in frames}
    return None


def check(project: Path, node_path: Path, opts: dict | None = None) -> list[str]:
    opts = opts or {}
    messages: list[str] = []
    node = json.loads(Path(node_path).read_text())
    config = node.get("config") if isinstance(node.get("config"), dict) else {}

    texture = config.get("texture")
    if not texture:
        messages.append("ERROR config.texture: required (manifest key of the layer image/atlas)")
        return messages

    keys = _load_manifest_keys(Path(project))
    if texture not in keys:
        messages.append(
            f'ERROR config.texture: "{texture}" not found in any manifest listed in project.json.manifests'
        )
    else:
        frame = config.get("frame")
        if frame is not None:
            names = _frame_names(keys[texture])
            if names is None:
                messages.append(
                    f'WARN config.frame "{frame}" set but manifest entry "{texture}" declares no frames (plain image?); frame is ignored'
                )
            elif str(frame) not in names:
                messages.append(
                    f'ERROR config.frame: "{frame}" is not a frame of atlas "{texture}" (available: {sorted(names)})'
                )

    if not any(m.startswith("ERROR") for m in messages):
        messages.insert(0, "PASS ParallaxModule static check passed")
    return messages
