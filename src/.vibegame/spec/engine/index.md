# VibeGame Game Development

The shared engine usage guide for architect, programmer, auditor, player and reviewer. Use [tilemap-guide.md](tilemap-guide.md) for tile-grid levels and [deployment.md](deployment.md) for packaging and deployment.

VibeGame runs on Phaser 3. Use ordinary JavaScript for rules, AI, economy and data. Use a Node for lifecycle, declared visuals/bodies, tree membership or inspection. Access the real Phaser scene through this.scene.

The engine owns project boot, declared objects, registered assets and inspection. Scripts own gameplay. Do not recreate a visual or body that scene data already declares. Inspect the shipped engine source when behavior needs deeper diagnosis.

## Project

Start with vibegame init and keep its index.html boot entry. Boot must happen when the page loads. A title menu controls the already-running game; it must not create a second Phaser game or postpone engine initialization.

File -> Purpose:
- project.json: Canvas settings, gravity, start scene, manifests and input map
- scenes/*.scene.json: Initial root node and its children
- entities/*.node.json: Reusable object definitions
- scripts/*.js: Game scripts and ordinary JavaScript helpers
- assets/**/manifest.json: Registered images and named atlas frames
- config/input-map.json: Named actions mapped to keyboard keys
- modules/: Supplied reusable Node subclasses; use config or project-local subclasses
- engine/: Shipped engine source; available for inspection

A scene references scripts by class name, without an extension: Hero loads scripts/Hero.js; StatusBarModule loads modules/StatusBarModule.js. TileMap, Collider and MountPoint load from engine/scripts/. Module filenames end with Module; game scripts do not.

### Project settings

project.json field -> Meaning:
- name, version, engine: Required project identifiers, e.g. engine: "vibegame@0.1.0"
- settings: Required canvas and physics settings
- startScene: Required path to initial scene JSON
- manifests: Manifest paths; declare them explicitly, e.g. ["assets/manifest.json"]
- inputMap: Path to named keyboard actions
- runtimeDefaults: dev/deploy appBasePath and apiBaseUrl; see Deployment
- releaseExtraRoots: Extra game runtime files to package; see Deployment

settings field -> Meaning / default:
- width, height: Logical canvas dimensions, default 800x600
- scaleMode: Phaser scale mode, default FIT
- pixelArt: Nearest-neighbor rendering, default false
- transparent: Transparent canvas, default false
- backgroundColor: CSS color, default black
- physics.gravity: World acceleration, default {x: 0, y: 0}
- physics.debug: Draw Arcade bodies, default false
- fpsLimit: Non-negative integer frame-rate cap; 0 disables the cap; runtime --fps can override

Use FIT, NONE, RESIZE, ENVELOP, WIDTH_CONTROLS_HEIGHT or HEIGHT_CONTROLS_WIDTH when the corresponding Phaser scale behavior fits the game. Canvas dimensions, camera zoom and browser scaling are different settings.

## Nodes

NodeDef field -> Meaning:
- name: Node name
- id: Optional stable snapshot/query ID; generated when omitted
- script: Node subclass to instantiate
- config: Script configuration, including initial x/y and gameplay tuning
- visual: Declared Phaser visual
- collider: Declared physics body
- visualTransform: Visual-only offsetX/offsetY from the physics/transform anchor
- animations: Clip data
- animator: State selection and transition data
- children: Nested NodeDefs
- tags: Labels for scene queries
- src: Reusable .node.json path
- enabled: Defaults true; false leaves a template unbuilt, including its subtree

There is no NodeDef type field. Behavior comes from script. Put tuning values in config. Promote a value to a shared config file only when multiple nodes consume it or it describes the whole project. Changing enabled to true after startup does not build a disabled template. Instantiate the template to create a live object.

### Scripts

From scripts/, import Node from ../engine/Node.js and export the class as default. The filename and class name match. Relative imports work for ordinary helpers. Initialize in ready(), not the constructor: engine references do not exist yet during construction.

Lifecycle / property -> Contract:
- ready(): May be async; children first, then parent
- update(dt): dt is seconds; parent before children
- destroy(): Release script-owned listeners, DOM and resources
- scene: The Phaser.Scene; use its physics, camera, input and effect APIs
- sceneTree: Shared tree, inputMap, UI layer, node registry and assets
- config: Merged node configuration
- parent, children, tags, id, name: Node identity and hierarchy
- getVisualObject(): Rendered object
- getPhysicsObject(): Body host, when present
- getTransformObject(): Object whose movement drives the node
- gameObject: Primary object; the physics host when host is separate
- animationPlayer, animator: Engine-created animation helpers

Siblings become ready in children-array order. Put a listener before a sibling that emits during ready(), or connect siblings from their parent's ready(). The engine cleans up declared visuals and bodies. Scripts clean up what they created manually, including DOM, timers and listeners on longer-lived objects.

