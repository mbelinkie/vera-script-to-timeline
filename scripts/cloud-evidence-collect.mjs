#!/usr/bin/env node
// Runs in the Validate workflow after the gate. Records what the run consumed
// into one allowlisted manifest. It never decides whether the run passed:
// scripts/cloud-evidence-validate.mjs reads that from GitHub.

import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  controlDigestsFromEntries,
  findVitestSkipMarkers,
  MANIFEST_SCHEMA_VERSION,
  parseCollectOnly,
  parseJunit,
  parseLsTree,
  summarizePytest,
  VALIDATE_COMMAND,
} from "./cloud-evidence-lib.mjs";

const INPUT_TREES = ["contracts", "fixtures", "tests", "packages"];
const OUTCOME_VARIABLES = {
  preflight: "VERA_OUTCOME_PREFLIGHT",
  validate: "VERA_OUTCOME_VALIDATE",
  lockfiles: "VERA_OUTCOME_LOCKFILES",
};

function sha256(data) {
  return createHash("sha256").update(data).digest("hex");
}

function makeRunner(root, errors) {
  return function run(command, args, options = {}) {
    const result = spawnSync(command, args, {
      cwd: options.cwd ?? root,
      encoding: "utf8",
      env: options.env ?? process.env,
      maxBuffer: 64 * 1024 * 1024,
    });
    if (result.error || result.status !== 0) {
      const detail = (result.error?.message ?? result.stderr ?? "").trim().split("\n").slice(-2).join(" ");
      errors.push(`${options.label ?? command}: exit ${result.status ?? "none"} ${detail.slice(0, 300)}`);
      return null;
    }
    return result.stdout;
  };
}

function firstLine(text) {
  return text ? text.split("\n")[0].trim() : null;
}

function osRelease() {
  try {
    const fields = Object.fromEntries(
      readFileSync("/etc/os-release", "utf8")
        .split("\n")
        .filter((line) => line.includes("="))
        .map((line) => {
          const index = line.indexOf("=");
          return [line.slice(0, index), line.slice(index + 1).replace(/^"|"$/g, "")];
        }),
    );
    return `${fields.ID} ${fields.VERSION_ID}`;
  } catch {
    return `${process.platform}`;
  }
}

function mediaFingerprint(run, errors) {
  const binary = (name) => {
    const location = firstLine(run("sh", ["-c", `command -v ${name}`], { label: `locate ${name}` }));
    if (!location) return null;
    try {
      return sha256(readFileSync(location));
    } catch (error) {
      errors.push(`hash ${name}: ${error.message}`);
      return null;
    }
  };
  const capabilities = ["-encoders", "-decoders", "-filters", "-formats", "-buildconf"].map((flag) =>
    run("ffmpeg", ["-hide_banner", flag], { label: `ffmpeg ${flag}` }),
  );
  return {
    ffmpegVersion: firstLine(run("ffmpeg", ["-hide_banner", "-version"], { label: "ffmpeg -version" })),
    ffprobeVersion: firstLine(run("ffprobe", ["-hide_banner", "-version"], { label: "ffprobe -version" })),
    ffmpegSha256: binary("ffmpeg"),
    ffprobeSha256: binary("ffprobe"),
    capabilitiesDigest: capabilities.every((text) => text !== null) ? sha256(capabilities.join("\u0000")) : null,
    package: firstLine(run("dpkg-query", ["-W", "-f=${Version}", "ffmpeg"], { label: "dpkg-query ffmpeg" })),
  };
}

function listTestSources(directory) {
  const found = [];
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name === "dist") continue;
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) found.push(...listTestSources(target));
    else if (/\.(test|spec)\.[cm]?[jt]sx?$/.test(entry.name)) found.push(target);
  }
  return found;
}

function vitestInventory(root, run, errors) {
  const ids = [];
  const skipMarkers = [];
  const packagesDirectory = path.join(root, "packages");
  const vitestBinary = path.join(root, "node_modules", ".bin", "vitest");
  for (const name of readdirSync(packagesDirectory).sort()) {
    const packageDirectory = path.join(packagesDirectory, name);
    const manifestPath = path.join(packageDirectory, "package.json");
    if (!existsSync(manifestPath)) continue;
    const scripts = JSON.parse(readFileSync(manifestPath, "utf8")).scripts ?? {};
    if (!/\bvitest\b/.test(scripts.test ?? "")) continue;
    const output = path.join(process.env.RUNNER_TEMP ?? root, `vera-vitest-list-${name}.json`);
    if (run(vitestBinary, ["list", `--json=${output}`], { cwd: packageDirectory, label: `vitest list ${name}` }) === null) {
      continue;
    }
    try {
      for (const entry of JSON.parse(readFileSync(output, "utf8"))) {
        ids.push(`${path.relative(root, path.resolve(packageDirectory, entry.file))} > ${entry.name}`);
      }
    } catch (error) {
      errors.push(`vitest list ${name}: ${error.message}`);
    }
    for (const file of listTestSources(packageDirectory)) {
      for (const marker of findVitestSkipMarkers(readFileSync(file, "utf8"))) {
        skipMarkers.push({ file: path.relative(root, file), marker });
      }
    }
  }
  if (ids.length === 0) errors.push("vitest inventory is empty");
  return { ids: ids.sort(), skipMarkers };
}

