#!/usr/bin/env node
/**
 * Generate Tauri updater latest.json from a GitHub release.
 * Usage: GITHUB_TOKEN=xxx node scripts/studio-desktop/generate-update-manifest.js <tag> <repo> [--out=path]
 */
const tag = process.argv[2];
const repo = process.argv[3];
const outFile = process.argv.find((a) => a.startsWith("--out="))?.slice(6);
const token = process.env.GITHUB_TOKEN;

if (!tag || !repo || !token) {
  console.error(
    "Usage: GITHUB_TOKEN=xxx node scripts/studio-desktop/generate-update-manifest.js <tag> <repo> [--out=path]",
  );
  process.exit(1);
}

const version = tag.replace(/^studio-desktop-v/i, "").replace(/^v/i, "");
const base = `https://api.github.com/repos/${repo}/releases`;

async function main() {
  const res = await fetch(`${base}/tags/${tag}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
    },
  });
  if (!res.ok) {
    console.error("Failed to fetch release:", res.status, await res.text());
    process.exit(1);
  }
  const release = await res.json();
  const assets = release.assets || [];
  const downloadBase = `https://github.com/${repo}/releases/download/${tag}`;

  const findAsset = (pred) => assets.find((a) => pred(a.name));
  const getSigContent = async (name) => {
    const a = findAsset((n) => n === name || n === `${name}.sig`);
    if (!a) return null;
    const r = await fetch(a.url, {
      headers: { Authorization: `Bearer ${token}`, Accept: "application/octet-stream" },
    });
    if (!r.ok) return null;
    return (await r.text()).trim();
  };

  const platforms = {};

  const winZip = findAsset((n) => n.endsWith(".nsis.zip") && !n.endsWith(".sig"));
  const winSig = findAsset((n) => n.endsWith(".nsis.zip.sig"));
  if (winZip && winSig) {
    const sig = await getSigContent(winSig.name);
    if (sig) {
      platforms["windows-x86_64"] = {
        signature: sig,
        url: `${downloadBase}/${winZip.name}`,
      };
    }
  }

  const macTgzAssets = assets.filter((a) => a.name.includes(".app.tar.gz") && !a.name.endsWith(".sig"));
  for (const macTgz of macTgzAssets) {
    const sigAsset = assets.find((a) => a.name === `${macTgz.name}.sig`);
    if (!sigAsset) continue;
    const sig = await getSigContent(sigAsset.name);
    if (sig) {
      const key = macTgz.name.includes("aarch64") ? "darwin-aarch64" : "darwin-x86_64";
      platforms[key] = { signature: sig, url: `${downloadBase}/${macTgz.name}` };
    }
  }

  const linuxTgz = findAsset((n) => n.includes("AppImage.tar.gz") && !n.endsWith(".sig"));
  const linuxSig = findAsset((n) => n.includes("AppImage.tar.gz.sig"));
  if (linuxTgz && linuxSig) {
    const sig = await getSigContent(linuxSig.name);
    if (sig) {
      platforms["linux-x86_64"] = { signature: sig, url: `${downloadBase}/${linuxTgz.name}` };
    }
  }

  if (Object.keys(platforms).length === 0) {
    console.warn(
      "No signed update bundles found. Set TAURI_PRIVATE_KEY in CI to enable auto-updates.",
    );
  }

  const manifest = {
    version,
    notes: release.body || `Immersive Studio ${version}`,
    pub_date: release.published_at || new Date().toISOString(),
    platforms,
  };

  const json = JSON.stringify(manifest, null, 2);
  if (outFile) {
    const fs = await import("fs");
    fs.writeFileSync(outFile, json);
    console.error("Wrote", outFile);
  } else {
    console.log(json);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