For genuinely dynamic visuals, omit the declaration and create a Phaser object in ready(). Expose it through this.gameObject for inspection and selection.

## World size

Plan a gameplay object's physical size in the game world, then fit artwork to it. A generated image's resolution must not decide how wide a doorway is, how far an attack reaches, or whether the player fits under a ceiling.

Value -> Units:
- config.x / y: Initial world position of the node anchor
- visual.width / height: Display size in world px; animation establishes scale from its first frame
- visual.ratio: Source pixels multiplied by a dimensionless scale
- collider.width / height / radius: Physical world px; do not multiply them by visual.ratio again
- collider.offsetX / offsetY: Additional world-pixel displacement
- visualTransform.offsetX / offsetY: Visual-only displacement in world px
- frame offset: Visual-only world-pixel displacement for one clip frame occurrence
- manifest bbox: Source-image pixels [x, y, width, height]
- pivot: Fractional anchor [x, y], not a pixel displacement

World px are logical game units, independent of camera zoom and browser scaling. An 800x1200 image displayed as 48x72 has ratio 0.06; a 36x68 collider is still 36x68.

### Visuals

visual field -> Meaning:
- type: rect, image or atlas for new content
- texture: Registered image/atlas key
- frame: Initial named atlas frame; set it explicitly
- width, height: Desired display size
- ratio: Uniform source-size multiplier, used instead of width/height
- color: Rectangle color, e.g. "0x465347"

Choose either width/height or ratio, never both. Use ratio by default for uniform scaling. If you specify both width and height, choose values that keep the displayed aspect ratio within 10% of the source frame's aspect ratio, unless non-uniform scaling is an intentional part of the visual design. Do not distort artwork merely to match a collider; the visual and collider bounds may differ.

Assume that source artwork is tightly cropped to its visible content, without transparent padding. The artist is responsible for ensuring and verifying this before delivery.

For an animated node with explicit width and height, AnimationPlayer uses the first frame of the initial clip to establish the visual scale. Later frames retain that scale. With ratio, each frame is sized from its own source dimensions.

Phaser object.width/height describe source geometry; displayWidth/displayHeight describe displayed geometry. Use the latter when measuring a visual.

### Collider size and visual fitting

When collider size is omitted, the engine derives it from the visual's displayed size during body setup. This is convenient when placeholder visual and body are the same size. Once the physical size is agreed, make it explicit when real art may have a different footprint. Keep it unchanged during a cosmetic asset swap.

Visual and collider do not need equal bounds: hair, capes, weapons and effects can extend beyond the body. Keep their intended world scale and anchor aligned.

By default the body is attached to the visual's Phaser object. Changing that object's scale at runtime can also change its body. Use collider.host: "separate" when varying animation frames or visual adjustments must leave a stable physics host. A per-frame visual offset with a collider requires this mode. Move the physics host; the engine follows it with the visual.

Verify the actual body after runtime resizing; cosmetic fitting must not change gameplay.

### Pivot

Ground characters normally use visual pivot [0.5, 1], at their feet. Images and atlas frames get their visual pivot in this order: clip override, manifest frame override, manifest entry, default [0.5, 1]. Set it on the appropriate asset or clip, not on visual.

Box collider pivot inherits the visual origin unless explicitly set. Circles default to [0.5, 0.5]. With no visual origin, the fallback is [0.5, 0.5]. The engine aligns the collider anchor to the object anchor; collider offsets are additional adjustments.

Use pivot to select the fixed anchor, and visualTransform for a drawing offset. A FrameRef offset applies only to that occurrence of a frame. Do not change the body's world position to correct a drawing's padding.

## Collisions

A collider defines body geometry and motion. Blocking versus triggering is chosen for each pair by script code.

collider field -> Meaning / default:
- shape: box or circle; default box
- body: dynamic or static; default dynamic
- host: Omit for the visual object; separate creates an invisible physics host
- width, height: Box world dimensions; omitted values use the visual
- radius: Circle world radius; omitted uses half the smaller visual dimension
- pivot: Fractional body anchor; see Pivot
- offsetX, offsetY: Extra world-pixel offsets, default 0
- gravity: Dynamic body receives gravity unless false
- immovable: Dynamic body is not pushed by another body, default false
- worldBounds: Constrain to physics world, default false
- bounce: Number or {x, y}, default 0
- oneWay: Blocks from above only, default false

A plain node's declared body requires a visual, including with host: "separate". For an invisible body without a visual, use the built-in Collider script.

Use static for fixed terrain. Use dynamic for velocity/gravity motion, including moving platforms with immovable: true and gravity: false. Directly moving or resizing a static host requires body.updateFromGameObject() or refreshBody(); parent-inherited changes are refreshed by the engine. Arcade boxes remain axis-aligned. Rotating artwork does not rotate a box collider.

