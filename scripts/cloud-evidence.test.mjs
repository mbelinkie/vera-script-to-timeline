import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  controlDigestsFromEntries,
  evaluateCloudEvidence,
  EvidenceError,
  findVitestSkipMarkers,
  gatherGitHubFacts,
  JOB_NAME,
  nodeIdToJunitId,
  parseCollectOnly,
  parseJunit,
  parseLsTree,
  REQUIRED_STEPS,
  summarizePytest,
  VALIDATE_COMMAND,
} from "./cloud-evidence-lib.mjs";
import { main } from "./cloud-evidence-validate.mjs";

const REPOSITORY = "mbelinkie/vera-script-to-timeline";
const sha = (character) => character.repeat(40);
const HEAD = sha("a");
const BASE = sha("b");
const MERGE = sha("c");
const TREE = sha("d");
const RUN_ID = 5001;

const PYTEST_IDS = ["tests.test_fixtures.test_probe", "tests.test_fixtures.test_values[one]"];
const VITEST_IDS = ["packages/contracts/test/a.test.ts > parses"];

function treeEntries() {
  return [
    { path: ".github/workflows/validate.yml", type: "blob", sha: sha("1") },
    { path: "package.json", type: "blob", sha: sha("2") },
    { path: "uv.lock", type: "blob", sha: sha("3") },
    { path: "scripts/cloud-evidence-lib.mjs", type: "blob", sha: sha("4") },
    { path: "tests/conftest.py", type: "blob", sha: sha("5") },
    { path: "docs/notes.md", type: "blob", sha: sha("6") },
    { path: "tests", type: "tree", sha: sha("7") },
  ];
}

function scenario() {
  const controls = controlDigestsFromEntries(treeEntries());
  const runtime = {
    node: "v24.19.0",
    npm: "11.17.0",
    uv: "uv 0.12.5",
    python: "3.12.14",
    os: "ubuntu 24.04",
    arch: "x64/X64",
    runnerLabel: "ubuntu-24.04",
  };
  const media = {
    ffmpegVersion: "ffmpeg version 6.1.1-3ubuntu5",
    ffprobeVersion: "ffprobe version 6.1.1-3ubuntu5",
    ffmpegSha256: sha("e"),
    ffprobeSha256: sha("f"),
    capabilitiesDigest: sha("9"),
  };
  const runnerImage = { os: "ubuntu24", version: "20261005.1", kernel: "6.8.0" };
  return {
    expected: { repository: REPOSITORY, runId: RUN_ID, attempt: 2, event: "pull_request", pullRequest: 77, tree: TREE },
    profile: {
      schemaVersion: 1,
      qualified: true,
      approval: { by: "Producer", at: "2026-10-20", reference: "issue #196 comment" },
      command: VALIDATE_COMMAND,
      controls,
      tools: { runtime: { ...runtime }, media: { ...media }, runnerImage: { ...runnerImage } },
      acceptedRunnerImages: ["20261005.1"],
      skipAllowlist: [],
      inventory: { pytest: [...PYTEST_IDS], vitest: [...VITEST_IDS] },
    },
    run: {
      id: RUN_ID,
      name: "Validate",
      path: ".github/workflows/validate.yml",
      run_attempt: 2,
      event: "pull_request",
      status: "completed",
      conclusion: "success",
      head_sha: HEAD,
      html_url: `https://github.com/${REPOSITORY}/actions/runs/${RUN_ID}`,
      pull_requests: [{ number: 77 }],
      repository: { full_name: REPOSITORY },
      head_repository: { full_name: REPOSITORY },
    },
    jobs: [
      {
        name: JOB_NAME,
        run_id: RUN_ID,
        run_attempt: 2,
        head_sha: HEAD,
        status: "completed",
        conclusion: "success",
        labels: ["ubuntu-24.04"],
        runner_name: "GitHub Actions 1000",
        steps: [
          { name: "Set up job", conclusion: "success" },
          ...REQUIRED_STEPS.map((name) => ({ name, conclusion: "success" })),
          { name: "Complete job", conclusion: "success" },
        ],
      },
    ],
    commit: { sha: MERGE, tree: { sha: TREE }, parents: [{ sha: BASE }, { sha: HEAD }] },
    tree: { sha: TREE, truncated: false, tree: treeEntries() },
    history: [
      { runId: RUN_ID, attempt: 1, status: "completed", conclusion: "success" },
      { runId: RUN_ID, attempt: 2, status: "completed", conclusion: "success" },
    ],
    dispositions: [],
    manifest: {
      schemaVersion: 1,
      run: { id: RUN_ID, attempt: 2 },
      event: { name: "pull_request", pullRequest: { number: 77, headSha: HEAD, baseSha: BASE } },
      checkout: { commit: MERGE, tree: TREE },
      command: VALIDATE_COMMAND,
      stepOutcomes: { preflight: "success", validate: "success", lockfiles: "success" },
      controls: { ...controls },
      runner: { name: "GitHub Actions 1000" },
      tools: { runtime: { ...runtime }, media: { ...media }, runnerImage: { ...runnerImage } },
      inventory: {
        pytest: {
          ids: [...PYTEST_IDS],
          collectedIds: [...PYTEST_IDS],
          counts: { total: 2, passed: 2, failed: 0, errors: 0, skipped: 0 },
          notPassed: [],
        },
        vitest: { ids: [...VITEST_IDS], skipMarkers: [] },
      },
      collection: { complete: true, errors: [] },
    },
  };
}

