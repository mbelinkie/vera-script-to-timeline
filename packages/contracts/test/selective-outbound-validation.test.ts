import { expect, it } from "vitest";
import {
  executeOutbound, freezeOutbound, loadOutbound, selectOutbound, startOutbound,
  type OutboundAdapter, type OutboundAttempt, type OutboundChange,
} from "../src/selective-outbound.ts";

const changes: OutboundChange[] = [{ id: "one", order: 0, kind: "cut", blocked: null, edits: [{ record: 24 }] }];
function initial(): OutboundAttempt {
  return startOutbound(freezeOutbound(changes, selectOutbound(changes, "safe"), { source: "revision", target: "copy", baseline: "before" }));
}
it("rejects a non-string semantic identity from decoded input", () => {
  const decoded = [{ ...changes[0]!, id: 7 }] as unknown as OutboundChange[];
  expect(() => selectOutbound(decoded, "safe")).toThrow();
});
it("rejects a non-string target fingerprint from decoded context", () => {
  expect(() => freezeOutbound(changes, selectOutbound(changes, "safe"), {
    source: "revision", target: "copy", baseline: 7 as unknown as string,
  })).toThrow();
});
it("rejects a saved no-op receipt claiming that a selected change verified", () => {
  const attempt = initial();
  const claimed = { ...attempt, completed: true, outcomes: [{ change: "one", status: "verified", error: null,
    receipt: { plan: attempt.plan.hash, change: "one", target: "copy", before: "before", after: "before" } }] };
  expect(() => loadOutbound(JSON.stringify(claimed))).toThrow(/receipt/i);
});
it("rejects a saved non-text error payload", () => {
  const attempt = initial();
  const invalid = { ...attempt, outcomes: [{ ...attempt.outcomes[0]!, error: { message: "malformed" } }] };
  expect(() => loadOutbound(JSON.stringify(invalid))).toThrow(/outcome/i);
});
it("independently reverifies even a structurally valid saved completion", async () => {
  const attempt = initial();
  const claimed = loadOutbound(JSON.stringify({ ...attempt, completed: true, current: "after", baseline: "after",
    outcomes: [{ change: "one", status: "verified", error: null, receipt: {
      plan: attempt.plan.hash, change: "one", target: "copy", before: "before", after: "after",
    } }] }));
  let applyCount = 0;
  let verifyCount = 0;
  const adapter: OutboundAdapter = {
    observe: () => Promise.resolve({ source: "revision", target: "copy", fingerprint: "after" }),
    apply: () => { applyCount++; return Promise.reject(new Error("Unexpected apply")); },
    verify: () => { verifyCount++; return Promise.resolve(false); },
    reconcile: () => Promise.resolve("unknown"),
  };
  await expect(executeOutbound({
    exclusive: (work) => work(), load: () => Promise.resolve(claimed),
    save: () => Promise.reject(new Error("Unexpected save")),
  }, adapter)).rejects.toThrow();
  expect(verifyCount).toBe(1);
  expect(applyCount).toBe(0);
});