Use standard Phaser pair registration:
~~~js
this.scene.physics.add.collider(this.getPhysicsObject(), wall.getPhysicsObject())
this.scene.physics.add.overlap(this.getPhysicsObject(), pickup.getPhysicsObject(), () => {
  pickup.removeSelf()
})
~~~

Overlap callbacks can fire every physics step. Game code owns hit deduplication, damage, invulnerability and removal. Do not infer a floor contact from any collision: read body.blocked.down or check the particular contact's direction.

When enter/exit events are useful, use:
~~~js
this.trackCollider(wall.getPhysicsObject(), wall)
this.trackOverlap(sensor.getPhysicsObject(), sensor)
this.on('overlap_enter', ({other}) => { this.currentSensor = other })
this.on('overlap_exit', ({other}) => {
  if (this.currentSensor === other) this.currentSensor = null
})
~~~

Tracked events are collision_enter/collision_exit or overlap_enter/overlap_exit. They use node IDs to track a target; select the appropriate interaction per pair.

### Hitboxes and body coordinates

Additional hitboxes are child nodes using script: "Collider". They can omit visual:
~~~json
{
  "name": "AttackArea",
  "script": "Collider",
  "config": {"startEnabled": false, "flipWithParent": true},
  "collider": {
    "body": "dynamic", "width": 50, "height": 24,
    "offsetX": 28, "offsetY": -32,
    "gravity": false, "immovable": true
  }
}
~~~

Use child.enable(), disable() and isEnabled() to control this body. Register overlaps with targets and apply the game's damage rules in the owner. For fixed invisible terrain, put a Collider node at the scene root with world x/y and a static body. A Collider nested under a moving node follows its parent.

physicsObject.x/y identify its origin; body.x/y identify the body's top-left. Use getPhysicsObject().x/y for node placement and body.reset() coordinates. Phaser body.radius is pre-scale; measure a world circle using body.width / 2. Do not pass world-pixel values directly to body.setSize/setCircle/setOffset: those Phaser methods use pre-scale coordinates and bypass the declarative pivot alignment. Author geometry in collider, or use separate child hitboxes for different gameplay states.

## Animation

Use one setup for animated nodes: animations.clips describes frames and timing, animator describes states and transitions, and scripts set parameters. A one-clip object uses one state and an empty transition list. More behaviors extend the same structure.

Clip field -> Meaning:
- source.texture: Override the node's visual texture for this clip
- source.type: atlas, image or spritesheet; normally inferred from visual
- frames: Named frame IDs, or FrameRef objects
- duration: Total duration in seconds; standard timing choice
- frameRate: Frames per second when duration is omitted, default 10
- frameDurations: Per-frame milliseconds; overrides duration and frameRate
- loop: Default true; set false for a finishing action
- onFinish: hold the final frame, or first; default hold
- pivot: Override visual anchor for this clip

Use named atlas frames for new assets. A FrameRef is an ID or {"frame": "attack_1", "offset": [0, 6]}; its offset changes only the visual.

Animator field -> Meaning:
- defaultState: Required for playback to start
- parameters: Named bool conditions and trigger requests
- states: {stateName: {clip: clipName}}
- transitions: Ordered rules; first matching rule wins
- from: One state name or Any, not an array
- to: Destination state name
- when: All conditions must match
- hasExitTime: Wait until the current non-looping clip finishes

A condition is {"param": "moving", "eq": true} or {"trigger": "attack"}. Use setBool(name, value), getBool(name), setTrigger(name), resetTrigger(name) and getState() on this.animator. Triggers are consumed by a matching transition. Any also matches the current state; entering the same state does not restart its clip. Express interruption and retrigger rules deliberately.

Do not also select clips with playAnim() on an animator-controlled node. Animations and animator state tables belong in NodeDef JSON, not runtime-generated tables hidden in script code.

### A complete prototype

After vibegame init, keep the generated index.html. These six files define a small prototype with movement, jumping, idle/run/attack animation and a DOM reset button. The attack demonstrates animation timing; it does not implement damage.

project.json:
~~~json
{
  "name": "Engine Guide Prototype",
  "version": "0.1.0",
  "engine": "vibegame@0.1.0",
  "settings": {
    "width": 640, "height": 360, "pixelArt": true,
    "backgroundColor": "#182028",
    "physics": {"gravity": {"x": 0, "y": 900}, "debug": false}
  },
  "startScene": "scenes/main.scene.json",
  "manifests": ["assets/manifest.json"],
  "inputMap": "config/input-map.json"
}
~~~

assets/manifest.json:
~~~json
{
  "hero": {
    "type": "placeholder_atlas",
    "frames": ["idle_0", "idle_1", "run_0", "run_1", "attack_0", "attack_1"],
    "pivot": [0.5, 1]
  }
}
~~~