function codes(report) {
  return report.failures.map((entry) => entry.code);
}

function assertRejected(mutate, code) {
  const input = scenario();
  mutate(input);
  const report = evaluateCloudEvidence(input);
  assert.equal(report.status, "fail");
  assert.deepEqual(report.suspendedScopes, ["all"]);
  assert.ok(codes(report).includes(code), `expected ${code}, got ${JSON.stringify(report.failures)}`);
  return report;
}

test("accepts complete evidence whose facts all come from GitHub and the qualified profile", () => {
  const report = evaluateCloudEvidence(scenario());
  assert.equal(report.status, "pass", JSON.stringify(report.failures));
  assert.deepEqual(report.suspendedScopes, []);
  assert.ok(report.limitations.some((entry) => entry.code === "outcome-by-step-only"));
});

test("an unqualified or unapproved profile never yields substitution", () => {
  assertRejected((input) => {
    input.profile.qualified = false;
  }, "profile-unqualified");
  assertRejected((input) => {
    input.profile.approval = null;
  }, "profile-unqualified");
});

test("rejects a tested tree that differs from the delivered tree", () => {
  assertRejected((input) => {
    input.expected.tree = sha("0");
  }, "wrong-tree");
});

test("rejects a stale tree listing and a manifest that misreports its checkout", () => {
  assertRejected((input) => {
    input.tree.sha = sha("0");
  }, "wrong-tree");
  assertRejected((input) => {
    input.manifest.checkout.tree = sha("0");
  }, "manifest-disagrees");
});

test("requires the PR merge commit of the run's head, and the head itself for push runs", () => {
  assertRejected((input) => {
    input.commit.parents = [{ sha: BASE }, { sha: sha("0") }];
  }, "not-pr-merge-commit");
  assertRejected((input) => {
    input.expected.event = "push";
    input.run.event = "push";
    input.manifest.event.name = "push";
  }, "wrong-tree");
  assertRejected((input) => {
    input.run.pull_requests = [{ number: 78 }];
  }, "wrong-pull-request");
});

test("rejects the wrong job or duplicated jobs", () => {
  assertRejected((input) => {
    input.jobs[0].name = "Lint only";
  }, "wrong-job");
  assertRejected((input) => {
    input.jobs.push({ ...input.jobs[0] });
  }, "wrong-job");
  assertRejected((input) => {
    input.jobs[0].runner_name = "other runner";
  }, "manifest-disagrees");
});

test("rejects evidence for a different attempt", () => {
  assertRejected((input) => {
    input.run.run_attempt = 1;
  }, "wrong-attempt");
  assertRejected((input) => {
    input.jobs[0].run_attempt = 1;
  }, "wrong-attempt");
  assertRejected((input) => {
    input.manifest.run.attempt = 1;
  }, "manifest-disagrees");
});

