import { describe, expect, it } from "vitest";
import {
  executeOutbound,
  freezeOutbound,
  loadOutbound,
  outboundCounts,
  outboundHash,
  selectOutbound,
  startOutbound,
  type OutboundAdapter,
  type OutboundAttempt,
  type OutboundChange,
  type OutboundPlan,
  type Receipt,
} from "../src/selective-outbound.js";

const SOURCE = "script:source-1";
const TARGET = "resolve:timeline-1";
const SELECTED_IDS = ["cut-selected", "structural-pair", "spanning-audio"];

function changesFixture(): OutboundChange[] {
  return [
    { id: "cut-selected", order: 30, kind: "cut", edits: [{ clip: "A", frame: 120 }], blocked: null },
    { id: "cut-skipped", order: 40, kind: "cut", edits: [{ clip: "B", frame: 240 }], blocked: null },
    { id: "cut-blocked", order: 50, kind: "cut", edits: [{ clip: "missing", frame: 360 }], blocked: "source unavailable" },
    { id: "structural-pair", order: 10, kind: "structural", edits: [
      { track: "V1", start: 0, end: 120 },
      { track: "V2", start: 120, end: 240 },
    ], blocked: null },
    { id: "spanning-audio", order: 20, kind: "spanning-audio", edits: [
      { track: "A1", start: 0, end: 180, clip: "narration" },
      { track: "A1", start: 180, end: 360, clip: "narration" },
    ], blocked: null },
  ];
}

function planFixture(): OutboundPlan {
  const changes = changesFixture();
  const selection = selectOutbound(changes, SELECTED_IDS);
  return freezeOutbound(changes, selection, {
    source: SOURCE,
    target: TARGET,
    baseline: outboundHash({ effects: {} }),
  });
}

type TargetState = { effects: Record<string, readonly Readonly<Record<string, string | number | boolean>>[]> };
type AdapterOptions = {
  throwBeforeOnce?: string;
  throwAfterOnce?: string;
  verifyFalseOnce?: string;
  verifyThrowOnce?: string;
  verifyFalseFor?: string;
  reconcileUnknownFor?: string;
  onApply?: (change: OutboundChange, key: string) => Promise<void>;
};

class MemoryAdapter implements OutboundAdapter {
  source = SOURCE;
  target = TARGET;
  readonly state: TargetState = { effects: {} };
  readonly applyCalls: Array<{ id: string; key: string }> = [];
  readonly verifyCalls: string[] = [];
  readonly reconcileCalls: string[] = [];
  readonly events: string[] = [];
  readonly options: AdapterOptions = {};
  private readonly receipts = new Map<string, Receipt>();
  private readonly snapshots = new Map<string, TargetState>();

  constructor(private readonly plan: OutboundPlan) {
    this.snapshots.set(this.fingerprint(), this.snapshot());
  }

  private snapshot(): TargetState {
    return structuredClone(this.state);
  }

  private fingerprint(): string {
    return outboundHash(this.state);
  }

  observe(): Promise<{ source: string; target: string; fingerprint: string }> {
    this.events.push("observe");
    return Promise.resolve({ source: this.source, target: this.target, fingerprint: this.fingerprint() });
  }

  async apply(change: OutboundChange, key: string): Promise<Receipt> {
    this.events.push("apply:" + change.id);
    this.applyCalls.push({ id: change.id, key });
    await this.options.onApply?.(change, key);
    if (this.options.throwBeforeOnce === change.id) {
      delete this.options.throwBeforeOnce;
      throw new Error("native call failed before mutation");
    }

    const before = this.fingerprint();
    this.state.effects[change.id] = structuredClone(change.edits);
    const after = this.fingerprint();
    this.snapshots.set(after, this.snapshot());
    const receipt: Receipt = { plan: this.plan.hash, change: change.id, target: this.target, before, after };
    this.receipts.set(key, receipt);
    if (this.options.throwAfterOnce === change.id) {
      delete this.options.throwAfterOnce;
      throw new Error("native call failed after mutation");
    }
    return receipt;
  }