config/input-map.json:
~~~json
{"left": ["A", "LEFT"], "right": ["D", "RIGHT"], "jump": ["SPACE"], "attack": ["J"]}
~~~

scenes/main.scene.json:
~~~json
{
  "name": "Prototype",
  "root": {
    "name": "Root",
    "children": [
      {"src": "entities/hero.node.json"},
      {
        "name": "Ground", "tags": ["ground"],
        "config": {"x": 320, "y": 340},
        "visual": {"type": "rect", "width": 640, "height": 40, "color": "0x465347"},
        "collider": {"body": "static"}
      }
    ]
  }
}
~~~

entities/hero.node.json:
~~~json
{
  "id": "hero",
  "name": "Hero",
  "script": "Hero",
  "tags": ["player"],
  "config": {"x": 120, "y": 280, "speed": 220, "jumpVelocity": -420},
  "visual": {"type": "atlas", "texture": "hero", "frame": "idle_0", "width": 48, "height": 72},
  "collider": {
    "body": "dynamic", "host": "separate",
    "width": 36, "height": 68, "worldBounds": true
  },
  "animations": {
    "clips": {
      "idle": {"frames": ["idle_0", "idle_1"], "duration": 0.6, "loop": true},
      "run": {"frames": ["run_0", "run_1"], "duration": 0.2, "loop": true},
      "attack": {"frames": ["attack_0", "attack_1"], "duration": 0.3, "loop": false}
    }
  },
  "animator": {
    "defaultState": "idle",
    "parameters": {"moving": "bool", "attack": "trigger"},
    "states": {
      "idle": {"clip": "idle"},
      "run": {"clip": "run"},
      "attack": {"clip": "attack"}
    },
    "transitions": [
      {"from": "idle", "to": "attack", "when": [{"trigger": "attack"}]},
      {"from": "run", "to": "attack", "when": [{"trigger": "attack"}]},
      {"from": "attack", "to": "run", "hasExitTime": true, "when": [{"param": "moving", "eq": true}]},
      {"from": "attack", "to": "idle", "hasExitTime": true, "when": [{"param": "moving", "eq": false}]},
      {"from": "idle", "to": "run", "when": [{"param": "moving", "eq": true}]},
      {"from": "run", "to": "idle", "when": [{"param": "moving", "eq": false}]}
    ]
  }
}
~~~

scripts/Hero.js:
~~~js
import { Node } from '../engine/Node.js'

export default class Hero extends Node {
  ready() {
    this.body = this.getPhysicsObject().body
    this.resetCount = 0
    for (const ground of this.findByTag('ground')) {
      this.scene.physics.add.collider(this.getPhysicsObject(), ground.getPhysicsObject())
    }
    this.resetButton = document.createElement('button')
    this.resetButton.type = 'button'
    this.resetButton.textContent = 'Reset position'
    this.resetButton.style.cssText =
      'position:absolute;left:480px;top:16px;width:140px;height:40px;pointer-events:auto'
    this.resetButton.addEventListener('click', () => {
      this.body.reset(this.config.x, this.config.y)
      this.body.setVelocity(0, 0)
      this.resetCount += 1
    })
    this.sceneTree.ui.mount(this.resetButton)
  }

  update(dt) {
    const input = this.sceneTree.inputMap
    const direction = Number(input.isHeld('right')) - Number(input.isHeld('left'))
    this.body.setVelocityX(direction * this.config.speed)
    if (input.isPressed('jump') && this.body.blocked.down) {
      this.body.setVelocityY(this.config.jumpVelocity)
    }
    if (direction) this.getVisualObject().setFlipX(direction < 0)
    this.animator.setBool('moving', direction !== 0)
    if (input.isPressed('attack') && this.animator.getState() !== 'attack') {
      this.animator.setTrigger('attack')
    }
  }

  runtimeState() {
    const object = this.getPhysicsObject()
    return {
      x: object.x, y: object.y, grounded: this.body.blocked.down,
      state: this.animator.getState(), resetCount: this.resetCount
    }
  }

  destroy() {
    this.resetButton.remove()
  }
}
~~~

Each update calls script, animator, then clip advancement. Attack takes priority over movement and exits to locomotion after finishing. Add jump/hurt/death states in the same structure.

### Animation and gameplay timing

Animator selects clips; it does not apply damage or open hitboxes. Game code owns these rules. For frame-coupled gameplay, check frames crossed since the previous update rather than currentFrameIndex === target: an update may skip an index. Reset this tracking on state exit, including interrupted actions. There is no animator timeline/frame-event field to configure.

For windup, active and recovery phases, use explicit clips/states when they carry distinct gameplay meaning. Use duration for whole-action timing and frameDurations only when particular frames need different holds. hasExitTime depends on a finished clip; a looping clip does not finish. The current player also does not advance completion for single-frame clips: use a multi-frame non-looping action for timed exit, or an explicit gameplay condition for a held pose.

