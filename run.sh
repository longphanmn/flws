#!/usr/bin/env bash
# Flatland launcher.
#   ./run.sh                  backend (:8000) + web UI (:5173) — full stack (auto-clones flws-web if missing)
#   ./run.sh docker           full stack via Docker Compose (auto-clones flws-web if missing)
#   ./run.sh backend          backend (:8000) only
#   ./run.sh tui [ws-url] [god-passkey]
#                             terminal TUI ONLY — attaches to an already-running
#                             world, never starts any server
#                             (default url ws://localhost:8000/ws, env FLATWORLD_WS)
#                             The passkey (3rd arg or FLATWORLD_GOD_KEY) is sent
#                             with every control/laws call — no prompt, ever.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$HOME/.local/bin:$PATH"

MODE="${1:-}"

port_busy() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

# ---------------------------------------------------------------- tui: pure frontend
# The TUI is a plain client of the /ws + REST API. It must never spawn a
# backend — it attaches to one that is already running, local or remote.
if [ "$MODE" = "tui" ]; then
  WS_URL="${2:-${FLATWORLD_WS:-ws://localhost:8000/ws}}"
  export FLATWORLD_WS="$WS_URL"
  # God passkey: 3rd arg wins, else the env var. The server rejects control
  # calls without it — there is no auth bypass, just no interactive prompt.
  if [ -n "${3:-}" ]; then export FLATWORLD_GOD_KEY="$3"; fi
  HTTP_BASE="$(printf '%s' "$WS_URL" | sed -E 's~^wss://~https://~; s~^ws://~http://~; s~(/api)?/ws$~~')"

  command -v uv >/dev/null || { echo "Error: uv not found (brew install uv)." >&2; exit 1; }
  cd "$ROOT/backend"
  [ -d .venv ] || uv sync --quiet

  echo "[tui] attaching to $WS_URL (no server will be started)"
  if command -v curl >/dev/null 2>&1 && curl -sf --max-time 3 "$HTTP_BASE/healthz" >/dev/null 2>&1; then
    echo "[tui] world is live"
  else
    echo "[tui] note: nothing answering at $HTTP_BASE yet — start it with ./run.sh," >&2
    echo "      or point at another host: ./run.sh tui ws://host:8000/ws" >&2
    echo "      (the TUI keeps retrying in the meantime)" >&2
  fi
  echo "[tui] keys: space pause · s step · r reset · f fit · a ascii/blocks · +/- zoom · hjkl pan · enter inspect · g laws · ? help · q quit"
  echo "[tui] auth: pass FLATWORLD_GOD_KEY (or 3rd arg) to control the world; without it, viewing works"
  exec uv run -m tui
fi

# Load .env if present
if [ -f "$ROOT/.env" ]; then
  set -a
  source "$ROOT/.env"
  set +a
elif [ -f "$ROOT/backend/.env" ]; then
  set -a
  source "$ROOT/backend/.env"
  set +a
fi

LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost')"
if [ -n "$LAN_IP" ] && [ "$LAN_IP" != "localhost" ]; then
  LAN_ORIGIN="http://${LAN_IP}:5173"
  case ",${FLATWORLD_ALLOWED_ORIGINS:-}," in
    *",${LAN_ORIGIN},"*) ;;
    *) export FLATWORLD_ALLOWED_ORIGINS="${FLATWORLD_ALLOWED_ORIGINS:+${FLATWORLD_ALLOWED_ORIGINS},}${LAN_ORIGIN}" ;;
  esac
fi

