#!/usr/bin/env node

import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  formatGraphqlRateLimitReport,
} from "./roadmap-rate-limit.mjs";
import { withRoadmapGraphqlGate } from "./roadmap-graphql-gate.mjs";

export const MODEL_CLASSES = ["luna", "terra", "sol"];
export const EFFORTS = ["low", "medium", "high", "xhigh", "max"];
export const STATUSES = ["Inbox", "Backlog", "Ready", "In progress", "Blocked", "In review", "Done"];

const VERA_ROADMAPS = new Map([
  ["mbelinkie/vera-research-video-clips", { owner: "mbelinkie", projectNumber: 1 }],
  ["mbelinkie/vera-script-to-timeline", { owner: "mbelinkie", projectNumber: 2 }],
]);

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const ISSUE_PROJECT_QUERY = `query RoadmapIssue($owner: String!, $name: String!, $number: Int!, $projectNumber: Int!) {
  repository(owner: $owner, name: $name) {
    escalationLabel: label(name: "needs:model-escalation") { id }
    issue(number: $number) {
      id number title url state body
      labels(first: 100) { nodes { id name description color } }
      comments(last: 100) { nodes { body } pageInfo { hasPreviousPage startCursor } }
      projectItems(first: 100) {
        nodes {
          id
          project { id number title }
          fieldValueByName(name: "Status") {
            ... on ProjectV2ItemFieldSingleSelectValue { name }
          }
          fieldValues(first: 30) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field { ... on ProjectV2SingleSelectField { name } }
              }
            }
          }
        }
      }
    }
  }
  user(login: $owner) {
    projectV2(number: $projectNumber) {
      id number title
      field(name: "Status") {
        ... on ProjectV2SingleSelectField { id name options { id name } }
      }
    }
  }
  rateLimit { limit remaining used resetAt cost }
}`;

const ISSUE_COMMENT_PAGE_QUERY = `query RoadmapIssueComments($owner: String!, $name: String!, $number: Int!, $before: String!) {
  repository(owner: $owner, name: $name) {
    issue(number: $number) {
      comments(last: 100, before: $before) {
        nodes { body }
        pageInfo { hasPreviousPage startCursor }
      }
    }
  }
  rateLimit { limit remaining used resetAt cost }
}`;

const PROJECT_METADATA_QUERY = `query RoadmapProject($owner: String!, $projectNumber: Int!) {
  user(login: $owner) {
    projectV2(number: $projectNumber) {
      id number title
      field(name: "Status") {
        ... on ProjectV2SingleSelectField { id name options { id name } }
      }
    }
  }
  rateLimit { limit remaining used resetAt cost }
}`;

const PARENT_ISSUE_QUERY = `query RoadmapParentIssue($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    issue(number: $number) { id }
  }
  rateLimit { limit remaining used resetAt cost }
}`;

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

