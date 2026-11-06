# Tests

Project-level regression tests live under `tests/`. This is shared, long-lived test code — distinct from per-task `Task dir/evidence/` artifacts.

## Layout

```
tests/
  test_<topic>/             one directory per test topic, e.g. test_player_move
    test.sh                 entry point
    assert_*.py             python assertion scripts called from test.sh
    evidence/               runtime output (gitignored)
      snapshot.jsonl        appended snapshot history
      *.png                 screenshots
```

`test_<topic>` names a long-lived subject (player movement, weapon system, room flow, boss phase 1...), not a transient task. Multiple tasks add or change asserts inside the same test directory over time.

## test.sh contract

Every `test.sh` exposes the same interface so any caller can run any test the same way:

- **Input**: `PORT` from environment. The script reads it (`: "${PORT:?PORT is required}"`) and passes it to every `vibegame play` invocation. No CLI args, no stdin.
- **Output**: every artifact written under `$(dirname "$0")/evidence/`. Nothing written anywhere else.
- **Failure**: on a failed assertion, exit non-zero **without** stopping the runtime. The live runtime on `$PORT` is left running so a debugging agent can reattach via `vibegame play --port "$PORT"` and inspect the failed frame.

Typical pipeline inside `test.sh`:

```bash
: "${PORT:?PORT is required}"
DIR="$(cd "$(dirname "$0")" && pwd)"
EVIDENCE="$DIR/evidence"
mkdir -p "$EVIDENCE"

vibegame play --port "$PORT" activate
vibegame play --port "$PORT" input -a move_right --held
vibegame play --port "$PORT" continue -f 30

vibegame play --port "$PORT" snapshot >> "$EVIDENCE/snapshot.jsonl"
vibegame play --port "$PORT" snapshot | python3 "$DIR/assert_player_move.py" || exit 1

vibegame play --port "$PORT" screenshot -o "$EVIDENCE/move_right.png"
```

There is no global aggregator (no `run_once.sh`). Callers run individual `test.sh` files directly with the port they manage.

## Participation

| Agent | Create | Modify | Run |
|---|---|---|---|
| `architect` / `programmer` | yes, during approved implementation | yes, within task scope | yes, during self-testing; hand off evidence |
| `player` | yes — creates a new `test_<topic>/` when a topic first earns one | yes — adds/updates assertions when their task touches the topic | yes — runs new/changed tests; may reuse applicable results |
| `reviewer` | no | yes — when a failure reveals an outdated assertion the reviewer can fix locally | **mandatory** during final review: runs every test in `tests/` |
| `orchestrator` | no | yes — used as a debugging aid when triaging issues | selective — runs whichever tests are relevant to the current question |
| `auditor` | no | no | **never** — `auditor` does static review only; running the runtime is not its job. Do not write prompts that ask `auditor` to invoke `vibegame play` or `tests/test_*/test.sh` |

When a test fails, whoever finds out fixes it directly — no fixed arbitration:
- a true regression → change the code that broke
- a legitimate behavior change per `prd.md` → update the assertion to match

## Shared runtime evidence

Architect/programmer self-tests before handing the completed implementation to auditor and then player. Player independently accepts the task; reviewer independently accepts the final game. Player may reuse test results; reviewer may reuse task evidence while retaining its final review checklist.

Index evidence in task `log.md`: architect/programmer appends `## Runtime Evidence` under `# Programmer`; player references it from `# Player`. For each checked claim, record:

- Expected and observed results, with pass/fail and any unverified cases.
- Reproduction commands or test/bot path, starting state, and inputs. Record any state setup or skipped steps; skipped steps remain unverified.
- Absolute artifact paths and the relevant fields, frames, or timestamps. Choose evidence that proves the claim; no mandatory media bundle.
- Tested workspace, revision, and relevant code/config/assets/test state. For dirty or shared files, retain contents, diff, or hashes so consumers can compare them; HEAD alone is insufficient.

Keep each handed-off run intact under `Task dir/evidence/<run-name>/`, or reference a unique bot/trace run directory. Copy mutable regression outputs into the task run directory before handoff. After changing files, reload them in the runtime before capturing evidence for the changed build.

Consumers open the actual artifacts and check coverage and applicability to the current files, including auditor fixes and integration changes. Record reused results with their source and reason; rerun missing, stale, doubtful, or high-risk checks. Run new/changed tests and recheck failed behavior after a fix. Reviewer still runs the full regression suite, independently plays the final core loop, and judges visual quality and feel.

## What to write a test for

Write a test when:
- An acceptance criterion in `prd.md` can be asserted programmatically (e.g. "boss drops loot on death" — assert a loot node spawns after `boss.hp` reaches 0). The test is the task's hard pass evidence and stays as regression coverage afterward.
- A bug that surfaced has been fixed. Add an assertion that would have caught it.

Do not write:
- One-shot debug scripts. Use them inline and discard; don't commit them to `tests/`.
- Pure visual / feel checks that need a human eye. Those stay as screenshots in `Task dir/evidence/`, not here.

## Writing good e2e tests

These tests are end-to-end against a live runtime: input goes in, frames advance, snapshot or screenshot comes out. A few principles keep them useful instead of flaky.

### Translate ACs into "interaction → expected snapshot field"

Take each acceptance criterion in `prd.md` and rewrite it as a triple:
- the interaction sequence (what `vibegame play input` / `continue` calls drive it)
- the snapshot field (or `eval` result) that proves it happened
- the expected value (or comparison)

Example: AC "rolling makes the player invincible for 0.5s" →
- interaction: `play input -a roll && play continue -f 2`
- field: `nodes[player].runtime.isInvincible`
- expected: `true` immediately, `false` after `play continue -f 32` (0.5s at 60fps)

If you can't translate an AC this way, it's probably a visual / feel AC — leave it as a screenshot in `Task dir/evidence/`, not in `tests/`.

### Pick stable assertion fields

Best (deterministic, tolerant to internal refactor):
- numeric runtime fields (`hp`, `x`, `y`, `phase`, `ammo`)
- counts (the number of snapshot `nodes` whose `tags` include `enemy`)
- boolean states / enum strings

Fragile (avoid):
- floating-point equality — use range checks (`abs(x - 304) < 1`)
- pixel colors — those drift with art changes
- exact tween-mid values — use start / end states only

### Reproducibility

- Aim for reproducible tests. For random behavior such as wandering or attack selection, consider seeds or presets; weigh implementation cost against verification benefit rather than requiring exact replay.
- Never `sleep`. Use `vibegame play continue -f N` to advance N frames.
- Don't depend on wall clock. Use frame counts.
- If the test depends on an initial state, set it explicitly via `play eval` rather than assuming default.
- One test per scenario. Don't chain unrelated assertions in one `test.sh` — when one fails, the rest never run, and the failure cause is muddier.

### Use the "fail with runtime alive" trick

A failed `assert_*.py` exits non-zero but **does not stop the runtime**. After a failure, an agent (you, orchestrator, reviewer) can:

```bash
vibegame play --port "$PORT" screenshot -o /tmp/failed.png
vibegame play --port "$PORT" snapshot | jq '...'
vibegame play --port "$PORT" eval "..."
```

…right at the failed frame, no replay needed. Design `test.sh` so the failed frame is the interesting frame — don't run extra interactions after the assert.

### Granularity

One `test_<topic>/` per long-lived subject (`test_player_move`, `test_weapon_basic_attack`, `test_room_transition`). Inside a topic, multiple `assert_*.py` files cover related sub-behaviors that share the same setup. When a topic grows past a handful of asserts, split into a new `test_<topic_subset>/`.
