import { readFileSync } from "node:fs";
import { URL } from "node:url";

import { deriveWorkflow, WORKFLOW_FRESHNESS_MS } from "./project-progress-workflow.mjs";

export const queueStyles = readFileSync(new URL("./project-progress-queue.css", import.meta.url), "utf8");

export const queueClientScript = String.raw`(() => {
  const root = document.querySelector(".workflow-queue");
  if (!root) return;

  const expiresAt = Number(root.dataset.workflowExpiresAt);
  let stale = false;
  function markStatus(status) {
    if (status.dataset.workflowStatus === "stale") return;
    status.dataset.workflowStatus = "stale";
    status.textContent = "Stale · needs refresh";
  }
  function markStale() {
    if (stale) return;
    stale = true;
    root.dataset.stale = "true";
    document.documentElement.dataset.snapshotStale = "true";
    for (const link of root.querySelectorAll("a[data-requires-fresh]")) {
      link.removeAttribute("href");
      link.setAttribute("aria-disabled", "true");
      link.setAttribute("tabindex", "-1");
    }
    for (const status of root.querySelectorAll("[data-workflow-status]")) markStatus(status);
    for (const next of root.querySelectorAll("[data-workflow-next]")) next.textContent = "Unknown · Refresh sources before acting.";
  }
  function checkExpiry() {
    const now = Date.now();
    if (!Number.isFinite(expiresAt) || now > expiresAt) return markStale();
    let next = expiresAt;
    for (const status of root.querySelectorAll("[data-workflow-status][data-workflow-expires-at]")) {
      const sourceExpiry = Number(status.dataset.workflowExpiresAt);
      if (!Number.isFinite(sourceExpiry) || now > sourceExpiry) markStatus(status);
      else next = Math.min(next, sourceExpiry);
    }
    for (const link of root.querySelectorAll("a[data-requires-fresh][data-workflow-expires-at]")) {
      const sourceExpiry = Number(link.dataset.workflowExpiresAt);
      if (!Number.isFinite(sourceExpiry) || now > sourceExpiry) {
        link.removeAttribute("href");
        link.setAttribute("aria-disabled", "true");
        link.setAttribute("tabindex", "-1");
      } else next = Math.min(next, sourceExpiry);
    }
    setTimeout(checkExpiry, Math.min(Math.max(next - now + 1, 1), 60_000));
  }
  if (root.dataset.stale === "true" || document.documentElement.dataset.snapshotStale === "true") markStale();
  else checkExpiry();

  const groups = new Map([...root.querySelectorAll("[data-queue-group]")].map((group) => [group.dataset.queueGroup, group]));
  const flat = root.querySelector("[data-flat-rows]");
  let mode = "groups";
  let actorFilter = "all";

  function rows() {
    return [...root.querySelectorAll(".wf-row")].sort((left, right) => Number(left.dataset.rowIndex) - Number(right.dataset.rowIndex));
  }

  function applyFilters() {
    const query = root.querySelector("[data-filter-search]").value.trim().toLowerCase();
    const project = root.querySelector("[data-filter-project]").value;
    const status = root.querySelector("[data-filter-status]").value;
    const size = root.querySelector("[data-filter-size]").value;
    const dependency = root.querySelector("[data-filter-dependency]").value;
    let visible = 0;

    for (const row of rows()) {
      const matches = (!query || row.dataset.search.includes(query))
        && (!project || row.dataset.project === project)
        && (!status || row.dataset.status === status)
        && (!size || row.dataset.size === size)
        && (!dependency || row.dataset.dependency === dependency)
        && (actorFilter === "all" || row.dataset.filter === actorFilter);
      row.hidden = !matches;
      const detail = root.querySelector("#" + CSS.escape(row.dataset.detailId));
      if (detail && !matches) {
        detail.hidden = true;
        row.querySelector("[data-expand-row]")?.setAttribute("aria-expanded", "false");
      }
      if (matches) visible++;
    }

    for (const [key, group] of groups) {
      const count = rows().filter((row) => row.dataset.group === key && !row.hidden).length;
      group.querySelector("[data-group-count]").textContent = String(count);
      group.hidden = mode === "flat" || count === 0;
    }
    flat.hidden = mode !== "flat";
    root.querySelector("[data-empty-results]").hidden = visible > 0;
  }

  function setMode(nextMode) {
    if (nextMode === mode) return;
    if (nextMode === "flat") {
      for (const row of rows()) {
        const detail = root.querySelector("#" + CSS.escape(row.dataset.detailId));
        flat.append(row);
        if (detail) flat.append(detail);
      }
    } else {
      for (const row of rows()) {
        const group = groups.get(row.dataset.group);
        const detail = root.querySelector("#" + CSS.escape(row.dataset.detailId));
        const list = group?.querySelector(".wf-group-rows");
        if (list) {
          list.append(row);
          if (detail) list.append(detail);
        }
      }
    }
    mode = nextMode;
    for (const button of root.querySelectorAll("[data-queue-mode]")) {
      button.setAttribute("aria-pressed", String(button.dataset.queueMode === mode));
    }
    applyFilters();
  }

  root.addEventListener("click", (event) => {
    const modeButton = event.target.closest("[data-queue-mode]");
    if (modeButton) {
      setMode(modeButton.dataset.queueMode);
      return;
    }

    const filterButton = event.target.closest("[data-actor-filter]");
    if (filterButton) {
      actorFilter = filterButton.dataset.actorFilter;
      for (const button of root.querySelectorAll("[data-actor-filter]")) {
        button.setAttribute("aria-pressed", String(button === filterButton));
      }
      applyFilters();
      return;
    }

    const expand = event.target.closest("[data-expand-row]");
    if (expand) {
      const detail = root.querySelector("#" + CSS.escape(expand.dataset.detailId));
      const opening = expand.getAttribute("aria-expanded") !== "true";
      expand.setAttribute("aria-expanded", String(opening));
      if (detail) detail.hidden = !opening;
    }
  });

  for (const selector of ["[data-filter-search]", "[data-filter-project]", "[data-filter-status]", "[data-filter-size]", "[data-filter-dependency]"]) {
    root.querySelector(selector).addEventListener(selector.includes("search") ? "input" : "change", applyFilters);
  }
})();`;

