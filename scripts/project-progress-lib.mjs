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

function metadataChip(label, value) {
  return `<span class="chip${value ? "" : " missing"}"><b>${escapeHtml(label)}</b> ${escapeHtml(value ?? "not set")}</span>`;
}

function renderIssue(item, options = {}) {
  const title = item.type === "historical"
    ? escapeHtml(item.title)
    : `#${item.number} · ${escapeHtml(item.title)}`;
  const titleMarkup = item.url
    ? `<a href="${escapeHtml(item.url)}">${title}</a>`
    : `<span class="issue-title">${title}</span>`;
  return `
              <article class="issue ${statusClass(item.status)}${options.goal ? " goal" : ""}" data-issue="${item.number}">
                <span class="status-dot" aria-hidden="true"></span>
                <div class="issue-main">
                  <div class="issue-heading">
                    ${titleMarkup}
                    <span class="status">${escapeHtml(item.status)}</span>
                  </div>
                  <div class="chips">
                    ${metadataChip("Route", `${item.model} · ${item.effort}`)}
                    ${metadataChip("Type", item.type)}
                    ${metadataChip("Priority", item.priority)}
                    ${metadataChip("Size", item.size)}
                    ${metadataChip("Acceptance", item.acceptance)}
                  </div>
                </div>
              </article>`;
}

