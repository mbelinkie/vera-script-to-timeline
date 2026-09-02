import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { chmodSync, existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { acquireRoadmapLock } from "./roadmap-lock.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const fakeSource = `#!/usr/bin/env node
const fs = require("node:fs");
const args = process.argv.slice(2);
const scenario = JSON.parse(process.env.GATE_TEST_SCENARIO);
const query = args.find(arg => arg.startsWith("query=")) || "";
const operation = query.match(/(?:query|mutation) (\\w+)/)?.[1] || "REST";
fs.appendFileSync(process.env.GATE_TEST_LOG, JSON.stringify({operation, args, locked: fs.existsSync(process.env.VERA_ROADMAP_LOCK_PATH)}) + "\\n");
const rateLimit = {limit:5000, remaining:50, used:4950, resetAt:"2030-01-01T00:00:00Z", cost:1};
const statuses = ["Inbox", "Backlog", "Ready", "In progress", "Blocked", "In review", "Done"];
const project = {id:"project",number:2,title:"Roadmap",field:{id:"status",options:statuses.map(name=>({id:name,name}))}};
let data;
if (operation === "RoadmapRateLimit") {
  if (scenario.refuse === "exhausted") rateLimit.remaining = 0;
  if (scenario.refuse === "secondary") process.stdout.write("HTTP/2 403\\nRetry-After: 60\\n\\n");
  data = {rateLimit};
} else if (operation === "RoadmapIssue") {
  const dependencyLines = Array.from({length:scenario.dependencies || 0}, (_, i) => "- Blocked by #" + (i + 1000));
  const body = "## Acceptance criteria\\n\\n- [ ] Works\\n\\n## Dependencies\\n\\n" + (dependencyLines.join("\\n") || "None");
  const comments = scenario.olderComments ? {nodes:[],pageInfo:{hasPreviousPage:true,startCursor:"older"}} : {nodes:[]};
  data = {repository:{escalationLabel:{id:"escalation"},issue:{id:"issue",number:30,title:"Issue",url:"https://example.test/30",state:"OPEN",body,
    labels:{nodes:[{name:"model:sol"},{name:"effort:high"}]},comments,
    projectItems:{nodes:[{id:"item",project,fieldValueByName:{name:scenario.status || "Ready"},fieldValues:{nodes:[]}}]}}},user:{projectV2:project},rateLimit};
} else if (operation === "RoadmapIssueComments") {
  data = {repository:{issue:{comments:{nodes:[{body:'<!-- vera-claim {"state":"released","task":"old-task"} -->'}],pageInfo:{hasPreviousPage:false}}}},rateLimit};
} else if (operation === "RoadmapDependencies") {
  data = {rateLimit};
  for (const match of query.matchAll(/dependency(\\d+): repository/g)) {
    data["dependency" + match[1]] = {issue:{title:"Dependency",url:"https://example.test/dependency",state:scenario.unresolved ? "OPEN" : "CLOSED",projectItems:{nodes:[{project:{number:2},fieldValueByName:{name:"Done"}}]}}};
  }
} else if (operation === "RoadmapProject") {
  data = {user:{projectV2:project},rateLimit};
} else if (operation === "RoadmapParentIssue") {
  data = {repository:{issue:{id:"parent"}},rateLimit};
} else if (operation === "AddRoadmapItem") {
  data = {addProjectV2ItemById:{item:{id:"created-item"}}};
} else if (operation === "RoadmapLifecycle" || operation === "LinkSubIssue") {
  data = {ok:true};
} else if (operation === "REST" && args[1] === "rate_limit") {
  process.stdout.write(JSON.stringify({limit:5000,remaining:50,used:4950,reset:1893456000}));
  process.exit(0);
} else if (operation === "REST" && args[1] === "-X" && args[2] === "POST" && args[3].endsWith("/issues")) {
  process.stdout.write(JSON.stringify({node_id:"created-issue",html_url:"https://example.test/31",number:31}));
  process.exit(0);
} else {
  process.stderr.write("Unexpected GitHub transport " + JSON.stringify(args));
  process.exit(1);
}
process.stdout.write(JSON.stringify({data}));
`;

function harness(t) {
  const directory = mkdtempSync(path.join(os.tmpdir(), "vera-gate-entrypoint-"));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const gh = path.join(directory, "gh");
  writeFileSync(gh, fakeSource);
  chmodSync(gh, 0o755);
  const bodyFile = path.join(directory, "issue.md");
  writeFileSync(bodyFile, "## Acceptance criteria\n\n- [ ] Works\n\n## Dependencies\n\nNone");
  const lockPath = path.join(directory, "lock");
  const logPath = path.join(directory, "calls.jsonl");
  const run = (args, scenario = {}, script = "roadmap.mjs") => {
    writeFileSync(logPath, "");
    const result = spawnSync(process.execPath, [path.join(root, "scripts", script), ...args], {
      cwd: root, encoding: "utf8",
      env: { ...process.env, PATH: `${directory}${path.delimiter}${process.env.PATH}`, GATE_TEST_LOG: logPath,
        GATE_TEST_SCENARIO: JSON.stringify(scenario), VERA_ROADMAP_LOCK_PATH: lockPath },
    });
    const calls = readFileSync(logPath, "utf8").split("\n").filter(Boolean).map(JSON.parse);
    assert.ok(calls.every(call => call.locked), "Every request must hold the shared host lock");
    return { ...result, calls, operations: calls.map(call => call.operation) };
  };
  return { run, bodyFile, lockPath };
}

test("CLI and dashboard entry points refuse exhaustion and secondary throttling before target reads", (t) => {
  const { run } = harness(t);
  for (const script of ["roadmap.mjs", "project-progress.mjs"]) {
    for (const refuse of ["exhausted", "secondary"]) {
      const result = run(script === "roadmap.mjs" ? ["inspect", "23"] : [], { refuse }, script);
      assert.equal(result.status, 1);
      assert.match(result.stderr, /Do not retry/);
      assert.deepEqual(result.operations, ["RoadmapRateLimit"]);
    }
  }
});

test("both entry points share the host lock and do no GitHub work during contention", (t) => {
  const { run, lockPath } = harness(t);
  const release = acquireRoadmapLock({ lockPath });
  try {
    for (const script of ["roadmap.mjs", "project-progress.mjs"]) {
      const result = run(script === "roadmap.mjs" ? ["inspect", "23"] : [], {}, script);
      assert.equal(result.status, 1);
      assert.match(result.stderr, /Another VERA roadmap command is active/);
      assert.deepEqual(result.calls, []);
    }
  } finally {
    release();
  }
});

test("inspection accounts for older claim pages and bounded dependency batches", (t) => {
  const { run, lockPath } = harness(t);
  const result = run(["inspect", "30"], { dependencies: 101, olderComments: true });
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.dependencies.items.length, 101);
  assert.equal(output.dependencies.resolved, true);
  assert.equal(output.claim.task, "old-task");
  assert.deepEqual(result.operations, ["RoadmapRateLimit", "RoadmapIssue", "RoadmapRateLimit", "RoadmapIssueComments",
    "RoadmapDependencies", "RoadmapRateLimit", "RoadmapDependencies"]);
  assert.equal(existsSync(lockPath), false);
});

test("lifecycle commands retain their status, routing, dependency, and acceptance behavior", (t) => {
  const { run } = harness(t);
  for (const [command, flags, status] of [
    ["ready", [], "Ready"],
    ["claim", ["--model", "gpt-5.6-sol", "--effort", "high", "--task", "test", "--branch", "codex/test"], "In progress"],
    ["block", ["--evidence", "test"], "Blocked"],
    ["escalate", ["--evidence", "test", "--recommend-model", "sol", "--recommend-effort", "xhigh"], "Blocked"],
    ["review", ["--evidence", "test"], "In review"],
    ["complete", ["--evidence", "test", "--accepted-by", "test producer"], "Done"],
  ]) {
    const result = run([command, "30", ...flags], { dependencies: 1 });
    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(result.operations.slice(-2), ["RoadmapRateLimit", "RoadmapLifecycle"]);
    const args = result.calls.at(-1).args;
    assert.ok(args.includes(`optionId=${status}`));
    assert.ok(args.includes(`closeIssue=${command === "complete"}`));
  }
  const unresolved = run(["ready", "30"], { dependencies: 1, unresolved: true });
  assert.equal(unresolved.status, 1);
  assert.match(unresolved.stderr, /Unresolved dependencies/);
  assert.equal(unresolved.operations.includes("RoadmapLifecycle"), false);
});

test("create with parent uses a targeted accounted GraphQL parent lookup and preserves Inbox creation", (t) => {
  const { run, bodyFile } = harness(t);
  const result = run(["create", "--title", "Test", "--body-file", bodyFile, "--model", "sol", "--effort", "high", "--parent", "2"]);
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(result.operations, ["RoadmapRateLimit", "RoadmapProject", "RoadmapParentIssue", "RoadmapRateLimit", "REST", "REST",
    "AddRoadmapItem", "RoadmapLifecycle", "LinkSubIssue"]);
  assert.ok(result.calls.find(call => call.operation === "RoadmapLifecycle").args.includes("optionId=Inbox"));
  assert.ok(result.calls.at(-1).args.includes("parent=parent"));
  assert.match(result.stdout, /https:\/\/example.test\/31/);
});
