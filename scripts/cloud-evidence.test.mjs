import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { collectEvidence } from "./cloud-evidence-collect.mjs";
import {
  controlDigestsFromEntries,
  evaluateCloudEvidence,
  EvidenceError,
  gatherGitHubFacts,
  isControlPath,
  JOB_NAME,
  nodeIdToJunitId,
  numberDuplicateIds,
  parseCollectOnly,
  parseJunit,
  parseLsTree,
  parsePorcelain,
  parseValidateLog,
  profileDigest,
  profileProblems,
  REQUIRED_STEPS,
  scopeAccepted,
  summarizePytest,
  VALIDATE_COMMAND,
} from "./cloud-evidence-lib.mjs";
import { main, parseArguments } from "./cloud-evidence-validate.mjs";

const REPOSITORY = "mbelinkie/vera-script-to-timeline";
const sha = (character) => character.repeat(40);
const HEAD = sha("a");
const BASE = sha("b");
const MERGE = sha("c");
const TREE = sha("d");
const HEAD_TREE = sha("5");
const RUN_ID = 5001;

const PYTEST_IDS = ["tests.test_fixtures.test_probe", "tests.test_fixtures.test_values[one]"];
const VITEST_IDS = ["packages/contracts/test/a.test.ts > parses"];
const NODE_COMMAND = "node --test scripts/roadmap.test.mjs";
const NODE_IDS = ["uses the latest claim marker"];

function treeEntries() {
  return [
    { path: ".github/workflows/validate.yml", type: "blob", sha: sha("1") },
    { path: "package.json", type: "blob", sha: sha("2") },
    { path: "uv.lock", type: "blob", sha: sha("3") },
    { path: "scripts/cloud-evidence-lib.mjs", type: "blob", sha: sha("4") },
    { path: "tests/conftest.py", type: "blob", sha: sha("6") },
    { path: "output/ruff.toml", type: "blob", sha: sha("8") },
    { path: "docs/notes.md", type: "blob", sha: sha("9") },
    { path: "tests", type: "tree", sha: sha("7") },
  ];
}

function approve(profile) {
  profile.qualified = true;
  profile.approval = { by: "Producer", at: "2026-10-20", reference: "#196 activation comment", profileDigest: profileDigest(profile) };
  return profile;
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
    ffmpegSha256: "e".repeat(64),
    ffprobeSha256: "f".repeat(64),
    capabilitiesDigest: "9".repeat(64),
  };
  const runnerImage = { os: "ubuntu24", version: "20261005.1", kernel: "6.8.0" };
  const profile = approve({
    schemaVersion: 2,
    command: VALIDATE_COMMAND,
    calibration: {
      runs: [
        { runId: 4000, attempt: 1, tree: TREE },
        { runId: 4000, attempt: 2, tree: TREE },
      ],
    },
    controls,
    tools: { runtime: { ...runtime }, media: { ...media }, runnerImage: { ...runnerImage } },
    acceptedRunnerImages: ["20261005.1"],
    skipAllowlist: [],
    inventory: { pytest: [...PYTEST_IDS], vitest: [...VITEST_IDS], node: NODE_IDS.map((id) => `${NODE_COMMAND} > ${id}`) },
  });
  return {
    expected: { repository: REPOSITORY, runId: RUN_ID, attempt: 2, event: "pull_request", pullRequest: 77, tree: TREE },
    profile,
    run: {
      id: RUN_ID,
      name: "Validate",
      path: ".github/workflows/validate.yml",
      run_attempt: 2,
      event: "pull_request",
      status: "completed",
      conclusion: "success",
      head_sha: HEAD,
      head_branch: "claude/issue-196-cloud-validation-prep",
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
      schemaVersion: 2,
      repository: REPOSITORY,
      run: { id: RUN_ID, attempt: 2 },
      event: { name: "pull_request", pullRequest: { number: 77, headSha: HEAD, baseSha: BASE } },
      checkout: { commit: MERGE, tree: TREE },
      trackedState: { modified: [] },
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
        vitest: { ids: [...VITEST_IDS] },
      },
      outcomes: {
        vitest: [{ total: 1, passed: 1 }],
        node: [{ command: NODE_COMMAND, ids: [...NODE_IDS], counts: { tests: 1, pass: 1, fail: 0, cancelled: 0, skipped: 0, todo: 0 } }],
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
  assert.equal(report.profileDigest, scenario().profile.approval.profileDigest);
  assert.ok(report.limitations.some((entry) => entry.code === "outcome-by-step-only"));
  assert.ok(report.limitations.some((entry) => entry.code === "checkout-attested"));
});

