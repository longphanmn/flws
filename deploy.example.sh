#!/usr/bin/env bash
set -euo pipefail

SERVER="${SERVER:-root@your-server-ip}"
REMOTE_DIR="~/app/fl"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Multi-repo auto-detection for backend (flws), frontend (flws-web) and landing page (flws-page)
if [ -z "${BACKEND_DIR:-}" ]; then
  if [ -d "$LOCAL_DIR/flws" ]; then
    BACKEND_DIR="$(cd "$LOCAL_DIR/flws" && pwd)"
  elif [ -d "$LOCAL_DIR/../flws" ]; then
    BACKEND_DIR="$(cd "$LOCAL_DIR/../flws" && pwd)"
  else
    BACKEND_DIR="$LOCAL_DIR"
  fi
fi

if [ -z "${FRONTEND_DIR:-}" ]; then
  if [ -d "$LOCAL_DIR/flws-web" ]; then
    FRONTEND_DIR="$(cd "$LOCAL_DIR/flws-web" && pwd)"
  elif [ -d "$LOCAL_DIR/../flws-web" ]; then
    FRONTEND_DIR="$(cd "$LOCAL_DIR/../flws-web" && pwd)"
  else
    FRONTEND_DIR="$LOCAL_DIR/flws-web"
  fi
fi

if [ -z "${LANDING_DIR:-}" ]; then
  if [ -d "$LOCAL_DIR/flws-page" ]; then
    LANDING_DIR="$(cd "$LOCAL_DIR/flws-page" && pwd)"
  elif [ -d "$LOCAL_DIR/../flws-page" ]; then
    LANDING_DIR="$(cd "$LOCAL_DIR/../flws-page" && pwd)"
  else
    LANDING_DIR="$LOCAL_DIR/flws-page"
  fi
fi

# Load independent backend, frontend and workspace .env files
if [ -f "$BACKEND_DIR/.env" ]; then
  echo "[deploy] Loading backend env from $BACKEND_DIR/.env"
  set -a
  source "$BACKEND_DIR/.env"
  set +a
elif [ -f "$BACKEND_DIR/backend/.env" ]; then
  echo "[deploy] Loading backend env from $BACKEND_DIR/backend/.env"
  set -a
  source "$BACKEND_DIR/backend/.env"
  set +a
fi

if [ -f "$FRONTEND_DIR/.env" ]; then
  echo "[deploy] Loading frontend env from $FRONTEND_DIR/.env"
  set -a
  source "$FRONTEND_DIR/.env"
  set +a
fi

if [ -f "$LOCAL_DIR/.env" ] && [ "$LOCAL_DIR" != "$BACKEND_DIR" ]; then
  echo "[deploy] Loading workspace orchestrator env from $LOCAL_DIR/.env"
  set -a
  source "$LOCAL_DIR/.env"
  set +a
fi

# Normalize directory paths if .env provided relative paths
if [ -d "$BACKEND_DIR" ]; then BACKEND_DIR="$(cd "$BACKEND_DIR" && pwd)"; fi
if [ -d "$FRONTEND_DIR" ]; then FRONTEND_DIR="$(cd "$FRONTEND_DIR" && pwd)"; fi
if [ -d "$LANDING_DIR" ]; then LANDING_DIR="$(cd "$LANDING_DIR" && pwd)"; fi

