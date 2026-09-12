#!/usr/bin/env bash
# ==============================================================================
# Flatland — One-Command Quickstart & Setup Script
#
# One-line installation & launch:
#   curl -fsSL https://raw.githubusercontent.com/longphanmn/flws/main/setup.sh | bash
#
# Advanced options:
#   curl -fsSL ... | bash -s -- [options]
#     --setup-only, --no-start  : Clone & install dependencies without launching
#     --docker, --compose       : Launch full stack via Docker Compose
#     --backend-only            : Launch backend simulation engine only (:8000)
#     -h, --help                : Display usage instructions
# ==============================================================================
set -euo pipefail

# Ensure standard local bin paths are included in PATH
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

BOLD='\033[1m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}"
cat << 'BANNER'
  ______ _       _   _                 _ 
 |  ____| |     | | | |               | |
 | |__  | | __ _| |_| | __ _ _ __   __| |
 |  __| | |/ _` | __| |/ _` | '_ \ / _` |
 | |    | | (_| | |_| | (_| | | | | (_| |
 |_|    |_|\__,_|\__|_|\__,_|_| |_|\__,_|
BANNER
echo -e "${BOLD}Autonomous 2D Artificial Life & Ecosystem Simulation${NC}"
echo -e "Developed from Edwin A. Abbott's 1884 classic Flatland\n"

START_SERVER=1
DOCKER_MODE=0
BACKEND_ONLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --setup-only|--no-start)
      START_SERVER=0
      shift
      ;;
    --docker|--compose)
      DOCKER_MODE=1
      shift
      ;;
    --backend-only)
      BACKEND_ONLY=1
      shift
      ;;
    -h|--help)
      echo "Flatland Setup & Quickstart Script"
      echo ""
      echo "Usage:"
      echo "  ./setup.sh [options]"
      echo ""
      echo "Options:"
      echo "  --setup-only, --no-start  Clone repositories and install dependencies without launching"
      echo "  --docker, --compose       Launch full stack via Docker Compose"
      echo "  --backend-only            Launch backend engine only (:8000)"
      echo "  -h, --help                Show this help message"
      exit 0
      ;;
    *)
      echo -e "${YELLOW}Warning: Unknown option '$1'${NC}"
      shift
      ;;
  esac
done

CURRENT_DIR="$(pwd)"

# ------------------------------------------------------------ 1. Path Resolution & Clones
echo -e "[setup] Locating Flatland components..."
if [ -f "$CURRENT_DIR/backend/app/main.py" ]; then
  # Script executed from inside flws repository
  BACKEND_DIR="$CURRENT_DIR"
  FRONTEND_DIR="${FRONTEND_DIR:-$(cd "$CURRENT_DIR/.." 2>/dev/null && pwd)/flws-web}"
elif [ -f "$CURRENT_DIR/flws/backend/app/main.py" ]; then
  # Script executed from workspace root containing ./flws
  BACKEND_DIR="$CURRENT_DIR/flws"
  FRONTEND_DIR="${FRONTEND_DIR:-$CURRENT_DIR/flws-web}"
else
  # Fresh directory: clone backend into ./flws
  if ! command -v git >/dev/null 2>&1; then
    echo -e "${RED}Error: git is required to clone Flatland repositories. Please install git and re-run.${NC}" >&2
    exit 1
  fi
  echo -e "[setup] ${GREEN}Cloning backend engine (flws)...${NC}"
  git clone https://github.com/longphanmn/flws.git ./flws
  BACKEND_DIR="$CURRENT_DIR/flws"
  FRONTEND_DIR="${FRONTEND_DIR:-$CURRENT_DIR/flws-web}"
fi

# Clone frontend if missing
if [ ! -d "$FRONTEND_DIR" ]; then
  if command -v git >/dev/null 2>&1; then
    echo -e "[setup] ${GREEN}Cloning frontend web client (flws-web)...${NC}"
    if ! git clone https://github.com/longphanmn/flws-web.git "$FRONTEND_DIR"; then
      echo -e "${YELLOW}Warning: Failed to clone flws-web from GitHub. Falling back to backend-only mode.${NC}"
      FRONTEND_DIR=""
    fi
  else
    echo -e "${YELLOW}Warning: git not found, skipping frontend clone.${NC}"
    FRONTEND_DIR=""
  fi
fi

