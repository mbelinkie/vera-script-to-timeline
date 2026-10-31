import { execFile } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";
import {
  assertGraphqlBudget,
  parseGraphqlRateLimitResponse,
} from "./roadmap-rate-limit.mjs";

const execFileAsync = promisify(execFile);

export const BOARD_STATUSES = Object.freeze([
  "Inbox",
  "Backlog",
  "Ready",
  "In progress",
  "Blocked",
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

function projectCountQuery(projectConfigs) {
  const projectCounts = projectConfigs.map((projectConfig, index) => {
    if (!Number.isInteger(projectConfig.projectNumber) || typeof projectConfig.owner !== "string") {
      throw new Error("Progress dashboard project configuration needs a numeric project number and owner");
    }
    return `project${index}: user(login: ${JSON.stringify(projectConfig.owner)}) { projectV2(number: ${projectConfig.projectNumber}) { items(first: 1) { totalCount } } }`;
  });
  return `query ProgressDashboardRateLimit { rateLimit { limit remaining used resetAt cost } ${projectCounts.join(" ")} }`;
}

function parseIncludedGraphqlBody(output) {
  const separator = output.match(/\r?\n\r?\n/);
  if (!separator) throw new Error("GitHub GraphQL preflight response did not include a response body");
  return JSON.parse(output.slice(separator.index + separator[0].length));
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

async function preflightProjectReads(repositoryRoot, projectConfigs) {
  let output;
  try {
    const { stdout } = await execFileAsync("gh", [
      "api", "graphql", "--include", "-f", `query=${projectCountQuery(projectConfigs)}`,
    ], { cwd: repositoryRoot, maxBuffer: 1024 * 1024 });
    output = stdout;
  } catch (error) {
    throw new Error(
      `GitHub GraphQL budget could not be checked; no Project items were requested: ${error instanceof Error ? error.message : String(error)}`,
      { cause: error },
    );
  }
  const snapshot = parseGraphqlRateLimitResponse(output);
  const payload = parseIncludedGraphqlBody(output);
  const itemCounts = Object.fromEntries(projectConfigs.map((projectConfig, index) => {
    const count = payload.data?.[`project${index}`]?.projectV2?.items?.totalCount;
    return [projectConfig.projectNumber, count];
  }));
  assertGraphqlBudget(snapshot, requiredGraphqlReadBudget(projectConfigs, itemCounts));
}

function onePrefixedLabel(labels, prefix, issueNumber) {
  const matches = labels.filter((label) => label.startsWith(prefix));
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
  return Number.isSafeInteger(value) && value > 0
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
  if (!BOARD_STATUSES.includes(item.status)) {
    throw new Error(`Project issue #${number} has unsupported project status: ${item.status}`);
  }
  const labels = Array.isArray(item.labels) ? item.labels : [];
  const queue = readQueueOrder(item);
  return {
    number,
    title,
    url,
    repository: issueLocation(url)?.repo ?? null,
    queueOrder: queue.value,
    queueOrderInvalid: queue.invalid,
    programMilestone: optionalText((() => {
      const field = projectField(item, "Program Milestone");
      return typeof field === "object" && field !== null ? field.name ?? field.value : field;
    })()),
    milestoneOrder: readMilestoneOrder(item),
    // Optional fixture-only dependencies; real data comes from the GitHub API.
    blockedBy: Array.isArray(item.blockedBy) ? item.blockedBy : null,
    status: item.status,
    type: onePrefixedLabel(labels, "type:", number),
    model: onePrefixedLabel(labels, "model:", number),
    effort: onePrefixedLabel(labels, "effort:", number),
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
    Number.isInteger(projectDocument.totalCount)
    && projectDocument.totalCount !== projectDocument.items.length
  ) {
    throw new Error(
      `Project response is incomplete: received ${projectDocument.items.length} of ${projectDocument.totalCount} items`,
    );
  }

  const seen = new Set();
  const items = projectDocument.items.map((item, index) => {
    if (isHistoricalRecord(item)) return parseHistoricalRecord(item, index);
    const parsed = parseItem(item);
    // Issue numbers are only unique *within* a repository, not across a
    // cross-repository GitHub Project. Compare canonical URLs instead.
    const key = issueLocation(parsed.url)?.url.toLowerCase() ?? `number:${parsed.number}`;
    if (seen.has(key)) throw new Error(`Duplicate project issue #${parsed.number}`);
    seen.add(key);
    return parsed;
  });

  return {
    goals: items.filter((item) => item.type === "goal"),
    workItems: items.filter((item) => item.type !== "goal"),
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
  };
}

export function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatPercent(value) {
  return `${value.toFixed(1)}%`;
}

function statusClass(status) {
  return status.toLowerCase().replaceAll(" ", "-");
}

function metadataText(label, value, missingText) {
  return value
    ? `<span>${label ? `${escapeHtml(label)} ` : ""}<b>${escapeHtml(value)}</b></span>`
    : `<span class="missing">${escapeHtml(missingText)}</span>`;
}

// Order statuses read in: active work first, finished work last.
const DISPLAY_ORDER = new Map(
  ["In progress", "In review", "Blocked", "Ready", "Backlog", "Inbox", "Done"].map((status, index) => [status, index]),
);
// Left-to-right order of the progress tracks: finished work fills from the left.
const TRACK_ORDER = ["Done", "In review", "In progress", "Blocked", "Ready", "Backlog", "Inbox"];

function displayPercent(value) {
  // Floor so a nearly finished board never reads as 100%.
  return `${Math.floor(value)}%`;
}

function countStatuses(items) {
  return Object.fromEntries(
    BOARD_STATUSES.map((status) => [status, items.filter((item) => item.status === status).length]),
  );
}

function renderTrack(statusCounts, label, { large = false } = {}) {
  const present = TRACK_ORDER.filter((status) => statusCounts[status] > 0);
  const description = present.map((status) => `${statusCounts[status]} ${status}`).join(", ") || "No work items";
  const segments = present
    .map((status) => `<span class="seg ${statusClass(status)}" style="flex-grow:${statusCounts[status]}" title="${escapeHtml(status)}: ${statusCounts[status]}"></span>`)
    .join("");
  return `<div class="track${large ? " track-lg" : ""}" role="img" aria-label="${escapeHtml(`${label}: ${description}`)}">${segments}</div>`;
}

function renderIssue(item, options = {}) {
  const title = item.type === "historical"
    ? escapeHtml(item.title)
    : `<span class="num">#${item.number}</span> ${escapeHtml(item.title)}`;
  const titleMarkup = item.url
    ? `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener">${title}</a>`
    : `<span class="issue-title">${title}</span>`;
  const meta = item.type === "historical"
    ? `<span>Historical record</span>`
    : [
      metadataText("", item.priority, "No priority"),
      metadataText("Size", item.size, "No size"),
      `<span>${escapeHtml(`${item.model}/${item.effort}`)}</span>`,
      metadataText("Accepted by", item.acceptance, "No acceptance owner"),
      options.goal ? "" : `<span>${escapeHtml(item.type)}</span>`,
    ].join("");
  return `
            <li class="issue ${statusClass(item.status)}" data-issue="${escapeHtml(item.number)}">
              <i class="swatch ${statusClass(item.status)}" aria-hidden="true"></i>
              <div class="issue-body">
                <div class="issue-line">${titleMarkup}<span class="issue-status">${escapeHtml(item.status)}</span></div>
                <div class="meta">${meta}</div>
              </div>
            </li>`;
}

function sortForDisplay(items) {
  return [...items].sort((left, right) =>
    (DISPLAY_ORDER.get(left.status) ?? 99) - (DISPLAY_ORDER.get(right.status) ?? 99)
    || compareItems(left, right));
}

function renderWorkstream(group) {
  const complete = group.remainingCount === 0;
  return `
        <details class="ws${complete ? " ws-complete" : ""}">
          <summary>
            <span class="ws-name">${escapeHtml(group.name)}</span>
            ${renderTrack(countStatuses(group.items), group.name)}
            <span class="ws-count">${group.doneCount} of ${group.items.length}</span>
          </summary>
          <ul class="issues">${sortForDisplay(group.items).map((item) => renderIssue(item)).join("")}
          </ul>
        </details>`;
}

function renderGoals(model) {
  return `
        <details class="ws goals-row">
          <summary>
            <span class="ws-name">Goal rollups</span>
            <span class="ws-note">Context only, not counted</span>
            <span class="ws-count">${model.goals.length}</span>
          </summary>
          <ul class="issues">${model.goals.length > 0
            ? sortForDisplay(model.goals).map((goal) => renderIssue(goal, { goal: true })).join("")
            : '<li class="empty">No goal issues on this board.</li>'}
          </ul>
        </details>`;
}

function formatInteger(value) {
  return new Intl.NumberFormat("en-US").format(value);
}

function projectKey(model, index) {
  return `project-${model.projectNumber ?? index + 1}`;
}

function shortProjectTitle(model) {
  return (model.projectTitle ?? "VERA Board")
    .replace(/^VERA /, "")
    .replace(/ Roadmap$/, "");
}

function describeGaps(gaps) {
  const parts = [
    [gaps.workstream, "a workstream"],
    [gaps.priority, "a priority"],
    [gaps.size, "a size"],
    [gaps.acceptance, "an acceptance owner"],
  ].filter(([count]) => count > 0).map(([count, field]) => `${count} without ${field}`);
  return parts.length > 0 ? `Metadata missing: ${parts.join(", ")}.` : "";
}

function renderBoardCard(model, index) {
  const key = projectKey(model, index);
  const projectTitle = model.projectTitle ?? "VERA Board";
  const name = escapeHtml(shortProjectTitle(model));
  const heading = model.projectUrl
    ? `<a href="${escapeHtml(model.projectUrl)}" target="_blank" rel="noopener" title="Open ${escapeHtml(projectTitle)} on GitHub">${name}</a>`
    : name;
  const legend = TRACK_ORDER
    .filter((status) => model.statusCounts[status] > 0)
    .map((status) => `<li><i class="swatch ${statusClass(status)}" aria-hidden="true"></i>${escapeHtml(status)} <b>${model.statusCounts[status]}</b></li>`)
    .join("");
  const code = model.codeStats
    ? `<b>${formatInteger(model.codeStats.total)}</b> lines of code, <b>${formatInteger(model.codeStats.production)}</b> production`
    : `Lines of code unavailable. ${escapeHtml(model.codeStatsError ?? "Check the local repository path.")}`;
  const gaps = describeGaps(model.metadataGaps);
  return `
      <article class="board" id="${key}" data-project="${model.projectNumber ?? index + 1}">
        <header class="board-head">
          <h2>${heading}</h2>
          <p class="pct">${displayPercent(model.completionPercent)}</p>
        </header>
        <p class="board-sub"><b>${model.doneCount}</b> of ${model.totalWork} work items done, ${model.remainingCount} to go</p>
        ${renderTrack(model.statusCounts, projectTitle, { large: true })}
        <ul class="legend">${legend}</ul>
        <footer class="board-foot">
          <p>${code}</p>${gaps ? `
          <p class="gaps">${escapeHtml(gaps)}</p>` : ""}
        </footer>
      </article>`;
}

function renderWorkstreamColumn(model, index) {
  const key = projectKey(model, index);
  const groups = [...model.workstreams].sort((left, right) =>
    Number(left.remainingCount === 0) - Number(right.remainingCount === 0)
    || left.name.localeCompare(right.name));
  return `
      <section class="column" aria-labelledby="${key}-ws">
        <h3 id="${key}-ws">${escapeHtml(shortProjectTitle(model))}</h3>
        <div class="ws-list">${groups.length > 0
          ? groups.map(renderWorkstream).join("")
          : '<p class="empty">No work items on this board yet.</p>'}
        </div>
        <div class="ws-list goals">${renderGoals(model)}
        </div>
      </section>`;
}

function formatGeneratedAt(date) {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  }).format(date);
}

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
  const queuedByKey = new Map(queue.map((item) => [item.key, item]));
  const usedOrder = new Map();
  for (const item of queue) {
    if (usedOrder.has(item.queueOrder)) {
      warnings.push(`Queue #${item.queueOrder} is assigned to both ${usedOrder.get(item.queueOrder)} and ${item.owner}/${item.repo}#${item.number}.`);
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
      const prerequisite = location ? queuedByKey.get(location.url.toLowerCase()) : null;
      const bad = !prerequisite || prerequisite.queueOrder >= item.queueOrder;
      if (bad) warnings.push(`${item.owner}/${item.repo}#${item.number} at #${item.queueOrder} depends on ${location ? `${location.owner}/${location.repo}#${location.number}` : String(url)} ${prerequisite ? `at #${prerequisite.queueOrder}` : "which has no queue position"}.`);
      return {
        url: location?.url ?? null,
        label: location ? `${location.repo}#${location.number}` : "Unknown issue",
        queueOrder: prerequisite?.queueOrder ?? null,
        isOpen: prerequisite ? prerequisite.status !== "Done" : (dep?.state === "OPEN" || dep?.state === "open"),
        invalid: bad,
      };
    });
  }

  const invalidRankCount = all.filter((item) => item.queueOrderInvalid).length;
  if (invalidRankCount) warnings.push(`${invalidRankCount} issues have an invalid Queue Order (must be a positive integer).`);
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
      `i${index}: repository(owner:${JSON.stringify(item.owner)},name:${JSON.stringify(item.repo)}) { issue(number:${item.number}) { blockedBy(first:50) { totalCount pageInfo { hasNextPage } nodes { url state } } } }`);
    try {
      const data = await fetchGraphql(`query VeraQueueDependencies { ${fields.join(" ")} }`);
      if (data.errors?.length) throw new Error(data.errors.map((entry) => entry.message).join("; "));
      for (const [index, item] of batch.entries()) {
        const result = data.data?.[`i${index}`]?.issue?.blockedBy;
        if (!result || !Array.isArray(result.nodes) || result.pageInfo?.hasNextPage
          || result.totalCount !== result.nodes.length) {
          errors.push(`Dependency list incomplete for ${item.owner}/${item.repo}#${item.number}.`);
          continue;
        }
        dependencies[item.key] = result.nodes;
        verified.push(item.key);
      }
    } catch (error) {
      errors.push(`Dependency check failed for ${batch.length} queued issues: ${error instanceof Error ? error.message : String(error)}`);
    }
  }
  return { dependencies, verified, errors };
}

