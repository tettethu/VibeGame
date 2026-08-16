# VibeGame Setup

## Prerequisites

- Python 3.12 or newer.
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/).
- `tmux`.
- Claude Code or Codex.

Node.js and npm are not required for the standard setup. `setup.sh` checks `uv` and `tmux`; it does not choose or install an agent CLI.

## For Humans

```sh
./setup.sh
```

The default mode is `human`. The script installs the `vibegame` CLI and Playwright Chromium, then opens an interactive wizard for configuring the agent providers, VLM, image generation, and default language.

The supported installation path is a cloned repository installed in editable
mode. The CLI reads the engine, templates, Dashboard, and init sources from that
checkout. A non-editable wheel is not currently self-contained.

## For Agents

Help the user set up VibeGame as follows:

1. Run `./setup.sh --mode agent`. This installs the Python dependencies, the `vibegame` CLI, and Playwright Chromium without opening the interactive wizard.
2. Show the user the default CLI provider and model configuration. Explain the available options (`claude`, `claude-thirdparty`, and `codex`), then ask whether they want to change the defaults. Never guess API keys, base URLs, or model IDs.
3. Configure `src/.vibegame/settings.json`, `src/.vibegame/defaults.json`, and `.env` using the sections below.
4. If the user wants to use Codex, run `vibegame setup codex-hooks` after configuring the files. This command is non-interactive. Then ask the user to open Codex, enter `/hooks`, and trust all newly added VibeGame hooks.

### `src/.vibegame/settings.json`

This file selects the CLI harness and model for each agent. When editing `agents`, preserve the existing `hooks` configuration.

The built-in CLI harnesses are:

- `claude`: Uses the user's existing Claude Code configuration. Available model names are defined in `src/.vibegame/team/models.json` and currently include `opus[1m]`, `opus`, `sonnet`, and `haiku`.
- `claude-thirdparty`: Launches Claude Code with provider-specific environment variables, such as `ANTHROPIC_BASE_URL`. It uses the same model aliases as `claude`, but each alias must be mapped to the provider's model ID in `.env`.
- `codex`: Uses the user's existing Codex configuration. It supports the GPT models listed under `codex` in `src/.vibegame/team/models.json`.
- `glm` (experimental, text-only): Uses Claude Code with the GLM Anthropic-compatible endpoint. It requires `GLM_API_KEY` in `.env` and should only be assigned to roles that do not need to inspect images or game frames.

Different agents may use different CLI harnesses. Each selected model must be supported by the corresponding harness.

Configure an agent like this:

```json
{
  "agents": {
    "orchestrator": {
      "cli": "claude",
      "model": "opus[1m]"
    }
  }
}
```

To use a third-party Claude-compatible provider, select `claude-thirdparty` in `settings.json`:

```json
{
  "agents": {
    "orchestrator": {
      "cli": "claude-thirdparty",
      "model": "opus[1m]"
    }
  }
}
```

These examples show only the `agents` section. Merge it into the existing file without replacing `hooks`. The model value is a VibeGame alias. Map that alias to the provider's actual model ID in `.env`, as shown below.

### `src/.vibegame/defaults.json`

This file selects the default language copied into new projects. The release default is English:

```json
{
  "language": "en",
  "setup_version": 1
}
```

### Agent Roles

- `orchestrator`: Clarifies the user's intent, owns the PRD, splits work into tasks, dispatches the team, reviews plans, and accepts completed work.
- `architect`: Researches the relevant code and specs, then writes the technical plan and verification plan for one task.
- `programmer`: Implements an approved technical plan and validates the code before handoff.
- `auditor`: Reviews code and spec alignment, runs static checks, and fixes safe local issues. It does not run the game.
- `player`: Runs the game, verifies behavior and visuals, and records runtime evidence. It must be vlm.
- `designer`: Clarifies game design and maintains the GDD. It does not write implementation code.
- `artist`: Generates and processes game art, then registers finished assets in the project manifest.
- `reviewer`: Runs the final end-to-end quality gate after all tasks for the current goal are complete.

### `.env`

Create `.env` in the repository root. Write only values provided or approved by the user, and never commit this file.

```sh
# === Image Generation (required) ===

IMAGE_PROVIDER=Openai
IMAGE_API_KEY=sk-xxxx
# Optional override for the selected image provider's endpoint:
IMAGE_BASE_URL=https://api.example.com/v1
IMAGE_MODEL=gpt-image-2

# To use a nano-banana model instead:
# IMAGE_PROVIDER=Google
# IMAGE_API_KEY=AIxxxx
# IMAGE_MODEL=nano-banana-2

# === VLM Provider (required, OpenAI-compatible) ===

# Base URL ends at /v1, not /chat/completions.
VLM_BASE_URL=https://api.example.com/v1
VLM_API_KEY=sk-xxxx
VLM_MODEL=provider-vlm-model-id

# === Third-Party Claude-Compatible Provider ===

THIRD_PARTY_BASE_URL=https://api.example.com
THIRD_PARTY_API_KEY=sk-xxxx
THIRD_PARTY_OPUS_MODEL=provider-opus-model-id
THIRD_PARTY_SONNET_MODEL=provider-sonnet-model-id
THIRD_PARTY_HAIKU_MODEL=provider-haiku-model-id

# === GLM (optional) ===

GLM_API_KEY=xxxx

# === Seedance 2.0 (optional) ===

# This feature is experimental, expensive, and unstable. Warn the user before enabling it.
VIDEO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks
VIDEO_API_KEY=xxxx

# === Qwen Image Layered (optional) ===

# This service is rarely needed because the default background-removal agent handles most assets.
# See docs/Qwen.md for deployment instructions.
QWEN_SERVER_URL=http://127.0.0.1:5001
```

The image generation settings form one active configuration. When the wizard
reconfigures image generation, it replaces all active `IMAGE_*` lines with the
selected provider, API key, model, and optional endpoint override. Selecting
the provider default removes `IMAGE_BASE_URL`. Skipping image generation setup
leaves the existing `IMAGE_*` configuration unchanged.
