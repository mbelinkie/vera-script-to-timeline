// Cloud validation evidence helpers for issue #196.
//
// The workflow-side collector records what a run consumed (tree, controls,
// tools, inventory). Authority over whether that run passed comes only from
// independently read GitHub metadata; a manifest never certifies itself.

export const MANIFEST_SCHEMA_VERSION = 1;
export const PROFILE_SCHEMA_VERSION = 1;

export const WORKFLOW_PATH = ".github/workflows/validate.yml";
export const WORKFLOW_NAME = "Validate";
export const JOB_NAME = "TypeScript and Python";
export const VALIDATE_COMMAND = "VITEST_MAX_WORKERS=1 npm run validate";
export const ARTIFACT_PREFIX = "vera-validation-evidence-attempt-";

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
// A run whose controls differ from the qualified profile cannot self-certify.
const CONTROL_PATTERNS = Object.freeze([
  /^\.github\/workflows\/validate\.yml$/,
  /^\.nvmrc$/,
  /^\.python-version$/,
  /^package\.json$/,
  /^package-lock\.json$/,
  /^pyproject\.toml$/,
  /^uv\.lock$/,
  /^eslint\.config\.mjs$/,
  /^tsconfig[^/]*\.json$/,
  /^vitest\.(config|workspace)\.[^/]+$/,
  /^packages\/[^/]+\/(package\.json|pyproject\.toml|tsconfig[^/]*\.json)$/,
  /^packages\/[^/]+\/vite(st)?\.config\.[^/]+$/,
  /^packages\/contracts\/scripts\/generate-contracts\.mjs$/,
  /(^|\/)conftest\.py$/,
  /^scripts\/cloud-evidence[^/]*\.mjs$/,
]);