test("rejects nonzero, aborted and incomplete runs from GitHub's own conclusions", () => {
  for (const conclusion of ["failure", "cancelled", "timed_out"]) {
    assertRejected((input) => {
      input.run.conclusion = conclusion;
    }, "run-not-successful");
    assertRejected((input) => {
      input.jobs[0].conclusion = conclusion;
    }, "job-not-successful");
  }
  assertRejected((input) => {
    input.run.status = "in_progress";
    input.run.conclusion = null;
  }, "run-incomplete");
  assertRejected((input) => {
    input.jobs[0].steps.find((step) => step.name === "Run repository validation").conclusion = "skipped";
  }, "step-not-successful");
  assertRejected((input) => {
    input.jobs[0].steps = input.jobs[0].steps.filter((step) => step.name !== "Preflight required media tools");
  }, "missing-step");
  assertRejected((input) => {
    input.manifest.stepOutcomes.validate = "failure";
  }, "self-reported-failure");
});

test("rejects incomplete collection and missing inventory", () => {
  assertRejected((input) => {
    input.manifest.collection = { complete: false, errors: ["pytest JUnit: missing"] };
  }, "incomplete-collection");
  assertRejected((input) => {
    delete input.manifest.inventory.pytest;
  }, "incomplete-collection");
  assertRejected((input) => {
    input.manifest.inventory.pytest.ids = [PYTEST_IDS[0]];
    input.manifest.inventory.pytest.collectedIds = [PYTEST_IDS[0]];
  }, "incomplete-coverage");
  assertRejected((input) => {
    input.manifest.inventory.vitest.ids = [];
  }, "incomplete-coverage");
});

test("rejects unqualified skips, failures and reporter-altered collection", () => {
  const skipped = { id: PYTEST_IDS[0], outcome: "skipped", reason: "FFprobe is not installed" };
  assertRejected((input) => {
    input.manifest.inventory.pytest.notPassed = [skipped];
  }, "unqualified-skip");
  assertRejected((input) => {
    input.manifest.inventory.vitest.skipMarkers = [{ file: "packages/contracts/test/a.test.ts", marker: "it.skip" }];
  }, "unqualified-skip");
  assertRejected((input) => {
    input.manifest.inventory.pytest.counts.failed = 1;
  }, "tests-not-passed");
  assertRejected((input) => {
    input.manifest.inventory.pytest.collectedIds = [PYTEST_IDS[0]];
  }, "reporter-collection-mismatch");

  const allowed = scenario();
  allowed.manifest.inventory.pytest.notPassed = [skipped];
  allowed.profile.skipAllowlist = [{ id: PYTEST_IDS[0], reason: "approved exception" }];
  assert.equal(evaluateCloudEvidence(allowed).status, "pass");
});

test("a changed control cannot self-certify, even when the manifest repeats the qualified digests", () => {
  const report = assertRejected((input) => {
    input.tree.tree[0] = { ...input.tree.tree[0], sha: sha("8") };
  }, "control-drift");
  assert.ok(report.failures.some((entry) => entry.detail.startsWith(".github/workflows/validate.yml")));
  assertRejected((input) => {
    input.tree.tree.push({ path: "packages/contracts/vitest.config.ts", type: "blob", sha: sha("8") });
  }, "control-drift");
  assertRejected((input) => {
    input.manifest.command = "npm run validate:fast";
  }, "control-drift");
  // Non-control files may differ without touching the control set.
  const documentation = scenario();
  documentation.tree.tree[5] = { ...documentation.tree.tree[5], sha: sha("8") };
  assert.equal(evaluateCloudEvidence(documentation).status, "pass");
});

