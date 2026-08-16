# Basic: Engine & Tech Setup

> **Owner**: Designer (initial setup, bootstrap task)
> **Updated by**: Architect (if tech requirements change)

---

## Engine

<!-- TODO: Choose one. Default is Phaser. -->

- [ ] **Phaser** — default for 2D games. Physics, input, animation, tilemaps built-in.
- [ ] **Canvas (raw)** — ultra-minimal, no physics needs.
- [ ] **PixiJS** — rendering performance is the primary concern.

**Decision**: <!-- TODO: which engine and why -->

---

## Scale Mode

<!-- TODO: Choose one based on game type. -->

| Mode | Behavior | Use when |
|------|----------|----------|
| **ENVELOP** | Fills screen, may crop edges | Action / exploration |
| **RESIZE** | Canvas resizes to window | Shows more map on large screens |
| **FIT** | Letterboxed to fit | All content must always be visible |

**Decision**: <!-- TODO -->