## Children and reuse

Children are a gameplay hierarchy, not Phaser Containers. Initial config.x/y are world positions; subsequent parent movement and size changes propagate as deltas.

Parent change -> Child behavior:
- x/y movement: Child moves by the same delta
- Display width/height change: Relative position and child display size scale
- Horizontal flip: Inherited only with child config.flipWithParent: true
- Rotation or vertical flip: Not inherited

Horizontal inheritance mirrors the relative X, visual flip and collider offsetX. An edge without flipWithParent stops inherited flipping below that parent. Separate visuals follow their physics host and visualTransform offsets. Do not move a parent every frame to chase its own child: inherited deltas would feed that motion back into the child.

Node method -> Result:
- getChild(name): Direct child or null
- getNode(path): Child, ../Sibling or Group/Child lookup
- findByTag(tag): Enabled matching nodes across the scene
- sceneTree.nodes.get(id): Registered node by ID
- addChild(node): Async attachment and ready propagation
- instantiate(src, config): Async template instance attached as a child
- removeSelf(): Remove this node and descendants
- emit/on/off: Node events, bubbling toward parents

Reuse a definition with {"src": "entities/hero.node.json", "config": {...}}. Inline config shallow-merges; inline name, tags and enabled can override. Visual, collider, script and children come from the template. Inline id does not override a template's id. Use a fixed template ID only for a singleton; omit it on repeatedly spawned templates so each instance gets a new ID.

### Runtime spawning

Use .node.json templates for bullets, enemies and other runtime-spawned nodes. Boot discovers definitions and their scripts from scene src references. A template used only in script must be declared as a disabled scene child:
~~~json
{"name": "_BulletTemplate", "src": "entities/bullet.node.json", "enabled": false}
~~~

Then spawn it from the owning node:
~~~js
const bullet = await this.instantiate('entities/bullet.node.json', {x: 200, y: 120})
~~~

Disabled src references preload definitions and scripts without live objects. Do not call private SceneTree._buildNode() to bypass this path.

### Events and attachments

emit() calls local listeners and bubbles to the parent with source identifying the original emitter. Siblings receive no automatic bubbling. Use stable event names and payloads instead of a distinct event per weapon.

For an equipment slot, add a child with script: "MountPoint". Its config accepts offsetX/offsetY, aimRotation (default false) and flipWithParent (default true for this component). Call await slot.mount(src), slot.unmount() and slot.getMounted(). The mounted template must also be preloaded. aimRotation uses the current pointer direction; it does not rotate Arcade boxes.

### Scene changes

Do not treat changeScene(name) as an automatic scene loader. The current method destroys the tree; it does not fetch or boot the named scene. For multi-level games, keep a controller and spawn/remove preloaded level nodes, or implement an explicit loader that registers the new scene's definitions, scripts and assets before loading it. A full project reload can select a product-defined scenario. Verify the whole transition from normal player input.

## Modules

A module is a reusable Node subclass, not a second object API. The modules/index.md catalog identifies available modules and their config. Use script: "NameModule" to attach one, or extend it in a game script:
~~~js
import GameOverlayModule from '../modules/GameOverlayModule.js'
export default class GameMenu extends GameOverlayModule {
  ready() {
    super.ready()
  }
}
~~~

Use "script": "GameMenu" for scripts/GameMenu.js. Customize modules through config or local subclasses, not Module-suffixed copies in scripts/. Promoting reusable code belongs to the self-evolve workflow.

Read the selected module's source for its supported config and methods. Compose module behavior through ordinary imports, Node events and child nodes. Keep game-specific damage and rules in the owning game script. A module must not secretly rewrite another node's animator states/transitions.

## UI

Game UI is ordinary DOM mounted under sceneTree.ui.root. It follows the canvas position and display scale, with logical dimensions from project.json.settings. CSS px and percentages refer to this logical UI surface. Use flex, grid, transitions, keyframes, web fonts and SVG normally.

The root has pointer-events: none. Interactive children opt into pointer-events: auto, as in the prototype button. Decorative overlays should pass input through. Use logical px/% inside the game UI, not vw/vh or position: fixed.

UI need -> Standard implementation:
- Text, score, timer, menus, buttons, panels: DOM/CSS with a chosen web font
- Authored chrome, portraits, badges: Registered image in DOM or a Phaser visual
- Simple arrows, reticles and geometric icons: Inline SVG

Current project policy uses DOM text, not Phaser.Text. CSS UI and supplied module UI must match the game's art direction from their first version: deliberate typography, palette, shape, spacing and boundaries. An unstyled stand-in is not final art.

UI helper -> Contract:
- ui.mount(element): Attach an Element to the logical UI root
- ui.setImage(img, key): Set a registered image on an HTMLImageElement
- ui.setBackground(element, key): Use a registered image as CSS background
- ui.assetUrl(key): Resolve a registered image URL
- ui.root: Ordinary DOM root, without Shadow DOM

