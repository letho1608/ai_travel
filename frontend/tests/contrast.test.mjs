import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";

const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

function hexToRgb(hex) {
  const h = hex.replace("#", "");
  if (h.length === 3) {
    return [
      parseInt(h[0] + h[0], 16),
      parseInt(h[1] + h[1], 16),
      parseInt(h[2] + h[2], 16),
    ];
  }
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ];
}

function luminance(hex) {
  const [r, g, b] = hexToRgb(hex).map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a, b) {
  const l1 = luminance(a);
  const l2 = luminance(b);
  const hi = Math.max(l1, l2);
  const lo = Math.min(l1, l2);
  return (hi + 0.05) / (lo + 0.05);
}

function parseVars(block) {
  const tokens = {};
  for (const m of block.matchAll(/--[\w-]+\s*:\s*[^;}]+/g)) {
    const parts = m[0].split(":");
    const name = parts[0];
    const value = parts.slice(1).join(":");
    tokens[name.replace(/\s+/g, "").replace(/^--/, "")] = value.trim();
  }
  return tokens;
}

function resolve(value, tokens, seen = new Set()) {
  value = value.trim().replace(/!important$/, "").trim();
  const m = value.match(/^var\(--([\w-]+)\)$/);
  if (!m) return value;
  const key = m[1];
  assert.ok(tokens[key], `token --${key} not found`);
  assert.ok(!seen.has(key), `circular var(--${key})`);
  seen.add(key);
  return resolve(tokens[key], tokens, seen);
}

function extractMediaDark() {
  const start = css.indexOf("@media(prefers-color-scheme:dark){:root{");
  if (start === -1) return "";
  let depth = 0;
  for (let i = start; i < css.length; i++) {
    if (css[i] === "{") depth++;
    if (css[i] === "}") {
      depth--;
      if (depth === 0) return css.slice(start + 1, i);
    }
  }
  return "";
}

const darkBlock = extractMediaDark();
assert.ok(darkBlock, "dark media block found");

const lightRoot = parseVars(css.slice(css.indexOf(":root{"), css.indexOf("}") + 1));
const darkRoot = parseVars(darkBlock.slice(darkBlock.indexOf(":root{"), darkBlock.indexOf("}") + 1));

function ruleDeclarations(scope, selector) {
  const re = new RegExp(escapeRegExp(selector) + "\\{([^}]*)\\}", "g");
  let m;
  const merged = {};
  while ((m = re.exec(scope)) !== null) {
    for (const decl of m[1].matchAll(/(?<prop>[a-zA-Z-]+):([^;}\s][^;}]*);?/g)) {
      merged[decl.groups.prop] = decl[2].trim();
    }
  }
  return merged;
}

function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function extractPair(scope, selector, tokens) {
  const merged = ruleDeclarations(scope, selector);
  assert.ok(merged.background, `background for ${selector} in scope`);
  const bg = resolve(merged.background, tokens);
  assert.ok(merged.color, `color for ${selector} in scope`);
  const color = resolve(merged.color, tokens);
  return { dbg: bg, dcolor: color };
}

const targets = [
  ".action-toast",
  ".itinerary-summary-badge",
  ".itinerary-regenerate",
  ".itinerary-summary-actions .primary",
  ".result-back-to-chat",
  ".result-ready-badge",
];

for (const sel of targets) {
  test(`contrast ≥ 4.5:1 for ${sel} (light + dark)`, () => {
    const light = extractPair(css.slice(0, css.indexOf("@media(prefers-color-scheme:dark){:root{")), sel, lightRoot);
    const dark = extractPair(darkBlock, sel, darkRoot);
    const lightBg = light.dbg.startsWith("#") ? light.dbg : "bg-not-resolved";
    const darkBg = dark.dbg.startsWith("#") ? dark.dbg : "bg-not-resolved";
    assert.ok(light.dbg.startsWith("#"), `light bg for ${sel} resolved, got ${light.dbg}`);
    assert.ok(dark.dbg.startsWith("#"), `dark bg for ${sel} resolved, got ${dark.dbg}`);
    const rLight = contrast(light.dcolor, lightBg);
    const rDark = contrast(dark.dcolor, darkBg);
    console.log(`  ${sel}: light ${rLight.toFixed(2)}:1  dark ${rDark.toFixed(2)}:1`);
    assert.ok(rLight >= 4.5, `light ${sel} contrast ${rLight.toFixed(2)}:1 < 4.5`);
    assert.ok(rDark >= 4.5, `dark ${sel} contrast ${rDark.toFixed(2)}:1 < 4.5`);
  });
}

test("globals.css has a single light :root block", () => {
  const outsideDark = css.slice(0, css.indexOf("@media(prefers-color-scheme:dark){:root{"));
  const roots = outsideDark.match(/:root\{/g);
  assert.deepEqual(roots, [":root{"], `expected one light :root, got ${roots?.length}`);
});