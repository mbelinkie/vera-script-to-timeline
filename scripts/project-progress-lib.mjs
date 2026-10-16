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
  return {
    number,
    title,
    url,
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
    if (seen.has(parsed.number)) throw new Error(`Duplicate project issue #${parsed.number}`);
    seen.add(parsed.number);
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
            <li class="issue ${statusClass(item.status)}" data-issue="${item.number}">
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
          <p class="pct" aria-label="${displayPercent(model.completionPercent)} of work items done">${displayPercent(model.completionPercent)}</p>
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

export function renderDashboard(models, options = {}) {
  const projects = Array.isArray(models) ? models : [models];
  const totalWork = projects.reduce((total, model) => total + model.totalWork, 0);
  const doneCount = projects.reduce((total, model) => total + model.doneCount, 0);
  const scope = projects.length > 1 ? " across both boards" : "";
  const updated = options.generatedAt ? `. Updated ${escapeHtml(formatGeneratedAt(options.generatedAt))}` : "";
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
        --done:#2e9462; --review:#8862cf; --progress:#c4861a; --blocked:#c8423a; --ready:#2d7dc0; --backlog:#a8adb5; --inbox:#c9cdd3; --warn:#a46a00; }
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
    <section class="grid${projects.length === 1 ? " single" : ""}" aria-label="Board progress">${projects.map(renderBoardCard).join("")}
    </section>
    <div class="section-head">
      <h2>Work by workstream</h2>
      <button type="button" class="toggle-all" aria-pressed="false">Expand all</button>
    </div>
    <div class="grid${projects.length === 1 ? " single" : ""}">${projects.map(renderWorkstreamColumn).join("")}
    </div>
  </main>
  <script>
    const toggle = document.querySelector('.toggle-all');
    const rows = [...document.querySelectorAll('details.ws')];
    function syncToggle() {
      const allOpen = rows.length > 0 && rows.every((row) => row.open);
      toggle.textContent = allOpen ? 'Collapse all' : 'Expand all';
      toggle.setAttribute('aria-pressed', String(allOpen));
    }
    toggle.addEventListener('click', () => {
      const open = !rows.every((row) => row.open);
      for (const row of rows) row.open = open;
      syncToggle();
    });
    for (const row of rows) row.addEventListener('toggle', syncToggle);
  </script>
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
  const html = renderDashboard(models, { generatedAt: options.generatedAt ?? new Date() });
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
    `  Dashboard: ${outputPath}`,
  ].join("\n");
}