  verify(receipt: Receipt, change: OutboundChange): Promise<boolean> {
    this.events.push("verify:" + change.id);
    this.verifyCalls.push(change.id);
    if (this.options.verifyThrowOnce === change.id) {
      delete this.options.verifyThrowOnce;
      return Promise.reject(new Error("readback unavailable"));
    }
    if (this.options.verifyFalseOnce === change.id) {
      delete this.options.verifyFalseOnce;
      return Promise.resolve(false);
    }
    if (this.options.verifyFalseFor === change.id) return Promise.resolve(false);
    const before = this.snapshots.get(receipt.before);
    const after = this.snapshots.get(receipt.after);
    return Promise.resolve(receipt.plan === this.plan.hash && receipt.change === change.id && receipt.target === this.target &&
      before !== undefined && after !== undefined &&
      before.effects[change.id] === undefined &&
      JSON.stringify(after.effects[change.id]) === JSON.stringify(change.edits) &&
      JSON.stringify(this.state.effects[change.id]) === JSON.stringify(change.edits) &&
      outboundHash(after) === receipt.after);
  }

  reconcile(change: OutboundChange, key: string): Promise<Receipt | "not-applied" | "unknown"> {
    this.events.push("reconcile:" + change.id);
    this.reconcileCalls.push(change.id);
    if (this.options.reconcileUnknownFor === change.id) return Promise.resolve("unknown");
    const receipt = this.receipts.get(key);
    if (receipt && JSON.stringify(this.state.effects[change.id]) === JSON.stringify(change.edits)) return Promise.resolve(receipt);
    if (this.state.effects[change.id] === undefined) return Promise.resolve("not-applied");
    return Promise.resolve("unknown");
  }
}

class MemoryStore {
  private raw: string;
  readonly saved: string[] = [];
  loads = 0;
  exclusiveCalls = 0;
  activeExclusive = 0;
  maxActiveExclusive = 0;
  private tail: Promise<void> = Promise.resolve();

  constructor(plan: OutboundPlan) {
    this.raw = JSON.stringify(startOutbound(plan));
  }

  async exclusive<T>(work: () => Promise<T>): Promise<T> {
    this.exclusiveCalls++;
    const previous = this.tail;
    let release = () => {};
    this.tail = new Promise<void>((resolve) => { release = resolve; });
    await previous;
    this.activeExclusive++;
    this.maxActiveExclusive = Math.max(this.maxActiveExclusive, this.activeExclusive);
    try {
      return await work();
    } finally {
      this.activeExclusive--;
      release();
    }
  }

  load(): Promise<OutboundAttempt> {
    this.loads++;
    return Promise.resolve().then(() => loadOutbound(this.raw));
  }

  save(attempt: OutboundAttempt): Promise<void> {
    return Promise.resolve().then(() => {
      const raw = JSON.stringify(attempt);
      const validated = loadOutbound(raw);
      this.raw = JSON.stringify(validated);
      this.saved.push(this.raw);
    });
  }

  current(): OutboundAttempt {
    return loadOutbound(this.raw);
  }

  replaceRaw(raw: string): void {
    this.raw = raw;
  }
}

function makeExecution() {
  const plan = planFixture();
  const store = new MemoryStore(plan);
  const adapter = new MemoryAdapter(plan);
  return { plan, store, adapter };
}

