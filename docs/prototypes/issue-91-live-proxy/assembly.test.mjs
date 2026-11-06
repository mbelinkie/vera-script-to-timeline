import assert from "node:assert/strict";
import test from "node:test";
import { assemble, cases, position } from "./assembly.mjs";

test("partial replacement uses independent source offsets and exact join ownership", () => {
  assert.deepEqual(position(cases.partial, 3), { index: 1, sourceTime: 2, time: 3 });
  assert.deepEqual(position(cases.partial, 5), { index: 2, sourceTime: 4, time: 5 });
  assert.deepEqual(position(cases.partial, 8), { index: 2, sourceTime: 7, time: 8 });
  assert.deepEqual(position(cases.partial, -1), { index: 0, sourceTime: 1, time: 0 });
});
test("same-source discontinuities map to the new offset rather than continuing playback", () => {
  assert.equal(position(cases.distant, 2).sourceTime, 8);
  assert.equal(position(cases.distant, 4).sourceTime, 3);
  assert.throws(() => assemble([{ source: "a", in: 4, out: 1, framing: "wide" }]));
  assert.throws(() => position([], 0));
});