These helpers accept image and placeholder_image entries. They throw for missing keys, missing paths and unsupported types. Atlas/spritesheet/tileset entries are not DOM-image sources; use a dedicated frame-cropping renderer, such as the existing card module, when needed. CSS still determines display size and crop.

Game pause is a game-owned behavior: stop the gameplay the menu promises to pause, while keeping the required menu input, UI effects and audio active. Skip the relevant gameplay work inside update, or pause a gameplay scene while handling the menu elsewhere. Do not rely on sceneTree.running as a game-pause API; the boot-created controller's update path does not gate nodes with that flag. The supplied overlay pauses the Phaser scene and handles resume through DOM listeners. Verify both stopped gameplay and a working resume path.

## Assets and polish

Register every runtime asset in a manifest listed by project.json.manifests. Entry paths are relative to their own manifest directory. Use image for a single file and atlas for named multi-frame artwork.

Manifest field -> Meaning:
- type: image, atlas, placeholder_image, placeholder_atlas, or tileset
- path: File relative to this manifest; real assets require it
- sprites: Atlas frame map: {name: {bbox: [x, y, w, h], pivot?: [x, y]}}
- pivot: Optional entry-level visual anchor
- frames: Semantic names for placeholder_atlas
- shape, color: placeholder_image only; rectangle/circle/hex and a hex color

Placeholders generate pixels without a path. Use semantic manifest entries, not the engine's low-level __placeholder_atlas__ / __placeholder_image__ keys.

A real atlas entry looks like:
~~~json
{
  "hero": {
    "type": "atlas", "path": "hero.png", "pivot": [0.5, 1],
    "sprites": {"idle_0": {"bbox": [0, 0, 800, 1200]}, "idle_1": {"bbox": [800, 0, 800, 1200]}}
  }
}
~~~

This fragment illustrates the format, not a replacement for the prototype's entire hero atlas: that prototype also references run and attack frames.

### Placeholder to real art

Before parallel production, agree the runtime asset roles, manifest keys, action names, layout footprint and required layers. A stable name alone does not make a flat title picture interchangeable with four separate UI layers.

During the swap:

1. Read the actual delivered manifest and artwork.
2. Replace placeholder entries with real image/atlas entries and file paths.
3. Update clip frame lists and any per-clip source texture to match actual art.
4. Fit the visual to the agreed world-space object; preserve collider dimensions and anchor unless gameplay explicitly changes the object's physical size.
5. Verify standing, largest poses, UI readability, input targets and gameplay timing. Remove placeholder-only shape/color fields from real entries.

Keep clip/state identity and whole-action timing where behavior depends on them. Placeholder frame counts are provisional. Frame-coupled hit windows require explicit retuning and verification against the real frames. The result must preserve gameplay, not arbitrary placeholder pixel dimensions.

Artist production and cleanup instructions remain in artist's own workflow.

## Runtime control

Use vibegame run/play from the game root. Run headlessly unless the user asks to watch.

~~~sh
vibegame check .
vibegame run . -b --headless --port auto
vibegame play status
vibegame play activate
vibegame play snapshot
vibegame play screenshot -o evidence.png
vibegame close .
~~~

When several runtimes exist for one root, select a port: vibegame play --port PORT snapshot; vibegame close . --port PORT. Use vibegame close, not a broad process kill.

`--port` goes right after `play`, before the action. The action's own options go after the action:

~~~sh
vibegame play --port 8801 screenshot -o shot.png    # right
vibegame play screenshot --port 8801 -o shot.png    # wrong: prints the usage text
~~~

The last argument of every `vibegame play` action is the game project path. It is optional and defaults to the current directory, so `vibegame play screenshot shot.png` reads `shot.png` as a project; use `-o` for the output file. `play status` answers `active: false` while control mode is off; any answer at all means the page is connected.

### Runtime launch

run option -> Contract:
- --host: Listen address, default 127.0.0.1
- --port: Explicit port or auto; omitted means 8765
- -b / --background: Start detached and return
- --headless: No visible browser window
- --activate: Start runtime control paused at frame 0
- --debug: Show Phaser Arcade physics debug bodies; does not activate runtime control
- --renderer: auto, webgl or canvas; webgl fails when unavailable
- --fps: Render cap; 0 means uncapped
- --shot: Record .webm or .mp4; mp4 requires ffmpeg
- --bot: Run a Python realtime bot and report its result
- --max-seconds: Override bot time budget

Background and headless are independent. A background run can be headed. A headless run can stay attached. A run never replaces a runtime already on its port: if the port is taken, by this project or anything else, it exits with an error. Stop your own runtime first with `close --port PORT`, or take a free port with `--port auto`. run --status lists tracked sessions; run --logs [--port PORT] shows the log tail. close --all closes runtimes belonging to this project.