CLEAR_DB="${CLEAR_DB:-0}"
GTM_ID="${GTM_ID:-${GOOGLE_TAG_MANAGER_ID:-}}"
GTM_CLEAR=0
GA_ID="${GA_ID:-${GA_MEASUREMENT_ID:-}}"
GA_CLEAR=0
API_URL="${API_URL:-${BACKEND_URL:-${VITE_BACKEND_URL:-}}}"
WS_URL="${WS_URL:-${VITE_WS_URL:-}}"
DEPLOY_GH_PAGES="${DEPLOY_GH_PAGES:-1}"
GH_PAGES_ONLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend-dir=*)
      BACKEND_DIR="${1#*=}"
      shift
      ;;
    --backend-dir)
      BACKEND_DIR="$2"
      shift 2
      ;;
    --frontend-dir=*)
      FRONTEND_DIR="${1#*=}"
      shift
      ;;
    --frontend-dir)
      FRONTEND_DIR="$2"
      shift 2
      ;;
    --landing-dir=*)
      LANDING_DIR="${1#*=}"
      shift
      ;;
    --landing-dir)
      LANDING_DIR="$2"
      shift 2
      ;;
    --skip-gh-pages|--no-gh-pages)
      DEPLOY_GH_PAGES=0
      shift
      ;;
    --gh-pages-only)
      GH_PAGES_ONLY=1
      DEPLOY_GH_PAGES=1
      shift
      ;;
    --clear-db)
      CLEAR_DB=1
      shift
      ;;
    --gtm-id=*)
      GTM_ID="${1#*=}"
      shift
      ;;
    --gtm-id)
      GTM_ID="$2"
      shift 2
      ;;
    --gtm=*)
      GTM_ID="${1#*=}"
      shift
      ;;
    --gtm)
      GTM_ID="$2"
      shift 2
      ;;
    --no-gtm|--clear-gtm)
      GTM_CLEAR=1
      GTM_ID=""
      shift
      ;;
    --ga-id=*)
      GA_ID="${1#*=}"
      shift
      ;;
    --ga-id)
      GA_ID="$2"
      shift 2
      ;;
    --ga=*)
      GA_ID="${1#*=}"
      shift
      ;;
    --ga)
      GA_ID="$2"
      shift 2
      ;;
    --no-ga|--clear-ga)
      GA_CLEAR=1
      GA_ID=""
      shift
      ;;
    --api-url=*)
      API_URL="${1#*=}"
      shift
      ;;
    --api-url|--api)
      API_URL="$2"
      shift 2
      ;;
    --api=*)
      API_URL="${1#*=}"
      shift
      ;;
    --ws-url=*)
      WS_URL="${1#*=}"
      shift
      ;;
    --ws-url|--ws)
      WS_URL="$2"
      shift 2
      ;;
    --ws=*)
      WS_URL="${1#*=}"
      shift
      ;;
    --no-tags|--clear-tags)
      GTM_CLEAR=1
      GTM_ID=""
      GA_CLEAR=1
      GA_ID=""
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [ -n "$GTM_ID" ]; then
  echo "[deploy] Google Tag Manager ID: $GTM_ID"
fi
if [ -n "$GA_ID" ]; then
  echo "[deploy] Google Analytics ID: $GA_ID"
fi

if [ "$GH_PAGES_ONLY" = "0" ]; then
  echo "[deploy] Ensuring remote directory $REMOTE_DIR"
  ssh "$SERVER" "mkdir -p $REMOTE_DIR"

echo "[deploy] Syncing project to $SERVER:$REMOTE_DIR"
# Detect what changed for smart restart (preserve world if only frontend).
# Compare against the last DEPLOYED commit (marker stored on the server), not
# HEAD~1 — several local commits between deploys would otherwise look "unchanged".
BACKEND_CHANGED=0
FRONTEND_CHANGED=0

# Backend change detection (checks $BACKEND_DIR git repo)
if [ -d "$BACKEND_DIR/.git" ]; then
  DEPLOYED_REF="$(ssh "$SERVER" "cat $REMOTE_DIR/.deployed-commit 2>/dev/null || true")"
  if [ -n "$DEPLOYED_REF" ] && git -C "$BACKEND_DIR" cat-file -e "$DEPLOYED_REF" 2>/dev/null; then
    DIFF_BASE="$DEPLOYED_REF"
  else
    DIFF_BASE="HEAD~1"  # legacy best-effort fallback
  fi
  if git -C "$BACKEND_DIR" diff --name-only "$DIFF_BASE" HEAD 2>/dev/null | grep -qE "(^backend/|\.py$|\.c$|\.h$|pyproject\.toml|uv\.lock)"; then
    BACKEND_CHANGED=1
  fi
  if git -C "$BACKEND_DIR" status --porcelain 2>/dev/null | grep -qE "(backend/|\.py$|\.c$|\.h$|pyproject\.toml|uv\.lock)"; then
    BACKEND_CHANGED=1
  fi
elif [ -d "$BACKEND_DIR" ]; then
  BACKEND_CHANGED=1
fi

# Frontend change detection (checks $FRONTEND_DIR git repo)
if [ -d "$FRONTEND_DIR/.git" ]; then
  FE_DEPLOYED_REF="$(ssh "$SERVER" "cat $REMOTE_DIR/.deployed-commit-frontend 2>/dev/null || true")"
  if [ -n "$FE_DEPLOYED_REF" ] && git -C "$FRONTEND_DIR" cat-file -e "$FE_DEPLOYED_REF" 2>/dev/null; then
    FE_DIFF_BASE="$FE_DEPLOYED_REF"
  else
    FE_DIFF_BASE="HEAD~1"
  fi
  if git -C "$FRONTEND_DIR" diff --name-only "$FE_DIFF_BASE" HEAD 2>/dev/null | grep -q .; then
    FRONTEND_CHANGED=1
  fi
  if git -C "$FRONTEND_DIR" status --porcelain 2>/dev/null | grep -q .; then
    FRONTEND_CHANGED=1
  fi