const GROUPS = [
  ["launch", "Ready to launch", "Fresh evidence supports the next step."],
  ["you", "Needs you", "A decision or approval is the next step."],
  ["working", "Working", "The current state indicates work is in progress."],
  ["stuck", "Stuck", "A source is blocked, missing, stale, or needs attention."],
  ["done", "Done", "Completed work."],
];
const CHIP_NAMES = ["Chat", "DeepSeek", "Codex", "Review", "CI"];
const STATUS_ORDER = ["Done", "In review", "In progress", "Blocked", "Ready", "Backlog", "Inbox"];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function publicText(value) {
  return String(value ?? "")
    .replace(/\b[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/gi, "[local identifier hidden]")
    .replace(/(?:file:\/\/|\/(?:Users|Volumes|Applications|Library|private|tmp|var(?:\/folders)?|home|opt)\/|~\/)[^\s]*/g, "[local path hidden]");
}

function text(value) {
  return escapeHtml(publicText(value));
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function numericOrder(value) {
  const number = typeof value === "number" ? value : typeof value === "string" && /^\d+(?:\.\d+)?$/.test(value) ? Number(value) : NaN;
  return Number.isFinite(number) ? number : null;
}

function projectName(project, index) {
  return project.projectTitle ?? project.title ?? `Project ${project.projectNumber ?? index + 1}`;
}

function canonicalUrl(value) {
  if (typeof value !== "string") return null;
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || !/(^|\.)github\.com$/i.test(url.hostname)) return null;
    url.search = "";
    url.hash = "";
    url.pathname = url.pathname.replace(/\/+$/, "").toLowerCase();
    return url.href;
  } catch {
    return null;
  }
}

function flattenProjects(projects, roadmapQueue, now, workflowEvidence) {
  const roadmapByUrl = new Map(roadmapQueue.map((entry) => [canonicalUrl(entry.url), entry]).filter(([url]) => url));
  const projectByName = new Map(projects.map((project, index) => [projectName(project, index), { project, projectIndex: index }]));
  const rowsByUrl = new Map();
  const unlinkedRows = [];
  const historicalByKey = new Map();
  for (const [projectIndex, project] of projects.entries()) {
    for (const [itemIndex, item] of asArray(project.workItems).entries()) {
      if (item.type === "historical") {
        const key = `${project.projectNumber ?? projectIndex + 1}:${item.number ?? itemIndex}`;
        if (!historicalByKey.has(key)) historicalByKey.set(key, { projectNumber: project.projectNumber ?? projectIndex + 1, projectName: projectName(project, projectIndex), status: item.status });
        continue;
      }
      const key = canonicalUrl(item.url) ?? `unlinked:${projectIndex}:${itemIndex}`;
      const road = roadmapByUrl.get(key);
      const selectedProject = road?.projectTitle ? projectByName.get(road.projectTitle) : null;
      const displayProject = selectedProject?.project ?? project;
      const displayProjectIndex = selectedProject?.projectIndex ?? projectIndex;
      const displayName = road?.projectTitle ?? projectName(displayProject, displayProjectIndex);
      const mergedItem = {
        ...item,
        ...(road ?? {}),
        snapshotAt: item.snapshotAt ?? project.snapshotAt,
        projectLastError: item.projectLastError ?? project.projectLastError,
      };
      const evidence = {
        ...workflowEvidence,
        issues: workflowEvidence.lastError ? {} : workflowEvidence.issues,
        project: {
          ...workflowEvidence.project,
          snapshotAt: mergedItem.snapshotAt ?? workflowEvidence.project?.snapshotAt,
          lastError: mergedItem.projectLastError ?? workflowEvidence.project?.lastError,
        },
      };
      let workflow;
      try {
        workflow = deriveWorkflow(mergedItem, evidence, now);
      } catch {
        workflow = {
          group: "stuck", actor: "Unknown", action: "Workflow evidence could not be derived.", filter: "blocked",
          chips: [], links: [], disabled: ["Workflow evidence could not be derived for this issue."], sources: [],
        };
      }
      const row = {
        key,
        item: mergedItem,
        road,
        project: displayProject,
        projectIndex: displayProjectIndex,
        projectNumber: displayProject.projectNumber ?? project.projectNumber,
        projectName: displayName,
        itemIndex,
        workflow,
        queueOrder: numericOrder(road ? road.queueOrder : item.queueOrder),
        dependencies: asArray(road?.dependencies ?? item.dependencies),
        dependenciesVerified: typeof road?.dependenciesVerified === "boolean" ? road.dependenciesVerified : null,
      };
      if (key.startsWith("unlinked:")) unlinkedRows.push(row);
      else if (!rowsByUrl.has(key)) rowsByUrl.set(key, row);
      else {
        const existing = rowsByUrl.get(key);
        if (!existing.road && row.road) rowsByUrl.set(key, row);
      }
    }
  }
  const rows = [...rowsByUrl.values(), ...unlinkedRows];
  rows.sort((left, right) => {
    if (left.queueOrder !== null || right.queueOrder !== null) {
      if (left.queueOrder === null) return 1;
      if (right.queueOrder === null) return -1;
      if (left.queueOrder !== right.queueOrder) return left.queueOrder - right.queueOrder;
    }
    return left.projectIndex - right.projectIndex || left.itemIndex - right.itemIndex;
  });
  return { rows, historical: [...historicalByKey.values()] };
}

function toneClass(tone) {
  return ["ok", "active", "wait", "attention", "blocked", "unknown", "na"].includes(tone) ? tone : "unknown";
}