function renderWorkstream(group, { open = true } = {}) {
  const summary = group.remainingCount === 0
    ? `${group.doneCount} done`
    : `${group.remainingCount} remaining · ${group.doneCount} done`;
  return `
        <details class="workstream"${open ? " open" : ""}>
          <summary>
            <span><strong>${escapeHtml(group.name)}</strong><small>${group.items.length} work items</small></span>
            <span class="workstream-summary">${summary}</span>
          </summary>
          <div class="issues">${group.items.map((item) => renderIssue(item)).join("")}
          </div>
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

function renderProjectCard(model, index) {
  const completion = formatPercent(model.completionPercent);
  const projectTitle = model.projectTitle ?? "VERA Board";
  const key = projectKey(model, index);
  return `
      <article class="card project-card"${model.projectNumber ? ` data-project="${model.projectNumber}"` : ""}>
        <div class="project-card-heading">
          <div>
            <p class="eyebrow">Project ${model.projectNumber ?? index + 1}</p>
            <h2>${escapeHtml(shortProjectTitle(model))}</h2>
          </div>
          <strong class="project-percent">${completion}</strong>
        </div>
        <div class="progress-track" role="img" aria-label="${completion} of ${escapeHtml(projectTitle)} work items Done"><span style="width:${model.completionPercent.toFixed(2)}%"></span></div>
        <div class="project-stats">
          <div><strong>${model.totalWork}</strong><span>Total</span></div>
          <div><strong>${model.doneCount}</strong><span>Done</span></div>
          <div><strong>${model.remainingCount}</strong><span>Remaining</span></div>
        </div>
        <div class="project-actions">
          <button type="button" data-open-tab="${key}-panel">View all work items</button>
          ${model.projectUrl ? `<a href="${escapeHtml(model.projectUrl)}" target="_blank" rel="noopener">Open board ↗</a>` : ""}
        </div>
      </article>`;
}

function renderProjectPanel(model, index) {
  const key = projectKey(model, index);
  return `
      <section id="${key}-panel" class="tab-panel detail-panel" role="tabpanel" aria-labelledby="${key}-tab" hidden>
        <div class="detail-heading">
          <div>
            <p class="eyebrow">${model.totalWork} work items · ${model.goals.length} goals</p>
            <h1>${escapeHtml(model.projectTitle ?? "VERA Board")}</h1>
          </div>
          ${model.projectUrl ? `<a href="${escapeHtml(model.projectUrl)}" target="_blank" rel="noopener">Open GitHub Project ↗</a>` : ""}
        </div>
        <div class="roadmap" aria-label="All board work items by workstream">${model.workstreams.length > 0
          ? model.workstreams.map((group) => renderWorkstream(group, { open: false })).join("")
          : '<p class="empty-state">No actionable work items are currently on this board.</p>'}
        </div>
        <section class="goal-panel card" aria-label="Goal rollups">
          <h2>Goal rollups</h2>
          <p>Goals provide context and are excluded from actionable work totals.</p>
          <div class="issues">${model.goals.length > 0
            ? model.goals.map((goal) => renderIssue(goal, { goal: true })).join("")
            : '<p class="empty-state">No goal issues are currently on this board.</p>'}
          </div>
        </section>
      </section>`;
}

export function renderDashboard(models) {
  const projects = Array.isArray(models) ? models : [models];
  const unavailableCodeProjects = projects.filter((model) => !model.codeStats);
  const codeTotals = projects.reduce((totals, model) => ({
    total: totals.total + (model.codeStats?.total ?? 0),
    production: totals.production + (model.codeStats?.production ?? 0),
  }), { total: 0, production: 0 });
  const totalWork = projects.reduce((total, model) => total + model.totalWork, 0);
  const doneCount = projects.reduce((total, model) => total + model.doneCount, 0);
  const remainingCount = totalWork - doneCount;
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VERA Progress</title>
  <style>
    :root { color-scheme:dark; --ink:#f6f3ed; --muted:#a9b1c1; --deep:#080b13; --panel:#111724; --panel2:#171f2f; --line:#2b3445; --cyan:#60d8ee; --violet:#a58aff; --amber:#ffbf69; --green:#70dda4; --red:#ff7d83; }
    * { box-sizing:border-box; }
    html { scroll-behavior:smooth; }
    body { margin:0; min-width:320px; background:radial-gradient(circle at 15% 0%,rgba(96,216,238,.12),transparent 34rem),radial-gradient(circle at 90% 12%,rgba(165,138,255,.13),transparent 30rem),var(--deep); color:var(--ink); font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; line-height:1.5; }
    button,a { font:inherit; }
    .shell { width:min(1180px,calc(100% - 32px)); margin:0 auto; }
    .tabs { position:sticky; top:0; z-index:5; display:flex; gap:8px; padding:12px 0; background:linear-gradient(var(--deep) 70%,transparent); }
    .tabs button { padding:9px 13px; border:1px solid var(--line); border-radius:9px; background:var(--panel2); color:var(--ink); cursor:pointer; }
    .tabs button:hover,.tabs button[aria-selected="true"] { border-color:var(--cyan); color:var(--cyan); }
    .tabs button[aria-selected="true"] { background:rgba(96,216,238,.1); }
    .overview { min-height:calc(100svh - 62px); display:flex; flex-direction:column; justify-content:center; gap:22px; padding:26px 0 42px; }
    .page-header { display:flex; justify-content:space-between; align-items:end; gap:24px; }
    .eyebrow { margin:0 0 7px; color:var(--cyan); font-size:.7rem; font-weight:800; letter-spacing:.16em; text-transform:uppercase; }
    h1,h2 { margin:0; letter-spacing:-.035em; }
    h1 { font-size:clamp(2.2rem,5vw,4rem); line-height:1; }
    .summary { margin:0; color:var(--muted); text-align:right; }
    .summary strong { color:var(--ink); }
    .card,.workstream { border:1px solid var(--line); border-radius:18px; background:linear-gradient(145deg,rgba(23,31,47,.96),rgba(13,18,29,.96)); box-shadow:0 18px 45px rgba(0,0,0,.18); }
    .loc-card { display:grid; grid-template-columns:minmax(180px,.7fr) repeat(2,minmax(220px,1fr)); gap:18px; align-items:center; padding:22px 26px; border-color:rgba(96,216,238,.34); background:linear-gradient(120deg,rgba(96,216,238,.13),rgba(165,138,255,.12)),var(--panel); }
    .loc-card h2 { font-size:1.1rem; }
    .loc-number { padding-left:22px; border-left:1px solid var(--line); }
    .loc-number strong { display:block; font-size:clamp(2rem,4.5vw,3.8rem); line-height:1; letter-spacing:-.055em; }
    .loc-number span { display:block; margin-top:6px; color:var(--muted); font-size:.72rem; letter-spacing:.09em; text-transform:uppercase; }
    .definition { margin:6px 0 0; color:var(--muted); font-size:.73rem; }
    .project-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; }
    .project-card { padding:22px; }
    .project-card-heading { display:flex; align-items:start; justify-content:space-between; gap:16px; }
    .project-card h2 { font-size:clamp(1.35rem,2.5vw,2rem); }
    .project-percent { color:var(--green); font-size:1.65rem; letter-spacing:-.04em; }
    .progress-track { height:8px; margin:19px 0; overflow:hidden; border-radius:999px; background:rgba(112,221,164,.1); }
    .progress-track span { display:block; height:100%; border-radius:inherit; background:var(--green); }
    .project-stats { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }
    .project-stats div { padding:10px; border-radius:10px; background:rgba(8,11,19,.52); }
    .project-stats strong,.project-stats span { display:block; }
    .project-stats strong { font-size:1.35rem; }
    .project-stats span { color:var(--muted); font-size:.68rem; text-transform:uppercase; letter-spacing:.08em; }
    .project-actions { display:flex; align-items:center; gap:16px; margin-top:18px; }
    .project-actions button { padding:9px 13px; border:1px solid var(--line); border-radius:9px; background:var(--panel2); color:var(--ink); cursor:pointer; }
    .project-actions button:hover { border-color:var(--cyan); color:var(--cyan); }
    .project-actions a,.detail-heading a { color:var(--muted); font-size:.8rem; text-decoration:none; }
    .project-actions a:hover,.detail-heading a:hover { color:var(--cyan); text-decoration:underline; }
    .detail-panel { padding:38px 0 80px; }
    .detail-heading { display:flex; justify-content:space-between; align-items:end; gap:20px; margin:0 0 24px; }
    .detail-heading h1 { font-size:clamp(1.8rem,4vw,3rem); }
    .roadmap { display:grid; gap:10px; }
    .workstream { overflow:hidden; }
    .workstream summary { display:flex; justify-content:space-between; gap:16px; align-items:center; padding:16px 19px; cursor:pointer; }
    .workstream summary strong,.workstream summary small { display:block; }
    .workstream summary small,.workstream-summary { color:var(--muted); font-size:.76rem; }
    .issues { display:grid; gap:1px; padding:0 10px 10px; }
    .issue { display:grid; grid-template-columns:12px minmax(0,1fr); gap:10px; padding:13px; border-radius:10px; background:rgba(8,11,19,.55); }
    .status-dot { width:8px; height:8px; margin-top:7px; border-radius:50%; background:var(--muted); }
    .issue.in-progress .status-dot,.issue.ready .status-dot { background:var(--cyan); }
    .issue.in-review .status-dot { background:var(--violet); }
    .issue.blocked .status-dot { background:var(--red); }
    .issue.inbox .status-dot,.issue.backlog .status-dot { background:var(--amber); }
    .issue-heading { display:flex; justify-content:space-between; align-items:start; gap:14px; }
    .issue-heading a,.issue-title { min-width:0; color:var(--ink); font-weight:650; text-decoration:none; }
    .issue-heading a:hover { color:var(--cyan); text-decoration:underline; }
    .goal-panel { margin-top:26px; padding:20px; }
    .goal-panel h2 { font-size:1.25rem; }
    .goal-panel > p { margin:5px 0 14px; color:var(--muted); font-size:.8rem; }
    .status { flex:none; color:var(--muted); font-size:.74rem; }
    .chips { display:flex; flex-wrap:wrap; gap:6px; margin-top:8px; }
    .chip { padding:3px 7px; border:1px solid var(--line); border-radius:999px; color:var(--muted); font-size:.68rem; }
    .chip b { color:var(--violet); font-weight:650; }
    .chip.missing { color:var(--amber); border-color:rgba(255,191,105,.35); }
    .empty-state { margin:0; padding:24px; border:1px solid var(--line); border-radius:16px; color:var(--muted); }
    [hidden] { display:none !important; }
    @media (max-width:760px) { .overview{min-height:auto;padding-top:30px}.page-header,.detail-heading{align-items:start;flex-direction:column}.summary{text-align:left}.loc-card{grid-template-columns:1fr 1fr}.loc-copy{grid-column:1/-1}.loc-number{padding:0;border:0}.project-grid{grid-template-columns:1fr}.tabs button{flex:1} }
    @media (max-width:480px) { .shell{width:calc(100% - 20px)}.loc-card{grid-template-columns:1fr}.loc-copy{grid-column:auto}.project-actions{align-items:start;flex-direction:column}.issue-heading{align-items:start;flex-direction:column}.status{align-self:flex-start} }
  </style>
</head>
<body>
  <main class="shell">
    <nav class="tabs" role="tablist" aria-label="VERA progress views">
      <button id="dashboard-tab" type="button" role="tab" aria-selected="true" aria-controls="dashboard-panel" tabindex="0">Dashboard</button>
      ${projects.map((model, index) => {
        const key = projectKey(model, index);
        return `<button id="${key}-tab" type="button" role="tab" aria-selected="false" aria-controls="${key}-panel" tabindex="-1">${escapeHtml(shortProjectTitle(model))}</button>`;
      }).join("\n")}
    </nav>
    <section id="dashboard-panel" class="overview tab-panel" role="tabpanel" aria-labelledby="dashboard-tab">
      <header class="page-header">
        <div><p class="eyebrow">Live GitHub Projects</p><h1 id="page-title">VERA Progress</h1></div>
        <p class="summary"><strong>${doneCount} of ${totalWork}</strong> work items Done<br>${remainingCount} remaining across both projects</p>
      </header>
      <section class="card loc-card" aria-label="VERA code line counts">
        <div class="loc-copy"><p class="eyebrow">Both codebases</p><h2>Tracked source lines</h2><p class="definition">Physical lines in tracked source files. Production excludes tests, fixtures, tooling, and generated output.${unavailableCodeProjects.length > 0 ? ` Counts unavailable for ${unavailableCodeProjects.map((model) => escapeHtml(model.projectTitle ?? "a project")).join(", ")}. ${unavailableCodeProjects.map((model) => escapeHtml(model.codeStatsError ?? "Check the local repository path.")).join(" ")}` : ""}</p></div>
        <div class="loc-number"><strong>${unavailableCodeProjects.length > 0 ? "Unavailable" : formatInteger(codeTotals.total)}</strong><span>Total lines of code</span></div>
        <div class="loc-number"><strong>${unavailableCodeProjects.length > 0 ? "Unavailable" : formatInteger(codeTotals.production)}</strong><span>Production code lines</span></div>
      </section>
      <section class="project-grid" aria-label="Project progress summaries">
        ${projects.map(renderProjectCard).join("\n")}
      </section>
    </section>
    ${projects.map(renderProjectPanel).join("\n")}
  </main>
  <script>
    const tabs = [...document.querySelectorAll('[role="tab"]')];
    const panels = [...document.querySelectorAll('[role="tabpanel"]')];
    function selectPanel(panelId, { focus = false } = {}) {
      const selectedTab = tabs.find((tab) => tab.getAttribute('aria-controls') === panelId);
      if (!selectedTab) return;
      for (const tab of tabs) {
        const selected = tab === selectedTab;
        tab.setAttribute('aria-selected', String(selected));
        tab.tabIndex = selected ? 0 : -1;
      }
      for (const panel of panels) panel.hidden = panel.id !== panelId;
      if (focus) selectedTab.focus();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    for (const tab of tabs) {
      tab.addEventListener('click', () => selectPanel(tab.getAttribute('aria-controls')));
      tab.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const current = tabs.indexOf(tab);
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
        selectPanel(tabs[next].getAttribute('aria-controls'), { focus: true });
      });
    }
    for (const button of document.querySelectorAll('[data-open-tab]')) {
      button.addEventListener('click', () => selectPanel(button.dataset.openTab));
    }
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
  const html = renderDashboard(models);
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