function guardMutation(gate, requiredRestRequests, graphqlOperationNames) {
  // Optional dependency validation is finished; unused read reservations cannot fund writes.
  gate.discard("dependencyBatch");
  const graphql = gate.reserve(graphqlOperationNames);
  if (requiredRestRequests > 0) {
    const core = gate.restCoreRateLimit();
    if (core.remaining < requiredRestRequests) {
      const resetAt = new Date(core.reset * 1000).toISOString();
      throw new Error(
        `Insufficient GitHub REST core budget: planned work needs ${requiredRestRequests} request(s), but ${core.remaining} remain. ` +
          `Safe retry: at or after ${resetAt}. No mutation was attempted.`,
      );
    }
  }
  return graphql;
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

function repositoryParts(repository) {
  const [owner, name, ...extra] = repository.split("/");
  if (!owner || !name || extra.length > 0) throw new Error(`Invalid GitHub repository: ${repository}`);
  return { owner, name };
}

function labelsOf(issue) {
  return issue.labels.map((label) => label.name);
}

function statusContext(project, itemId = null) {
  const field = project?.field;
  if (!project?.id || !field?.id || !Array.isArray(field.options)) {
    throw new Error("Configured roadmap project has no usable Status field");
  }
  return {
    projectId: project.id,
    projectNumber: project.number,
    projectTitle: project.title,
    itemId,
    statusFieldId: field.id,
    statusOptions: new Map(field.options.map((option) => [option.name, option.id])),
  };
}

function projectMetadata(settings, gate) {
  const data = gate.query("projectMetadata", PROJECT_METADATA_QUERY, {
    owner: settings.owner,
    projectNumber: settings.projectNumber,
  });
  if (!data.user?.projectV2) throw new Error("Configured roadmap project was not found");
  return statusContext(data.user.projectV2);
}

function applyLifecycleMutation(gate, context, issueId, { status, comment = null, escalationLabelId = null, close = false }) {
  if (!context.itemId) throw new Error("Issue is not on the configured roadmap project");
  const optionId = context.statusOptions.get(status);
  if (!optionId) throw new Error(`Configured roadmap project has no Status option named ${status}`);
  gate.mutation(
    "lifecycleMutation",
    `mutation RoadmapLifecycle(
      $issueId: ID!,
      $comment: String!,
      $writeComment: Boolean!,
      $labelId: ID!,
      $writeLabel: Boolean!,
      $projectId: ID!,
      $itemId: ID!,
      $fieldId: ID!,
      $optionId: String!,
      $writeStatus: Boolean!,
      $closeIssue: Boolean!
    ) {
      label: addLabelsToLabelable(input: { labelableId: $issueId, labelIds: [$labelId] }) @include(if: $writeLabel) {
        labelable { ... on Node { id } }
      }
      comment: addComment(input: { subjectId: $issueId, body: $comment }) @include(if: $writeComment) {
        commentEdge { node { id } }
      }
      status: updateProjectV2ItemFieldValue(input: {
        projectId: $projectId,
        itemId: $itemId,
        fieldId: $fieldId,
        value: { singleSelectOptionId: $optionId }
      }) @include(if: $writeStatus) { projectV2Item { id } }
      close: closeIssue(input: { issueId: $issueId }) @include(if: $closeIssue) { issue { id } }
    }`,
    {
      issueId,
      comment: comment ?? "",
      writeComment: comment !== null,
      labelId: escalationLabelId ?? issueId,
      writeLabel: escalationLabelId !== null,
      projectId: context.projectId,
      itemId: context.itemId,
      fieldId: context.statusFieldId,
      optionId,
      writeStatus: true,
      closeIssue: close,
    },
  );
}

function projectFields(item) {
  return new Map(
    (item?.fieldValues?.nodes ?? [])
      .filter((value) => value?.field?.name && typeof value.name === "string")
      .map((value) => [value.field.name, value.name]),
  );
}

function issueProjectSnapshot(settings, number, gate) {
  const { owner, name } = repositoryParts(settings.repository);
  const data = gate.query("issueProjectSnapshot", ISSUE_PROJECT_QUERY, {
    owner,
    name,
    number,
    projectNumber: settings.projectNumber,
  });
  const rawIssue = data.repository?.issue;
  const project = data.user?.projectV2;
  if (!rawIssue) throw new Error(`Issue #${number} was not found in ${settings.repository}`);
  if (!project) throw new Error("Configured roadmap project was not found");
  const rawItem = (rawIssue.projectItems?.nodes ?? []).find((candidate) => candidate.project?.id === project.id);
  const fields = projectFields(rawItem);
  let comments = rawIssue.comments?.nodes ?? [];
  let commentsPage = rawIssue.comments?.pageInfo;
  while (commentsPage?.hasPreviousPage && !latestClaim(comments)) {
    gate.reserve(["issueCommentPage"]);
    const pageData = gate.query("issueCommentPage", ISSUE_COMMENT_PAGE_QUERY, {
      owner,
      name,
      number,
      before: commentsPage.startCursor,
    });
    const page = pageData.repository?.issue?.comments;
    if (!page) throw new Error(`Could not read older claim history for issue #${number}`);
    comments = [...(page.nodes ?? []), ...comments];
    commentsPage = page.pageInfo;
  }
  const issue = {
    id: rawIssue.id,
    number: rawIssue.number,
    title: rawIssue.title,
    url: rawIssue.url,
    state: rawIssue.state,
    body: rawIssue.body,
    labels: rawIssue.labels?.nodes ?? [],
    comments,
  };
  const item = rawItem
    ? {
        id: rawItem.id,
        title: issue.title,
        repository: `https://github.com/${settings.repository}`,
        status: rawItem.fieldValueByName?.name ?? fields.get("Status") ?? null,
        priority: fields.get("Priority") ?? null,
        size: fields.get("Size") ?? null,
        workstream: fields.get("Workstream") ?? null,
        acceptance: fields.get("Acceptance") ?? null,
        labels: labelsOf(issue),
        content: {
          body: issue.body,
          number: issue.number,
          repository: settings.repository,
          title: issue.title,
          type: "Issue",
          url: issue.url,
        },
      }
    : null;
  return {
    issue,
    item,
    context: statusContext(project, rawItem?.id ?? null),
    escalationLabelId: data.repository?.escalationLabel?.id ?? null,
  };
}

function roadmapForRepository(settings, repository) {
  if (repository === settings.repository) return settings;
  const roadmap = VERA_ROADMAPS.get(repository);
  if (!roadmap) throw new Error(`Dependency repository ${repository} is not a configured VERA roadmap`);
  return { ...roadmap, repository };
}

function dependencyStates(settings, issueNumberValue, body, gate) {
  const dependencies = parseDependencies(body, settings.repository);
  const states = [];
  // Each alias has one Project connection; at most 100 connections cost one point.
  for (let offset = 0; offset < dependencies.length; offset += 100) {
    if (offset > 0) gate.reserve(["dependencyBatch"]);
    states.push(...dependencyBatchStates(settings, issueNumberValue, dependencies.slice(offset, offset + 100), gate));
  }
  return states;
}

function dependencyBatchStates(settings, issueNumberValue, dependencies, gate) {
  const definitions = [];
  const selections = [];
  const variables = {};
  const configured = dependencies.map((dependency, index) => {
    if (dependency.repository === settings.repository && dependency.number === issueNumberValue) {
      throw new Error("An issue cannot depend on itself");
    }
    const dependencySettings = roadmapForRepository(settings, dependency.repository);
    const { owner, name } = repositoryParts(dependency.repository);
    definitions.push(`$owner${index}: String!`, `$name${index}: String!`, `$number${index}: Int!`);
    variables[`owner${index}`] = owner;
    variables[`name${index}`] = name;
    variables[`number${index}`] = dependency.number;
    selections.push(`dependency${index}: repository(owner: $owner${index}, name: $name${index}) {
      issue(number: $number${index}) {
        title url state
        projectItems(first: 100) {
          nodes {
            project { number }
            fieldValueByName(name: "Status") {
              ... on ProjectV2ItemFieldSingleSelectValue { name }
            }
          }
        }
      }
    }`);
    return { dependency, dependencySettings };
  });
  const query = `query RoadmapDependencies(${definitions.join(", ")}) {
    ${selections.join("\n")}
    rateLimit { limit remaining used resetAt cost }
  }`;
  const data = gate.query("dependencyBatch", query, variables);
  return configured.map(({ dependency, dependencySettings }, index) => {
    const dependencyIssue = data[`dependency${index}`]?.issue;
    if (!dependencyIssue) throw new Error(`Dependency ${dependency.repository}#${dependency.number} was not found`);
    const dependencyItem = (dependencyIssue.projectItems?.nodes ?? []).find(
      (candidate) => candidate.project?.number === dependencySettings.projectNumber,
    );
    const issueState = dependencyIssue.state;
    const projectStatus = dependencyItem?.fieldValueByName?.name ?? null;
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

function claimMarker(claim) {
  return `<!-- vera-claim ${JSON.stringify(claim)} -->`;
}

function acceptanceReady(body) {
  return /^#{2,3} Acceptance criteria\s*$/im.test(body) && /- \[ \] |\n\d+\. /m.test(body);
}

function validateReadyRequirements(settings, issue, gate) {
  if (issue.state !== "OPEN") throw new Error("Only open issues can become or remain Ready");
  const labels = labelsOf(issue);
  routingProfile(labels);
  if (labels.includes("needs:model-escalation")) throw new Error("Resolve model escalation before Ready");
  if (!acceptanceReady(issue.body)) {
    throw new Error("Issue body needs a heading named 'Acceptance criteria' and a checklist or numbered criteria");
  }
  const dependencies = dependencyStates(settings, issue.number, issue.body, gate);
  assertDependenciesResolved(dependencies);
  return dependencies;
}

function createIssue(settings, title, body, labels, gate) {
  const args = ["api", "-X", "POST", `repos/${settings.repository}/issues`, "-f", `title=${title}`, "-f", `body=${body}`];
  for (const label of labels) args.push("-f", `labels[]=${label}`);
  const created = JSON.parse(gate.restMutation(args));
  if (!created.node_id || !created.html_url || !Number.isInteger(created.number)) {
    throw new Error("GitHub issue creation response was incomplete");
  }
  return { id: created.node_id, number: created.number, url: created.html_url };
}

function addToProject(context, contentId, gate) {
  const data = gate.mutation(
    "projectAdd",
    `mutation AddRoadmapItem($projectId: ID!, $contentId: ID!) {
      addProjectV2ItemById(input: { projectId: $projectId, contentId: $contentId }) {
        item { id }
      }
    }`,
    { projectId: context.projectId, contentId },
  );
  const itemId = data.addProjectV2ItemById?.item?.id;
  if (!itemId) throw new Error("GitHub did not return the new roadmap item ID");
  return { ...context, itemId };
}

function parentIssueId(settings, parentNumber, gate) {
  const { owner, name } = repositoryParts(settings.repository);
  const data = gate.query("parentIssueSnapshot", PARENT_ISSUE_QUERY, { owner, name, number: parentNumber });
  const id = data.repository?.issue?.id;
  if (!id) throw new Error(`Parent issue #${parentNumber} was not found in ${settings.repository}`);
  return id;
}

async function linkSubIssue(parentId, childId, gate) {
  gate.mutation(
    "subIssueLink",
    "mutation LinkSubIssue($parent: ID!, $child: ID!) { addSubIssue(input: { issueId: $parent, subIssueId: $child }) { issue { id } } }",
    { parent: parentId, child: childId },
  );
}

async function main(gate) {
  const parsed = parseArguments(process.argv.slice(2));
  const settings = await config();
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
    const parentNumber = parsed.flags.has("parent") ? Number(parsed.flags.get("parent")) : null;
    gate.reserve(parentNumber === null ? ["projectMetadata"] : ["projectMetadata", "parentIssueSnapshot"]);
    const metadata = projectMetadata(settings, gate);
    const parentId = parentNumber === null ? null : parentIssueId(settings, parentNumber, gate);
    const graphqlMutations = ["projectAdd", "lifecycleMutation"];
    if (parentId !== null) graphqlMutations.push("subIssueLink");
    guardMutation(gate, 1, graphqlMutations);
    const created = createIssue(settings, title, body, [`model:${model}`, `effort:${effort}`, `type:${type}`], gate);
    const context = addToProject(metadata, created.id, gate);
    applyLifecycleMutation(gate, context, created.id, { status: "Inbox" });
    if (parentId !== null) await linkSubIssue(parentId, created.id, gate);
    console.log(created.url);
    return;
  }

  if (parsed.command === "rate-limit") {
    console.log(formatGraphqlRateLimitReport(gate.rateLimit()));
    return;
  }

  const number = issueNumber(parsed);
  gate.reserve(["issueProjectSnapshot", "dependencyBatch"]);
  const snapshot = issueProjectSnapshot(settings, number, gate);
  const { issue, item, context, escalationLabelId } = snapshot;
  if (parsed.command === "inspect") {
    let dependencies;
    try {
      const states = dependencyStates(settings, issue.number, issue.body, gate);
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
    validateReadyRequirements(settings, issue, gate);
    assertClaimAvailable(issue.comments);
    guardMutation(gate, 0, ["lifecycleMutation"]);
    applyLifecycleMutation(gate, context, issue.id, { status: "Ready" });
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
    validateReadyRequirements(settings, issue, gate);
    assertClaimAvailable(issue.comments);
    const claim = {
      state: "active",
      model,
      effort,
      task,
      branch,
      startedAt: new Date().toISOString(),
    };
    guardMutation(gate, 0, ["lifecycleMutation"]);
    applyLifecycleMutation(gate, context, issue.id, {
      status: "In progress",
      comment: `${claimMarker(claim)}\nClaimed by task \`${task}\` on branch \`${branch}\` using \`${model}\` at \`${effort}\` effort.`,
    });
    console.log(`Claimed ${issue.url}`);
    return;
  }

  const evidence = required(parsed.flags, "evidence");
  if (parsed.command === "block") {
    guardMutation(gate, 0, ["lifecycleMutation"]);
    applyLifecycleMutation(gate, context, issue.id, { status: "Blocked", comment: `Blocked.\n\nConfirmed evidence: ${evidence}` });
  } else if (parsed.command === "escalate") {
    const recommendedModel = required(parsed.flags, "recommend-model");
    const recommendedEffort = required(parsed.flags, "recommend-effort");
    if (!MODEL_CLASSES.includes(recommendedModel) || !EFFORTS.includes(recommendedEffort)) throw new Error("Unsupported recommended profile");
    if (!escalationLabelId) throw new Error("Repository has no needs:model-escalation label");
    const prior = latestClaim(issue.comments);
    const released = {
      ...(prior ?? {}),
      state: "released",
      releasedAt: new Date().toISOString(),
    };
    guardMutation(gate, 0, ["lifecycleMutation"]);
    applyLifecycleMutation(gate, context, issue.id, {
      status: "Blocked",
      escalationLabelId,
      comment: `${claimMarker(released)}\nModel escalation requested.\n\nConfirmed evidence: ${evidence}\n\nRecommended profile: \`${recommendedModel}/${recommendedEffort}\`. The steward must approve routing labels before a new claim.`,
    });
  } else if (parsed.command === "review") {
    guardMutation(gate, 0, ["lifecycleMutation"]);
    applyLifecycleMutation(gate, context, issue.id, {
      status: "In review",
      comment: `Implementation is ready for acceptance review.\n\nEvidence: ${evidence}`,
    });
  } else if (parsed.command === "complete") {
    const acceptedBy = required(parsed.flags, "accepted-by");
    guardMutation(gate, 0, ["lifecycleMutation"]);
    applyLifecycleMutation(gate, context, issue.id, {
      status: "Done",
      comment: `Accepted by ${acceptedBy}.\n\nAcceptance evidence: ${evidence}`,
      close: true,
    });
  } else {
    throw new Error(`Unknown command: ${parsed.command}`);
  }
}

async function runMainWithLock() {
  const parsed = parseArguments(process.argv.slice(2));
  if (!parsed.command || parsed.flags.has("help")) return main();
  return withRoadmapGraphqlGate((gate) => main(gate));
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  runMainWithLock().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}
