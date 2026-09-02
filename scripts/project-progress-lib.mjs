import { execFile } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

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
  const items = projectDocument.items.map((item) => {
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
  return (
    (STATUS_ORDER.get(left.status) ?? 99) - (STATUS_ORDER.get(right.status) ?? 99)
    || left.number - right.number
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
  return `
              <article class="issue ${statusClass(item.status)}${options.goal ? " goal" : ""}" data-issue="${item.number}">
                <span class="status-dot" aria-hidden="true"></span>
                <div class="issue-main">
                  <div class="issue-heading">
                    <a href="${escapeHtml(item.url)}">#${item.number} · ${escapeHtml(item.title)}</a>
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

function renderWorkstream(group) {
  const summary = group.remainingCount === 0
    ? `${group.doneCount} done`
    : `${group.remainingCount} remaining · ${group.doneCount} done`;
  return `
        <details class="workstream"${group.remainingCount > 0 ? " open" : ""}>
          <summary>
            <span><strong>${escapeHtml(group.name)}</strong><small>${group.items.length} work items</small></span>
            <span class="workstream-summary">${summary}</span>
          </summary>
          <div class="issues">${group.items.map((item) => renderIssue(item)).join("")}
          </div>
        </details>`;
}

export function renderDashboard(model) {
  const completion = formatPercent(model.completionPercent);
  const metadataGapTotal = Object.values(model.metadataGaps).reduce((sum, count) => sum + count, 0);
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VERA Board Progress</title>
  <style>
    :root { color-scheme: dark; --ink:#f6f3ed; --muted:#a9b1c1; --deep:#080b13; --panel:#111724; --panel2:#171f2f; --line:#2b3445; --cyan:#60d8ee; --violet:#a58aff; --amber:#ffbf69; --green:#70dda4; --red:#ff7d83; }
    * { box-sizing:border-box; }
    body { margin:0; min-width:320px; background:radial-gradient(circle at 15% 0%,rgba(96,216,238,.12),transparent 34rem),radial-gradient(circle at 90% 12%,rgba(165,138,255,.13),transparent 30rem),var(--deep); color:var(--ink); font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; line-height:1.5; }
    .shell { width:min(1160px,calc(100% - 32px)); margin:0 auto; padding:52px 0 72px; }
    .eyebrow { margin:0 0 10px; color:var(--cyan); font-size:.73rem; font-weight:800; letter-spacing:.18em; text-transform:uppercase; }
    h1 { margin:0; max-width:850px; font-size:clamp(2.3rem,6vw,5.2rem); line-height:.98; letter-spacing:-.055em; }
    .intro { max-width:790px; margin:20px 0 0; color:var(--muted); }
    .hero { display:grid; grid-template-columns:minmax(250px,.8fr) minmax(0,2fr); gap:24px; margin:40px 0 24px; }
    .card,.workstream,.goal-panel,.notice { border:1px solid var(--line); border-radius:20px; background:linear-gradient(145deg,rgba(23,31,47,.96),rgba(13,18,29,.96)); box-shadow:0 20px 50px rgba(0,0,0,.2); }
    .progress-card { display:grid; place-items:center; min-height:280px; padding:24px; }
    .orbit { --progress:${model.completionPercent.toFixed(2)}%; position:relative; display:grid; place-items:center; width:210px; aspect-ratio:1; border-radius:50%; background:conic-gradient(var(--green) 0 var(--progress),rgba(112,221,164,.1) var(--progress) 100%); }
    .orbit::before { content:""; position:absolute; inset:13px; border-radius:50%; background:var(--panel); }
    .orbit-copy { position:relative; z-index:1; text-align:center; }
    .orbit-copy strong { display:block; font-size:3.3rem; line-height:1; letter-spacing:-.07em; }
    .orbit-copy span { display:block; margin-top:8px; color:var(--muted); font-size:.75rem; letter-spacing:.11em; text-transform:uppercase; }
    .scope-card { padding:26px; }
    .scope-card h2 { margin:0; font-size:1rem; }
    .scope-card p { margin:8px 0 0; color:var(--muted); font-size:.86rem; }
    .stats { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-top:24px; }
    .stat { padding:15px; border-top:1px solid var(--line); }
    .stat strong { display:block; font-size:2rem; line-height:1.1; }
    .stat span { color:var(--muted); font-size:.7rem; letter-spacing:.08em; text-transform:uppercase; }
    .lifecycle { display:grid; grid-template-columns:repeat(7,1fr); gap:8px; margin-top:10px; }
    .lifecycle div { padding:11px; border-radius:12px; background:rgba(8,11,19,.55); text-align:center; }
    .lifecycle strong { display:block; font-size:1.3rem; }
    .lifecycle span { color:var(--muted); font-size:.68rem; }
    .section-heading { display:flex; align-items:end; justify-content:space-between; gap:16px; margin:48px 0 14px; }
    .section-heading h2 { margin:0; font-size:1.35rem; }
    .section-heading p { margin:0; color:var(--muted); font-size:.8rem; }
    .roadmap { display:grid; gap:10px; }
    .workstream { overflow:hidden; border-radius:16px; }
    .workstream summary { display:flex; justify-content:space-between; gap:16px; align-items:center; padding:17px 20px; cursor:pointer; }
    .workstream summary strong,.workstream summary small { display:block; }
    .workstream summary small,.workstream-summary { color:var(--muted); font-size:.76rem; }
    .issues { display:grid; gap:1px; padding:0 10px 10px; }
    .issue { display:grid; grid-template-columns:12px minmax(0,1fr); gap:10px; padding:13px; border-radius:10px; background:rgba(8,11,19,.55); }
    .status-dot { width:8px; height:8px; margin-top:7px; border-radius:50%; background:var(--muted); }
    .issue.done .status-dot { background:var(--green); box-shadow:0 0 12px rgba(112,221,164,.4); }
    .issue.in-progress .status-dot,.issue.ready .status-dot { background:var(--cyan); }
    .issue.in-review .status-dot { background:var(--violet); }
    .issue.blocked .status-dot { background:var(--red); }
    .issue.inbox .status-dot,.issue.backlog .status-dot { background:var(--amber); }
    .issue-heading { display:flex; justify-content:space-between; align-items:start; gap:14px; }
    .issue-heading a { min-width:0; color:var(--ink); font-weight:650; text-decoration:none; }
    .issue-heading a:hover { color:var(--cyan); text-decoration:underline; }
    .status { flex:none; color:var(--muted); font-size:.74rem; }
    .chips { display:flex; flex-wrap:wrap; gap:6px; margin-top:8px; }
    .chip { padding:3px 7px; border:1px solid var(--line); border-radius:999px; color:var(--muted); font-size:.68rem; }
    .chip b { color:var(--violet); font-weight:650; }
    .chip.missing { color:var(--amber); border-color:rgba(255,191,105,.35); }
    .goal-panel { padding:10px; }
    .goal-panel .issue { background:rgba(23,31,47,.72); }
    .notice { margin-top:18px; padding:18px 20px; border-color:rgba(255,191,105,.35); }
    .notice h3 { margin:0; color:var(--amber); font-size:.9rem; }
    .notice p { margin:6px 0 0; color:var(--muted); font-size:.8rem; }
    @media (max-width:850px) { .hero{grid-template-columns:1fr}.lifecycle{grid-template-columns:repeat(4,1fr)} }
    @media (max-width:560px) { .shell{width:calc(100% - 20px);padding-top:34px}.stats{grid-template-columns:repeat(2,1fr)}.lifecycle{grid-template-columns:repeat(2,1fr)}.issue-heading,.section-heading{align-items:start;flex-direction:column}.status{align-self:flex-start} }
  </style>
</head>
<body>
  <main class="shell">
    <p class="eyebrow">VERA · authoritative GitHub Project</p>
    <h1>Progress you can trace<br>to the board.</h1>
    <p class="intro">Every number below comes from the live roadmap. A work item is complete only when its Project status is <strong>Done</strong>; every other non-goal issue is remaining scope.</p>
    <section class="hero" aria-label="Overall board progress">
      <div class="card progress-card"><div class="orbit" role="img" aria-label="${completion} of board work items Done"><div class="orbit-copy"><strong>${completion}</strong><span>board complete</span></div></div></div>
      <div class="card scope-card">
        <h2>Actionable board scope</h2>
        <p>Goals are shown separately and excluded from these totals so their child work is not counted twice.</p>
        <div class="stats">
          <div class="stat"><strong>${model.totalWork}</strong><span>Work items</span></div>
          <div class="stat"><strong>${model.doneCount}</strong><span>Done</span></div>
          <div class="stat"><strong>${model.remainingCount}</strong><span>Remaining</span></div>
        </div>
        <div class="lifecycle">${BOARD_STATUSES.map((status) => `<div><strong>${model.statusCounts[status]}</strong><span>${escapeHtml(status)}</span></div>`).join("")}</div>
      </div>
    </section>
    <div class="section-heading"><h2>Work by workstream</h2><p>${model.remainingCount} remaining · ${model.doneCount} Done · status from ${model.lastUpdated}</p></div>
    <section class="roadmap" aria-label="Board work by workstream">${model.workstreams.map(renderWorkstream).join("")}
    </section>
    <div class="section-heading"><h2>Goal rollups</h2><p>${model.goals.length} goals · excluded from work-item totals</p></div>
    <section class="goal-panel" aria-label="Goal rollups">${model.goals.length > 0 ? model.goals.map((goal) => renderIssue(goal, { goal: true })).join("") : "<p>No goal issues are currently on the board.</p>"}
    </section>
    <aside class="notice" aria-label="Board metadata coverage">
      <h3>${metadataGapTotal === 0 ? "Board metadata complete" : "Metadata missing"}</h3>
      <p>${metadataGapTotal === 0 ? "Every work item has workstream, priority, size, and acceptance fields." : `The dashboard does not invent missing values: ${model.metadataGaps.workstream} workstream, ${model.metadataGaps.priority} priority, ${model.metadataGaps.size} size, and ${model.metadataGaps.acceptance} acceptance field${model.metadataGaps.acceptance === 1 ? "" : "s"} are not set.`}</p>
    </aside>
  </main>
</body>
</html>
`;
}

export async function loadProgressModel(repositoryRoot, options = {}) {
  const configPath = path.join(repositoryRoot, ".github", "vera-roadmap.json");
  const projectConfig = JSON.parse(await readFile(configPath, "utf8"));
  let projectDocument = options.projectData;
  if (!projectDocument) {
    try {
      const { stdout } = await execFileAsync("gh", [
        "project", "item-list", String(projectConfig.projectNumber),
        "--owner", projectConfig.owner, "--limit", "500", "--format", "json",
      ], { cwd: repositoryRoot, maxBuffer: 10 * 1024 * 1024 });
      projectDocument = JSON.parse(stdout);
    } catch (error) {
      throw new Error(
        `GitHub Project is unavailable: ${error instanceof Error ? error.message : String(error)}`,
        { cause: error },
      );
    }
  }
  return buildProgressModel(parseProjectItems(projectDocument));
}

export async function writeDashboard(repositoryRoot, outputPath, options = {}) {
  const model = await loadProgressModel(repositoryRoot, options);
  const html = renderDashboard(model);
  await mkdir(path.dirname(outputPath), { recursive: true });
  await writeFile(outputPath, html, "utf8");
  return model;
}

export function terminalSummary(model, outputPath) {
  const activeCount = model.statusCounts["In progress"] + model.statusCounts["In review"];
  return [
    "VERA board progress",
    `  ${model.doneCount} of ${model.totalWork} board work items Done (${formatPercent(model.completionPercent)})`,
    `  ${model.remainingCount} remaining: ${activeCount} active/review, ${model.statusCounts.Blocked} Blocked, ${model.statusCounts.Ready} Ready`,
    `  ${model.goals.length} goal rollups shown separately`,
    `  Dashboard: ${outputPath}`,
  ].join("\n");
}