describe("selective outbound plan", () => {
  it("freezes three selected changes, one skipped change and one blocked change in order", () => {
    const plan = planFixture();

    expect(plan.changes.map((item) => [item.change.id, item.disposition])).toEqual([
      ["structural-pair", "selected"],
      ["spanning-audio", "selected"],
      ["cut-selected", "selected"],
      ["cut-skipped", "skipped"],
      ["cut-blocked", "blocked"],
    ]);
    expect(outboundCounts(plan)).toEqual({ selected: 3, skipped: 1, blocked: 1 });
    expect(plan.source).toBe(SOURCE);
    expect(plan.target).toBe(TARGET);
    expect(plan.baseline).toBe(outboundHash({ effects: {} }));
    expect(plan.hash).toBe(outboundHash({
      version: 1,
      source: plan.source,
      target: plan.target,
      baseline: plan.baseline,
      changes: plan.changes,
    }));
  });

  it("keeps a structural multi-edit as one selected semantic unit", () => {
    const plan = planFixture();
    const structural = plan.changes.find((item) => item.change.id === "structural-pair");

    expect(structural?.disposition).toBe("selected");
    expect(structural?.change.kind).toBe("structural");
    expect(structural?.change.edits).toHaveLength(2);
    expect(selectOutbound(changesFixture(), ["structural-pair"]).changeIds).toEqual(["structural-pair"]);
  });

  it("keeps spanning audio under one semantic selection id", () => {
    const selection = selectOutbound(changesFixture(), ["spanning-audio"]);
    const plan = freezeOutbound(changesFixture(), selection, {
      source: SOURCE,
      target: TARGET,
      baseline: outboundHash({ effects: {} }),
    });
    const selected = plan.changes.filter((item) => item.disposition === "selected");

    expect(selected).toHaveLength(1);
    expect(selected[0]?.change.id).toBe("spanning-audio");
    expect(selected[0]?.change.kind).toBe("spanning-audio");
    expect(selected[0]?.change.edits).toHaveLength(2);
  });

  it("supports safe and clear selection", () => {
    const changes = changesFixture();

    expect(selectOutbound(changes, "safe").changeIds).toEqual(changes.filter((change) => change.blocked === null).map((change) => change.id));
    expect(selectOutbound(changes, "clear").changeIds).toEqual([]);
    expect(() => freezeOutbound(changes, selectOutbound(changes, "clear"), {
      source: SOURCE,
      target: TARGET,
      baseline: outboundHash({ effects: {} }),
    })).toThrow(/selection/i);
  });

  it("rejects duplicate, unknown and blocked ids", () => {
    const changes = changesFixture();

    expect(() => selectOutbound(changes, ["cut-selected", "cut-selected"])).toThrow(/unknown, duplicate or blocked/i);
    expect(() => selectOutbound(changes, ["not-a-change"])).toThrow(/unknown, duplicate or blocked/i);
    expect(() => selectOutbound(changes, ["cut-blocked"])).toThrow(/unknown, duplicate or blocked/i);
  });

  it("copies and deeply freezes the selection and plan inputs", () => {
    const changes = changesFixture();
    const ids = ["structural-pair"];
    const selection = selectOutbound(changes, ids);
    const plan = freezeOutbound(changes, selection, {
      source: SOURCE,
      target: TARGET,
      baseline: outboundHash({ effects: {} }),
    });
    ids[0] = "cut-selected";
    const mutableChanges = changes as unknown as Array<{ id: string; edits: Array<Record<string, string | number | boolean>> }>;
    mutableChanges.find((change) => change.id === "structural-pair")!.edits[0]!.track = "changed";

    expect(selection.changeIds).toEqual(["structural-pair"]);
    expect(plan.changes.find((item) => item.change.id === "structural-pair")?.change.edits[0]?.track).toBe("V1");
    expect(Object.isFrozen(selection.changeIds)).toBe(true);
    expect(Object.isFrozen(plan.changes)).toBe(true);
    expect(Object.isFrozen(plan.changes[0]?.change.edits[0])).toBe(true);
  });

  it("remounts from JSON with its hash, counts, order and dispositions intact", () => {
    const plan = planFixture();
    const attempt = startOutbound(plan);
    const loaded = loadOutbound(JSON.stringify(attempt));

    expect(loaded).toEqual(attempt);
    expect(loaded.plan.hash).toBe(plan.hash);
    expect(outboundCounts(loaded.plan)).toEqual({ selected: 3, skipped: 1, blocked: 1 });
    expect(loaded.plan.changes.map((item) => item.change.order)).toEqual([10, 20, 30, 40, 50]);
    expect(loaded.outcomes.map((item) => item.status)).toEqual(["unattempted", "unattempted", "unattempted", "skipped", "blocked"]);
  });

  it("refuses a saved plan whose content no longer matches its hash", () => {
    const saved = JSON.parse(JSON.stringify(startOutbound(planFixture()))) as {
      plan: { changes: Array<{ change: { edits: Array<Record<string, string | number | boolean>> } }> };
    };
    saved.plan.changes[0]!.change.edits[0] = { track: "different" };

    expect(() => loadOutbound(JSON.stringify(saved))).toThrow(/changed saved plan/i);
  });
});