elif [ -d "$FRONTEND_DIR" ]; then
  FRONTEND_CHANGED=1
fi

# If GTM or GA configuration changed or passed explicitly, force frontend restart
if [ -n "$GTM_ID" ] || [ "$GTM_CLEAR" = "1" ] || [ -n "$GA_ID" ] || [ "$GA_CLEAR" = "1" ]; then
  FRONTEND_CHANGED=1
fi
if [ "$CLEAR_DB" = "1" ]; then
  BACKEND_CHANGED=1
fi
# fallback: if we can't detect, assume frontend-only to preserve world
if [ "$BACKEND_CHANGED" = 0 ] && [ "$FRONTEND_CHANGED" = 0 ]; then
  echo "[deploy] No backend/frontend changes detected, assuming frontend-only (preserve world)"
  FRONTEND_CHANGED=1
fi
echo "[deploy] Backend changed: $BACKEND_CHANGED, Frontend changed: $FRONTEND_CHANGED (world preserved if backend unchanged)"

# Use rsync if available, otherwise fallback to scp
if command -v rsync >/dev/null 2>&1; then
  echo "[deploy] Syncing backend from $BACKEND_DIR to $SERVER:$REMOTE_DIR/"
  rsync -avz --delete \
    --exclude '.git' \
    --exclude '.venv' \
    --exclude 'node_modules' \
    --exclude '__pycache__' \
    --exclude '.pytest_cache' \
    --exclude 'dist' \
    --exclude '.DS_Store' \
    --exclude 'deploy.sh' \
    --exclude '.deployed-commit*' \
    --exclude '.ga_id' \
    --exclude '.gtm_id' \
    --exclude '*.log' \
    --exclude 'snapshot*' \
    --exclude '**/snapshot*' \
    --exclude 'backend/flatworld.db' \
    --exclude 'backend/flatworld.db-*' \
    --exclude '**/flatworld.db*' \
    --exclude 'backend/app/_flatland_core.so' \
    --exclude 'backend/app/_flatland_core.dylib' \
    --exclude '*.so' \
    --exclude '*.dylib' \
    --exclude 'frontend' \
    "$BACKEND_DIR"/ "$SERVER:$REMOTE_DIR"/

  # Sync frontend from $FRONTEND_DIR to $SERVER:$REMOTE_DIR/frontend/
  if [ -d "$FRONTEND_DIR" ]; then
    echo "[deploy] Syncing frontend from $FRONTEND_DIR to $SERVER:$REMOTE_DIR/frontend/"
    rsync -avz --delete \
      --exclude '.git' \
      --exclude 'node_modules' \
      --exclude 'dist' \
      --exclude '.DS_Store' \
      "$FRONTEND_DIR"/ "$SERVER:$REMOTE_DIR/frontend"/
  fi
else
  echo "[deploy] rsync not found, using tar+scp"
  tar -czf /tmp/fl-backend.tgz \
    --exclude='.git' --exclude='.venv' \
    --exclude='__pycache__' --exclude='.pytest_cache' \
    --exclude='*.log' --exclude='*.so' --exclude='*.dylib' \
    -C "$BACKEND_DIR" .
  tar -czf /tmp/fl-frontend.tgz \
    --exclude='.git' --exclude='node_modules' --exclude='dist' \
    -C "$FRONTEND_DIR" .
  scp /tmp/fl-backend.tgz /tmp/fl-frontend.tgz "$SERVER:/tmp/"
  ssh "$SERVER" "mkdir -p $REMOTE_DIR/frontend && tar -xzf /tmp/fl-backend.tgz -C $REMOTE_DIR && tar -xzf /tmp/fl-frontend.tgz -C $REMOTE_DIR/frontend && rm /tmp/fl-backend.tgz /tmp/fl-frontend.tgz"
fi

echo "[deploy] Installing deps and (re)starting server in background"
ssh "$SERVER" bash << REMOTE
set -euo pipefail
cd ~/app/fl
BACKEND_CHANGED=$BACKEND_CHANGED
FRONTEND_CHANGED=$FRONTEND_CHANGED
CLEAR_DB=$CLEAR_DB
GTM_ID="$GTM_ID"
GTM_CLEAR=$GTM_CLEAR
GA_ID="$GA_ID"
GA_CLEAR=$GA_CLEAR
echo "[remote] Backend changed: \$BACKEND_CHANGED, Frontend changed: \$FRONTEND_CHANGED, Clear DB: \$CLEAR_DB"

