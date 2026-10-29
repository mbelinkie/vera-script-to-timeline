import { describe, expect, it } from "vitest";
import {
  executeOutbound,
  freezeOutbound,
  loadOutbound,
  outboundHash,
  selectOutbound,
  startOutbound,
  type OutboundAdapter,
  type OutboundAttempt,
  type OutboundChange,
  type OutboundStore,
  type Receipt,
} from "../src/selective-outbound.ts";

const changes: OutboundChange[] = [
  { id: "first", order: 0, kind: "cut", edits: [{ record: 1 }], blocked: null },
  { id: "last", order: 1, kind: "cut", edits: [{ record: 2 }], blocked: null },
];

type Effect = readonly Readonly<Record<string, string | number | boolean>>[];
type Identity = { source: string; target: string };
type Hooks = {
  failUncertainSave?: boolean;
  onApply?: (change: OutboundChange, effects: Record<string, Effect>) => void;
  onReconcile?: (change: OutboundChange, key: string) => Promise<Receipt | "not-applied" | "unknown">;
  onVerify?: (change: OutboundChange, call: number, identity: Identity) => void;
};

function execution() {
  const baseline = outboundHash({});
  const plan = freezeOutbound(changes, selectOutbound(changes, "safe"), {
    source: "source:1", target: "target:1", baseline,
  });
  let raw = JSON.stringify(startOutbound(plan));
  const effects: Record<string, Effect> = {};
  const identity = { source: "source:1", target: "target:1" };
  const hooks: Hooks = {};
  const applyCalls: string[] = [];
  const reconcileCalls: string[] = [];
  const verifyCalls: Array<{ change: string; valid: boolean }> = [];
  const verifyCounts = new Map<string, number>();
  const receipts = new Map<string, Receipt>();
  const store: OutboundStore = {
    exclusive: (work) => work(),
    load: () => Promise.resolve(loadOutbound(raw)),
    save: (attempt) => {
      const next = loadOutbound(JSON.stringify(attempt));
      if (hooks.failUncertainSave && next.outcomes.some((outcome) => outcome.status === "uncertain")) {
        return Promise.reject(new Error("uncertain marker persistence failed"));
      }
      raw = JSON.stringify(next);
      return Promise.resolve();
    },
  };
  const adapter: OutboundAdapter = {
    observe: () => Promise.resolve({ source: identity.source, target: identity.target, fingerprint: outboundHash(effects) }),
    apply: (change, key) => {
      applyCalls.push(change.id);
      const before = outboundHash(effects);
      effects[change.id] = structuredClone(change.edits);
      hooks.onApply?.(change, effects);
      const receipt: Receipt = {
        plan: plan.hash, change: change.id, target: identity.target, before, after: outboundHash(effects),
      };
      receipts.set(key, receipt);
      return Promise.resolve(receipt);
    },
    verify: (receipt, change) => {
      const call = (verifyCounts.get(change.id) ?? 0) + 1;
      verifyCounts.set(change.id, call);
      hooks.onVerify?.(change, call, identity);
      const valid = receipt.plan === plan.hash && receipt.change === change.id &&
        receipt.target === identity.target && JSON.stringify(effects[change.id]) === JSON.stringify(change.edits);
      verifyCalls.push({ change: change.id, valid });
      return Promise.resolve(valid);
    },
    reconcile: (change, key) => {
      reconcileCalls.push(change.id);
      return hooks.onReconcile?.(change, key) ?? Promise.resolve(receipts.get(key) ?? "not-applied");
    },
  };
  return {
    plan, store, adapter, effects, identity, hooks, applyCalls, reconcileCalls, verifyCalls,
    current: () => loadOutbound(raw),
    seed: (attempt: OutboundAttempt) => { raw = JSON.stringify(loadOutbound(JSON.stringify(attempt))); },
  };
}

describe("selective outbound recovery adversarial cases", () => {
  it("refuses a not-applied recovery answer when unrelated target content drifted", async () => {
    const fixture = execution();
    const saved = fixture.current();
    fixture.seed({ ...saved, outcomes: saved.outcomes.map((outcome, index) => index === 0 ? { ...outcome, status: "uncertain" } : outcome) });
    fixture.effects.external = [{ clip: "outside", frame: 99 }];
    fixture.hooks.onReconcile = () => Promise.resolve("not-applied");
    const before = fixture.current();

    await expect(executeOutbound(fixture.store, fixture.adapter)).rejects.toThrow();

    expect(fixture.reconcileCalls).toEqual(["first"]);
    expect(fixture.applyCalls).toEqual([]);
    expect(fixture.effects).toEqual({ external: [{ clip: "outside", frame: 99 }] });
    expect(fixture.current()).toEqual(before);
    expect(fixture.current().baseline).toBe(fixture.plan.baseline);
  });

  it("keeps the final item uncertain when it corrupts an earlier verified effect", async () => {
    const fixture = execution();
    fixture.hooks.onApply = (change, effects) => {
      if (change.id === "last") effects.first = [{ record: "corrupted" }];
    };

    const interrupted = await executeOutbound(fixture.store, fixture.adapter);

    expect(fixture.verifyCalls).toContainEqual({ change: "last", valid: true });
    expect(interrupted.outcomes.map((outcome) => outcome.status)).toEqual(["verified", "uncertain"]);
    expect(interrupted.baseline).toBe(fixture.plan.baseline);
    expect(interrupted.completed).toBe(false);
    expect(fixture.effects.first).toEqual([{ record: "corrupted" }]);
    expect(fixture.current()).toEqual(interrupted);
    const persisted = fixture.current();

    await expect(executeOutbound(fixture.store, fixture.adapter)).rejects.toThrow(/previously verified receipt/i);

    expect(fixture.applyCalls).toEqual(["first", "last"]);
    expect(fixture.reconcileCalls).toEqual([]);
    expect(fixture.verifyCalls.at(-1)).toEqual({ change: "first", valid: false });
    expect(fixture.current()).toEqual(persisted);
    expect(fixture.current().baseline).toBe(fixture.plan.baseline);
  });

  it("never applies when saving the pre-apply uncertain marker fails", async () => {
    const fixture = execution();
    fixture.hooks.failUncertainSave = true;

    await expect(executeOutbound(fixture.store, fixture.adapter)).rejects.toThrow("uncertain marker persistence failed");

    expect(fixture.applyCalls).toEqual([]);
    expect(fixture.effects).toEqual({});
    expect(fixture.current().outcomes.map((outcome) => outcome.status)).toEqual(["unattempted", "unattempted"]);
    expect(fixture.current().baseline).toBe(fixture.plan.baseline);
  });

  it.each(["source", "target"] as const)("keeps the old baseline if the final readback sees %s drift", async (drift) => {
    const fixture = execution();
    fixture.hooks.onVerify = (change, call, identity) => {
      if (change.id !== "first" || call !== 2) return;
      if (drift === "source") identity.source = "source:changed";
      else identity.target = "target:changed";
    };

    const result = await executeOutbound(fixture.store, fixture.adapter);

    expect(result.outcomes.map((outcome) => outcome.status)).toEqual(["verified", "uncertain"]);
    expect(result.baseline).toBe(fixture.plan.baseline);
    expect(result.current).not.toBe(result.baseline);
    expect(result.completed).toBe(false);
    expect(fixture.applyCalls).toEqual(["first", "last"]);
    expect(fixture.current()).toEqual(result);
  });
});