For render rate, explicit --fps overrides the project's fpsLimit. Without either, controlled runtime sessions use 60 FPS; 0 explicitly disables the cap. Frame stepping does not make all external clocks deterministic.

Pass game-specific URL parameters after --:
~~~sh
vibegame run . -b --headless -- preset=boss seed=42
~~~

Read these with URLSearchParams(location.search). runtime, activate, debug, physicsDebug, renderer and fps are reserved. The reserved ones last for the life of the tab: navigating it yourself (location.href = '...?scenario=X') keeps them, so the page stays connected to vibegame play. Game parameters follow the new URL. The bot's META.params uses the same parameter mechanism.

### Runtime commands

play command -> Effect:
- status: Inspect active state and controller mode
- activate: Take control and pause
- deactivate: Leave controlled mode
- pause: Pause immediately
- play: Resume free-running execution
- continue -f N: Advance N game-loop frames at normal game speed, then pause; default 60. Does not fast-forward.
- snapshot: Structured live state
- screenshot -o FILE: Composed viewport, including DOM
- refresh: Reload after edits
- input -a NAME --held / --release: Hold/release a mapped action
- input -a NAME: Inject a one-shot mapped press
- key -c CODE -t press/down/up: Raw keyboard event
- click -x X -y Y: Browser pointer click at game-world coordinates
- mousemove -x X -y Y: Browser pointer movement
- drag --from-x X --from-y Y --to-x X --to-y Y: Browser pointer drag
- set -n ID -p FIELD -v JSON: Write a runtime property
- eval CODE: Evaluate JavaScript with sceneTree, host and runtime available
- console -l LEVEL -s SEQ / --clear: Read or clear captured console entries
- network / --clear: Read or clear captured network entries

Under vibegame run, activate/pause freezes game frames, page timers and time reads, CSS animations and playing audio. The idle game loop stops rendering; status, snapshot, screenshot and control remain responsive. activate/deactivate retain the controller and preserve game-owned running, scene pause and physics pause states. continue counts game-loop frames even when a gameplay scene is paused; that scene stays paused and its nodes do not update. Audio that was playing resumes during continue/play and freezes again when runtime pauses; audio already paused by the game stays paused. This is normal-speed stepping, not fast-forward or sample-accurate audio synchronization.

While runtime is paused, click, mousemove, drag, key and input commands return status queued without changing the game. continue/play applies them in send order before advancing. Direct human input is blocked while the agent owns runtime control. deactivate, connection loss and page reload discard unexecuted inputs; deactivate releases runtime restrictions without closing the game's pause menu. set and eval are explicit inspection/editing tools and can still change state while paused.

Runtime time control covers the main game page. It does not make network/resource completion or external services deterministic. A deployed static game runs its ordinary browser loop without the runtime host.

Update the project's copied engine together with the runtime host. An older engine without the runtime clock integration fails startup with an explicit update message.

Pointer operations share the bot's Playwright executor. Chromium hit-tests the actual DOM/canvas target. Broker/input failures return errors without a synthetic canvas-event fallback. Check game state after input delivery. Mapped input and raw key commands remain separate engine input operations.

For screen-fixed DOM while the camera moves, use the bot or REST pointer payload with space: "client". CLI pointer coordinates remain game-world coordinates.

A snapshot includes frame, mode and nodes keyed by ID. Nodes expose config, transform and physics when available; runtimeState() adds game-specific values under runtime. Expose acceptance-critical state, including state owned by ordinary JS modules, through a host node. Use sceneTree.nodes.get(id), not window.__vibegameRuntime, to inspect gameplay.

~~~sh
vibegame play eval 'return sceneTree.nodes.get("hero").runtimeState()'
vibegame play set -n hero -p config.speed -v 260
~~~

Eval accepts multiline stdin and runs asynchronously; return a value, otherwise null.

### Batch

Batch runs commands sequentially in one Python process:
~~~sh
vibegame play batch <<'OPS'
activate
input -a right --held
continue -f 30
input -a right --release
snapshot
click -x 550 -y 36
snapshot
OPS
~~~

It accepts @file, inline text or stdin. Empty lines and comments are skipped. Lines may include the vibegame play or run prefix. Everything after eval is JavaScript; eval @file.js reads its content. A failing CLI/HTTP operation stops the batch and reports its index and snapshot. Check error responses and assertions as well as the batch exit status. Use individual commands when the next action depends on the result.

### Runtime bot

A bot is a Python policy inside the runtime runner, not another agent. It reads snapshots and returns (kind, payload, duration_seconds, reason). Do not import Playwright inside a bot.

~~~python
META = {"name": "walk_right", "max_seconds": 4}
def decide(snap, ctx):
    hero = snap["nodes"]["hero"]["runtime"]
    if hero["x"] >= 220:
        return ("done", None, 0, "Reached x >= 220")
    return ("hold", ctx.KEY["right"], 0.1, "Move toward target")
