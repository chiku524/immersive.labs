# Releasing `immersive-studio` (PyPI)

Checklist for maintainers when cutting a new **Python package** release from this monorepo.

## 1. Version bump

- Edit **`apps/studio-worker/pyproject.toml`** → `[project]` → **`version`** (PEP 440).
- Update **`CHANGELOG.md`** at the repo root with a new section for the release (date, highlights).

## 2. JSON Schema (bundled copy)

The canonical Studio asset spec schema lives at:

`packages/studio-types/schema/studio-asset-spec-v0.1.schema.json`

Runtime and wheels use a **copy** at:

`apps/studio-worker/src/studio_worker/data/studio-asset-spec-v0.1.schema.json`

After editing the canonical file, sync the bundled copy:

```bash
python scripts/sync-studio-asset-schema.py
```

CI (**schema sync check** workflow) fails on PRs if these two files drift apart (`--check`).

## 3. Tag and GitHub Release

- Create an **annotated or lightweight tag** matching the package version, e.g. **`v0.2.0`**:

  ```bash
  git tag -a v0.2.0 -m "immersive-studio 0.2.0"
  git push origin v0.2.0
  ```

- On GitHub: **Releases → Draft a new release**, choose the tag, paste **release notes** (can mirror `CHANGELOG.md`), and **Publish release**.

Publishing a release triggers **`.github/workflows/publish-immersive-studio.yml`** (`release: types: [published]`) which builds and uploads to **PyPI** (requires **`PYPI_API_TOKEN`**).

You can also run the workflow manually: **Actions → PyPI publish (immersive-studio package) → Run workflow**.

## 4. Verify PyPI

- [https://pypi.org/project/immersive-studio/](https://pypi.org/project/immersive-studio/) — version, files, description.
- Smoke test: `pip install immersive-studio==<version>` and `immersive-studio doctor` (or `python -m studio_worker.cli doctor`).

## 5. Optional: TestPyPI dry run

For a test upload without affecting the real index:

- Create an API token on [TestPyPI](https://test.pypi.org/manage/account/token/).
- Add repository secret **`TESTPYPI_API_TOKEN`**.
- Run **Actions → Publish to TestPyPI** (`workflow_dispatch` only).

## 6. Optional: trusted publishing (OIDC)

The default PyPI workflow uses **`PYPI_API_TOKEN`** and **`twine`** only. To adopt **PyPI trusted publishing** later, see [PyPI trusted publishers](https://docs.pypi.org/trusted-publishers/) and adjust workflows carefully (avoid mixing with token uploads in the same step).