test("runtime drift fails everything; media drift suspends only media-sensitive scope", () => {
  assertRejected((input) => {
    input.manifest.tools.runtime.node = "v24.20.0";
  }, "runtime-drift");
  assertRejected((input) => {
    input.jobs[0].labels = ["ubuntu-26.04"];
  }, "runtime-drift");

  const media = scenario();
  media.manifest.tools.media.ffmpegSha256 = sha("0");
  const mediaReport = evaluateCloudEvidence(media);
  assert.equal(mediaReport.status, "pass");
  assert.deepEqual(mediaReport.suspendedScopes, ["media-sensitive"]);
  assert.ok(mediaReport.limitations.some((entry) => entry.code === "media-tool-drift"));

  const image = scenario();
  image.manifest.tools.runnerImage.version = "20261012.2";
  const imageReport = evaluateCloudEvidence(image);
  assert.deepEqual(imageReport.suspendedScopes, ["media-sensitive"]);
  assert.ok(imageReport.limitations.some((entry) => entry.code === "runner-image-changed"));
});

test("a later green attempt does not hide an unexplained earlier failure", () => {
  assertRejected((input) => {
    input.history[0].conclusion = "failure";
  }, "unresolved-prior-failure");
  assertRejected((input) => {
    input.history.push({ runId: 4999, attempt: 1, status: "completed", conclusion: "cancelled" });
  }, "unresolved-prior-failure");
  assertRejected((input) => {
    input.history[0].conclusion = "failure";
    input.dispositions = [{ runId: RUN_ID, attempt: 1, classification: "infrastructure", explanation: "", evidence: "x" }];
  }, "unresolved-prior-failure");
  assertRejected((input) => {
    input.history[0].conclusion = "failure";
    input.dispositions = [{ runId: RUN_ID, attempt: 1, classification: "latest-is-green", explanation: "x", evidence: "y" }];
  }, "unresolved-prior-failure");
  assertRejected((input) => {
    input.history.push({ runId: 5002, attempt: 1, status: "in_progress", conclusion: null });
  }, "sibling-run-incomplete");

  const resolved = scenario();
  resolved.history[0].conclusion = "failure";
  resolved.dispositions = [
    {
      runId: RUN_ID,
      attempt: 1,
      classification: "diagnosed-flake",
      explanation: "apt mirror timeout before tests started",
      evidence: "https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/5001/attempts/1",
    },
  ];
  const report = evaluateCloudEvidence(resolved);
  assert.equal(report.status, "pass");
  assert.ok(report.limitations.some((entry) => entry.code === "flake-disposition"));
});

test("fails closed on malformed or incomplete facts", () => {
  assertRejected((input) => {
    input.manifest = { schemaVersion: 99 };
  }, "malformed-manifest");
  assertRejected((input) => {
    input.profile = null;
  }, "malformed-profile");
  assertRejected((input) => {
    input.jobs = undefined;
  }, "incomplete-github-facts");
  assertRejected((input) => {
    input.tree.truncated = true;
  }, "incomplete-github-facts");
  assertRejected((input) => {
    input.run.head_repository = { full_name: "someone/fork" };
  }, "fork-unqualified");
  const input = scenario();
  input.expected.attempt = undefined;
  assert.throws(() => evaluateCloudEvidence(input), EvidenceError);
  const noPullRequest = scenario();
  delete noPullRequest.expected.pullRequest;
  assert.throws(() => evaluateCloudEvidence(noPullRequest), EvidenceError);
});

test("parses pytest JUnit identities, outcomes and skip reasons without failure text", () => {
  const cases = parseJunit(`<?xml version="1.0"?><testsuites><testsuite name="pytest" tests="4">
    <testcase classname="tests.test_fixtures" name="test_values[a&amp;b]" time="0.5"/>
    <testcase classname="tests.test_fixtures" name="test_probe" time="0.1"><skipped type="pytest.skip" message="FFprobe is not installed">x</skipped></testcase>
    <testcase classname="tests.test_x.TestA" name="test_fail" time="2"><failure message="secret-ish &lt;output&gt;">trace</failure></testcase>
    <testcase classname="tests.test_x" name="test_error" time="0"><error message="boom"/></testcase>
  </testsuite></testsuites>`);
  assert.deepEqual(
    cases.map(({ id, outcome, reason }) => [id, outcome, reason]),
    [
      ["tests.test_fixtures.test_values[a&b]", "passed", null],
      ["tests.test_fixtures.test_probe", "skipped", "FFprobe is not installed"],
      ["tests.test_x.TestA.test_fail", "failed", null],
      ["tests.test_x.test_error", "error", null],
    ],
  );
  const summary = summarizePytest(cases, ["tests/test_fixtures.py::test_values[a&b]"]);
  assert.deepEqual(summary.counts, { total: 4, passed: 1, failed: 1, errors: 1, skipped: 1 });
  assert.equal(JSON.stringify(summary).includes("secret-ish"), false);
  assert.throws(() => parseJunit("<html/>"), EvidenceError);
});

