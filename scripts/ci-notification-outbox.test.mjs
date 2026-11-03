import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
import { createHash } from "node:crypto";
import test from "node:test";
import { URL } from "node:url";
import {
  canonicalEvent,
  NotificationOutbox,
  OUTBOX_BRANCH,
  REPOSITORY,
  renderReport,
  validateEvent,
} from "./ci-notification-outbox.mjs";

const SHA40 = (letter) => letter.repeat(40);
const SHA64 = (letter) => letter.repeat(64);
const NOW = Date.parse("2026-11-02T12:00:00.000Z");

function eventFields(overrides = {}) {
  return {
    issue: 398,
    pr: 43,
    launchId: SHA64("c"),
    transaction: "dispatch-43",
    queueTransaction: "queue-entry-8",
    runId: 9123,
    runAttempt: 2,
    workflowId: 17,
    workflowHead: SHA40("a"),
    candidate: SHA40("b"),
    base: SHA40("c"),
    mergeSha: null,
    stateSha: SHA40("d"),
    bindingSha: SHA40("e"),
    phase: "smoke",
    conclusion: "success",
    assessment: "gates_completed",
    emittedAt: "2026-11-02T12:00:00Z",
    ...overrides,
  };
}

function makeEvent(overrides = {}) {
  return canonicalEvent(eventFields(overrides));
}

function apiError(status = 404) {
  const error = new Error("sanitized test failure");
  error.status = status;
  return error;
}

class FakeGitHub {
  constructor() {
    this.repository = REPOSITORY;
    this.refs = new Map();
    this.files = new Map();
    this.history = new Map();
    this.comments = new Map();
    this.requests = [];
    this.createdTrees = [];
    this.createdCommits = [];
    this.putEvents = 0;
    this.commentPosts = 0;
    this.commentListFailures = 0;
    this.eventWriteMode = "normal";
    this.commentMode = "normal";
    this.commitAuthor = "github-actions[bot]";
  }

  seed(path, data) {
    this.#store(path, JSON.stringify(data));
  }

  #store(path, content) {
    const sha = createHash("sha1").update(content).digest("hex");
    const commitSha = createHash("sha1").update(path + content + String(this.history.size)).digest("hex");
    this.files.set(path, { content, sha });
    this.history.set(path, { sha: commitSha, author: { login: this.commitAuthor } });
    return sha;
  }

  async api(method, path, body) {
    const url = new URL(path, "https://api.github.com");
    this.requests.push({ method, path: url.pathname, search: url.search, body });
    const prefix = "/repos/" + REPOSITORY;
    const route = url.pathname.slice(prefix.length);

    if (method === "GET" && route.startsWith("/git/ref/heads/")) {
      const branch = route.slice("/git/ref/heads/".length);
      const sha = this.refs.get(branch);
      if (!sha) throw apiError(404);
      return { object: { sha } };
    }
    if (method === "POST" && route === "/git/blobs") {
      return { sha: SHA40("f") };
    }
    if (method === "POST" && route === "/git/trees") {
      this.createdTrees.push(body);
      return { sha: SHA40("e") };
    }
    if (method === "POST" && route === "/git/commits") {
      this.createdCommits.push(body);
      return { sha: SHA40("d") };
    }
    if (method === "POST" && route === "/git/refs") {
      const branch = body.ref.slice("refs/heads/".length);
      if (this.refs.has(branch)) throw apiError(422);
      this.refs.set(branch, body.sha);
      return null;
    }
    if (route.startsWith("/contents/")) {
      const filePath = route.slice("/contents/".length);
      if (method === "GET") {
        const file = this.files.get(filePath);
        if (!file) throw apiError(404);
        return {
          encoding: "base64",
          content: Buffer.from(file.content, "utf8").toString("base64"),
          sha: file.sha,
        };
      }
      if (method === "PUT") {
        const current = this.files.get(filePath);
        if ((current && body.sha !== current.sha) || (!current && body.sha)) throw apiError(409);
        if (filePath.startsWith("events/")) {
          this.putEvents += 1;
          if (this.eventWriteMode === "fail") throw apiError(503);
        }
        const content = Buffer.from(body.content, "base64").toString("utf8");
        const sha = this.#store(filePath, content);
        if (filePath.startsWith("events/") && this.eventWriteMode === "storeThenThrow") {
          throw new Error("transport ended after commit");
        }
        return { content: { sha } };
      }
    }
    if (method === "GET" && route === "/commits") {
      const history = this.history.get(url.searchParams.get("path"));
      return history ? [{ ...history, sha: history.sha, author: { login: this.commitAuthor } }] : [];
    }
    const match = route.match(/^\/issues\/([1-9][0-9]*)\/comments$/);
    if (match && method === "GET") {
      if (this.commentListFailures > 0) {
        this.commentListFailures -= 1;
        throw apiError(502);
      }
      const comments = this.comments.get(Number(match[1])) ?? [];
      const page = Number(url.searchParams.get("page") ?? 1);
      const perPage = Number(url.searchParams.get("per_page") ?? 100);
      return comments.slice((page - 1) * perPage, page * perPage);
    }
    if (match && method === "POST") {
      this.commentPosts += 1;
      if (this.commentMode === "throwWithoutStore") throw new Error("transport ended before confirmation");
      const comments = this.comments.get(Number(match[1])) ?? [];
      const comment = { user: { login: "github-actions[bot]" }, body: body.body };
      comments.push(comment);
      this.comments.set(Number(match[1]), comments);
      if (this.commentMode === "storeThenThrow") throw new Error("transport ended after comment");
      return comment;
    }
    throw new Error("Unexpected fake GitHub route " + method + " " + route);
  }
}