~~~

Run with vibegame run . --headless --bot tests/bot/walk_right.py. Bot mode requires foreground execution; --bot with --background is rejected. META may specify params for game URL parameters. An optional compact(snap, ctx) controls saved trace state. ctx exposes KEY, scratch, elapsed_s and tick. KEY maps semantic actions to physical key codes. Use scratch for a policy state machine or an elapsed timeline; mixing tick equality with early time-based returns can skip phases.

### Actions

Bot kind -> Payload / meaning:
- wait: None; wait for duration
- tap, hold: One key or a list; press/release then wait
- down, up: Change key state; policy must pair them
- mousemove: {x, y, space?} or [x, y]
- click: {x, y, button?, space?} or [x, y]
- drag: {from: point, to: point, steps?, button?, space?}
- breakpoint: Pause and remain available for step debugging
- done, fail: End with the corresponding verdict

Pointer coordinates default to game-world space; client uses browser viewport CSS pixels. Buttons are left/middle/right; Runtime API also accepts 0/1/2. Duration is the action's waiting/holding time, not a frame count.

Default bot output is .vibegame/logs/bot/<run-id>/: video.webm, trace.jsonl, result.json and stdout.log. run-id is YYYYMMDD-HHMMSS-<bot-basename>; --shot overrides the video path. Each trace row contains tick, t, action and state. result.json records ok, status, reason, setup_s, duration_s, decision_count, bot_file, bot_meta, error and console_errors. Statuses include done, fail, timeout, crash and breakpoint; only done sets ok true. Read the trace to confirm the intended behavior was exercised. After breakpoint, recording remains active and the runner waits for shutdown.

### Record and verify

play record NAME records discrete commands to .vibegame/traces/NAME/play.sh. Activate before recording. play record --stop ends it and appends deactivate. Screenshots go into the trace's logs directory. Review the commands before replay with bash or play batch @FILE.

Verify state transitions through actual input, inspect decisive screenshots and check console/network failures. Save repeatable tests, then close the runtime.

continue controls frame count, not a fixed simulation time per frame. Assert reached states, contact, ordering or bounded outcomes rather than an unverified assumption about elapsed milliseconds. node.breakpoint(reason) pauses an active controller for inspection. A bot and frame control do not automatically validate playability or readability.

### REST API

Advanced tools use the same host and port as the game runtime.

| Endpoint below /api/runtime/ | Method | Payload / result |
|---|---|---|
| activate, deactivate, pause, play | POST | Controller operation |
| continue | POST | {frames: N} |
| status, snapshot | GET | Controller or node state |
| screenshot | GET | PNG bytes |
| refresh | POST | Reload the browser |
| input | POST | {action, held?}; true holds, false releases, omitted presses once |
| key | POST | {key, type: "press" or "down" or "up"} |
| click, mousemove | POST | {x, y, space?, button?} |
| drag | POST | {from: {x,y}, to: {x,y}, steps?, button?, space?}; flat fromX/fromY/toX/toY also accepted |
| set | POST | {nodeId, path, value} |
| eval | POST | {code} |
| console | GET | level and since query parameters |
| console/clear | POST | Clear buffer |
| network | GET | since and failedOnly query parameters |
| network/clear | POST | Clear buffer |

## Runtime AI

Game code may call a model through the supplied browser interface:
~~~js
import { Vlm } from '../engine/ai/Vlm.js'
const reply = await Vlm.describe({
  prompt: 'Choose one legal action from the supplied game state.',
  system: 'Return JSON with one action field.',
  images: []
})
~~~

Vlm.describe accepts prompt, optional images, system and model. It POSTs to the game's backend at apiUrl('api/ai/vlm') and returns response JSON. The backend defines the response, commonly including text. For runtime image generation, import { Imagegen } from ../engine/ai/Imagegen.js. Imagegen.generate({prompt, refs?, model?, size?, aspect?, resolution?, quality?}) POSTs to apiUrl('api/ai/imagegen'); the expected response contains dataUrl. The runtime host supplies neither game-model backend nor credentials.

Keep credentials on the backend. Configure its address with project.json.runtimeDefaults.dev.apiBaseUrl; restart the runtime after changing that address. Use engine/url.js helpers for resourceUrl(path), assetUrl(path), fetchJson(path) and apiUrl(path), so game code works under deployment prefixes.

The game decides when to ask, what information is visible to the model, which actions are legal and how failures appear to the player. Parse and validate returned actions before changing game state. Log the request and outcome. Expose pending/completed/failed state through a node so runtime tests can distinguish a model decision from an unavailable service. Do not block the initial game boot on an external model request.

Packaging the backend and configuring production URLs are covered in [deployment.md](deployment.md). Game-specific chatbot design and team handoff belong to the runtime-ai collaboration contract.
