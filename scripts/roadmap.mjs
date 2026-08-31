#!/usr/bin/env node

import { readFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { assertMutationBudget, formatRateLimitReport, parseRateLimitResponse } from "./roadmap-rate-limit.mjs";

export const MODEL_CLASSES = ["luna", "terra", "sol"];
export const EFFORTS = ["low", "medium", "high", "xhigh", "max"];
export const STATUSES = ["Inbox", "Backlog", "Ready", "In progress", "Blocked", "In review", "Done"];

const VERA_ROADMAPS = new Map([
  ["mbelinkie/vera-research-video-clips", { owner: "mbelinkie", projectNumber: 1 }],
  ["mbelinkie/vera-script-to-timeline", { owner: "mbelinkie", projectNumber: 2 }],
]);

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

export function parseArguments(values) {
  const [command, ...rest] = values;
  const flags = new Map();
  const positionals = [];
  for (let index = 0; index < rest.length; index += 1) {
    const value = rest[index];
    if (!value.startsWith("--")) {
      positionals.push(value);
      continue;
    }
    const key = value.slice(2);
    const next = rest[index + 1];
    if (!next || next.startsWith("--")) flags.set(key, true);
    else {
      flags.set(key, next);
      index += 1;
    }
  }
  return { command, flags, positionals };
}

function required(flags, name) {
  const value = flags.get(name);
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`Missing required --${name}`);
  }
  return value.trim();
}

function runGh(args, input) {
  const result = spawnSync("gh", args, {
    cwd: root,
    encoding: "utf8",
    input,
    env: process.env,
  });
  if (result.status !== 0) {
    throw new Error((result.stderr || result.stdout || "GitHub command failed").trim());
  }
  return result.stdout.trim();
}

function rateLimit() {
  return parseRateLimitResponse(runGh(["api", "rate_limit", "--include"]));
}

function guardMutation(requiredRequests, graphqlRequests = 0) {
  const parsed = rateLimit();
  assertMutationBudget(parsed, requiredRequests, graphqlRequests);
  return parsed;
}

function routeClass(model) {
  const normalized = model.toLowerCase();
  return MODEL_CLASSES.find((candidate) => normalized === candidate || normalized.includes(`-${candidate}`));
}

export function routingProfile(labels) {
  const modelLabels = labels.filter((label) => label.startsWith("model:"));
  const effortLabels = labels.filter((label) => label.startsWith("effort:"));
  if (modelLabels.length !== 1 || effortLabels.length !== 1) {
    throw new Error("Ready work requires exactly one model label and one effort label");
  }
  const expectedModel = modelLabels[0].slice("model:".length);
  const expectedEffort = effortLabels[0].slice("effort:".length);
  if (!MODEL_CLASSES.includes(expectedModel) || !EFFORTS.includes(expectedEffort)) {
    throw new Error("Issue has an unsupported model or effort label");
  }
  return { expectedModel, expectedEffort };
}

export function validateRouting(labels, actualModel, actualEffort) {
  const { expectedModel, expectedEffort } = routingProfile(labels);
  const actualClass = routeClass(actualModel);
  if (actualClass !== expectedModel || actualEffort !== expectedEffort) {
    throw new Error(`Profile mismatch: issue requires ${expectedModel}/${expectedEffort}; task is ${actualModel}/${actualEffort}`);
  }
  return { expectedModel, expectedEffort };
}