function pytestInventory(root, evidenceDirectory, run, errors) {
  const junitPath = path.join(evidenceDirectory, "pytest-junit.xml");
  let cases = [];
  try {
    cases = parseJunit(readFileSync(junitPath, "utf8"));
  } catch (error) {
    errors.push(`pytest JUnit: ${error.message}`);
  }
  // Plain collection, without the reporter, proves the reporter changed nothing.
  const environment = { ...process.env };
  delete environment.PYTEST_ADDOPTS;
  const listing = run("uv", ["run", "--frozen", "pytest", "--collect-only", "-q"], {
    env: environment,
    label: "pytest --collect-only",
  });
  let collected = [];
  try {
    collected = listing === null ? [] : parseCollectOnly(listing);
  } catch (error) {
    errors.push(error.message);
  }
  return summarizePytest(cases, collected);
}

export function collectEvidence({ root, evidenceDirectory, environment = process.env }) {
  const errors = [];
  const run = makeRunner(root, errors);
  const commit = firstLine(run("git", ["rev-parse", "HEAD"], { label: "git rev-parse HEAD" }));
  const tree = firstLine(run("git", ["rev-parse", "HEAD^{tree}"], { label: "git rev-parse tree" }));
  const listing = run("git", ["ls-tree", "-r", "-t", "HEAD"], { label: "git ls-tree" });
  const entries = listing === null ? [] : parseLsTree(listing);
  const inputs = Object.fromEntries(
    INPUT_TREES.map((name) => [name, entries.find((entry) => entry.type === "tree" && entry.path === name)?.sha ?? null]),
  );
  for (const file of ["package-lock.json", "uv.lock"]) {
    inputs[file] = entries.find((entry) => entry.path === file)?.sha ?? null;
  }

  let pullRequest = null;
  if (environment.GITHUB_EVENT_NAME === "pull_request" && environment.GITHUB_EVENT_PATH) {
    const event = JSON.parse(readFileSync(environment.GITHUB_EVENT_PATH, "utf8"));
    pullRequest = {
      number: event.pull_request?.number ?? null,
      headSha: event.pull_request?.head?.sha ?? null,
      baseSha: event.pull_request?.base?.sha ?? null,
      baseRef: event.pull_request?.base?.ref ?? null,
    };
  }

  const stepOutcomes = Object.fromEntries(
    Object.entries(OUTCOME_VARIABLES).map(([name, variable]) => [name, environment[variable] || "not-run"]),
  );
  const manifest = {
    schemaVersion: MANIFEST_SCHEMA_VERSION,
    note: "Self-recorded inputs only. Run success is read from GitHub, never from this file.",
    repository: environment.GITHUB_REPOSITORY ?? null,
    run: {
      id: Number(environment.GITHUB_RUN_ID),
      attempt: Number(environment.GITHUB_RUN_ATTEMPT),
      job: environment.GITHUB_JOB ?? null,
      workflowRef: environment.GITHUB_WORKFLOW_REF ?? null,
      workflowSha: environment.GITHUB_WORKFLOW_SHA ?? null,
    },
    event: { name: environment.GITHUB_EVENT_NAME ?? null, ref: environment.GITHUB_REF ?? null, pullRequest },
    checkout: { commit, tree },
    command: VALIDATE_COMMAND,
    stepOutcomes,
    controls: controlDigestsFromEntries(entries),
    inputs,
    runner: { name: environment.RUNNER_NAME ?? null },
    tools: {
      runtime: {
        node: process.version,
        npm: firstLine(run("npm", ["--version"], { label: "npm --version" })),
        uv: firstLine(run("uv", ["--version"], { label: "uv --version" })),
        python: firstLine(
          run("uv", ["run", "--frozen", "python", "-c", "import platform; print(platform.python_version())"], {
            label: "python version",
          }),
        ),
        os: osRelease(),
        arch: `${process.arch}/${environment.RUNNER_ARCH ?? "unknown"}`,
        runnerLabel: environment.VERA_RUNNER_LABEL ?? null,
      },
      media: mediaFingerprint(run, errors),
      runnerImage: {
        os: environment.ImageOS ?? null,
        version: environment.ImageVersion ?? null,
        kernel: firstLine(run("uname", ["-r"], { label: "uname" })),
      },
    },
    inventory: {
      pytest: pytestInventory(root, evidenceDirectory, run, errors),
      vitest: vitestInventory(root, run, errors),
    },
  };
  manifest.collection = { complete: errors.length === 0, errors };
  return manifest;
}

function main() {
  const index = process.argv.indexOf("--output");
  const evidenceDirectory = index === -1 ? null : process.argv[index + 1];
  if (!evidenceDirectory) {
    console.error("Usage: node scripts/cloud-evidence-collect.mjs --output <directory>");
    process.exit(2);
  }
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  mkdirSync(evidenceDirectory, { recursive: true });
  let manifest;
  try {
    manifest = collectEvidence({ root, evidenceDirectory });
  } catch (error) {
    // An incomplete manifest fails validation later; it must not mask the gate.
    manifest = { schemaVersion: MANIFEST_SCHEMA_VERSION, collection: { complete: false, errors: [error.message] } };
  }
  writeFileSync(path.join(evidenceDirectory, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
  for (const error of manifest.collection.errors) console.log(`::warning title=Evidence collection incomplete::${error}`);
  console.log(`Evidence manifest written; collection complete: ${manifest.collection.complete}`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main();
}
