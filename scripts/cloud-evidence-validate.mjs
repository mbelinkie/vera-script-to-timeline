#!/usr/bin/env node
// Judges one exact Validate run attempt against a qualified profile using
// read-only GitHub metadata. Exit 0 only when every check passes.
//
//   node scripts/cloud-evidence-validate.mjs --repo owner/name --run <id> --attempt <n>
//     --event pull_request --pr <number> --delivered <rev> --profile <file>
//     [--dispositions <file>] [--manifest <file>]
//   node scripts/cloud-evidence-validate.mjs --draft-profile <out> --repo ... --run ... --attempt ... [--manifest <file>]

import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  ARTIFACT_PREFIX,
  controlDigestsFromEntries,
  draftProfileFromEvidence,
  evaluateCloudEvidence,
  EvidenceError,
  gatherGitHubFacts,
  JOB_NAME,
  stepDurations,
} from "./cloud-evidence-lib.mjs";

export function parseArguments(values) {
  const options = {};
  for (let index = 0; index < values.length; index += 1) {
    const flag = values[index];
    if (!flag.startsWith("--") || index + 1 >= values.length) throw new EvidenceError(`Unexpected argument ${flag}`);
    options[flag.slice(2)] = values[(index += 1)];
  }
  for (const name of ["repo", "run", "attempt"]) {
    if (!options[name]) throw new EvidenceError(`--${name} is required`);
  }
  if (!options["draft-profile"]) {
    for (const name of ["event", "profile"]) {
      if (!options[name]) throw new EvidenceError(`--${name} is required`);
    }
    if (!options["expected-tree"] && !options.delivered) {
      throw new EvidenceError("--delivered <rev> or --expected-tree <sha> is required");
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
  gh(["run", "download", options.run, "--repo", options.repo, "--name", `${ARTIFACT_PREFIX}${options.attempt}`, "--dir", directory]);
  return readJson(path.join(directory, "manifest.json"));
}

function deliveredTree(options) {
  if (options["expected-tree"]) return options["expected-tree"];
  const result = spawnSync("git", ["rev-parse", "--verify", `${options.delivered}^{tree}`], { encoding: "utf8" });
  if (result.status !== 0) throw new EvidenceError(`Cannot resolve delivered tree for ${options.delivered}`);
  return result.stdout.trim();
}

export async function main(values, { getJson, log = console.log } = {}) {
  const options = parseArguments(values);
  const readGitHub = getJson ?? (async (endpoint) => JSON.parse(gh(["api", endpoint])));
  const manifest = loadManifest(options);
  const facts = await gatherGitHubFacts(readGitHub, {
    repository: options.repo,
    runId: Number(options.run),
    attempt: Number(options.attempt),
    manifestCommit: manifest.checkout?.commit,
  });

  if (options["draft-profile"]) {
    const draft = draftProfileFromEvidence({ manifest, controls: controlDigestsFromEntries(facts.tree.tree ?? []) });
    writeFileSync(options["draft-profile"], `${JSON.stringify(draft, null, 2)}\n`);
    log(`Wrote unqualified draft profile to ${options["draft-profile"]}; qualification review must approve it.`);
    return 0;
  }

  const report = evaluateCloudEvidence({
    expected: {
      repository: options.repo,
      runId: Number(options.run),
      attempt: Number(options.attempt),
      event: options.event,
      pullRequest: options.pr === undefined ? undefined : Number(options.pr),
      tree: deliveredTree(options),
    },
    profile: readJson(options.profile),
    dispositions: options.dispositions ? readJson(options.dispositions) : [],
    manifest,
    ...facts,
  });
  const job = facts.jobs.find((entry) => entry.name === JOB_NAME);
  log(
    JSON.stringify(
      {
        ...report,
        run: { url: facts.run.html_url, id: facts.run.id, attempt: facts.run.run_attempt, event: facts.run.event },
        testedTree: facts.commit.tree?.sha,
        testedCommit: facts.commit.sha,
        steps: stepDurations(job),
        pytest: manifest.inventory?.pytest?.counts ?? null,
        vitestTests: manifest.inventory?.vitest?.ids?.length ?? null,
      },
      null,
      2,
    ),
  );
  return report.status === "pass" ? 0 : 1;
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
