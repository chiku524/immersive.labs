@echo off
REM Run the studio CLI without relying on PATH to pip's Scripts folder (common on Windows user installs).
REM Usage: scripts\immersive-studio.cmd doctor
python -m studio_worker.cli %*
