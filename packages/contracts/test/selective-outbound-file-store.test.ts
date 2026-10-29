import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { afterEach, expect, it } from "vitest";
import { outboundFileStore } from "../src/selective-outbound-file-store.ts";
import { freezeOutbound, selectOutbound, startOutbound } from "../src/selective-outbound.ts";

const directories: string[] = [];
afterEach(async () => { await Promise.all(directories.splice(0).map((directory) => rm(directory, { recursive: true }))); });
async function fixture() {
  const directory = await mkdtemp(join(tmpdir(), "vera-outbound-"));
  directories.push(directory);
  const path = join(directory, "attempt.json");
  const changes = [{ id: "cut", order: 0, kind: "cut" as const, edits: [{ record: 24 }], blocked: null }];
  const attempt = startOutbound(freezeOutbound(changes, selectOutbound(changes, "safe"), { source: "revision", target: "duplicate", baseline: "original" }));
  return { path, attempt, store: outboundFileStore(path) };
}
it("persists a complete immutable attempt across store recreation", async () => {
  const { path, attempt, store } = await fixture();
  await store.exclusive(() => store.save(attempt));
  expect(await outboundFileStore(path).load()).toEqual(attempt);
  expect(JSON.parse(await readFile(path, "utf8"))).toEqual(attempt);
});
it("refuses concurrent owners and releases the lock after a failure", async () => {
  const { path, store } = await fixture();
  await expect(store.exclusive(async () => {
    await expect(outboundFileStore(path).exclusive(() => Promise.resolve(undefined))).rejects.toThrow();
    throw new Error("interrupted");
  })).rejects.toThrow("interrupted");
  await expect(outboundFileStore(path).exclusive(() => Promise.resolve("released"))).resolves.toBe("released");
});
it("refuses unowned writes and invalid baseline replacement", async () => {
  const { store, attempt } = await fixture();
  await expect(store.save(attempt)).rejects.toThrow("exclusive");
  await store.exclusive(async () => {
    await store.save(attempt);
    await expect(store.save({ ...attempt, baseline: "premature" })).rejects.toThrow("baseline");
    expect(await store.load()).toEqual(attempt);
  });
});
it("refuses a different frozen plan in an existing journal", async () => {
  const { store, attempt } = await fixture();
  const changes = attempt.plan.changes.map((item) => item.change);
  const replacement = startOutbound(freezeOutbound(changes, selectOutbound(changes, "safe"), {
    source: attempt.plan.source, target: "different-target", baseline: attempt.plan.baseline,
  }));
  await store.exclusive(async () => {
    await store.save(attempt);
    await expect(store.save(replacement)).rejects.toThrow("frozen plan");
    expect(await store.load()).toEqual(attempt);
  });
});
it("retains uncertainty instead of accepting an old unattempted checkpoint", async () => {
  const { store, attempt } = await fixture();
  const uncertain = { ...attempt, outcomes: attempt.outcomes.map((outcome) => ({ ...outcome, status: "uncertain" as const })) };
  await store.exclusive(async () => {
    await store.save(attempt);
    await store.save(uncertain);
    await expect(store.save(attempt)).rejects.toThrow("frozen plan");
    expect(await store.load()).toEqual(uncertain);
  });
});
it("refuses a new journal that claims work has already started", async () => {
  const { store, attempt } = await fixture();
  await store.exclusive(async () => {
    await expect(store.save({ ...attempt, outcomes: attempt.outcomes.map((outcome) => ({ ...outcome, status: "uncertain" as const })) })).rejects.toThrow("before native work");
  });
});
it("retains an interrupted replacement without blocking a fresh atomic save", async () => {
  const { path, store, attempt } = await fixture();
  const interrupted = `${path}.interrupted.next`;
  await writeFile(interrupted, "partial replacement");
  await store.exclusive(() => store.save(attempt));
  expect(await store.load()).toEqual(attempt);
  expect(await readFile(interrupted, "utf8")).toBe("partial replacement");
});
