// Checks the static website: every page's local links, scripts, styles and
// images exist, manifests parse, and their icons exist. Used by CI.
//   node scripts/check_website.mjs apps/website
import { readFileSync, existsSync, readdirSync, statSync } from "node:fs";
import { join, dirname, resolve } from "node:path";

const root = resolve(process.argv[2] || "apps/website");
const errors = [];
const pages = [];
const walk = dir => {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p);
    else if (name.endsWith(".html")) pages.push(p);
  }
};
walk(root);

// Files that are uploaded at deploy time rather than committed.
const deployOnly = [/^\/downloads\/.+\.apk$/];

const target = (page, ref) => {
  const clean = ref.split("#")[0].split("?")[0];
  if (!clean) return null;
  let p = clean.startsWith("/") ? join(root, clean) : join(dirname(page), clean);
  if (clean.endsWith("/")) p = join(p, "index.html");
  return p;
};

for (const page of pages) {
  const html = readFileSync(page, "utf8");
  if (!/<title>[^<]+<\/title>/.test(html)) errors.push(`${page}: missing <title>`);
  for (const [, ref] of html.matchAll(/(?:href|src)="([^"]+)"/g)) {
    if (/^(https?:|mailto:|data:|#|javascript:)/.test(ref) || ref.includes("${")) continue;
    const rel = "/" + resolve(target(page, ref) || page).slice(root.length + 1);
    if (deployOnly.some(r => r.test(rel))) continue;
    const p = target(page, ref);
    if (p && !existsSync(p)) errors.push(`${page}: broken link ${ref}`);
  }
  for (const [, id] of html.matchAll(/href="#([^"]+)"/g)) {
    if (!html.includes(`id="${id}"`)) errors.push(`${page}: missing anchor #${id}`);
  }
}

for (const m of ["app/app-mobile/manifest.webmanifest", "app/app-desktop/manifest.webmanifest"]) {
  const p = join(root, m);
  try {
    const json = JSON.parse(readFileSync(p, "utf8"));
    for (const icon of json.icons || []) if (!existsSync(join(root, icon.src))) errors.push(`${m}: missing icon ${icon.src}`);
  } catch (e) {
    errors.push(`${m}: ${e.message}`);
  }
}
try { JSON.parse(readFileSync(join(root, "vercel.json"), "utf8")); } catch (e) { errors.push(`vercel.json: ${e.message}`); }

if (errors.length) {
  for (const e of errors) console.error("✗ " + e);
  process.exit(1);
}
console.log(`✓ ${pages.length} pages checked: links, assets, anchors and manifests OK`);
