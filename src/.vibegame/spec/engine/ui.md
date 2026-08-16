# UI Guide

The engine provides a DOM UI Layer aligned with the Phaser canvas. It is not a widget library: game scripts still own their HTML, CSS, SVG, text, animation, and interaction logic.

## UI must match the art from its first version

UI built with CSS instead of art assets is still art direction. Its first version must already match the style of the project's current assets and concept art — at prototype stage too, when the only reference is a concept image. Refine it once the real assets land; do not defer style until then.

A panel is not done until each of these has a deliberate answer: palette sampled from the game's own art, silhouette and corner treatment that sit with that art, a defined edge, and type consistent with the game's identity. An unstyled default rectangle is a placeholder and must not ship.

UI supplied by a module is held to the same requirement. Modules are not editable; subclass and restyle what the module builds.

## UI Layer

Access the layer from any game `Node`:

```js
const ui = this.sceneTree.ui

const overlay = document.createElement('div')
overlay.id = 'pause-overlay'
overlay.innerHTML = `<button class="resume">Resume</button>`
ui.mount(overlay)
```

`ui.root` is ordinary DOM without Shadow DOM. Project CSS can use flex, grid, gradients, filters, pseudo-elements, transitions, keyframes, web fonts, inline SVG, and CSS variables as usual.

The root uses `project.json.settings.width/height` as its logical size and follows the canvas position and display scale. A CSS value such as `left: 32px` or `width: 180px` therefore uses the same screen-space logical pixels as Phaser. Percentages are relative to the logical UI root.

Use logical `px` and `%` inside game UI. Do not use `vw`, `vh`, or `position: fixed`: those refer to the browser page rather than the game canvas.

The root has `pointer-events: none`. Interactive overlays or controls must opt in:

```css
#pause-overlay,
#pause-overlay button {
  pointer-events: auto;
}
```

## Manifest assets in DOM UI

DOM UI consumes semantic manifest keys through the UI Layer:

```js
ui.setImage(iconElement, 'icon_heart')
ui.setBackground(panelElement, 'hud_panel')
const url = ui.assetUrl('weapon_pistol')
```

Supported entry types:

| Type | DOM result |
|---|---|
| `image` | Resolves `path` below the project asset root. PNG, WebP, SVG, and other browser-supported image files use the same type. |
| `placeholder_image` | Uses the engine placeholder builder and returns a generated PNG data URL. No placeholder file is needed. |

Missing keys, missing paths, and unsupported types throw errors. `placeholder_atlas`, `atlas`, `spritesheet`, and `tileset` are not DOM UI sources in this interface.

CSS still decides display size, position, crop, opacity, rotation, filters, and animation. The manifest key only chooses the source image.

## Three visual routes

### Route 1 - CSS and web font

Use for score, HP text, menus, buttons, timers, pause or game-over text, dialog, panels that can be expressed with CSS, and other text-heavy UI. Mount the DOM under `sceneTree.ui`.

In-game text uses CSS and a chosen web font, never `Phaser.Text`.

### Route 2 - Manifest image

Use for chrome that needs authored pixels: themed panels, heart icons, segmented bars, image-backed buttons, and weapon icons.

In DOM UI, use `sceneTree.ui` with the manifest key. For an in-world object rendered by Phaser, use the same key as the node visual texture. Text layered over UI chrome still uses Route 1.

### Route 3 - SVG

Use inline SVG for simple geometry such as arrows, plus signs, target reticles, and upgrade symbols. If the SVG is an authored asset that should be replaced during polish, register its path as `type: "image"` and use its manifest key.

## Choosing a route

Choose the route that matches the UI element's required visual form.

| Element | Route |
|---|---|
| Score, HP number, menu label, dialog | CSS and web font |
| CSS panel or button | CSS and web font |
| Authored panel, badge, bar, weapon icon | Manifest image |
| Simple geometric icon | Inline SVG |
| Pre-rendered logo or engraved text | Manifest image |

When in doubt, use CSS and web font.
