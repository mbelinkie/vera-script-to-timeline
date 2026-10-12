// Cloud validation evidence helpers for issue #196.
//
// The workflow-side collector records what a run consumed (tree, controls,
// tools, inventory, runtime outcomes). Authority over whether that run passed
// comes only from independently read GitHub metadata; a manifest never
// certifies itself.

import { createHash } from "node:crypto";

export const MANIFEST_SCHEMA_VERSION = 2;
export const PROFILE_SCHEMA_VERSION = 2;

export const WORKFLOW_PATH = ".github/workflows/validate.yml";
export const WORKFLOW_NAME = "Validate";
export const JOB_NAME = "TypeScript and Python";
export const VALIDATE_COMMAND = "VITEST_MAX_WORKERS=1 npm run validate";
export const ARTIFACT_PREFIX = "vera-validation-evidence-attempt-";
export const SCOPES = Object.freeze(["full", "excluding-media-sensitive"]);

export const REQUIRED_STEPS = Object.freeze([
  "Check out repository",
  "Install TypeScript dependencies",
  "Install Python dependencies",
  "Install FFmpeg",
  "Preflight required media tools",
  "Run repository validation",
  "Verify lockfiles remain unchanged",
  "Collect validation evidence",
  "Upload validation evidence",
]);

// Files whose change alters what the gate runs or how its result is judged.
// Ruff, ESLint, pytest (conftest), TypeScript, Vitest/Vite and npm discover
// these per directory, so a matching basename at any depth is a control.
const CONTROL_BASENAME =
  /^(?:package(?:-lock)?\.json|pyproject\.toml|uv\.(?:lock|toml)|\.npmrc|\.nvmrc|\.node-version|\.python-version|\.tool-versions|\.gitattributes|\.?ruff\.toml|\.?mypy\.ini|\.?pytest\.ini|tox\.ini|setup\.cfg|conftest\.py|tsconfig[^/]*\.json|(?:eslint|vite|vitest)\.(?:config|workspace)\.[cm]?[jt]s)$/;
const CONTROL_PATHS = Object.freeze([
  /^\.github\/workflows\/validate\.yml$/,
  /^packages\/contracts\/scripts\/generate-contracts\.mjs$/,
  /^scripts\/cloud-evidence[^/]*\.mjs$/,
]);

const RUNTIME_TOOL_KEYS = Object.freeze(["node", "npm", "uv", "python", "os", "arch", "runnerLabel"]);
const MEDIA_TOOL_KEYS = Object.freeze([
  "ffmpegVersion",
  "ffprobeVersion",
  "ffmpegSha256",
  "ffprobeSha256",
  "capabilitiesDigest",
]);

const DISPOSITION_CLASSES = Object.freeze(["infrastructure", "operator-cancelled", "diagnosed-flake"]);
const SHA = /^[0-9a-f]{40}$/;
const REPOSITORY = /^[A-Za-z0-9-]+\/[A-Za-z0-9._-]+$/;

export class EvidenceError extends Error {}

export function isControlPath(filePath) {
  return CONTROL_BASENAME.test(filePath.slice(filePath.lastIndexOf("/") + 1)) || CONTROL_PATHS.some((pattern) => pattern.test(filePath));
}

export function controlDigestsFromEntries(entries) {
  const controls = {};
  for (const entry of entries) {
    if (entry.type === "blob" && isControlPath(entry.path)) {
      controls[entry.path] = entry.sha;
    }
  }
  return sortObject(controls);
}

// `git ls-tree -r -t -z HEAD` records: "<mode> <type> <sha>\t<path>\0", with
// paths unquoted so they match GitHub's decoded tree listing.
export function parseLsTree(output) {
  return output
    .split("\0")
    .filter(Boolean)
    .map((record) => {
      const tab = record.indexOf("\t");
      const [mode, type, sha] = record.slice(0, tab).split(" ");
      return { mode, type, sha, path: record.slice(tab + 1) };
    });
}

// `git status --porcelain=v1 -z --untracked-files=no`: tracked paths the gate changed.
export function parsePorcelain(output) {
  return output
    .split("\0")
    .filter(Boolean)
    .map((record) => record.slice(3))
    .sort();
}

