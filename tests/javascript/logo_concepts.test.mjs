import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const html = await readFile(resolve(repositoryRoot, "docs/logo-concepts.html"), "utf8");

test("logo review board offers six distinct selectable SVG directions", () => {
  const symbols = [...html.matchAll(/<symbol id="logo-([a-f])"/g)].map((match) => match[1]);
  const cards = [...html.matchAll(/data-logo="([a-f])"/g)].map((match) => match[1]);

  assert.deepEqual(symbols, ["a", "b", "c", "d", "e", "f"]);
  assert.deepEqual(cards, ["a", "b", "c", "d", "e", "f"]);
  assert.equal(new Set(cards).size, 6);
});

test("logo review board explains the decision and remains responsive", () => {
  assert.match(html, /连通、交互/);
  assert.match(html, /看得见的驿站/);
  assert.match(html, /如意云纹/);
  assert.match(html, /窗棂/);
  assert.match(html, /数字驿亭/);
  assert.match(html, /@media \(max-width: 620px\)/);
  assert.match(html, /aria-pressed="true"/);
  assert.match(html, /prefers-reduced-motion/);
  assert.match(html, /本地设计评审 · 未替换正式 Logo/);
});
