import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { loadOutbound, outboundCounts } from "../src/selective-outbound.ts";

// Written by the Python changed-rows update (#104); see tests/test_update_timeline_cli.py.
const saved = readFileSync(new URL("./fixtures/timeline-update-attempt.json", import.meta.url), "utf8");

it("loads the Python timeline update record as a completed #328 attempt", () => {
  const attempt = loadOutbound(saved);
  expect(attempt.completed).toBe(true);
  expect(outboundCounts(attempt.plan)).toEqual({ selected: 1, skipped: 0, blocked: 1 });
  expect(attempt.outcomes.map((outcome) => outcome.status)).toEqual(["verified", "blocked"]);
  expect(attempt.baseline).toBe(attempt.outcomes[0]!.receipt!.after);
});
