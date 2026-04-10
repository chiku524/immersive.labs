# Build from monorepo root (paths expect apps/studio-worker + packages/studio-types):
#   docker build -f apps/studio-worker/Dockerfile .
#
# Runtime: STUDIO_CORS_ORIGINS = comma-separated browser origins for /studio (Vercel + custom domain), e.g.:
#   https://your-app.vercel.app,https://www.example.com

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STUDIO_REPO_ROOT=/repo

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