function decodeXml(value) {
  return value.replace(/&(#x[0-9a-fA-F]+|#[0-9]+|amp|lt|gt|quot|apos);/g, (match, entity) => {
    if (entity === "amp") return "&";
    if (entity === "lt") return "<";
    if (entity === "gt") return ">";
    if (entity === "quot") return '"';
    if (entity === "apos") return "'";
    const code = entity.startsWith("#x") ? Number.parseInt(entity.slice(2), 16) : Number.parseInt(entity.slice(1), 10);
    return String.fromCodePoint(code);
  });
}

function parseAttributes(source) {
  const attributes = {};
  for (const match of source.matchAll(/([\w:-]+)\s*=\s*"([^"]*)"/g)) {
    attributes[match[1]] = decodeXml(match[2]);
  }
  return attributes;
}

// Minimal pytest JUnit reader: identities, outcomes, skip reasons and times.
// Failure text and captured output are deliberately dropped so the published
// manifest never carries test output.
export function parseJunit(xml) {
  if (typeof xml !== "string" || !/<testsuites?\b/.test(xml)) {
    throw new EvidenceError("JUnit report is missing a testsuite element");
  }
  const cases = [];
  const pattern = /<testcase\b([^>]*?)(?:\/>|>([\s\S]*?)<\/testcase>)/g;
  for (const match of xml.matchAll(pattern)) {
    const attributes = parseAttributes(match[1]);
    const body = match[2] ?? "";
    let outcome = "passed";
    let reason = null;
    const skipped = /<skipped\b([^>]*?)(?:\/>|>)/.exec(body);
    if (/<error\b/.test(body)) outcome = "error";
    else if (/<failure\b/.test(body)) outcome = "failed";
    else if (skipped) {
      outcome = "skipped";
      reason = parseAttributes(skipped[1]).message ?? null;
    }
    const id = attributes.classname ? `${attributes.classname}.${attributes.name}` : attributes.name;
    cases.push({ id, outcome, reason, time: Number(attributes.time ?? 0) });
  }
  return cases;
}

// Same address mangling pytest applies when writing JUnit classname/name.
export function nodeIdToJunitId(nodeId) {
  const bracket = nodeId.indexOf("[");
  const pathPart = bracket === -1 ? nodeId : nodeId.slice(0, bracket);
  const params = bracket === -1 ? "" : nodeId.slice(bracket);
  const names = pathPart.split("::");
  names[0] = names[0].replaceAll("/", ".").replace(/\.py$/, "");
  names[names.length - 1] += params;
  return names.join(".");
}

// `pytest --collect-only -q`: node IDs until the first blank line.
export function parseCollectOnly(output) {
  const ids = [];
  for (const line of output.split("\n")) {
    if (line.trim() === "") break;
    if (line.includes("::")) ids.push(line.trim());
  }
  if (ids.length === 0) throw new EvidenceError("pytest collection listed no tests");
  return ids;
}

