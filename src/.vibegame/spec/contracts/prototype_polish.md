# Prototype / Polish Contract

An optional two-task workflow: implement gameplay with placeholders, then integrate real art in a scoped polish task. Real-art-from-day-one tasks and disposable experiments need not use it.

The [engine guide](../engine/index.md#assets-and-polish) owns manifest formats,
world-size authoring and art replacement. Its [animation section](../engine/index.md#animation)
owns the setup. This contract only assigns workflow decisions and handoffs.

## Pattern 1: prototype

### When to use

A gameplay task intentionally prepares for a later real-art pass. Use placeholder visuals with the final texture keys and semantic frame names.

### Responsibility

#### Orchestrator

- Enumerates each controllable node's required clips, such as idle, move, attack
  and hurt. Missing requirements are not the architect's product decision.

#### Architect

- Plans placeholder entries and the agreed future asset names.
- If required clips are missing, reports [MISSING LEAD DECISION] animation clips: <node>.
- Uses 4 frames per clip unless the PRD specifies another count. This is a
  workflow planning default, not an engine restriction or an artist delivery guarantee.
- Records gameplay timing independently of replaceable art where possible.
- For frame-coupled actions, adds a Frame-coupled events section to plan.md:
  clip, meaningful frame/window, and gameplay effect. Attack hitboxes, dash
  windows and release-commit frames must survive the later art integration.

#### Programmer

- Implements the plan using the engine guide.
- Keeps the agreed texture keys and semantic frame names. Remaining work is
  visible through manifest placeholder types, not TODO comments in scripts.

#### Reviewer

- Accepts placeholder appearance for the in-scope prototype.
- Flags gameplay dependent on raw frame indices unless declared in the
  Frame-coupled events handoff.

## Pattern 2: polish

### When to use

An existing prototype swaps to real art without redesigning its gameplay. Use real assets registered in the manifest and present on disk.

### Responsibility

#### Orchestrator

- Names the nodes/assets in scope; polish need not cover the whole project.
- Confirms delivery or commissions artist before the real-asset implementation.

#### Artist

- Produces and registers the agreed real assets through the independent
  [sprite production workflow](../art/sprite.md).

#### Architect

- Cross-checks every required real asset against the manifest and disk.
  Missing files/keys stop planning with [ASSETS GAP] <keys>.
- Plans art fitting against the existing gameplay dimensions using the engine guide.
- Reviews the prototype's Frame-coupled events against delivered art and names
  each required timing adjustment, such as hitbox-on/off or a dash hold frame.
- Lists remaining placeholder entries as either in scope or deliberately deferred.

#### Programmer

- Applies the planned swap and timing changes.
- Does not redesign gameplay to accommodate the new art.

#### Reviewer

- Checks that in-scope entries are real assets, with no placeholders left.
- Verifies visual/physical alignment and the agreed frame-coupled actions in motion.
- Accepts placeholders outside this polish task's explicit scope.