# ------------------------------------------------------------ clone & setup flws-web
setup_frontend() {
  FE_DIR="${FRONTEND_DIR:-}"
  if [ -z "$FE_DIR" ]; then
    if [ -d "$ROOT/../flws-web" ]; then
      FE_DIR="$(cd "$ROOT/../flws-web" && pwd)"
    elif [ -d "$ROOT/frontend" ]; then
      FE_DIR="$ROOT/frontend"
    else
      # Default: sibling ../flws-web if parent is writable, otherwise ./frontend
      if [ -w "$ROOT/.." ]; then
        FE_DIR="$(cd "$ROOT/.." && pwd)/flws-web"
      else
        FE_DIR="$ROOT/frontend"
      fi
    fi
  fi

  if [ ! -d "$FE_DIR" ]; then
    echo "[frontend] flws-web not found at $FE_DIR. Cloning from GitHub..."
    REPO_URL="${FLWS_WEB_REPO:-https://github.com/longphanmn/flws-web.git}"
    if git clone "$REPO_URL" "$FE_DIR" 2>/dev/null || git clone git@github.com:longphanmn/flws-web.git "$FE_DIR"; then
      echo "[frontend] Successfully cloned flws-web into $FE_DIR"
    else
      echo "[frontend] Warning: Failed to clone flws-web from $REPO_URL" >&2
      return 1
    fi
  fi

  if [ -d "$FE_DIR" ]; then
    # Setup .env in frontend if not present
    if [ ! -f "$FE_DIR/.env" ] && [ -f "$FE_DIR/.env.example" ]; then
      echo "[frontend] Initializing $FE_DIR/.env from .env.example"
      cp "$FE_DIR/.env.example" "$FE_DIR/.env"
    fi
    # Install dependencies if node_modules missing and npm is available
    if command -v npm >/dev/null 2>&1 && [ ! -d "$FE_DIR/node_modules" ]; then
      echo "[frontend] Installing dependencies (npm install)..."
      (cd "$FE_DIR" && npm install --silent)
    fi
  fi
  export FRONTEND_DIR="$FE_DIR"
  return 0
}

# ------------------------------------------------------------ docker compose mode
if [ "$MODE" = "docker" ] || [ "$MODE" = "compose" ] || [ "$MODE" = "--docker" ]; then
  setup_frontend || true
  command -v docker >/dev/null || { echo "Error: docker not found." >&2; exit 1; }
  shift || true
  echo "[docker] Launching Flatland stack via Docker Compose..."
  FRONTEND_DIR="${FRONTEND_DIR:-../flws-web}" exec docker compose up --build "$@"
fi

# ------------------------------------------------------------ backend-only mode
if [ "$MODE" = "backend" ] || [ "$MODE" = "--backend" ]; then
  echo "[backend] installing deps + starting on :8000 (0.0.0.0)"
  cd "$ROOT/backend"
  [ -d .venv ] || uv sync --quiet
  # Finding #17: remove --reload to eliminate file watcher attack surface
  # 0.0.0.0 binding kept for container/LAN accessibility (Docker compatible)
  exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 \
    --ws-per-message-deflate false
fi

setup_frontend || true
PORTS_TO_CHECK=(8000)
if [ -n "$FE_DIR" ] && [ -d "$FE_DIR" ]; then
  PORTS_TO_CHECK+=(5173)
fi
for port in "${PORTS_TO_CHECK[@]}"; do
  if port_busy "$port"; then
    echo "Error: port $port is already in use." >&2
    exit 1
  fi
done

command -v uv >/dev/null || { echo "Error: uv not found (brew install uv)." >&2; exit 1; }

PIDS=()
cleanup() {
  echo ""
  echo "Shutting down..."
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

echo "[backend] installing deps + starting on :8000 (0.0.0.0)"
cd "$ROOT/backend"
[ -d .venv ] || uv sync --quiet
# Finding #17: remove --reload to eliminate file watcher attack surface
# §AX P0: permessage-deflate disabled on LAN — synchronous zlib cost 33% CPU
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  --ws-per-message-deflate false &
PIDS+=("$!")

if [ -n "$FE_DIR" ] && [ -d "$FE_DIR" ] && command -v npm >/dev/null 2>&1; then
  echo "[frontend] installing deps + starting on :5173 (0.0.0.0) from $FE_DIR"
  cd "$FE_DIR"
  [ -d node_modules ] || npm install --silent
  npm run dev -- --host 0.0.0.0 --port 5173 &
  PIDS+=("$!")
else
  echo "[frontend] Note: frontend directory ($FE_DIR) or npm not found; running backend only."
fi

echo ""
echo "  World UI : http://localhost:5173  (or http://${LAN_IP}:5173 on LAN)"
echo "  API docs : http://localhost:8000/docs"
echo "  Terminal : ./run.sh tui   (attach a TUI to this world)"
echo ""
wait
