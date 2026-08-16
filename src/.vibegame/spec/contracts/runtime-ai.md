# Runtime AI

This contract covers games that call a language model while the game is running. Read `engine/ai/Vlm.js` for its method-level interface. This file explains when to use that interface, what each role must decide or deliver, and what failures need attention.

## Shared runtime setup

```text
Browser game
  -> engine/ai/Vlm.js
  -> game backend
  -> model service
```

- The browser never contains the model API key. The game backend reads it from server-side configuration.
- `project.json.runtimeDefaults` tells the browser where to find the backend in dev and deploy.
- `Vlm.js` throws an error when the backend request fails. The game decides how that error affects the player.
- If the released game needs the backend, include it through `project.json.releaseExtraRoots`.
- Read `engine/ai/Vlm.js` and `engine/url.js` for the exact request and URL behavior.

## Pattern 1: chatbot-as-game-character-or-player

### When to use

Use this Pattern when a game character or player talks through a language model and may also choose from a small set of game actions.

The game calls the model at a specific moment. It sends only information that the character or player is allowed to know. It then asks for either:

- Text that the player will read.
- A small JSON response for an action such as voting, choosing a target, answering yes or no, or choosing a direction.

The model does not change game state directly. The game checks every action response before applying it.

For example:

```text
The game sends:
- facts known by everyone;
- facts known only by this character;
- allowed vote targets: [2, 5, 8].

The model returns:
{"targetId": 5}

The game checks:
- targetId exists;
- 5 is one of [2, 5, 8].

Only then does the game apply the vote.
```

`prd.md` defines what the player sees when the model cannot be reached, returns empty text, or returns an invalid action. A local fallback is one possible product choice, not a requirement of this Pattern.

The `orchestrator` writes the expected product behavior in `prd.md`. The `architect` turns it into a technical plan and chooses how each claim will be verified. The `programmer` implements the plan. The `auditor` checks the code without running the game. The `player` runs the verification selected in the plan. The `reviewer` applies the normal final quality gate.

**Verified scope**: a single-player text social-deduction game with many chatbot players. Each chatbot produced turn speech and simple game actions. That project used a local rule-based player when the model was unavailable.

### Basic Knowledge

This Pattern describes a request-response chatbot, not an autonomous agent. The game decides when to call the model, what the model may know, what it may return, and whether the returned action is accepted.

Two model-service issues caused failures in practice:

1. Some reasoning models spend most of their output budget on hidden reasoning and leave the final answer empty. Give those models enough output budget and retry once when the final answer is empty.
2. Different model services use different settings to enable thinking. Send only settings supported by the selected model.

The runtime server reads `apiBaseUrl` when it starts. Restart the runtime after changing the backend URL or port.

### Responsibility

#### Orchestrator

- Select this Pattern when a game character or player needs model-generated speech and simple game actions.
- In `prd.md`, state which character or player uses the model, when the game calls it, what speech and actions it must produce, which outputs may change game state, and what the player sees when the model call fails or returns invalid output.

#### Architect

- In `plan.md`, describe how the game uses `Vlm.js`, where the backend lives, how the browser finds it, and how the backend is included in the release.
- For every chatbot action, write down what information the game sends, what JSON the model must return, which returned values are allowed, and what happens when the response is empty or invalid.
- For each runtime AI claim, choose `bot` or `runtime api` in the normal Verification Plan. Declare only the `runtimeState()` fields that the selected verification uses.
- Choose one source for the model configuration. Keep the backend address consistent with `runtimeDefaults.dev.apiBaseUrl`.

#### Programmer

- Implement the prompts and game information described in `plan.md`.
- Before changing game state, parse the model response and check every required field and allowed value.
- Implement the failure behavior defined in `prd.md`.
- Log each model request and its outcome with enough information to identify the model, action, response, and failure.
- Send only thinking settings supported by the selected model.

#### Auditor

- Confirm that browser code contains no model API key and that the backend reads the key from server-side configuration.
- Follow every code path where a model response changes game state and confirm that the response is checked first.
- Confirm that empty, invalid, and failed responses follow the behavior defined in `prd.md`.
- Confirm that the model configuration has one source.

#### Player

- Run the `bot` and/or `runtime api` steps selected in `plan.md` for each runtime AI claim.
- Collect the state, screenshot, trace, or bot result requested by the Verification Plan.
- If a claim depends on whether a result came from the model or on why a request failed, verify the corresponding `runtimeState()` fields declared by the architect.

#### Reviewer

- Use the task logs and runtime evidence during the normal final review.
- Reject a release that exposes the model API key or omits a backend required by the goal.

### Common mistakes

- Building another browser-side model client instead of using `Vlm.js`.
- Giving a reasoning model too little output budget, so its final answer is empty.
- Sending a thinking setting that the selected model does not support.
- Changing the backend address but verifying against a runtime that still uses the old `apiBaseUrl`.
- Applying model JSON to game state without checking its fields and allowed values.
- Writing a verification claim that needs model-source or failure information without exposing that information through `runtimeState()`.
- Sending only a raw conversation transcript when the chatbot also needs structured facts about the game.
