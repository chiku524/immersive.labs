#!/usr/bin/env node
/**
 * Generate Tauri updater latest.json from a GitHub release.
 * Usage: GITHUB_TOKEN=xxx node scripts/studio-desktop/generate-update-manifest.js <tag> <repo> [--out=path]
 *
 * Platform keys match tauri-plugin-updater 2.x lookup order:
 *   Windows NSIS: windows-x86_64-nsis, then windows-x86_64
 *   Windows MSI:  windows-x86_64-msi, then windows-x86_64
 */
const tag = process.argv[2];
const repo = process.argv[3];
const outFile = process.argv.find((a) => a.startsWith("--out="))?.slice(6);
const token = process.env.GITHUB_TOKEN;
const strict = process.argv.includes("--strict");

if (!tag || !repo || !token) {
  console.error(
    "Usage: GITHUB_TOKEN=xxx node scripts/studio-desktop/generate-update-manifest.js <tag> <repo> [--out=path] [--strict]",
  );
  process.exit(1);
}

const version = tag.replace(/^studio-desktop-v/i, "").replace(/^v/i, "");
const base = `https://api.github.com/repos/${repo}/releases`;

function encodeAssetName(name) {
  return name.replace(/ /g, "%20");
}

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

  const getSigContent = async (sigAsset) => {
    if (!sigAsset) return null;
    const urls = [sigAsset.browser_download_url, sigAsset.url].filter(Boolean);
    for (const url of urls) {
      const r = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: url.includes("api.github.com") ? "application/octet-stream" : "*/*",
        },
      });
      if (!r.ok) continue;
      const text = (await r.text()).trim();
      if (text) return text;
    }
    console.error(`Failed to read signature for ${sigAsset.name}`);
    return null;
  };

  const platforms = {};

  const addPlatform = (key, bundleAsset, sigAsset) => {
    if (!bundleAsset || !sigAsset) return;
    if (platforms[key]) return;
    return getSigContent(sigAsset).then((sig) => {
      if (!sig) {
        console.error(`Missing signature content for ${key} (${sigAsset.name})`);
        return;
      }
      platforms[key] = {
        signature: sig,
        url: `${downloadBase}/${encodeAssetName(bundleAsset.name)}`,
      };
    });
  };

  const tasks = [];

  const winNsisZip = findAsset((n) => n.endsWith(".nsis.zip") && !n.endsWith(".sig"));
  const winNsisSig = findAsset((n) => n.endsWith(".nsis.zip.sig"));
  if (winNsisZip && winNsisSig) {
    const entry = { signature: null, url: `${downloadBase}/${encodeAssetName(winNsisZip.name)}` };
    tasks.push(
      getSigContent(winNsisSig).then((sig) => {
        if (!sig) {
          console.error("Missing Windows NSIS signature");
          return;
        }
        entry.signature = sig;
        // Tauri 2 NSIS updater checks windows-x86_64-nsis first, then windows-x86_64.
        platforms["windows-x86_64-nsis"] = { ...entry };
        platforms["windows-x86_64"] = { ...entry };
      }),
    );
  }

  const winMsiZip = findAsset((n) => n.endsWith(".msi.zip") && !n.endsWith(".sig"));
  const winMsiSig = findAsset((n) => n.endsWith(".msi.zip.sig"));
  tasks.push(addPlatform("windows-x86_64-msi", winMsiZip, winMsiSig));

  await Promise.all(tasks);

  // Newer Tauri CLI signs the installers directly (no *.nsis.zip / *.msi.zip on disk).
  if (!platforms["windows-x86_64"]) {
    const winExe = findAsset(
      (n) => /x64-setup\.exe$/i.test(n) && !n.endsWith(".sig") && !n.includes(".nsis.zip"),
    );
    const winExeSig = findAsset((n) => /x64-setup\.exe\.sig$/i.test(n));
    await addPlatform("windows-x86_64-nsis", winExe, winExeSig);
    if (platforms["windows-x86_64-nsis"]) {
      platforms["windows-x86_64"] = { ...platforms["windows-x86_64-nsis"] };
    }
  }
  if (!platforms["windows-x86_64-msi"]) {
    const winMsi = findAsset(
      (n) => /\.msi$/i.test(n) && !n.endsWith(".sig") && !n.endsWith(".zip"),
    );
    const winMsiInstallerSig = findAsset((n) => /\.msi\.sig$/i.test(n) && !n.includes(".zip"));
    await addPlatform("windows-x86_64-msi", winMsi, winMsiInstallerSig);
  }

  const macTgzAssets = assets.filter((a) => a.name.includes(".app.tar.gz") && !a.name.endsWith(".sig"));
  for (const macTgz of macTgzAssets) {
    const sigAsset = assets.find((a) => a.name === `${macTgz.name}.sig`);
    if (!sigAsset) continue;
    const sig = await getSigContent(sigAsset);
    if (sig) {
      const key = macTgz.name.includes("aarch64") ? "darwin-aarch64" : "darwin-x86_64";
      platforms[key] = {
        signature: sig,
        url: `${downloadBase}/${encodeAssetName(macTgz.name)}`,
      };
    }
  }

  const linuxTgz = findAsset((n) => n.includes("AppImage.tar.gz") && !n.endsWith(".sig"));
  const linuxSig = findAsset((n) => n.includes("AppImage.tar.gz.sig"));
  if (linuxTgz && linuxSig) {
    const sig = await getSigContent(linuxSig);
    if (sig) {
      platforms["linux-x86_64"] = {
        signature: sig,
        url: `${downloadBase}/${encodeAssetName(linuxTgz.name)}`,
      };
    }
  }

  const platformKeys = Object.keys(platforms);
  if (platformKeys.length === 0) {
    const msg =
      "No signed update bundles found in release assets. Set TAURI_PRIVATE_KEY in CI and ensure .nsis.zip.sig assets exist.";
    if (strict || process.env.CI) {
      console.error(msg);
      process.exit(1);
    }
    console.warn(msg);
  } else {
    console.error(`Platforms: ${platformKeys.join(", ")}`);
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
