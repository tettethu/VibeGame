"""Launch helpers for team runtimes."""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
import tempfile
from pathlib import Path

import subprocess

from .context_config import INJECT_CONFIG
from .paths import workspace_root


def _get_git_root_env_path() -> Path | None:
    """Get .env path under git root directory."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()) / ".env"


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


def load_cli_configs() -> dict:
    config_path = Path(__file__).resolve().with_name("models.json")
    data = json.loads(config_path.read_text(encoding="utf-8"))
    for cli_cfg in data.values():
        flags = cli_cfg.get("flags", {})
        for key, val in flags.items():
            if isinstance(val, list):
                flags[key] = tuple(val)
    return data


CLI_CONFIGS = load_cli_configs()


def runtime_env_values(team_dir: str) -> dict[str, str]:
    """Read unified .env file (git root).

    Priority: system env vars > .env file
    """
    env_path = _get_git_root_env_path()
    if env_path is None or not env_path.exists():
        return {}
    return _parse_env_file(env_path)


def resolve_env_value(value: str, model: str, runtime_env: dict[str, str] | None = None) -> str:
    env_map = runtime_env or {}

    def replacer(match: re.Match[str]) -> str:
        var = match.group(1)
        if var == "model":
            return model
        return os.environ.get(var, env_map.get(var, ""))

    return re.sub(r"\$\{(\w+)\}", replacer, value)


def build_launch_command(cli: str, params: dict) -> str:
    config = CLI_CONFIGS[cli]
    parts = [config["command"]]
    model_cli_value = config.get("model_cli_value")
    for key, value in params.items():
        flag = config["flags"].get(key)
        if flag is None:
            continue
        if isinstance(flag, tuple):
            if value is not None and value is not False:
                actual = model_cli_value if (key == "model" and model_cli_value) else str(value)
                parts.extend([flag[0], shlex.quote(actual)])
        elif value:
            parts.append(flag)
    return " ".join(parts)


def build_initial_prompt_command(command: str, prompt: str, config: dict) -> str:
    if not prompt:
        return command
    if config.get("initial_prompt_mode") == "argument":
        return f"{command} {shlex.quote(prompt)}"
    return command


def _strip_yaml_frontmatter(content: str) -> str:
    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return content
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "".join(lines[index + 1:]).lstrip()
    return content


def ensure_codex_role_doc(team_root: str, role: str) -> Path:
    root = Path(team_root)
    roles_dir = root / ".codex" / "roles"
    roles_dir.mkdir(parents=True, exist_ok=True)
    role_doc = roles_dir / f"{role}.md"

    source_path = root / ".claude" / "agents" / f"{role}.md"
    if role == "orchestrator":
        source_path = root / ".vibegame" / "orchestrator.md"
    if not source_path.is_file():
        raise ValueError(f"Missing Codex role source for '{role}': {source_path}")

    content = _strip_yaml_frontmatter(source_path.read_text(encoding="utf-8"))
    if not role_doc.exists() or role_doc.read_text(encoding="utf-8") != content:
        role_doc.write_text(content, encoding="utf-8")
    return role_doc


def append_codex_model_instructions(command: str, role_doc: Path) -> str:
    override = f'model_instructions_file="{role_doc}"'
    return f"{command} -c {shlex.quote(override)}"


def prepare_launch(
    cli: str,
    model: str | None,
    agent: str | None,
    name: str | None = None,
    team_root: str | None = None,
) -> tuple[str, dict, str]:
    config = CLI_CONFIGS[cli]
    resolved_model = model or config.get("default_model")
    if config.get("models") and resolved_model not in config["models"]:
        print(
            f"Warning: Model '{resolved_model}' may not be supported for {cli} and may cause errors",
            file=sys.stderr,
        )
    params = {**config.get("default_params", {}), "model": resolved_model}
    if name and cli != "codex":
        params["name"] = name
    # Orchestrator uses orchestrator.md as its system prompt, not a CLI agent.
    if cli != "codex" and agent and agent != "orchestrator":
        params["agent"] = agent
    command = build_launch_command(cli, params)
    if cli == "codex" and agent:
        if not team_root:
            raise ValueError("team_root is required for codex role injection")
        command = append_codex_model_instructions(command, ensure_codex_role_doc(team_root, agent))
    return command, config, resolved_model


def launch_env_parts(team_dir: str, name: str, workdir: str, config: dict, model: str) -> list[str]:
    runtime_env = runtime_env_values(team_dir)
    env_parts = [
        "VIBEGAME_ROLE=mate",
        f"VIBEGAME_TEAM_DIR={shlex.quote(team_dir)}",
        f"VIBEGAME_MATE_NAME={shlex.quote(name)}",
        f"VIBEGAME_MATE_WORKDIR={shlex.quote(workdir)}",
    ]
    cli_env = config.get("env", {})
    for key, value in cli_env.items():
        resolved = resolve_env_value(value, model, runtime_env)
        if resolved:
            env_parts.append(f"{key}={shlex.quote(resolved)}")
    return env_parts


def build_launch_script_command(workdir: str, env_parts: list[str], launch_cmd: str, name: str) -> str:
    fd, script_path = tempfile.mkstemp(prefix=f"vibegame-launch-{name}-", suffix=".sh")
    os.close(fd)
    path = Path(script_path)
    cleanup_python = shlex.quote(sys.executable)
    pid_dir = Path(workdir) / ".vibegame" / "team" / "pids"
    pid_file = pid_dir / f"{name}.pid"
    lines = [
        "#!/bin/sh",
        "set -e",
        "(",
        "  sleep 5",
        f"  {cleanup_python} - \"$0\" <<'PY'",
        "from pathlib import Path",
        "import sys",
        "Path(sys.argv[1]).unlink(missing_ok=True)",
        "PY",
        ") >/dev/null 2>&1 &",
    ]
    for part in env_parts:
        lines.append(f"export {part}")
    lines.extend([
        f"cd {shlex.quote(workdir)}",
        f"mkdir -p {shlex.quote(str(pid_dir))}",
        f"echo $$ > {shlex.quote(str(pid_file))}",
        f"exec {launch_cmd}",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")
    path.chmod(0o700)
    quoted_path = shlex.quote(str(path))
    return f"exec /bin/sh {quoted_path}"
