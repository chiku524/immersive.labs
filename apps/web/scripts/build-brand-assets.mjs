/**
 * Regenerate logo/icon/social PNGs from the master brand artwork.
 *
 * Source: public/use this.png  (your reference: squircle, glow, mark)
 * Also writes public/brand-mark.png (stable URL for <img> and JSON-LD).
 *
 * Run: npm run build:brand-assets -w @immersive/web
 *
 * Slogan type: Comfortaa from public/fonts/Comfortaa-VariableFont_wght.ttf (embedded in SVG).
 */
import { existsSync, readFileSync } from "node:fs";
import { mkdir, rename, stat } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const __dirname = dirname(fileURLToPath(import.meta.url));
const publicDir = join(__dirname, "../public");
/** Master reference file (filename from your upload). */
const BRAND_SOURCE = join(publicDir, "use this.png");
const COMFORTAA_PATH = join(publicDir, "fonts/Comfortaa-VariableFont_wght.ttf");

const SLOGAN_PRIMARY = "Immersive Labs";
const SLOGAN_SECONDARY = "Clarity, motion & craft.";

const pngOpts = {
  compressionLevel: 9,
  effort: 10,
};

/** @typedef {"og" | "twitter" | "square"} TrailVariant */

/**
 * Near-black canvas (#06080c) plus one continuous abstract stroke per variant.
 * Each export size uses a different route (entry angle + loops) so OG / banner / square don’t look identical.
 */