function chipFor(name, chips) {
  const aliases = {
    Chat: ["chat", "approval"],
    DeepSeek: ["deepseek"],
    Codex: ["codex"],
    Review: ["review", "claude"],
    CI: ["ci", "controller"],
  }[name] ?? [name.toLowerCase()];
  return chips.find((chip) => aliases.some((alias) => String(chip.name ?? "").toLowerCase().includes(alias)))
    ?? { name, label: "Unknown", tone: "unknown", detail: "No status was supplied for this source." };
}

function isApprovedCurrent(chip) {
  return /approved.{0,24}current|current.{0,24}approved/i.test(String(chip.label ?? ""));
}

function chipMarkup(name, chip) {
  const fresh = chip.requiresFresh === true || isApprovedCurrent(chip);
  const detail = chip.detail ? ` title="${text(chip.detail)}"` : "";
  const status = fresh ? ` data-workflow-status="${text(chip.state || (isApprovedCurrent(chip) ? "approved-current" : "status"))}" data-requires-fresh="true"` : "";
  return `<span class="wf-chip tone-${toneClass(chip.tone)}"${detail}><span>${text(name)}</span><strong${status}>${text(chip.label)}</strong></span>`;
}

function safeWorkflowUrl(link) {
  if (!link || typeof link.url !== "string") return null;
  try {
    const url = new URL(link.url);
    if (url.protocol !== "https:") return null;
    const githubHost = url.hostname.toLowerCase() === "github.com";
    const chatHost = url.hostname.toLowerCase() === "chatgpt.com";
    if (!githubHost && !chatHost) return null;
    if (/\b[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/i.test(url.href)) return null;
    if (/\/(?:Users|Volumes|private|tmp|var\/folders|home)\//i.test(url.href)) return null;
    if (/(?:^|\.)localhost$/i.test(url.hostname) || url.hostname === "127.0.0.1" || url.hostname === "::1") return null;
    const githubPath = /^\/[^/]+\/[^/]+\/(?:issues\/\d+(?:\/comments)?|pull\/\d+(?:\/(?:checks|files|commits))?|actions\/runs\/\d+|commit\/[0-9a-f]{7,40}|commits\/[0-9a-f]{7,40})$/i;
    const chatPath = /^\/(?:g\/[a-z0-9_-]+(?:\/[^/?#]+)?|share\/[a-z0-9_-]+|c\/[a-z0-9_-]+)\/?$/i;
    const chatPrompt = chatHost && link.label === "Open Chat review prompt" && url.pathname === "/" && !url.search && !url.hash;
    if (githubHost && !githubPath.test(url.pathname)) return null;
    if (chatHost && !chatPath.test(url.pathname) && !chatPrompt) return null;
    if (chatPrompt) return `${url.origin}/`;
    const hash = githubHost && /^#issuecomment-\d+$/.test(url.hash) ? url.hash : "";
    return `${url.origin}${url.pathname}${hash}`;
  } catch {
    return null;
  }
}

function itemUrl(item) {
  if (typeof item.url !== "string") return null;
  try {
    const url = new URL(item.url);
    if (url.protocol !== "https:" || url.hostname.toLowerCase() !== "github.com" || !/^\/[^/]+\/[^/]+\/issues\/\d+\/?$/i.test(url.pathname)) return null;
    if (/\b[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/i.test(url.href)) return null;
    if (/\/(?:Users|Volumes|private|tmp|var\/folders|home)\//i.test(url.href)) return null;
    return `${url.origin}${url.pathname.replace(/\/+$/, "")}`;
  } catch {
    return null;
  }
}

function workflowLinks(row, options) {
  const links = asArray(row.workflow.links).map((link) => {
    const href = safeWorkflowUrl(link);
    if (!href) return null;
    const label = String(link.label ?? "");
    const requiresFresh = link.requiresFresh === true || /^(?:Open Chat review prompt|Verified Chat review|CI run)$/i.test(label);
    return { ...link, href, requiresFresh };
  }).filter(Boolean);
  const session = row.workflow.session;
  const issue = itemUrl(row.item);
  if (options.live === true && issue && session?.hasBrowser === true && ["verified-local", "web-only"].includes(session.status)) {
    links.unshift({ href: `/local-session?issue=${encodeURIComponent(issue)}&surface=browser`, label: "Open separate web conversation", requiresFresh: true, primary: true });
  }
  if (options.live === true && issue && session?.status === "verified-local") {
    links.unshift({ href: `/local-session?issue=${encodeURIComponent(issue)}`, label: "Open existing Codex chat", requiresFresh: true, primary: true });
  }
  return links;
}

function renderWorkflowLinks(links) {
  const markup = links.map((link) => `<a href="${escapeHtml(link.href)}"${link.href.startsWith("https:") ? ' target="_blank" rel="noopener noreferrer"' : ""}${link.requiresFresh ? ' data-requires-fresh="true"' : ""}>${text(link.label || "Open evidence")}</a>${link.label === "Open Chat review prompt" && typeof link.prompt === "string" ? `<details class="wf-chat-prompt"><summary>Chat review draft</summary><p>Copy this draft into ChatGPT and send it when ready.</p><pre>${text(link.prompt)}</pre></details>` : ""}`).join("");
  return markup || '<span class="wf-muted">No safe workflow link is available.</span>';
}

function primaryActionMarkup(row, options) {
  const links = workflowLinks(row, options);
  const find = (label) => links.find((link) => link.label === label);
  const issue = find("Issue") ?? (itemUrl(row.item) ? { href: itemUrl(row.item), label: "Issue" } : null);
  const chat = row.workflow.chat;
  const ciState = row.workflow.ci?.state;
  const chatPending = chat?.state === "pending";
  const ciNeeded = row.workflow.actor === "CI" || ["waiting", "validating", "smoke-running", "failed-paused"].includes(ciState);
  const pr = find("PR");
  const needsReview = row.workflow.review?.state === "unknown" && pr;
  const approvedCurrent = chat?.state === "approved" || isApprovedCurrent(chipFor("Chat", asArray(row.workflow.chips)));
  const primary = (chatPending ? find("Open Chat review prompt") ?? issue
    : ciNeeded ? find("CI run") ?? pr
      : needsReview ? pr
        : approvedCurrent ? find("Verified Chat review")
          : null) ?? links.find((link) => link.primary) ?? issue;
  if (primary) return `<a class="wf-primary-action" href="${escapeHtml(primary.href)}"${primary.href.startsWith("https:") ? ' target="_blank" rel="noopener noreferrer"' : ""}${primary.requiresFresh ? ' data-requires-fresh="true"' : ""}>${text(primary.label)}</a>`;
  const reason = row.workflow.session?.reason || asArray(row.workflow.disabled)[0] || "No safe next-action link is available.";
  return `<span class="wf-action-reason">${text(reason)}</span>`;
}

function formatSnapshot(value) {
  if (value == null || value === "") return '<span class="wf-muted">snapshot time unavailable</span>';
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return `<span>${text(value)}</span>`;
  return `<time datetime="${date.toISOString()}">${escapeHtml(new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" }).format(date))}</time>`;
}

function workflowExpiresAt(projects, workflow, now) {
  const snapshots = [
    ...projects.map((project) => project.snapshotAt),
    workflow.snapshotAt,
  ];
  let earliest = Infinity;
  for (const value of snapshots) {
    const timestamp = value instanceof Date ? value.getTime() : typeof value === "string" ? Date.parse(value) : NaN;
    if (!Number.isFinite(timestamp) || timestamp > now.getTime()) return now.getTime() - 1;
    earliest = Math.min(earliest, timestamp + WORKFLOW_FRESHNESS_MS);
  }
  return Number.isFinite(earliest) ? earliest : now.getTime() - 1;
}

function staleNotice(projects, workflow, rows) {
  const groups = GROUPS.map(([key, label]) => `${label} ${rows.filter((row) => row.workflow.group === key).length}`).join(" · ");
  const projectSnapshots = projects.map((project, index) => `${text(projectName(project, index))} ${formatSnapshot(project.snapshotAt)}`).join(" · ") || "unavailable";
  return `<aside class="wf-stale-notice" role="status" aria-live="polite"><strong>Last-known groups:</strong> ${text(groups)}<span>Last checks: Project ${projectSnapshots} · workflow ${formatSnapshot(workflow.snapshotAt)}</span></aside>`;
}

function renderSources(sources) {
  const list = asArray(sources);
  if (!list.length) return '<p class="wf-muted">Per-source freshness details are unavailable.</p>';
  return `<ul class="wf-source-list">${list.map((source) => `<li><strong>${text(source.name || "Source")}</strong><span>Snapshot: ${formatSnapshot(source.snapshotAt)}</span>${source.lastError ? `<span class="wf-error">Refresh error: ${text(source.lastError)}</span>` : ""}</li>`).join("")}</ul>`;
}

function renderDependencies(row) {
  if (!row.dependencies.length) {
    return row.dependenciesVerified === true
      ? '<p class="wf-muted">No dependencies.</p>'
      : '<p class="wf-muted">Dependency state is unavailable.</p>';
  }
  const list = `<ul class="wf-dependencies">${row.dependencies.map((dependency) => {
    const label = typeof dependency === "string" ? dependency : dependency.label || dependency.url || "Dependency";
    const state = typeof dependency === "object" && dependency.invalid ? "Invalid reference"
      : typeof dependency === "object" && dependency.isOpen === true ? "Open"
        : typeof dependency === "object" && dependency.isOpen === false ? "Done"
          : "Status unknown";
    return `<li><span>${text(label)}</span><span>${state}</span></li>`;
  }).join("")}</ul>`;
  return `${row.dependenciesVerified === false ? '<p class="wf-error">Dependency data is not verified for this issue.</p>' : ""}${list}`;
}

function itemLabel(item, prefix) {
  return asArray(item.labels).map((label) => typeof label === "string" ? label : label?.name)
    .find((label) => typeof label === "string" && label.toLowerCase().startsWith(prefix))?.slice(prefix.length);
}

function renderDetailsMetadata(item) {
  const issueUrl = itemUrl(item);
  const repository = typeof item.repository === "string" && /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(item.repository)
    ? item.repository : issueUrl ? new URL(issueUrl).pathname.split("/").slice(1, 3).join("/") : "Unavailable";
  const type = item.type ?? itemLabel(item, "type:") ?? "Unspecified";
  const model = item.model ?? itemLabel(item, "model:");
  const effort = item.effort ?? itemLabel(item, "effort:");
  const route = [model, effort].map((value) => typeof value === "string" && value !== "n/a" ? value : "unconfigured").join(" / ");
  return `<p class="wf-detail-meta">Repository: ${text(repository)} · Type: ${text(type)} · Route: ${text(route)} · Acceptance: ${text(item.acceptance || "Unknown")}</p>`;
}

function renderRow(row, index, options) {
  const { item, projectName: name, workflow } = row;
  const group = GROUPS.some(([key]) => key === workflow.group) ? workflow.group : "stuck";
  const filter = ["chat", "approval", "codex", "deepseek", "blocked", "working", "done"].includes(workflow.filter) ? workflow.filter : "blocked";
  const projectValue = String(row.projectNumber ?? row.project.projectNumber ?? row.projectIndex + 1);
  const status = item.status ?? "Unknown";
  const size = item.size ?? "Unknown";
  const detailId = `wf-detail-${index}`;
  const title = `${item.number ? `#${item.number} ` : ""}${item.title ?? "Untitled issue"}`;
  const search = [title, name, status, size, item.priority, item.workstream, item.type, item.acceptance,
    ...asArray(item.labels), ...row.dependencies.map((dependency) => typeof dependency === "string" ? dependency : dependency.label ?? "")].join(" ").toLowerCase();
  const issueHref = safeWorkflowUrl(asArray(workflow.links).find((link) => link.label === "Issue"));
  const titleMarkup = issueHref
    ? `<a href="${escapeHtml(issueHref)}" target="_blank" rel="noopener noreferrer">${text(title)}</a>`
    : text(title);
  const chips = CHIP_NAMES.map((name) => chipMarkup(name, chipFor(name, asArray(workflow.chips)))).join("");
  const metadata = [
    status && `<span>${text(status)}</span>`,
    item.priority && `<span>${text(item.priority)}</span>`,
    item.size && `<span>Size ${text(item.size)}</span>`,
    item.workstream && `<span>${text(item.workstream)}</span>`,
    `<span>${text(name)}</span>`,
  ].filter(Boolean).join("");
  const disabled = asArray(workflow.disabled);
  const disabledMarkup = disabled.length ? `<ul class="wf-disabled">${disabled.map((reason) => `<li>${text(reason)}</li>`).join("")}</ul>` : '<p class="wf-muted">No disabled actions were reported.</p>';
  const queueLabel = row.queueOrder === null ? "—" : String(row.queueOrder);
  const nextAction = primaryActionMarkup(row, options);
  return `<li class="wf-row g-${group}" data-row-index="${index}" data-queue-order="${row.queueOrder === null ? "" : row.queueOrder}" data-group="${group}" data-filter="${filter}" data-project="${escapeHtml(projectValue)}" data-status="${text(status)}" data-size="${text(size)}" data-dependency="${row.dependenciesVerified === false ? "unverified" : row.dependencies.length ? "has" : row.dependenciesVerified === true ? "none" : "unknown"}" data-search="${text(search)}" data-detail-id="${detailId}">
  <span class="wf-order" title="Canonical Queue Order">${escapeHtml(queueLabel)}</span>
  <div class="wf-row-main"><div class="wf-title">${titleMarkup}</div><div class="wf-next" data-workflow-next="true"><span class="wf-actor">${text(workflow.actor || "Unknown")}</span><span>${text(workflow.action || "Next action unavailable.")}</span></div><div class="wf-meta">${metadata}</div></div>
  <div class="wf-chips" aria-label="Workflow evidence status">${chips}</div>
  <div class="wf-row-action">${nextAction}</div>
  <button type="button" class="wf-expand" data-expand-row data-detail-id="${detailId}" aria-expanded="false" aria-controls="${detailId}"><span>Details</span><span class="wf-chevron" aria-hidden="true"></span></button>
</li>
<li class="wf-detail" id="${detailId}" hidden>${renderDetailsMetadata(item)}<div class="wf-detail-grid"><section><h4>Evidence sources</h4>${renderSources(workflow.sources)}</section><section><h4>Dependencies</h4>${renderDependencies(row)}</section><section><h4>Disabled actions</h4>${disabledMarkup}</section><section><h4>Safe links</h4><div class="wf-links">${renderWorkflowLinks(workflowLinks(row, options))}</div></section></div></li>`;
}

function percent(done, total) {
  return total > 0 ? Math.max(0, Math.min(100, Math.round(done / total * 100))) : 0;
}

function progressStrip(projects, rows, historical) {
  const counts = Object.fromEntries(STATUS_ORDER.map((status) => [status, 0]));
  const total = rows.length + historical.length;
  let done = 0;
  for (const row of rows) {
    const status = row.item.status;
    if (Object.hasOwn(counts, status)) counts[status]++;
    if (status === "Done") done++;
  }
  for (const row of historical) {
    if (Object.hasOwn(counts, row.status)) counts[row.status]++;
    if (row.status === "Done") done++;
  }
  const pct = percent(done, total);
  const segments = STATUS_ORDER.filter((status) => counts[status] > 0).map((status) => `<span class="wf-segment s-${status.toLowerCase().replaceAll(" ", "-")}" style="flex-grow:${counts[status]}" title="${text(status)}: ${counts[status]}"></span>`).join("");
  const projectCounts = new Map(projects.map((project, index) => [String(project.projectNumber ?? index + 1), { name: projectName(project, index), total: 0, done: 0 }]));
  for (const row of rows) {
    const key = String(row.projectNumber ?? row.projectIndex + 1);
    if (!projectCounts.has(key)) projectCounts.set(key, { name: row.projectName, total: 0, done: 0 });
    const counter = projectCounts.get(key);
    counter.total++;
    if (row.item.status === "Done") counter.done++;
  }
  for (const row of historical) {
    const key = String(row.projectNumber);
    if (!projectCounts.has(key)) projectCounts.set(key, { name: row.projectName, total: 0, done: 0 });
    const counter = projectCounts.get(key);
    counter.total++;
    if (row.status === "Done") counter.done++;
  }
  const boards = [...projectCounts.values()].map((board) => `<li><span>${text(board.name)}</span><strong>${board.done} / ${board.total}</strong></li>`).join("");
  return `<section class="wf-card wf-progress" aria-labelledby="wf-progress-title"><h2 id="wf-progress-title">Overall progress</h2><div class="wf-progress-head"><strong>${done} of ${total} work items done</strong><span>${pct}%</span></div><div class="wf-progress-track" role="img" aria-label="${pct}% complete; ${done} of ${total} work items done">${segments}</div><ul class="wf-board-progress">${boards}</ul></section>`;
}

function milestoneStrip(roadmap) {
  const milestones = asArray(roadmap?.milestones);
  const milestone = milestones.find((entry) => Number.isFinite(entry.done) && Number.isFinite(entry.total) && entry.done < entry.total)
    ?? milestones.find((entry) => entry.done == null || entry.total == null);
  if (!milestone) return `<section class="wf-card wf-milestone" aria-labelledby="wf-milestone-title"><h2 id="wf-milestone-title">Next milestone</h2><p class="wf-muted">${milestones.length ? "All recorded program milestones are done." : "Program milestone data is unavailable."}</p></section>`;
  const entries = asArray(milestone.items);
  const done = Number.isFinite(milestone.done) ? milestone.done : null;
  const total = Number.isFinite(milestone.total) ? milestone.total : null;
  const pct = Number.isFinite(milestone.percent) ? Math.max(0, Math.min(100, milestone.percent)) : done !== null && total !== null ? percent(done, total) : null;
  const open = entries.filter((entry) => entry.status !== "Done");
  const itemLabel = (entry) => `${entry.number ? `#${entry.number} ` : ""}${entry.title ?? "Issue title unavailable"}`;
  return `<section class="wf-card wf-milestone" aria-labelledby="wf-milestone-title"><h2 id="wf-milestone-title">Next milestone</h2><strong class="wf-milestone-name">${text(milestone.name || "Program milestone")}</strong>${done !== null && total !== null ? `<div class="wf-milestone-count">${done} of ${total} member issues done</div><div class="wf-progress-track" role="img" aria-label="${pct}% complete"><span class="wf-milestone-fill" style="width:${pct}%"></span></div>` : '<p class="wf-muted">Milestone membership or completion is unknown.</p>'}${entries.length ? `<div class="wf-milestone-open"><strong>${open.length} open member issue${open.length === 1 ? "" : "s"}</strong><ul>${open.slice(0, 3).map((entry) => `<li>${text(itemLabel(entry))}</li>`).join("")}</ul>${open.length > 3 ? `<details><summary>Show all ${open.length} open member issues</summary><ul>${open.slice(3).map((entry) => `<li>${text(itemLabel(entry))}</li>`).join("")}</ul></details>` : ""}</div>` : '<p class="wf-muted">Milestone membership is unavailable.</p>'}</section>`;
}

function shortSha(value) {
  return typeof value === "string" && /^[0-9a-f]{40}$/i.test(value) ? value.slice(0, 7) : value;
}

function ciShaEvidence(entry) {
  const values = [entry?.head && /^[0-9a-f]{40}$/i.test(entry.head) && `head ${entry.head}`, entry?.base && /^[0-9a-f]{40}$/i.test(entry.base) && `base ${entry.base}`].filter(Boolean);
  return values.length ? `<details class="wf-ci-sha"><summary>Full head/base evidence</summary><code>${text(values.join(" · "))}</code></details>` : "";
}

function ciEntry(entry, statusName, expiresAt) {
  const status = statusName ? ` data-workflow-status="${text(statusName)}" data-workflow-expires-at="${expiresAt}"` : "";
  if (typeof entry === "string" || typeof entry === "number") return `<li><span${status}>${text(entry)}</span></li>`;
  if (!entry || typeof entry !== "object") return "";
  const readiness = entry.ready === true ? entry.verified === true ? "Ready to submit" : "Readiness unverified" : "";
  const verification = entry.verified === false ? "Head or base not verified" : "";
  const fields = [entry.pr != null && `PR #${entry.pr}`, entry.phase, readiness, verification, entry.runId != null && `run #${entry.runId}`, entry.head && `head ${shortSha(entry.head)}`, entry.base && `base ${shortSha(entry.base)}`].filter(Boolean);
  return fields.length ? `<li><span${status}>${text(fields.join(" · "))}</span>${ciShaEvidence(entry)}</li>` : "";
}

function ciList(label, entries, className = "", statusName = label.toLowerCase(), expiresAt) {
  if (!entries.length) return "";
  const status = ` data-workflow-status="ciQueue.${text(statusName)}" data-workflow-expires-at="${expiresAt}"`;
  const list = `<ol class="wf-ci-list">${entries.map((entry) => ciEntry(entry, `ciQueue.${statusName}`, expiresAt)).filter(Boolean).join("")}</ol>`;
  return entries.length > 3
    ? `<details class="wf-ci-section ${className}"><summary><span${status}>${text(label)} (${entries.length})</span></summary>${list}</details>`
    : `<div class="wf-ci-section ${className}"><strong><span${status}>${text(label)}</span></strong>${list}</div>`;
}

function otherRunEntry(run, expiresAt) {
  const label = [`Run #${run.id ?? "unknown"}`, run.status ?? "status unknown"].join(" · ");
  const href = safeWorkflowUrl({ url: run.url });
  const link = href
    ? `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer" data-requires-fresh="true" data-workflow-expires-at="${expiresAt}">Open Actions run</a>`
    : '<span class="wf-muted">Actions link unavailable.</span>';
  return `<li><span data-workflow-status="ciQueue.otherRuns" data-workflow-expires-at="${expiresAt}">${text(label)}</span> ${link}</li>`;
}

function sourceIsFresh(snapshotAt, now) {
  const timestamp = snapshotAt instanceof Date ? snapshotAt.getTime() : typeof snapshotAt === "string" ? Date.parse(snapshotAt) : NaN;
  const age = now.getTime() - timestamp;
  return Number.isFinite(timestamp) && age >= 0 && age <= WORKFLOW_FRESHNESS_MS;
}

function sourceExpiresAt(snapshotAt, now) {
  const timestamp = snapshotAt instanceof Date ? snapshotAt.getTime() : typeof snapshotAt === "string" ? Date.parse(snapshotAt) : NaN;
  return Number.isFinite(timestamp) && timestamp <= now.getTime() ? timestamp + WORKFLOW_FRESHNESS_MS : now.getTime() - 1;
}

function ciStrip(workflow, now) {
  const ci = workflow?.ciQueue;
  const queue = ci && typeof ci === "object" ? ci : null;
  const snapshotAt = queue?.snapshotAt ?? queue?.source?.snapshotAt;
  const lastError = queue?.lastError ?? queue?.source?.lastError;
  const snapshotFresh = sourceIsFresh(snapshotAt, now);
  const current = Boolean(queue && !lastError && snapshotFresh);
  const expiresAt = snapshotFresh ? sourceExpiresAt(snapshotAt, now) : null;
  const waiting = current ? asArray(queue.waiting) : [];
  const active = current ? Array.isArray(queue.active) ? queue.active : queue.active ? [queue.active] : [] : [];
  const ready = current ? asArray(queue.ready) : [];
  const delivered = current ? asArray(queue.delivered) : [];
  const readyCount = current && Number.isFinite(queue.ready) ? queue.ready : ready.length;
  const deliveredCount = current && Number.isFinite(queue.delivered) ? queue.delivered : delivered.length;
  const lastDelivered = current ? queue.lastDelivered : null;
  const slot = current ? queue.slot : null;
  const slotUnknown = !current || queue.slotUnknown === true || !slot || slot.phase === "unknown";
  const slotVerified = !slotUnknown && typeof slot === "object";
  const slotIdle = slotVerified && slot.phase === "idle";
  const rawState = typeof queue?.state === "string" ? queue.state : "Unknown";
  const paused = queue?.paused === true || rawState === "failed-paused";
  const state = paused ? "Paused" : current && slotIdle ? "Idle"
    : current && slotVerified && slot.phase === "other-active" ? "Other run active"
      : current && slotVerified && slot.phase === "queue-active" ? rawState === "idle" ? "Queue active" : rawState
        : current && rawState.toLowerCase() !== "idle" ? rawState : "Unknown";
  const expiryAttr = snapshotFresh ? ` data-workflow-expires-at="${expiresAt}"` : "";
  const slotText = slotUnknown ? "Slot unknown"
    : slotIdle ? "Slot idle"
      : slot.phase === "other-active" ? "Other Validate run active"
        : slot.phase === "queue-active" ? text(["Queue active", slot.pr != null && `PR #${slot.pr}`, slot.head && `head ${shortSha(slot.head)}`, slot.base && `base ${shortSha(slot.base)}`].filter(Boolean).join(" · "))
          : "Slot unknown";
  const slotUrl = slotVerified ? safeWorkflowUrl({ url: slot.runUrl ?? slot.url }) : null;
  const slotLink = slotUrl ? ` <a href="${escapeHtml(slotUrl)}" target="_blank" rel="noopener noreferrer" data-requires-fresh="true" data-workflow-expires-at="${expiresAt}">Open Actions run</a>` : "";
  const slotMarkup = `<span data-workflow-status="ciQueue.slot"${expiryAttr}>${slotText}</span>${slot && typeof slot === "object" ? ciShaEvidence(slot) : ""}${slotLink}`;
  const stateMarkup = `<span class="wf-ci-state" data-workflow-status="${text(state)}"${expiryAttr} data-requires-fresh="true">${text(state)}</span>`;
  const controlUrl = safeWorkflowUrl({ url: queue?.url });
  const control = controlUrl && /\/mbelinkie\/vera-script-to-timeline\/issues\/361$/i.test(new URL(controlUrl).pathname)
    ? `<a href="${escapeHtml(controlUrl)}" target="_blank" rel="noopener noreferrer">Queue control issue #361</a>` : "";
  const otherRuns = current ? asArray(queue.otherRuns) : [];
  const otherRunsMarkup = !current || queue.slotUnknown === true
    ? otherRuns.length ? `<details class="wf-ci-section wf-ci-other-runs"><summary><span data-workflow-status="ciQueue.otherRuns"${expiryAttr}>Observed Validate runs (${otherRuns.length})</span></summary><ol class="wf-ci-list">${otherRuns.map((run) => otherRunEntry(run, expiresAt)).join("")}</ol></details>`
      : `<p class="wf-muted"><span data-workflow-status="ciQueue.otherRuns"${expiryAttr}>Validate run inventory unknown.</span></p>`
    : otherRuns.length ? `<details class="wf-ci-section wf-ci-other-runs"><summary><span data-workflow-status="ciQueue.otherRuns"${expiryAttr}>Other Validate runs (${otherRuns.length})</span></summary><ol class="wf-ci-list">${otherRuns.map((run) => otherRunEntry(run, expiresAt)).join("")}</ol></details>`
      : '<p class="wf-muted">No other Validate runs were observed.</p>';
  const pauseMarkup = paused ? '<p class="wf-error">Queue paused by controller.</p>' : "";
  const body = !queue ? `<p class="wf-muted">CI queue source unavailable; slot and queue state are unknown.</p>${otherRunsMarkup}`
    : current ? `<p class="wf-ci-slot">${slotMarkup}</p>${ciList("Active", active, "", "active", expiresAt)}${ciList("Waiting", waiting, "wf-ci-waiting", "waiting", expiresAt)}${readyCount > 0 ? `<p class="wf-ci-count"><span data-workflow-status="ciQueue.ready" data-workflow-expires-at="${expiresAt}">Ready to send: ${readyCount}</span></p>` : ""}${deliveredCount > 0 ? `<p class="wf-ci-count"><span data-workflow-status="ciQueue.delivered" data-workflow-expires-at="${expiresAt}">Verified deliveries: ${deliveredCount}</span></p>` : ""}${ciList("Ready", ready, "", "ready", expiresAt)}${ciList("Delivered", delivered, "", "delivered", expiresAt)}${lastDelivered ? `<div class="wf-ci-section"><strong><span data-workflow-status="ciQueue.lastDelivered" data-workflow-expires-at="${expiresAt}">Last delivered</span></strong><ol class="wf-ci-list">${ciEntry(lastDelivered, "ciQueue.lastDelivered", expiresAt)}</ol></div>` : ""}${otherRunsMarkup}`
      : `<p class="wf-muted">Queue state is unknown; only the last known controller snapshot is shown.</p>${otherRunsMarkup}`;
  return `<section class="wf-card wf-ci" aria-labelledby="wf-ci-title"><h2 id="wf-ci-title">CI queue ${stateMarkup}</h2>${body}${pauseMarkup}${!queue || !current ? `<p class="wf-muted"><span data-workflow-status="ciQueue.slot">Slot unknown</span></p>` : ""}<p class="wf-source-stamp">Controller snapshot: ${formatSnapshot(snapshotAt)}</p>${lastError ? '<p class="wf-error">CI source could not be verified.</p>' : ""}${control ? `<p class="wf-ci-control">${control}</p>` : ""}</section>`;
}

function listMarkup(groupKey, rows, options) {
  return `<ul class="wf-group-rows">${rows.filter((row) => row.workflow.group === groupKey).map((row) => renderRow(row, row.queueIndex, options)).join("")}</ul>`;
}

function optionsMarkup(projects, rows) {
  const options = (values) => [...new Set(values.filter(Boolean).map(String))].sort((a, b) => a.localeCompare(b)).map((value) => `<option value="${escapeHtml(value)}">${text(value)}</option>`).join("");
  const projectOptions = [...new Map(projects.map((project, index) => [String(project.projectNumber ?? index + 1), projectName(project, index)])).entries()]
    .map(([value, label]) => `<option value="${escapeHtml(value)}">${text(label)}</option>`).join("");
  return `<div class="wf-filter-grid"><label>Search<input type="search" data-filter-search placeholder="Issue, board, workstream"></label><label>Project<select data-filter-project><option value="">All projects</option>${projectOptions}</select></label><label>Status<select data-filter-status><option value="">All statuses</option>${options(rows.map((row) => row.item.status))}</select></label><label>Size<select data-filter-size><option value="">All sizes</option>${options(rows.map((row) => row.item.size))}</select></label><label>Dependencies<select data-filter-dependency><option value="">All dependency states</option><option value="has">Has dependencies</option><option value="none">No dependencies</option><option value="unverified">Unverified</option><option value="unknown">Unknown</option></select></label></div>`;
}

function renderRoadmapHealth(roadmap) {
  const warnings = asArray(roadmap?.warnings);
  const errors = asArray(roadmap?.dependencyErrors);
  const unverified = Number.isFinite(roadmap?.unverifiedCount) ? roadmap.unverifiedCount : 0;
  const unqueued = Number.isFinite(roadmap?.unqueuedCount) ? roadmap.unqueuedCount : 0;
  const lines = [
    ...warnings.map((warning) => typeof warning === "object" ? warning.message ?? JSON.stringify(warning) : warning),
    ...errors.map((error) => typeof error === "object" ? error.message ?? JSON.stringify(error) : error),
  ].filter(Boolean);
  return `<details class="wf-roadmap-health"><summary>Roadmap source: ${warnings.length} warning${warnings.length === 1 ? "" : "s"}, ${errors.length} dependency error${errors.length === 1 ? "" : "s"}, ${unverified} unverified, ${unqueued} unqueued</summary>${lines.length ? `<ul>${lines.map((line) => `<li>${text(line)}</li>`).join("")}</ul>` : '<p class="wf-muted">No roadmap warnings or dependency errors were reported.</p>'}</details>`;
}

export function renderWorkflowQueue(projects, options = {}) {
  const models = Array.isArray(projects) ? projects : [projects];
  const suppliedTime = new Date(options.generatedAt ?? options.workflow?.snapshotAt ?? 0);
  const now = Number.isFinite(suppliedTime.getTime()) ? suppliedTime : new Date(0);
  const roadmap = options.roadmap ?? {};
  const workflow = options.workflow ?? {};
  const roadmapQueue = asArray(roadmap.queue);
  const { rows, historical } = flattenProjects(models, roadmapQueue, now, workflow);
  for (const [queueIndex, row] of rows.entries()) {
    row.queueIndex = queueIndex;
    row.workflow = { ...row.workflow, group: GROUPS.some(([key]) => key === row.workflow.group) ? row.workflow.group : "stuck" };
  }
  const expiresAt = workflowExpiresAt(models, workflow, now);
  const initiallyStale = expiresAt < now.getTime();
  const groups = GROUPS.map(([key, label, hint]) => `<section class="wf-group grp-${key}" data-queue-group="${key}" aria-labelledby="wf-group-${key}"><h3 id="wf-group-${key}"><span class="wf-group-dot" aria-hidden="true"></span>${label}<b data-group-count>${rows.filter((row) => row.workflow.group === key).length}</b><span class="wf-group-hint">${hint}</span></h3>${listMarkup(key, rows, options)}</section>`).join("");
  const actorFilters = [["chat", "Chat can advance"], ["codex", "Codex ready"], ["approval", "My approval"], ["deepseek", "DeepSeek"], ["blocked", "Blocked"], ["all", "All"]]
    .map(([key, label]) => `<button type="button" data-actor-filter="${key}" aria-pressed="${key === "all"}">${label}<span>${key === "all" ? rows.length : rows.filter((row) => row.workflow.filter === key).length}</span></button>`).join("");
  const snapshot = `<div class="wf-source-health"><span>Workflow snapshot: ${formatSnapshot(workflow.snapshotAt)}</span>${workflow.lastError ? `<span class="wf-error">Refresh error: ${text(workflow.lastError)}</span>` : ""}</div>`;
  return `<div class="workflow-queue" data-workflow-queue data-workflow-expires-at="${expiresAt}"${initiallyStale ? ' data-stale="true"' : ""}>
  <div class="wf-topstrip">${progressStrip(models, rows, historical)}${milestoneStrip(roadmap)}${ciStrip(workflow, now)}</div>
  ${staleNotice(models, workflow, rows)}${snapshot}${renderRoadmapHealth(roadmap)}
  <section class="wf-queue" aria-labelledby="wf-queue-title"><div class="wf-queue-head"><div><h2 id="wf-queue-title">What's next</h2><p>Project issues in canonical Queue Order; unqueued issues follow ranked work.</p></div><div class="wf-mode"><button type="button" data-queue-mode="groups" aria-pressed="true">By next step</button><button type="button" data-queue-mode="flat" aria-pressed="false">Queue order</button></div></div>
    <div class="wf-actor-filters" role="group" aria-label="Filter by next actor">${actorFilters}</div>
    ${optionsMarkup(models, rows)}
    <div class="wf-group-list">${groups}</div>
    <ul class="wf-flat-rows" data-flat-rows hidden></ul>
    <p class="wf-no-results" data-empty-results hidden>No work items match these filters.</p>
  </section>
</div>`;
}
