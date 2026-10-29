import { spawnSync } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { outboundFileStore } from "./selective-outbound-file-store.ts";
import { executeOutbound, freezeOutbound, selectOutbound, startOutbound } from "./selective-outbound.ts";
import type { OutboundAdapter, OutboundChange, OutboundStore, Receipt } from "./selective-outbound.ts";

type Observation = { source: string; target: string; fingerprint: string };
type BridgeResult = {
  session?: Record<string, unknown>;
  observation?: Observation;
  receipt?: Receipt;
  reconciliation?: Receipt | "not-applied" | "unknown";
  verified?: boolean;
  originalUnchanged?: boolean;
  originalCurrent?: boolean;
};
const NATIVE_PYTHON = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Resources/ResolvePython/ResolvePython";
const NATIVE_BRIDGE = fileURLToPath(new URL("../../../scripts/issue328_native_bridge.py", import.meta.url));
type Session = { python: string; bridge: string; bridgeSha256: string; native: Record<string, unknown> };

function command(session: Session, action: string, fields: Record<string, unknown> = {}): BridgeResult {
  if (!session || session.python !== NATIVE_PYTHON || session.bridge !== NATIVE_BRIDGE ||
      session.bridgeSha256 !== createHash("sha256").update(readFileSync(NATIVE_BRIDGE)).digest("hex") ||
      !session.native || typeof session.native !== "object" || Array.isArray(session.native)) {
    throw new Error("Native bridge/session identity changed; inspect before continuing");
  }
  const result = spawnSync(session.python, [session.bridge], {
    input: JSON.stringify({ schemaVersion: "vera-issue-328-native-command/v1", action, session: session.native, ...fields }),
    encoding: "utf8", timeout: 60_000, maxBuffer: 1024 * 1024,
  });
  if (result.error || result.status !== 0) throw new Error(`Native ${action} uncertain: ${result.error?.message ?? result.stderr}`);
  return JSON.parse(result.stdout) as BridgeResult;
}
function nativeChange(change: OutboundChange) {
  const edit = change.edits[0];
  if (change.kind !== "cut" || change.edits.length !== 1 || !edit ||
    typeof edit.sourceId !== "string" || typeof edit.recordFrame !== "number" || typeof edit.durationFrames !== "number") {
    throw new Error("Native proof supports one cut-only append per change");
  }
  return { id: change.id, kind: change.kind, sourceId: edit.sourceId, recordFrame: edit.recordFrame, durationFrames: edit.durationFrames };
}
function adapter(session: Session, hash: string, failAtBoundary: boolean, store: OutboundStore): OutboundAdapter {
  return {
    observe() {
      const observation = command(session, "observe", { planSha256: hash }).observation;
      if (!observation) return Promise.reject(new Error("Missing native observation"));
      return Promise.resolve(observation);
    },
    async apply(change, key) {
      if (key !== `${hash}:${change.id}`) return Promise.reject(new Error("Changed idempotency key"));
      if (failAtBoundary && change.id === "append-red") return Promise.reject(new Error("Injected failure before native item2"));
      const currentTargetFingerprint = (await store.load()).current;
      const receipt = command(session, "apply", { planSha256: hash, change: nativeChange(change), currentTargetFingerprint }).receipt;
      if (!receipt) return Promise.reject(new Error("Missing native receipt"));
      return Promise.resolve(receipt);
    },
    verify(receipt, change) {
      return Promise.resolve(command(session, "verify", { planSha256: hash, change: nativeChange(change), receipt }).verified === true);
    },
    async reconcile(change, key) {
      if (key !== `${hash}:${change.id}`) return Promise.reject(new Error("Changed recovery key"));
      const currentTargetFingerprint = (await store.load()).current;
      return command(session, "reconcile", { planSha256: hash, change: nativeChange(change), currentTargetFingerprint }).reconciliation ?? "unknown";
    },
  };
}
async function setup(directory: string, python: string, bridge: string, red: string, blue: string, expectedEmptyProjectUid?: string): Promise<void> {
  // A consumed setup directory is retained even after a timeout: never create a replacement blindly.
  await mkdir(directory, { mode: 0o700 });
  await writeFile(resolve(directory, "setup-started.json"), JSON.stringify({ version: 1 }), { flag: "wx" });
  const sources = await Promise.all([red, blue].map(async (path, index) => ({
    id: index === 0 ? "red" : "blue", path: resolve(path),
    sha256: createHash("sha256").update(await readFile(path)).digest("hex"), sourceInFrame: 0, durationFrames: 24,
  })));
  const session: Session = { python: resolve(python), bridge: resolve(bridge),
    bridgeSha256: createHash("sha256").update(await readFile(NATIVE_BRIDGE)).digest("hex"), native: {} };
  const request = {
    operationId: randomUUID(), projectName: `VERA_328_${randomUUID().slice(0, 8)}`,
    sourceRevision: "issue328-public-synthetic-v1", operationDir: directory, sources,
    ...(expectedEmptyProjectUid === undefined ? {} : { expectedEmptyProjectUid }),
  };
  await writeFile(resolve(directory, "setup-request.json"), JSON.stringify({ ...request, bridgeSha256: session.bridgeSha256 }), { flag: "wx", mode: 0o600 });
  const result = command(session, "setup", request);
  if (!result.session || !result.observation) throw new Error("Native setup incomplete; inspect retained target before any new setup");
  session.native = result.session;
  await writeFile(resolve(directory, "session.json"), JSON.stringify(session), { flag: "wx", mode: 0o600 });
  const changes: OutboundChange[] = [
    { id: "append-blue", kind: "cut", order: 0, blocked: null, edits: [{ sourceId: "blue", recordFrame: 24, durationFrames: 24 }] },
    { id: "append-red", kind: "cut", order: 1, blocked: null, edits: [{ sourceId: "red", recordFrame: 48, durationFrames: 24 }] },
  ];
  const plan = freezeOutbound(changes, selectOutbound(changes, "safe"), {
    source: result.observation.source, target: result.observation.target, baseline: result.observation.fingerprint,
  });
  const store = outboundFileStore(resolve(directory, "attempt.json"));
  await store.exclusive(() => store.save(startOutbound(plan)));
  await writeFile(resolve(directory, "setup-result.json"), JSON.stringify(result), { flag: "wx", mode: 0o600 });
  console.log(JSON.stringify({ status: "prepared", plan: plan.hash, target: plan.target }));
}
async function main(): Promise<void> {
  const [action, location, ...args] = process.argv.slice(2);
  if (!location || !["setup", "partial", "retry", "reopen"].includes(action ?? "")) throw new Error("Use setup DIRECTORY PYTHON BRIDGE RED BLUE [EXPECTED_EMPTY_PROJECT_UID], or partial|retry|reopen DIRECTORY");
  const directory = resolve(location);
  if (action === "setup") {
    if (args.length !== 4 && args.length !== 5) throw new Error("Setup requires explicit Python, bridge, two public synthetic sources, and an optional empty-project UID opt-in");
    await setup(directory, args[0]!, args[1]!, args[2]!, args[3]!, args[4]);
    return;
  }
  if (args.length) throw new Error("Unexpected arguments");
  const session = JSON.parse(await readFile(resolve(directory, "session.json"), "utf8")) as Session;
  const store = outboundFileStore(resolve(directory, "attempt.json"));
  const before = await store.load();
  if (action === "reopen") {
    const result = await store.exclusive(() => Promise.resolve(command(session, "reopen", { planSha256: before.plan.hash })));
    if (result.verified !== true || result.originalUnchanged !== true || result.originalCurrent !== true ||
      result.observation?.fingerprint !== before.current || result.observation.source !== before.plan.source ||
      result.observation.target !== before.plan.target) throw new Error("Save/reopen did not preserve the frozen target and original");
    console.log(JSON.stringify(result));
    return;
  }
  const result = await executeOutbound(store, adapter(session, before.plan.hash, action === "partial", store));
  if (result.plan.hash !== before.plan.hash || result.plan.target !== before.plan.target) throw new Error("Plan or target changed");
  if (action === "partial" && (result.completed || result.outcomes[0]?.status !== "verified" || result.outcomes[1]?.status !== "failed" || result.baseline !== before.plan.baseline)) throw new Error("Expected boundary failure was not preserved");
  if (action === "retry" && !result.completed) throw new Error("Same-target retry did not complete");
  console.log(JSON.stringify(result));
}
await main();