function sectionLines(body, headingPattern, missingMessage) {
  const lines = body.split(/\r?\n/);
  const start = lines.findIndex((line) => headingPattern.test(line));
  if (start < 0) throw new Error(missingMessage);
  const headingLevel = lines[start].match(/^#+/)[0].length;
  const section = [];
  for (let index = start + 1; index < lines.length; index += 1) {
    const nextHeading = lines[index].match(/^(#+)\s+/);
    if (nextHeading && nextHeading[1].length <= headingLevel) break;
    section.push(lines[index]);
  }
  return section.map((line) => line.trim()).filter(Boolean);
}

function dependencyTarget(value, currentRepository) {
  const sameRepository = value.match(/^#(\d+)$/);
  if (sameRepository) return { repository: currentRepository, number: Number(sameRepository[1]) };
  const qualified = value.match(/^([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)#(\d+)$/);
  if (qualified) return { repository: qualified[1], number: Number(qualified[2]) };
  const url = value.match(/^https:\/\/github\.com\/([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)\/issues\/(\d+)\/?$/);
  if (url) return { repository: url[1], number: Number(url[2]) };
  throw new Error(`Invalid dependency target \`${value}\``);
}

export function parseDependencies(body, currentRepository) {
  const lines = sectionLines(body, /^#{2,3}\s+Dependencies\s*$/i, "Issue body needs a heading named 'Dependencies'");
  if (lines.length === 0) throw new Error("Dependencies must be 'None' or one 'Blocked by' entry per line");
  if (lines.length === 1 && /^-?\s*None\.?$/i.test(lines[0])) return [];
  const dependencies = [];
  for (const line of lines) {
    const match = line.match(/^[-*]\s+Blocked by\s+(.+?)\.?$/i);
    if (!match) throw new Error("Dependencies must use `- Blocked by #123`, `- Blocked by owner/repo#123`, or `None`");
    dependencies.push(dependencyTarget(match[1], currentRepository));
  }
  const unique = new Map(dependencies.map((dependency) => [`${dependency.repository}#${dependency.number}`, dependency]));
  if (unique.size !== dependencies.length) throw new Error("Dependencies must not contain duplicates");
  return [...unique.values()];
}

export function assertDependenciesResolved(states) {
  const unresolved = states.filter((state) => !state.resolved);
  if (unresolved.length > 0) {
    const summary = unresolved
      .map((state) => `${state.repository}#${state.number} (${state.issueState}/${state.projectStatus ?? "not on roadmap"})`)
      .join(", ");
    throw new Error(`Unresolved dependencies: ${summary}`);
  }
  return states;
}

export function latestClaim(comments) {
  const marker = /<!-- vera-claim (\{.+?\}) -->/g;
  let latest;
  for (const comment of comments) {
    for (const match of comment.body.matchAll(marker)) {
      latest = JSON.parse(match[1]);
    }
  }
  return latest;
}

export function assertClaimAvailable(comments) {
  const current = latestClaim(comments);
  if (current?.state === "active") {
    throw new Error(`Issue already claimed by ${current.task}`);
  }
  return current ?? null;
}

function issueNumber(parsed) {
  const value = parsed.positionals[0] ?? parsed.flags.get("issue");
  const number = Number(value);
  if (!Number.isInteger(number) || number < 1) throw new Error("Provide a positive issue number");
  return number;
}

async function config() {
  return JSON.parse(await readFile(path.join(root, ".github", "vera-roadmap.json"), "utf8"));
}

function issueView(repository, number) {
  return JSON.parse(runGh(["issue", "view", String(number), "--repo", repository, "--json", "number,title,url,state,body,labels,comments"]));
}

function labelsOf(issue) {
  return issue.labels.map((label) => label.name);
}

function addToProject(settings, url) {
  runGh(["project", "item-add", String(settings.projectNumber), "--owner", settings.owner, "--url", url]);
}

function setStatus(settings, url, status) {
  if (!STATUSES.includes(status)) throw new Error(`Unsupported status: ${status}`);
  runGh(["project", "item-edit", String(settings.projectNumber), "--owner", settings.owner, "--url", url, "--field", "Status", "--value", status]);
}

function projectItems(settings) {
  return JSON.parse(runGh(["project", "item-list", String(settings.projectNumber), "--owner", settings.owner, "--limit", "500", "--format", "json"])).items;
}

function projectItem(settings, number, items = projectItems(settings)) {
  return items.find((item) => item.content?.number === number && item.content?.repository === settings.repository);
}

function roadmapForRepository(settings, repository) {
  if (repository === settings.repository) return settings;
  const roadmap = VERA_ROADMAPS.get(repository);
  if (!roadmap) throw new Error(`Dependency repository ${repository} is not a configured VERA roadmap`);
  return { ...roadmap, repository };
}

function dependencyStates(settings, issueNumberValue, body, projectCache = new Map()) {
  const dependencies = parseDependencies(body, settings.repository);
  return dependencies.map((dependency) => {
    if (dependency.repository === settings.repository && dependency.number === issueNumberValue) {
      throw new Error("An issue cannot depend on itself");
    }
    const dependencySettings = roadmapForRepository(settings, dependency.repository);
    const dependencyIssue = issueView(dependency.repository, dependency.number);
    let items = projectCache.get(dependency.repository);
    if (!items) {
      items = projectItems(dependencySettings);
      projectCache.set(dependency.repository, items);
    }
    const dependencyItem = projectItem(dependencySettings, dependency.number, items);
    const issueState = dependencyIssue.state;
    const projectStatus = dependencyItem?.status ?? null;
    return {
      ...dependency,
      title: dependencyIssue.title,
      url: dependencyIssue.url,
      issueState,
      projectStatus,
      resolved: issueState === "CLOSED" && projectStatus === "Done",
    };
  });
}

function addComment(repository, number, body) {
  runGh(["issue", "comment", String(number), "--repo", repository, "--body-file", "-"], body);
}

function claimMarker(claim) {
  return `<!-- vera-claim ${JSON.stringify(claim)} -->`;
}

function acceptanceReady(body) {
  return /^#{2,3} Acceptance criteria\s*$/im.test(body) && /- \[ \] |\n\d+\. /m.test(body);
}

function validateReadyRequirements(settings, issue, projectCache) {
  if (issue.state !== "OPEN") throw new Error("Only open issues can become or remain Ready");
  const labels = labelsOf(issue);
  routingProfile(labels);
  if (labels.includes("needs:model-escalation")) throw new Error("Resolve model escalation before Ready");
  if (!acceptanceReady(issue.body)) {
    throw new Error("Issue body needs a heading named 'Acceptance criteria' and a checklist or numbered criteria");
  }
  const dependencies = dependencyStates(settings, issue.number, issue.body, projectCache);
  assertDependenciesResolved(dependencies);
  return dependencies;
}

async function linkSubIssue(settings, parentNumber, childNumber) {
  const parentId = runGh(["api", `repos/${settings.repository}/issues/${parentNumber}`, "--jq", ".node_id"]);
  const childId = runGh(["api", `repos/${settings.repository}/issues/${childNumber}`, "--jq", ".node_id"]);
  runGh([
    "api",
    "graphql",
    "-f",
    "query=mutation($parent:ID!,$child:ID!){addSubIssue(input:{issueId:$parent,subIssueId:$child}){issue{id}}}",
    "-f",
    `parent=${parentId}`,
    "-f",
    `child=${childId}`,
  ]);
}

async function main() {
  const parsed = parseArguments(process.argv.slice(2));
  const settings = await config();
  const repository = settings.repository;
  if (!parsed.command || parsed.flags.has("help")) {
    console.log("Usage: npm run roadmap -- <inspect|rate-limit|create|ready|claim|block|escalate|review|complete> [issue] [flags]");
    return;
  }

  if (parsed.command === "create") {
    const title = required(parsed.flags, "title");
    const bodyPath = required(parsed.flags, "body-file");
    const model = required(parsed.flags, "model");
    const effort = required(parsed.flags, "effort");
    const type = String(parsed.flags.get("type") ?? "implementation");
    if (!MODEL_CLASSES.includes(model) || !EFFORTS.includes(effort)) throw new Error("Unsupported model or effort");
    const body = await readFile(path.resolve(bodyPath), "utf8");
    if (!acceptanceReady(body)) throw new Error("Issue body needs a heading named 'Acceptance criteria' and a checklist or numbered criteria");
    guardMutation(3, parsed.flags.has("parent") ? 1 : 0);
    const url = runGh([
      "issue",
      "create",
      "--repo",
      repository,
      "--title",
      title,
      "--body-file",
      bodyPath,
      "--label",
      `model:${model}`,
      "--label",
      `effort:${effort}`,
      "--label",
      `type:${type}`,
    ]);
    addToProject(settings, url);
    setStatus(settings, url, "Inbox");
    const number = Number(url.split("/").at(-1));
    if (parsed.flags.has("parent")) await linkSubIssue(settings, Number(parsed.flags.get("parent")), number);
    console.log(url);
    return;
  }

  if (parsed.command === "rate-limit") {
    console.log(formatRateLimitReport(rateLimit()));
    return;
  }

  const number = issueNumber(parsed);
  const issue = issueView(repository, number);
  const items = projectItems(settings);
  const item = projectItem(settings, number, items);
  const projectCache = new Map([[settings.repository, items]]);
  if (parsed.command === "inspect") {
    let dependencies;
    try {
      const states = dependencyStates(settings, issue.number, issue.body, projectCache);
      dependencies = {
        valid: true,
        resolved: states.every((state) => state.resolved),
        items: states,
      };
    } catch (error) {
      dependencies = {
        valid: false,
        resolved: false,
        error: error instanceof Error ? error.message : String(error),
      };
    }
    console.log(
      JSON.stringify(
        {
          issue: { ...issue, comments: undefined },
          project: item ?? null,
          dependencies,
          claim: latestClaim(issue.comments) ?? null,
        },
        null,
        2,
      ),
    );
    return;
  }
  if (!item) throw new Error("Issue is not on the configured roadmap project");

  if (parsed.command === "ready") {
    if (!["Inbox", "Backlog", "Blocked", "Ready"].includes(item.status)) {
      throw new Error(`Issue cannot move to Ready from ${item.status ?? "unknown"}`);
    }
    validateReadyRequirements(settings, issue, projectCache);
    assertClaimAvailable(issue.comments);
    guardMutation(1);
    setStatus(settings, issue.url, "Ready");
    console.log(`Ready ${issue.url}`);
    return;
  }

  if (parsed.command === "claim") {
    const model = required(parsed.flags, "model");
    const effort = required(parsed.flags, "effort");
    const task = required(parsed.flags, "task");
    const branch = required(parsed.flags, "branch");
    validateRouting(labelsOf(issue), model, effort);
    if (item.status !== "Ready") throw new Error(`Issue must be Ready before claim; current status is ${item.status ?? "unknown"}`);
    validateReadyRequirements(settings, issue, projectCache);
    assertClaimAvailable(issue.comments);
    guardMutation(2);
    const claim = {
      state: "active",
      model,
      effort,
      task,
      branch,
      startedAt: new Date().toISOString(),
    };
    addComment(repository, number, `${claimMarker(claim)}\nClaimed by task \`${task}\` on branch \`${branch}\` using \`${model}\` at \`${effort}\` effort.`);
    setStatus(settings, issue.url, "In progress");
    console.log(`Claimed ${issue.url}`);
    return;
  }

  const evidence = required(parsed.flags, "evidence");
  if (parsed.command === "block") {
    guardMutation(2);
    addComment(repository, number, `Blocked.\n\nConfirmed evidence: ${evidence}`);
    setStatus(settings, issue.url, "Blocked");
  } else if (parsed.command === "escalate") {
    const recommendedModel = required(parsed.flags, "recommend-model");
    const recommendedEffort = required(parsed.flags, "recommend-effort");
    if (!MODEL_CLASSES.includes(recommendedModel) || !EFFORTS.includes(recommendedEffort)) throw new Error("Unsupported recommended profile");
    guardMutation(3);
    runGh(["issue", "edit", String(number), "--repo", repository, "--add-label", "needs:model-escalation"]);
    const prior = latestClaim(issue.comments);
    const released = {
      ...(prior ?? {}),
      state: "released",
      releasedAt: new Date().toISOString(),
    };
    addComment(
      repository,
      number,
      `${claimMarker(released)}\nModel escalation requested.\n\nConfirmed evidence: ${evidence}\n\nRecommended profile: \`${recommendedModel}/${recommendedEffort}\`. The steward must approve routing labels before a new claim.`,
    );
    setStatus(settings, issue.url, "Blocked");
  } else if (parsed.command === "review") {
    guardMutation(2);
    addComment(repository, number, `Implementation is ready for acceptance review.\n\nEvidence: ${evidence}`);
    setStatus(settings, issue.url, "In review");
  } else if (parsed.command === "complete") {
    const acceptedBy = required(parsed.flags, "accepted-by");
    guardMutation(3);
    addComment(repository, number, `Accepted by ${acceptedBy}.\n\nAcceptance evidence: ${evidence}`);
    setStatus(settings, issue.url, "Done");
    runGh(["issue", "close", String(number), "--repo", repository, "--reason", "completed"]);
  } else {
    throw new Error(`Unknown command: ${parsed.command}`);
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}