function engravedTrailBackdropSvg(width, height, variant) {
  const w = width;
  const h = height;
  const sw = Math.max(1.4, Math.min(w, h) * 0.002);
  const d = engravedTrailPathD(w, h, variant);
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
  <rect width="${w}" height="${h}" fill="#06080c"/>
  <path d="${d}" fill="none" stroke="rgba(0,0,0,0.48)" stroke-width="${sw * 3.1}" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="${d}" fill="none" stroke="rgba(150,168,195,0.32)" stroke-width="${sw * 1.45}" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`;
}

function xy(w, h) {
  return {
    x: (t) => t * w,
    y: (t) => t * h,
  };
}

/** Open Graph (~1.91:1): enters lower-left, loops across, exits upper-right. */
function trailPathOg(w, h) {
  const { x, y } = xy(w, h);
  return [
    `M ${x(0.015)} ${y(0.9)}`,
    `C ${x(0.08)} ${y(0.55)}, ${x(0.14)} ${y(0.12)}, ${x(0.24)} ${y(0.22)}`,
    `C ${x(0.32)} ${y(0.3)}, ${x(0.38)} ${y(0.72)}, ${x(0.46)} ${y(0.82)}`,
    `C ${x(0.52)} ${y(0.9)}, ${x(0.56)} ${y(0.38)}, ${x(0.62)} ${y(0.18)}`,
    `C ${x(0.68)} ${y(0.05)}, ${x(0.72)} ${y(0.42)}, ${x(0.78)} ${y(0.62)}`,
    `C ${x(0.82)} ${y(0.78)}, ${x(0.86)} ${y(0.88)}, ${x(0.9)} ${y(0.52)}`,
    `C ${x(0.93)} ${y(0.28)}, ${x(0.96)} ${y(0.2)}, ${x(0.985)} ${y(0.35)}`,
  ].join(" ");
}

/** Ultra-wide banner: enters from top edge (right-of-center), dives and snakes, fades toward upper-right. */
function trailPathTwitter(w, h) {
  const { x, y } = xy(w, h);
  return [
    `M ${x(0.82)} ${y(0.03)}`,
    `C ${x(0.58)} ${y(0.14)}, ${x(0.32)} ${y(0.06)}, ${x(0.14)} ${y(0.28)}`,
    `C ${x(0.04)} ${y(0.42)}, ${x(0.08)} ${y(0.68)}, ${x(0.22)} ${y(0.82)}`,
    `C ${x(0.38)} ${y(0.95)}, ${x(0.58)} ${y(0.88)}, ${x(0.72)} ${y(0.62)}`,
    `C ${x(0.84)} ${y(0.42)}, ${x(0.88)} ${y(0.22)}, ${x(0.92)} ${y(0.12)}`,
    `C ${x(0.96)} ${y(0.05)}, ${x(0.98)} ${y(0.12)}, ${x(0.99)} ${y(0.28)}`,
  ].join(" ");
}

/**
 * Square profile (512): elongated zig-zag — long diagonal legs, shallow bends,
 * less “orbiting” / circular than prior passes (reads more like a meander across the tile).
 */
function trailPathSquare(w, h) {
  const { x, y } = xy(w, h);
  return [
    `M ${x(0.04)} ${y(0.88)}`,
    `C ${x(0.28)} ${y(0.78)}, ${x(0.48)} ${y(0.48)}, ${x(0.64)} ${y(0.28)}`,
    `C ${x(0.78)} ${y(0.12)}, ${x(0.9)} ${y(0.06)}, ${x(0.96)} ${y(0.16)}`,
    `C ${x(0.99)} ${y(0.24)}, ${x(0.92)} ${y(0.38)}, ${x(0.72)} ${y(0.46)}`,
    `C ${x(0.48)} ${y(0.56)}, ${x(0.22)} ${y(0.62)}, ${x(0.08)} ${y(0.72)}`,
    `C ${x(0.02)} ${y(0.78)}, ${x(0.06)} ${y(0.92)}, ${x(0.26)} ${y(0.96)}`,
    `C ${x(0.5)} ${y(0.97)}, ${x(0.74)} ${y(0.88)}, ${x(0.9)} ${y(0.66)}`,
    `C ${x(0.98)} ${y(0.52)}, ${x(0.98)} ${y(0.32)}, ${x(0.88)} ${y(0.2)}`,
  ].join(" ");
}

function engravedTrailPathD(w, h, variant) {
  switch (variant) {
    case "twitter":
      return trailPathTwitter(w, h);
    case "square":
      return trailPathSquare(w, h);
    case "og":
    default:
      return trailPathOg(w, h);
  }
}

async function backdropPng(w, h, variant) {
  return sharp(Buffer.from(engravedTrailBackdropSvg(w, h, variant))).png(pngOpts).toBuffer();
}

async function markBuffer(size) {
  return sharp(BRAND_SOURCE).resize(size, size, { fit: "contain", kernel: sharp.kernel.lanczos3 }).png(pngOpts).toBuffer();
}

function escapeXml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

let comfortaaDefsCache;

/** Embeds Comfortaa TTF as data URI so Sharp’s SVG rasterizer can use it. */
function comfortaaFontDefs() {
  if (comfortaaDefsCache !== undefined) {
    return comfortaaDefsCache;
  }
  if (!existsSync(COMFORTAA_PATH)) {
    console.warn(
      `Comfortaa not found at ${COMFORTAA_PATH} — add Comfortaa-VariableFont_wght.ttf under public/fonts/ (see Google Fonts).`,
    );
    comfortaaDefsCache = "";
    return comfortaaDefsCache;
  }
  const b64 = readFileSync(COMFORTAA_PATH).toString("base64");
  comfortaaDefsCache = `<defs><style type="text/css"><![CDATA[
@font-face{font-family:'Comfortaa';font-style:normal;font-weight:300 700;src:url(data:font/ttf;base64,${b64}) format('truetype');}
]]></style></defs>`;
  return comfortaaDefsCache;
}

function sloganFontFamilyAttr() {
  return existsSync(COMFORTAA_PATH)
    ? "Comfortaa, system-ui, sans-serif"
    : "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
}

function sloganLayerSvg(width, height, primary, secondary, style) {
  const { primaryY, secondaryY, textX, primarySize, secondarySize, anchor } = style;
  const anchorAttr = anchor === "middle" ? `text-anchor="middle"` : `text-anchor="start"`;
  const defs = comfortaaFontDefs();
  const ff = sloganFontFamilyAttr();
  return Buffer.from(
    `<svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
${defs}
  <text x="${textX}" y="${primaryY}" ${anchorAttr} fill="#f0f4fa" font-family="${ff}" font-size="${primarySize}" font-weight="600">${escapeXml(primary)}</text>
  <text x="${textX}" y="${secondaryY}" ${anchorAttr} fill="#a8b4c8" font-family="${ff}" font-size="${secondarySize}" font-weight="500">${escapeXml(secondary)}</text>
</svg>`,
  );
}

async function writePng(buffer, outPath) {
  const tmp = `${outPath}.tmp.png`;
  await sharp(buffer).png(pngOpts).toFile(tmp);
  await rename(tmp, outPath);
}

async function main() {
  if (!existsSync(BRAND_SOURCE)) {
    console.error(
      `Missing brand source: ${BRAND_SOURCE}\nPlace your reference PNG there (e.g. "use this.png") and re-run.`,
    );
    process.exit(1);
  }

  await mkdir(join(publicDir, "social"), { recursive: true });
  await mkdir(join(publicDir, "billing"), { recursive: true });

  const brandOptimized = await sharp(BRAND_SOURCE).png(pngOpts).toBuffer();
  await writePng(brandOptimized, join(publicDir, "brand-mark.png"));

  const fav32 = await markBuffer(32);
  await writePng(fav32, join(publicDir, "favicon.png"));

  const apple = await markBuffer(180);
  await writePng(apple, join(publicDir, "apple-touch-icon.png"));

  const stripe128 = await markBuffer(128);
  await writePng(stripe128, join(publicDir, "billing/stripe-icon-128.png"));

  const ogW = 1200;
  const ogH = 630;
  const ogMarkSize = 300;
  const ogBase = await backdropPng(ogW, ogH, "og");
  const markOg = await markBuffer(ogMarkSize);
  const markLeft = 72;
  const markTop = Math.floor((ogH - ogMarkSize) / 2);
  const textX = markLeft + ogMarkSize + 56;
  const sloganOg = await sharp(
    sloganLayerSvg(ogW, ogH, SLOGAN_PRIMARY, SLOGAN_SECONDARY, {
      textX,
      primaryY: Math.floor(ogH / 2) - 38,
      secondaryY: Math.floor(ogH / 2) + 56,
      primarySize: 72,
      secondarySize: 42,
      anchor: "start",
    }),
  )
    .png()
    .toBuffer();

  const ogBuf = await sharp(ogBase)
    .composite([
      { input: markOg, left: markLeft, top: markTop },
      { input: sloganOg, left: 0, top: 0 },
    ])
    .png(pngOpts)
    .toBuffer();
  await writePng(ogBuf, join(publicDir, "social/og-image.png"));

  const sq = 512;
  const markSq = 220;
  const profileBase = await backdropPng(sq, sq, "square");
  const markProfile = await markBuffer(markSq);
  const markSqLeft = Math.floor((sq - markSq) / 2);
  const markSqTop = 48;
  const sloganProfile = await sharp(
    sloganLayerSvg(sq, sq, SLOGAN_PRIMARY, SLOGAN_SECONDARY, {
      textX: sq / 2,
      primaryY: markSqTop + markSq + 66,
      secondaryY: markSqTop + markSq + 112,
      primarySize: 42,
      secondarySize: 26,
      anchor: "middle",
    }),
  )
    .png()
    .toBuffer();

  const profileBuf = await sharp(profileBase)
    .composite([
      { input: markProfile, left: markSqLeft, top: markSqTop },
      { input: sloganProfile, left: 0, top: 0 },
    ])
    .png(pngOpts)
    .toBuffer();
  await writePng(profileBuf, join(publicDir, "social/social-profile-512.png"));

  const twW = 1500;
  const twH = 500;
  const twMark = 220;
  const twBase = await backdropPng(twW, twH, "twitter");
  const markTw = await markBuffer(twMark);
  const twMarkLeft = 64;
  const twMarkTop = Math.floor((twH - twMark) / 2);
  const twTextX = twMarkLeft + twMark + 48;
  const sloganTw = await sharp(
    sloganLayerSvg(twW, twH, SLOGAN_PRIMARY, SLOGAN_SECONDARY, {
      textX: twTextX,
      primaryY: Math.floor(twH / 2) - 34,
      secondaryY: Math.floor(twH / 2) + 56,
      primarySize: 68,
      secondarySize: 40,
      anchor: "start",
    }),
  )
    .png()
    .toBuffer();

  const twBuf = await sharp(twBase)
    .composite([
      { input: markTw, left: twMarkLeft, top: twMarkTop },
      { input: sloganTw, left: 0, top: 0 },
    ])
    .png(pngOpts)
    .toBuffer();
  await writePng(twBuf, join(publicDir, "social/twitter-banner.png"));

  for (const name of ["stripe-product-indie", "stripe-product-team"]) {
    const p = join(publicDir, "billing", `${name}.png`);
    const out = await sharp(p)
      .resize(1024, 1024, { fit: "cover", position: "centre" })
      .png(pngOpts)
      .toBuffer();
    await writePng(out, p);
  }

  const appleBytes = (await stat(join(publicDir, "apple-touch-icon.png"))).size;
  console.log("Brand assets OK", {
    source: "public/use this.png",
    outputs: "brand-mark.png, favicon.png, apple-touch, social/*, billing/stripe-icon-128.png",
    appleTouch180: `${appleBytes} bytes`,
  });
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
