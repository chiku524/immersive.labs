#!/usr/bin/env node
/**
 * Align Immersive Studio desktop version with a release tag (studio-desktop-v0.1.2 → 0.1.2).
 *
 * Usage: node scripts/studio-desktop/set-version-from-tag.cjs studio-desktop-v0.1.2
 */
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "../..");

let raw = process.argv[2] || process.env.VERSION || process.env.GITHUB_REF || "";
if (raw.startsWith("refs/tags/")) raw = raw.slice("refs/tags/".length);
const tag = raw.replace(/^studio-desktop-v/i, "").replace(/^v/i, "");

if (!tag || !/^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?$/.test(tag)) {
  console.error("Usage: node scripts/studio-desktop/set-version-from-tag.cjs studio-desktop-v0.1.2");
  process.exit(1);
}

const releaseTag = raw.startsWith("studio-desktop-") ? raw : `studio-desktop-v${tag}`;

function patchJson(file, mutator) {
  const data = JSON.parse(fs.readFileSync(file, "utf8"));
  mutator(data);
  fs.writeFileSync(file, `${JSON.stringify(data, null, 2)}\n`);
}

patchJson(path.join(root, "apps/studio-desktop/package.json"), (d) => {
  d.version = tag;
});
console.log("Set apps/studio-desktop/package.json version to", tag);

const tauriConfPath = path.join(root, "apps/studio-desktop/src-tauri/tauri.conf.json");
const tauriConf = JSON.parse(fs.readFileSync(tauriConfPath, "utf8"));
tauriConf.version = tag;
delete tauriConf.package;
fs.writeFileSync(tauriConfPath, `${JSON.stringify(tauriConf, null, 2)}\n`);
console.log("Set tauri.conf.json version to", tag);

const cargoPath = path.join(root, "apps/studio-desktop/src-tauri/Cargo.toml");
let cargo = fs.readFileSync(cargoPath, "utf8");
cargo = cargo.replace(/^version = ".*"$/m, `version = "${tag}"`);
fs.writeFileSync(cargoPath, cargo);
console.log("Set Cargo.toml version to", tag);

const downloadTs = path.join(root, "apps/web/src/studioDesktopDownload.ts");
let downloadSrc = fs.readFileSync(downloadTs, "utf8");
downloadSrc = downloadSrc.replace(
  /export const STUDIO_DESKTOP_RELEASE_TAG = "[^"]+";/,
  `export const STUDIO_DESKTOP_RELEASE_TAG = "${releaseTag}";`,
);
downloadSrc = downloadSrc.replace(
  /export const STUDIO_DESKTOP_VERSION = "[^"]+";/,
  `export const STUDIO_DESKTOP_VERSION = "${tag}";`,
);
fs.writeFileSync(downloadTs, downloadSrc);
console.log("Set studioDesktopDownload.ts to", releaseTag, tag);

const vercelPath = path.join(root, "vercel.json");
const vercel = JSON.parse(fs.readFileSync(vercelPath, "utf8"));
for (const rule of vercel.rewrites || []) {
  if (rule.source === "/downloads/desktop/(.*)" && rule.destination) {
    rule.destination = `https://github.com/chiku524/immersive.labs/releases/download/${releaseTag}/$1`;
  }
}
fs.writeFileSync(vercelPath, `${JSON.stringify(vercel, null, 2)}\n`);
console.log("Set vercel.json desktop proxy to", releaseTag);