test("maps pytest node IDs to JUnit identities and reads collect-only output", () => {
  assert.equal(nodeIdToJunitId("tests/test_x.py::TestA::test_b[p/1.py]"), "tests.test_x.TestA.test_b[p/1.py]");
  assert.equal(nodeIdToJunitId("tests/test_y.py::test_c"), "tests.test_y.test_c");
  assert.deepEqual(parseCollectOnly("tests/test_y.py::test_c\ntests/test_y.py::test_d\n\n2 tests collected in 0.1s\n"), [
    "tests/test_y.py::test_c",
    "tests/test_y.py::test_d",
  ]);
  assert.throws(() => parseCollectOnly("\nno tests ran\n"), EvidenceError);
});

test("reads git ls-tree output into the same control digests GitHub's tree listing yields", () => {
  const listing = treeEntries()
    .map((entry) => `${entry.type === "tree" ? "040000" : "100644"} ${entry.type} ${entry.sha}\t${entry.path}`)
    .join("\n");
  const entries = parseLsTree(`${listing}\n100644 blob ${sha("0")}\tdocs/with space.md\n`);
  assert.equal(entries.at(-1).path, "docs/with space.md");
  assert.deepEqual(controlDigestsFromEntries(entries), controlDigestsFromEntries(treeEntries()));
  assert.deepEqual(Object.keys(controlDigestsFromEntries(entries)), [
    ".github/workflows/validate.yml",
    "package.json",
    "scripts/cloud-evidence-lib.mjs",
    "tests/conftest.py",
    "uv.lock",
  ]);
});

test("detects Vitest skip, todo and focus markers but not prose", () => {
  assert.deepEqual(findVitestSkipMarkers('it.skip("a"); test .todo("b"); describe.only("c"); xit("d"); it.skipIf(x)("e")'), [
    "it.skip",
    "test.todo",
    "describe.only",
    "xit(",
    "it.skipIf",
  ]);
  assert.deepEqual(findVitestSkipMarkers('it("validates excluded narration integrity but skips its coverage checks")'), []);
});

test("the workflow defines every required step, the exact command and the artifact name", () => {
  const workflow = readFileSync(new URL("../.github/workflows/validate.yml", import.meta.url), "utf8");
  const stepNames = [...workflow.matchAll(/^ {6}- name: (.+)$/gm)].map((match) => match[1]);
  for (const name of REQUIRED_STEPS) assert.ok(stepNames.includes(name), `workflow lacks step "${name}"`);
  assert.match(workflow, new RegExp(`^ {8}run: ${VALIDATE_COMMAND}$`, "m"));
  assert.match(workflow, /name: vera-validation-evidence-attempt-\$\{\{ github\.run_attempt \}\}/);
  assert.match(workflow, /^permissions:\n {2}contents: read\n/m);
  for (const match of workflow.matchAll(/uses: (\S+)/g)) assert.match(match[1], /@[0-9a-f]{40}$/);
});