// The existing GitHub Project Size field is a relative estimate, not a time
// commitment. Keep unfamiliar custom options visible rather than inventing
// an interpretation. Normalize common abbreviations for easy scanning.
function describeSize(value) {
  const raw = optionalText(value);
  if (!raw) return { key: "unsized", label: "Unassigned", display: "Unassigned", sort: 99 };
  const definitions = [
    ["XS", "Extra small", ["XS", "EXTRA SMALL", "EXTRA-SMALL"]],
    ["S", "Small", ["S", "SMALL"]],
    ["M", "Medium", ["M", "MEDIUM"]],
    ["L", "Large", ["L", "LARGE"]],
    ["XL", "Extra large", ["XL", "EXTRA LARGE", "EXTRA-LARGE", "VERY LARGE"]],
    ["XXL", "Huge", ["XXL", "HUGE", "EXTRA EXTRA LARGE"]],
  ];
  const upper = raw.toUpperCase();
  for (const [index, [short, name, aliases]] of definitions.entries()) {
    if (aliases.includes(upper)) return { key: short.toLowerCase(), label: name,
      display: `${short} · ${name}`, sort: index };
  }
  return { key: `custom:${raw.toLowerCase()}`, label: raw, display: raw, sort: 90 };
}

function renderSharedRoadmap(roadmap) {
  const warnings = [...roadmap.warnings, ...roadmap.dependencyErrors];
  const completeAudit = roadmap.queue.length > 0 && roadmap.unverifiedCount === 0;
  const audit = roadmap.queue.length === 0
    ? "No queue entries yet. Add Queue Order to GitHub Project issues to begin."
    : !completeAudit
      ? `${roadmap.unverifiedCount} queued issues not dependency-verified. Do not assume the order is valid.`
      : warnings.length > 0
        ? `${warnings.length} queue or milestone configuration problem(s) detected.`
        : "All queued issue dependencies are ordered correctly.";
  const issueLink = (item) => `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener">${escapeHtml(item.repo)}#${item.number}: ${escapeHtml(item.title)}</a>`;
  const milestoneMarkup = roadmap.milestones.length
    ? roadmap.milestones.map((m) => `<article class="milestone"><div class="milestone-name">${escapeHtml(m.name)}<b>${m.done}/${m.total}</b></div><div class="track" role="img" aria-label="${escapeHtml(m.name)} ${m.percent}% complete"><span class="milestone-fill" style="width:${m.percent}%"></span></div><p>${m.percent}% complete</p></article>`).join("")
    : '<p class="empty">No program milestones assigned yet. Set the Program Milestone field on GitHub Project items.</p>';
  const sizeChoices = [...new Map(roadmap.queue.map((item) => {
    const size = describeSize(item.size);
    return [size.key, size];
  })).values()].sort((a, b) => a.sort - b.sort || a.label.localeCompare(b.label));
  const queueRows = roadmap.queue.map((item) => {
    const size = describeSize(item.size);
    const deps = item.dependenciesVerified
      ? item.dependencies.length
        ? item.dependencies.map((d) => `${d.url ? `<a href="${escapeHtml(d.url)}" target="_blank" rel="noopener">${escapeHtml(d.label)}</a>` : escapeHtml(d.label)}${d.invalid ? ' <strong class="queue-bad">Out of order</strong>' : d.isOpen ? ' <span class="queue-wait">Open</span>' : ''}`).join(", ")
        : "None"
      : '<span class="queue-wait">Not verified</span>';
    return `<tr data-repository="${escapeHtml(item.repo.toLowerCase())}" data-queue-status="${escapeHtml(item.status)}" data-queue-size="${escapeHtml(size.key)}"><td class="order">${item.queueOrder}</td><td>${issueLink(item)}</td><td>${escapeHtml(item.projectTitle)}</td><td>${escapeHtml(item.status)}</td><td><span class="queue-size${size.key === "unsized" ? " queue-size-missing" : ""}" title="${escapeHtml(size.label)}">${escapeHtml(size.display)}</span></td><td>${escapeHtml(item.programMilestone ?? "Unassigned")}</td><td>${deps}</td></tr>`;
  }).join("");
  return `<section class="shared-roadmap" aria-labelledby="master-roadmap-title">
    <div class="section-head"><h2 id="master-roadmap-title">Master execution queue</h2><span class="queue-note">Across both GitHub Projects · read-only</span></div>
    <div class="queue-kpis"><span><b>${roadmap.queue.length}</b> ordered issues</span><span><b>${roadmap.unqueuedCount}</b> unqueued active issues</span><span><b>${roadmap.milestones.length}</b> milestones</span></div>
    <p class="audit${warnings.length || !completeAudit ? ' audit-warning' : ''}">${escapeHtml(audit)}</p>
    ${warnings.length ? `<details class="queue-warnings"><summary>Review ${warnings.length} issue(s) and warning(s)</summary><ul>${warnings.map((w) => `<li>${escapeHtml(w)}</li>`).join("")}</ul></details>` : ""}
    <div class="section-head"><h2>Program milestones</h2></div><div class="milestones">${milestoneMarkup}</div>
    <div class="queue-filter"><label for="queue-repo">Repository</label><select id="queue-repo"><option value="all">All repositories</option>${[...new Set(roadmap.queue.map((item) => item.repo))].sort().map((repo) => `<option value="${escapeHtml(repo.toLowerCase())}">${escapeHtml(repo)}</option>`).join("")}</select><label for="queue-state">Status</label><select id="queue-state"><option value="all">All statuses</option><option value="active">Not done</option><option value="done">Done</option></select><label for="queue-size">Size</label><select id="queue-size"><option value="all">All sizes</option>${sizeChoices.map((size) => `<option value="${escapeHtml(size.key)}">${escapeHtml(size.display)}</option>`).join("")}</select><span id="queue-visible" class="queue-note"></span></div>
    <div class="queue-table-wrap"><table class="queue-table"><thead><tr><th scope="col">Queue</th><th scope="col">Issue</th><th scope="col">Project</th><th scope="col">Status</th><th scope="col">Size</th><th scope="col">Program milestone</th><th scope="col">Blocked by</th></tr></thead><tbody>${queueRows || '<tr><td colspan="7" class="empty">Nothing queued yet. Existing board progress remains below.</td></tr>'}</tbody></table></div>
    <p class="queue-note">Size is a relative scope estimate from GitHub Projects, not a calendar-time prediction. Missing sizes show as Unassigned.</p>
  </section>`;
}

