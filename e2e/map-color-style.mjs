// E2E test: per-feature color on the map.
//
// Bug: features with different `properties.color` (NL outline gold, provinces
// purple, cities red) all render in OL's hard-coded default blue. This test
// fails until the vector layer is given a per-feature style that reads
// `properties.color`.
//
// Verification is via the layer's style function (reliable) plus a screenshot
// for visual confirmation.

import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { strict as assert } from "node:assert";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const EMAIL = `e2e-color-${Date.now()}@example.test`;
const PASSWORD = "test-password-1234";
const SCREENSHOT_DIR = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "screenshots",
);

function normalizeColor(c) {
  if (typeof c !== "string") return null;
  const trimmed = c.trim();
  if (/^#[0-9a-fA-F]{6}$/.test(trimmed)) return trimmed.toLowerCase();
  return trimmed;
}

async function registerUser(request) {
  const response = await request.post(`${BASE}/api/auth/register/`, {
    data: { email: EMAIL, password: PASSWORD, password_confirm: PASSWORD },
  });
  assert.equal(response.status(), 201, `register failed: ${response.status()}`);
}

async function loginUser(request) {
  const response = await request.post(`${BASE}/api/auth/login/`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  assert.equal(response.status(), 200, `login failed: ${response.status()}`);
  return response.json();
}

async function readFeatureStyles(page) {
  return page.evaluate(() => {
    const mapState = window.__geojsonMap;
    if (!mapState?.map || !mapState.source) return null;
    const layers = mapState.map.getLayers().getArray();
    const vectorLayer = layers.find(
      (candidate) => candidate.getSource && candidate.getSource() === mapState.source,
    );
    if (!vectorLayer) return null;
    return mapState.source.getFeatures().map((feature) => {
      const styleLike = vectorLayer.getStyleFunction()(feature, 0);
      const styles = Array.isArray(styleLike) ? styleLike : [styleLike];
      const primary = styles[0] || null;
      const props = feature.get("properties") || {};
      return {
        name: props.name ?? null,
        category: props.category ?? null,
        expected_color: props.color ?? null,
        stroke_color: primary?.getStroke()?.getColor() ?? null,
        fill_color: primary?.getFill()?.getColor() ?? null,
      };
    });
  });
}

async function main() {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();
  const request = context.request;

  await registerUser(request);
  const { access, refresh } = await loginUser(request);

  await page.addInitScript(
    ({ accessToken, refreshToken }) => {
      localStorage.setItem("access", accessToken);
      localStorage.setItem("refresh", refreshToken);
    },
    { accessToken: access, refreshToken: refresh },
  );

  await page.goto(`${BASE}/map/`, { waitUntil: "networkidle" });
  await page.waitForFunction(
    () => window.__geojsonMap?.source?.getFeatures().length > 0,
    { timeout: 15000 },
  );

  const styleData = await readFeatureStyles(page);
  assert.ok(Array.isArray(styleData) && styleData.length > 0, "no features loaded on the map");

  const mismatches = styleData
    .map((entry) => ({
      ...entry,
      expected: normalizeColor(entry.expected_color),
      got: normalizeColor(entry.stroke_color),
    }))
    .filter((entry) => entry.expected && entry.got !== entry.expected);

  if (mismatches.length > 0) {
    const summary = mismatches
      .map((m) => `  ${m.name} (${m.category}): expected=${m.expected}, got=${m.got}`)
      .join("\n");
    throw new Error(
      `${mismatches.length}/${styleData.length} features render with the wrong stroke color:\n${summary}`,
    );
  }

  await mkdir(SCREENSHOT_DIR, { recursive: true });
  await page.screenshot({ path: resolve(SCREENSHOT_DIR, "map.png"), fullPage: true });
  await page.locator("#map").screenshot({ path: resolve(SCREENSHOT_DIR, "map-canvas.png") });

  await browser.close();
  console.log(
    `OK: ${styleData.length} features rendered; every stroke color matches properties.color.`,
  );
  console.log(`Screenshot: ${resolve(SCREENSHOT_DIR, "map.png")}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
