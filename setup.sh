#!/bin/sh
set -eu

# Portable script dir (works in dash, bash, zsh, sh)
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { printf "${CYAN}=>${NC} %s\n" "$*"; }
ok()    { printf "${GREEN}OK${NC} %s\n" "$*"; }
fail()  { printf "${RED}ERROR:${NC} %s\n" "$*" >&2; exit 1; }
require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "$2"
}

MODE="human"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --mode)
      [ "$#" -ge 2 ] || fail "--mode requires human or agent"
      MODE="$2"
      shift 2
      ;;
    *)
      fail "Unknown argument: $1"
      ;;
  esac
done

case "$MODE" in
  human|agent) ;;
  *) fail "Unsupported mode: $MODE (expected human or agent)" ;;
esac

require_command uv "uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/"
require_command tmux "tmux is required. Install it with your system package manager."

UV_TOOL_BIN="$(uv tool dir --bin)"
case ":$PATH:" in
  *":$UV_TOOL_BIN:"*) ;;
  *) export PATH="$UV_TOOL_BIN:$PATH" ;;
esac

# --- Install vibegame ---
info "Installing vibegame CLI..."
uv tool install --editable "$ROOT_DIR" --constraints "$ROOT_DIR/requirements.txt" --force
ok "vibegame installed"

if [ "$MODE" = "human" ]; then
  info "Launching setup wizard..."
  vibegame setup "$ROOT_DIR"
else
  info "Agent mode: skipping the interactive setup wizard."
fi

# --- Install Playwright ---
info "Installing Playwright Chromium..."
VIBEGAME_BIN="$(command -v vibegame)"
VIBEGAME_PYTHON="$(sed -n '1s/^#!//p' "$VIBEGAME_BIN")"
[ -n "$VIBEGAME_PYTHON" ] && [ -x "$VIBEGAME_PYTHON" ] || fail "Cannot locate the vibegame tool environment Python"
"$VIBEGAME_PYTHON" -m playwright install chromium

echo ""
if [ "$MODE" = "agent" ]; then
  ok "Installation complete. Configure providers before running vibegame init."
else
  ok "All done! Run: mkdir my-game && cd my-game && vibegame init"
fi
