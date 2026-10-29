import { createHash } from "node:crypto";

export type OutboundChange = Readonly<{
  id: string;
  order: number;
  kind: "structural" | "spanning-audio" | "cut";
  edits: readonly Readonly<Record<string, string | number | boolean>>[];
  blocked: string | null;
}>;
export type Selection = Readonly<{ changeIds: readonly string[] }>;
export type OutboundPlan = Readonly<{
  version: 1;
  source: string;
  target: string;
  baseline: string;
  changes: readonly Readonly<{ change: OutboundChange; disposition: "selected" | "skipped" | "blocked" }>[];
  hash: string;
}>;
export type Receipt = Readonly<{ plan: string; change: string; target: string; before: string; after: string }>;
export type Outcome = Readonly<{
  change: string;
  status: "unattempted" | "verified" | "failed" | "uncertain" | "skipped" | "blocked";
  receipt: Receipt | null;
  error: string | null;
}>;
export type OutboundAttempt = Readonly<{
  version: 1;
  plan: OutboundPlan;
  outcomes: readonly Outcome[];
  baseline: string;
  current: string;
  completed: boolean;
}>;
export interface OutboundAdapter {
  observe(): Promise<{ source: string; target: string; fingerprint: string }>;
  /** Must verify the whole semantic unit. Throwing after mutation is uncertain. */
  apply(change: OutboundChange, key: string): Promise<Receipt>;
  /** Independent readback of this exact receipt, including native geometry. */
  verify(receipt: Receipt, change: OutboundChange): Promise<boolean>;
  /** Called only after explicit recovery from an interrupted/failed operation. */
  reconcile(change: OutboundChange, key: string): Promise<Receipt | "not-applied" | "unknown">;
}
export interface OutboundStore {
  /** Serialize the entire execution, including native calls; no expiring auto-takeover. */
  exclusive<T>(work: () => Promise<T>): Promise<T>;
  load(): Promise<OutboundAttempt>;
  /** Atomically persist the entire attempt (including baseline), or throw. */
  save(attempt: OutboundAttempt): Promise<void>;
}

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value !== null && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical((value as Record<string, unknown>)[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}
export function outboundHash(value: unknown): string {
  return createHash("sha256").update(canonical(value)).digest("hex");
}
function immutable<T>(value: T): T {
  if (value !== null && typeof value === "object") {
    for (const entry of Object.values(value)) immutable(entry);
    Object.freeze(value);
  }
  return value;
}
function validateChanges(changes: readonly OutboundChange[]): void {
  if (new Set(changes.map((change) => change.id)).size !== changes.length ||
      new Set(changes.map((change) => change.order)).size !== changes.length ||
      changes.some((change) => typeof change.id !== "string" || !change.id || !Number.isSafeInteger(change.order) || change.order < 0 ||
        !["structural", "spanning-audio", "cut"].includes(change.kind) || !change.edits.length ||
        !(change.blocked === null || (typeof change.blocked === "string" && change.blocked.length > 0)) ||
        change.edits.some((edit) => Object.values(edit).some((value) =>
          !["string", "number", "boolean"].includes(typeof value) || (typeof value === "number" && !Number.isFinite(value)))))) {
    throw new Error("Invalid semantic changes");
  }
}
export function selectOutbound(changes: readonly OutboundChange[], ids: readonly string[] | "safe" | "clear"): Selection {
  validateChanges(changes);
  const selected = ids === "safe" ? changes.filter((change) => change.blocked === null).map((change) => change.id) : ids === "clear" ? [] : [...ids];
  if (new Set(selected).size !== selected.length || selected.some((id) => !changes.some((change) => change.id === id && change.blocked === null))) {
    throw new Error("Unknown, duplicate or blocked selection");
  }
  return immutable({ changeIds: selected });
}
export function freezeOutbound(changes: readonly OutboundChange[], selection: Selection, context: { source: string; target: string; baseline: string }): OutboundPlan {
  selectOutbound(changes, selection.changeIds);
  if (!selection.changeIds.length || [context.source, context.target, context.baseline].some((value) => typeof value !== "string" || !value)) throw new Error("Selection and context required");
  const body = {
    version: 1 as const, ...context,
    changes: structuredClone([...changes]).sort((a, b) => a.order - b.order).map((change) => ({ change,
      disposition: change.blocked !== null ? "blocked" as const : selection.changeIds.includes(change.id) ? "selected" as const : "skipped" as const })),
  };
  return immutable({ ...body, hash: outboundHash(body) });
}
export function outboundCounts(plan: OutboundPlan): { selected: number; skipped: number; blocked: number } {
  return plan.changes.reduce((counts, item) => { counts[item.disposition]++; return counts; }, { selected: 0, skipped: 0, blocked: 0 });
}
export function startOutbound(plan: OutboundPlan): OutboundAttempt {
  const attempt: OutboundAttempt = { version: 1, plan, outcomes: plan.changes.map((item) => ({ change: item.change.id,
    status: item.disposition === "selected" ? "unattempted" : item.disposition, receipt: null, error: null })),
  baseline: plan.baseline, current: plan.baseline, completed: false };
  return loadOutbound(JSON.stringify(attempt));
}
export function loadOutbound(json: string): OutboundAttempt {
  const value = JSON.parse(json) as OutboundAttempt;
  if (!value || value.version !== 1 || !value.plan || value.plan.version !== 1) throw new Error("Invalid saved attempt");
  const { hash, ...body } = value.plan;
  const selected = value.plan.changes.filter((item) => item.disposition === "selected").map((item) => item.change.id);
  const rebuilt = freezeOutbound(value.plan.changes.map((item) => item.change), { changeIds: selected }, { source: body.source, target: body.target, baseline: body.baseline });
  if (hash !== outboundHash(body) || canonical(rebuilt) !== canonical(value.plan) || value.outcomes.length !== value.plan.changes.length) throw new Error("Changed saved plan");
  let current = value.plan.baseline;
  let stopped = false;
  for (const [index, item] of value.plan.changes.entries()) {
    const outcome = value.outcomes[index];
    if (!outcome || outcome.change !== item.change.id || !(outcome.error === null || typeof outcome.error === "string")) throw new Error("Changed or invalid outcome");
    if (item.disposition !== "selected") {
      if (outcome.status !== item.disposition || outcome.receipt !== null || outcome.error !== null) throw new Error("Invalid excluded outcome");
      continue;
    }
    if (outcome.status === "verified") {
      const receipt = outcome.receipt;
      if (stopped || !receipt || receipt.plan !== hash || receipt.change !== item.change.id || receipt.target !== body.target || receipt.before !== current || typeof receipt.after !== "string" || !receipt.after || receipt.after === current || outcome.error !== null) throw new Error("Stale or reordered receipt");
      current = receipt.after;
    } else {
      if (!["unattempted", "failed", "uncertain"].includes(outcome.status) || outcome.receipt !== null || (stopped && outcome.status !== "unattempted")) throw new Error("Invalid pending outcome");
      stopped = true;
    }
  }
  const complete = value.outcomes.filter((outcome) => outcome.status === "verified").length === selected.length;
  if (value.current !== current || value.completed !== complete || value.baseline !== (complete ? current : body.baseline)) throw new Error("Non-atomic baseline");
  return immutable(value);
}

export async function executeOutbound(store: OutboundStore, adapter: OutboundAdapter): Promise<OutboundAttempt> {
  return store.exclusive(async () => {
    let attempt = loadOutbound(JSON.stringify(await store.load()));
    const observe = async () => {
      const value = await adapter.observe();
      if (value.source !== attempt.plan.source || value.target !== attempt.plan.target || typeof value.fingerprint !== "string" || !value.fingerprint) {
        throw new Error("Source or target changed");
      }
      return value;
    };
    const initial = await observe();
    const pending = attempt.outcomes.find((outcome) => !["verified", "skipped", "blocked"].includes(outcome.status));
    if (initial.fingerprint !== attempt.current && pending?.status !== "uncertain") throw new Error("Target content changed");
    for (const [index, outcome] of attempt.outcomes.entries()) {
      if (outcome.status === "verified" && !await adapter.verify(outcome.receipt!, attempt.plan.changes[index]!.change)) {
        throw new Error("Previously verified receipt no longer reads back");
      }
    }
    if (attempt.completed) {
      if ((await observe()).fingerprint !== attempt.current) throw new Error("Completed target changed");
      return attempt;
    }
    const save = async (index: number, status: Outcome["status"], receipt: Receipt | null, error: string | null) => {
      const outcomes = attempt.outcomes.map((outcome, position) => position === index ? { change: outcome.change, status, receipt, error } : outcome);
      const current = status === "verified" ? receipt!.after : attempt.current;
      const completed = outcomes.every((outcome) => ["verified", "skipped", "blocked"].includes(outcome.status));
      const next = loadOutbound(JSON.stringify({ ...attempt, outcomes, current, completed, baseline: completed ? current : attempt.plan.baseline }));
      await store.save(next);
      attempt = next;
    };
    const verify = async (receipt: Receipt, change: OutboundChange) => {
      if (!receipt || receipt.plan !== attempt.plan.hash || receipt.change !== change.id || receipt.target !== attempt.plan.target ||
          receipt.before !== attempt.current || typeof receipt.after !== "string" || !receipt.after || receipt.after === receipt.before ||
          !await adapter.verify(receipt, change) || (await observe()).fingerprint !== receipt.after) {
        throw new Error("Receipt is stale or did not verify");
      }
      // Recheck the whole selected prefix before the atomic baseline commit.
      const last = attempt.plan.changes.every((item, index) => item.disposition !== "selected" ||
        item.change.id === change.id || attempt.outcomes[index]!.status === "verified");
      if (last) {
        for (const [index, outcome] of attempt.outcomes.entries()) {
          if (outcome.status === "verified" && !await adapter.verify(outcome.receipt!, attempt.plan.changes[index]!.change)) {
            throw new Error("Earlier selected work changed before completion");
          }
        }
        if ((await observe()).fingerprint !== receipt.after) throw new Error("Target changed before completion");
      }
    };
    for (const [index, item] of attempt.plan.changes.entries()) {
      const outcome = attempt.outcomes[index]!;
      if (item.disposition !== "selected" || outcome.status === "verified") continue;
      const key = `${attempt.plan.hash}:${item.change.id}`;
      if (outcome.status === "failed" || outcome.status === "uncertain") {
        const recovered = await adapter.reconcile(item.change, key);
        if (recovered === "unknown") throw new Error("Native outcome remains unknown");
        if (recovered !== "not-applied") {
          await verify(recovered, item.change);
          await save(index, "verified", recovered, null);
          continue;
        }
      }
      if ((await observe()).fingerprint !== attempt.current) throw new Error("Target content changed before apply");
      await save(index, "uncertain", null, null);
      let receipt: Receipt;
      try {
        receipt = await adapter.apply(item.change, key);
      } catch (error) {
        let status: "failed" | "uncertain" = "uncertain";
        try {
          if (await adapter.reconcile(item.change, key) === "not-applied" && (await observe()).fingerprint === attempt.current) status = "failed";
        } catch { /* An unreadable native result remains uncertain. */ }
        await save(index, status, null, error instanceof Error ? error.message : "Native apply failed");
        return attempt;
      }
      try { await verify(receipt, item.change); }
      catch (error) {
        await save(index, "uncertain", null, error instanceof Error ? error.message : "Native verification failed");
        return attempt;
      }
      await save(index, "verified", receipt, null);
    }
    return attempt;
  });
}