function createOutbox(github, now = () => NOW) {
  return new NotificationOutbox(github, { now });
}

test("canonicalizes only public fields and derives a stable event id independent of emission time", () => {
  const event = canonicalEvent({ ...eventFields(), secret: "private", log: "raw PR text" });
  const replay = makeEvent({ emittedAt: "2026-11-02T12:10:00.000Z" });

  assert.equal(event.eventId, replay.eventId);
  assert.equal(event.repository, REPOSITORY);
  assert.equal(event.expiresAt, "2026-11-09T12:00:00.000Z");
  assert.equal(Object.hasOwn(event, "secret"), false);
  assert.equal(validateEvent(event), event);
  assert.throws(() => validateEvent({ ...event, private: "extra" }), /invalid shape/);
  assert.throws(() => canonicalEvent(eventFields({ transaction: "bad<!--marker" })), /schema validation/);
  assert.throws(() => canonicalEvent(eventFields({ runUrl: "https://example.com/log" })), /run URL/);
  assert.throws(() => canonicalEvent(eventFields({ emittedAt: "2026-02-30T12:00:00Z" })), /valid UTC ISO/);
});

test("renders a fixed report with exact public links and no free-form PR or log data", () => {
  const event = canonicalEvent({
    ...eventFields(),
    title: "PR title with secret",
    logs: "authorization: private",
  });
  const report = renderReport(event);
  const code = String.fromCharCode(96);

  assert.match(report, new RegExp("<!-- vera-ci-event:" + event.eventId + " -->"));
  assert.match(report, new RegExp("Candidate: " + code + event.candidate + code));
  assert.match(report, new RegExp("Base: " + code + event.base + code));
  assert.match(report, /Assessment: gates_completed; enclosing workflow completion is not implied/);
  assert.match(report, /Automatic comment\/report injection is disabled/);
  assert.match(report, /no approval or merge authority/);
  assert.match(report, new RegExp("blob/" + event.stateSha + "/queue.json"));
  assert.match(report, new RegExp("blob/" + OUTBOX_BRANCH + "/events/" + event.eventId + "\\.json"));
  assert.doesNotMatch(report, /secret|authorization|private/);
});

test("creates an orphan outbox root and publishes an immutable event before one bot comment", async () => {
  const github = new FakeGitHub();
  const outbox = createOutbox(github);
  const event = makeEvent();
  const result = await outbox.publish(event);
  const stored = await outbox.read(event.eventId);

  assert.equal(result.status, "commented");
  assert.equal(result.persisted, true);
  assert.equal(github.commentPosts, 1);
  assert.deepEqual(github.createdCommits[0].parents, []);
  assert.deepEqual(github.createdTrees[0].tree.map((entry) => entry.path), ["outbox.json"]);
  assert.equal(github.requests.some((request) => request.path.includes("/git/ref/heads/main")), false);
  assert.equal(github.requests.some((request) => request.path.includes("vera-ci-queue-state")), false);
  assert.equal(stored.event.eventId, event.eventId);
  assert.equal(stored.provenance.author, "github-actions[bot]");
  assert.match(stored.blobSha, /^[0-9a-f]{40}$/);
  assert.equal(github.files.get("events/" + event.eventId + ".json").content, JSON.stringify(event));
});

test("deduplicates repeated publication by bot marker and returns registration documents with blob hashes", async () => {
  const github = new FakeGitHub();
  const outbox = createOutbox(github);
  const event = makeEvent();
  await outbox.publish(event);
  const duplicate = await outbox.publish(event);

  assert.equal(duplicate.status, "commented");
  assert.equal(github.commentPosts, 1);

  await outbox.writeDocument("registrations/pr-43.json", { pr: 43, binding: "public" }, { expectedSha: null });
  const registration = await outbox.readDocument("registrations/pr-43.json");
  assert.deepEqual(registration.data, { pr: 43, binding: "public" });
  assert.match(registration.sha, /^[0-9a-f]{40}$/);
  await assert.rejects(outbox.writeDocument("registrations/pr-43.json", { pr: 43 }, {}), /requires its expected blob id/);
  await assert.rejects(outbox.readDocument("../queue.json"), /path was invalid/);
});

test("serializes concurrent publishers through the audit claim before posting a comment", async () => {
  const github = new FakeGitHub();
  const outbox = createOutbox(github);
  const event = makeEvent();

  const results = await Promise.all([outbox.publish(event), outbox.publish(event)]);

  assert.ok(results.every((result) => result.persisted));
  assert.equal(github.commentPosts, 1);
  assert.equal((github.comments.get(event.pr) ?? []).length, 1);
});