# Handle Google Tag Manager & Google Analytics (purely deploy-time, zero source code change)
# 1. Google Tag Manager (GTM)
if [ "\$GTM_CLEAR" = "1" ]; then
  echo "[remote] Removing Google Tag Manager tags"
  rm -f ~/app/fl/.gtm_id
  python3 - << 'PYEOF'
import os, sys, re
html_path = os.path.expanduser("~/app/fl/frontend/index.html")
if os.path.exists(html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    content = re.sub(r'\s*<!-- Google Tag Manager -->[\s\S]*?<!-- End Google Tag Manager -->\s*', '\n  ', content)
    content = re.sub(r'\s*<!-- Google Tag Manager \(noscript\) -->[\s\S]*?<!-- End Google Tag Manager \(noscript\) -->\s*', '\n    ', content)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("[remote] Google Tag Manager removed from frontend/index.html")
PYEOF
else
  if [ -z "\$GTM_ID" ] && [ -f ~/app/fl/.gtm_id ]; then
    GTM_ID="\$(cat ~/app/fl/.gtm_id 2>/dev/null | tr -d '[:space:]')"
  fi
  if [ -n "\$GTM_ID" ]; then
    echo "[remote] Configuring Google Tag Manager (\$GTM_ID) in frontend/index.html"
    echo "\$GTM_ID" > ~/app/fl/.gtm_id
    export GTM_ID="\$GTM_ID"
    python3 - << 'PYEOF'
import os, sys, re
gtm_id = os.environ.get("GTM_ID", "").strip()
if not gtm_id:
    sys.exit(0)
html_path = os.path.expanduser("~/app/fl/frontend/index.html")
if not os.path.exists(html_path):
    print(f"[remote] Warning: {html_path} not found", file=sys.stderr)
    sys.exit(0)
with open(html_path, "r", encoding="utf-8") as f:
    content = f.read()

# Clean existing GTM snippets
content = re.sub(r'\s*<!-- Google Tag Manager -->[\s\S]*?<!-- End Google Tag Manager -->\s*', '\n  ', content)
content = re.sub(r'\s*<!-- Google Tag Manager \(noscript\) -->[\s\S]*?<!-- End Google Tag Manager \(noscript\) -->\s*', '\n    ', content)

head_snippet = f"""    <!-- Google Tag Manager -->
    <script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{\x27gtm.start\x27:
    new Date().getTime(),event:\x27gtm.js\x27}});var f=d.getElementsByTagName(s)[0],
    j=d.createElement(s),dl=l!=\x27dataLayer\x27?\x27&l=\x27+l:\x27\x27;j.async=true;j.src=
    \x27https://www.googletagmanager.com/gtm.js?id=\x27+i+dl;f.parentNode.insertBefore(j,f);
    }})(window,document,\x27script\x27,\x27dataLayer\x27,\x27{gtm_id}\x27);</script>
    <!-- End Google Tag Manager -->
"""

body_snippet = f"""    <!-- Google Tag Manager (noscript) -->
    <noscript><iframe src="https://www.googletagmanager.com/ns.html?id={gtm_id}"
    height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
    <!-- End Google Tag Manager (noscript) -->
"""

if "</head>" in content:
    content = content.replace("</head>", head_snippet + "  </head>", 1)
content = re.sub(r"(<body[^>]*>)", r"\1\n" + body_snippet, content, count=1)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(content)
print(f"[remote] Injected Google Tag Manager ({gtm_id}) into frontend/index.html (head script + body noscript)")
PYEOF
  fi
fi

# 2. Google Analytics 4 (GA4) fallback
if [ "\$GA_CLEAR" = "1" ]; then
  echo "[remote] Removing Google Analytics tag"
  rm -f ~/app/fl/.ga_id
  python3 - << 'PYEOF'
import os, sys, re
html_path = os.path.expanduser("~/app/fl/frontend/index.html")
if os.path.exists(html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    cleaned = re.sub(r'\s*<!-- Google tag \(gtag\.js\) START -->[\s\S]*?<!-- Google tag \(gtag\.js\) END -->\s*', '\n', content)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(cleaned)
    print("[remote] Google Analytics removed from frontend/index.html")
PYEOF
else
  if [ -z "\$GA_ID" ] && [ -f ~/app/fl/.ga_id ]; then
    GA_ID="\$(cat ~/app/fl/.ga_id 2>/dev/null | tr -d '[:space:]')"
  fi
  if [ -n "\$GA_ID" ]; then
    echo "[remote] Configuring Google Analytics (\$GA_ID) in frontend/index.html"
    echo "\$GA_ID" > ~/app/fl/.ga_id
    export GA_ID="\$GA_ID"
    python3 - << 'PYEOF'
import os, sys, re
ga_id = os.environ.get("GA_ID", "").strip()
if not ga_id:
    sys.exit(0)
html_path = os.path.expanduser("~/app/fl/frontend/index.html")
if not os.path.exists(html_path):
    print(f"[remote] Warning: {html_path} not found", file=sys.stderr)
    sys.exit(0)
with open(html_path, "r", encoding="utf-8") as f:
    content = f.read()

content = re.sub(r'\s*<!-- Google tag \(gtag\.js\) START -->[\s\S]*?<!-- Google tag \(gtag\.js\) END -->\s*', '\n', content)

snippet = f"""    <!-- Google tag (gtag.js) START -->
    <script async src="https://www.googletagmanager.com/gtag/js?id={ga_id}"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());

      gtag('config', '{ga_id}');
    </script>
    <!-- Google tag (gtag.js) END -->
"""

if "</head>" in content:
    content = content.replace("</head>", snippet + "  </head>", 1)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[remote] Injected Google Analytics ({ga_id}) into frontend/index.html")
PYEOF
  fi
fi

if [ "\$BACKEND_CHANGED" = "1" ]; then
  if [ "\$CLEAR_DB" = "1" ]; then
    echo "[remote] Clear DB: discarding world snapshot too — next start is a fresh world"
    rm -f ~/app/fl/snapshot.json ~/app/fl/snapshot.loaded
  else
    echo "[remote] Saving live world snapshot before restart (preserve tick/entities)"
    curl -s http://localhost:8000/api/state > ~/app/fl/snapshot.json 2>/dev/null && echo "[remote] snapshot saved tick=\$(python3 -c 'import json;print(json.load(open(\"/root/app/fl/snapshot.json\"))[\"tick\"])' 2>/dev/null || echo '?') entities=\$(python3 -c 'import json;print(len(json.load(open(\"/root/app/fl/snapshot.json\"))[\"entities\"]))' 2>/dev/null || echo '?')" || echo "[remote] snapshot save failed (fresh world)"
  fi
  echo "[remote] Killing backend (uvicorn) — will restore snapshot if present"
  pkill -f "uvicorn app.main:app" || true
  fuser -k 8000/tcp 2>/dev/null || true
  sleep 1
  if [ "\$CLEAR_DB" = "1" ]; then
    echo "[remote] Wiping production database (chronicle + god passkey)"
    rm -f ~/app/fl/backend/flatworld.db ~/app/fl/backend/flatworld.db-wal ~/app/fl/backend/flatworld.db-shm
  fi
else
  echo "[remote] Backend unchanged — preserving world (no restart)"
fi
if [ "\$FRONTEND_CHANGED" = "1" ]; then
  echo "[remote] Killing frontend (vite)"
  pkill -f "vite" || true
  pkill -f "npm.*dev" || true
  fuser -k 5173/tcp 2>/dev/null || true
else
  echo "[remote] Frontend unchanged — preserving frontend"
fi
sleep 2
export PATH="\$HOME/.local/bin:\$PATH"

if [ "$BACKEND_CHANGED" = "1" ]; then
  if ! command -v uv >/dev/null 2>&1; then
    echo "[remote] uv not found, please install uv"
    exit 1
  fi
  echo "[remote] [backend] sync deps"
  cd ~/app/fl/backend
  uv sync --quiet
  echo "[remote] [backend] compiling native core (M-4 OpenMP)"
  gcc -O3 -shared -fPIC -fopenmp -march=native -ffast-math -Wall app/flatland_core.c -o app/_flatland_core.so -lm 2>/dev/null || gcc -O3 -shared -fPIC -Wall -ffast-math app/flatland_core.c -o app/_flatland_core.so -lm 2>/dev/null || true
  ls -lh app/_flatland_core.so 2>/dev/null | awk '{print "[remote] native core:", \$9, \$5}' || true
  if nm -D app/_flatland_core.so 2>/dev/null | grep -q c_batch_update_creatures_omp; then echo "[remote] OpenMP kernel: OK (c_batch_update_creatures_omp)"; else echo "[remote] OpenMP kernel: serial fallback"; fi
  echo "[remote] Starting backend on 0.0.0.0:8000 (bg) — permessage-deflate off (AX P0)"
  nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --ws-per-message-deflate false > ~/app/fl/backend.log 2>&1 &
  echo "[remote] backend pid \$! log: ~/app/fl/backend.log"
  cd ~/app/fl
else
  echo "[remote] Skipping backend sync/start (unchanged, world preserved)"
fi

if [ "$FRONTEND_CHANGED" = "1" ]; then
  if ! command -v npm >/dev/null 2>&1; then
    echo "[remote] npm not found, please install npm/node"
    exit 1
  fi
  echo "[remote] [frontend] install deps"
  cd ~/app/fl/frontend
  if [ ! -d node_modules ]; then
    npm install --silent
  else
    npm install --silent || true
  fi
  echo "[remote] [frontend] building production bundle"
  npm run build
  echo "[remote] Starting frontend in preview mode on 0.0.0.0:5173 (bg)"
  nohup ./node_modules/.bin/vite preview --host 0.0.0.0 --port 5173 > ~/app/fl/frontend.log 2>&1 &
  echo "[remote] frontend pid \$! log: ~/app/fl/frontend.log"
  cd ~/app/fl
else
  echo "[remote] Skipping frontend sync/start (unchanged)"
fi

sleep 3
echo "[remote] Checking ports"
ss -tulpn | grep -E '8000|5173' || ss -tlnp | grep -E '8000|5173' || netstat -tulpn 2>/dev/null | grep -E '8000|5173' || echo "ss/netstat not available, trying lsof"
lsof -nP -iTCP:8000 -sTCP:LISTEN 2>/dev/null | head -n 5 || true
lsof -nP -iTCP:5173 -sTCP:LISTEN 2>/dev/null | head -n 5 || true

echo "[remote] Tail logs (last 20 lines)"
echo "--- backend.log ---"
tail -n 20 ~/app/fl/backend.log 2>/dev/null || true
echo "--- frontend.log ---"
tail -n 20 ~/app/fl/frontend.log 2>/dev/null || true

echo "[remote] Done. UI: http://${SERVER_HOST:-your-server-ip}:5173  API: http://${SERVER_HOST:-your-server-ip}:8000/docs"
REMOTE

  echo "[deploy] Done production server deployment"
  # Remember what was deployed so the next run diffs against the right commit.
  if [ -d "$BACKEND_DIR/.git" ]; then
    git -C "$BACKEND_DIR" rev-parse HEAD | ssh "$SERVER" "cat > $REMOTE_DIR/.deployed-commit"
  fi
  if [ -d "$FRONTEND_DIR/.git" ]; then
    git -C "$FRONTEND_DIR" rev-parse HEAD | ssh "$SERVER" "cat > $REMOTE_DIR/.deployed-commit-frontend"
  fi
  echo "  Remote UI : http://${SERVER_HOST:-your-server-ip}:5173"
  echo "  Remote API: http://${SERVER_HOST:-your-server-ip}:8000/docs"
  echo "  Logs: ssh $SERVER 'tail -f ~/app/fl/backend.log ~/app/fl/frontend.log'"
fi

if [ "$DEPLOY_GH_PAGES" = "1" ]; then
  echo ""
  echo "====================================================================="
  echo "[deploy] Building & deploying minified frontend demo to GitHub Pages"
  echo "====================================================================="
  DEMO_API_URL="${API_URL:-${BACKEND_URL:-${VITE_BACKEND_URL:-}}}"
  DEMO_API_URL="${DEMO_API_URL%/}"
  DEMO_WS_URL="${WS_URL:-${VITE_WS_URL:-}}"
  if [ -z "$DEMO_WS_URL" ]; then
    if [[ "$DEMO_API_URL" =~ ^https:// ]]; then
      DEMO_WS_URL="${DEMO_API_URL/https:\/\//wss://}/ws"
    elif [[ "$DEMO_API_URL" =~ ^http:// ]]; then
      DEMO_WS_URL="${DEMO_API_URL/http:\/\//ws://}/ws"
    fi
  fi
  echo "[deploy] Demo target API link from .env: $DEMO_API_URL (WS: $DEMO_WS_URL)"
  FRONTEND_URL="${FRONTEND_URL:-${DEMO_URL:-https://longphanmn.github.io/flws-web/}}"
  LANDING_URL="${LANDING_URL:-https://longphanmn.github.io/flws-page/}"
  (
    cd "$FRONTEND_DIR"
    echo "[deploy] Generating static Living Wiki, OpenAPI, and Swagger UI for flws-web"
    FRONTEND_DIR="$FRONTEND_DIR" BACKEND_DIR="$BACKEND_DIR" DEMO_API_URL="$DEMO_API_URL" python3 -c '
import urllib.request, re, os

headers = {"User-Agent": "Mozilla/5.0 (Flatland-Deploy/1.0)"}
def fetch(url):
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(req, timeout=10).read().decode("utf-8")

frontend_dir = os.environ.get("FRONTEND_DIR", ".")
backend_dir = os.environ.get("BACKEND_DIR", ".")
server_api = os.environ.get("DEMO_API_URL", "https://world.minhnhan.in").rstrip("/")
pub = os.path.join(frontend_dir, "public")
os.makedirs(os.path.join(pub, "docs"), exist_ok=True)
os.makedirs(os.path.join(pub, "wiki"), exist_ok=True)
os.makedirs(os.path.join(pub, "health"), exist_ok=True)

try:
    openapi_raw = fetch(f"{server_api}/openapi.json")
    with open(os.path.join(pub, "openapi.json"), "w", encoding="utf-8") as f: f.write(openapi_raw)
except Exception as e:
    print(f"Warning: could not fetch openapi.json: {e}")

laws_src = os.path.join(backend_dir, "docs/god-laws.md")
if os.path.exists(laws_src):
    with open(laws_src, "r", encoding="utf-8") as f: c = f.read()
    with open(os.path.join(pub, "docs/god-laws.md"), "w", encoding="utf-8") as f: f.write(c)

swagger_html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Flatland World Simulation — API Documentation</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
  <link rel="icon" type="image/svg+xml" href="../icon.svg">
  <style>
    body { margin: 0; background: #0d1117; color: #c9d1d9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .nav-bar { background: #161b22; border-bottom: 1px solid #30363d; padding: 12px 24px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
    .nav-bar a { color: #58a6ff; text-decoration: none; font-size: 13px; margin-left: 16px; font-weight: 500; }
    .nav-bar a:hover { text-decoration: underline; }
    .nav-bar .brand { font-weight: 700; color: #f0f6fc; font-size: 14px; margin-left: 0; display: inline-flex; align-items: center; gap: 6px; }
    .swagger-ui { filter: invert(88%) hue-rotate(180deg); max-width: 1200px; margin: 0 auto; }
    .swagger-ui .topbar { display: none; }
    .swagger-ui img { filter: invert(100%) hue-rotate(180deg); }
  </style>
</head>
<body>
  <div class="nav-bar">
    <a href="../" class="brand">← Back to Flatland Simulation</a>
    <div>
      <a href="../wiki/">Living Wiki ↗</a>
      <a href="../health/">Engine Health ↗</a>
      <a href="https://longphanmn.github.io/flws-page/" target="_blank" rel="noopener noreferrer">Introduce Page ↗</a>
      <a href="../openapi.json" target="_blank">/openapi.json ↗</a>
    </div>
  </div>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.onload = function() {
      SwaggerUIBundle({
        url: "../openapi.json",
        dom_id: "#swagger-ui",
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIBundle.SwaggerUIStandalonePreset
        ],
        layout: "BaseLayout"
      });
    };
  </script>
</body>
</html>
"""
with open(os.path.join(pub, "docs/index.html"), "w", encoding="utf-8") as f: f.write(swagger_html)

langs = ["en", "vi", "fr"]
for l in langs:
    try:
        raw = fetch(f"{server_api}/wiki?lang={l}")
        p = raw
        p = p.replace(server_api + "/wiki", "./")
        p = p.replace(server_api, "./")
        p = p.replace("href=\"/wiki?lang=en\"", "href=\"./\"")
        p = p.replace("href=\"/wiki?lang=vi\"", "href=\"./wiki-vi.html\"")
        p = p.replace("href=\"/wiki?lang=fr\"", "href=\"./wiki-fr.html\"")
        p = p.replace("href=\"/docs\"", "href=\"../docs/\"")
        p = p.replace("href=\"/openapi.json\"", "href=\"../openapi.json\"")
        p = p.replace("href=\"/docs/god-laws.md#", "href=\"../docs/god-laws.md#")
        p = re.sub(r"href=\"/api/wiki\?lang=[a-z]+\"", "href=\"../openapi.json\"", p)
        p = p.replace("href=\"/demo/\"", "href=\"../\"")
        p = p.replace("href=\"/demo\"", "href=\"../\"")
        p = p.replace("href=\"/\"", "href=\"../\"")
        redir = {
            "en": """<script>(function(){var p=new URLSearchParams(window.location.search);var l=p.get("lang");if(l==="vi"||l==="vn"){window.location.replace("./wiki-vi.html"+window.location.search+window.location.hash);}else if(l==="fr"){window.location.replace("./wiki-fr.html"+window.location.search+window.location.hash);}})();</script>""",
            "vi": """<script>(function(){var p=new URLSearchParams(window.location.search);var l=p.get("lang");if(l==="en"){window.location.replace("./"+window.location.search+window.location.hash);}else if(l==="fr"){window.location.replace("./wiki-fr.html"+window.location.search+window.location.hash);}})();</script>""",
            "fr": """<script>(function(){var p=new URLSearchParams(window.location.search);var l=p.get("lang");if(l==="en"){window.location.replace("./"+window.location.search+window.location.hash);}else if(l==="vi"||l==="vn"){window.location.replace("./wiki-vi.html"+window.location.search+window.location.hash);}})();</script>"""
        }
        p = p.replace("<head>", "<head>\n" + redir[l])
        target_name = "index.html" if l == "en" else f"wiki-{l}.html"
        with open(os.path.join(pub, "wiki", target_name), "w", encoding="utf-8") as f: f.write(p)
    except Exception as e:
        print(f"Warning: could not fetch wiki {l}: {e}")
'
    VITE_BASE="./" VITE_IS_DEMO="true" VITE_DEMO_API_URL="$DEMO_API_URL" VITE_DEMO_WS_URL="$DEMO_WS_URL" FRONTEND_URL="$FRONTEND_URL" LANDING_URL="$LANDING_URL" npm run build
    DEMO_API_URL="$DEMO_API_URL" python3 -c '
import re, os
with open("dist/index.html", "r", encoding="utf-8") as f: c = f.read()
c = re.sub(r"<!--(?!\[if)[\s\S]*?-->", "", c)
c = re.sub(r"[ \t]+", " ", c)
c = re.sub(r"\n\s*", "\n", c)
with open("dist/index.html", "w", encoding="utf-8") as f: f.write(c.strip())

api_url = os.environ.get("DEMO_API_URL", "").rstrip("/")
health_path = "dist/health.html"
if os.path.exists(health_path):
    with open(health_path, "r", encoding="utf-8") as f: hc = f.read()
    import base64
    b64_url = base64.b64encode(api_url.encode("utf-8")).decode("ascii") if api_url else ""
    hc = hc.replace("__API_URL_PLACEHOLDER__", b64_url)
    with open(health_path, "w", encoding="utf-8") as f: f.write(hc)
'
  )

  # Support independent frontend GitHub Pages repository (flws-web)
  GH_PAGES_WEB_DIR="${GH_PAGES_WEB_DIR:-}"
  if [ -n "$GH_PAGES_WEB_DIR" ] && [ -d "$GH_PAGES_WEB_DIR/.git" ]; then
    echo "[deploy] Syncing independent web client bundle to $GH_PAGES_WEB_DIR/"
    rm -rf "$GH_PAGES_WEB_DIR/assets/"*
    cp -R "$FRONTEND_DIR/dist/"* "$GH_PAGES_WEB_DIR/"
    (
      cd "$GH_PAGES_WEB_DIR"
      git add .
      if ! git diff --cached --quiet; then
        git commit -m "deploy: update independent frontend web app on GitHub Pages"
        git push origin gh-pages 2>/dev/null || git push origin main 2>/dev/null || true
        echo "[deploy] Successfully deployed flws-web to GitHub Pages"
      fi
    )
  fi

  GH_PAGES_DIR="${GH_PAGES_DIR:-$LANDING_DIR}"
  if [ -d "$GH_PAGES_DIR/.git" ]; then
    echo "[deploy] Syncing landing page portal at $GH_PAGES_DIR/"
    (
      cd "$GH_PAGES_DIR"
      git add index.html 404.html assets/ README.md .nojekyll 2>/dev/null || true
      if ! git diff --cached --quiet; then
        git commit -m "deploy: update landing showcase portal on GitHub Pages"
        git push origin main 2>/dev/null || git push origin gh-pages 2>/dev/null || true
        echo "[deploy] Successfully deployed landing page to GitHub Pages"
      else
        echo "[deploy] Landing page already up-to-date"
      fi
    )
    echo "  GitHub Pages Landing: ${LANDING_URL:-https://longphanmn.github.io/flws-page/}"
    echo "  GitHub Pages Web UI:  ${FRONTEND_URL:-https://longphanmn.github.io/flws-web/}"
  else
    echo "[deploy] Notice: GitHub Pages workspace not found at $GH_PAGES_DIR, skipping gh-pages deploy"
  fi
fi
