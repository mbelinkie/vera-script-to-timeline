import { execFile } from "node:child_process";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";
import { parseDependencies } from "./roadmap.mjs";

const execFileAsync = promisify(execFile);

export const BOARD_STATUSES = Object.freeze([
  "Inbox",
  "Backlog",
  "Ready",
  "In progress",
  "Blocked",
  "Deferred",
  "In review",
  "Done",
]);

const STATUS_ORDER = new Map(BOARD_STATUSES.map((status, index) => [status, index]));
const ITEM_READ_LIMIT = 500;
const PROJECT_ITEMS_PER_PAGE = 100;
const GRAPHQL_POINTS_PER_PAGE = 500;
const RATE_LIMIT_QUERY_POINTS = 1;
const PROJECT_COUNT_QUERY_POINTS = 1;
const CODE_EXTENSIONS = new Set([
  ".c", ".cc", ".cpp", ".css", ".go", ".h", ".html", ".java", ".js", ".jsx",
  ".mjs", ".py", ".rb", ".rs", ".sh", ".sql", ".swift", ".ts", ".tsx",
]);
const PRODUCTION_ROOTS = new Set(["apps", "packages", "python", "src"]);

function isCodePath(filePath) {
  return CODE_EXTENSIONS.has(path.extname(filePath)) || filePath.endsWith(".command");
}

function isProductionPath(filePath) {
  const parts = filePath.split("/");
  return PRODUCTION_ROOTS.has(parts[0])
    && !parts.some((part) => ["__tests__", "build", "dist", "fixtures", "generated", "test", "tests", "testdata"].includes(part))
    && !/\.(?:spec|test)\.[^.]+$/.test(filePath);
}

function physicalLines(contents) {
  if (!contents) return 0;
  return contents.split(/\r?\n/).length - (contents.endsWith("\n") ? 1 : 0);
}

export function summarizeCodeFiles(files) {
  return files.reduce((totals, file) => {
    if (!isCodePath(file.path)) return totals;
    const lines = physicalLines(file.contents);
    totals.total += lines;
    if (isProductionPath(file.path)) totals.production += lines;
    return totals;
  }, { total: 0, production: 0 });
}

export async function countCodeLines(repositoryRoot) {
  let filePaths;
  try {
    const { stdout } = await execFileAsync("git", ["ls-files", "-z"], {
      cwd: repositoryRoot,
      maxBuffer: 10 * 1024 * 1024,
    });
    filePaths = stdout.split("\0").filter(Boolean);
  } catch (error) {
    throw new Error(
      `Code line counts are unavailable for ${repositoryRoot}: ${error instanceof Error ? error.message : String(error)}`,
      { cause: error },
    );
  }

  const files = (await Promise.all(filePaths.filter(isCodePath).map(async (filePath) => {
    try {
      return { path: filePath, contents: await readFile(path.join(repositoryRoot, filePath), "utf8") };
    } catch (error) {
      if (error?.code === "ENOENT") return null;
      throw error;
    }
  }))).filter(Boolean);
  return summarizeCodeFiles(files);
}

export function resolveProjectRepositoryPath(repositoryRoot, projectConfig, environment = process.env) {
  const overrideName = optionalText(projectConfig.repositoryPathEnv);
  const overridePath = overrideName ? optionalText(environment[overrideName]) : null;
  return path.resolve(repositoryRoot, overridePath ?? projectConfig.repositoryPath ?? ".");
}

export function requiredGraphqlReadBudget(projectConfigs, itemCounts) {
  const pageCount = projectConfigs.reduce((total, projectConfig) => {
    const itemCount = itemCounts[projectConfig.projectNumber];
    if (!Number.isSafeInteger(itemCount) || itemCount < 0) {
      throw new Error(`GitHub GraphQL preflight did not return a valid item count for project #${projectConfig.projectNumber}`);
    }
    return total + Math.max(1, Math.ceil(Math.min(itemCount, ITEM_READ_LIMIT) / PROJECT_ITEMS_PER_PAGE));
  }, 0);
  return RATE_LIMIT_QUERY_POINTS
    + projectConfigs.length * PROJECT_COUNT_QUERY_POINTS
    + pageCount * GRAPHQL_POINTS_PER_PAGE;
}

