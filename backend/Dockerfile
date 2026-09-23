# Flatland Backend — FastAPI + WebSocket + SimEngine
# Build: docker build -t flatland-backend .
# Run:   docker run -p 8000:8000 -v flatland-data:/data flatland-backend
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FLATWORLD_DB=/data/flatworld.db

WORKDIR /app

# Native core needs a C compiler; keep layer cache-friendly
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (better layer cache)
COPY pyproject.toml ./
# uv.lock is optional — present for local uv sync but not required in Docker
COPY uv.lock* ./

# Install runtime deps directly (avoid needing uv inside image).
# Keep in sync with pyproject.toml dependencies.
RUN pip install --upgrade pip && \
    pip install \
        "fastapi>=0.115" \
        "httpx>=0.27" \
        "numpy>=2" \
        "orjson>=3.10" \
        "textual>=8" \
        "uvicorn[standard]>=0.30" \
        "websockets>=12"

# Copy backend source
COPY app ./app
COPY tui ./tui

# Compile the OpenMP native core (M-4). Falls back to serial if OpenMP unavailable.
RUN gcc -O3 -shared -fPIC -fopenmp -march=native -ffast-math -Wall app/flatland_core.c -o app/_flatland_core.so -lm 2>&1 || \
    gcc -O3 -shared -fPIC -Wall -ffast-math app/flatland_core.c -o app/_flatland_core.so -lm 2>&1 || \
    echo "[docker] native core compile failed — running in pure-Python fallback" && \
    ls -lh app/_flatland_core.so 2>/dev/null || true && \
    (nm -D app/_flatland_core.so 2>/dev/null | grep -q c_batch_update_creatures_omp && echo "[docker] OpenMP kernel: OK" || echo "[docker] OpenMP kernel: serial/unavailable") || true

# Data volume for SQLite persistence and non-root process execution
RUN groupadd -g 1000 app && \
    useradd -u 1000 -g app app && \
    mkdir -p /data && \
    chown -R app:app /data /app
VOLUME ["/data"]

COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod 0755 /app/docker-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/healthz', timeout=3).raise_for_status()" || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--ws-per-message-deflate", "false"]
