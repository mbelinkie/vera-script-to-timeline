import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { buildProgressModel, fetchProjectDocument, parseProjectItems, renderDashboard, terminalSummary } from "./project-progress-lib.mjs";
import { withRoadmapGraphqlGate } from "./roadmap-graphql-gate.mjs";
import { parseGraphqlRateLimitResponse } from "./roadmap-rate-limit.mjs";
import { parseGraphqlResponse } from "./roadmap-rate-limit.mjs";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const resetAt = "2026-09-01T18:00:00Z";

test("direct response parsing preserves the outer document in pretty-printed GraphQL pages", () => {
  const payload = { data: { project: { items: { nodes: [{ id: "first" }, { id: "last" }] } } } };
  assert.deepEqual(parseGraphqlResponse(`HTTP/2 200\n\n${JSON.stringify(payload, null, 2)}\ngh: diagnostic`), payload);
});

function directRateLimitResponse({ remaining = 40, retryAfter = null, restPayload = false } = {}) {
  const retryHeader = retryAfter === null ? "" : `Retry-After: ${retryAfter}\n`;
  const payload = restPayload
    ? JSON.stringify({ resources: { graphql: { limit: 5000, remaining, used: 5000 - remaining } } })
    : JSON.stringify({ data: { rateLimit: { limit: 5000, remaining, used: 5000 - remaining, resetAt, cost: 1 } } });
  return `HTTP/2 200 OK\nX-RateLimit-Limit: 5000\nX-RateLimit-Remaining: ${remaining}\nX-RateLimit-Used: ${5000 - remaining}\nX-RateLimit-Reset: 1788285600\n${retryHeader}\n${payload}`;
}

function fakeRunner(rateLimitOptions = {}) {
  const calls = [];
  const runGhResult = (args) => {
    calls.push(args);
    const query = args.find((value) => value.startsWith("query=")) ?? "";
    if (query.includes("RoadmapRateLimit")) {
      return { status: 0, stdout: directRateLimitResponse(rateLimitOptions), stderr: "" };
    }
    return { status: 0, stdout: JSON.stringify({ data: {
      viewer: { login: "bounded-reader" },
      rateLimit: { limit: 5000, remaining: 38, used: 4962, resetAt, cost: 2 },
    } }), stderr: "" };
  };
  return { calls, runGhResult };
}