function onePrefixedLabel(labels, prefix, issueNumber, allowUnassigned = false) {
  const matches = labels.filter((label) => label.startsWith(prefix));
  if (allowUnassigned && matches.length === 0) return "unassigned";
  if (matches.length !== 1) {
    throw new Error(`Project issue #${issueNumber} must have exactly one ${prefix.slice(0, -1)} label`);
  }
  return matches[0].slice(prefix.length);
}

function optionalText(value) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

// GitHub CLI JSON flattens custom Project fields onto each item. Accept either
// the display name or the CLI camelCase spelling; absent fields are optional.
function projectField(item, name) {
  const normalized = name.toLowerCase().replace(/[^a-z0-9]/g, "");
  const key = Object.keys(item).find((candidate) =>
    candidate.toLowerCase().replace(/[^a-z0-9]/g, "") === normalized);
  return key === undefined ? null : item[key];
}

function readQueueOrder(item) {
  const raw = projectField(item, "Queue Order");
  if (raw === null || raw === undefined || raw === "") return { value: null, invalid: false };
  const value = Number(typeof raw === "object" && raw !== null ? raw.number ?? raw.value : raw);
  // GitHub's Project Number field supports fractional queue slots (e.g. 15.5).
  // Keep exact numeric ordering while rejecting non-finite and unsafe ranks.
  return Number.isFinite(value) && value > 0 && value <= Number.MAX_SAFE_INTEGER
    ? { value, invalid: false }
    : { value: null, invalid: true };
}

function readMilestoneOrder(item) {
  const raw = projectField(item, "Milestone Order");
  if (raw === null || raw === undefined || raw === "") return null;
  const value = Number(typeof raw === "object" && raw !== null ? raw.number ?? raw.value : raw);
  return Number.isSafeInteger(value) && value > 0 ? value : null;
}