const VITEST_SKIP_PATTERN = /\b(?:it|test|describe|suite|bench)\s*\.\s*(?:skip|todo|only|skipIf|runIf)\b|\bx(?:it|describe)\s*\(/g;

const RUNTIME_TOOL_KEYS = Object.freeze(["node", "npm", "uv", "python", "os", "arch", "runnerLabel"]);
const MEDIA_TOOL_KEYS = Object.freeze([
  "ffmpegVersion",
  "ffprobeVersion",
  "ffmpegSha256",
  "ffprobeSha256",
  "capabilitiesDigest",
]);

const DISPOSITION_CLASSES = Object.freeze(["infrastructure", "operator-cancelled", "diagnosed-flake"]);

export class EvidenceError extends Error {}

export function isControlPath(filePath) {
  return CONTROL_PATTERNS.some((pattern) => pattern.test(filePath));
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

// `git ls-tree -r HEAD` lines: "<mode> <type> <sha>\t<path>".
export function parseLsTree(output) {
  return output
    .split("\n")
    .filter(Boolean)
    .map((line) => {
      const tab = line.indexOf("\t");
      const [mode, type, sha] = line.slice(0, tab).split(" ");
      return { mode, type, sha, path: line.slice(tab + 1) };
    });
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

export function findVitestSkipMarkers(source) {
  return [...source.matchAll(VITEST_SKIP_PATTERN)].map((match) => match[0].replace(/\s+/g, ""));
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

// Builds an unqualified draft from one run's evidence. Qualification review
// sets `qualified`, `approval` and any skip allowlist; nothing here does.
export function draftProfileFromEvidence({ manifest, controls }) {
  return {
    schemaVersion: PROFILE_SCHEMA_VERSION,
    qualified: false,
    approval: null,
    command: manifest.command,
    calibration: {
      runId: manifest.run.id,
      attempt: manifest.run.attempt,
      tree: manifest.checkout.tree,
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
    },
  };
}

// Pure decision over already-fetched data. Every input except `manifest` is
// read from GitHub or reviewed local records, never from the run itself.
export function evaluateCloudEvidence({ expected, profile, run, jobs, commit, tree, history, dispositions, manifest }) {
  const failures = [];
  const limitations = [];
  const suspended = new Set();
  const fail = (code, detail) => failures.push({ code, detail });
  const limit = (code, detail) => limitations.push({ code, detail });

  if (
    !isObject(expected) ||
    !/^[0-9a-f]{40}$/.test(expected.tree ?? "") ||
    typeof expected.repository !== "string" ||
    !Number.isInteger(expected.runId) ||
    !Number.isInteger(expected.attempt) ||
    !["pull_request", "push"].includes(expected.event) ||
    (expected.event === "pull_request" && !Number.isInteger(expected.pullRequest))
  ) {
    throw new EvidenceError(
      "Expected evidence must name the repository, run, exact attempt, event (with pull request) and delivered tree",
    );
  }
  if (!isObject(profile) || profile.schemaVersion !== PROFILE_SCHEMA_VERSION) {
    fail("malformed-profile", "Qualification profile is missing or has an unsupported schema version");
  } else if (profile.qualified !== true || !isObject(profile.approval)) {
    fail("profile-unqualified", "Profile has not been qualified and approved; local acceptance remains required");
  }
  if (!isObject(manifest) || manifest.schemaVersion !== MANIFEST_SCHEMA_VERSION) {
    fail("malformed-manifest", "Evidence manifest is missing or has an unsupported schema version");
  }
  if (!isObject(run) || !Array.isArray(jobs) || !isObject(commit) || !isObject(tree) || !Array.isArray(history)) {
    fail("incomplete-github-facts", "Run, jobs, commit, tree and run history must all be read from GitHub");
  }
  if (failures.some((entry) => entry.code !== "profile-unqualified")) {
    return { status: "fail", failures, limitations, suspendedScopes: ["all"] };
  }

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
    if (!(job.labels ?? []).includes(profile.tools?.runtime?.runnerLabel)) {
      fail("runtime-drift", `Job labels [${(job.labels ?? []).join(", ")}] lack the qualified runner label`);
    }
    if (manifest.runner?.name !== job.runner_name) {
      fail("manifest-disagrees", "Manifest runner name differs from the job GitHub reports");
    }
  }

  // Attempt history: a later green attempt never erases an unexplained failure.
  const resolved = new Map((dispositions ?? []).map((entry) => [`${entry.runId}:${entry.attempt}`, entry]));
  for (const entry of history) {
    if (entry.runId === run.id && entry.attempt === expected.attempt) continue;
    const key = `${entry.runId}:${entry.attempt}`;
    if (entry.status !== "completed") {
      fail("sibling-run-incomplete", `Run ${key} on the same head is ${entry.status}; its outcome is unknown`);
      continue;
    }
    if (entry.conclusion === "success") continue;
    const disposition = resolved.get(key);
    if (
      !disposition ||
      !DISPOSITION_CLASSES.includes(disposition.classification) ||
      !disposition.explanation?.trim() ||
      !disposition.evidence?.trim()
    ) {
      fail("unresolved-prior-failure", `Run ${key} concluded ${entry.conclusion} without a retained disposition`);
    } else if (disposition.classification === "diagnosed-flake") {
      limit("flake-disposition", `Run ${key} was dispositioned as a flake; reviewer must confirm under the flake policy`);
    }
  }

  // Tested tree: corroborate the manifest's checkout with GitHub's commit object.
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
  } else if (commit.sha !== run.head_sha) {
    fail("wrong-tree", "Push run did not check out its head commit");
  }
  if (commit.tree?.sha !== expected.tree) {
    fail("wrong-tree", `Tested tree ${commit.tree?.sha} differs from delivered tree ${expected.tree}`);
  }

  // Controls: read from GitHub's tree listing, not from the manifest.
  if (tree.sha !== commit.tree?.sha) fail("wrong-tree", "Tree listing does not belong to the tested commit");
  if (tree.truncated === true || !Array.isArray(tree.tree)) {
    fail("incomplete-github-facts", "GitHub tree listing was truncated; controls cannot be verified");
  } else {
    const controls = controlDigestsFromEntries(tree.tree);
    for (const change of diffMaps(profile.controls ?? {}, controls)) {
      fail("control-drift", `${change.key}: qualified ${change.expected ?? "absent"}, tested ${change.actual ?? "absent"}`);
    }
    if (diffMaps(controls, manifest.controls ?? {}).length > 0) {
      fail("manifest-disagrees", "Manifest control digests differ from GitHub's tree listing");
    }
  }
  if (manifest.command !== profile.command || profile.command !== VALIDATE_COMMAND) {
    fail("control-drift", `Command "${manifest.command}" is not the qualified "${VALIDATE_COMMAND}"`);
  }

  // Self-reported collection must be complete and agree with GitHub's result.
  if (manifest.collection?.complete !== true || (manifest.collection?.errors ?? []).length > 0) {
    fail("incomplete-collection", `Collection errors: ${(manifest.collection?.errors ?? ["not marked complete"]).join("; ")}`);
  }
  for (const [name, outcome] of Object.entries(manifest.stepOutcomes ?? {})) {
    if (outcome !== "success") fail("self-reported-failure", `Manifest records step ${name} as ${outcome}`);
  }

  // Tool profile: runtime drift suspends everything, media drift only media.
  const tools = manifest.tools ?? {};
  for (const key of RUNTIME_TOOL_KEYS) {
    if (tools.runtime?.[key] !== profile.tools?.runtime?.[key]) {
      fail("runtime-drift", `${key}: qualified ${profile.tools?.runtime?.[key]}, tested ${tools.runtime?.[key]}`);
    }
  }
  const mediaChanges = MEDIA_TOOL_KEYS.filter((key) => !tools.media?.[key] || tools.media[key] !== profile.tools?.media?.[key]);
  if (mediaChanges.length > 0) {
    suspended.add("media-sensitive");
    limit("media-tool-drift", `Unqualified media tool fields: ${mediaChanges.join(", ")}`);
  }
  if (!(profile.acceptedRunnerImages ?? []).includes(tools.runnerImage?.version)) {
    suspended.add("media-sensitive");
    limit("runner-image-changed", `Runner image ${tools.runnerImage?.version ?? "unknown"} has no recorded profile exception`);
  }

  // Inventory, outcomes and skips.
  const pytest = manifest.inventory?.pytest;
  const vitest = manifest.inventory?.vitest;
  if (!isObject(pytest) || !Array.isArray(pytest.ids) || !Array.isArray(pytest.collectedIds)) {
    fail("incomplete-collection", "pytest inventory is missing");
  } else {
    if (pytest.counts?.failed !== 0 || pytest.counts?.errors !== 0) {
      fail("tests-not-passed", `pytest reported ${pytest.counts?.failed} failures and ${pytest.counts?.errors} errors`);
    }
    const allowedSkips = new Set((profile.skipAllowlist ?? []).map((entry) => entry.id));
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
    const missing = missingFrom(profile.inventory?.pytest ?? [], pytest.ids);
    if (missing.length > 0) fail("incomplete-coverage", `${missing.length} required pytest IDs absent, e.g. ${missing.slice(0, 3).join(", ")}`);
    const added = pytest.ids.length - ((profile.inventory?.pytest ?? []).length - missing.length);
    if (added > 0) limit("inventory-added", `${added} pytest IDs beyond the qualified inventory`);
  }
  if (!isObject(vitest) || !Array.isArray(vitest.ids) || !Array.isArray(vitest.skipMarkers)) {
    fail("incomplete-collection", "Vitest inventory is missing");
  } else {
    const missing = missingFrom(profile.inventory?.vitest ?? [], vitest.ids);
    if (missing.length > 0) fail("incomplete-coverage", `${missing.length} required Vitest IDs absent, e.g. ${missing.slice(0, 3).join(", ")}`);
    for (const marker of vitest.skipMarkers) fail("unqualified-skip", `${marker.file} contains ${marker.marker}`);
  }
  limit(
    "outcome-by-step-only",
    "Lint, type checks, generated-currentness, Vitest and node:test outcomes are proven by the GitHub step conclusion, not per-test reports",
  );

  if (failures.length > 0) suspended.add("all");
  return {
    status: failures.length === 0 ? "pass" : "fail",
    failures,
    limitations,
    suspendedScopes: suspended.has("all") ? ["all"] : [...suspended].sort(),
  };
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

// Reads every authoritative fact through a caller-supplied read-only JSON
// fetcher (`gh api` in the CLI, stubs in tests). Responses are data only.
export async function gatherGitHubFacts(getJson, { repository, runId, attempt, manifestCommit }) {
  const base = `repos/${repository}`;
  const run = await getJson(`${base}/actions/runs/${runId}/attempts/${attempt}`);
  const jobsPage = await getJson(`${base}/actions/runs/${runId}/attempts/${attempt}/jobs?per_page=100`);
  const commit = await getJson(`${base}/git/commits/${manifestCommit}`);
  const tree = await getJson(`${base}/git/trees/${commit.tree.sha}?recursive=1`);
  const runsPage = await getJson(
    `${base}/actions/workflows/validate.yml/runs?head_sha=${run.head_sha}&per_page=100`,
  );
  if ((runsPage.total_count ?? 0) > (runsPage.workflow_runs ?? []).length) {
    throw new EvidenceError("Run history exceeds one page; refusing to evaluate an incomplete history");
  }
  const history = [];
  for (const sibling of runsPage.workflow_runs ?? []) {
    for (let index = 1; index <= sibling.run_attempt; index += 1) {
      const attemptRun =
        sibling.run_attempt === index ? sibling : await getJson(`${base}/actions/runs/${sibling.id}/attempts/${index}`);
      history.push({
        runId: sibling.id,
        attempt: index,
        event: attemptRun.event,
        status: attemptRun.status,
        conclusion: attemptRun.conclusion,
      });
    }
  }
  return { run, jobs: jobsPage.jobs ?? [], commit, tree, history };
}