function usingGate(runGhResult, callback) {
  const directory = mkdtempSync(path.join(os.tmpdir(), "vera-read-test-"));
  try {
    return withRoadmapGraphqlGate(callback, { runGhResult, lockOptions: { lockPath: path.join(directory, "lock") } });
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}

test("requires an accounted direct GraphQL preflight before each protected read", () => {
  const fake = fakeRunner();
  usingGate(fake.runGhResult, (gate) => {
  assert.throws(
    () => gate.query("projectItemsPage", "query Target { viewer { login } }"),
    /has no reserved GraphQL query/,
  );
  gate.reserve(["projectItemsPage"]);
  assert.equal(gate.query("projectItemsPage", "query Target { viewer { login } }").viewer.login, "bounded-reader");
  assert.throws(
    () => gate.query("projectItemsPage", "query Target { viewer { login } }"),
    /has no reserved GraphQL query/,
  );
  assert.equal(fake.calls.length, 2);
  assert.match(fake.calls[0].join(" "), /RoadmapRateLimit/);
  assert.match(fake.calls[1].join(" "), /query Target/);
  assert.throws(
    () => gate.restMutation(["api", "repos/example/project/issues/1"]),
    /REST only for explicit mutations.*live reads must use accounted GraphQL queries/,
  );
  });
});

test("failed target transport invalidates every reservation without a retry", () => {
  const fake = fakeRunner();
  usingGate((args) => args.some((arg) => arg.includes("query Target"))
    ? { status: 1, stdout: "", stderr: "Network unavailable" }
    : fake.runGhResult(args), (gate) => {
    gate.reserve(["issueProjectSnapshot", "dependencyBatch"]);
    assert.throws(() => gate.query("issueProjectSnapshot", "query Target { viewer { login } }"));
    assert.throws(() => gate.query("dependencyBatch", "query Next { viewer { login } }"), /no reserved/);
  });
  assert.equal(fake.calls.length, 1);
});

test("the read API rejects mutations before transport", () => {
  const fake = fakeRunner();
  usingGate(fake.runGhResult, (gate) => {
    gate.reserve(["projectItemsPage"]);
    assert.throws(() => gate.query("projectItemsPage", "mutation Nope { viewer { login } }"), /Expected one explicit GraphQL query/);
  });
  assert.equal(fake.calls.length, 1);
});

test("secondary throttle guidance does not require primary headers or JSON", () => {
  assert.throws(() => parseGraphqlRateLimitResponse("HTTP/2 403\nRetry-After: 60\n\nNot JSON"), /secondary.*at least 60s/);
  assert.throws(() => parseGraphqlRateLimitResponse(JSON.stringify({ errors: [{ message: "secondary rate limit" }] })), /secondary.*Wait at least 60s/);
  const rate = JSON.parse(directRateLimitResponse().split("\n\n")[1]).data.rateLimit;
  assert.doesNotThrow(() => parseGraphqlRateLimitResponse(JSON.stringify({ data: {
    rateLimit: rate, issue: { body: "Test secondary rate limit refusal and abuse detection" },
  } })));
  for (const missing of [null, undefined, "", true]) {
    assert.throws(() => parseGraphqlRateLimitResponse(JSON.stringify({ data: { rateLimit: { ...rate, remaining: missing } } })), /incomplete/);
  }
});

test("a retained gate cannot read after releasing its host lock", () => {
  const fake = fakeRunner();
  const gate = usingGate(fake.runGhResult, (activeGate) => activeGate);
  assert.throws(() => gate.rateLimit(), /no longer holds the host lock/);
  assert.equal(fake.calls.length, 0);
});

test("dashboard reserves two points for its nested connections, not one HTTP request", () => {
  const fake = fakeRunner({ remaining: 1 });
  usingGate(fake.runGhResult, (gate) => {
    assert.throws(() => gate.reserve(["projectItemsPage"]), /needs 2 point.*1 remain.*Safe retry/s);
  });
  assert.equal(fake.calls.length, 1);
});

test("a fresh reservation includes all still-unspent reserved work", () => {
  const fake = fakeRunner({ remaining: 2 });
  usingGate(fake.runGhResult, (gate) => {
    gate.reserve(["projectItemsPage"]);
    assert.throws(() => gate.reserve(["issueCommentPage"]), /needs 3 point.*2 remain/);
    assert.throws(() => gate.query("projectItemsPage", "query Target { viewer { login } }"), /no reserved/);
  });
  assert.equal(fake.calls.length, 2);
});

test("returned direct budget prevents the next reserved read after unexpected spending", () => {
  const fake = fakeRunner();
  const runGhResult = (args) => {
    if (args.some((value) => value.includes("query Target"))) {
      return { status: 0, stderr: "", stdout: JSON.stringify({ data: {
        rateLimit: { limit: 5000, remaining: 0, used: 5000, resetAt, cost: 40 }, viewer: { login: "ok" },
      } }) };
    }
    return fake.runGhResult(args);
  };
  usingGate(runGhResult, (gate) => {
    gate.reserve(["issueProjectSnapshot", "dependencyBatch"]);
    gate.query("issueProjectSnapshot", "query Target { viewer { login } }");
    assert.throws(() => gate.query("dependencyBatch", "query Next { viewer { login } }"), /Safe retry/);
  });
  assert.equal(fake.calls.length, 1);
});

test("shared host lock refuses contention before any GitHub request", () => {
  const temporary = mkdtempSync(path.join(os.tmpdir(), "vera-shared-read-gate-"));
  const lockPath = path.join(temporary, "roadmap.lock");
  const fake = fakeRunner();
  try {
    withRoadmapGraphqlGate(
      () => {
        assert.throws(
          () => withRoadmapGraphqlGate(() => {}, { lockOptions: { lockPath }, runGhResult: fake.runGhResult }),
          /Another VERA roadmap command is active.*no GitHub request was attempted/,
        );
      },
      { lockOptions: { lockPath }, runGhResult: fake.runGhResult },
    );
    assert.equal(fake.calls.length, 0);
  } finally {
    rmSync(temporary, { recursive: true, force: true });
  }
});

for (const [name, options, pattern] of [
  ["exhausted primary budget", { remaining: 0 }, /GraphQL budget is exhausted.*Do not retry before that reset/s],
  ["secondary throttle", { remaining: 40, retryAfter: 60 }, /secondary rate limit is active.*Do not retry for at least 60s/s],
  ["REST-derived pseudo-authority", { remaining: 40, restPayload: true }, /direct GraphQL rateLimit object/],
]) {
  test(`${name} refuses before the protected target query`, () => {
    const fake = fakeRunner(options);
    usingGate(fake.runGhResult, (gate) => {
      assert.throws(() => fetchProjectDocument({ owner: "mbelinkie", projectNumber: 2 }, gate), pattern);
    });
    assert.equal(fake.calls.length, 1);
    assert.match(fake.calls[0].join(" "), /RoadmapRateLimit/);
  });
}

function projectItem(number, status, type) {
  return {
    id: `item-${number}`,
    content: {
      __typename: "Issue",
      number,
      title: `Issue ${number}`,
      url: `https://example.test/${number}`,
      repository: { nameWithOwner: "mbelinkie/vera-script-to-timeline" },
      labels: { totalCount: 3, nodes: [{ name: "model:sol" }, { name: "effort:high" }, { name: `type:${type}` }] },
    },
    fieldValues: {
      totalCount: 5,
      nodes: [
        { name: status, field: { name: "Status" } },
        { name: "P1", field: { name: "Priority" } },
        { name: "M", field: { name: "Size" } },
        { name: "Operations", field: { name: "Workstream" } },
        { name: "Producer", field: { name: "Acceptance" } },
      ],
    },
  };
}

test("bounded Project pages preserve dashboard data and totals", () => {
  const pages = [
    {
      user: { projectV2: { id: "project-id", title: "Roadmap", items: {
        totalCount: 2,
        nodes: [projectItem(1, "Done", "goal")],
        pageInfo: { hasNextPage: true, endCursor: "page-2" },
      } } },
    },
    {
      user: { projectV2: { id: "project-id", title: "Roadmap", items: {
        totalCount: 2,
        nodes: [projectItem(2, "In progress", "implementation")],
        pageInfo: { hasNextPage: false, endCursor: null },
      } } },
    },
  ];
  const calls = [];
  const gate = {
    reserve(operationNames) {
      calls.push(["reserve", operationNames]);
    },
    query(operationName, query, variables) {
      calls.push(["query", operationName, query, variables]);
      return pages.shift();
    },
  };
  const document = fetchProjectDocument({ owner: "mbelinkie", projectNumber: 2 }, gate);
  const model = buildProgressModel(parseProjectItems(document));
  assert.equal(document.totalCount, 2);
  assert.equal(model.goals.length, 1);
  assert.equal(model.totalWork, 1);
  assert.equal(model.doneCount, 0);
  assert.equal(model.statusCounts["In progress"], 1);
  const legacyModel = buildProgressModel(parseProjectItems({ totalCount: 2, items: [1, 2].map((number) => ({
    content: { type: "Issue", number, title: `Issue ${number}`, url: `https://example.test/${number}` },
    labels: ["model:sol", "effort:high", number === 1 ? "type:goal" : "type:implementation"],
    status: number === 1 ? "Done" : "In progress",
    priority: "P1", size: "M", workstream: "Operations", acceptance: "Producer",
  })) }));
  assert.deepEqual(model, legacyModel);
  assert.equal(renderDashboard(model), renderDashboard(legacyModel));
  assert.equal(terminalSummary(model, "dashboard"), terminalSummary(legacyModel, "dashboard"));
  assert.deepEqual(calls.filter(([kind]) => kind === "reserve").map(([, operations]) => operations), [
    ["projectItemsPage"],
    ["projectItemsPage"],
  ]);
  assert.equal(calls.filter(([kind]) => kind === "query").length, 2);
  assert.deepEqual(calls.filter(([kind]) => kind === "query").map((call) => call[3].after), [null, "page-2"]);
});

test("bounded Project reads fail closed on truncated item metadata", () => {
  const item = projectItem(2, "Ready", "implementation");
  item.content.labels.totalCount += 1;
  const gate = {
    reserve() {},
    query() {
      return {
        user: { projectV2: { id: "project-id", items: {
          totalCount: 1,
          nodes: [item],
          pageInfo: { hasNextPage: false, endCursor: null },
        } } },
      };
    },
  };
  assert.throws(
    () => fetchProjectDocument({ owner: "mbelinkie", projectNumber: 2 }, gate),
    /labels exceed or violate the bounded metadata response/,
  );
});

test("Project pagination rejects incomplete, over-limit, changed, and non-progressing pages", () => {
  const page = (overrides = {}) => ({ totalCount: 1, nodes: [projectItem(2, "Ready", "implementation")],
    pageInfo: { hasNextPage: false, endCursor: null }, ...overrides });
  for (const [pages, pattern] of [
    [[page({ totalCount: 2 })], /incomplete/],
    [[page({ totalCount: 501 })], /bounded reader limit/],
    [[page({ totalCount: 2, pageInfo: { hasNextPage: true, endCursor: "next" } }), page({ totalCount: 3 })], /changed while/],
    [[page({ totalCount: 2, pageInfo: { hasNextPage: true, endCursor: "" } })], /forward progress/],
    [[page({ pageInfo: null })], /incomplete/],
  ]) {
    const gate = { reserve() {}, query() { return { user: { projectV2: { id: "project", items: pages.shift() } } }; } };
    assert.throws(() => fetchProjectDocument({ owner: "mbelinkie", projectNumber: 2 }, gate), pattern);
  }
});

test("a later dashboard page is refused when its fresh direct preflight is exhausted", () => {
  const calls = [];
  usingGate((args) => {
    const probe = args.some(arg => arg.includes("RoadmapRateLimit"));
    calls.push(probe ? "probe" : "page");
    if (probe) return { status: 0, stderr: "", stdout: directRateLimitResponse({ remaining: calls.length === 1 ? 40 : 0 }) };
    return { status: 0, stderr: "", stdout: JSON.stringify({ data: {
      rateLimit: { limit: 5000, remaining: 38, used: 4962, resetAt, cost: 2 },
      user: { projectV2: { id: "project", items: { totalCount: 2, nodes: [projectItem(2, "Ready", "implementation")],
        pageInfo: { hasNextPage: true, endCursor: "next" } } } },
    } }) };
  }, (gate) => {
    assert.throws(() => fetchProjectDocument({ owner: "mbelinkie", projectNumber: 2 }, gate), /exhausted/);
  });
  assert.deepEqual(calls, ["probe", "page", "probe"]);
});

function bypassesGate(source) {
  return /["']gh["']|\bgh\s+(?:api|issue|project)\b|api\.github\.com|["']api["']\s*,\s*["']graphql["']|["'](?:issue|project)["']\s*,\s*["'](?:view|list|item-list)["']/.test(source);
}

test("inventory detector catches alternate runtimes, hidden commands, and direct HTTP bypasses", () => {
  for (const source of [
    'execFileAsync("gh", ["project", "item-list"])',
    'const executable = "gh"; spawnSync(executable, args)',
    'subprocess.run(["gh", "issue", "view", "23"])',
    'gh api graphql -f query=...',
    'runGh(["api", "graphql", query])',
    'fetch("https://api.github.com/graphql")',
    'fetch("https://api.github.com/repos/owner/repo/issues/1")',
  ]) assert.equal(bypassesGate(source), true, source);
});

test("committed executable sources cannot bypass the shared live-read gate", (t) => {
  const files = execFileSync("git", ["ls-files", "-z"], { cwd: repositoryRoot, encoding: "utf8" })
    .split("\0")
    .filter(Boolean)
    .filter((file) => /\.(?:[mc]?js|tsx?|py|sh|command|ya?ml)$/.test(file) || /(?:^|\/)package\.json$/.test(file))
    .filter((file) => !/\.test\.|(?:^|\/)tests?\//.test(file) && file !== "scripts/roadmap-graphql-gate.mjs");
  const offenders = [];
  for (const file of files) {
    const source = readFileSync(path.join(repositoryRoot, file), "utf8");
    if (bypassesGate(source)) offenders.push(file);
  }
  assert.deepEqual(offenders, [], `Ungated live roadmap reader(s): ${offenders.join(", ")}`);
  t.diagnostic(`No ungated live roadmap reader in ${files.length} committed source, launcher, manifest, or workflow files.`);
});