function stubGitHub(input, extraRuns = []) {
  const requests = [];
  const responses = new Map([
    [`repos/${REPOSITORY}/actions/runs/${RUN_ID}/attempts/2`, input.run],
    [`repos/${REPOSITORY}/actions/runs/${RUN_ID}/attempts/2/jobs?per_page=100`, { jobs: input.jobs }],
    [`repos/${REPOSITORY}/actions/runs/${RUN_ID}/attempts/1`, { ...input.run, run_attempt: 1, conclusion: "failure" }],
    [`repos/${REPOSITORY}/git/commits/${MERGE}`, input.commit],
    [`repos/${REPOSITORY}/git/trees/${TREE}?recursive=1`, input.tree],
    [
      `repos/${REPOSITORY}/actions/workflows/validate.yml/runs?head_sha=${HEAD}&per_page=100`,
      { total_count: 1 + extraRuns.length, workflow_runs: [input.run, ...extraRuns] },
    ],
  ]);
  const getJson = async (endpoint) => {
    requests.push(endpoint);
    if (!responses.has(endpoint)) throw new Error(`unexpected request ${endpoint}`);
    return structuredClone(responses.get(endpoint));
  };
  return { getJson, requests };
}

test("gathers authoritative facts, including every earlier attempt, through read-only requests", async () => {
  const input = scenario();
  const { getJson, requests } = stubGitHub(input);
  const facts = await gatherGitHubFacts(getJson, { repository: REPOSITORY, runId: RUN_ID, attempt: 2, manifestCommit: MERGE });
  assert.deepEqual(
    facts.history.map(({ runId, attempt, conclusion }) => [runId, attempt, conclusion]),
    [
      [RUN_ID, 1, "failure"],
      [RUN_ID, 2, "success"],
    ],
  );
  assert.ok(requests.every((endpoint) => endpoint.startsWith(`repos/${REPOSITORY}/`)));
  const report = evaluateCloudEvidence({ ...input, ...facts });
  assert.ok(codes(report).includes("unresolved-prior-failure"));
});

test("refuses to evaluate a run history it could not read completely", async () => {
  const input = scenario();
  const { getJson } = stubGitHub(input);
  const truncated = async (endpoint) => {
    const response = await getJson(endpoint);
    return endpoint.includes("/workflows/") ? { ...response, total_count: 150 } : response;
  };
  await assert.rejects(
    gatherGitHubFacts(truncated, { repository: REPOSITORY, runId: RUN_ID, attempt: 2, manifestCommit: MERGE }),
    /incomplete history/,
  );
});

test("CLI exits nonzero for unresolved history and writes only unqualified draft profiles", async (t) => {
  const directory = mkdtempSync(path.join(os.tmpdir(), "vera-cloud-evidence-test-"));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const input = scenario();
  const files = Object.fromEntries(
    ["manifest", "profile"].map((name) => {
      const file = path.join(directory, `${name}.json`);
      writeFileSync(file, JSON.stringify(input[name]));
      return [name, file];
    }),
  );
  const common = ["--repo", REPOSITORY, "--run", String(RUN_ID), "--attempt", "2", "--manifest", files.manifest];
  const logs = [];
  const { getJson } = stubGitHub(input);
  const code = await main([...common, "--event", "pull_request", "--pr", "77", "--expected-tree", TREE, "--profile", files.profile], {
    getJson,
    log: (line) => logs.push(line),
  });
  assert.equal(code, 1);
  assert.ok(JSON.parse(logs[0]).failures.some((entry) => entry.code === "unresolved-prior-failure"));

  const dispositions = path.join(directory, "dispositions.json");
  writeFileSync(
    dispositions,
    JSON.stringify([{ runId: RUN_ID, attempt: 1, classification: "infrastructure", explanation: "runner lost", evidence: "link" }]),
  );
  const passing = await main(
    [...common, "--event", "pull_request", "--pr", "77", "--expected-tree", TREE, "--profile", files.profile, "--dispositions", dispositions],
    { getJson: stubGitHub(input).getJson, log: (line) => logs.push(line) },
  );
  assert.equal(passing, 0);
  assert.ok(JSON.parse(logs[1]).steps.some((step) => step.name === "Run repository validation"));

  const draftPath = path.join(directory, "draft.json");
  await main([...common, "--draft-profile", draftPath], { getJson: stubGitHub(input).getJson, log: () => {} });
  const draft = JSON.parse(readFileSync(draftPath, "utf8"));
  assert.equal(draft.qualified, false);
  assert.equal(draft.approval, null);
  assert.deepEqual(draft.controls, input.profile.controls);
  assert.deepEqual(draft.skipAllowlist, []);
});
