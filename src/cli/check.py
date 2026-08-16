"""
Game project config validator. Static checks without starting the engine.

Usage:
    vibegame check [path/to/project]
    python src/cli/check.py [path/to/project]

Validates project.json, scene JSON, manifest.json, input-map.json,
tileset/tilemap/node.json files. Reports errors (will crash) and
warnings (suspicious but won't crash).
"""

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

# Phaser 3.80 valid KeyCodes (extracted from Phaser source)
VALID_KEY_CODES = {
    "BACKSPACE", "TAB", "ENTER", "SHIFT", "CTRL", "ALT", "PAUSE", "CAPS_LOCK",
    "ESC", "SPACE", "PAGE_UP", "PAGE_DOWN", "END", "HOME",
    "LEFT", "UP", "RIGHT", "DOWN",
    "PRINT_SCREEN", "INSERT", "DELETE",
    "ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE",
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
    "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
    "NUMPAD_ZERO", "NUMPAD_ONE", "NUMPAD_TWO", "NUMPAD_THREE", "NUMPAD_FOUR",
    "NUMPAD_FIVE", "NUMPAD_SIX", "NUMPAD_SEVEN", "NUMPAD_EIGHT", "NUMPAD_NINE",
    "NUMPAD_ADD", "NUMPAD_SUBTRACT",
    "OPEN_BRACKET", "CLOSED_BRACKET", "SEMICOLON_FIREFOX",
    "COLON", "COMMA_FIREFOX_WINDOWS", "COMMA_FIREFOX",
    "BRACKET_RIGHT_FIREFOX", "BRACKET_LEFT_FIREFOX",
    "SEMICOLON", "QUOTES", "BACKTICK", "BACK_SLASH", "COMMA", "PERIOD",
    "FORWARD_SLASH",
}

# Structural rules — field names, types, required-ness, enums — live in
# .vibegame/schema/ and are enforced by check_schemas(). Only what a schema
# cannot express belongs here: valid key codes, and cross-file consistency.
# An animator state only selects a clip; the engine reads nothing else from it.
VALID_ANIMATOR_STATE_KEYS = {"clip"}


class Issue:
    """A validation issue with severity and context."""

    def __init__(self, level: str, file: str, message: str):
        self.level = level  # "error" or "warning"
        self.file = file
        self.message = message

    def __str__(self):
        tag = "ERROR" if self.level == "error" else "WARN"
        return f"  [{tag}] {self.file}: {self.message}"