# ------------------------------------------------------------ 2. Initialize .env Files
if [ -d "$BACKEND_DIR" ]; then
  if [ ! -f "$BACKEND_DIR/.env" ] && [ -f "$BACKEND_DIR/.env.example" ]; then
    echo -e "[setup] Initializing backend .env from .env.example..."
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  fi
fi

if [ -n "$FRONTEND_DIR" ] && [ -d "$FRONTEND_DIR" ]; then
  if [ ! -f "$FRONTEND_DIR/.env" ] && [ -f "$FRONTEND_DIR/.env.example" ]; then
    echo -e "[setup] Initializing frontend .env from .env.example..."
    cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env"
  fi
fi

# ------------------------------------------------------------ 3. Prerequisites & Dependencies
if [ "$DOCKER_MODE" = "1" ]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo -e "${RED}Error: docker is required for --docker mode but was not found in PATH.${NC}" >&2
    exit 1
  fi
else
  # A. Check and install uv (Fast Python Package Manager)
  if ! command -v uv >/dev/null 2>&1; then
    echo -e "[setup] ${YELLOW}uv not found. Installing uv (fast Python manager)...${NC}"
    if command -v curl >/dev/null 2>&1; then
      curl -LsSf https://astral.sh/uv/install.sh | sh
      export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    elif command -v wget >/dev/null 2>&1; then
      wget -qO- https://astral.sh/uv/install.sh | sh
      export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    fi
  fi

  if ! command -v uv >/dev/null 2>&1; then
    echo -e "${RED}Error: uv could not be installed automatically.${NC}" >&2
    echo "Please install uv manually: https://docs.astral.sh/uv/" >&2
    exit 1
  fi

  # B. Install Python backend dependencies
  echo -e "[setup] ${GREEN}Installing backend dependencies via uv...${NC}"
  (
    cd "$BACKEND_DIR/backend"
    uv sync --quiet
    if command -v gcc >/dev/null 2>&1; then
      echo -e "[setup] Compiling native C simulation core..."
      gcc -O3 -shared -fPIC -fopenmp -march=native -ffast-math app/flatland_core.c -o app/_flatland_core.so -lm 2>/dev/null || \
      gcc -O3 -shared -fPIC -ffast-math app/flatland_core.c -o app/_flatland_core.so -lm 2>/dev/null || true
    fi
  )

  # C. Install Frontend Node dependencies
  if [ "$BACKEND_ONLY" = "0" ] && [ -n "$FRONTEND_DIR" ] && [ -d "$FRONTEND_DIR" ]; then
    if command -v npm >/dev/null 2>&1; then
      echo -e "[setup] ${GREEN}Installing frontend dependencies via npm...${NC}"
      (
        cd "$FRONTEND_DIR"
        [ -d node_modules ] || npm install --silent
      )
    else
      echo -e "${YELLOW}Notice: npm/node not found. Install Node.js (v18+) to run the web UI, or use --docker.${NC}"
      BACKEND_ONLY=1
    fi
  fi
fi

# ------------------------------------------------------------ 4. Ready & Launch
echo ""
echo -e "${GREEN}======================================================${NC}"
echo -e "${GREEN}✓ Flatland setup completed successfully!${NC}"
echo -e "${GREEN}======================================================${NC}"
echo ""
echo -e "  Backend Engine : ${CYAN}$BACKEND_DIR${NC}"
if [ -n "$FRONTEND_DIR" ] && [ -d "$FRONTEND_DIR" ]; then
  echo -e "  Web Client     : ${CYAN}$FRONTEND_DIR${NC}"
fi
echo ""

if [ "$START_SERVER" = "0" ]; then
  echo "To launch Flatland anytime, run:"
  if [ "$DOCKER_MODE" = "1" ]; then
    echo "  cd $BACKEND_DIR && ./run.sh docker"
  else
    echo "  cd $BACKEND_DIR && ./run.sh"
  fi
  echo ""
  exit 0
fi

echo -e "${BOLD}Starting Flatland...${NC}"
if [ "$DOCKER_MODE" = "1" ]; then
  cd "$BACKEND_DIR"
  FRONTEND_DIR="$FRONTEND_DIR" exec ./run.sh docker
elif [ "$BACKEND_ONLY" = "1" ]; then
  cd "$BACKEND_DIR"
  exec ./run.sh backend
else
  cd "$BACKEND_DIR"
  FRONTEND_DIR="$FRONTEND_DIR" exec ./run.sh
fi
