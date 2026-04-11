# Build from monorepo root (paths expect apps/studio-worker + packages/studio-types):
#   docker build -f apps/studio-worker/Dockerfile .
#
# Runtime env (see apps/studio-worker/.env.example):
#   STUDIO_CORS_ORIGINS — comma-separated browser origins for /studio
#   STUDIO_COMFY_URL — ComfyUI base URL (default in code: https://comfy.immersivelabs.space; same-VM: http://127.0.0.1:8188)
# Blender: official 4.2 LTS (docs target 4.x). Debian's apt package is older 3.4.x.

FROM python:3.12-slim-bookworm

ARG BLENDER_TAR_XZ_URL=https://download.blender.org/release/Blender4.2/blender-4.2.9-linux-x64.tar.xz
ARG BLENDER_DIR=blender-4.2.9-linux-x64

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STUDIO_REPO_ROOT=/repo \
    STUDIO_BLENDER_BIN=/usr/local/bin/blender \
    STUDIO_EMBEDDED_QUEUE_WORKER=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    xz-utils \
    && curl -fsSL "${BLENDER_TAR_XZ_URL}" -o /tmp/blender.tar.xz \
    && tar -xJf /tmp/blender.tar.xz -C /opt \
    && ln -sf "/opt/${BLENDER_DIR}/blender" /usr/local/bin/blender \
    && rm /tmp/blender.tar.xz \
    && apt-get purge -y curl xz-utils \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Official Blender build expects X11/GL shared libs (the apt `blender` package pulled these in before).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    libgl1 \
    libx11-6 \
    libsm6 \
    libice6 \
    libxext6 \
    libxxf86vm1 \
    libxi6 \
    libxfixes3 \
    libxrender1 \
    libfontconfig1 \
    libfreetype6 \
    libxkbcommon0 \
    libatomic1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /repo

# Layout required by studio_worker.paths (repo root = /repo)
COPY packages/studio-types/schema /repo/packages/studio-types/schema
COPY apps/studio-worker /repo/apps/studio-worker

WORKDIR /repo/apps/studio-worker
RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 1000 studio \
    && mkdir -p /repo/apps/studio-worker/output \
    && chown -R studio:studio /repo/apps/studio-worker/output

USER studio

EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/api/studio/health', timeout=4)"

CMD ["immersive-studio", "serve", "--host", "0.0.0.0", "--port", "8787"]
