import assert from "node:assert/strict";
import { mkdtempSync, lstatSync, mkdirSync, realpathSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import {
  bindOrigin,
  captureOrigin,
  DEFAULT_DIRECTORY,
  findOriginForEvent,
  loadDeliveryAudit,
  loadOrigin,
  privateNavigationUrl,
  publicBinding,
  publicOwnerKey,
  saveDeliveryAudit,
  saveOrigin,
  VERA_REPOSITORY,
} from "./ci-notification-origin.mjs";

const THREAD_ID = "018f7c2a-7b1d-7cc0-9b23-1234567890ab";
const REVISION = "a".repeat(64);
const BRANCH = "codex/398-ci-origin-handoff";

test("public claim owner is stable and never contains the private runtime UUID", () => {
  const key = publicOwnerKey(THREAD_ID);
  assert.match(key, /^codex-owner-[0-9a-f]{64}$/);
  assert.equal(key, publicOwnerKey(THREAD_ID));
  assert.ok(!key.includes(THREAD_ID));
  assert.notEqual(key, publicOwnerKey("11111111-1111-4111-8111-111111111111"));
  assert.throws(() => publicOwnerKey("guessed-title"));
});

function makeRecord(overrides = {}) {
  return captureOrigin({
    repository: VERA_REPOSITORY,
    issue: 398,
    branch: BRANCH,
    approvalCommentId: 123456,
    approvalRevision: REVISION,
    authorizedScope: { title: "Private launch origin", body: "Approved scope", revision: REVISION },
    env: { CODEX_THREAD_ID: THREAD_ID },
    now: new Date("2026-11-02T15:30:00.000Z"),
    ...overrides,
  });
}

function registryDirectory(t) {
  const tempRoot = realpathSync(mkdtempSync(path.join(realpathSync(os.tmpdir()), "vera-ci-origin-")));
  const directory = path.join(tempRoot, "registry");
  t.after(() => rmSync(tempRoot, { recursive: true, force: true }));
  return directory;
}

test("captures the exact runtime thread and immutable approval as manual-review-only", () => {
  const record = makeRecord();
  assert.match(record.launchId, /^[0-9a-f]{64}$/);
  assert.equal(record.threadId, THREAD_ID);
  assert.equal(record.originSurface, "codex-desktop");
  assert.equal(record.provenance.method, "runtime-thread-environment");
  assert.deepEqual(record.provenance.approval, {
    kind: "current-producer-chat-review",
    commentId: 123456,
    revision: REVISION,
  });
  assert.equal(record.status, "manual-review-only");
  assert.equal(record.pr, null);
  assert.equal("canInject" in record, false);
  assert.equal(record.registeredAt, "2026-11-02T15:30:00.000Z");
  assert.equal(privateNavigationUrl(record), `codex://threads/${THREAD_ID}`);
});

test("requires the exact runtime UUID and fixed repository", () => {
  assert.throws(() => makeRecord({ env: {} }), /CODEX_THREAD_ID/);
  assert.throws(() => makeRecord({ env: { CODEX_THREAD_ID: "guessed-from-title" } }), /CODEX_THREAD_ID/);
  assert.throws(() => makeRecord({ repository: "mbelinkie/vera-research-video-clips" }), /repository/);
  assert.throws(() => makeRecord({ issue: 0 }), /issue/);
  assert.throws(() => makeRecord({ approvalRevision: "not-a-revision" }), /revision/);
});

test("stores immutable origins privately and makes repeated registration idempotent", async t => {
  const directory = registryDirectory(t);
  const record = makeRecord();
  const stored = await saveOrigin(record, directory);
  assert.deepEqual(stored, record);
  assert.deepEqual(await saveOrigin(record, directory), record);
  assert.deepEqual(loadOrigin(record.launchId, directory), record);
  assert.equal(lstatSync(directory).mode & 0o777, 0o700);
  const file = path.join(directory, `${record.launchId}.json`);
  assert.equal(lstatSync(file).mode & 0o777, 0o600);

  const eventId = "b".repeat(64);
  const emptyAudit = { version: 1, entries: [] };
  const audit = { version: 1, entries: [{ threadId: THREAD_ID }] };
  assert.equal(loadDeliveryAudit(eventId, directory), null);
  assert.equal(await saveDeliveryAudit(eventId, audit, emptyAudit, directory), true);
  assert.deepEqual(loadDeliveryAudit(eventId, directory), audit);
  assert.equal(lstatSync(path.join(directory, `delivery-audit-${eventId}.json`)).mode & 0o777, 0o600);
  assert.deepEqual(await saveDeliveryAudit(eventId, { version: 1, entries: [] }, emptyAudit, directory), { status: "writer_conflict" });
  assert.deepEqual(loadDeliveryAudit(eventId, directory), audit);

  const changed = { ...record, branch: "codex/other" };
  await assert.rejects(saveOrigin(changed, directory), /immutable/);
  await assert.rejects(saveOrigin({ ...record, injectionPermission: true }, directory), /Invalid/);
});

test("serializes writes with a private registry lock", async t => {
  const directory = registryDirectory(t);
  const record = makeRecord();
  await saveOrigin(record, directory);
  const lock = path.join(directory, ".registry.lock");
  writeFileSync(lock, "occupied", { mode: 0o600 });
  await assert.rejects(saveOrigin(record, directory), /locked/);
  rmSync(lock);
  assert.deepEqual(await saveOrigin(record, directory), record);
});

test("binds an open pull request once and publishes only approved public fields", async t => {
  const directory = registryDirectory(t);
  const record = makeRecord();
  await saveOrigin(record, directory);
  const bound = bindOrigin(record, 410, directory);
  assert.equal(bound.pr, 410);
  assert.equal(loadOrigin(record.launchId, directory).pr, 410);
  assert.equal(lstatSync(path.join(directory, `${record.launchId}.binding.json`)).mode & 0o777, 0o600);
  assert.equal(bindOrigin(bound, 410, directory).pr, 410);
  assert.throws(() => bindOrigin(bound, 411, directory), /another pull request/);

  const publicRecord = publicBinding(bound);
  assert.deepEqual(Object.keys(publicRecord), [
    "version", "repository", "issue", "pr", "launchId", "branch", "registeredAt", "approvalCommentId", "approvalRevision",
  ]);
  assert.equal(publicRecord.launchId, record.launchId);
  assert.equal("threadId" in publicRecord, false);
  assert.equal("authorizedScope" in publicRecord, false);
  assert.equal(JSON.stringify(publicRecord).includes(THREAD_ID), false);
});

test("matches events only on exact launch, repository, issue, PR, and branch", async t => {
  const directory = registryDirectory(t);
  const record = makeRecord();
  await saveOrigin(record, directory);
  bindOrigin(record, 410, directory);
  const event = {
    launchId: record.launchId,
    repository: record.repository,
    issue: record.issue,
    pr: 410,
    branch: record.branch,
  };
  assert.deepEqual(findOriginForEvent(event, directory), { ...record, pr: 410 });
  for (const mismatch of [
    { ...event, launchId: "f".repeat(64) },
    { ...event, repository: "other/repository" },
    { ...event, issue: 399 },
    { ...event, pr: 411 },
    { ...event, branch: "codex/wrong-branch" },
    { ...event, branch: undefined },
  ]) assert.equal(findOriginForEvent(mismatch, directory), null);
  assert.equal(findOriginForEvent({}, directory), null);
  assert.equal(findOriginForEvent(null, directory), null);
  assert.equal(findOriginForEvent(event, path.join(path.dirname(directory), "missing")), null);
});

test("refuses unsafe directory permissions and symlinks", async t => {
  const directory = registryDirectory(t);
  mkdirSync(directory, { mode: 0o700 });
  (await import("node:fs")).chmodSync(directory, 0o755);
  await assert.rejects(saveOrigin(makeRecord(), directory), /mode-0700/);

  const target = path.join(path.dirname(directory), "private-target");
  mkdirSync(target, { mode: 0o700 });
  const link = path.join(path.dirname(directory), "registry-link");
  symlinkSync(target, link);
  await assert.rejects(saveOrigin(makeRecord(), link), /mode-0700/);
});

test("refuses symlink origin files and invalid launch identifiers", async t => {
  const directory = registryDirectory(t);
  const record = makeRecord();
  await saveOrigin(record, directory);
  const source = path.join(directory, "source.json");
  writeFileSync(source, JSON.stringify(record), { mode: 0o600 });
  const originFile = path.join(directory, `${record.launchId}.json`);
  rmSync(originFile);
  symlinkSync(source, originFile);
  assert.throws(() => loadOrigin(record.launchId, directory), /unavailable or unsafe/);
  assert.throws(() => loadOrigin("../thread-id", directory), /launch ID/);
  assert.equal(DEFAULT_DIRECTORY.endsWith(path.join("VERA", "ci-notifications")), true);
});
