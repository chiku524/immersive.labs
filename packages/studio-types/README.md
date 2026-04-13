# @immersive/studio-types

Shared TypeScript types for the Video Game Generation Studio asset spec and job manifest.

Source of truth for field meanings: `docs/studio/json-schema-spec.md`.

JSON Schema (for Python worker validation): `schema/studio-asset-spec-v0.1.schema.json` and `schema/studio-job-manifest-v0.1.schema.json`.

The **`/studio`** page imports **`StudioDashboardPayload`**, **`StudioWorkerHints`**, **`StudioQueueSloSnapshot`**, **`StudioUsageInfo`**, **`StudioBillingStatus`**, **`StudioJobSummary`**, and **`StudioComfyStatusPayload`** from this package so UI types stay aligned with **`GET /api/studio/dashboard`** and related worker routes.
