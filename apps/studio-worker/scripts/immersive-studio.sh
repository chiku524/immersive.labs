#!/usr/bin/env bash
# Run the studio CLI without relying on PATH to pip's Scripts folder (common on Windows user installs).
# Usage: ./scripts/immersive-studio.sh doctor
exec python -m studio_worker.cli "$@"
