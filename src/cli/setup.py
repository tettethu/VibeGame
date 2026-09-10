"""
VibeGame Setup Wizard - Interactive configuration for AI providers and project defaults.

Usage:
    python -m cli.setup --repo-root /path/to/repo
    vibegame setup

Guides user through language, agent providers, VLM, and image generation.
Writes to repo source files (.env, src/.vibegame/) as defaults for vibegame init.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import questionary


# === Data Models ===

@dataclass
class ProviderConfig:
    """One AI provider selected by the user."""
    id: str                     # "claude-default", "claude-api", "glm", "codex"
    display_name: str           # "Claude default", "Claude API", "Zhipu GLM (Claude Code)"
    cli_key: str                # models.json key: "claude", "glm", "claude-thirdparty", "codex"
    models: list[str]           # available models: ["sonnet", "opus", "haiku"]
    env_values: dict[str, str]  # keys to write to .env


@dataclass
class SetupConfig:
    language: str = "en"
    providers: list[ProviderConfig] = field(default_factory=list)
    agent_mappings: dict[str, dict[str, str]] = field(default_factory=dict)
    vlm_base_url: str = ""
    vlm_api_key: str = ""
    vlm_model: str = ""
    image_provider: str = ""
    image_api_key: str = ""
    image_model: str = ""
    image_base_url: str = ""


# === Provider Registry ===

PROVIDER_REGISTRY = {
    "claude-default": {
        "display_name": "Claude default",
        "description": "use your existing Claude Code setup, no config needed",
        "cli_key": "claude",
        "needs_config": False,
    },
    "claude-api": {
        "display_name": "Claude API",
        "description": "configure base URL, API key, model IDs - works with Anthropic or any OpenAI-compatible endpoint",
        "cli_key": "claude-thirdparty",
        "needs_config": True,
    },
    "glm": {
        "display_name": "Zhipu GLM (Claude Code)",
        "description": "GLM via Claude Code protocol",
        "cli_key": "glm",
        "needs_config": True,
    },
    "codex": {
        "display_name": "Codex / OpenAI",
        "description": "use system's existing OpenAI setup",
        "cli_key": "codex",
        "needs_config": False,
    },
}


def _read_models_config(repo_root: Path) -> dict:
    """Parse models.json, the single source of what each CLI accepts."""
    path = repo_root / "src" / ".vibegame" / "team" / "models.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {key: entry for key, entry in data.items() if isinstance(entry, dict)}


def _load_models_json(repo_root: Path) -> dict[str, list[str]]:
    """Load cli_key -> models list from models.json."""
    return {key: entry.get("models", []) for key, entry in _read_models_config(repo_root).items()}


def _load_efforts_json(repo_root: Path) -> dict[str, list[str]]:
    """Load cli_key -> thinking-effort levels from models.json."""
    return {key: entry.get("efforts", []) for key, entry in _read_models_config(repo_root).items()}

def _discover_image_providers(repo_root: Path) -> dict:
    """Discover image providers from src/artist/providers/."""
    import importlib

    providers_dir = repo_root / "src" / "artist" / "providers"
    if not providers_dir.is_dir():
        return {}

    result = {}
    for p in sorted(providers_dir.glob("*.py")):
        if p.name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"artist.providers.{p.stem}")
        except Exception:
            continue
        name = getattr(mod, "PROVIDER_NAME", p.stem)
        models = sorted(getattr(mod, "SUPPORTED_MODELS", set()))
        result[name] = {"models": models, "file": p.name}
    return result

LANGUAGE_OPTIONS = [
    questionary.Choice("English", value="en"),
    questionary.Choice("Chinese", value="zh-CN"),
    questionary.Choice("Japanese", value="ja"),
    questionary.Choice("Korean", value="ko"),
    questionary.Choice("Spanish", value="es"),
    questionary.Choice("French", value="fr"),
    questionary.Choice("German", value="de"),
    questionary.Choice("Portuguese", value="pt"),
    questionary.Choice("Russian", value="ru"),
    questionary.Choice("Arabic", value="ar"),
]

# Agent display names and suggested defaults
AGENT_ROLES = [
    "orchestrator",
    "architect", "programmer", "auditor", "player",
    "designer", "artist", "reviewer",
]

# Orchestrator only supports Claude Code CLI
ORCHESTRATOR_DEFAULTS = {"cli": "claude", "model": "opus"}

# Sentinel for "write no effort key", which leaves the CLI's own default in place.
EFFORT_UNSET = "__unset__"


# === File I/O ===

def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse .env file into dict."""
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in {"'", '"'}:
            val = val[1:-1]
        if key:
            values[key] = val
    return values