// Runtime outcomes from the unchanged gate's own output: Vitest run summaries
// and node:test results per `node --test` invocation (spec or TAP reporter).
export function parseValidateLog(text) {
  // eslint-disable-next-line no-control-regex -- strips ANSI colour codes
  const lines = text.replace(/\x1b\[[0-9;]*[A-Za-z]/g, "").split(/\r?\n/);
  const vitest = [];
  const node = [];
  let current = null;
  for (const line of lines) {
    const tests = /^\s+Tests\s+(.+?)\s+\((\d+)\)\s*$/.exec(line);
    if (tests) {
      const counts = { total: Number(tests[2]) };
      for (const part of tests[1].split("|")) {
        const piece = /^(\d+)\s+([a-z]+)$/.exec(part.trim());
        if (piece) counts[piece[2]] = Number(piece[1]);
      }
      vitest.push(counts);
      continue;
    }
    const command = /^> (node --test\b.*)$/.exec(line);
    if (command) {
      current = { command: command[1], ids: [], counts: {} };
      node.push(current);
      continue;
    }
    if (!current) continue;
    const spec = /^([✔✖﹣]) (.+?) \([\d.]+m?s\)(?: # (SKIP|TODO)\b.*)?$/.exec(line);
    const tap = /^(not )?ok \d+ - (.+?)(?: # (SKIP|TODO)\b.*)?$/.exec(line);
    if (spec) current.ids.push(spec[2]);
    else if (tap) current.ids.push(tap[2]);
    const summary = /^(?:ℹ|#) (tests|pass|fail|cancelled|skipped|todo) (\d+)$/.exec(line);
    if (summary) current.counts[summary[1]] = Number(summary[2]);
  }
  return { vitest, node };
}

export function summarizePytest(cases, collectedNodeIds) {
  const count = (outcome) => cases.filter((entry) => entry.outcome === outcome).length;
  return {
    ids: cases.map((entry) => entry.id).sort(),
    counts: {
      total: cases.length,
      passed: count("passed"),
      failed: count("failed"),
      errors: count("error"),
      skipped: count("skipped"),
    },
    notPassed: cases
      .filter((entry) => entry.outcome !== "passed")
      .map(({ id, outcome, reason }) => ({ id, outcome, reason })),
    collectedIds: collectedNodeIds.map(nodeIdToJunitId).sort(),
    totalSeconds: Number(cases.reduce((sum, entry) => sum + entry.time, 0).toFixed(3)),
    slowest: [...cases]
      .sort((left, right) => right.time - left.time)
      .slice(0, 25)
      .map(({ id, time }) => ({ id, seconds: time })),
  };
}

function sortObject(value) {
  return Object.fromEntries(Object.entries(value).sort(([left], [right]) => left.localeCompare(right)));
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (isObject(value)) return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonical(value[key])]));
  return value;
}

// Identity of the qualified content. Approval must name this digest, so an
// approval cannot be carried over to an edited profile.
export function profileDigest(profile) {
  const content = { ...profile };
  delete content.qualified;
  delete content.approval;
  return createHash("sha256").update(JSON.stringify(canonical(content))).digest("hex");
}

function diffMaps(expected, actual) {
  const changed = [];
  for (const key of new Set([...Object.keys(expected), ...Object.keys(actual)])) {
    if (expected[key] !== actual[key]) {
      changed.push({ key, expected: expected[key] ?? null, actual: actual[key] ?? null });
    }
  }
  return changed.sort((left, right) => left.key.localeCompare(right.key));
}

function missingFrom(required, present) {
  const available = new Set(present);
  return required.filter((id) => !available.has(id));
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isNonEmptyIdList(value) {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every((id) => typeof id === "string" && id.length > 0) &&
    new Set(value).size === value.length
  );
}

function nonEmpty(value) {
  return typeof value === "string" && value.trim().length > 0;
}

// Structural validation of a profile before it may judge any run.
export function profileProblems(profile, { requireApproval = true } = {}) {
  const problems = [];
  const need = (condition, message) => {
    if (!condition) problems.push(message);
  };
  if (!isObject(profile)) return ["profile is not an object"];
  need(profile.schemaVersion === PROFILE_SCHEMA_VERSION, `schemaVersion must be ${PROFILE_SCHEMA_VERSION}`);
  need(profile.command === VALIDATE_COMMAND, `command must be "${VALIDATE_COMMAND}"`);
  const controls = profile.controls;
  need(
    isObject(controls) && Object.values(controls).every((sha) => SHA.test(sha ?? "")),
    "controls must map paths to blob SHAs",
  );
  need(isObject(controls) && SHA.test(controls[WORKFLOW_PATH] ?? ""), `controls must include ${WORKFLOW_PATH}`);
  for (const key of RUNTIME_TOOL_KEYS) need(nonEmpty(profile.tools?.runtime?.[key]), `tools.runtime.${key} is required`);
  for (const key of MEDIA_TOOL_KEYS) need(nonEmpty(profile.tools?.media?.[key]), `tools.media.${key} is required`);
  need(
    Array.isArray(profile.acceptedRunnerImages) && profile.acceptedRunnerImages.length > 0 && profile.acceptedRunnerImages.every(nonEmpty),
    "acceptedRunnerImages must list at least one image version",
  );
  for (const runner of ["pytest", "vitest", "node"]) {
    need(isNonEmptyIdList(profile.inventory?.[runner]), `inventory.${runner} must be a nonempty list of unique IDs`);
  }
  need(
    Array.isArray(profile.skipAllowlist) && profile.skipAllowlist.every((entry) => nonEmpty(entry?.id) && nonEmpty(entry?.reason)),
    "skipAllowlist entries need an id and a reason",
  );
  const calibration = profile.calibration;
  need(
    Array.isArray(calibration?.runs) &&
      calibration.runs.length > 0 &&
      calibration.runs.every((run) => Number.isInteger(run?.runId) && Number.isInteger(run?.attempt) && SHA.test(run?.tree ?? "")),
    "calibration.runs must record each qualifying run, attempt and tree",
  );
  if (requireApproval) {
    const runs = Array.isArray(calibration?.runs) ? calibration.runs : [];
    need(
      runs.length >= 2 && new Set(runs.map((run) => `${run.runId}:${run.attempt}`)).size === runs.length && new Set(runs.map((run) => run.tree)).size === 1,
      "a qualified profile needs at least two distinct calibration runs on the same tree",
    );
    need(profile.qualified === true, "profile is not marked qualified");
    const approval = profile.approval;
    need(
      isObject(approval) && nonEmpty(approval.by) && !Number.isNaN(Date.parse(approval.at ?? "")) && nonEmpty(approval.reference),
      "approval needs by, an ISO date and a reference to the retained decision",
    );
    need(isObject(approval) && approval.profileDigest === profileDigest(profile), "approval.profileDigest does not match this profile");
  }
  return problems;
}

// Builds an unqualified draft from one clean calibration run. Qualification
// review sets `qualified`, `approval` and any skip allowlist; nothing here does.
export function draftProfileFromEvidence({ manifest, controls, run }) {
  return {
    schemaVersion: PROFILE_SCHEMA_VERSION,
    qualified: false,
    approval: null,
    command: manifest.command,
    calibration: {
      runs: [{ runId: run.id, attempt: run.run_attempt, tree: manifest.checkout.tree, url: run.html_url }],
    },
    controls: sortObject(controls),
    tools: {
      runtime: manifest.tools.runtime,
      media: manifest.tools.media,
      runnerImage: manifest.tools.runnerImage,
    },
    acceptedRunnerImages: [manifest.tools.runnerImage?.version].filter(Boolean),
    skipAllowlist: [],
    inventory: {
      pytest: manifest.inventory.pytest.ids,
      vitest: manifest.inventory.vitest.ids,
      node: (manifest.outcomes?.node ?? []).flatMap((entry) => entry.ids.map((id) => `${entry.command} > ${id}`)),
    },
  };
}

// Validates caller-supplied identifiers before they reach a subprocess or API path.
export function assertExpectedShape(expected) {
  if (
    !isObject(expected) ||
    !SHA.test(expected.tree ?? "") ||
    !REPOSITORY.test(expected.repository ?? "") ||
    !(Number.isInteger(expected.runId) && expected.runId > 0) ||
    !(Number.isInteger(expected.attempt) && expected.attempt > 0) ||
    !["pull_request", "push"].includes(expected.event) ||
    (expected.event === "pull_request" && !(Number.isInteger(expected.pullRequest) && expected.pullRequest > 0))
  ) {
    throw new EvidenceError(
      "Expected evidence must name the repository, run, exact attempt, event (with pull request) and delivered tree",
    );
  }
}

// Pure decision over already-fetched data. Every input except `manifest` is
// read from GitHub or reviewed local records, never from the run itself.
export function evaluateCloudEvidence({ expected, profile, run, jobs, commit, tree, history, dispositions, manifest, options = {} }) {
  const failures = [];
  const limitations = [];
  const suspended = new Set();
  const acceptedDispositions = [];
  const fail = (code, detail) => failures.push({ code, detail });
  const limit = (code, detail) => limitations.push({ code, detail });
  const finish = () => ({
    status: failures.length === 0 ? "pass" : "fail",
    profileDigest: isObject(profile) ? profileDigest(profile) : null,
    failures,
    limitations,
    acceptedDispositions,
    suspendedScopes: failures.length > 0 || suspended.has("all") ? ["all"] : [...suspended].sort(),
  });

  assertExpectedShape(expected);
  const problems = profileProblems(profile, { requireApproval: !options.calibration });
  for (const problem of problems) {
    fail(/qualified|approval/.test(problem) ? "profile-unqualified" : "malformed-profile", problem);
  }
  if (!isObject(manifest) || manifest.schemaVersion !== MANIFEST_SCHEMA_VERSION) {
    fail("malformed-manifest", "Evidence manifest is missing or has an unsupported schema version");
  }
  if (!isObject(run) || !Array.isArray(jobs) || !isObject(commit) || !isObject(tree) || !Array.isArray(history)) {
    fail("incomplete-github-facts", "Run, jobs, commit, tree and run history must all be read from GitHub");
  }
  if (failures.some((entry) => entry.code !== "profile-unqualified")) return finish();

  // Run identity and authoritative conclusion.
  if (run.path !== WORKFLOW_PATH || run.name !== WORKFLOW_NAME) {
    fail("wrong-workflow", `Run used ${run.path ?? "unknown"} (${run.name ?? "unnamed"})`);
  }
  if (run.repository?.full_name !== expected.repository) {
    fail("wrong-repository", `Run belongs to ${run.repository?.full_name ?? "unknown"}`);
  }
  if (run.head_repository?.full_name !== run.repository?.full_name) {
    fail("fork-unqualified", "Fork-originated runs are outside the qualified trust profile");
  }
  if (run.id !== expected.runId) fail("wrong-run", `GitHub returned run ${run.id}, expected ${expected.runId}`);
  if (run.run_attempt !== expected.attempt) {
    fail("wrong-attempt", `GitHub returned attempt ${run.run_attempt}, expected ${expected.attempt}`);
  }
  if (run.event !== expected.event) fail("wrong-event", `Run event ${run.event}, expected ${expected.event}`);
  if (run.status !== "completed") fail("run-incomplete", `Run status is ${run.status}`);
  else if (run.conclusion !== "success") fail("run-not-successful", `Run concluded ${run.conclusion}`);
  if (expected.event === "pull_request") {
    const numbers = (run.pull_requests ?? []).map((entry) => entry.number);
    if (!numbers.includes(expected.pullRequest)) {
      fail("wrong-pull-request", `Run is linked to pull requests [${numbers.join(", ")}], expected #${expected.pullRequest}`);
    }
  }

  // Job and step conclusions for this exact attempt.
  const matchingJobs = jobs.filter((job) => job.name === JOB_NAME && job.run_id === run.id);
  if (matchingJobs.length !== 1) {
    fail("wrong-job", `Expected exactly one "${JOB_NAME}" job in run ${run.id}, found ${matchingJobs.length}`);
  }
  const job = matchingJobs[0];
  if (job) {
    if (job.run_attempt !== expected.attempt) fail("wrong-attempt", `Job belongs to attempt ${job.run_attempt}`);
    if (job.head_sha !== run.head_sha) fail("wrong-job", "Job head SHA differs from its run");
    if (job.status !== "completed") fail("job-incomplete", `Job status is ${job.status}`);
    else if (job.conclusion !== "success") fail("job-not-successful", `Job concluded ${job.conclusion}`);
    const steps = new Map((job.steps ?? []).map((step) => [step.name, step]));
    for (const name of REQUIRED_STEPS) {
      const step = steps.get(name);
      if (!step) fail("missing-step", `Required step "${name}" did not run`);
      else if (step.conclusion !== "success") fail("step-not-successful", `Step "${name}" concluded ${step.conclusion}`);
    }
    for (const step of job.steps ?? []) {
      if (!REQUIRED_STEPS.includes(step.name) && !["success", "skipped"].includes(step.conclusion)) {
        fail("step-not-successful", `Step "${step.name}" concluded ${step.conclusion}`);
      }
    }
    if (!(job.labels ?? []).includes(profile.tools.runtime.runnerLabel)) {
      fail("runtime-drift", `Job labels [${(job.labels ?? []).join(", ")}] lack the qualified runner label`);
    }
    if (manifest.runner?.name !== job.runner_name) {
      fail("manifest-disagrees", "Manifest runner name differs from the job GitHub reports");
    }
  }

  // Attempt history on the same tested source: a later green attempt never
  // erases an unexplained failure.
  const resolved = new Map((dispositions ?? []).map((entry) => [`${entry.runId}:${entry.attempt}`, entry]));
  for (const entry of history) {
    if (entry.runId === run.id && entry.attempt === expected.attempt) continue;
    const key = `${entry.runId}:${entry.attempt}`;
    if (entry.status !== "completed") {
      fail("sibling-run-incomplete", `Run ${key} on the same source is ${entry.status}; its outcome is unknown`);
      continue;
    }
    if (entry.conclusion === "success") continue;
    const disposition = resolved.get(key);
    if (
      !disposition ||
      !DISPOSITION_CLASSES.includes(disposition.classification) ||
      !nonEmpty(disposition.explanation) ||
      !nonEmpty(disposition.evidence)
    ) {
      fail("unresolved-prior-failure", `Run ${key} concluded ${entry.conclusion} without a retained disposition`);
    } else {
      acceptedDispositions.push({ key, conclusion: entry.conclusion, ...disposition });
      limit("prior-failure-dispositioned", `Run ${key} (${entry.conclusion}) accepted as ${disposition.classification}; reviewer must audit`);
    }
  }
  limit("history-scope", "Prior attempts are those on the same head SHA or on the same branch with an identical head tree");

  // Tested tree: corroborate the manifest's checkout with GitHub's commit object.
  if (manifest.repository !== expected.repository) fail("manifest-disagrees", "Manifest names a different repository");
  if (manifest.run?.id !== run.id || manifest.run?.attempt !== expected.attempt) {
    fail("manifest-disagrees", "Manifest names a different run or attempt");
  }
  if (manifest.event?.name !== run.event) fail("manifest-disagrees", "Manifest event differs from GitHub");
  if (commit.sha !== manifest.checkout?.commit) {
    fail("manifest-disagrees", "GitHub commit object does not match the manifest checkout commit");
  }
  if (commit.tree?.sha !== manifest.checkout?.tree) {
    fail("manifest-disagrees", "GitHub reports a different tree for the checked-out commit");
  }
  const parents = (commit.parents ?? []).map((parent) => parent.sha);
  if (run.event === "pull_request") {
    if (parents.length !== 2 || parents[1] !== run.head_sha) {
      fail("not-pr-merge-commit", "Checked-out commit is not the merge of the run's pull request head");
    }
    if (manifest.event?.pullRequest?.headSha !== run.head_sha) {
      fail("manifest-disagrees", "Manifest pull request head differs from GitHub");
    }
    if (manifest.event?.pullRequest?.baseSha !== parents[0]) {
      limit("pr-base-moved", `Merge base parent ${parents[0]} differs from the event base ${manifest.event?.pullRequest?.baseSha}`);
    }
    limit("checkout-attested", "The merge commit is named by the collector; GitHub corroborates its tree and its head parent");
  } else if (commit.sha !== run.head_sha) {
    fail("wrong-tree", "Push run did not check out its head commit");
  }
  if (commit.tree?.sha !== expected.tree) {
    fail("wrong-tree", `Tested tree ${commit.tree?.sha} differs from delivered tree ${expected.tree}`);
  }
  const changedTracked = manifest.trackedState?.modified;
  if (!Array.isArray(changedTracked)) fail("incomplete-collection", "Post-gate tracked-file state was not recorded");
  else if (changedTracked.length > 0) {
    fail("tracked-state-changed", `The gate modified tracked files: ${changedTracked.slice(0, 5).join(", ")}`);
  }

  // Controls: read from GitHub's tree listing, not from the manifest.
  if (tree.sha !== commit.tree?.sha) fail("wrong-tree", "Tree listing does not belong to the tested commit");
  if (tree.truncated === true || !Array.isArray(tree.tree)) {
    fail("incomplete-github-facts", "GitHub tree listing was truncated; controls cannot be verified");
  } else {
    const controls = controlDigestsFromEntries(tree.tree);
    for (const change of diffMaps(profile.controls, controls)) {
      fail("control-drift", `${change.key}: qualified ${change.expected ?? "absent"}, tested ${change.actual ?? "absent"}`);
    }
    if (diffMaps(controls, manifest.controls ?? {}).length > 0) {
      fail("manifest-disagrees", "Manifest control digests differ from GitHub's tree listing");
    }
  }
  if (manifest.command !== profile.command) {
    fail("control-drift", `Command "${manifest.command}" is not the qualified "${VALIDATE_COMMAND}"`);
  }

  // Self-reported collection must be complete and agree with GitHub's result.
  if (manifest.collection?.complete !== true || (manifest.collection?.errors ?? []).length > 0) {
    fail("incomplete-collection", `Collection errors: ${(manifest.collection?.errors ?? ["not marked complete"]).join("; ")}`);
  }
  for (const [name, outcome] of Object.entries(manifest.stepOutcomes ?? {})) {
    if (outcome !== "success") fail("self-reported-failure", `Manifest records step ${name} as ${outcome}`);
  }

  // Tool profile: runtime drift fails everything, media drift only media.
  const tools = manifest.tools ?? {};
  for (const key of RUNTIME_TOOL_KEYS) {
    if (tools.runtime?.[key] !== profile.tools.runtime[key]) {
      fail("runtime-drift", `${key}: qualified ${profile.tools.runtime[key]}, tested ${tools.runtime?.[key]}`);
    }
  }
  const mediaChanges = MEDIA_TOOL_KEYS.filter((key) => !tools.media?.[key] || tools.media[key] !== profile.tools.media[key]);
  if (mediaChanges.length > 0) {
    suspended.add("media-sensitive");
    limit("media-tool-drift", `Unqualified media tool fields: ${mediaChanges.join(", ")}`);
  }
  if (!profile.acceptedRunnerImages.includes(tools.runnerImage?.version)) {
    suspended.add("media-sensitive");
    limit("runner-image-changed", `Runner image ${tools.runnerImage?.version ?? "unknown"} has no recorded profile exception`);
  }

  // pytest: JUnit identities and outcomes, with reporter parity.
  const pytest = manifest.inventory?.pytest;
  if (!isObject(pytest) || !isNonEmptyIdList(pytest.ids) || !isNonEmptyIdList(pytest.collectedIds)) {
    fail("incomplete-collection", "pytest inventory is missing or empty");
  } else {
    if (pytest.counts?.total !== pytest.ids.length) fail("incomplete-collection", "pytest counts disagree with its IDs");
    if (pytest.counts?.skipped !== (pytest.notPassed ?? []).filter((entry) => entry.outcome === "skipped").length) {
      fail("incomplete-collection", "pytest skip count disagrees with its skipped outcomes");
    }
    if (pytest.counts?.failed !== 0 || pytest.counts?.errors !== 0) {
      fail("tests-not-passed", `pytest reported ${pytest.counts?.failed} failures and ${pytest.counts?.errors} errors`);
    }
    const allowedSkips = new Set(profile.skipAllowlist.map((entry) => entry.id));
    for (const entry of pytest.notPassed ?? []) {
      if (entry.outcome === "skipped" && !allowedSkips.has(entry.id)) {
        fail("unqualified-skip", `${entry.id} skipped: ${entry.reason ?? "no reason"}`);
      }
    }
    const reported = [...pytest.ids].sort();
    const collected = [...pytest.collectedIds].sort();
    if (reported.length !== collected.length || reported.some((id, index) => id !== collected[index])) {
      fail("reporter-collection-mismatch", "JUnit-reported test IDs differ from plain pytest collection");
    }
    requireInventory("pytest", profile.inventory.pytest, pytest.ids);
  }

  // Vitest: listed identities, and the gate's own run summaries for outcomes.
  const vitestIds = manifest.inventory?.vitest?.ids;
  const vitestRuns = manifest.outcomes?.vitest;
  if (!isNonEmptyIdList(vitestIds) || !Array.isArray(vitestRuns) || vitestRuns.length === 0) {
    fail("incomplete-collection", "Vitest inventory or run summaries are missing");
  } else {
    let total = 0;
    for (const counts of vitestRuns) {
      total += counts.total ?? 0;
      if (counts.passed !== counts.total) fail("tests-not-passed", `Vitest passed ${counts.passed} of ${counts.total}`);
      for (const [outcome, value] of Object.entries(counts)) {
        if (outcome === "total" || outcome === "passed" || value === 0) continue;
        fail(["skipped", "todo"].includes(outcome) ? "unqualified-skip" : "tests-not-passed", `Vitest reported ${value} ${outcome}`);
      }
    }
    if (total !== vitestIds.length) fail("incomplete-collection", `Vitest ran ${total} tests but listed ${vitestIds.length}`);
    requireInventory("vitest", profile.inventory.vitest, vitestIds);
  }

  // node:test: identities and counts per invocation from the gate's output.
  const nodeRuns = manifest.outcomes?.node;
  if (!Array.isArray(nodeRuns) || nodeRuns.length === 0) {
    fail("incomplete-collection", "node:test outcomes are missing");
  } else {
    for (const entry of nodeRuns) {
      const counts = entry.counts ?? {};
      if (counts.tests === undefined || counts.tests !== entry.ids?.length || counts.pass !== counts.tests) {
        fail("incomplete-collection", `${entry.command}: ${counts.tests} tests, ${entry.ids?.length} named, ${counts.pass} passed`);
      }
      if (counts.fail || counts.cancelled) fail("tests-not-passed", `${entry.command}: ${counts.fail} failed, ${counts.cancelled} cancelled`);
      if (counts.skipped || counts.todo) fail("unqualified-skip", `${entry.command}: ${counts.skipped} skipped, ${counts.todo} todo`);
    }
    requireInventory(
      "node",
      profile.inventory.node,
      nodeRuns.flatMap((entry) => (entry.ids ?? []).map((id) => `${entry.command} > ${id}`)),
    );
  }
  limit(
    "outcome-by-step-only",
    "Lint, type checks and generated-currentness are proven by the GitHub step conclusion, not per-check reports",
  );

  return finish();

  function requireInventory(runner, required, present) {
    const missing = missingFrom(required, present);
    if (missing.length > 0) {
      fail("incomplete-coverage", `${missing.length} required ${runner} IDs absent, e.g. ${missing.slice(0, 3).join(", ")}`);
    }
    const added = present.length - (required.length - missing.length);
    if (added > 0) limit("inventory-added", `${added} ${runner} IDs beyond the qualified inventory`);
  }
}

// Exit decision for a caller-requested scope. Suspended media scope never
// satisfies a full-scope request.
export function scopeAccepted(report, scope) {
  if (!SCOPES.includes(scope)) throw new EvidenceError(`Unknown scope ${scope}; use ${SCOPES.join(" or ")}`);
  if (report.status !== "pass") return false;
  const allowed = scope === "full" ? [] : ["media-sensitive"];
  return report.suspendedScopes.every((entry) => allowed.includes(entry));
}

// Phase timing from GitHub's step records, for qualification runtime reports.
export function stepDurations(job) {
  return (job?.steps ?? []).map((step) => ({
    name: step.name,
    conclusion: step.conclusion,
    seconds:
      step.started_at && step.completed_at ? (Date.parse(step.completed_at) - Date.parse(step.started_at)) / 1000 : null,
  }));
}

const MAX_HISTORY_PAGES = 10;

// Reads every page of a filtered run listing; refuses beyond the cap rather
// than evaluate an incomplete history.
async function readRunsPages(getJson, endpoint) {
  const runs = [];
  for (let page = 1; page <= MAX_HISTORY_PAGES; page += 1) {
    const response = await getJson(`${endpoint}&page=${page}`);
    const batch = response.workflow_runs ?? [];
    runs.push(...batch);
    if (runs.length >= (response.total_count ?? 0)) return runs;
    if (batch.length === 0) break;
  }
  throw new EvidenceError("Run history is incomplete or exceeds the page cap; refusing to evaluate an incomplete history");
}

// Reads every authoritative fact through a caller-supplied read-only JSON
// fetcher (`gh api` in the CLI, stubs in tests). Responses are data only.
export async function gatherGitHubFacts(getJson, { repository, runId, attempt, manifestCommit }) {
  if (!REPOSITORY.test(repository ?? "") || !(runId > 0) || !(attempt > 0) || !SHA.test(manifestCommit ?? "")) {
    throw new EvidenceError("Refusing GitHub reads for a malformed repository, run, attempt or manifest commit");
  }
  const base = `repos/${repository}`;
  const run = await getJson(`${base}/actions/runs/${runId}/attempts/${attempt}`);
  const jobsPage = await getJson(`${base}/actions/runs/${runId}/attempts/${attempt}/jobs?per_page=100`);
  const commit = await getJson(`${base}/git/commits/${manifestCommit}`);
  const tree = await getJson(`${base}/git/trees/${commit.tree.sha}?recursive=1`);

  // Same tested source: the same head SHA, or an identical head tree on the
  // same branch (a recommit of unchanged content gets a new SHA).
  const headTrees = new Map();
  const headTree = async (sha) => {
    if (!headTrees.has(sha)) headTrees.set(sha, (await getJson(`${base}/git/commits/${sha}`)).tree.sha);
    return headTrees.get(sha);
  };
  const runsEndpoint = `${base}/actions/workflows/validate.yml/runs?per_page=100`;
  const candidates = new Map();
  for (const sibling of await readRunsPages(getJson, `${runsEndpoint}&head_sha=${run.head_sha}`)) candidates.set(sibling.id, sibling);
  for (const sibling of await readRunsPages(getJson, `${runsEndpoint}&branch=${encodeURIComponent(run.head_branch)}`)) {
    candidates.set(sibling.id, sibling);
  }
  const currentTree = await headTree(run.head_sha);
  const history = [];
  for (const sibling of [...candidates.values()].sort((left, right) => left.id - right.id)) {
    if (sibling.head_sha !== run.head_sha && (await headTree(sibling.head_sha)) !== currentTree) continue;
    for (let index = 1; index <= sibling.run_attempt; index += 1) {
      const attemptRun =
        sibling.run_attempt === index ? sibling : await getJson(`${base}/actions/runs/${sibling.id}/attempts/${index}`);
      history.push({
        runId: sibling.id,
        attempt: index,
        headSha: sibling.head_sha,
        event: attemptRun.event,
        status: attemptRun.status,
        conclusion: attemptRun.conclusion,
      });
    }
  }
  return { run, jobs: jobsPage.jobs ?? [], commit, tree, history };
}