test("an unqualified, unbound or edited profile never yields substitution", () => {
  assertRejected((input) => {
    input.profile.qualified = false;
  }, "profile-unqualified");
  assertRejected((input) => {
    input.profile.approval = {};
  }, "profile-unqualified");
  assertRejected((input) => {
    input.profile.approval.reference = " ";
  }, "profile-unqualified");
  // Editing any qualified content after approval breaks the approval binding.
  assertRejected((input) => {
    input.profile.skipAllowlist.push({ id: PYTEST_IDS[0], reason: "added later" });
  }, "profile-unqualified");
});

test("rejects malformed profiles before they can judge a run", () => {
  for (const runner of ["pytest", "vitest", "node"]) {
    assertRejected((input) => {
      input.profile.inventory[runner] = [];
      approve(input.profile);
    }, "malformed-profile");
  }
  assertRejected((input) => {
    input.profile.inventory.pytest = [PYTEST_IDS[0], PYTEST_IDS[0]];
    approve(input.profile);
  }, "malformed-profile");
  assertRejected((input) => {
    delete input.profile.controls[".github/workflows/validate.yml"];
    approve(input.profile);
  }, "malformed-profile");
  assertRejected((input) => {
    input.profile.command = "npm run validate:fast";
    approve(input.profile);
  }, "malformed-profile");
  assertRejected((input) => {
    input.profile.tools.media.ffmpegSha256 = "";
    approve(input.profile);
  }, "malformed-profile");
  assertRejected((input) => {
    input.profile.calibration = { runs: [] };
    approve(input.profile);
  }, "malformed-profile");
  // Qualification needs two distinct complete runs on the same tree.
  for (const runs of [
    [{ runId: 4000, attempt: 1, tree: TREE }],
    [
      { runId: 4000, attempt: 1, tree: TREE },
      { runId: 4000, attempt: 1, tree: TREE },
    ],
    [
      { runId: 4000, attempt: 1, tree: TREE },
      { runId: 4001, attempt: 1, tree: sha("0") },
    ],
  ]) {
    assertRejected((input) => {
      input.profile.calibration = { runs };
      approve(input.profile);
    }, "profile-unqualified");
  }
  assert.deepEqual(profileProblems(scenario().profile), []);
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
  assertRejected((input) => {
    input.manifest.repository = "someone/else";
  }, "manifest-disagrees");
});