class ProjectChecker:
    """Validates a game project directory."""

    # Framework-shipped texture keys auto-registered by the engine; treat
    # as implicitly present in every project's manifest.
    BUILTIN_TEXTURE_KEYS: set[str] = {"__placeholder_atlas__", "__placeholder_image__"}

    def __init__(self, project_dir: Path):
        self.root = project_dir.resolve()
        self.issues: list[Issue] = []
        self.manifest_keys: set[str] = set(self.BUILTIN_TEXTURE_KEYS)
        self.manifest: dict = {}
        self.manifest_key_sources: dict[str, str] = {}  # key -> rel path of listed manifest that defined it
        self.listed_manifest_paths: set[Path] = set()    # resolved paths of manifests in project.json.manifests
        # resolved image path -> [(manifest_rel_path, key, listed_bool), ...]
        # used to flag the same image file referenced by multiple manifest entries (the dashboard
        # navigates by image, so two entries pointing at the same image create an ambiguous edit target)
        self.entry_image_paths: dict[Path, list[tuple[str, str, bool]]] = {}
        self.script_files: set[str] = set()
        self.module_files: set[str] = set()
        # Level 2/3 state
        self.script_animations: dict[str, set[str]] = {}  # script stem -> defined clip names
        self._js_codes: dict[Path, str] = {}  # script path -> source code
        self.referenced_scripts: set[str] = set()  # script stems referenced via script= in scene JSON
        self.scene_src_refs: set[str] = set()  # .node.json paths referenced via src= in scene/node JSON

    def error(self, file: str, msg: str):
        self.issues.append(Issue("error", file, msg))

    def warn(self, file: str, msg: str):
        self.issues.append(Issue("warning", file, msg))

    def _load_json(self, path: Path) -> dict | list | None:
        """Load and parse a JSON file, report errors."""
        rel = str(path.relative_to(self.root))
        if not path.exists():
            self.error(rel, "file not found")
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            self.error(rel, f"invalid JSON: {e}")
            return None

    def run(self) -> list[Issue]:
        """Run all checks. Returns list of issues."""
        self._check_engine_dir()
        self._check_url_contract_files()
        self._check_project_json()
        self._check_script_module_naming()
        self._check_instantiate_refs()
        return self.issues

    def _check_engine_dir(self):
        if not (self.root / "engine").is_dir():
            self.warn(
                "engine/",
                "missing ./engine directory; skeletons may rely on vibegame run source-engine fallback, but game projects should run vibegame init first so ./engine is copied into the project root",
            )

    def _check_script_module_naming(self):
        """Enforce the Module-suffix convention.

        boot.js routes `script: "X"` references by name suffix:
          - X ends with "Module" -> modules/X.js
          - otherwise            -> scripts/X.js
        A misnamed file produces a silent miss at runtime, so reject early.

        skeletons/** is excluded — those are reference projects, not runtime code.
        """
        scripts_dir = self.root / "scripts"
        if scripts_dir.is_dir():
            for js in scripts_dir.rglob("*.js"):
                if js.stem.endswith("Module"):
                    rel = str(js.relative_to(self.root))
                    self.error(
                        rel,
                        f'script file "{js.name}" ends with "Module"; that suffix is reserved for '
                        f'modules/. Rename to something without the "Module" suffix, or move into modules/.',
                    )

        modules_dir = self.root / "modules"
        if modules_dir.is_dir():
            for js in modules_dir.glob("*.js"):
                if not js.stem.endswith("Module"):
                    rel = str(js.relative_to(self.root))
                    self.error(
                        rel,
                        f'module file "{js.name}" must end with "Module" (e.g. {js.stem}Module.js). '
                        f'boot.js routes only Module-suffixed names to modules/.',
                    )

    def _check_url_contract_files(self):
        """Catch static paths that work in dev aliases but fail in static deploys.

        skeletons/** is excluded — those are reference projects, not runtime code.
        """
        roots = [
            "index.html",
            "scripts",
            "scenes",
            "config",
            "entities",
        ]
        for root in roots:
            path = self.root / root
            if not path.exists():
                continue
            files = [path] if path.is_file() else [
                p for p in path.rglob("*")
                if p.is_file() and p.suffix.lower() in {".js", ".html", ".json"}
                and "skeletons" not in p.parts
            ]
            for file in files:
                try:
                    code = file.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                self._check_static_url_contract(file, code)

    def _check_static_url_contract(self, path: Path, code: str):
        rel = str(path.relative_to(self.root))
        if re.search(r"""['"`]/game(?:/|['"`?])""", code):
            self.error(rel, "do not hardcode '/game/...'; vibegame run serves project files at the same paths as a static server")

        if re.search(r"""['"`]/(?:assets|config|scenes|scripts|entities)/""", code):
            self.error(rel, "do not hardcode root project resource paths; derive URLs from window.__APP_CONFIG__.appBasePath or engine/url.js")

        if re.search(r"""location\.origin\s*\+\s*['"`]/""", code):
            self.error(rel, "do not build project URLs from location.origin; use appBasePath-derived helpers")

    # === project.json ===

    def _check_project_json(self):
        data = self._load_json(self.root / "project.json")
        if data is None:
            return

        f = "project.json"
        required = ["name", "version", "engine", "settings", "startScene"]
        for field in required:
            if field not in data:
                self.error(f, f'missing required field "{field}"')

        settings = data.get("settings")
        if isinstance(settings, dict):
            for num_field in ("width", "height"):
                val = settings.get(num_field)
                if val is not None and not isinstance(val, (int, float)):
                    self.error(f, f'settings.{num_field} must be a number, got {type(val).__name__}')
            physics = settings.get("physics")
            if physics is not None and not isinstance(physics, dict):
                self.error(f, f'settings.physics must be an object, got {type(physics).__name__}')
        elif settings is not None:
            self.error(f, f'settings must be an object, got {type(settings).__name__}')

        # Discover and check manifests (from project.json.manifests or default)
        manifest_paths = data.get("manifests", ["assets/manifest.json"]) if isinstance(data, dict) else ["assets/manifest.json"]
        for mp in manifest_paths:
            mpath = self.root / mp
            self.listed_manifest_paths.add(mpath.resolve())
            if mpath.exists():
                self._check_manifest(mpath)

        # Catch orphan manifest.json files that the engine ignores but the dashboard may edit
        self._check_orphan_manifests()

        # Discover script files and do syntax-only checks for all modules
        scripts_dir = self.root / "scripts"
        if scripts_dir.is_dir():
            for js_file in scripts_dir.rglob("*.js"):
                self.script_files.add(js_file.stem)
                try:
                    code = js_file.read_text(encoding="utf-8")
                    self._check_js_syntax(js_file)
                    self._js_codes[js_file] = code
                except Exception:
                    pass

        # Discover module files (Module-suffixed components in modules/)
        modules_dir = self.root / "modules"
        if modules_dir.is_dir():
            for js_file in modules_dir.rglob("*.js"):
                self.module_files.add(js_file.stem)

        # Check startScene exists
        start_scene = data.get("startScene")
        if isinstance(start_scene, str):
            scene_path = self.root / start_scene
            if not scene_path.exists():
                self.error(f, f'startScene "{start_scene}" file not found')
            else:
                self._check_scene_json(scene_path)

        # Check inputMap exists
        input_map = data.get("inputMap")
        if isinstance(input_map, str):
            im_path = self.root / input_map
            if not im_path.exists():
                self.warn(f, f'inputMap "{input_map}" file not found')
            else:
                self._check_input_map(im_path)

        # Check all scene files
        scenes_dir = self.root / "scenes"
        if scenes_dir.is_dir():
            for scene_file in scenes_dir.rglob("*.scene.json"):
                if scene_file != (self.root / start_scene if isinstance(start_scene, str) else None):
                    self._check_scene_json(scene_file)

        # Level 2 structure + Level 3 consistency checks apply only to actual Node scripts
        for js_file, code in self._js_codes.items():
            if js_file.stem in self.referenced_scripts:
                self._check_js_structure(js_file, code)
                self._check_js_consistency(js_file, code)
            else:
                self._check_js_module_imports(js_file, code)

    def _check_instantiate_refs(self):
        """this.instantiate('X.node.json') literals must resolve to preloaded templates.

        Boot only preloads .node.json files referenced via `src` in scene JSON.
        A template consumed only from script code is invisible to that scan, so
        instantiate() would throw at runtime. Matching is scoped to
        `this.instantiate(` with a string literal to avoid unrelated methods
        that happen to share the name; dynamic path expressions are not checked
        (the runtime error covers those).
        """
        pattern = re.compile(r"""this\s*\.\s*instantiate\s*\(\s*['"]([^'"]+\.node\.json)['"]""")
        for js_file, code in self._js_codes.items():
            rel = str(js_file.relative_to(self.root))
            for m in pattern.finditer(code):
                src = m.group(1)
                if not (self.root / src).exists():
                    self.error(rel, f'instantiate("{src}"): file not found')
                elif src not in self.scene_src_refs:
                    self.warn(
                        rel,
                        f'instantiate("{src}"): not referenced by any scene src, so boot will not '
                        f'preload it and instantiate() will throw at runtime. Add a disabled '
                        f'placeholder node {{"src": "{src}", "enabled": false}} to the scene, '
                        f'or register the definition manually before instantiating.',
                    )

    # === manifest.json ===

    def _check_manifest(self, path: Path):
        data = self._load_json(path)
        if data is None:
            return
        if not isinstance(data, dict):
            self.error(str(path.relative_to(self.root)), "manifest must be a JSON object")
            return

        f = str(path.relative_to(self.root))
        assets_dir = path.parent

        for key, entry in data.items():
            if key in self.manifest_keys:
                prev = self.manifest_key_sources.get(key, "(unknown)")
                self.error(f, f'duplicate asset key "{key}" — already defined in {prev}; engine load order silently overwrites earlier entry')
            self.manifest_keys.add(key)
            self.manifest[key] = entry
            self.manifest_key_sources[key] = f

            if not isinstance(entry, dict):
                self.error(f, f'entry "{key}" must be an object')
                continue

            entry_type = entry.get("type")
            entry_path = entry.get("path")

            if not entry_type:
                self.error(f, f'entry "{key}" missing "type"')

            if entry_type != "placeholder_image":
                forbidden = sorted({"shape", "color"} & set(entry))
                if forbidden:
                    self.error(f, f'entry "{key}" field(s) only valid for placeholder_image: {", ".join(forbidden)}')

            if entry_type not in {"tileset", "placeholder_atlas", "placeholder_image"}:
                if not entry_path:
                    self.error(f, f'entry "{key}" missing "path"')
                elif not (assets_dir / entry_path).exists():
                    self.error(f, f'entry "{key}" path "{entry_path}" file not found in {assets_dir.relative_to(self.root)}/')
                elif entry_path:
                    try:
                        resolved = (assets_dir / entry_path).resolve()
                        self.entry_image_paths.setdefault(resolved, []).append((f, key, True))
                    except OSError:
                        pass

            # Deprecated: spritesheet kept for backwards compatibility; new assets use atlas.
            if entry_type == "spritesheet":
                if "frameWidth" not in entry:
                    self.error(f, f'spritesheet "{key}" missing "frameWidth"')
                if "frameHeight" not in entry:
                    self.error(f, f'spritesheet "{key}" missing "frameHeight"')

            # atlas with sprites: validate bbox format
            if entry_type == "atlas" and "sprites" in entry:
                for sprite_name, sprite_data in entry["sprites"].items():
                    bbox = sprite_data.get("bbox")
                    if not isinstance(bbox, list) or len(bbox) != 4:
                        self.error(f, f'atlas "{key}" sprite "{sprite_name}" bbox must be [x,y,w,h]')

            if entry_type == "placeholder_atlas":
                allowed = {"type", "frames", "sprites", "pivot"}
                extra_fields = sorted(set(entry) - allowed)
                if extra_fields:
                    self.error(f, f'placeholder_atlas "{key}" has unsupported field(s): {", ".join(extra_fields)}')
                frame_names = []
                frames = entry.get("frames")
                sprites = entry.get("sprites")
                if isinstance(frames, list):
                    frame_names = [x for x in frames if isinstance(x, str) and x]
                    if len(frame_names) != len(frames):
                        self.error(f, f'placeholder_atlas "{key}" frames must be non-empty strings')
                elif isinstance(sprites, dict):
                    frame_names = list(sprites.keys())
                else:
                    self.error(f, f'placeholder_atlas "{key}" requires "frames" array or "sprites" object')
                if len(frame_names) > 64:
                    self.error(f, f'placeholder_atlas "{key}" has {len(frame_names)} frames; max is 64')

            if entry_type == "placeholder_image":
                allowed = {"type", "pivot", "shape", "color"}
                extra_fields = sorted(set(entry) - allowed)
                if extra_fields:
                    self.error(f, f'placeholder_image "{key}" has unsupported field(s): {", ".join(extra_fields)}')
                color = entry.get("color")
                if color is not None:
                    if not isinstance(color, str) or not re.match(r"^(#[0-9a-fA-F]{3,8}|0x[0-9a-fA-F]{6})$", color):
                        self.error(f, f'placeholder_image "{key}" color must be a hex string like "#ff3366" or "0xff3366"')

            # tileset: validate inline tile data
            if entry_type == "tileset":
                self._check_tileset_entry(key, entry, f, assets_dir)

    # === input-map.json ===

    def _check_orphan_manifests(self):
        """Scan assets/**/manifest.json for files NOT listed in project.json.manifests.

        Orphan manifests are invisible to the engine but the Dashboard assets editor
        may still walk up the directory tree and find them — edits there silently
        diverge from the listed manifest. Flag any orphan whose keys overlap with
        a listed manifest as an error; warn for orphans with unique keys.
        """
        assets_dir = self.root / "assets"
        if not assets_dir.is_dir():
            return
        for mfile in assets_dir.rglob("manifest.json"):
            if mfile.resolve() in self.listed_manifest_paths:
                continue
            try:
                data = json.loads(mfile.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict) or not data:
                continue
            rel = str(mfile.relative_to(self.root))
            overlap = sorted(set(data.keys()) & self.manifest_keys)
            if overlap:
                for key in overlap:
                    listed = self.manifest_key_sources.get(key, "(listed manifest)")
                    self.error(
                        rel,
                        f'orphan manifest contains "{key}" also defined in {listed}; '
                        'engine ignores this file, dashboard edits here will not reach the engine — '
                        'either delete this manifest or add it to project.json.manifests',
                    )
            else:
                self.warn(
                    rel,
                    f'orphan manifest not listed in project.json.manifests; '
                    f'its {len(data)} entries are invisible to the engine and the dashboard may edit them by mistake',
                )
            # Record orphan entries' image paths too, so the path-collision check sees the full picture
            mfile_assets_dir = mfile.parent
            for key, entry in data.items():
                if not isinstance(entry, dict):
                    continue
                entry_path = entry.get("path")
                if not entry_path:
                    continue
                try:
                    resolved = (mfile_assets_dir / entry_path).resolve()
                except OSError:
                    continue
                if not resolved.exists():
                    continue
                self.entry_image_paths.setdefault(resolved, []).append((rel, key, False))

        # Path-collision check: same physical image file referenced by more than one manifest entry.
        # The dashboard navigates by image path, so multiple entries pointing at the same image
        # produce a non-deterministic edit target.
        for resolved, refs in self.entry_image_paths.items():
            if len(refs) <= 1:
                continue
            try:
                rel_img = str(resolved.relative_to(self.root))
            except ValueError:
                rel_img = str(resolved)
            desc = ", ".join(
                f'"{k}" in {p}{"" if listed else " (orphan)"}'
                for p, k, listed in refs
            )
            primary_file = refs[0][0]
            self.error(
                primary_file,
                f'image "{rel_img}" is referenced by multiple manifest entries: {desc}. '
                'Dashboard navigates by image file, so this creates an ambiguous edit target. '
                'Keep one entry, delete the rest.',
            )

    def _check_input_map(self, path: Path):
        data = self._load_json(path)
        if data is None:
            return
        if not isinstance(data, dict):
            self.error(str(path.relative_to(self.root)), "input-map must be a JSON object")
            return

        f = str(path.relative_to(self.root))
        # Support both flat and nested formats
        actions = data.get("actions", data)
        if not isinstance(actions, dict):
            self.error(f, '"actions" must be an object')
            return

        for action, val in actions.items():
            if isinstance(val, list):
                key_names = val
            elif isinstance(val, dict):
                key_names = val.get("keys", [])
            else:
                self.error(f, f'action "{action}" must be an array or {{keys: [...]}}')
                continue

            if not isinstance(key_names, list):
                self.error(f, f'action "{action}" keys must be an array')
                continue

            for key_name in key_names:
                if not isinstance(key_name, str):
                    self.error(f, f'action "{action}" key must be a string, got {type(key_name).__name__}')
                elif key_name not in VALID_KEY_CODES:
                    self.error(f, f'action "{action}" invalid key "{key_name}" (not a valid Phaser KeyCode)')

    # === scene JSON ===

    def _check_scene_json(self, path: Path):
        data = self._load_json(path)
        if data is None:
            return
        if not isinstance(data, dict):
            self.error(str(path.relative_to(self.root)), "scene must be a JSON object")
            return

        f = str(path.relative_to(self.root))

        if "root" not in data:
            self.error(f, 'scene missing required field "root" - engine will crash')
            return

        if not isinstance(data["root"], dict):
            self.error(f, '"root" must be an object')
            return

        self._check_node_def(data["root"], f, "root")

    def _check_node_def(self, node: dict, file: str, path: str):
        """Recursively validate a node definition."""
        # Check src reference
        if "src" in node:
            src = node["src"]
            if isinstance(src, str):
                self.scene_src_refs.add(src)
                src_path = self.root / src
                if not src_path.exists():
                    self.error(file, f'{path}: src "{src}" file not found')
                else:
                    # Validate the referenced node file
                    self._check_node_json(src_path)
            else:
                self.error(file, f'{path}: src must be a string')

        # Check visual
        if "visual" in node:
            self._check_visual(node["visual"], file, path)

        # Check collider
        if "collider" in node:
            self._check_collider(node["collider"], file, path)

        # Check top-level AnimationPlayer clips
        if "animations" in node:
            self._check_animations(node["animations"], node.get("collider"), file, path)

        if "animator" in node:
            self._check_animator(node["animator"], node, file, path)

        # Check script reference
        if "script" in node:
            script = node["script"]
            if not isinstance(script, str):
                self.error(file, f'{path}: script must be a string')
            # boot.js script resolution by suffix:
            #   - "TileMap" / "Collider" / "MountPoint" -> engine/scripts/ (built-in)
            #   - Name ending in "Module"               -> modules/        (shipped components)
            #   - Everything else                       -> scripts/        (project scripts)
            elif script in ("TileMap", "Collider", "MountPoint"):
                pass  # engine built-in, always available
            elif script.endswith("Module"):
                self.referenced_scripts.add(script)
                if self.module_files and script not in self.module_files:
                    self.warn(file, f'{path}: script "{script}" not found in modules/ directory')
            else:
                self.referenced_scripts.add(script)
                if self.script_files and script not in self.script_files:
                    self.warn(file, f'{path}: script "{script}" not found in scripts/ directory')

        # Collect animation clips per script for Level 3 consistency check
        if "script" in node and "animations" in node:
            stem = node["script"]
            anims = node.get("animations")
            if isinstance(anims, dict):
                clips = anims.get("clips", {})
                if isinstance(clips, dict):
                    self.script_animations.setdefault(stem, set()).update(clips.keys())

        # Check children
        if "children" in node:
            children = node["children"]
            if not isinstance(children, list):
                self.error(file, f'{path}: children must be an array - engine will crash (TypeError: not iterable)')
            else:
                for i, child in enumerate(children):
                    if not isinstance(child, dict):
                        self.error(file, f'{path}.children[{i}]: child must be an object')
                    else:
                        child_name = child.get("name", f"[{i}]")
                        self._check_node_def(child, file, f"{path}/{child_name}")

        # Check tags
        if "tags" in node:
            tags = node["tags"]
            if not isinstance(tags, list):
                self.warn(file, f'{path}: tags must be an array')

    def _check_visual(self, visual: dict, file: str, path: str):
        """Validate a visual definition."""
        if not isinstance(visual, dict):
            self.error(file, f'{path}.visual: must be an object')
            return

        vtype = visual.get("type")
        if not vtype:
            self.warn(file, f'{path}.visual: missing "type" (defaults to "rect")')

        has_ratio = "ratio" in visual
        has_width = "width" in visual
        has_height = "height" in visual

        if has_ratio:
            ratio = visual.get("ratio")
            if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or ratio <= 0:
                self.error(file, f'{path}.visual.ratio: must be a positive number')

        if has_width != has_height:
            self.error(file, f'{path}.visual: width and height must be provided together')

        if has_width:
            width = visual.get("width")
            if isinstance(width, bool) or not isinstance(width, (int, float)) or width <= 0:
                self.error(file, f'{path}.visual.width: must be a positive number')
        if has_height:
            height = visual.get("height")
            if isinstance(height, bool) or not isinstance(height, (int, float)) or height <= 0:
                self.error(file, f'{path}.visual.height: must be a positive number')

        if has_ratio and (has_width or has_height):
            self.error(file, f'{path}.visual: use either ratio or width/height, not both')

        # Texture reference check
        if vtype in ("image", "spritesheet", "atlas"):
            texture = visual.get("texture")
            if not texture:
                self.error(file, f'{path}.visual: {vtype} requires "texture" field')
            elif self.manifest_keys and texture not in self.manifest_keys:
                self.error(file, f'{path}.visual: texture "{texture}" not found in manifest - engine will crash')

        # Animation validation
        if "animations" in visual:
            anims = visual["animations"]
            if not isinstance(anims, dict):
                self.error(file, f'{path}.visual.animations: must be an object')
            else:
                for anim_name, anim_def in anims.items():
                    if not isinstance(anim_def, dict):
                        self.error(file, f'{path}.visual.animations.{anim_name}: must be an object')
                        continue
                    if "frames" not in anim_def:
                        self.error(file, f'{path}.visual.animations.{anim_name}: missing "frames"')
                    if "frameRate" not in anim_def:
                        self.warn(file, f'{path}.visual.animations.{anim_name}: missing "frameRate" (defaults to 10)')

    def _check_collider(self, collider: dict, file: str, path: str):
        """Validate a collider definition."""
        if not isinstance(collider, dict):
            self.error(file, f'{path}.collider: must be an object')
            return

    def _check_animations(self, animations: dict, collider: dict | None, file: str, path: str):
        """Validate top-level AnimationPlayer clips."""
        if not isinstance(animations, dict):
            self.error(file, f'{path}.animations: must be an object')
            return
        clips = animations.get("clips")
        if clips is None:
            self.error(file, f'{path}.animations: missing "clips"')
            return
        if not isinstance(clips, dict):
            self.error(file, f'{path}.animations.clips: must be an object')
            return

        has_frame_offset = False
        for clip_name, clip in clips.items():
            clip_path = f'{path}.animations.clips.{clip_name}'
            if not isinstance(clip, dict):
                self.error(file, f'{clip_path}: must be an object')
                continue
            frames = clip.get("frames")
            if frames is None:
                self.error(file, f'{clip_path}: missing "frames"')
                continue
            if not isinstance(frames, list):
                self.error(file, f'{clip_path}.frames: must be an array')
                continue
            if not frames:
                self.warn(file, f'{clip_path}.frames: empty frames array')
            for i, frame_ref in enumerate(frames):
                if self._check_frame_ref(frame_ref, file, f'{clip_path}.frames[{i}]'):
                    has_frame_offset = True

        if has_frame_offset and isinstance(collider, dict) and collider.get("host") != "separate":
            self.error(
                file,
                f'{path}.animations: frame offset requires collider.host: "separate" because offset is visual-only',
            )

    def _check_frame_ref(self, frame_ref, file: str, path: str) -> bool:
        """Validate one FrameRef. Returns True when it has a non-zero/declared offset."""
        if isinstance(frame_ref, (str, int, float)) and not isinstance(frame_ref, bool):
            return False
        if not isinstance(frame_ref, dict):
            self.error(file, f'{path}: frame ref must be a string, number, or object')
            return False

        if "frame" not in frame_ref:
            self.error(file, f'{path}: object frame ref missing "frame"')
        else:
            frame = frame_ref.get("frame")
            if isinstance(frame, bool) or not isinstance(frame, (str, int, float)):
                self.error(file, f'{path}.frame: must be a string or number')

        if "duration" in frame_ref:
            self.error(file, f'{path}.duration: not supported; use frameDurations for timing')

        if "offset" not in frame_ref:
            return False

        offset = frame_ref.get("offset")
        if not isinstance(offset, list) or len(offset) != 2:
            self.error(file, f'{path}.offset: must be [x, y]')
            return True
        for j, value in enumerate(offset):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                self.error(file, f'{path}.offset[{j}]: must be a number')
        return True

    def _check_animator(self, animator: dict, node: dict, file: str, path: str):
        """Validate Animator state machine config."""
        if not isinstance(animator, dict):
            self.error(file, f'{path}.animator: must be an object')
            return

        states = animator.get("states")
        if states is None:
            self.error(file, f'{path}.animator: missing "states"')
            return
        if not isinstance(states, dict):
            self.error(file, f'{path}.animator.states: must be an object')
            return

        clip_names = set()
        animations = node.get("animations")
        if isinstance(animations, dict) and isinstance(animations.get("clips"), dict):
            clip_names = set(animations["clips"].keys())

        for state_name, state in states.items():
            state_path = f'{path}.animator.states.{state_name}'
            if not isinstance(state, dict):
                self.error(file, f'{state_path}: must be an object')
                continue
            clip = state.get("clip")
            if clip is not None:
                if not isinstance(clip, str):
                    self.error(file, f'{state_path}.clip: must be a string')
                elif clip_names and clip not in clip_names:
                    self.error(file, f'{state_path}.clip: clip "{clip}" not found in animations.clips')
            # An animator state only selects a clip. Anything else is ignored by
            # the engine, so warn instead of letting it fail silently at runtime.
            unknown = sorted(set(state) - VALID_ANIMATOR_STATE_KEYS)
            if unknown:
                self.warn(
                    file,
                    f'{state_path}: unknown key(s) {", ".join(unknown)} — ignored by the engine '
                    f'(valid: {", ".join(sorted(VALID_ANIMATOR_STATE_KEYS))})',
                )

        transitions = animator.get("transitions", [])
        if transitions is not None and not isinstance(transitions, list):
            self.error(file, f'{path}.animator.transitions: must be an array')

    # === Level 2: JS syntax + structure ===

    def _check_js_syntax(self, path: Path):
        """Level 2a: node --check via temp .mjs (parse-only, no execution)."""
        rel = str(path.relative_to(self.root))
        try:
            code = path.read_text(encoding="utf-8")
            with tempfile.NamedTemporaryFile(suffix=".mjs", mode="w", encoding="utf-8", delete=False) as tmp:
                tmp.write(code)
                tmp_path = tmp.name
            try:
                result = subprocess.run(
                    ["node", "--check", tmp_path],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode != 0:
                    err = result.stderr.replace(tmp_path, rel)
                    for line in err.splitlines():
                        if "SyntaxError" in line:
                            self.error(rel, f"JS syntax: {line.strip()}")
                            return
                    self.error(rel, "JS syntax error (node --check failed)")
            finally:
                os.unlink(tmp_path)
        except FileNotFoundError:
            pass  # node not installed
        except subprocess.TimeoutExpired:
            self.warn(rel, "JS syntax check timed out")
        except Exception:
            pass

    def _check_js_structure(self, path: Path, code: str):
        """Level 2b: regex-based module structure checks."""
        rel = str(path.relative_to(self.root))

        self._check_js_module_imports(path, code)

        # Must import Node from engine (skip if extends a known script -- inherits indirectly)
        m_extends = re.search(r"export\s+default\s+class\s+\w+\s+extends\s+(\w+)", code)
        extends_known_script = m_extends and m_extends.group(1) in self.script_files
        if not extends_known_script:
            if not re.search(r"import\b.*\bNode\b.*from\s+['\"].*engine/Node\.js['\"]", code):
                self.warn(rel, "missing: import { Node } from '/engine/Node.js'")

        # Must export default class X extends Node (or another script that eventually extends Node)
        m = re.search(r"export\s+default\s+class\s+(\w+)\s+extends\s+(\w+)", code)
        if not m:
            self.warn(rel, "no 'export default class X extends Node' found")
        else:
            class_name, parent_name = m.group(1), m.group(2)
            # Allow multi-level inheritance: SlimeEnemy -> Enemy -> Node
            # Only warn if parent is neither 'Node' nor a known script file
            if parent_name != "Node" and parent_name not in self.script_files:
                self.warn(rel, f"extends '{parent_name}' which is not 'Node' or a known script in scripts/")
            if class_name != path.stem:
                self.warn(rel, f"class name '{class_name}' doesn't match filename '{path.stem}.js'")

    def _check_js_module_imports(self, path: Path, code: str):
        """Import-path checks that apply to all JS modules, not just Node subclasses."""
        rel = str(path.relative_to(self.root))

        if re.search(r"""from\s+['"]/game/scripts/[^'"]+['"]""", code):
            self.error(rel, "use relative imports between game scripts; do not import from '/game/scripts/...'")

    # === Level 3: cross-file consistency ===

    def _check_js_consistency(self, path: Path, code: str):
        """Level 3: check JS references against JSON-defined data."""
        rel = str(path.relative_to(self.root))
        stem = path.stem

        # 3c: playAnim('clipName') must reference a defined clip
        known_clips = self.script_animations.get(stem)
        if known_clips:
            for m in re.finditer(r"""playAnim\s*\(\s*['"]([^'"]+)['"]""", code):
                clip = m.group(1)
                if clip not in known_clips:
                    self.warn(rel, f"playAnim('{clip}') - clip not defined in any node using this script (defined: {', '.join(sorted(known_clips))})")

    # === .node.json ===

    _checked_nodes: set[str] = set()

    def _check_node_json(self, path: Path):
        """Validate an external .node.json file."""
        rel = str(path.relative_to(self.root))
        if rel in self._checked_nodes:
            return
        self._checked_nodes.add(rel)

        data = self._load_json(path)
        if data is None:
            return
        if not isinstance(data, dict):
            self.error(rel, "node.json must be a JSON object")
            return

        self._check_node_def(data, rel, data.get("name", "root"))

    # === tileset (inline in manifest) ===

    def _check_tileset_entry(self, key: str, entry: dict, f: str, assets_dir: Path):
        """Validate an inline tileset definition from manifest.json."""
        if "image" in entry:
            self.error(f, f'tileset "{key}" uses unsupported field "image"; use "path"')

        for field in ("tileSize", "tiles"):
            if field not in entry:
                self.error(f, f'tileset "{key}" missing "{field}"')

        # `path` is optional: with no tileset PNG the engine builds a canvas
        # texture from each tile's `color`, which is how a map is prototyped
        # before the art lands. One of the two has to be there, or the tileset
        # renders nothing.
        entry_path = entry.get("path")
        if entry_path is None:
            tiles_def = entry.get("tiles")
            colored = isinstance(tiles_def, dict) and any(
                isinstance(t, dict) and t.get("color") for t in tiles_def.values()
            )
            if not colored:
                self.error(
                    f,
                    f'tileset "{key}" has no "path" and no tile defines "color"; '
                    f'give it a tileset image, or a placeholder color per tile',
                )

        if isinstance(entry_path, str):
            full = assets_dir / entry_path
            if not full.exists():
                self.error(f, f'tileset "{key}" path "{entry_path}" file not found in {assets_dir.relative_to(self.root)}/')
            else:
                try:
                    self.entry_image_paths.setdefault(full.resolve(), []).append((f, key, True))
                except OSError:
                    pass

        # Check tileSize is a number
        tile_size = entry.get("tileSize")
        if tile_size is not None and not isinstance(tile_size, (int, float)):
            self.error(f, f'tileset "{key}" tileSize must be a number')

        # Check tiles
        tiles = entry.get("tiles")
        if tiles is not None:
            if not isinstance(tiles, dict):
                self.error(f, f'tileset "{key}" tiles must be an object')
            else:
                for tile_name, tile_def in tiles.items():
                    if not isinstance(tile_def, dict):
                        self.error(f, f'tileset "{key}" tile "{tile_name}" must be an object')
                        continue
                    if "index" not in tile_def:
                        self.error(f, f'tileset "{key}" tile "{tile_name}" missing "index"')
                    # Validate collisionShapes if present
                    shapes = tile_def.get("collisionShapes")
                    if isinstance(shapes, list):
                        for si, shape in enumerate(shapes):
                            if not isinstance(shape, dict):
                                self.error(f, f'tileset "{key}" tile "{tile_name}" collisionShapes[{si}] must be an object')
                                continue
                            for sf in ("type", "x", "y", "width", "height"):
                                if sf not in shape:
                                    self.error(f, f'tileset "{key}" tile "{tile_name}" collisionShapes[{si}] missing "{sf}"')

    # === tilemap.json ===

    def _check_tilemap_json(self, path: Path):
        data = self._load_json(path)
        if data is None:
            return
        if not isinstance(data, dict):
            self.error(str(path.relative_to(self.root)), "tilemap must be a JSON object")
            return

        f = str(path.relative_to(self.root))

        if "tileset" not in data:
            self.error(f, 'missing required field "tileset"')
        else:
            ts_name = data["tileset"]
            # Check tileset exists in manifest as a tileset type entry
            ts_entry = self.manifest.get(ts_name)
            if ts_entry and ts_entry.get("type") != "tileset":
                self.error(f, f'tileset "{ts_name}" exists in manifest but is not type "tileset" - engine will crash')
            elif not ts_entry and self.manifest:
                self.error(f, f'tileset "{ts_name}" not found in manifest - engine will crash')

        layers = data.get("layers")
        if layers is None:
            self.error(f, 'missing required field "layers"')
        elif not isinstance(layers, list):
            self.error(f, '"layers" must be an array')
        else:
            for i, layer in enumerate(layers):
                if not isinstance(layer, dict):
                    self.error(f, f'layers[{i}] must be an object')
                    continue
                if "name" not in layer:
                    self.warn(f, f'layers[{i}] missing "name"')
                layer_data = layer.get("data")
                if layer_data is None:
                    self.error(f, f'layers[{i}] missing "data" - engine will crash')
                elif not isinstance(layer_data, list):
                    self.error(f, f'layers[{i}].data must be a 2D array - engine will crash')
                else:
                    for j, row in enumerate(layer_data):
                        if not isinstance(row, list):
                            self.error(f, f'layers[{i}].data[{j}] must be an array - engine will crash')
                            break

    # === Discovery and full check ===

    def _discover_and_check_extra(self):
        """Check tilemap and node files."""
        # Tilemaps from maps/ directory
        maps_dir = self.root / "maps"
        if maps_dir.is_dir():
            for tm_file in maps_dir.rglob("*.tilemap.json"):
                self._check_tilemap_json(tm_file)

        # Node files from entities/ or nodes/ directory
        for subdir in ("entities", "nodes"):
            d = self.root / subdir
            if d.is_dir():
                for node_file in d.rglob("*.node.json"):
                    self._check_node_json(node_file)

        # Level 3: cross-file consistency (run after all JSON checks collected data)
        for js_path, code in self._js_codes.items():
            self._check_js_consistency(js_path, code)


# Which schema validates which files. Globs are relative to the project root.
SCHEMA_TARGETS: tuple[tuple[str, str], ...] = (
    ("project.schema.json", "project.json"),
    ("node.schema.json", "**/*.node.json"),
    ("scene.schema.json", "**/*.scene.json"),
    ("manifest.schema.json", "assets/**/manifest.json"),
    ("input-map.schema.json", "config/input-map.json"),
    ("tilemap.schema.json", "**/*.tilemap.json"),
)

SCHEMA_SKIP_DIRS = {"node_modules", "engine", "modules", ".git", "artifacts"}


def _schema_registry(schema_dir: Path):
    """Registry resolving the cross-file $refs the schemas use (e.g. node.json#/$defs/...)."""
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012

    registry = Registry()
    contents: dict[str, dict] = {}
    for path in sorted(schema_dir.glob("*.schema.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        contents[path.name] = data
        resource = Resource(contents=data, specification=DRAFT202012)
        # Reachable as "node.schema.json", as "node.json" (how the schemas $ref
        # each other), and by its own $id.
        registry = registry.with_resource(uri=path.name, resource=resource)
        registry = registry.with_resource(uri=path.name.replace(".schema", ""), resource=resource)
        if "$id" in data:
            registry = registry.with_resource(uri=data["$id"], resource=resource)
    return contents, registry, Draft202012Validator


def check_schemas(project_dir: Path) -> list[Issue]:
    """Validate project JSON against the schemas shipped in .vibegame/schema/.

    The schemas are the contract a game agent reads. Validating against them here
    is what keeps them from drifting away from the engine: a schema that no longer
    describes real project data now fails the same command the agent runs.
    """
    schema_dir = project_dir / ".vibegame" / "schema"
    if not schema_dir.is_dir():
        return []

    try:
        contents, registry, Validator = _schema_registry(schema_dir)
    except json.JSONDecodeError as exc:
        return [Issue("error", ".vibegame/schema", f"invalid schema JSON: {exc}")]

    issues: list[Issue] = []
    for schema_name, pattern in SCHEMA_TARGETS:
        schema = contents.get(schema_name)
        if schema is None:
            issues.append(Issue("warning", ".vibegame/schema", f"missing {schema_name}; files matching {pattern} are unchecked"))
            continue
        validator = Validator(schema, registry=registry)
        for path in sorted(project_dir.glob(pattern)):
            if not path.is_file() or SCHEMA_SKIP_DIRS & set(path.relative_to(project_dir).parts):
                continue
            rel = str(path.relative_to(project_dir))
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue  # the JSON parse error is already reported by the file's own check
            for error in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
                where = "/".join(str(p) for p in error.absolute_path)
                issues.append(Issue("error", rel, f"{where or '(root)'}: {error.message}"))
    return issues


def check_project(project_dir: Path) -> list[Issue]:
    """Main entry: validate a game project, return list of issues."""
    checker = ProjectChecker(project_dir)
    checker.run()
    checker._discover_and_check_extra()
    return checker.issues + check_schemas(project_dir) + check_hook_configs(project_dir)


def check_hook_configs(project_dir: Path) -> list[Issue]:
    """Validate SessionStart hook commands carry --source-app.

    session-start.py refuses to run without --source-app, so a stale hook
    config from an older vibegame install would silently break the
    agents.jsonl roster. Fail loudly here so vibegame check surfaces it.
    """
    issues: list[Issue] = []
    issues.extend(_check_claude_session_start(project_dir))
    issues.extend(_check_codex_session_start(project_dir))
    return issues


def _check_claude_session_start(project_dir: Path) -> list[Issue]:
    rel = ".claude/settings.json"
    path = project_dir / rel
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [Issue("error", rel, f"parse error: {exc}")]
    for group in (data.get("hooks", {}) or {}).get("SessionStart", []) or []:
        for hook in (group or {}).get("hooks", []) or []:
            command = (hook or {}).get("command", "")
            if "session-start.py" in command and "--source-app claude" not in command:
                return [Issue(
                    "error",
                    rel,
                    "SessionStart hook for session-start.py is missing '--source-app claude'. "
                    "Re-run vibegame setup or patch the command manually.",
                )]
    return []


def _check_codex_session_start(project_dir: Path) -> list[Issue]:
    rel = ".codex/hooks.json"
    path = project_dir / rel
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [Issue("error", rel, f"parse error: {exc}")]
    for group in (data.get("hooks", {}) or {}).get("SessionStart", []) or []:
        for hook in (group or {}).get("hooks", []) or []:
            command = (hook or {}).get("command", "")
            if "session-start.py" in command and "--source-app codex" not in command:
                return [Issue(
                    "error",
                    rel,
                    "SessionStart hook for session-start.py is missing '--source-app codex'. "
                    "Re-run vibegame setup to reinstall Codex hooks.",
                )]
    return []


def print_report(issues: list[Issue]) -> int:
    """Print human-readable report. Returns exit code (0=ok, 1=errors)."""
    errors = [i for i in issues if i.level == "error"]
    warnings = [i for i in issues if i.level == "warning"]
    infos = [i for i in issues if i.level == "info"]

    if not issues:
        print("All checks passed.")
        return 0

    if errors:
        print(f"\n{len(errors)} error(s):")
        for e in errors:
            print(e)

    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for w in warnings:
            print(w)

    if infos:
        print()
        for i in infos:
            print(i)

    print()
    if errors:
        print(f"FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    else:
        print(f"PASSED with {len(warnings)} warning(s)")
        return 0


REQUIRED_RUNTIME_FILES: tuple[str, ...] = (
    ".claude/settings.json",
    ".codex/config.toml",
    ".vibegame/global.json",
    ".vibegame/orchestrator.md",
    ".vibegame/settings.json",
    ".vibegame/config/context.json",
    ".vibegame/hooks/agent-team-stop.py",
    ".vibegame/hooks/enforce-team-mode.py",
    ".vibegame/hooks/enforce-team-setup.py",
    ".vibegame/hooks/session-start.py",
    ".vibegame/hooks/teammate-message-touch.py",
    ".vibegame/hooks/user-prompt-submit.py",
    ".vibegame/hooks/web_hook.py",
    ".vibegame/team/__init__.py",
    ".vibegame/team/context_config.py",
    ".vibegame/team/hook_identity.py",
    ".vibegame/team/launch.py",
    ".vibegame/team/locks.py",
    ".vibegame/team/logger.py",
    ".vibegame/team/messages.py",
    ".vibegame/team/models.json",
    ".vibegame/team/paths.py",
    ".vibegame/team/settings.py",
    ".vibegame/team/state.py",
    ".vibegame/team/tmux.py",
)


def check_runtime(project_dir: Path) -> list[Issue]:
    """Validate vibegame agent runtime files (presence + parse validity)."""
    issues: list[Issue] = []
    for rel in REQUIRED_RUNTIME_FILES:
        path = project_dir / rel
        if not path.is_file():
            issues.append(Issue("error", rel, "missing required runtime file"))
            continue
        try:
            text = path.read_text(encoding="utf-8")
            suffix = Path(rel).suffix
            if suffix == ".json":
                json.loads(text)
            elif suffix == ".toml":
                tomllib.loads(text)
            elif suffix == ".py":
                ast.parse(text, filename=rel)
        except Exception as exc:
            issues.append(Issue("error", rel, f"parse error: {exc}"))
    return issues


def main():
    project_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    if not (project_dir / "project.json").exists():
        print(f"Error: {project_dir} is not a game project (no project.json)")
        sys.exit(1)
    issues = check_project(project_dir)
    sys.exit(print_report(issues))


if __name__ == "__main__":
    main()