export function renderDashboard(models, options = {}) {
  const projects = Array.isArray(models) ? models : [models];
  const roadmap = buildSharedRoadmap(projects, options.dependencySnapshot);
  // The same GitHub Issue can appear on both Projects. Count it once in the
  // program-wide total, while each board retains its own original totals.
  const counted = new Set();
  let totalWork = 0;
  let doneCount = 0;
  for (const [index, model] of projects.entries()) {
    for (const item of model.workItems ?? []) {
      const key = issueLocation(item.url)?.url.toLowerCase() ?? `${index}:${item.number}`;
      if (counted.has(key)) continue;
      counted.add(key);
      totalWork += 1;
      if (item.status === "Done") doneCount += 1;
    }
  }
  const scope = projects.length === 2 ? " across both boards" : projects.length > 2 ? ` across ${projects.length} boards` : "";
  const updated = options.generatedAt ? `. Updated ${escapeHtml(formatGeneratedAt(options.generatedAt))}` : "";
  const live = options.live === true;
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VERA Progress</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg:#1b1c1f; --surface:#232529; --raised:#2b2e33; --line:#363940; --ink:#e8e6e1; --muted:#9b9fa6; --faint:#6e737b; --focus:#8fc3ff;
      --done:#5cb88a; --review:#b095e8; --progress:#e5aa4a; --blocked:#e2645c; --ready:#5aa5e0; --backlog:#5c6068; --inbox:#474a51; --warn:#d9a54a;
    }
    @media (prefers-color-scheme: light) {
      :root { --bg:#eef0f3; --surface:#ffffff; --raised:#f6f7f9; --line:#d8dce1; --ink:#1c1f24; --muted:#5c626b; --faint:#8a9099; --focus:#1f6fd1;
        --done:#2e9462; --review:#8862cf; --progress:#c4861a; --blocked:#c8423a; --ready:#2d7dc0; --backlog:#8a9099; --inbox:#b4b9c0; --warn:#a46a00; }
    }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",system-ui,sans-serif; font-variant-numeric:tabular-nums; -webkit-font-smoothing:antialiased; }
    a { color:inherit; }
    a:focus-visible, summary:focus-visible, button:focus-visible { outline:2px solid var(--focus); outline-offset:2px; border-radius:4px; }
    .shell { width:min(1240px, calc(100% - 32px)); margin:0 auto; padding:40px 0 72px; }
    .top { display:flex; justify-content:space-between; align-items:baseline; gap:8px 24px; flex-wrap:wrap; margin-bottom:24px; }
    h1 { margin:0; font-size:1.75rem; font-weight:600; letter-spacing:-.01em; }
    .top p { margin:0; color:var(--muted); }
    .top p b { color:var(--ink); font-weight:600; }
    .live-controls { display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin:0 0 16px; }
    .live-status { font-size:.85rem; color:var(--muted); }
    .live-status.warn { color:var(--warn); }
    .live-refresh { border:1px solid var(--line); border-radius:6px; padding:7px 12px; background:var(--surface); color:var(--ink); font:inherit; cursor:pointer; }
    .live-refresh:hover:not(:disabled) { border-color:var(--muted); }
    .live-refresh:disabled { opacity:.6; cursor:wait; }
    .queue-kpis { display:flex; gap:8px 22px; flex-wrap:wrap; color:var(--muted); margin:10px 0; }
    .queue-kpis b { color:var(--ink); }
    .audit { margin:12px 0 4px; padding:10px 14px; background:var(--surface); border:1px solid var(--line); border-radius:8px; color:var(--done); }
    .audit-warning { color:var(--warn); }
    .queue-warnings { padding:8px 14px; border:1px solid var(--line); border-radius:8px; margin:8px 0; }
    .queue-warnings summary { cursor:pointer; color:var(--warn); }
    .queue-warnings li { margin:5px 0; overflow-wrap:anywhere; }
    .milestones { display:grid; grid-template-columns:repeat(auto-fit, minmax(235px, 1fr)); gap:12px; }
    .milestone { background:var(--surface); border:1px solid var(--line); border-radius:8px; padding:14px; }
    .milestone-name { display:flex; justify-content:space-between; gap:8px; font-weight:600; margin-bottom:12px; }
    .milestone-name b { color:var(--muted); white-space:nowrap; }
    .milestone-fill { background:var(--done); border-radius:3px; height:100%; }
    .milestone p { margin:6px 0 0; color:var(--muted); font-size:.8rem; }
    .queue-filter { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin:24px 0 12px; font-size:.85rem; }
    .queue-filter select { border:1px solid var(--line); border-radius:6px; background:var(--surface); color:var(--ink); padding:6px; margin-right:12px; }
    .queue-note { color:var(--muted); font-size:.8rem; }
    .queue-table-wrap { overflow-x:auto; background:var(--surface); border:1px solid var(--line); border-radius:8px; }
    .queue-table { border-collapse:collapse; width:100%; font-size:.85rem; }
    .queue-table th { text-align:left; color:var(--muted); font-weight:600; white-space:nowrap; }
    .queue-table td, .queue-table th { border-bottom:1px solid var(--line); padding:10px 12px; vertical-align:top; }
    .queue-table tr:last-child td { border-bottom:none; }
    .queue-table a { text-decoration:none; }
    .queue-table a:hover { text-decoration:underline; }
    .queue-table .order { font-weight:700; }
    .queue-size { font-weight:600; white-space:nowrap; }
    .queue-size-missing { color:var(--warn); font-weight:400; }
    .queue-bad { color:var(--blocked); }
    .queue-wait { color:var(--warn); }

    .grid { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:20px; }
    .grid.single { grid-template-columns:minmax(0, 1fr); }
    .board { padding:22px 24px 18px; border:1px solid var(--line); border-radius:10px; background:var(--surface); }
    .board-head { display:flex; justify-content:space-between; align-items:baseline; gap:16px; }
    .board h2 { margin:0; font-size:1.3rem; font-weight:600; }
    .board h2 a { text-decoration:none; }
    .board h2 a:hover { text-decoration:underline; text-underline-offset:3px; }
    .pct { margin:0; font-size:2.25rem; font-weight:500; line-height:1; color:var(--done); }
    .board-sub { margin:6px 0 16px; color:var(--muted); }
    .board-sub b { color:var(--ink); font-weight:600; }
    /* Progress reads like a track of clips on an edit timeline. */
    .track { display:flex; gap:2px; height:6px; overflow:hidden; border-radius:3px; background:var(--raised); }
    .track-lg { height:28px; gap:3px; border-radius:5px; }
    .seg { flex-basis:0; min-width:3px; }
    .track-lg .seg { border-radius:3px; }
    .track-lg .seg:first-child { transform-origin:left; animation:grow .7s cubic-bezier(.2,.7,.2,1) both; }
    @keyframes grow { from { transform:scaleX(0); } }
    @media (prefers-reduced-motion: reduce) { .track-lg .seg:first-child { animation:none; } }
    .done { background:var(--done); } .in-review { background:var(--review); } .in-progress { background:var(--progress); }
    .blocked { background:var(--blocked); } .ready { background:var(--ready); } .backlog { background:var(--backlog); } .inbox { background:var(--inbox); }
    .legend { display:flex; flex-wrap:wrap; gap:4px 16px; margin:12px 0 0; padding:0; list-style:none; color:var(--muted); font-size:.82rem; }
    .legend li { display:flex; align-items:center; gap:6px; }
    .legend b { color:var(--ink); font-weight:600; }
    .swatch { display:inline-block; flex:none; width:9px; height:9px; border-radius:2px; }
    .board-foot { margin-top:16px; padding-top:12px; border-top:1px solid var(--line); color:var(--muted); font-size:.82rem; }
    .board-foot p { margin:0; }
    .board-foot b { color:var(--ink); font-weight:600; }
    .board-foot .gaps { margin-top:4px; color:var(--warn); }
    .section-head { display:flex; justify-content:space-between; align-items:baseline; gap:16px; margin:44px 0 12px; }
    .section-head h2 { margin:0; font-size:1.1rem; font-weight:600; }
    .toggle-all { padding:5px 10px; border:1px solid var(--line); border-radius:6px; background:none; color:var(--muted); font:inherit; font-size:.82rem; cursor:pointer; }
    .toggle-all:hover { border-color:var(--muted); color:var(--ink); }
    .column h3 { margin:0 0 8px; color:var(--muted); font-size:.9rem; font-weight:500; }
    .ws-list { overflow:hidden; border:1px solid var(--line); border-radius:10px; background:var(--surface); }
    .ws-list.goals { margin-top:12px; }
    .ws + .ws { border-top:1px solid var(--line); }
    .ws summary { display:grid; grid-template-columns:14px minmax(9rem, 1.3fr) minmax(5rem, 1fr) 4.8rem; align-items:center; gap:12px; padding:11px 16px 11px 12px; cursor:pointer; list-style:none; }
    .ws summary::-webkit-details-marker { display:none; }
    .ws summary::before { content:""; width:6px; height:6px; margin-left:3px; border-right:1.5px solid var(--faint); border-bottom:1.5px solid var(--faint); transform:rotate(-45deg); transition:transform .15s; }
    .ws[open] > summary::before { transform:rotate(45deg); }
    .ws summary:hover { background:var(--raised); }
    .ws-name { overflow:hidden; font-weight:500; text-overflow:ellipsis; white-space:nowrap; }
    .ws-count { color:var(--muted); font-size:.82rem; text-align:right; white-space:nowrap; }
    .ws-complete .ws-name { color:var(--muted); }
    .ws-complete .ws-count { color:var(--done); }
    .ws-note { color:var(--faint); font-size:.8rem; }
    .issues { margin:0; padding:2px 0 8px; border-top:1px solid var(--line); background:var(--raised); list-style:none; }
    .issue { display:grid; grid-template-columns:9px minmax(0, 1fr); gap:12px; padding:9px 16px 9px 38px; background:none; }
    .issue .swatch { margin-top:7px; }
    .issue-line { display:flex; justify-content:space-between; align-items:baseline; gap:12px; }
    .issue-line a, .issue-title { min-width:0; text-decoration:none; }
    .issue-line a:hover { text-decoration:underline; text-underline-offset:3px; }
    .issue.done .issue-line a, .issue.done .issue-title { color:var(--muted); }
    .num { color:var(--faint); }
    .issue-status { flex:none; color:var(--muted); font-size:.8rem; }
    .meta { display:flex; flex-wrap:wrap; gap:2px 14px; margin-top:2px; color:var(--faint); font-size:.78rem; }
    .meta b { color:var(--muted); font-weight:500; }
    .meta .missing { color:var(--warn); }
    .empty { margin:0; padding:16px; color:var(--muted); list-style:none; }
    @media (max-width: 900px) { .grid { grid-template-columns:minmax(0, 1fr); } .column + .column { margin-top:28px; } }
    @media (max-width: 520px) {
      .shell { padding-top:28px; } .board { padding:18px 16px 14px; } .pct { font-size:1.9rem; }
      .ws summary { grid-template-columns:14px minmax(0, 1fr) 4.2rem 3.8rem; gap:10px; } .ws-note { display:none; }
      .goals-row summary { grid-template-columns:14px minmax(0, 1fr) auto; }
      .issue { padding-left:16px; } .issue-line { flex-direction:column; gap:0; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="top">
      <h1 id="page-title">VERA progress</h1>
      <p><b>${doneCount} of ${totalWork}</b> work items done${scope}${updated}</p>
    </header>
    ${live ? `<div class="live-controls" aria-live="polite">
      <button id="refresh-now" type="button" class="live-refresh">Refresh now</button>
      <span class="live-status" id="live-status">Checking dashboard connection…</span>
    </div>` : ""}
    ${renderSharedRoadmap(roadmap)}
    <div class="section-head"><h2>Board progress</h2></div>
    <section class="grid${projects.length === 1 ? " single" : ""}" aria-label="Board progress">${projects.map(renderBoardCard).join("")}
    </section>
    <div class="section-head">
      <h2>Work by workstream</h2>
      <button type="button" class="toggle-all">Expand all</button>
    </div>
    <div class="grid${projects.length === 1 ? " single" : ""}">${projects.map(renderWorkstreamColumn).join("")}
    </div>
  </main>
  <script>
    const toggle = document.querySelector('.toggle-all');
    const rows = [...document.querySelectorAll('details.ws')];
    const queueRepo = document.getElementById('queue-repo');
    const queueState = document.getElementById('queue-state');
    const queueSize = document.getElementById('queue-size');
    const queueVisible = document.getElementById('queue-visible');
    const queueRows = [...document.querySelectorAll('tr[data-queue-status]')];
    function filterQueue() {
      let count = 0;
      for (const row of queueRows) {
        const visibleRepo = queueRepo.value === 'all' || row.dataset.repository === queueRepo.value;
        const visibleStatus = queueState.value === 'all' || (queueState.value === 'done' ? row.dataset.queueStatus === 'Done' : row.dataset.queueStatus !== 'Done');
        const visibleSize = queueSize.value === 'all' || row.dataset.queueSize === queueSize.value;
        row.hidden = !(visibleRepo && visibleStatus && visibleSize);
        if (!row.hidden) count += 1;
      }
      queueVisible.textContent = count + ' shown';
    }
    queueRepo.addEventListener('change', filterQueue);
    queueState.addEventListener('change', filterQueue);
    queueSize.addEventListener('change', filterQueue);
    filterQueue();
    function syncToggle() {
      const allOpen = rows.length > 0 && rows.every((row) => row.open);
      toggle.textContent = allOpen ? 'Collapse all' : 'Expand all';
    }
    toggle.addEventListener('click', () => {
      const open = !rows.every((row) => row.open);
      for (const row of rows) row.open = open;
      syncToggle();
    });
    for (const row of rows) row.addEventListener('toggle', syncToggle);
  </script>
  ${live ? `<script>
    (() => {
      const statusNode = document.getElementById('live-status');
      const button = document.getElementById('refresh-now');
      const loadedVersion = Number(document.documentElement.dataset.snapshotVersion || 0);
      let requestInFlight = false;

      function displayStatus(status) {
        const when = new Date(status.updatedAt).toLocaleString();
        const interval = Math.round(status.refreshIntervalSeconds / 60);
        const message = status.error
          ? 'Refresh failed; showing snapshot from ' + when + '. ' + status.error
          : status.refreshing
            ? 'Checking GitHub… Last successful update: ' + when
            : 'Updated ' + when + ' · Auto-check every ' + interval + ' min while open';
        statusNode.textContent = message;
        statusNode.classList.toggle('warn', Boolean(status.error));
        if (status.version > loadedVersion) window.location.reload();
      }

      async function checkStatus() {
        if (document.hidden || requestInFlight) return;
        requestInFlight = true;
        try {
          const reply = await fetch('/status', { cache: 'no-store' });
          if (!reply.ok) throw new Error('Status endpoint unavailable');
          displayStatus(await reply.json());
        } catch {
          statusNode.textContent = 'Connection lost. Showing last downloaded snapshot.';
          statusNode.classList.add('warn');
        } finally {
          requestInFlight = false;
        }
      }

      button.addEventListener('click', async () => {
        button.disabled = true;
        button.textContent = 'Refreshing…';
        statusNode.textContent = 'Checking GitHub…';
        try {
          const reply = await fetch('/refresh', {
            method: 'POST',
            headers: { 'X-VERA-Refresh': '1' },
            cache: 'no-store',
          });
          displayStatus(await reply.json());
        } catch {
          statusNode.textContent = 'Refresh failed. Check the local dashboard server.';
          statusNode.classList.add('warn');
        } finally {
          button.disabled = false;
          button.textContent = 'Refresh now';
        }
      });
      document.addEventListener('visibilitychange', checkStatus);
      window.addEventListener('focus', checkStatus);
      setInterval(checkStatus, 20_000);
      void checkStatus();
    })();
  </script>` : ""}
</body>
</html>
`;
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
  };
}

export async function writeDashboard(repositoryRoot, outputPath, options = {}) {
  const rootConfig = JSON.parse(await readFile(path.join(repositoryRoot, ".github", "vera-roadmap.json"), "utf8"));
  const projectConfigs = options.projectData ? [rootConfig] : (rootConfig.progressProjects ?? [rootConfig]);
  const projectDataByNumber = options.projectDataByNumber ?? {};
  const liveProjectConfigs = projectConfigs.filter((projectConfig) =>
    !options.projectData && !Object.hasOwn(projectDataByNumber, projectConfig.projectNumber)
  );
  if (liveProjectConfigs.length > 0) await preflightProjectReads(repositoryRoot, liveProjectConfigs);
  const models = await Promise.all(projectConfigs.map((projectConfig) => loadProgressModel(repositoryRoot, {
    projectConfig,
    projectData: options.projectData ?? projectDataByNumber[projectConfig.projectNumber],
    codeStats: options.codeStats ?? options.codeStatsByNumber?.[projectConfig.projectNumber],
  })));
  const dependencySnapshot = options.dependencySnapshot ?? (
    liveProjectConfigs.length > 0 ? await fetchNativeDependencies(repositoryRoot, models) : undefined
  );
  const html = renderDashboard(models, {
    generatedAt: options.generatedAt ?? new Date(), live: options.live, dependencySnapshot,
  });
  await mkdir(path.dirname(outputPath), { recursive: true });
  await writeFile(outputPath, html, "utf8");
  return models;
}

export function terminalSummary(models, outputPath) {
  const projects = Array.isArray(models) ? models : [models];
  const codeTotals = projects.reduce((totals, model) => ({
    total: totals.total + (model.codeStats?.total ?? 0),
    production: totals.production + (model.codeStats?.production ?? 0),
  }), { total: 0, production: 0 });
  const unavailableCodeProjects = projects.filter((model) => !model.codeStats);
  return [
    "VERA progress",
    `  Code: ${unavailableCodeProjects.length > 0 ? `unavailable (${unavailableCodeProjects.map((model) => model.codeStatsError ?? "local checkout missing").join("; ")})` : `${formatInteger(codeTotals.total)} total lines · ${formatInteger(codeTotals.production)} production`}`,
    ...projects.flatMap((model) => {
      const activeCount = model.statusCounts["In progress"] + model.statusCounts["In review"];
      return [
        `  ${model.projectTitle ?? "Board"}: ${model.doneCount} of ${model.totalWork} work items Done (${formatPercent(model.completionPercent)})`,
        `    ${model.remainingCount} remaining: ${activeCount} active/review, ${model.statusCounts.Blocked} Blocked, ${model.statusCounts.Ready} Ready`,
      ];
    }),
    `  Master queue: ${buildSharedRoadmap(projects).queue.length} positioned issues, ${buildSharedRoadmap(projects).milestones.length} program milestones`,
    `  Dashboard: ${outputPath}`,
  ].join("\n");
}