test("rejects a gate that changed tracked files or did not record that state", () => {
  assertRejected((input) => {
    input.manifest.trackedState.modified = ["fixtures/golden.json"];
  }, "tracked-state-changed");
  assertRejected((input) => {
    input.manifest.trackedState = { modified: null };
  }, "incomplete-collection");
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
  const moved = scenario();
  moved.manifest.event.pullRequest.baseSha = sha("0");
  const report = evaluateCloudEvidence(moved);
  assert.equal(report.status, "pass");
  assert.ok(report.limitations.some((entry) => entry.code === "pr-base-moved"));
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

test("rejects incomplete collection and missing or empty inventory", () => {
  assertRejected((input) => {
    input.manifest.collection = { complete: false, errors: ["pytest JUnit: missing"] };
  }, "incomplete-collection");
  assertRejected((input) => {
    delete input.manifest.inventory.pytest;
  }, "incomplete-collection");
  assertRejected((input) => {
    input.manifest.inventory.pytest.ids = [];
    input.manifest.inventory.pytest.collectedIds = [];
  }, "incomplete-collection");
  assertRejected((input) => {
    input.manifest.inventory.pytest.ids = [PYTEST_IDS[0]];
    input.manifest.inventory.pytest.collectedIds = [PYTEST_IDS[0]];
    input.manifest.inventory.pytest.counts.total = 1;
  }, "incomplete-coverage");
  assertRejected((input) => {
    input.manifest.inventory.vitest.ids = [];
  }, "incomplete-collection");
  assertRejected((input) => {
    input.manifest.outcomes.node = [];
  }, "incomplete-collection");
  assertRejected((input) => {
    input.manifest.outcomes.node[0].ids = [];
    input.manifest.outcomes.node[0].counts = { tests: 0, pass: 0 };
  }, "incomplete-coverage");
});

test("rejects unqualified pytest skips, failures and reporter-altered collection", () => {
  const skipped = { id: PYTEST_IDS[0], outcome: "skipped", reason: "FFprobe is not installed" };
  assertRejected((input) => {
    input.manifest.inventory.pytest.notPassed = [skipped];
  }, "unqualified-skip");
  assertRejected((input) => {
    input.manifest.inventory.pytest.counts.failed = 1;
  }, "tests-not-passed");
  assertRejected((input) => {
    input.manifest.inventory.pytest.collectedIds = [PYTEST_IDS[0]];
  }, "reporter-collection-mismatch");

  assertRejected((input) => {
    input.manifest.inventory.pytest.counts.skipped = 1;
  }, "incomplete-collection");

  const allowed = scenario();
  allowed.manifest.inventory.pytest.notPassed = [skipped];
  Object.assign(allowed.manifest.inventory.pytest.counts, { passed: 1, skipped: 1 });
  allowed.profile.skipAllowlist = [{ id: PYTEST_IDS[0], reason: "approved exception" }];
  approve(allowed.profile);
  assert.equal(evaluateCloudEvidence(allowed).status, "pass");
});

test("rejects runtime Vitest and node:test skips, todos and count disagreements", () => {
  assertRejected((input) => {
    input.manifest.outcomes.vitest = [{ total: 1, skipped: 1 }];
  }, "unqualified-skip");
  assertRejected((input) => {
    input.manifest.outcomes.vitest = [{ total: 1, todo: 1 }];
  }, "unqualified-skip");
  assertRejected((input) => {
    input.manifest.outcomes.vitest = [{ total: 1, failed: 1 }];
  }, "tests-not-passed");
  assertRejected((input) => {
    input.manifest.outcomes.vitest = [{ total: 2, passed: 2 }];
  }, "incomplete-collection");
  // An outcome word the parser does not recognise still fails closed.
  assertRejected((input) => {
    input.manifest.outcomes.vitest = [{ total: 1 }];
  }, "tests-not-passed");
  assertRejected((input) => {
    Object.assign(input.manifest.outcomes.node[0].counts, { pass: 0, skipped: 1 });
  }, "unqualified-skip");
  assertRejected((input) => {
    Object.assign(input.manifest.outcomes.node[0].counts, { tests: 2 });
  }, "incomplete-collection");
  assertRejected((input) => {
    Object.assign(input.manifest.outcomes.node[0].counts, { pass: 0, cancelled: 1 });
  }, "tests-not-passed");
});

test("treats every gate configuration that tools discover per directory as a control", () => {
  for (const file of [
    "output/ruff.toml",
    "docs/investigations/issue-141/ruff.toml",
    ".ruff.toml",
    "mypy.ini",
    "pytest.ini",
    "tests/sub/conftest.py",
    "setup.cfg",
    "tox.ini",
    ".npmrc",
    "packages/contracts/.npmrc",
    "packages/contracts/eslint.config.mjs",
    "packages/contracts/vitest.config.ts",
    "vite.config.ts",
    "packages/word-timing/pyproject.toml",
    "tsconfig.base.json",
    ".gitattributes",
    "uv.toml",
  ]) {
    assert.equal(isControlPath(file), true, file);
  }
  for (const file of ["docs/notes.md", "tests/test_fixtures.py", "fixtures/ruff.toml.txt"]) {
    assert.equal(isControlPath(file), false, file);
  }
});

test("a changed or added control cannot self-certify, even when the manifest repeats the qualified digests", () => {
  const report = assertRejected((input) => {
    input.tree.tree[0] = { ...input.tree.tree[0], sha: sha("e") };
  }, "control-drift");
  assert.ok(report.failures.some((entry) => entry.detail.startsWith(".github/workflows/validate.yml")));
  for (const added of ["packages/contracts/vitest.config.ts", "docs/investigations/new/ruff.toml", "packages/contracts/.npmrc"]) {
    assertRejected((input) => {
      input.tree.tree.push({ path: added, type: "blob", sha: sha("e") });
    }, "control-drift");
  }
  assertRejected((input) => {
    input.manifest.command = "npm run validate:fast";
  }, "control-drift");
  // Non-control files may differ without touching the control set.
  const documentation = scenario();
  documentation.tree.tree[6] = { ...documentation.tree.tree[6], sha: sha("e") };
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
  media.manifest.tools.media.ffmpegSha256 = "0".repeat(64);
  const mediaReport = evaluateCloudEvidence(media);
  assert.equal(mediaReport.status, "pass");
  assert.deepEqual(mediaReport.suspendedScopes, ["media-sensitive"]);
  assert.ok(mediaReport.limitations.some((entry) => entry.code === "media-tool-drift"));
  assert.equal(scopeAccepted(mediaReport, "full"), false);
  assert.equal(scopeAccepted(mediaReport, "excluding-media-sensitive"), true);

  const image = scenario();
  image.manifest.tools.runnerImage.version = "20261012.2";
  const imageReport = evaluateCloudEvidence(image);
  assert.deepEqual(imageReport.suspendedScopes, ["media-sensitive"]);
  assert.ok(imageReport.limitations.some((entry) => entry.code === "runner-image-changed"));
  assert.throws(() => scopeAccepted(imageReport, "pure-logic"), EvidenceError);
});

test("a later green attempt does not hide an unexplained earlier failure, and accepted dispositions stay visible", () => {
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

  for (const classification of ["infrastructure", "diagnosed-flake"]) {
    const resolved = scenario();
    resolved.history[0].conclusion = "failure";
    resolved.dispositions = [
      { runId: RUN_ID, attempt: 1, classification, explanation: "apt mirror timeout before tests started", evidence: "run 5001 attempt 1 log" },
    ];
    const report = evaluateCloudEvidence(resolved);
    assert.equal(report.status, "pass");
    assert.deepEqual(
      report.acceptedDispositions.map((entry) => [entry.key, entry.classification]),
      [[`${RUN_ID}:1`, classification]],
    );
    assert.ok(report.limitations.some((entry) => entry.code === "prior-failure-dispositioned"));
  }
});

test("fails closed on malformed or incomplete facts", () => {
  assertRejected((input) => {
    input.manifest = { schemaVersion: 1 };
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
  for (const change of [{ attempt: undefined }, { attempt: 0 }, { pullRequest: undefined }, { tree: "abc" }, { repository: "../x" }]) {
    const input = scenario();
    Object.assign(input.expected, change);
    assert.throws(() => evaluateCloudEvidence(input), EvidenceError, JSON.stringify(change));
  }
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

test("reads runtime outcomes from the gate's own Vitest and node:test output", () => {
  // Shape copied from the retained #193 local full-gate log, plus TAP and skips.
  const log = [
    " RUN  v4.1.11 /work/packages/contracts",
    "",
    " Test Files  19 passed (19)",
    "      Tests  400 passed | 1 skipped | 1 todo (402)",
    "   Start at  12:10:09",
    "> vera-script-to-timeline@0.0.0 test:progress",
    "> node --test scripts/project-progress.test.mjs",
    "",
    "\x1b[32m✔ parses the authoritative board without counting goals as work (1.890702ms)\x1b[39m",
    "﹣ waits for a board (0.1ms) # SKIP",
    "  ✔ nested subtest is not top level (0.2ms)",
    "ℹ tests 2",
    "ℹ suites 0",
    "ℹ pass 1",
    "ℹ fail 0",
    "ℹ cancelled 0",
    "ℹ skipped 1",
    "ℹ todo 0",
    "> node --test scripts/roadmap.test.mjs",
    "ok 1 - uses the latest claim marker",
    "ok 2 - uses the latest claim marker",
    "    ok 1 - nested",
    "not ok 2 - rejects prose # TODO later",
    "# tests 3",
    "# pass 2",
    "# todo 1",
    "tests/test_word_timing_cli.py ......   [ 90%]",
  ].join("\n");
  const outcomes = parseValidateLog(log);
  assert.deepEqual(outcomes.vitest, [{ total: 402, passed: 400, skipped: 1, todo: 1 }]);
  assert.deepEqual(outcomes.node, [
    {
      command: "node --test scripts/project-progress.test.mjs",
      ids: ["parses the authoritative board without counting goals as work", "waits for a board"],
      counts: { tests: 2, pass: 1, fail: 0, cancelled: 0, skipped: 1, todo: 0 },
    },
    {
      command: "node --test scripts/roadmap.test.mjs",
      ids: ["uses the latest claim marker", "uses the latest claim marker #2", "rejects prose"],
      counts: { tests: 3, pass: 2, todo: 1 },
    },
  ]);
});

test("numbered duplicate names still detect a removed case and refuse colliding numbering", () => {
  assert.deepEqual(numberDuplicateIds(["x", "y", "x", "x"]), ["x", "y", "x #2", "x #3"]);
  assertRejected((input) => {
    input.profile.inventory.vitest = numberDuplicateIds([VITEST_IDS[0], VITEST_IDS[0], VITEST_IDS[0]]);
    approve(input.profile);
    input.manifest.inventory.vitest.ids = numberDuplicateIds([VITEST_IDS[0], VITEST_IDS[0]]);
    input.manifest.outcomes.vitest = [{ total: 2, passed: 2 }];
  }, "incomplete-coverage");
  assertRejected((input) => {
    input.manifest.inventory.vitest.ids = numberDuplicateIds(["a", "a", "a #2"]);
    input.manifest.outcomes.vitest = [{ total: 3, passed: 3 }];
  }, "incomplete-collection");
});

test("reads NUL-delimited tree and status listings with unusual paths", () => {
  const entries = parseLsTree(
    `100644 blob ${sha("1")}\tdocs/with space/ruff.toml\u0000100644 blob ${sha("2")}\tdocs/naïve "quoted"/x.md\u0000040000 tree ${sha("3")}\ttests\u0000`,
  );
  assert.deepEqual(
    entries.map((entry) => entry.path),
    ["docs/with space/ruff.toml", 'docs/naïve "quoted"/x.md', "tests"],
  );
  assert.deepEqual(controlDigestsFromEntries(entries), { "docs/with space/ruff.toml": sha("1") });
  assert.deepEqual(parsePorcelain(" M fixtures/a b.json\u0000M  uv.lock\u0000"), ["fixtures/a b.json", "uv.lock"]);
});

function git(directory, ...args) {
  const result = spawnSync("git", ["-c", "user.name=Test", "-c", "user.email=test@example.invalid", ...args], {
    cwd: directory,
    encoding: "utf8",
  });
  assert.equal(result.status, 0, result.stderr);
  return result.stdout;
}

function collectorFixture(t) {
  const root = mkdtempSync(path.join(os.tmpdir(), "vera-cloud-collect-test-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const evidence = path.join(root, ".evidence");
  mkdirSync(evidence);
  mkdirSync(path.join(root, "packages", "demo"), { recursive: true });
  mkdirSync(path.join(root, "docs", "naïve dir"), { recursive: true });
  mkdirSync(path.join(root, "tests"));
  writeFileSync(path.join(root, "package.json"), "{}\n");
  writeFileSync(path.join(root, "packages", "demo", "package.json"), JSON.stringify({ scripts: { test: "vitest run" } }));
  writeFileSync(path.join(root, "docs", "naïve dir", "ruff.toml"), "line-length = 100\n");
  writeFileSync(path.join(root, "tests", "test_a.py"), "def test_a(): pass\n");
  writeFileSync(path.join(root, ".gitignore"), ".evidence/\n");
  git(root, "init", "-q");
  git(root, "add", "-A");
  git(root, "commit", "-q", "-m", "fixture");
  const binary = path.join(evidence, "ffmpeg-binary");
  writeFileSync(binary, "binary");
  writeFileSync(
    path.join(evidence, "pytest-junit.xml"),
    '<testsuites><testsuite><testcase classname="tests.test_a" name="test_a" time="0.1"/></testsuite></testsuites>',
  );
  writeFileSync(
    path.join(evidence, "validate.log"),
    "      Tests  3 passed (3)\n> node --test scripts/x.test.mjs\n✔ works (1ms)\nℹ tests 1\nℹ pass 1\nℹ fail 0\nℹ skipped 0\nℹ todo 0\n",
  );
  const calls = [];
  const runCommand = (command, args, options) => {
    calls.push([command, ...args]);
    if (command === "git") return spawnSync(command, args, { ...options, encoding: "utf8" });
    const ok = (stdout) => ({ status: 0, stdout, stderr: "" });
    if (command === "sh") return ok(`${binary}\n`);
    if (command === "ffmpeg") return ok("ffmpeg version 6.1.1\n");
    if (command === "ffprobe") return ok("ffprobe version 6.1.1\n");
    if (command.endsWith("vitest")) {
      const output = args.find((arg) => arg.startsWith("--json=")).slice("--json=".length);
      // it.each display names collide in `vitest list` (observed in calibration round 1).
      const file = path.join(options.cwd, "test", "a.test.ts");
      writeFileSync(
        output,
        JSON.stringify([
          { name: "suite > works", file },
          { name: "suite > each [ Array(1) ]", file },
          { name: "suite > each [ Array(1) ]", file },
        ]),
      );
      return ok("");
    }
    if (command === "uv" && args.includes("--collect-only")) {
      assert.equal(options.env.PYTEST_ADDOPTS, undefined);
      return ok("tests/test_a.py::test_a\n\n1 test collected in 0.01s\n");
    }
    if (command === "uv" && args.includes("python")) return ok("3.12.14\n");
    return ok("1.0\n");
  };
  const environment = {
    GITHUB_REPOSITORY: REPOSITORY,
    GITHUB_RUN_ID: "5001",
    GITHUB_RUN_ATTEMPT: "2",
    GITHUB_EVENT_NAME: "push",
    PYTEST_ADDOPTS: "--junitxml=x",
    RUNNER_TEMP: evidence,
    VERA_OUTCOME_PREFLIGHT: "success",
    VERA_OUTCOME_VALIDATE: "success",
    VERA_OUTCOME_LOCKFILES: "success",
  };
  return { root, evidence, environment, runCommand, calls };
}

test("collector records checkout, unusual control paths, inventories and runtime outcomes", (t) => {
  const { root, evidence, environment, runCommand } = collectorFixture(t);
  const manifest = collectEvidence({ root, evidenceDirectory: evidence, environment, runCommand });
  assert.deepEqual(manifest.collection, { complete: true, errors: [] });
  assert.equal(manifest.checkout.commit, git(root, "rev-parse", "HEAD").trim());
  assert.equal(manifest.checkout.tree, git(root, "rev-parse", "HEAD^{tree}").trim());
  assert.deepEqual(Object.keys(manifest.controls), ["docs/naïve dir/ruff.toml", "package.json", "packages/demo/package.json"]);
  assert.deepEqual(manifest.trackedState, { modified: [] });
  assert.deepEqual(manifest.inventory.pytest.ids, ["tests.test_a.test_a"]);
  assert.deepEqual(manifest.inventory.pytest.collectedIds, ["tests.test_a.test_a"]);
  assert.deepEqual(manifest.inventory.vitest.ids, [
    "packages/demo/test/a.test.ts > suite > each [ Array(1) ]",
    "packages/demo/test/a.test.ts > suite > each [ Array(1) ] #2",
    "packages/demo/test/a.test.ts > suite > works",
  ]);
  assert.deepEqual(manifest.outcomes.node[0].ids, ["works"]);
  assert.equal(manifest.tools.media.ffmpegSha256.length, 64);
  // Published fields carry no raw log or environment dump.
  assert.equal(JSON.stringify(manifest).includes("--junitxml"), false);
});

test("collector reports tracked-file changes and marks failed collection incomplete", (t) => {
  const { root, evidence, environment, runCommand } = collectorFixture(t);
  writeFileSync(path.join(root, "tests", "test_a.py"), "def test_a(): assert True\n");
  rmSync(path.join(evidence, "validate.log"));
  const failing = (command, args, options) =>
    command === "ffprobe" ? { status: 1, stdout: "", stderr: "ffprobe: not found" } : runCommand(command, args, options);
  const manifest = collectEvidence({ root, evidenceDirectory: evidence, environment, runCommand: failing });
  assert.deepEqual(manifest.trackedState.modified, ["tests/test_a.py"]);
  assert.equal(manifest.collection.complete, false);
  assert.ok(manifest.collection.errors.some((error) => error.startsWith("ffprobe -version")));
  assert.ok(manifest.collection.errors.some((error) => error.startsWith("validate log")));
});

test("the workflow defines every required step, the exact command and the artifact name", () => {
  const workflow = readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), "..", ".github", "workflows", "validate.yml"), "utf8");
  const stepNames = [...workflow.matchAll(/^ {6}- name: (.+)$/gm)].map((match) => match[1]);
  for (const name of REQUIRED_STEPS) assert.ok(stepNames.includes(name), `workflow lacks step "${name}"`);
  const validateStep = workflow.slice(workflow.indexOf("- name: Run repository validation"), workflow.indexOf("- name: Verify lockfiles"));
  assert.match(validateStep, /^ {8}shell: bash$/m);
  assert.match(validateStep, /^ {10}set -o pipefail$/m);
  assert.match(validateStep, new RegExp(`^ {10}${VALIDATE_COMMAND} 2>&1 \\| tee "\\$RUNNER_TEMP/vera-evidence/validate\\.log"$`, "m"));
  assert.match(workflow, /name: vera-validation-evidence-attempt-\$\{\{ github\.run_attempt \}\}/);
  assert.match(workflow, /path: \$\{\{ runner\.temp \}\}\/vera-evidence\/manifest\.json$/m);
  assert.match(workflow, /^permissions:\n {2}contents: read\n/m);
  for (const match of workflow.matchAll(/uses: (\S+)/g)) assert.match(match[1], /@[0-9a-f]{40}$/);
});

test("PR and manual events run the full gate; main pushes run bounded smoke checks", () => {
  const workflow = readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), "..", ".github", "workflows", "validate.yml"), "utf8");
  assert.match(workflow, /^on:\n {2}pull_request:\n {2}push:\n {4}branches:\n {6}- main\n {2}workflow_dispatch:\n/m);

  const fullStart = workflow.indexOf("  validate:\n");
  const smokeStart = workflow.indexOf("  main-smoke:\n");
  assert.ok(fullStart >= 0 && smokeStart > fullStart, "workflow must keep the full job before the push smoke job");
  const fullJob = workflow.slice(fullStart, smokeStart);
  const smokeJob = workflow.slice(smokeStart);
  assert.match(fullJob, /^ {4}if: \$\{\{ github\.event_name != 'push' \}\}$/m);
  assert.match(smokeJob, /^ {4}if: \$\{\{ github\.event_name == 'push' \}\}$/m);
  assert.match(smokeJob, /^ {10}node --test scripts\/cloud-evidence\.test\.mjs scripts\/agent-safety\.test\.mjs$/m);
  assert.match(smokeJob, /^ {10}uv run --no-project --python 3\.12\.14 python -m compileall -q python$/m);
  assert.doesNotMatch(smokeJob, /npm run validate(?::fast)?\b/);
  assert.match(workflow, /cancel-in-progress: \$\{\{ github\.event_name == 'pull_request' \}\}/);
});

function branchPages(endpoint, runs, pageSize) {
  const pages = [];
  for (let index = 0; index * pageSize < runs.length; index += 1) {
    pages.push([`${endpoint}&page=${index + 1}`, { total_count: runs.length, workflow_runs: runs.slice(index * pageSize, (index + 1) * pageSize) }]);
  }
  return pages;
}

function stubGitHub(input, { branchRuns = [], extraCommits = {}, pageSize = 100 } = {}) {
  const requests = [];
  const runs = `repos/${REPOSITORY}/actions/workflows/validate.yml/runs?per_page=100`;
  const responses = new Map([
    [`repos/${REPOSITORY}/actions/runs/${RUN_ID}/attempts/2`, input.run],
    [`repos/${REPOSITORY}/actions/runs/${RUN_ID}/attempts/2/jobs?per_page=100`, { jobs: input.jobs }],
    [`repos/${REPOSITORY}/actions/runs/${RUN_ID}/attempts/1`, { ...input.run, run_attempt: 1, conclusion: "failure" }],
    [`repos/${REPOSITORY}/git/commits/${MERGE}`, input.commit],
    [`repos/${REPOSITORY}/git/commits/${HEAD}`, { sha: HEAD, tree: { sha: HEAD_TREE } }],
    [`repos/${REPOSITORY}/git/trees/${TREE}?recursive=1`, input.tree],
    [`${runs}&head_sha=${HEAD}&page=1`, { total_count: 1, workflow_runs: [input.run] }],
    ...branchPages(`${runs}&branch=${encodeURIComponent(input.run.head_branch)}`, [input.run, ...branchRuns], pageSize),
    ...Object.entries(extraCommits).map(([commitSha, treeSha]) => [
      `repos/${REPOSITORY}/git/commits/${commitSha}`,
      { sha: commitSha, tree: { sha: treeSha } },
    ]),
  ]);
  const getJson = async (endpoint) => {
    requests.push(endpoint);
    if (!responses.has(endpoint)) throw new Error(`unexpected request ${endpoint}`);
    return JSON.parse(JSON.stringify(responses.get(endpoint)));
  };
  return { getJson, requests };
}

test("gathers every earlier attempt on the same tested source, including recommits of an identical tree", async () => {
  const input = scenario();
  const recommit = { ...input.run, id: 4990, run_attempt: 1, head_sha: sha("6"), conclusion: "failure", event: "push" };
  const unrelated = { ...input.run, id: 4980, run_attempt: 1, head_sha: sha("7"), conclusion: "failure", event: "push" };
  const { getJson, requests } = stubGitHub(input, {
    branchRuns: [recommit, unrelated],
    extraCommits: { [sha("6")]: HEAD_TREE, [sha("7")]: sha("8") },
    pageSize: 2,
  });
  const facts = await gatherGitHubFacts(getJson, { repository: REPOSITORY, runId: RUN_ID, attempt: 2, manifestCommit: MERGE });
  assert.deepEqual(
    facts.history.map(({ runId, attempt, conclusion }) => [runId, attempt, conclusion]),
    [
      [4990, 1, "failure"],
      [RUN_ID, 1, "failure"],
      [RUN_ID, 2, "success"],
    ],
  );
  assert.ok(requests.every((endpoint) => endpoint.startsWith(`repos/${REPOSITORY}/`)));
  const report = evaluateCloudEvidence({ ...input, ...facts });
  assert.ok(report.failures.filter((entry) => entry.code === "unresolved-prior-failure").length === 2);
});

test("refuses to evaluate a run history it could not read completely, or malformed identifiers", async () => {
  const input = scenario();
  const { getJson } = stubGitHub(input);
  const truncated = async (endpoint) => {
    if (endpoint.includes("/workflows/") && !endpoint.endsWith("&page=1")) return { total_count: 150, workflow_runs: [] };
    const response = await getJson(endpoint);
    return endpoint.includes("/workflows/") ? { ...response, total_count: 150 } : response;
  };
  await assert.rejects(
    gatherGitHubFacts(truncated, { repository: REPOSITORY, runId: RUN_ID, attempt: 2, manifestCommit: MERGE }),
    /incomplete history/,
  );
  // A busy branch beyond the page cap is refused, never silently truncated.
  const busy = Array.from({ length: 1001 }, (_, index) => ({ ...input.run, id: 3000 + index, head_sha: sha("6") }));
  const { getJson: busyBranch } = stubGitHub(input, { branchRuns: busy, extraCommits: { [sha("6")]: sha("8") } });
  await assert.rejects(
    gatherGitHubFacts(busyBranch, { repository: REPOSITORY, runId: RUN_ID, attempt: 2, manifestCommit: MERGE }),
    /page cap/,
  );
  const { getJson: untouched, requests } = stubGitHub(input);
  for (const malformed of [{ manifestCommit: "HEAD" }, { manifestCommit: undefined }, { repository: "x/../y/z" }, { attempt: 0 }]) {
    await assert.rejects(
      gatherGitHubFacts(untouched, { repository: REPOSITORY, runId: RUN_ID, attempt: 2, manifestCommit: MERGE, ...malformed }),
      EvidenceError,
    );
  }
  assert.deepEqual(requests, []);
});

test("CLI rejects malformed arguments before any subprocess or GitHub request", () => {
  const valid = ["--repo", REPOSITORY, "--run", "5001", "--attempt", "2", "--event", "push", "--expected-tree", TREE, "--profile", "p.json"];
  assert.equal(parseArguments(valid).scope, "full");
  const replace = (flag, value) => valid.map((entry, index) => (valid[index - 1] === flag ? value : entry));
  for (const values of [
    replace("--repo", "a/b/c"),
    replace("--run", "0"),
    replace("--attempt", "1; rm -rf /"),
    replace("--event", "pull_request_target"),
    replace("--expected-tree", "main"),
    [...valid, "--scope", "pure-logic"],
    [...valid, "--unknown", "x"],
    replace("--event", "pull_request"),
  ]) {
    assert.throws(() => parseArguments(values), EvidenceError, values.join(" "));
  }
});

async function cliRun(t, input, extraArguments, stubOptions) {
  const directory = mkdtempSync(path.join(os.tmpdir(), "vera-cloud-evidence-test-"));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const files = {};
  for (const name of ["manifest", "profile", "dispositions"]) {
    files[name] = path.join(directory, `${name}.json`);
    writeFileSync(files[name], JSON.stringify(input[name]));
  }
  const logs = [];
  const code = await main(
    [
      ...["--repo", REPOSITORY, "--run", String(RUN_ID), "--attempt", "2", "--manifest", files.manifest],
      ...["--dispositions", files.dispositions],
      ...extraArguments(files, directory),
    ],
    { getJson: stubGitHub(input, stubOptions).getJson, log: (line) => logs.push(line) },
  );
  return { code, logs, directory };
}

const verdictArguments = (files) => ["--event", "pull_request", "--pr", "77", "--expected-tree", TREE, "--profile", files.profile];

test("CLI exits nonzero for unresolved history and zero once the failure is dispositioned", async (t) => {
  const input = scenario();
  const unresolved = await cliRun(t, input, verdictArguments);
  assert.equal(unresolved.code, 1);
  assert.ok(JSON.parse(unresolved.logs[0]).failures.some((entry) => entry.code === "unresolved-prior-failure"));

  input.dispositions = [{ runId: RUN_ID, attempt: 1, classification: "infrastructure", explanation: "runner lost", evidence: "link" }];
  const passing = await cliRun(t, input, verdictArguments);
  assert.equal(passing.code, 0);
  const report = JSON.parse(passing.logs[0]);
  assert.equal(report.accepted, true);
  assert.equal(report.manifest.source, "local-file");
  assert.match(report.manifest.sha256, /^[0-9a-f]{64}$/);
  assert.equal(report.acceptedDispositions.length, 1);
  assert.ok(report.steps.some((step) => step.name === "Run repository validation"));
});

test("CLI success is scoped: suspended media scope fails a full-scope request", async (t) => {
  const input = scenario();
  input.dispositions = [{ runId: RUN_ID, attempt: 1, classification: "infrastructure", explanation: "runner lost", evidence: "link" }];
  input.manifest.tools.media.ffprobeSha256 = "0".repeat(64);
  const full = await cliRun(t, input, verdictArguments);
  assert.equal(full.code, 1);
  assert.equal(JSON.parse(full.logs[0]).accepted, false);
  const scoped = await cliRun(t, input, (files) => [...verdictArguments(files), "--scope", "excluding-media-sensitive"]);
  assert.equal(scoped.code, 0);
});

test("CLI drafts only unqualified profiles, and only from a clean complete calibration run", async (t) => {
  const input = scenario();
  input.dispositions = [{ runId: RUN_ID, attempt: 1, classification: "infrastructure", explanation: "runner lost", evidence: "link" }];
  const draftArguments = (files, directory) => ["--draft-profile", path.join(directory, "draft.json")];
  const clean = await cliRun(t, input, draftArguments);
  assert.equal(clean.code, 0, clean.logs.join("\n"));
  const draft = JSON.parse(readFileSync(path.join(clean.directory, "draft.json"), "utf8"));
  assert.equal(draft.qualified, false);
  assert.equal(draft.approval, null);
  assert.deepEqual(draft.controls, input.profile.controls);
  assert.deepEqual(draft.inventory, input.profile.inventory);
  assert.deepEqual(draft.skipAllowlist, []);
  assert.deepEqual(draft.calibration.runs[0], { runId: RUN_ID, attempt: 2, tree: TREE, url: input.run.html_url });
  assert.ok(profileProblems(draft).some((problem) => problem.includes("qualified")));
  assert.deepEqual(profileProblems(draft, { requireApproval: false }), []);

  for (const mutate of [
    (value) => {
      value.manifest.inventory.pytest.ids = [];
      value.manifest.inventory.pytest.collectedIds = [];
    },
    (value) => {
      value.manifest.collection = { complete: false, errors: ["vitest list: failed"] };
    },
    (value) => {
      value.run.conclusion = "failure";
    },
    (value) => {
      value.dispositions = [];
    },
    (value) => {
      value.manifest.tools.media.ffmpegSha256 = null;
    },
  ]) {
    const value = scenario();
    value.dispositions = input.dispositions;
    mutate(value);
    const refused = await cliRun(t, value, draftArguments);
    assert.equal(refused.code, 1);
    assert.ok(refused.logs.at(-1).startsWith("Refusing to draft"));
  }
});
