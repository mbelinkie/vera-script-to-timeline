import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
import test from "node:test";
import { URL } from "node:url";
import { GitHub } from "./ci-queue-github.mjs";

const repository = "owner/project";
const PAGE_SIZE = 100;
const sha = (letter) => letter.repeat(40);

function jsonResponse(payload, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => payload };
}

test("validates repository credentials and keeps HTTP errors free of response data", async () => {
  assert.throws(() => new GitHub({ repository: "https://github.com/owner/project", token: "token" }), /owner\/repository/);
  assert.throws(() => new GitHub({ repository, token: " " }), /token is required/);

  const seen = [];
  const client = new GitHub({
    repository,
    token: "private-token",
    fetchImpl: async (url, options) => {
      seen.push({ url: String(url), options });
      if (options.method === "POST") return jsonResponse({ created: true });
      return { ok: false, status: 403, json: async () => ({ message: "private response body" }) };
    },
  });

  assert.deepEqual(await client.api("POST", "/repos/owner/project/example", { value: 1 }), { created: true });
  assert.equal(seen[0].url, "https://api.github.com/repos/owner/project/example");
  assert.equal(seen[0].options.headers.Authorization, "Bearer private-token");
  assert.equal(seen[0].options.headers["Content-Type"], "application/json");
  assert.deepEqual(JSON.parse(seen[0].options.body), { value: 1 });

  await assert.rejects(client.api("GET", "/repos/owner/project/private"), (error) => {
    assert.equal(error.status, 403);
    assert.equal(error.message, "GET /repos/owner/project/private returned HTTP 403");
    assert.doesNotMatch(error.message, /private-token|private response body/);
    return true;
  });
});

test("returns null for 204 and never retries a failed mutation", async () => {
  let calls = 0;
  const client = new GitHub({
    repository,
    token: "token",
    fetchImpl: async () => {
      calls += 1;
      if (calls === 1) return { ok: true, status: 204 };
      throw new Error("private transport detail");
    },
  });

  assert.equal(await client.api("PATCH", "/repos/owner/project/git/refs/heads/state", { sha: sha("a") }), null);
  await assert.rejects(client.api("POST", "/repos/owner/project/git/refs", { ref: "refs/heads/state" }), (error) => {
    assert.match(error.message, /^POST \/repos\/owner\/project\/git\/refs failed before receiving an HTTP response$/);
    assert.doesNotMatch(error.message, /private transport detail/);
    return true;
  });
  assert.equal(calls, 2);
});

test("collects array pages and rejects malformed or over-limit pagination", async () => {
  const requests = [];
  const client = new GitHub({
    repository,
    token: "token",
    fetchImpl: async (url) => {
      const parsed = new URL(url);
      requests.push(parsed);
      const page = Number(parsed.searchParams.get("page"));
      return jsonResponse(page === 1 ? Array.from({ length: 100 }, (_, index) => index) : [100]);
    },
  });

  assert.deepEqual(await client.pages("/repos/owner/project/items?state=open"), [...Array.from({ length: 100 }, (_, index) => index), 100]);
  assert.equal(requests.length, 2);
  assert.equal(requests[0].searchParams.get("state"), "open");
  assert.equal(requests[0].searchParams.get("per_page"), "100");
  assert.equal(requests[0].searchParams.get("page"), "1");
  assert.equal(requests[1].searchParams.get("page"), "2");

  const malformed = new GitHub({ repository, token: "token", fetchImpl: async () => jsonResponse({ items: [] }) });
  await assert.rejects(malformed.pages("/repos/owner/project/items"), /non-array page/);

  let pageCalls = 0;
  const unbounded = new GitHub({
    repository,
    token: "token",
    fetchImpl: async () => {
      pageCalls += 1;
      return jsonResponse(Array(PAGE_SIZE).fill(null));
    },
  });
  await assert.rejects(unbounded.pages("/repos/owner/project/items"), /100-page limit/);
  assert.equal(pageCalls, 100);
});

test("loads the state branch through its exact nonrecursive queue.json blob", async () => {
  const requests = [];
  const content = JSON.stringify({ version: 1, entries: [{ id: "job-1" }] });
  const client = new GitHub({
    repository,
    token: "token",
    fetchImpl: async (url) => {
      const path = new URL(url).pathname;
      requests.push(path);
      if (path.endsWith("/ref/heads/vera-ci-queue-state")) return jsonResponse({ object: { sha: sha("a") } });
      if (path.endsWith(`/commits/${sha("a")}`)) return jsonResponse({ tree: { sha: sha("b") } });
      if (path.endsWith(`/trees/${sha("b")}`)) {
        assert.equal(new URL(url).searchParams.has("recursive"), false);
        return jsonResponse({ tree: [{ path: "queue.json", mode: "100644", type: "blob", sha: sha("c") }] });
      }
      if (path.endsWith(`/blobs/${sha("c")}`)) return jsonResponse({ encoding: "base64", content: Buffer.from(content).toString("base64") });
      throw new Error("unexpected route");
    },
  });

  assert.deepEqual(await client.loadState(), { sha: sha("a"), state: { version: 1, entries: [{ id: "job-1" }] } });
  assert.deepEqual(requests, [
    "/repos/owner/project/git/ref/heads/vera-ci-queue-state",
    `/repos/owner/project/git/commits/${sha("a")}`,
    `/repos/owner/project/git/trees/${sha("b")}`,
    `/repos/owner/project/git/blobs/${sha("c")}`,
  ]);
});

