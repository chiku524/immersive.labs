# Contributing

This monorepo hosts the marketing site (`apps/web`), the **Immersive Studio** Python worker (`apps/studio-worker`, published as [**immersive-studio** on PyPI](https://pypi.org/project/immersive-studio/)), shared types (`packages/studio-types`), and the Unity importer (`packages/studio-unity`).

## End users (CLI from PyPI)

Install the published package:

```bash
pipx install immersive-studio
# or: pip install immersive-studio
```

See [apps/studio-worker/README.md](./apps/studio-worker/README.md) for the CLI, environment variables, and local ComfyUI/Blender setup.

## Monorepo developers

From the repo root:

```bash
cd apps/studio-worker
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m pytest
```

The web app: `npm install` then `npm run dev` (see root [README.md](./README.md)).

## Releases (maintainers)

See **[docs/studio/releasing.md](./docs/studio/releasing.md)** for versioning, schema sync, tags, GitHub Releases, and PyPI/TestPyPI workflows.
