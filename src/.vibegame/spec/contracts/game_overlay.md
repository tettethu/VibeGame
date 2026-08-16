# Pause Overlay Contract

Full-screen DOM overlays for pause, death, victory, and similar non-diegetic prompts. Ships with `modules/GameOverlayModule.js` — the contract IS the module's user-facing manual.

## Pattern 1: dom-overlay-with-phaser-pause

### When to use

Use this pattern when the game needs full-screen menus that interrupt play (pause, death, victory, level-complete, settings) and the world must truly freeze while shown.

Good fits:

- Single-screen action / arcade / roguelike where ESC opens a pause menu.
- Death overlays that show "YOU DIED" + Restart / Quit buttons.
- Victory overlays that show a title + Continue / Quit buttons.
- Any custom prompt menu (settings, confirm-quit, level-select) that should pause physics / animations / timers.

Do **not** use this pattern when the menu is part of normal HUD that does not pause the game (resource counters, minimap, chat). Those are HUD nodes, not pause overlays.

Do **not** use this pattern when the project explicitly wants a Phaser-rendered modal (text on canvas, pixel-art panel inside the game world). For those, build a Phaser scene with `scene.scene.launch` and a dedicated pause scene — that is a different contract not covered here.

The critical correctness property: this pattern halts BOTH `sceneTree.running` AND `scene.scene.pause()`. Anything halting only one will leak — `sceneTree.running = false` alone leaves Phaser physics / anims / timers running; `scene.scene.pause()` alone leaves vibegame `Node.update(dt)` ticking. The module bakes the correct two-line pause into a single `showMenu` call.

### Responsibility

#### Artist

Artist does not participate in this contract yet. Fill in this part after a successful project.

#### Architect/Programmer

Architect/Programmer owns wiring and configuration:

1. **Place a `GameOverlayModule` node** in the scene tree. Reference the module from scene JSON as `"script": "GameOverlayModule"`. Recommended placement: as a child of the root manager so menu actions can emit / observe game-state events through the manager.

2. **Declare menus** in `config.menus`. Each menu has an `id`, optional `title` / `subtitle`, `pausesGame` flag (default false — set `true` for pause/death/victory), optional `toggleKey` (DOM key name like `"Escape"` to bind a global keydown listener), and a `buttons` array.

3. **Use built-in actions** for the common cases:
   - `'resume'` — calls `hideMenu(currentId)`, which resumes the game if the menu had `pausesGame: true`.
   - `'restart'` — calls `window.location.reload()`. Required for "fresh start" because the engine's `changeScene` only destroys current nodes; it does not reload scripts / assets / Phaser state.
   - `'quit'` — calls `window.location.reload()` (or a custom destination). Override by passing a function instead of a string.

4. **For custom actions**, pass a function as `action`: `{ label: 'Settings', action: (overlay) => overlay.showMenu('settings') }`.

5. **Style** the overlay via `config.style`. If `panelTexture` / `buttonIdleTex` are present in the asset manifest, the module uses them as `background-image`. If absent, the module falls back to plain dark divs.

   Those divs are a placeholder for development only and must not ship: see `engine/ui.md`, which requires UI to match the project's art from its first version. Panel art is not the only way to satisfy that — subclass the module and restyle the DOM it returns, which reaches shippable quality with CSS alone:

   ```js
   _buildMenu(menu) {
     const outer = super._buildMenu(menu)   // module owns the structure
     outer.style.background = SKIN.scrim    // subclass owns the skin
     Object.assign(outer.firstElementChild.style, SKIN.panel)
     for (const b of outer.querySelectorAll('button')) Object.assign(b.style, SKIN.button)
     return outer
   }
   ```

   Restyle the returned tree rather than reimplementing the builder, so the subclass survives changes to the module's structure. The module writes inline styles, so an external stylesheet cannot override it.

6. **Hurt flash** (red full-screen blink on player damage) is a built-in feature: call `overlay.flashHurt()` from the player controller's hit handler. Independent from menu state.

Reference scene placement:

```json
{
  "name": "Overlay",
  "script": "GameOverlayModule",
  "config": {
    "menus": [
      {
        "id": "pause",
        "title": "PAUSED",
        "pausesGame": true,
        "toggleKey": "Escape",
        "buttons": [
          { "label": "Resume",  "action": "resume" },
          { "label": "Restart", "action": "restart" },
          { "label": "Quit",    "action": "quit" }
        ]
      },
      {
        "id": "death",
        "title": "YOU DIED",
        "pausesGame": true,
        "buttons": [
          { "label": "Restart", "action": "restart" },
          { "label": "Quit",    "action": "quit" }
        ]
      },
      {
        "id": "victory",
        "title": "VICTORY",
        "subtitle": "The arena is yours.",
        "pausesGame": true,
        "buttons": [
          { "label": "Restart", "action": "restart" },
          { "label": "Quit",    "action": "quit" }
        ]
      }
    ],
    "style": {
      "panelTexture": "ui_panel",
      "buttonIdleTex": "ui_button_idle",
      "fontFamily": "'Cinzel', serif",
      "titleColor": "#e8d5a3"
    }
  }
}
```

Trigger menus from game logic:

```js
// Player died
this.findByTag('overlay')[0]?.showMenu('death')

// Boss defeated
this.findByTag('overlay')[0]?.showMenu('victory')

// Player took damage (hurt flash; does not pause)
this.findByTag('overlay')[0]?.flashHurt()
```

Common mistakes:

- Calling `this.sceneTree.running = false` directly to pause. Use `overlay.showMenu(id)` with `pausesGame: true` — the module handles both clocks.
- Using `engine.SceneTree.changeScene` for "restart". It does NOT reload assets/scripts. The `'restart'` action correctly uses `window.location.reload()`.
- Baking button labels into the panel art. Buttons are DOM elements composited on top of the panel image; the panel should be just the frame.
- Showing a pause menu while another `pausesGame: true` menu is already open. The module does not stack — call `hideMenu(otherId)` first, or treat menus as mutually exclusive.

#### Player

Player owns runtime verification:

- Verify the toggle key (default `Escape`) opens / closes the bound menu.
- After showing a `pausesGame: true` menu: snapshot a few entity positions, wait several seconds, snapshot again — positions must be identical (proves Phaser physics is paused). Also verify any in-flight animations stop visibly.
- Verify resume returns control: animations continue, input registers, projectiles continue from their paused positions.
- Verify Restart actually reloads the page (URL unchanged, fresh state, full HUD reset).
- Verify hurt flash is brief (~150ms) and does not interfere with subsequent input.

Use Runtime API:
- `vibegame play input --key Escape` to send the pause key.
- `vibegame play screenshot` before and during pause to confirm freeze.
- `vibegame play snapshot` to compare positions.

#### Reviewer

Reviewer owns acceptance:

- Confirm `pausesGame` flag matches the design intent for each menu. A "victory" overlay should pause; a transient toast should not.
- Reject implementations that only stop `sceneTree.running` (insufficient — physics keeps running).
- Reject pause flows that rely on `inputMap.isPressed('pause')` for resume. The inputMap does not advance frames while paused, so the resume key must come from a DOM listener — this is built into the module via `toggleKey`.
- Confirm the module is loaded directly from `modules/GameOverlayModule.js` via the `Module`-suffix routing. Do not allow project-local copies of the module file under `scripts/`.

### Manifest and asset boundary

- `ui_panel`: registered as `image` type. Optional — without it the module renders plain dark divs.
- `ui_button_idle`, `ui_button_hover`: registered as `image` type. Hover variant is optional (CSS filter brightness is the default hover treatment to avoid bbox-mismatch squish).
- No baked text in panel images. Titles / subtitles / button labels are DOM text.
- Fonts are NOT artist work. When the design wants a stylized font (e.g. Cinzel for gothic), orchestrator sources the font from Google Fonts / a font CDN and `programmer` wires the `@font-face` rule into the page CSS. The font family name then goes into `config.style.fontFamily`.
