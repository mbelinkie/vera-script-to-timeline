import assert from "node:assert/strict";
import { chmodSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { assertDependenciesResolved, assertClaimAvailable, latestClaim, parseArguments, parseDependencies, validateRouting } from "./roadmap.mjs";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("parses commands and flags", () => {
  const parsed = parseArguments(["claim", "12", "--model", "gpt-5.6-terra", "--effort", "high"]);
  assert.equal(parsed.command, "claim");
  assert.deepEqual(parsed.positionals, ["12"]);
  assert.equal(parsed.flags.get("effort"), "high");
});

test("accepts one exact routing profile", () => {
  assert.deepEqual(validateRouting(["model:terra", "effort:high"], "gpt-5.6-terra", "high"), {
    expectedModel: "terra",
    expectedEffort: "high",
  });
});

test("rejects missing routing labels", () => {
  assert.throws(() => validateRouting(["effort:high"], "gpt-5.6-terra", "high"), /exactly one/);
});

test("rejects duplicate routing labels", () => {
  assert.throws(() => validateRouting(["model:luna", "model:terra", "effort:high"], "gpt-5.6-terra", "high"), /exactly one/);
});

test("rejects Luna claiming Terra work", () => {
  assert.throws(() => validateRouting(["model:terra", "effort:high"], "gpt-5.6-luna", "high"), /Profile mismatch/);
});

test("rejects Sol claiming Luna work", () => {
  assert.throws(() => validateRouting(["model:luna", "effort:low"], "gpt-5.6-sol", "low"), /Profile mismatch/);
});

test("rejects unsupported effort labels", () => {
  assert.throws(() => validateRouting(["model:terra", "effort:ultra"], "gpt-5.6-terra", "ultra"), /unsupported/);
});

test("uses the latest claim marker", () => {
  const comments = [{ body: '<!-- vera-claim {"state":"active","task":"one"} -->' }, { body: '<!-- vera-claim {"state":"released","task":"one"} -->' }];
  assert.equal(latestClaim(comments).state, "released");
  assert.doesNotThrow(() => assertClaimAvailable(comments));
  assert.throws(() => assertClaimAvailable([{ body: '<!-- vera-claim {"state":"active","task":"task-one"} -->' }]), /already claimed by task-one/);
});

test("preserves exclusive ownership across Luna-to-Terra and Terra-to-Sol escalation markers", () => {
  const comments = [
    {
      body: '<!-- vera-claim {"state":"active","model":"gpt-5.6-luna","task":"luna-task"} -->',
    },
    {
      body: 'Confirmed evidence: scope exceeded.\n<!-- vera-claim {"state":"released","model":"gpt-5.6-luna","task":"luna-task"} -->',
    },
    {
      body: '<!-- vera-claim {"state":"active","model":"gpt-5.6-terra","task":"terra-task"} -->',
    },
    {
      body: 'Confirmed evidence: architecture boundary found.\n<!-- vera-claim {"state":"released","model":"gpt-5.6-terra","task":"terra-task"} -->',
    },
    {
      body: '<!-- vera-claim {"state":"active","model":"gpt-5.6-sol","task":"sol-task"} -->',
    },
  ];

  assert.deepEqual(latestClaim(comments), {
    state: "active",
    model: "gpt-5.6-sol",
    task: "sol-task",
  });
  assert.throws(() => assertClaimAvailable(comments), /already claimed by sol-task/);
});

test("parses no dependencies and same-repository blockers", () => {
  assert.deepEqual(parseDependencies("## Dependencies\n\nNone", "owner/repo"), []);
  assert.deepEqual(parseDependencies("## Dependencies\n\n- Blocked by #12\n- Blocked by #13", "owner/repo"), [
    { repository: "owner/repo", number: 12 },
    { repository: "owner/repo", number: 13 },
  ]);
});

test("parses cross-roadmap dependency references", () => {
  assert.deepEqual(
    parseDependencies(
      "### Dependencies\n\n- Blocked by mbelinkie/vera-script-to-timeline#13\n- Blocked by https://github.com/mbelinkie/vera-research-video-clips/issues/14",
      "owner/repo",
    ),
    [
      { repository: "mbelinkie/vera-script-to-timeline", number: 13 },
      { repository: "mbelinkie/vera-research-video-clips", number: 14 },
    ],
  );
});

test("rejects prose and duplicate dependency declarations", () => {
  assert.throws(() => parseDependencies("## Dependencies\n\nComplete the design first.", "owner/repo"), /must use/);
  assert.throws(() => parseDependencies("## Dependencies\n\n- Blocked by #12\n- Blocked by #12", "owner/repo"), /duplicates/);
});

test("requires every dependency to be closed and Done", () => {
  const resolved = {
    repository: "owner/repo",
    number: 12,
    issueState: "CLOSED",
    projectStatus: "Done",
    resolved: true,
  };
  assert.deepEqual(assertDependenciesResolved([resolved]), [resolved]);
  assert.throws(
    () =>
      assertDependenciesResolved([
        {
          ...resolved,
          number: 13,
          issueState: "OPEN",
          projectStatus: "In review",
          resolved: false,
        },
        {
          ...resolved,
          number: 14,
          issueState: "CLOSED",
          projectStatus: "In review",
          resolved: false,
        },
      ]),
    /owner\/repo#13 \(OPEN\/In review\).*owner\/repo#14 \(CLOSED\/In review\)/,
  );
});

test("inspect, ready, and claim preflight before GraphQL reads and again before mutation", (t) => {
  const temporary = mkdtempSync(path.join(os.tmpdir(), "vera-roadmap-preflight-test-"));
  t.after(() => rmSync(temporary, { recursive: true, force: true }));
  const fakeGh = path.join(temporary, "gh");
  const logPath = path.join(temporary, "calls.log");
  const fakeSource = `#!/usr/bin/env node
const fs = require("node:fs");
const args = process.argv.slice(2);
fs.appendFileSync(process.env.FAKE_GH_LOG, JSON.stringify(args) + "\\n");
const query = args.find((value) => value.startsWith("query=")) || "";
if (query.includes("RoadmapRateLimit")) {
  process.stdout.write('HTTP/2 200 OK\\nX-RateLimit-Limit: 5000\\nX-RateLimit-Remaining: 50\\nX-RateLimit-Used: 4950\\nX-RateLimit-Reset: 1788215569\\nX-RateLimit-Resource: graphql\\n\\n{"data":{"rateLimit":{"limit":5000,"remaining":50,"used":4950,"resetAt":"2026-08-31T22:32:49Z","cost":1}}}');
} else if (query.includes("RoadmapIssue")) {
  const status = process.env.FAKE_ROADMAP_STATUS;
  process.stdout.write(JSON.stringify({data:{repository:{issue:{id:"issue-id",number:23,title:"Test issue",url:"https://github.com/mbelinkie/vera-script-to-timeline/issues/23",state:"OPEN",body:"## Acceptance criteria\\n\\n- [ ] Works\\n\\n## Dependencies\\n\\nNone",labels:{nodes:[{name:"model:sol"},{name:"effort:high"}]},comments:{nodes:[]},projectItems:{nodes:[{id:"item-id",project:{id:"project-id",number:2,title:"Roadmap"},fieldValues:{nodes:[{name:status,field:{name:"Status"}}]}}]}}},user:{projectV2:{id:"project-id",number:2,title:"Roadmap",field:{id:"status-field",name:"Status",options:[{id:"ready-option",name:"Ready"},{id:"progress-option",name:"In progress"}]}}},rateLimit:{limit:5000,remaining:49,used:4951,resetAt:"2026-08-31T22:32:49Z",cost:1}}}));
} else if (query.includes("RoadmapLifecycle")) {
  process.stdout.write('{"data":{"status":{"projectV2Item":{"id":"item-id"}}}}');
} else if (args[0] === "api" && args[1] === "rate_limit") {
  process.stdout.write('{"limit":5000,"remaining":50,"used":4950,"reset":1788215569}');
} else if (args[0] === "issue" && args[1] === "comment") {
  process.stdout.write("https://example.invalid/comment");
} else {
  process.stderr.write("Unexpected fake gh call: " + JSON.stringify(args));
  process.exitCode = 1;
}
`;
  writeFileSync(fakeGh, fakeSource);
  chmodSync(fakeGh, 0o755);

  const run = (command, status) => {
    writeFileSync(logPath, "");
    const lockPath = path.join(temporary, `${command[0]}.lock`);
    const result = spawnSync(process.execPath, [path.join(repositoryRoot, "scripts", "roadmap.mjs"), ...command], {
      cwd: repositoryRoot,
      encoding: "utf8",
      env: {
        ...process.env,
        PATH: `${temporary}${path.delimiter}${process.env.PATH}`,
        FAKE_GH_LOG: logPath,
        FAKE_ROADMAP_STATUS: status,
        VERA_ROADMAP_LOCK_PATH: lockPath,
      },
    });
    assert.equal(result.status, 0, result.stderr);
    return readFileSync(logPath, "utf8").trim().split("\n").map(JSON.parse);
  };

  const inspectCalls = run(["inspect", "23"], "Ready");
  assert.match(inspectCalls[0].join(" "), /RoadmapRateLimit/);
  assert.match(inspectCalls[1].join(" "), /RoadmapIssue/);

  const readyCalls = run(["ready", "23"], "Ready");
  assert.match(readyCalls[0].join(" "), /RoadmapRateLimit/);
  assert.match(readyCalls[1].join(" "), /RoadmapIssue/);
  assert.match(readyCalls[2].join(" "), /RoadmapRateLimit/);
  assert.match(readyCalls.at(-1).join(" "), /RoadmapLifecycle/);

  const claimCalls = run(
    ["claim", "23", "--model", "gpt-5.6-sol", "--effort", "high", "--task", "test-task", "--branch", "codex/test"],
    "Ready",
  );
  assert.match(claimCalls[0].join(" "), /RoadmapRateLimit/);
  assert.match(claimCalls[1].join(" "), /RoadmapIssue/);
  assert.match(claimCalls[2].join(" "), /RoadmapRateLimit/);
  const lifecycleIndex = claimCalls.findIndex((args) => args.join(" ").includes("RoadmapLifecycle"));
  assert.equal(lifecycleIndex, 3);
  assert.equal(claimCalls.some((args) => args[0] === "issue"), false);
});