describe("selective outbound execution", () => {
  it("applies selected semantic changes in plan order and atomically advances the baseline", async () => {
    const { plan, store, adapter } = makeExecution();
    const result = await executeOutbound(store, adapter);

    expect(adapter.applyCalls.map((call) => call.id)).toEqual(["structural-pair", "spanning-audio", "cut-selected"]);
    expect(result.outcomes.map((outcome) => outcome.status)).toEqual(["verified", "verified", "verified", "skipped", "blocked"]);
    expect(result.completed).toBe(true);
    expect(result.baseline).toBe(result.current);
    expect(result.current).not.toBe(plan.baseline);
    expect(adapter.state.effects["cut-skipped"]).toBeUndefined();
    expect(adapter.state.effects["cut-blocked"]).toBeUndefined();
    expect(store.saved.every((raw) => loadOutbound(raw).plan.hash === plan.hash)).toBe(true);
  });

  it("passes a stable idempotency key and binds each receipt to its plan, change and target", async () => {
    const { plan, store, adapter } = makeExecution();
    const result = await executeOutbound(store, adapter);

    expect(adapter.applyCalls.map((call) => call.key)).toEqual([
      plan.hash + ":structural-pair",
      plan.hash + ":spanning-audio",
      plan.hash + ":cut-selected",
    ]);
    for (const outcome of result.outcomes.filter((item) => item.status === "verified")) {
      expect(outcome.receipt).toMatchObject({ plan: plan.hash, change: outcome.change, target: TARGET });
      expect(outcome.receipt?.after).not.toBe(outcome.receipt?.before);
    }
  });

  it("persists each uncertain marker before entering the native apply call", async () => {
    const { store, adapter } = makeExecution();
    const seen: string[] = [];
    adapter.options.onApply = (change, key) => Promise.resolve().then(() => {
      const saved = store.current();
      const outcome = saved.outcomes.find((item) => item.change === change.id);
      seen.push(change.id);
      expect(key).toBe(saved.plan.hash + ":" + change.id);
      expect(outcome?.status).toBe("uncertain");
      expect(outcome?.receipt).toBeNull();
      expect(saved.baseline).toBe(saved.plan.baseline);
    });

    await executeOutbound(store, adapter);

    expect(seen).toEqual(["structural-pair", "spanning-audio", "cut-selected"]);
  });

  it("serializes concurrent callers across the whole execution", async () => {
    const { store, adapter } = makeExecution();
    let entered!: () => void;
    let release!: () => void;
    const insideApply = new Promise<void>((resolve) => { entered = resolve; });
    const gate = new Promise<void>((resolve) => { release = resolve; });
    adapter.options.onApply = async (change) => {
      if (change.id === "structural-pair") {
        entered();
        await gate;
      }
    };
    const first = executeOutbound(store, adapter);
    const waitingForExecution = first.then(
      () => { throw new Error("execution completed before entering apply"); },
      (error: unknown) => { throw error; },
    );
    await Promise.race([insideApply, waitingForExecution]);
    const second = executeOutbound(store, adapter);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(store.activeExclusive).toBe(1);
    expect(store.maxActiveExclusive).toBe(1);
    expect(adapter.events.filter((event) => event === "observe")).toHaveLength(1);
    release();
    const results = await Promise.all([first, second]);

    expect(results[1]).toEqual(results[0]);
    expect(store.maxActiveExclusive).toBe(1);
    expect(adapter.applyCalls).toHaveLength(3);
  });

  it("guards source, target and fingerprint before the first mutation", async () => {
    for (const drift of ["source", "target", "fingerprint"] as const) {
      const { store, adapter } = makeExecution();
      if (drift === "source") adapter.source = "script:changed";
      if (drift === "target") adapter.target = "resolve:other-timeline";
      if (drift === "fingerprint") adapter.state.effects.external = [{ clip: "outside", frame: 1 }];

      await expect(executeOutbound(store, adapter)).rejects.toThrow();
      expect(adapter.applyCalls).toHaveLength(0);
    }
  });

  it("reverifies earlier receipts before continuing a saved failed attempt", async () => {
    const { store, adapter } = makeExecution();
    adapter.options.throwBeforeOnce = "cut-selected";
    const first = await executeOutbound(store, adapter);
    expect(first.outcomes.map((item) => item.status)).toEqual(["verified", "verified", "failed", "unattempted", "blocked"]);
    adapter.events.length = 0;

    await executeOutbound(store, adapter);

    expect(adapter.events.slice(0, 3)).toEqual(["observe", "verify:structural-pair", "verify:spanning-audio"]);
    expect(adapter.events.indexOf("verify:spanning-audio")).toBeLessThan(adapter.events.indexOf("reconcile:cut-selected"));
    expect(adapter.events.indexOf("verify:spanning-audio")).toBeLessThan(adapter.events.indexOf("apply:cut-selected"));
  });

  it("refuses continuation when an earlier verified receipt no longer reads back", async () => {
    const { store, adapter } = makeExecution();
    adapter.options.throwBeforeOnce = "cut-selected";
    await executeOutbound(store, adapter);
    const applyCount = adapter.applyCalls.length;
    adapter.options.verifyFalseFor = "structural-pair";

    await expect(executeOutbound(store, adapter)).rejects.toThrow();

    expect(adapter.applyCalls).toHaveLength(applyCount);
    expect(store.current().outcomes[0]?.status).toBe("verified");
  });

  it("keeps the old baseline and stops when independent readback returns false", async () => {
    const { plan, store, adapter } = makeExecution();
    adapter.options.verifyFalseOnce = "structural-pair";
    const result = await executeOutbound(store, adapter);

    expect(result.outcomes.map((item) => item.status)).toEqual(["uncertain", "unattempted", "unattempted", "skipped", "blocked"]);
    expect(result.baseline).toBe(plan.baseline);
    expect(result.current).toBe(plan.baseline);
    expect(adapter.applyCalls.map((call) => call.id)).toEqual(["structural-pair"]);
  });

  it("keeps the old baseline and stops when independent readback throws", async () => {
    const { plan, store, adapter } = makeExecution();
    adapter.options.verifyThrowOnce = "structural-pair";
    const result = await executeOutbound(store, adapter);

    expect(result.outcomes[0]?.status).toBe("uncertain");
    expect(result.baseline).toBe(plan.baseline);
    expect(result.current).toBe(plan.baseline);
    expect(adapter.applyCalls).toHaveLength(1);
  });

  it("reconciles a pre-mutation throw as failed and leaves later items unattempted", async () => {
    const { plan, store, adapter } = makeExecution();
    adapter.options.throwBeforeOnce = "spanning-audio";
    const result = await executeOutbound(store, adapter);

    expect(adapter.reconcileCalls).toContain("spanning-audio");
    expect(adapter.state.effects["spanning-audio"]).toBeUndefined();
    expect(result.outcomes.map((item) => item.status)).toEqual(["verified", "failed", "unattempted", "skipped", "blocked"]);
    expect(result.baseline).toBe(plan.baseline);
    expect(adapter.applyCalls.map((call) => call.id)).toEqual(["structural-pair", "spanning-audio"]);
  });

  it("retries a reconciled failed item without replaying prior verified effects", async () => {
    const { store, adapter } = makeExecution();
    adapter.options.throwBeforeOnce = "spanning-audio";
    await executeOutbound(store, adapter);
    const retried = await executeOutbound(store, adapter);

    expect(retried.completed).toBe(true);
    expect(adapter.applyCalls.map((call) => call.id)).toEqual([
      "structural-pair", "spanning-audio", "spanning-audio", "cut-selected",
    ]);
    expect(adapter.state.effects["structural-pair"]).toEqual(changesFixture().find((change) => change.id === "structural-pair")?.edits);
    expect(retried.outcomes.filter((item) => item.status === "verified")).toHaveLength(3);
  });

  it("recovers an uncertain partial mutation from its receipt and readback without applying twice", async () => {
    const { plan, store, adapter } = makeExecution();
    adapter.options.throwAfterOnce = "structural-pair";
    adapter.options.reconcileUnknownFor = "structural-pair";
    const interrupted = await executeOutbound(store, adapter);

    expect(interrupted.outcomes[0]?.status).toBe("uncertain");
    expect(interrupted.baseline).toBe(plan.baseline);
    expect(adapter.state.effects["structural-pair"]).toBeDefined();
    expect(adapter.applyCalls).toHaveLength(1);

    delete adapter.options.reconcileUnknownFor;
    const recovered = await executeOutbound(store, adapter);

    expect(recovered.completed).toBe(true);
    expect(adapter.applyCalls.filter((call) => call.id === "structural-pair")).toHaveLength(1);
    expect(adapter.verifyCalls.filter((id) => id === "structural-pair")).toHaveLength(2);
    expect(recovered.outcomes[0]?.status).toBe("verified");
  });

  it("refuses unknown recovery without applying later changes", async () => {
    const { store, adapter } = makeExecution();
    adapter.options.throwAfterOnce = "structural-pair";
    adapter.options.reconcileUnknownFor = "structural-pair";
    await executeOutbound(store, adapter);
    const callsBeforeRecovery = adapter.applyCalls.length;

    const result = await executeOutbound(store, adapter).catch((error: unknown) => error);

    expect(adapter.applyCalls).toHaveLength(callsBeforeRecovery);
    expect(adapter.applyCalls.map((call) => call.id)).toEqual(["structural-pair"]);
    expect(store.current().outcomes[0]?.status).toBe("uncertain");
    expect(result).toBeInstanceOf(Error);
  });

  it("does not save or apply again after completion when guards still match", async () => {
    const { store, adapter } = makeExecution();
    const completed = await executeOutbound(store, adapter);
    const savedCount = store.saved.length;
    const applyCount = adapter.applyCalls.length;
    const again = await executeOutbound(store, adapter);

    expect(again).toEqual(completed);
    expect(store.saved).toHaveLength(savedCount);
    expect(adapter.applyCalls).toHaveLength(applyCount);
  });

  it("checks the source guard again after completion", async () => {
    const { store, adapter } = makeExecution();
    await executeOutbound(store, adapter);
    adapter.source = "script:changed";
    const applyCount = adapter.applyCalls.length;

    await expect(executeOutbound(store, adapter)).rejects.toThrow();

    expect(adapter.applyCalls).toHaveLength(applyCount);
  });

  it("checks the target guard again after completion", async () => {
    const { store, adapter } = makeExecution();
    await executeOutbound(store, adapter);
    adapter.target = "resolve:other-timeline";
    const applyCount = adapter.applyCalls.length;

    await expect(executeOutbound(store, adapter)).rejects.toThrow();

    expect(adapter.applyCalls).toHaveLength(applyCount);
  });

  it("checks the completed target fingerprint before returning without writes", async () => {
    const { store, adapter } = makeExecution();
    await executeOutbound(store, adapter);
    adapter.state.effects.external = [{ clip: "outside", frame: 1 }];
    const applyCount = adapter.applyCalls.length;
    const savedCount = store.saved.length;

    await expect(executeOutbound(store, adapter)).rejects.toThrow();

    expect(adapter.applyCalls).toHaveLength(applyCount);
    expect(store.saved).toHaveLength(savedCount);
  });

  it("validates the persisted attempt on remount before attempting native work", async () => {
    const { store, adapter } = makeExecution();
    const tampered = JSON.parse(JSON.stringify(store.current())) as {
      plan: { changes: Array<{ change: { id: string } }> };
    };
    tampered.plan.changes[0]!.change.id = "different-change";
    store.replaceRaw(JSON.stringify(tampered));

    await expect(executeOutbound(store, adapter)).rejects.toThrow(/changed saved plan/i);

    expect(adapter.applyCalls).toHaveLength(0);
    expect(tampered.plan.changes[0]?.change.id).toBe("different-change");
  });
});
