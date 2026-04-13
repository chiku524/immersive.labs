#!/usr/bin/env node
/**
 * Production Vercel deploy after `npm run build`.
 *
 * Env:
 *   VERCEL_SCOPE or VERCEL_TEAM — team slug passed as `--scope` (needed when multiple teams exist).
 *   VERCEL_TOKEN — non-interactive auth (CI); combine with a linked project or dashboard project id.
 *
 * First-time local deploy: run `npx vercel link --scope <your-team-slug>` once so `.vercel/project.json` exists.
 */
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const cwd = process.cwd();
const linked = fs.existsSync(path.join(cwd, ".vercel", "project.json"));
const token = (process.env.VERCEL_TOKEN ?? "").trim();
if (!linked && !token) {
  console.error(
    "Vercel: missing .vercel/project.json and no VERCEL_TOKEN.\n" +
      "  Run once from repo root:  npx vercel link --scope <team-slug>\n" +
      "  Or set VERCEL_TOKEN (CI) and ensure the project is linked / env vars are set in Vercel.\n" +
      "  Optional: VERCEL_SCOPE=<team-slug> for explicit --scope on each deploy.",
  );
  process.exit(1);
}

const scope = (process.env.VERCEL_SCOPE ?? process.env.VERCEL_TEAM ?? "").trim();
const args = ["vercel", "deploy", "--prod", "--yes"];
if (scope) {
  args.push("--scope", scope);
}
if (token) {
  args.push("--token", token);
}

const r = spawnSync("npx", args, {
  stdio: "inherit",
  env: process.env,
  cwd,
  shell: true,
});

process.exit(typeof r.status === "number" ? r.status : 1);
