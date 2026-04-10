# Changelog

All notable changes to the **`immersive-studio`** PyPI package and the studio worker in this monorepo are documented here. Versions follow the Python package version in `apps/studio-worker/pyproject.toml`.

## [0.1.0] — 2026-04-10

### Added

- Initial PyPI publication as **`immersive-studio`**: CLI (`immersive-studio`), import package **`immersive_studio`**, and **`studio_worker`** implementation.
- Unity-oriented job packs (`manifest.json`, `spec.json`, `pack.zip`), optional ComfyUI PBR textures and Blender placeholder GLB export.
- FastAPI worker for the `/studio` web UI; GitHub Actions workflow to build and upload to PyPI with **`twine`** and repository secret **`PYPI_API_TOKEN`**.

[0.1.0]: https://pypi.org/project/immersive-studio/0.1.0/
