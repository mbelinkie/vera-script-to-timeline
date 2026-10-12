#!/usr/bin/env node
// Judges one exact Validate run attempt against a qualified profile using
// read-only GitHub metadata. Exit 0 only when every check passes for the
// requested scope (default: full).
//
//   node scripts/cloud-evidence-validate.mjs --repo owner/name --run <id> --attempt <n>
//     --event pull_request --pr <number> --delivered <rev> --profile <file>
//     [--scope full|excluding-media-sensitive] [--dispositions <file>] [--manifest <file>]
//   node scripts/cloud-evidence-validate.mjs --draft-profile <out> --repo ... --run ... --attempt ...
//     [--dispositions <file>] [--manifest <file>]

import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  ARTIFACT_PREFIX,
  assertExpectedShape,
  controlDigestsFromEntries,
  draftProfileFromEvidence,
  evaluateCloudEvidence,
  EvidenceError,
  gatherGitHubFacts,
  JOB_NAME,
  profileDigest,
  scopeAccepted,
  SCOPES,
  stepDurations,
} from "./cloud-evidence-lib.mjs";

const FLAGS = new Set(["repo", "run", "attempt", "event", "pr", "delivered", "expected-tree", "profile", "scope", "dispositions", "manifest", "draft-profile"]);

function positiveInteger(value, name) {
  if (!/^[1-9][0-9]*$/.test(value ?? "")) throw new EvidenceError(`--${name} must be a positive integer`);
  return Number(value);
}

export function parseArguments(values) {
  const options = {};
  for (let index = 0; index < values.length; index += 1) {
    const flag = values[index];
    if (!flag.startsWith("--") || !FLAGS.has(flag.slice(2)) || index + 1 >= values.length) {
      throw new EvidenceError(`Unexpected argument ${flag}`);
    }
    options[flag.slice(2)] = values[(index += 1)];
  }
  if (!/^[A-Za-z0-9-]+\/[A-Za-z0-9._-]+$/.test(options.repo ?? "")) throw new EvidenceError("--repo must be owner/name");
  options.runId = positiveInteger(options.run, "run");
  options.attemptNumber = positiveInteger(options.attempt, "attempt");
  options.scope ??= "full";
  if (!SCOPES.includes(options.scope)) throw new EvidenceError(`--scope must be one of ${SCOPES.join(", ")}`);
  if (!options["draft-profile"]) {
    if (!["pull_request", "push"].includes(options.event)) throw new EvidenceError("--event must be pull_request or push");
    if (options.event === "pull_request") options.pullRequest = positiveInteger(options.pr, "pr");
    if (!options.profile) throw new EvidenceError("--profile is required");
    if (!options["expected-tree"] && !options.delivered) {
      throw new EvidenceError("--delivered <rev> or --expected-tree <sha> is required");
    }
    if (options["expected-tree"] && !/^[0-9a-f]{40}$/.test(options["expected-tree"])) {
      throw new EvidenceError("--expected-tree must be a 40-character tree SHA");
    }
  }
  return options;
}

function gh(args) {
  const result = spawnSync("gh", args, { encoding: "utf8", maxBuffer: 256 * 1024 * 1024 });
  if (result.error || result.status !== 0) {
    throw new EvidenceError(`gh ${args[0]} failed: ${(result.error?.message ?? result.stderr).trim()}`);
  }
  return result.stdout;
}

function readJson(filePath) {
  return JSON.parse(readFileSync(filePath, "utf8"));
}

function loadManifest(options) {
  if (options.manifest) return readJson(options.manifest);
  // Downloaded artifacts are untrusted data: fresh directory, parsed as JSON only.
  const directory = mkdtempSync(path.join(os.tmpdir(), "vera-cloud-evidence-"));
  gh(["run", "download", String(options.runId), "--repo", options.repo, "--name", `${ARTIFACT_PREFIX}${options.attemptNumber}`, "--dir", directory]);
  return readJson(path.join(directory, "manifest.json"));
}

function deliveredTree(options) {
  if (options["expected-tree"]) return options["expected-tree"];
  const result = spawnSync("git", ["rev-parse", "--verify", "--end-of-options", `${options.delivered}^{tree}`], { encoding: "utf8" });
  if (result.status !== 0) throw new EvidenceError(`Cannot resolve delivered tree for ${options.delivered}`);
  return result.stdout.trim();
}

function summary(report, facts, manifest) {
  const job = facts.jobs.find((entry) => entry.name === JOB_NAME);
  return {
    ...report,
    run: { url: facts.run.html_url, id: facts.run.id, attempt: facts.run.run_attempt, event: facts.run.event },
    testedTree: facts.commit.tree?.sha,
    testedCommit: facts.commit.sha,
    testedBase: facts.commit.parents?.[0]?.sha ?? null,
    history: facts.history,
    steps: stepDurations(job),
    pytest: manifest.inventory?.pytest?.counts ?? null,
    pytestSlowest: manifest.inventory?.pytest?.slowest ?? null,
    vitest: manifest.outcomes?.vitest ?? null,
    node: (manifest.outcomes?.node ?? []).map(({ command, counts }) => ({ command, counts })),
  };
}

export async function main(values, { getJson, log = console.log } = {}) {
  const options = parseArguments(values);
  const readGitHub = getJson ?? (async (endpoint) => JSON.parse(gh(["api", endpoint])));
  const manifest = loadManifest(options);
  const facts = await gatherGitHubFacts(readGitHub, {
    repository: options.repo,
    runId: options.runId,
    attempt: options.attemptNumber,
    manifestCommit: manifest?.checkout?.commit,
  });
  const dispositions = options.dispositions ? readJson(options.dispositions) : [];

  if (options["draft-profile"]) {
    // A draft comes only from a clean, complete calibration run on its own tree.
    const draft = draftProfileFromEvidence({ manifest, controls: controlDigestsFromEntries(facts.tree.tree ?? []), run: facts.run });
    const pullRequest = facts.run.pull_requests?.[0]?.number;
    const expected = {
      repository: options.repo,
      runId: options.runId,
      attempt: options.attemptNumber,
      event: facts.run.event,
      pullRequest,
      tree: facts.commit.tree?.sha,
    };
    assertExpectedShape(expected);
    const report = evaluateCloudEvidence({ expected, profile: draft, dispositions, manifest, options: { calibration: true }, ...facts });
    if (report.status !== "pass" || report.suspendedScopes.length > 0) {
      log(JSON.stringify(summary(report, facts, manifest), null, 2));
      log("Refusing to draft a profile from a run that is not a clean, complete calibration.");
      return 1;
    }
    writeFileSync(options["draft-profile"], `${JSON.stringify(draft, null, 2)}\n`);
    log(`Wrote unqualified draft profile ${profileDigest(draft)} to ${options["draft-profile"]}; qualification review must approve it.`);
    return 0;
  }

  const expected = {
    repository: options.repo,
    runId: options.runId,
    attempt: options.attemptNumber,
    event: options.event,
    pullRequest: options.pullRequest,
    tree: deliveredTree(options),
  };
  const report = evaluateCloudEvidence({ expected, profile: readJson(options.profile), dispositions, manifest, ...facts });
  const accepted = scopeAccepted(report, options.scope);
  log(JSON.stringify({ ...summary(report, facts, manifest), requestedScope: options.scope, accepted }, null, 2));
  return accepted ? 0 : 1;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main(process.argv.slice(2)).then(
    (code) => process.exit(code),
    (error) => {
      console.error(error instanceof EvidenceError ? error.message : error);
      process.exit(2);
    },
  );
}