test("returns null only when the state ref is missing and fails closed on later 404s or corruption", async () => {
  const missingRef = new GitHub({ repository, token: "token", fetchImpl: async () => jsonResponse({}, 404) });
  assert.equal(await missingRef.loadState(), null);

  const missingCommit = new GitHub({
    repository,
    token: "token",
    fetchImpl: async (url) => {
      const path = new URL(url).pathname;
      if (path.endsWith("/ref/heads/vera-ci-queue-state")) return jsonResponse({ object: { sha: sha("a") } });
      return jsonResponse({ message: "not found" }, 404);
    },
  });
  await assert.rejects(missingCommit.loadState(), (error) => error.status === 404);

  const corruptTree = new GitHub({
    repository,
    token: "token",
    fetchImpl: async (url) => {
      const path = new URL(url).pathname;
      if (path.endsWith("/ref/heads/vera-ci-queue-state")) return jsonResponse({ object: { sha: sha("a") } });
      if (path.endsWith(`/commits/${sha("a")}`)) return jsonResponse({ tree: { sha: sha("b") } });
      if (path.endsWith(`/trees/${sha("b")}`)) {
        return jsonResponse({ tree: [{ path: "queue.json", mode: "100644", type: "blob", sha: sha("c") }, { path: "other", mode: "100644", type: "blob", sha: sha("d") }] });
      }
      throw new Error("unexpected route");
    },
  });
  await assert.rejects(corruptTree.loadState(), /unexpected files/);

  const corruptBlob = new GitHub({
    repository,
    token: "token",
    fetchImpl: async (url) => {
      const path = new URL(url).pathname;
      if (path.endsWith("/ref/heads/vera-ci-queue-state")) return jsonResponse({ object: { sha: sha("a") } });
      if (path.endsWith(`/commits/${sha("a")}`)) return jsonResponse({ tree: { sha: sha("b") } });
      if (path.endsWith(`/trees/${sha("b")}`)) return jsonResponse({ tree: [{ path: "queue.json", mode: "100644", type: "blob", sha: sha("c") }] });
      return jsonResponse({ encoding: "utf-8", content: "{\"ok\":true}" });
    },
  });
  await assert.rejects(corruptBlob.loadState(), /invalid encoding or content/);
});

test("writes one-file commits, using compare-and-swap without force for updates", async () => {
  const requests = [];
  const client = new GitHub({
    repository,
    token: "token",
    fetchImpl: async (url, options) => {
      const path = new URL(url).pathname;
      const body = options.body === undefined ? null : JSON.parse(options.body);
      requests.push({ method: options.method, path, body });
      if (path.endsWith("/blobs")) return jsonResponse({ sha: sha("b") });
      if (path.endsWith("/trees")) return jsonResponse({ sha: sha("c") });
      if (path.endsWith("/commits")) return jsonResponse({ sha: sha("d") });
      if (path.endsWith("/refs")) return jsonResponse({ ref: body.ref });
      if (path.endsWith("/refs/heads/vera-ci-queue-state")) return jsonResponse({ object: { sha: body.sha } });
      throw new Error("unexpected route");
    },
  });

  const firstState = { version: 1, entries: [] };
  assert.deepEqual(await client.saveState(firstState), { sha: sha("d"), state: firstState });
  const secondState = { version: 1, entries: [{ id: "job-2" }] };
  const updated = await client.saveState(secondState, sha("a"));
  assert.deepEqual(updated, { sha: sha("d"), state: secondState });

  assert.equal(requests.length, 8);
  assert.deepEqual(requests[0].body, { content: JSON.stringify(firstState), encoding: "utf-8" });
  assert.deepEqual(requests[1].body, { tree: [{ path: "queue.json", mode: "100644", type: "blob", sha: sha("b") }] });
  assert.deepEqual(requests[2].body, { message: "Update CI queue state", tree: sha("c"), parents: [] });
  assert.deepEqual(requests[3].body, { ref: "refs/heads/vera-ci-queue-state", sha: sha("d") });
  assert.deepEqual(requests[6].body, { message: "Update CI queue state", tree: sha("c"), parents: [sha("a")] });
  assert.equal(requests[7].method, "PATCH");
  assert.equal(requests[7].path, "/repos/owner/project/git/refs/heads/vera-ci-queue-state");
  assert.deepEqual(requests[7].body, { sha: sha("d"), force: false });
});

test("rejects invalid state SHAs and state content larger than 1 MiB before writing", async () => {
  let requests = 0;
  const client = new GitHub({ repository, token: "token", fetchImpl: async () => { requests += 1; return jsonResponse({}); } });
  await assert.rejects(client.saveState({ version: 1 }, "bad-sha"), /previous state SHA/);
  await assert.rejects(client.saveState("x".repeat(1024 * 1024)), /exceeded 1 MiB/);
  assert.equal(requests, 0);
});
