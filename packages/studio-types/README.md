# @immersive/studio-types

Shared TypeScript types for the Video Game Generation Studio asset spec and job manifest.

Source of truth for field meanings: `docs/studio/json-schema-spec.md`.

JSON Schema (for Python worker validation): `schema/studio-asset-spec-v0.1.schema.json` and `schema/studio-job-manifest-v0.1.schema.json`.

When the studio worker is implemented, both the web UI and worker should depend on this package.
