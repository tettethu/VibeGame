# Digit HUD Contract

Digit HUD covers score, timer, combo number, best score, and other frequently-changing numeric UI.

## Pattern 1: dom-css-digit-hud

### When to use

Use this pattern when a game needs readable runtime numbers that change often, especially score or timer UI. This is the default route unless a custom raster digit sheet has already passed strict QA.

### Responsibility

#### Artist

Artist does not participate in this contract by default. Generated raster digit sheets failed in practice because digits were clipped, adjacent cells bled into each other, `0` was missing, and label text such as `BEST` split across cells. Artist may still provide icon sprites around the numeric UI, such as miss marks, hearts, badges, or decorative frames.

#### Architect/Programmer

Programmer owns the runtime numeric display using DOM/CSS or another engine-approved UI text route. Do not use Phaser.Text when the project UI rules forbid it. Use CSS font, weight, outline, shadow, color, and animation to match the game's art direction.

If decorative sprite icons are present, load them from `assets/manifest.json` or as DOM image URLs according to the project UI stack.

#### Player

Player verifies that numbers are readable at runtime against the real background and do not cover critical gameplay targets.

#### Reviewer

Reviewer rejects raster digit sheets unless all of these are true:

- digits `0-9` are present.
- every required label, such as `BEST`, is a complete single usable asset.
- no digit is clipped.
- no digit contains part of an adjacent digit.
- no marker-color artifacts remain inside holes or counters.
- all digits share a consistent baseline, scale, outline, and style.
- runtime can assemble any expected score value without missing glyphs.

### Manifest and asset boundary

Register only actual sprite assets that pass QA, such as icons or decorative frames. Do not register failed digit experiments. If the score is DOM/CSS, it does not belong in `assets/manifest.json`.