test("refuses to overwrite a conflicting event path", async () => {
  const github = new FakeGitHub();
  const outbox = createOutbox(github);
  const event = makeEvent();
  const path = "events/" + event.eventId + ".json";
  github.seed(path, { different: true });

  await assert.rejects(outbox.writeDocument(path, event, { expectedSha: null }), (error) => error.code === "conflict");
  assert.equal(github.putEvents, 0);
});

test("reconciles an ambiguous event PUT before retrying", async () => {
  const github = new FakeGitHub();
  github.eventWriteMode = "storeThenThrow";
  const result = await createOutbox(github).publish(makeEvent());

  assert.equal(result.status, "commented");
  assert.equal(github.putEvents, 1);
  assert.equal(github.commentPosts, 1);
});

test("reconciles an ambiguous comment outcome and never blindly posts twice", async () => {
  const github = new FakeGitHub();
  github.commentMode = "storeThenThrow";
  const event = makeEvent();
  const result = await createOutbox(github).publish(event);

  assert.equal(result.status, "commented");
  assert.equal(github.commentPosts, 1);
  assert.equal((github.comments.get(event.pr) ?? []).length, 1);
});

test("allows one explicit manual retry after the recorded backoff and caps comment posts at two", async () => {
  const github = new FakeGitHub();
  let now = NOW;
  github.commentMode = "throwWithoutStore";
  const outbox = createOutbox(github, () => now);
  const event = makeEvent();
  const pending = await outbox.publish(event);

  assert.equal(pending.status, "pending");
  assert.equal(pending.manualRetryAvailable, true);
  assert.equal(github.commentPosts, 1);
  assert.ok(Date.parse(pending.nextAttemptAt) > now);

  const early = await outbox.manualRetry(event.eventId);
  assert.equal(early.status, "pending");
  assert.equal(github.commentPosts, 1);

  now = Date.parse(pending.nextAttemptAt);
  const retryAt = await outbox.manualRetry(event.eventId);
  assert.equal(retryAt.status, "pending");
  assert.equal(retryAt.manualRetryAvailable, false);
  assert.equal(github.commentPosts, 2);
  const exhausted = await outbox.manualRetry(event.eventId);
  assert.equal(exhausted.status, "pending");
  assert.equal(github.commentPosts, 2);
});

test("manual retry recovers from a transient initial comment-list failure with zero prior posts", async () => {
  const github = new FakeGitHub();
  let now = NOW;
  github.commentListFailures = 1;
  const outbox = createOutbox(github, () => now);
  const event = makeEvent();
  const pending = await outbox.publish(event);

  assert.equal(pending.attempts.commentPost, 0);
  assert.equal(pending.status, "pending");
  assert.equal(pending.manualRetryAvailable, true);
  assert.equal(github.commentPosts, 0);

  const early = await outbox.manualRetry(event.eventId);
  assert.equal(early.attempts.commentPost, 0);
  assert.equal(github.commentPosts, 0);

  now = Date.parse(event.expiresAt);
  await assert.rejects(outbox.manualRetry(event.eventId), /Expired/);
  assert.equal(github.commentPosts, 0);

  now = Date.parse(pending.nextAttemptAt);
  const results = await Promise.all([
    outbox.manualRetry(event.eventId),
    outbox.manualRetry(event.eventId),
  ]);
  assert.ok(results.every((result) => result.persisted));
  assert.equal(github.commentPosts, 1);
  assert.equal((github.comments.get(event.pr) ?? []).length, 1);
  assert.equal((await outbox.manualRetry(event.eventId)).manualRetryAvailable, false);
  assert.equal(github.commentPosts, 1);
});

test("bounds failed event writes to three attempts and does not comment without a durable event", async () => {
  const github = new FakeGitHub();
  github.eventWriteMode = "fail";
  const outbox = createOutbox(github);

  await assert.rejects(outbox.publish(makeEvent()), (error) => error.status === 503);
  assert.equal(github.putEvents, 3);
  assert.equal(github.commentPosts, 0);
});

test("expiry stops explicit replay and identifiers must remain primitive strings", async () => {
  const github = new FakeGitHub(), event = makeEvent();
  const outbox = createOutbox(github);
  await outbox.publish(event);
  const expired = createOutbox(github, () => Date.parse(event.expiresAt));
  await assert.rejects(expired.manualRetry(event.eventId), /Expired/);
  for (const field of ["candidate", "base", "workflowHead", "stateSha", "launchId"]) {
    assert.throws(() => canonicalEvent({ ...event, [field]: [field === "launchId" ? "a".repeat(64) : "a".repeat(40)] }), /schema/);
  }
});

test("rejects event reads whose latest path commit is not authored by the GitHub Actions bot", async () => {
  const github = new FakeGitHub();
  const outbox = createOutbox(github);
  const event = makeEvent();
  await outbox.publish(event);
  github.commitAuthor = "a-human";

  await assert.rejects(outbox.read(event.eventId), /authenticated bot provenance/);
});