def _write_env(
    repo_root: Path,
    env_values: dict[str, str],
    remove_keys: set[str] | None = None,
) -> None:
    """Merge env values into .env, preserving user entries and comments."""
    env_path = repo_root / ".env"
    existing_lines: list[str] = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()

    to_remove = remove_keys or set()
    # Build set of keys we manage
    managed_keys = set(env_values.keys()) | to_remove
    written_keys: set[str] = set()

    # Update existing lines
    new_lines: list[str] = []
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        if "=" not in stripped:
            new_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in to_remove:
            continue  # drop removed keys
        if key in env_values:
            new_lines.append(f"{key}={env_values[key]}")
            written_keys.add(key)
        else:
            new_lines.append(line)

    # Append new keys not in existing file
    for key, val in env_values.items():
        if key not in written_keys:
            new_lines.append(f"{key}={val}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _write_image_env(
    repo_root: Path,
    provider: str,
    api_key: str,
    model: str,
    base_url: str,
) -> None:
    """Replace all active IMAGE_* lines with one complete configuration."""
    required = {
        "IMAGE_PROVIDER": provider,
        "IMAGE_API_KEY": api_key,
        "IMAGE_MODEL": model,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise ValueError(f"Image configuration requires: {', '.join(missing)}")

    env_path = repo_root / ".env"
    existing_lines = (
        env_path.read_text(encoding="utf-8").splitlines()
        if env_path.exists()
        else []
    )
    image_values = {
        "IMAGE_PROVIDER": provider,
        "IMAGE_API_KEY": api_key,
    }
    if base_url:
        image_values["IMAGE_BASE_URL"] = base_url
    image_values["IMAGE_MODEL"] = model

    new_lines: list[str] = []
    insert_at: int | None = None
    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key.startswith("IMAGE_"):
                if insert_at is None:
                    insert_at = len(new_lines)
                continue
        new_lines.append(line)

    image_lines = [f"{key}={value}" for key, value in image_values.items()]
    if insert_at is None:
        insert_at = len(new_lines)
    new_lines[insert_at:insert_at] = image_lines
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _load_defaults(repo_root: Path) -> dict:
    """Load src/.vibegame/defaults.json."""
    path = repo_root / "src" / ".vibegame" / "defaults.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_defaults(repo_root: Path, language: str) -> None:
    """Write src/.vibegame/defaults.json."""
    path = repo_root / "src" / ".vibegame" / "defaults.json"
    data = {
        "language": language,
        "setup_version": 1,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _load_source_settings(repo_root: Path) -> dict:
    """Load src/.vibegame/settings.json."""
    path = repo_root / "src" / ".vibegame" / "settings.json"
    if not path.exists():
        return {"agents": {}, "hooks": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"agents": {}, "hooks": {}}


def _write_source_settings(repo_root: Path, agent_mappings: dict) -> None:
    """Write src/.vibegame/settings.json with agent mappings."""
    path = repo_root / "src" / ".vibegame" / "settings.json"
    existing = _load_source_settings(repo_root)
    existing["agents"] = agent_mappings
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _install_codex_hooks() -> None:
    """Install global Codex hooks after setup."""
    from cli.codex_hooks import install_global_codex_hooks

    result = install_global_codex_hooks()
    action = "updated" if result.changed else "already up to date"
    print(f"Codex hooks: {action} ({result.path})")


def _install_codex_hooks_for_selected_providers(
    providers: list[ProviderConfig],
) -> None:
    """Install Codex hooks only when Codex was selected."""
    if any(provider.cli_key == "codex" for provider in providers):
        _install_codex_hooks()


class WizardCancelled(Exception):
    """User cancelled the wizard (Ctrl+C or selected nothing)."""


def _prompt_language(current: str = "en") -> str:
    """Step 1: Language selection."""
    result = questionary.select(
        "Select language:",
        choices=LANGUAGE_OPTIONS,
        default=current if current in ("zh-CN", "en") else "en",
    ).ask()
    if result is None:
        raise WizardCancelled
    return result


def _prompt_providers(current_env: dict[str, str], models_json: dict[str, list[str]]) -> list[ProviderConfig]:
    """Step 2: Select and configure AI providers."""
    choices = []
    for pid, info in PROVIDER_REGISTRY.items():
        label = f"{info['display_name']} ({info['description']})"
        choices.append(questionary.Choice(label, value=pid))

    selected = questionary.checkbox(
        "Select AI providers:",
        choices=choices,
    ).ask()
    if selected is None:
        raise WizardCancelled

    if not selected:
        print("No providers selected. Using Claude default.")
        selected = ["claude-default"]

    providers: list[ProviderConfig] = []
    for pid in selected:
        info = PROVIDER_REGISTRY[pid]
        models = list(models_json.get(info["cli_key"], []))

        if not info["needs_config"]:
            providers.append(ProviderConfig(
                id=pid,
                display_name=info["display_name"],
                cli_key=info["cli_key"],
                models=models,
                env_values={},
            ))
            continue

        # Per-provider configuration
        env: dict[str, str] = {}
        print(f"\n--- {info['display_name']} ---")

        if pid == "claude-api":
            base_url = questionary.text(
                "Base URL (press Enter for https://api.anthropic.com):",
                default=current_env.get("THIRD_PARTY_BASE_URL", "https://api.anthropic.com"),
            ).ask()
            if base_url is None:
                raise WizardCancelled
            base_url = base_url or "https://api.anthropic.com"
            existing_key = current_env.get("THIRD_PARTY_API_KEY", "")
            api_key = questionary.password(
                "API key (press Enter to keep current):",
                default=existing_key,
            ).ask()
            if api_key is None:
                raise WizardCancelled
            api_key = api_key if api_key else existing_key
            env["THIRD_PARTY_BASE_URL"] = base_url
            env["THIRD_PARTY_API_KEY"] = api_key

            # Optional model ID overrides (only written to .env if non-empty)
            print("Model ID overrides (leave empty to use provider defaults):")
            for tier in ("Opus", "Sonnet", "Haiku"):
                env_key = f"THIRD_PARTY_{tier.upper()}_MODEL"
                existing_mid = current_env.get(env_key, "")
                hint = f" (current: {existing_mid})" if existing_mid else ""
                mid = questionary.text(
                    f"Model ID for {tier}{hint}:",
                    default=existing_mid,
                ).ask()
                if mid is None:
                    raise WizardCancelled
                if mid.strip():
                    env[env_key] = mid.strip()
                # empty -> not written -> removed by remove_keys below if stale

            providers.append(ProviderConfig(
                id=pid,
                display_name=info["display_name"],
                cli_key="claude-thirdparty",
                models=list(models_json.get("claude-thirdparty", models)),
                env_values=env,
            ))

        elif pid == "glm":
            existing_key = current_env.get("GLM_API_KEY", "")
            api_key = questionary.password(
                "API key (press Enter to keep current):",
                default=existing_key,
            ).ask()
            if api_key is None:
                raise WizardCancelled
            env["GLM_API_KEY"] = api_key if api_key else existing_key

            providers.append(ProviderConfig(
                id=pid,
                display_name=info["display_name"],
                cli_key=info["cli_key"],
                models=models,
                env_values=env,
            ))

    return providers


def _build_model_choices(providers: list[ProviderConfig]) -> list[dict]:
    """Build flat list of (cli_key, model, display) from selected providers."""
    choices: list[dict] = []
    seen: set[str] = set()
    for p in providers:
        for model in p.models:
            key = f"{p.cli_key}-{model}"
            if key in seen:
                continue
            seen.add(key)
            display = f"{model} ({p.display_name})"
            choices.append({"cli": p.cli_key, "model": model, "display": display, "key": key})
    return choices


def _with_effort(
    mapping: dict[str, str],
    effort: str | None,
    efforts_json: dict[str, list[str]],
) -> dict[str, str]:
    """Attach an effort only when the resolved CLI offers that level."""
    if effort and effort in efforts_json.get(mapping["cli"], []):
        mapping["effort"] = effort
    return mapping


def _prompt_effort(
    role: str,
    cli: str,
    efforts_json: dict[str, list[str]],
    current: str | None,
) -> str | None:
    """Ask one agent's thinking effort. None means no key is written at all.

    Defaults to whatever settings.json already holds for this agent, so pressing
    Enter through the wizard reproduces the existing configuration unchanged.
    """
    levels = efforts_json.get(cli, [])
    if not levels:
        return None
    choices = [questionary.Choice("Not set (use the CLI default)", value=EFFORT_UNSET)]
    choices += [questionary.Choice(level, value=level) for level in levels]
    result = questionary.select(
        f"Effort [{role}]:",
        choices=choices,
        default=current if current in levels else EFFORT_UNSET,
    ).ask()
    if result is None:
        raise WizardCancelled
    return None if result == EFFORT_UNSET else result


def _prompt_orchestrator(
    providers: list[ProviderConfig],
    current_mappings: dict[str, dict[str, str]],
    efforts_json: dict[str, list[str]],
) -> dict[str, str]:
    """Prompt for orchestrator CLI/model/effort."""
    model_choices = _build_model_choices(providers)
    if not model_choices:
        return dict(ORCHESTRATOR_DEFAULTS)

    existing = current_mappings.get("orchestrator", ORCHESTRATOR_DEFAULTS)
    default_key = f"{existing['cli']}-{existing['model']}"

    choices = [questionary.Choice(mc["display"], value=mc["key"]) for mc in model_choices]
    result = questionary.select(
        "Orchestrator model:",
        choices=choices,
        default=default_key if default_key in [mc["key"] for mc in model_choices] else model_choices[0]["key"],
    ).ask()
    if result is None:
        raise WizardCancelled

    match = next((mc for mc in model_choices if mc["key"] == result), model_choices[0])
    mapping = {"cli": match["cli"], "model": match["model"]}
    effort = _prompt_effort("orchestrator", match["cli"], efforts_json, existing.get("effort"))
    return _with_effort(mapping, effort, efforts_json)


def _prompt_agent_mappings(
    providers: list[ProviderConfig],
    current_mappings: dict[str, dict[str, str]],
    efforts_json: dict[str, list[str]],
) -> dict[str, dict[str, str]]:
    """Step 4: Per-agent CLI/model/effort mapping."""
    mappings: dict[str, dict[str, str]] = {}

    # Orchestrator is always configured (it's always a Claude Code session)
    mappings["orchestrator"] = _prompt_orchestrator(providers, current_mappings, efforts_json)

    model_choices = _build_model_choices(providers)
    if not model_choices:
        return mappings

    default_model = model_choices[0]
    use_default_all = False
    mate_roles = [r for r in AGENT_ROLES if r != "orchestrator"]

    for role in mate_roles:
        existing = current_mappings.get(role, {})
        if use_default_all:
            # Effort was never asked for this role, so keep what it already had.
            mappings[role] = _with_effort(
                {"cli": default_model["cli"], "model": default_model["model"]},
                existing.get("effort"),
                efforts_json,
            )
            continue

        default_key = f"{existing.get('cli', default_model['cli'])}-{existing.get('model', default_model['model'])}"

        choices = []
        for mc in model_choices:
            choices.append(questionary.Choice(mc["display"], value=mc["key"]))
        choices.append(questionary.Choice(f"Use default ({default_model['display']})", value="use-default"))
        choices.append(questionary.Choice("Use default for all remaining agents", value="use-default-all"))

        result = questionary.select(
            f"Agent [{role}]:",
            choices=choices,
            default=default_key if default_key in [c.value for c in choices[:-2]] else model_choices[0]["key"],
        ).ask()
        if result is None:
            raise WizardCancelled

        if result == "use-default-all":
            match = default_model
            use_default_all = True
        elif result == "use-default":
            match = default_model
        else:
            match = next((mc for mc in model_choices if mc["key"] == result), default_model)

        mapping = {"cli": match["cli"], "model": match["model"]}
        if use_default_all:
            # This answer also covers the remaining roles, so skip the question.
            mappings[role] = _with_effort(mapping, existing.get("effort"), efforts_json)
            continue
        effort = _prompt_effort(role, match["cli"], efforts_json, existing.get("effort"))
        mappings[role] = _with_effort(mapping, effort, efforts_json)

    return mappings


def _prompt_vlm(current_env: dict[str, str]) -> tuple[str, str, str]:
    """Configure the VLM used by visual verification and asset tools."""
    configured = all(
        current_env.get(key)
        for key in ("VLM_BASE_URL", "VLM_API_KEY", "VLM_MODEL")
    )
    want = questionary.confirm(
        "Configure VLM?",
        default=configured,
    ).ask()
    if want is None or not want:
        return "", "", ""

    base_url = questionary.text(
        "OpenAI-compatible VLM base URL (end at /v1, not /chat/completions):",
        default=current_env.get("VLM_BASE_URL", ""),
    ).ask()
    if base_url is None:
        raise WizardCancelled

    existing_key = current_env.get("VLM_API_KEY", "")
    api_key = questionary.password(
        "VLM API key (press Enter to keep current):",
        default=existing_key,
    ).ask()
    if api_key is None:
        raise WizardCancelled

    model = questionary.text(
        "VLM model:",
        default=current_env.get("VLM_MODEL", ""),
    ).ask()
    if model is None:
        raise WizardCancelled

    values = {
        "VLM_BASE_URL": base_url.strip(),
        "VLM_API_KEY": api_key or existing_key,
        "VLM_MODEL": model.strip(),
    }
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise ValueError(f"VLM configuration requires: {', '.join(missing)}")

    return (
        values["VLM_BASE_URL"],
        values["VLM_API_KEY"],
        values["VLM_MODEL"],
    )


def _same_provider(current: str, selected: str) -> bool:
    return current.strip().lower() == selected.strip().lower()


def _prompt_image_base_url(
    current_env: dict[str, str],
    *,
    same_provider: bool,
) -> str:
    current_base_url = (
        current_env.get("IMAGE_BASE_URL", "")
        if same_provider
        else ""
    )
    mode = questionary.select(
        "Image endpoint:",
        choices=[
            questionary.Choice("Use provider default", value="default"),
            questionary.Choice("Use custom endpoint", value="custom"),
        ],
        default="custom" if current_base_url else "default",
    ).ask()
    if mode is None:
        raise WizardCancelled
    if mode == "default":
        return ""

    base_url = questionary.text(
        "Image base URL:",
        default=current_base_url,
    ).ask()
    if base_url is None:
        raise WizardCancelled
    base_url = base_url.strip()
    if not base_url:
        raise ValueError("Custom image endpoint requires IMAGE_BASE_URL")
    return base_url


def _prompt_image(
    current_env: dict[str, str],
    discovered: dict,
) -> tuple[str, str, str, str]:
    """Configure an optional image generation provider."""
    current_provider = current_env.get("IMAGE_PROVIDER", "")
    want = questionary.confirm(
        "Configure image generation?",
        default=bool(current_provider),
    ).ask()
    if want is None or not want:
        return "", "", "", ""

    choices = []
    for name, info in discovered.items():
        label = name
        if info["models"]:
            label += f"  ({', '.join(info['models'])})"
        choices.append(questionary.Choice(label, value=name))
    choices.append(questionary.Choice("Other Providers", value="__other__"))
    choices.append(questionary.Choice("Skip", value="skip"))

    discovered_current = next(
        (
            name
            for name in discovered
            if _same_provider(current_provider, name)
        ),
        None,
    )
    provider = questionary.select(
        "Select image provider:",
        choices=choices,
        default=discovered_current or ("__other__" if current_provider else None),
    ).ask()
    if provider is None or provider == "skip":
        return "", "", "", ""

    if provider == "__other__":
        provider = questionary.text(
            "Provider name:",
            default=current_provider if not discovered_current else "",
        ).ask()
        if provider is None or not provider.strip():
            return "", "", "", ""
        provider = provider.strip()
        same_provider = _same_provider(current_provider, provider)
        base_url = _prompt_image_base_url(
            current_env,
            same_provider=same_provider,
        )
        existing_key = current_env.get("IMAGE_API_KEY", "") if same_provider else ""
        api_key = questionary.password(
            "Image API key (press Enter to keep current):",
            default=existing_key,
        ).ask()
        if api_key is None:
            raise WizardCancelled
        api_key = api_key or existing_key
        model = questionary.text(
            "Model name:",
            default=current_env.get("IMAGE_MODEL", "") if same_provider else "",
        ).ask()
        if model is None:
            raise WizardCancelled
        return provider, api_key, model.strip(), base_url

    # Discovered provider
    same_provider = _same_provider(current_provider, provider)
    info = discovered[provider]
    base_url = _prompt_image_base_url(
        current_env,
        same_provider=same_provider,
    )
    existing_image_key = current_env.get("IMAGE_API_KEY", "") if same_provider else ""
    api_key = questionary.password(
        "Image API key (press Enter to keep current):",
        default=existing_image_key,
    ).ask()
    if api_key is None:
        raise WizardCancelled
    api_key = api_key if api_key else existing_image_key

    models = info["models"]
    if models:
        model_choices = [questionary.Choice(m, value=m) for m in models]
        current_model = (
            current_env.get("IMAGE_MODEL", models[0])
            if same_provider
            else models[0]
        )
        if current_model not in models:
            current_model = models[0]
        model = questionary.select(
            "Image model:",
            choices=model_choices,
            default=current_model,
        ).ask()
        if model is None:
            raise WizardCancelled
    else:
        model = questionary.text(
            "Model name:",
            default=current_env.get("IMAGE_MODEL", "") if same_provider else "",
        ).ask()
        if model is None:
            raise WizardCancelled
        model = model.strip()

    return provider, api_key or "", model, base_url


# === Summary ===

def _print_summary(config: SetupConfig) -> None:
    """Print configuration summary."""
    print("=== Configuration Summary ===")
    print(f"  Language:       {config.language}")

    if config.providers:
        provider_str = ", ".join(p.display_name for p in config.providers)
        print(f"  AI providers:   {provider_str}")
    else:
        print(f"  AI providers:   (none)")

    if config.agent_mappings:
        mappings_str = ", ".join(
            f"{role}: {m['cli']}/{m['model']}" + (f"/{m['effort']}" if m.get("effort") else "")
            for role, m in config.agent_mappings.items()
        )
        print(f"  Agent mapping:  {mappings_str}")
    else:
        print(f"  Agent mapping:  (default)")

    if config.vlm_model:
        print(f"  VLM:            {config.vlm_base_url} / {config.vlm_model}")
    else:
        print("  VLM:            (not configured)")

    if config.image_provider:
        print(f"  Image provider: {config.image_provider} / {config.image_model}")
        endpoint = config.image_base_url or "(provider default)"
        print(f"  Image endpoint: {endpoint}")
    else:
        print("  Image provider: (unchanged)")


# === Main Wizard ===

def run_wizard(repo_root: Path) -> None:
    """Run the interactive setup wizard."""

    # Welcome
    print("=== VibeGame Setup Wizard ===")
    print("This will configure agent providers, VLM, image generation, and defaults.")
    print("Configuration is saved to repo source files and used by vibegame init.")
    print("Press Ctrl+C at any time to cancel.")

    try:
        _run_wizard_steps(repo_root)
    except (KeyboardInterrupt, WizardCancelled):
        print("\nSetup cancelled.")
        sys.exit(1)


def _run_wizard_steps(repo_root: Path) -> None:
    """Inner wizard steps, cancellable via KeyboardInterrupt."""
    # Load current state
    current_env = _parse_env_file(repo_root / ".env")
    current_defaults = _load_defaults(repo_root)
    current_settings = _load_source_settings(repo_root)
    current_mappings = current_settings.get("agents", {})

    # Step 1: Language
    language = _prompt_language(current_defaults.get("language", "en"))

    # Step 2: AI Providers
    models_json = _load_models_json(repo_root)
    providers = _prompt_providers(current_env, models_json)

    # Step 3: Agent mapping
    agent_mappings = _prompt_agent_mappings(
        providers, current_mappings, _load_efforts_json(repo_root),
    )

    # Step 4: VLM
    vlm_base_url, vlm_api_key, vlm_model = _prompt_vlm(current_env)

    # Step 5: Image generation
    discovered_providers = _discover_image_providers(repo_root)
    (
        image_provider,
        image_api_key,
        image_model,
        image_base_url,
    ) = _prompt_image(current_env, discovered_providers)

    # Build config
    config = SetupConfig(
        language=language,
        providers=providers,
        agent_mappings=agent_mappings,
        vlm_base_url=vlm_base_url,
        vlm_api_key=vlm_api_key,
        vlm_model=vlm_model,
        image_provider=image_provider,
        image_api_key=image_api_key,
        image_model=image_model,
        image_base_url=image_base_url,
    )

    # Summary
    _print_summary(config)

    # Confirm
    confirmed = questionary.confirm("Write configuration?", default=True).ask()
    if not confirmed:
        print("Setup cancelled.")
        return

    # Write files
    _write_defaults(repo_root, language)

    env_values: dict[str, str] = {}
    for p in providers:
        env_values.update(p.env_values)
    if vlm_model:
        env_values["VLM_BASE_URL"] = vlm_base_url
        env_values["VLM_API_KEY"] = vlm_api_key
        env_values["VLM_MODEL"] = vlm_model
    # Clean up stale keys
    remove_keys: set[str] = set()
    for tier in ("OPUS", "SONNET", "HAIKU"):
        key = f"THIRD_PARTY_{tier}_MODEL"
        if key not in env_values and key in current_env:
            remove_keys.add(key)

    if env_values or remove_keys:
        _write_env(repo_root, env_values, remove_keys)
    if image_provider:
        _write_image_env(
            repo_root,
            image_provider,
            image_api_key,
            image_model,
            image_base_url,
        )

    if agent_mappings:
        _write_source_settings(repo_root, agent_mappings)

    # Hint for custom provider implementation
    if image_provider and image_provider not in discovered_providers:
        file_name = image_provider.lower().replace(" ", "_").replace("-", "_")
        print(f"\n  Please implement src/artist/providers/{file_name}.py")
        print(f"  See docs/IMAGEGEN.md for the provider extension API.\n")

    print("=== Setup complete! ===")
    print("Configuration saved to:")
    print("  .env")
    print("  src/.vibegame/defaults.json")
    print("  src/.vibegame/settings.json")
    _install_codex_hooks_for_selected_providers(providers)
    print("Next: mkdir my-game && cd my-game && vibegame init")


# === CLI Entry Point ===

def main() -> None:
    """CLI entry point for python -m cli.setup."""
    import argparse

    parser = argparse.ArgumentParser(description="VibeGame Setup Wizard")
    parser.add_argument("--repo-root", type=str, help="Repo root directory")
    args = parser.parse_args()

    if args.repo_root:
        repo_root = Path(args.repo_root).resolve()
    else:
        # Walk up from CWD to find repo root
        repo_root = Path.cwd()
        while not (repo_root / "pyproject.toml").exists():
            parent = repo_root.parent
            if parent == repo_root:
                print("Cannot find repo root (no pyproject.toml found)")
                sys.exit(1)
            repo_root = parent

    run_wizard(repo_root)


if __name__ == "__main__":
    main()