function issueLocation(url) {
  const match = /^https:\/\/github\.com\/([^/?#]+)\/([^/?#]+)\/issues\/(\d+)(?:[/?#]|$)/i.exec(url ?? "");
  if (!match) return null;
  return { owner: match[1], repo: match[2], number: Number(match[3]),
    url: `https://github.com/${match[1]}/${match[2]}/issues/${match[3]}` };
}

function parseItem(item) {
  if (item.content?.type !== "Issue") {
    throw new Error(`Project item ${item.title ?? "(untitled)"} must be a GitHub Issue`);
  }
  const { number, title, url } = item.content;
  if (!Number.isInteger(number) || typeof title !== "string" || typeof url !== "string") {
    throw new Error("Project issue is missing its number, title, or URL");
  }
  if (item.status != null && !BOARD_STATUSES.includes(item.status)) {
    throw new Error(`Project issue #${number} has unsupported project status: ${item.status}`);
  }
  const labels = Array.isArray(item.labels) ? item.labels : [];
  const queue = readQueueOrder(item);
  const queueControl = url === "https://github.com/mbelinkie/vera-script-to-timeline/issues/361";
  return {
    number,
    title,
    url,
    repository: issueLocation(url)?.repo ?? null,
    body: typeof item.content.body === "string" ? item.content.body : null,
    labels,
    queueOrder: queue.value,
    queueOrderInvalid: queue.invalid,
    programMilestone: optionalText((() => {
      const field = projectField(item, "Program Milestone");
      return typeof field === "object" && field !== null ? field.name ?? field.value : field;
    })()),
    milestoneOrder: readMilestoneOrder(item),
    // Optional fixture-only dependencies; real data comes from the GitHub API.
    blockedBy: Array.isArray(item.blockedBy) ? item.blockedBy : null,
    status: item.status ?? "Unknown",
    ...(item.status == null ? { evidenceConflict: true } : {}),
    type: queueControl ? "operations-control" : onePrefixedLabel(labels, "type:", number),
    model: queueControl ? "n/a" : onePrefixedLabel(labels, "model:", number, true),
    effort: queueControl ? "n/a" : onePrefixedLabel(labels, "effort:", number, true),
    priority: optionalText(item.priority),
    size: optionalText(item.size),
    workstream: optionalText(item.workstream),
    acceptance: optionalText(item.acceptance),
  };
}

function isHistoricalRecord(item) {
  return item.content?.type === "DraftIssue"
    && item.status === "Done"
    && item.title?.startsWith("Historical —");
}

function parseHistoricalRecord(item, index) {
  return {
    number: `historical-${item.content.id ?? item.id ?? index}`,
    title: item.content.title ?? item.title,
    url: "",
    repository: null,
    queueOrder: null,
    queueOrderInvalid: false,
    programMilestone: null,
    milestoneOrder: null,
    blockedBy: null,
    status: "Done",
    type: "historical",
    model: "n/a",
    effort: "n/a",
    priority: optionalText(item.priority),
    size: optionalText(item.size),
    workstream: optionalText(item.workstream),
    acceptance: optionalText(item.acceptance),
  };
}

export function parseProjectItems(projectDocument) {
  if (!Array.isArray(projectDocument?.items)) {
    throw new Error("GitHub Project response has no items array");
  }

  if (
    Number.isInteger(projectDocument.totalCount) &&
    projectDocument.totalCount !== projectDocument.items.length
  ) {
    throw new Error(
      `Project response is incomplete: received ${projectDocument.items.length} of ${projectDocument.totalCount} items`
    );
  }

  const seen = new Set();
  const warnings = [];

  const items = projectDocument.items.flatMap((item, index) => {
    if (item.content?.type === "PullRequest") return [];
    if (isHistoricalRecord(item)) return [parseHistoricalRecord(item, index)];
    const parsed = parseItem(item);
    const key = issueLocation(parsed.url)?.url.toLowerCase() ?? `number:${parsed.number}`;
    if (seen.has(key)) throw new Error(`Duplicate project issue #${parsed.number}`);
    seen.add(key);
    return [parsed];
  });

  return {
    goals: items.filter(item => item.type === "goal"),
    workItems: items.filter(item => item.type !== "goal"),
    warnings,
  };
}

function percentage(value, total) {
  return total === 0 ? 0 : (value / total) * 100;
}

function compareItems(left, right) {
  const leftHasIssueNumber = Number.isInteger(left.number);
  const rightHasIssueNumber = Number.isInteger(right.number);
  const numberDifference = leftHasIssueNumber && rightHasIssueNumber
    ? left.number - right.number
    : 0;
  return (
    (STATUS_ORDER.get(left.status) ?? 99) - (STATUS_ORDER.get(right.status) ?? 99)
    || (leftHasIssueNumber === rightHasIssueNumber ? 0 : leftHasIssueNumber ? -1 : 1)
    || numberDifference
    || left.title.localeCompare(right.title)
  );
}

export function buildProgressModel(parsedProject) {
  const workItems = [...parsedProject.workItems];
  const doneCount = workItems.filter((item) => item.status === "Done").length;
  const statusCounts = Object.fromEntries(
    BOARD_STATUSES.map((status) => [status, workItems.filter((item) => item.status === status).length]),
  );
  const workstreamMap = new Map();
  for (const item of workItems) {
    const name = item.workstream ?? "Unassigned";
    if (!workstreamMap.has(name)) workstreamMap.set(name, []);
    workstreamMap.get(name).push(item);
  }
  const workstreams = [...workstreamMap.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([name, items]) => ({
      name,
      items: items.sort(compareItems),
      doneCount: items.filter((item) => item.status === "Done").length,
      remainingCount: items.filter((item) => item.status !== "Done").length,
    }));
  const metadataGaps = Object.fromEntries(
    ["workstream", "priority", "size", "acceptance"].map((field) => [
      field,
      workItems.filter((item) => item[field] === null).length,
    ]),
  );

  return {
    goals: [...parsedProject.goals].sort(compareItems),
    workItems,
    workstreams,
    totalWork: workItems.length,
    doneCount,
    remainingCount: workItems.length - doneCount,
    completionPercent: percentage(doneCount, workItems.length),
    statusCounts,
    metadataGaps,
    lastUpdated: "live GitHub Project",
    warnings: parsedProject.warnings ?? [],
  };
}

// Order statuses read in: active work first, finished work last.
// Left-to-right order of the progress tracks: finished work fills from the left.

// A GitHub-wide queue assembled from both existing Projects, with issues
// de-duplicated by URL. The dashboard audits, but never silently changes, rank.
export function buildSharedRoadmap(models, dependencySnapshot = {}) {
  const projects = Array.isArray(models) ? models : [models];
  const byUrl = new Map();
  const warnings = [];
  for (const model of projects) {
    for (const item of model.workItems ?? []) {
      const location = issueLocation(item.url);
      if (!location || item.type === "historical") continue;
      const key = location.url.toLowerCase();
      const candidate = { ...item, ...location, projectTitle: model.projectTitle ?? "VERA", key };
      const previous = byUrl.get(key);
      if (!previous) { byUrl.set(key, candidate); continue; }
      if (previous.status !== candidate.status || previous.title !== candidate.title) {
        previous.evidenceConflict = candidate.evidenceConflict = true;
        warnings.push(`Conflicting current issue metadata for ${location.owner}/${location.repo}#${location.number} across Projects.`);
      }
      // A shared master Project may contain an issue also present on its
      // original research board. A rank on one board wins over an empty rank.
      if (previous.queueOrder !== null && candidate.queueOrder !== null
        && previous.queueOrder !== candidate.queueOrder) {
        warnings.push(`Conflicting Queue Order for ${location.owner}/${location.repo}#${location.number} across Projects.`);
      }
      if (previous.programMilestone && candidate.programMilestone
        && previous.programMilestone !== candidate.programMilestone) {
        warnings.push(`Conflicting Program Milestone for ${location.owner}/${location.repo}#${location.number}.`);
      }
      if (previous.size && candidate.size && previous.size.toLowerCase() !== candidate.size.toLowerCase()) {
        warnings.push(`Conflicting Size for ${location.owner}/${location.repo}#${location.number} across Projects.`);
      }
      if (previous.queueOrder === null && candidate.queueOrder !== null) {
        // Retain size from the issue's original board when the master board
        // supplies the queue position but has not been sized yet.
        byUrl.set(key, { ...previous, ...candidate, size: candidate.size ?? previous.size,
          blockedBy: candidate.blockedBy ?? previous.blockedBy });
      } else {
        if (!previous.size && candidate.size) previous.size = candidate.size;
        if (!previous.programMilestone && candidate.programMilestone) {
          previous.programMilestone = candidate.programMilestone;
          previous.milestoneOrder = candidate.milestoneOrder;
        }
      }
    }
  }

  const all = [...byUrl.values()];
  const queue = all.filter((item) => item.queueOrder !== null)
    .sort((a, b) => a.queueOrder - b.queueOrder || a.key.localeCompare(b.key));
  const usedOrder = new Map();
  for (const item of queue) {
    if (usedOrder.has(item.queueOrder)) {
      warnings.push(`Queue #${item.queueOrder} is assigned to both ${usedOrder.get(item.queueOrder)} and ${item.owner}/${item.repo}#${item.number}.`);
      item.evidenceConflict = true;
      for (const other of queue) if (other.queueOrder === item.queueOrder) other.evidenceConflict = true;
    } else usedOrder.set(item.queueOrder, `${item.owner}/${item.repo}#${item.number}`);
  }

  const providedDependencies = dependencySnapshot.dependencies ?? {};
  const verified = new Set((dependencySnapshot.verified ?? []).map((value) => value.toLowerCase()));
  const unavailable = new Set();
  const dependencyErrors = [...(dependencySnapshot.errors ?? [])];
  for (const item of queue) {
    const entry = providedDependencies[item.key] ?? providedDependencies[item.url]
      ?? item.blockedBy;
    const hasFixture = Array.isArray(item.blockedBy);
    const known = Array.isArray(entry) && (verified.has(item.key) || hasFixture);
    if (!known) unavailable.add(item.key);
    item.dependenciesVerified = known;
    item.dependencies = (Array.isArray(entry) ? entry : []).map((dep) => {
      const url = typeof dep === "string" ? dep : dep.url ?? dep.html_url;
      const location = issueLocation(url);
      const prerequisite = location ? byUrl.get(location.url.toLowerCase()) : null;
      const isOpen = prerequisite
        ? prerequisite.status !== "Done" || (!hasFixture && !["CLOSED", "closed"].includes(dep?.state))
        : !["CLOSED", "closed"].includes(dep?.state);
      const bad = !location || (isOpen && (!prerequisite || prerequisite.queueOrder === null || prerequisite.queueOrder >= item.queueOrder));
      if (bad) warnings.push(`${item.owner}/${item.repo}#${item.number} at #${item.queueOrder} depends on ${location ? `${location.owner}/${location.repo}#${location.number}` : String(url)} ${prerequisite ? `at #${prerequisite.queueOrder}` : "which has no queue position"}.`);
      return {
        url: location?.url ?? null,
        label: location ? `${location.repo}#${location.number}` : "Unknown issue",
        queueOrder: prerequisite?.queueOrder ?? null,
        isOpen,
        invalid: bad,
      };
    });
  }

  const invalidRankCount = all.filter((item) => item.queueOrderInvalid).length;
  if (invalidRankCount) warnings.push(`${invalidRankCount} issues have an invalid Queue Order (must be a positive finite number).`);
  const unassignedMilestones = queue.filter((item) => !item.programMilestone).length;
  if (unassignedMilestones) warnings.push(`${unassignedMilestones} queued issues have no Program Milestone.`);

  const milestoneMap = new Map();
  for (const item of all) {
    if (!item.programMilestone) continue;
    const name = item.programMilestone;
    if (!milestoneMap.has(name)) milestoneMap.set(name, { name, items: [], order: Infinity, earliestQueue: Infinity });
    const milestone = milestoneMap.get(name);
    milestone.items.push(item);
    if (item.milestoneOrder !== null && Number.isFinite(milestone.order)
      && milestone.order !== item.milestoneOrder) {
      warnings.push(`Program Milestone ${name} has conflicting Milestone Order values: ${milestone.order} and ${item.milestoneOrder}.`);
    }
    if (item.milestoneOrder !== null) milestone.order = Math.min(milestone.order, item.milestoneOrder);
    if (item.queueOrder !== null) milestone.earliestQueue = Math.min(milestone.earliestQueue, item.queueOrder);
  }
  const milestones = [...milestoneMap.values()].map((milestone) => {
    const done = milestone.items.filter((item) => item.status === "Done").length;
    return { ...milestone, done, total: milestone.items.length,
      percent: milestone.items.length ? Math.round(100 * done / milestone.items.length) : 0 };
  }).sort((a, b) => a.order - b.order || a.earliestQueue - b.earliestQueue || a.name.localeCompare(b.name));
  return {
    queue, milestones, warnings, dependencyErrors,
    unverifiedCount: unavailable.size,
    unqueuedCount: all.filter((item) => item.status !== "Done" && item.queueOrder === null).length,
    duplicateCount: projects.reduce((n, model) => n + (model.workItems?.filter((i) => issueLocation(i.url)).length ?? 0), 0) - all.length,
  };
}

// Native GitHub issue dependencies (including across repositories) are read
// through GraphQL in bounded batches. Read-only; failures are surfaced instead
// of being mistaken for an empty dependency graph.
export async function fetchNativeDependencies(repositoryRoot, models, options = {}) {
  const items = buildSharedRoadmap(models).queue;
  const dependencies = {};
  const verified = [];
  const errors = [];
  const fetchGraphql = options.queryGraphql ?? (async (query) => {
    const { stdout } = await execFileAsync("gh", ["api", "graphql", "-f", `query=${query}`],
      { cwd: repositoryRoot, maxBuffer: 10 * 1024 * 1024 });
    return JSON.parse(stdout);
  });
  // Keep individual GraphQL documents small, and do not silently claim to have
  // audited issues if a request fails or returns a partial dependency list.
  const BATCH_SIZE = 15;
  for (let start = 0; start < items.length; start += BATCH_SIZE) {
    const batch = items.slice(start, start + BATCH_SIZE);
    const fields = batch.map((item, index) =>
      `i${index}: repository(owner:${JSON.stringify(item.owner)},name:${JSON.stringify(item.repo)}) { issue(number:${item.number}) { url body blockedBy(first:50) { totalCount pageInfo { hasNextPage } nodes { url state } } } }`);
    try {
      const data = await fetchGraphql(`query VeraQueueDependencies { ${fields.join(" ")} }`);
      if (data.errors?.length) throw new Error(data.errors.map((entry) => entry.message).join("; "));
      for (const [index, item] of batch.entries()) {
        const issue = data.data?.[`i${index}`]?.issue;
        const result = issue?.blockedBy;
        if (!result || !Array.isArray(result.nodes) || result.pageInfo?.hasNextPage
          || result.totalCount !== result.nodes.length) {
          errors.push(`Dependency list incomplete for ${item.owner}/${item.repo}#${item.number}.`);
          continue;
        }
        if (issue.url !== item.url || typeof issue.body !== "string") {
          errors.push(`Canonical dependency source unavailable for ${item.owner}/${item.repo}#${item.number}.`);
          continue;
        }
        let canonical;
        try {
          canonical = parseDependencies(issue.body, `${item.owner}/${item.repo}`);
        } catch {
          errors.push(`Canonical Dependencies section needs verification for ${item.owner}/${item.repo}#${item.number}.`);
          continue;
        }
        const byUrl = new Map(result.nodes.map((node) => [node.url, node]));
        for (const dependency of canonical) {
          const url = `https://github.com/${dependency.repository}/issues/${dependency.number}`;
          if (!byUrl.has(url)) byUrl.set(url, { url });
        }
        const missingStates = [...byUrl.values()].filter((node) => !["OPEN", "CLOSED"].includes(node.state));
        if (missingStates.length > 50) {
          errors.push(`Canonical dependency list exceeds the bounded read for ${item.owner}/${item.repo}#${item.number}.`);
          continue;
        }
        if (missingStates.length) {
          const fields = missingStates.map((dependency, index) => {
            const location = issueLocation(dependency.url);
            if (!location) throw new Error("Invalid dependency identity");
            return `d${index}: repository(owner:${JSON.stringify(location.owner)},name:${JSON.stringify(location.repo)}) { issue(number:${location.number}) { url state } }`;
          });
          const states = await fetchGraphql(`query VeraCanonicalDependencyStates { ${fields.join(" ")} }`);
          if (states.errors?.length) throw new Error("Canonical dependency states unavailable");
          for (const [index, dependency] of missingStates.entries()) {
            const state = states.data?.[`d${index}`]?.issue;
            if (state?.url !== dependency.url || !["OPEN", "CLOSED"].includes(state?.state)) throw new Error("Canonical dependency identity mismatch");
            byUrl.set(dependency.url, state);
          }
        }
        dependencies[item.key] = [...byUrl.values()];
        verified.push(item.key);
      }
    } catch {
      errors.push(`Dependency check failed for ${batch.length} queued issues; GitHub source unavailable.`);
    }
  }
  return { dependencies, verified, errors };
}

export async function loadProgressModel(repositoryRoot, options = {}) {
  const projectConfig = options.projectConfig
    ?? JSON.parse(await readFile(path.join(repositoryRoot, ".github", "vera-roadmap.json"), "utf8"));
  let projectDocument = options.projectData;
  if (!projectDocument) {
    try {
      const { stdout } = await execFileAsync("gh", [
        "project", "item-list", String(projectConfig.projectNumber),
      "--owner", projectConfig.owner, "--limit", String(ITEM_READ_LIMIT), "--format", "json",
      ], { cwd: repositoryRoot, maxBuffer: 10 * 1024 * 1024 });
      projectDocument = JSON.parse(stdout);
    } catch (error) {
      throw new Error(
        `GitHub Project is unavailable: ${error instanceof Error ? error.message : String(error)}`,
        { cause: error },
      );
    }
  }
  let codeStats = options.codeStats ?? null;
  let codeStatsError = null;
  if (!codeStats) {
    try {
      codeStats = await countCodeLines(resolveProjectRepositoryPath(repositoryRoot, projectConfig));
    } catch {
      codeStatsError = projectConfig.repositoryPathEnv
        ? `Set ${projectConfig.repositoryPathEnv} to the local checkout to enable line counts.`
        : "Check the local repository path to enable line counts.";
    }
  }
  return {
    ...buildProgressModel(parseProjectItems(projectDocument)),
    projectTitle: projectConfig.projectTitle,
    projectNumber: projectConfig.projectNumber,
    projectUrl: `https://github.com/users/${projectConfig.owner}/projects/${projectConfig.projectNumber}`,
    codeStats,
    codeStatsError,
    snapshotAt: options.snapshotAt ?? new Date().toISOString(),
    lastError: null,
  };
}
