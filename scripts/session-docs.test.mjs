// Agents read these files at the start of every session. Keep them short so
// process can't quietly grow back (D-0018), and keep their links working.
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const BUDGET = {
  "AGENTS.md": 1000,
  "CLAUDE.md": 100,
  "docs/VERIFICATION_POLICY.md": 200,
  ".agents/skills/vera-roadmap-coordination/SKILL.md": 300,
};
const TOTAL_BUDGET = 1500;

const words = (file) => readFileSync(path.join(root, file), "utf8").split(/\s+/).filter(Boolean).length;

test("session docs stay within their word budget", () => {
  let total = 0;
  for (const [file, limit] of Object.entries(BUDGET)) {
    const count = words(file);
    total += count;
    assert.ok(count <= limit, `${file} has ${count} words (budget ${limit}). Cut something before adding.`);
  }
  assert.ok(total <= TOTAL_BUDGET, `Session docs total ${total} words (budget ${TOTAL_BUDGET}).`);
});

test("session doc links point at files that exist", () => {
  for (const file of Object.keys(BUDGET)) {
    const text = readFileSync(path.join(root, file), "utf8");
    for (const [, target] of text.matchAll(/\]\(([^)#\s]+)(?:#[^)]*)?\)/g)) {
      if (/^[a-z]+:/i.test(target)) continue;
      assert.ok(existsSync(path.resolve(path.dirname(path.join(root, file)), target)), `${file} links to missing ${target}`);
    }
  }
});
