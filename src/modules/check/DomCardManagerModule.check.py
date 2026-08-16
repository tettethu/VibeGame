import json
from pathlib import Path


def _load_json(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        return {"__error__": str(exc)}


def _project_manifest(project: Path) -> dict:
    project_json = _load_json(project / "project.json")
    keys = {}
    for rel in project_json.get("manifests", []) or []:
        manifest_path = project / rel
        if manifest_path.exists():
            manifest = _load_json(manifest_path)
            if isinstance(manifest, dict):
                keys.update(manifest)
    return keys


def _nodes(obj):
    if not isinstance(obj, dict):
        return
    if obj.get("script") == "DomCardManagerModule":
        yield obj
    for child in obj.get("children", []) or []:
        yield from _nodes(child)
    if isinstance(obj.get("root"), dict):
        yield from _nodes(obj["root"])


def _num(config, key, messages, *, positive=True):
    if key not in config:
        return
    value = config.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        messages.append(f"ERROR config.{key}: must be a number")
    elif positive and value <= 0:
        messages.append(f"ERROR config.{key}: must be positive")


def _check_node(node: dict, manifest: dict, label: str) -> list[str]:
    messages: list[str] = []
    config = node.get("config") if isinstance(node.get("config"), dict) else {}

    card_atlas = config.get("cardAtlas", "cards")
    if not isinstance(card_atlas, str) or not card_atlas:
        messages.append(f"ERROR {label} config.cardAtlas: must be a non-empty string")
    elif manifest and card_atlas not in manifest:
        messages.append(f"WARN {label} config.cardAtlas: '{card_atlas}' not found in project manifests")

    for key in [
        "logicalWidth", "logicalHeight", "cardW", "cardH", "hoverScale", "hoverLift",
        "hitboxPad", "snapBackDuration", "handRootW", "handRootH",
        "arrowChevronSpacing", "arrowChevronLength", "arrowChevronWidth", "arrowChevronStroke",
    ]:
        _num(config, key, messages)

    scale_mode = config.get("scaleMode", "fit")
    if scale_mode not in ("fit", "stretch"):
        messages.append(f"ERROR {label} config.scaleMode: must be 'fit' or 'stretch'")

    layout = config.get("layout", "flat")
    if layout not in ("flat", "arc"):
        messages.append(f"ERROR {label} config.layout: must be 'flat' or 'arc'")
    if layout == "arc":
        for key in ["arcRadius", "arcAngleStepDeg", "arcMaxAngleDeg"]:
            _num(config, key, messages)

    targets = config.get("targets", [])
    if targets and not isinstance(targets, list):
        messages.append(f"ERROR {label} config.targets: must be an array")
    for i, target in enumerate(targets if isinstance(targets, list) else []):
        if not isinstance(target, dict):
            messages.append(f"ERROR {label} config.targets[{i}]: must be an object")
            continue
        if not target.get("id"):
            messages.append(f"ERROR {label} config.targets[{i}].id: required")
        if not target.get("tag"):
            messages.append(f"WARN {label} config.targets[{i}].tag: missing target tag")

    effects = config.get("enemyTargetEffects", [])
    if effects and not isinstance(effects, list):
        messages.append(f"ERROR {label} config.enemyTargetEffects: must be an array")

    return messages


def check(project: Path, node_path: Path, opts: dict | None = None) -> list[str]:
    opts = opts or {}
    data = _load_json(node_path)
    if "__error__" in data:
        return [f"ERROR invalid JSON: {data['__error__']}"]

    manifest = _project_manifest(project)
    messages: list[str] = []
    found = False
    for idx, node in enumerate(_nodes(data) or []):
        found = True
        label = node.get("name") or f"DomCardManagerModule[{idx}]"
        messages.extend(_check_node(node, manifest, label))

    if not found:
        return ["PASS no DomCardManagerModule node found"]
    if not any(m.startswith("ERROR") for m in messages):
        messages.insert(0, "PASS DomCardManagerModule static check passed")
    return messages
