import assert from "node:assert/strict";
import { chmodSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const issueResponseBytes = (temporary) => Number(readFileSync(path.join(temporary, "response-bytes.txt"), "utf8"));

function inspectWithFakeGh(t, mode, historyBytes = 0) {
  const temporary = mkdtempSync(path.join(os.tmpdir(), "vera-roadmap-transport-154-"));
  t.after(() => rmSync(temporary, { recursive: true, force: true }));
  if (mode !== "missing") {
    const fakeGh = path.join(temporary, "gh");
    writeFileSync(
      fakeGh,
      `#!/usr/bin/env node
const fs = require("node:fs");
const args = process.argv.slice(2);
const query = args.find((value) => value.startsWith("query=")) || "";
if (process.env.FAKE_GH_MODE === "signal") {
  process.kill(process.pid, "SIGTERM");
} else if (process.env.FAKE_GH_MODE === "nonzero" && !query.includes("RoadmapRateLimit")) {
  process.stderr.write("fake gh failure");
  process.exit(7);
} else if (process.env.FAKE_GH_MODE === "overflow" && query.includes("RoadmapIssue")) {
  process.stdout.write(Buffer.alloc(32 * 1024 * 1024, "x"));
} else if (query.includes("RoadmapRateLimit")) {
  if (process.env.FAKE_GH_MODE === "rate-limit-nonzero") {
    process.stdout.write("HTTP/2 200 OK\\nX-RateLimit-Limit: 5000\\nX-RateLimit-Remaining: 0\\nX-RateLimit-Used: 5000\\nX-RateLimit-Reset: 1893456000\\nX-RateLimit-Resource: graphql\\n\\n{\\"data\\":null,\\"errors\\":[{\\"type\\":\\"RATE_LIMITED\\",\\"message\\":\\"API rate limit exceeded for GraphQL API\\"}]}");
    process.exitCode = 1;
  } else {
    process.stdout.write("HTTP/2 200 OK\\nX-RateLimit-Limit: 5000\\nX-RateLimit-Remaining: 50\\nX-RateLimit-Used: 4950\\nX-RateLimit-Reset: 1893456000\\nX-RateLimit-Resource: graphql\\n\\n{\\"data\\":{\\"rateLimit\\":{\\"limit\\":5000,\\"remaining\\":50,\\"used\\":4950,\\"resetAt\\":\\"2030-01-01T00:00:00Z\\",\\"cost\\":1}}}");
  }
} else if (query.includes("RoadmapIssueComments")) {
  const claim = JSON.stringify({state:"active",model:"gpt-6.1-sol",effort:"xhigh",task:"paged-claim-task",branch:"codex/paged-claim",startedAt:"2030-01-01T00:00:00.000Z"});
  const payload = {data:{repository:{issue:{comments:{nodes:[{body:"<!-- vera-claim " + claim + " -->"}],pageInfo:{hasPreviousPage:false,startCursor:null}}}}}};
  process.stdout.write(JSON.stringify(payload));
} else if (query.includes("RoadmapIssue")) {
  if (process.env.FAKE_GH_MODE === "invalid") {
    process.stdout.write("{\\"data\\":{\\"repository\\":");
    process.exit(0);
  }
  const paged = process.env.FAKE_GH_MODE === "paged-claim";
  const payload = {data:{repository:{escalationLabel:null,issue:{id:"issue-id",number:154,title:"Transport fixture",url:"https://github.com/mbelinkie/vera-script-to-timeline/issues/154",state:"OPEN",body:"## Acceptance criteria\\n\\n- [ ] Works\\n\\n## Dependencies\\n\\nNone",labels:{nodes:[{name:"model:luna"},{name:"effort:max"}]},comments:{nodes:[{body:"x".repeat(Number(process.env.FAKE_HISTORY_BYTES))}],pageInfo:{hasPreviousPage:paged,startCursor:paged ? "older-page" : null}},projectItems:{nodes:[{id:"item-id",project:{id:"project-id",number:2,title:"Roadmap"},fieldValueByName:{name:"Ready"},fieldValues:{nodes:[{name:"Ready",field:{name:"Status"}},{name:"Automated",field:{name:"Acceptance"}},{name:"S",field:{name:"Size"}}]}}]}}},user:{projectV2:{id:"project-id",number:2,title:"Roadmap",field:{id:"status-field",name:"Status",options:[{id:"ready",name:"Ready"}]}}}}};
  const response = JSON.stringify(payload);
  fs.writeFileSync(process.env.FAKE_GH_RESPONSE_BYTES, String(Buffer.byteLength(response)));
  process.stdout.write(response);
} else {
  process.stderr.write("unexpected fake gh request");
  process.exit(1);
}
`,
    );
    chmodSync(fakeGh, 0o755);
  }

  return {
    temporary,
    result: spawnSync(process.execPath, [path.join(repositoryRoot, "scripts", "roadmap.mjs"), "inspect", "154"], {
      cwd: repositoryRoot,
      encoding: "utf8",
      env: {
        ...process.env,
        PATH: `${temporary}${path.delimiter}${path.dirname(process.execPath)}`,
        FAKE_GH_MODE: mode,
        FAKE_HISTORY_BYTES: String(historyBytes),
        FAKE_GH_RESPONSE_BYTES: path.join(temporary, "response-bytes.txt"),
        VERA_ROADMAP_LOCK_PATH: path.join(temporary, "roadmap.lock"),
      },
    }),
  };
}

test("inspects a valid issue response larger than the old 1 MiB buffer", (t) => {
  const { temporary, result } = inspectWithFakeGh(t, "large", 2 * 1024 * 1024);
  assert.equal(result.status, 0, result.stderr.slice(0, 256));
  assert.ok(issueResponseBytes(temporary) > 1024 * 1024);
  const inspection = JSON.parse(result.stdout);
  assert.equal(inspection.issue.number, 154);
  assert.deepEqual(inspection.issue.labels.map(({ name }) => name), ["model:luna", "effort:max"]);
  assert.equal(inspection.project.status, "Ready");
  assert.equal(inspection.project.acceptance, "Automated");
  assert.deepEqual(inspection.dependencies, { valid: true, resolved: true, items: [] });
  assert.equal(inspection.claim, null);
});

test("finds the retained claim on an older page after a large initial history page", (t) => {
  const { temporary, result } = inspectWithFakeGh(t, "paged-claim", 2 * 1024 * 1024);
  assert.equal(result.status, 0, result.stderr.slice(0, 256));
  assert.ok(issueResponseBytes(temporary) > 1024 * 1024);
  const inspection = JSON.parse(result.stdout);
  assert.deepEqual(inspection.claim, {
    state: "active",
    model: "gpt-6.1-sol",
    effort: "xhigh",
    task: "paged-claim-task",
    branch: "codex/paged-claim",
    startedAt: "2030-01-01T00:00:00.000Z",
  });
});

test("reports bounded stdout overflow without parsing or printing partial JSON", (t) => {
  const { result } = inspectWithFakeGh(t, "overflow");
  assert.equal(result.status, 1);
  assert.match(result.stderr, /GitHub CLI output exceeded the 16 MiB limit/);
  assert.ok(result.stderr.length < 512);
  assert.doesNotMatch(result.stderr, /Unexpected end of JSON input|Unexpected token/);
  assert.equal(result.stdout, "");
});

test("rejects invalid JSON without returning a partial inspection", (t) => {
  const { result } = inspectWithFakeGh(t, "invalid");
  assert.equal(result.status, 1);
  assert.match(result.stderr, /JSON|property name|Unexpected token/i);
  assert.equal(result.stdout, "");
  assert.doesNotMatch(result.stderr, /Transport fixture|issue-id/);
});

test("preserves rate-limit reset guidance when gh exits nonzero", (t) => {
  const { result } = inspectWithFakeGh(t, "rate-limit-nonzero");
  assert.equal(result.status, 1);
  assert.match(result.stderr, /GitHub GraphQL budget is exhausted/);
  assert.match(result.stderr, /Do not retry before that reset \(2030-01-01T00:00:00\.000Z/);
  assert.doesNotMatch(result.stderr, /HTTP\/2 200 OK|RATE_LIMITED/);
});

test("reports spawn, exit, and signal failures clearly", async (t) => {
  const missing = inspectWithFakeGh(t, "missing");
  assert.equal(missing.result.status, 1);
  assert.match(missing.result.stderr, /Could not start GitHub CLI: spawnSync gh ENOENT/);

  const failed = inspectWithFakeGh(t, "nonzero");
  assert.equal(failed.result.status, 1);
  assert.match(failed.result.stderr, /fake gh failure/);

  const terminated = inspectWithFakeGh(t, "signal");
  assert.equal(terminated.result.status, 1);
  assert.match(terminated.result.stderr, /GitHub CLI was terminated by SIGTERM/);
});
