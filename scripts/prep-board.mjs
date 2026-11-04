#!/usr/bin/env node
// VERA prep board: the pre-Codex pipeline for both repositories.
//   npm run prep              start (or reuse) the local board and open it
//   npm run prep -- --no-open
//   npm run prep -- --next    print the next prepped ticket for Codex/Claude and exit
// Stages: To groom -> DeepSeek running -> Ready for Codex / Needs a look, plus
// "Not ready" (dependencies open, design work, already owned...) with no buttons.
// A "Your next step" panel names the one thing to do now, and while the board
// runs it checks every 5 minutes and pops a Mac notification when a run ends.
// Read-only: reads GitHub through the local `gh` CLI. DeepSeek is only ever
// launched by the ChatGPT grooming chat, after it has prepared a brief.
import { execFile } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import path from "node:path";
import { fileURLToPath, URL } from "node:url";
import { setInterval } from "node:timers";
import { promisify } from "node:util";

import { buildSharedRoadmap, fetchNativeDependencies, loadProgressModel } from "./project-progress-lib.mjs";

const run = promisify(execFile);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PORT = Number(process.env.VERA_PREP_PORT ?? 51750);
const REFRESH_MS = 3 * 60_000;
const DEPENDENCY_TTL_MS = 10 * 60_000;
const WATCH_MS = 5 * 60_000;
const PIPELINE_DEPTH = 3; // keep about this many tickets prepped or in flight ahead of Codex
const STATE_FILE = path.join(ROOT, "out", "prep-board-state.json");
const OWNER = "mbelinkie";

export const REPOS = {
  "vera-script-to-timeline": { short: "timeline", name: "Timeline" },
  "vera-research-video-clips": { short: "research", name: "Research" },
};
// Only code tickets go to DeepSeek; design, investigation, review, acceptance and goal tickets don't.
export const GROOM_TYPES = new Set(["implementation", "bug"]);
export const EXCLUDE_LABELS = new Set(["deepseek-excluded"]);
const BUSY = new Set(["In progress", "In review"]);

function locate(url) {
  const match = /^https:\/\/github\.com\/([^/]+)\/([^/]+)\/issues\/(\d+)/i.exec(url ?? "");
  return match && match[1].toLowerCase() === OWNER && REPOS[match[2]] ? { repo: match[2], number: Number(match[3]) } : null;
}

const shortRef = (label) => label
  .replace("vera-script-to-timeline#", "Timeline #")
  .replace("vera-research-video-clips#", "Research #");

export function deepseekState(labels = []) {
  const set = new Set(labels);
  if (set.has("deepseek-running")) return "running";
  if (set.has("deepseek") || set.has("deepseek-pro")) return "queued";
  if (set.has("deepseek-done") || set.has("codex-prepped")) return "ready";
  if (set.has("deepseek-failed")) return "failed";
  return "none";
}

// Why an issue can't be groomed and coded right now (empty list = groomable).
export function notReadyReasons(item) {
  const reasons = [];
  if (BUSY.has(item.status)) reasons.push(`Already ${item.status.toLowerCase()}`);
  if (item.status === "Blocked") reasons.push("Marked Blocked");
  if (!GROOM_TYPES.has(item.type)) reasons.push(`type:${item.type} isn't code work`);
  if (item.queueOrder === null) reasons.push("Not in Queue Order");
  else if (!item.dependenciesVerified) reasons.push("Dependencies not verified");
  const open = (item.dependencies ?? []).filter((dependency) => dependency.isOpen);
  if (open.length) reasons.push(`Waiting on ${open.map((dependency) => shortRef(dependency.label)).join(", ")}`);
  return reasons;
}

// Which prep a ticket gets: DeepSeek (Chat brief + DeepSeek draft) or, for
// deepseek-excluded tickets such as real-Resolve work, a Chat brief for Codex.
export function prepPath(labels = []) {
  return labels.some((label) => EXCLUDE_LABELS.has(label)) ? "codex" : "deepseek";
}

export function stageOf(row) {
  if (row.deepseek === "running" || row.deepseek === "queued") return "running";
  if (row.deepseek === "ready") return "ready";
  if (row.deepseek === "failed") return "failed";
  return row.reasons.length ? "blocked" : "groom";
}

const PRIORITY = { P0: 0, P1: 1, P2: 2, P3: 3, P4: 4 };
export function compareRows(a, b) {
  return (a.queueOrder ?? Infinity) - (b.queueOrder ?? Infinity)
    || (PRIORITY[a.priority] ?? 9) - (PRIORITY[b.priority] ?? 9)
    || a.repo.localeCompare(b.repo)
    || a.number - b.number;
}

export function prsByIssue(repo, pulls) {
  const map = new Map();
  for (const pr of pulls) {
    const match = /^deepseek\/issue-(\d+)-(\d+)$/.exec(pr.headRefName ?? "");
    if (!match) continue;
    const key = `${repo}#${match[1]}`;
    const previous = map.get(key);
    if (!previous || Number(match[2]) > previous.runId) map.set(key, { url: pr.url, number: pr.number, runId: Number(match[2]) });
  }
  return map;
}

export function chatPrompt(template, row) {
  return template
    .replaceAll("{{ISSUE_URL}}", row.url)
    .replaceAll("{{REPO}}", `${OWNER}/${row.repo}`)
    .replaceAll("{{SHORT_REPO}}", REPOS[row.repo].short)
    .replaceAll("{{NUMBER}}", String(row.number))
    .trim();
}

export function codexPrompt(row) {
  if (row.prep === "codex-brief") {
    return `Work on issue ${row.url}. Start from the "Codex prep brief" comment on the issue (written by ChatGPT): use its code map and plan to skip exploration, but verify against the real code before relying on it. Implement, verify and deliver it normally per AGENTS.md.`;
  }
  return `Review and finish DeepSeek's draft for issue ${row.url}${row.pr ? ` (draft PR ${row.pr.url})` : " (its result comment links the pushed branch)"}. Treat it as an unreviewed starting point: check its notes, verify the work against the issue and the repository rules in AGENTS.md, fix what's wrong, finish what's missing, and deliver it normally.`;
}

// Pure assembly of the board from Project models, dependency data and open PRs.
export function buildBoard(models, dependencies, pulls, templates = {}) {
  if (typeof templates === "string") templates = { deepseek: templates };
  const roadmap = buildSharedRoadmap(models, dependencies);
  const prs = new Map();
  for (const [repo, list] of Object.entries(pulls)) for (const [key, pr] of prsByIssue(repo, list)) prs.set(key, pr);
  const items = new Map(roadmap.queue.map((item) => [item.key, item]));
  for (const model of models) {
    for (const item of model.workItems ?? []) {
      const key = String(item.url ?? "").toLowerCase();
      if (!key || items.has(key) || item.type === "historical") continue;
      items.set(key, { ...item, key, queueOrder: null, dependencies: [], dependenciesVerified: false });
    }
  }
  const rows = [];
  for (const item of items.values()) {
    const location = locate(item.url);
    if (!location || item.status === "Done" || item.type === "goal" || item.type === "operations-control") continue;
    const labels = item.labels ?? [];
    const row = {
      key: `${location.repo}#${location.number}`,
      repo: location.repo,
      repoName: REPOS[location.repo].name,
      number: location.number,
      title: item.title,
      url: item.url,
      status: item.status,
      type: item.type,
      priority: item.priority,
      size: item.size,
      milestone: item.programMilestone ?? null,
      queueOrder: item.queueOrder,
      labels,
      deepseek: deepseekState(labels),
      path: prepPath(labels),
      prep: labels.includes("codex-prepped") ? "codex-brief" : labels.includes("deepseek-done") ? "deepseek" : null,
      pr: prs.get(`${location.repo}#${location.number}`) ?? null,
      reasons: notReadyReasons({ ...item, labels }),
    };
    row.stage = stageOf(row);
    row.canGroom = row.reasons.length === 0 && (row.stage === "groom" || row.stage === "failed");
    const template = templates[row.path];
    if (row.canGroom && template) row.chatPrompt = chatPrompt(template, row);
    if (row.stage === "ready") row.codexPrompt = codexPrompt(row);
    rows.push(row);
  }
  rows.sort(compareRows);

  const projects = models.map((model) => ({
    name: /research/i.test(model.projectTitle ?? "") ? "Research" : "Timeline",
    done: model.doneCount,
    total: model.totalWork,
    productionLines: model.codeStats?.production ?? null,
    codeHint: model.codeStatsError ?? null,
  }));
  const done = projects.reduce((sum, p) => sum + p.done, 0);
  const total = projects.reduce((sum, p) => sum + p.total, 0);
  const next = roadmap.milestones.find((milestone) => milestone.done < milestone.total) ?? null;
  return {
    rows,
    summary: {
      done,
      total,
      percent: total ? Math.round((100 * done) / total) : 0,
      projects,
      productionLines: projects.every((p) => p.productionLines === null) ? null : projects.reduce((sum, p) => sum + (p.productionLines ?? 0), 0),
      nextMilestone: next && { name: next.name, done: next.done, total: next.total, left: next.total - next.done },
      milestones: roadmap.milestones.map((milestone) => ({ name: milestone.name, done: milestone.done, total: milestone.total })),
    },
    nextPrepped: nextPrepped(rows),
    nextStep: nextStep(rows),
    dependencyErrors: roadmap.dependencyErrors,
  };
}

// "The next prepped ticket": highest-priority open issue with a finished DeepSeek
// draft (label deepseek-done) that nobody is working on yet.
export function nextPrepped(rows) {
  const row = rows.find((candidate) => candidate.stage === "ready" && !BUSY.has(candidate.status)
    && !(candidate.reasons ?? []).some((reason) => reason.startsWith("Waiting on")));
  return row ? { key: row.key, repo: row.repo, number: row.number, title: row.title, url: row.url, pr: row.pr, prep: row.prep, queueOrder: row.queueOrder } : null;
}

const repoName = (row) => REPOS[row.repo]?.name ?? row.repo;
const brief = (row) => ({ key: row.key, repo: row.repo, number: row.number, title: row.title, url: row.url, pr: row.pr ?? null });

// The one thing Matthew should do next, in priority order: hand a finished
// draft to Codex, look at a failed run, keep the pipeline topped up, or wait.
export function nextStep(rows) {
  const prepped = nextPrepped(rows);
  if (prepped) {
    return { kind: "codex", row: prepped, title: `Hand ${repoName(prepped)} #${prepped.number} to Codex`,
      detail: `${prepped.prep === "codex-brief" ? "ChatGPT posted a Codex brief" : "DeepSeek finished a draft"}. Tell Codex "work on the next prepped ticket", or click Open in Codex.` };
  }
  const failed = rows.find((row) => row.stage === "failed");
  if (failed) {
    return { kind: "failed", row: brief(failed), title: `DeepSeek couldn't finish ${repoName(failed)} #${failed.number}`,
      detail: "Read its note on the issue. If it looks worth another try, groom it again in ChatGPT; otherwise leave it for Codex." };
  }
  const inFlight = rows.filter((row) => row.stage === "running").length;
  const groom = rows.find((row) => row.stage === "groom" && row.canGroom);
  if (groom && inFlight < PIPELINE_DEPTH) {
    return { kind: "groom", row: brief(groom), title: `${groom.path === "codex" ? "Prep" : "Groom"} ${repoName(groom)} #${groom.number} in ChatGPT${groom.path === "codex" ? " for Codex" : ""}`,
      detail: inFlight ? `${inFlight} DeepSeek job${inFlight === 1 ? " is" : "s are"} already running. Prepping one more keeps Codex fed.` : "Nothing is being prepped. Start the next ticket in priority order." };
  }
  if (inFlight) {
    return { kind: "wait", row: null, title: `DeepSeek is working on ${inFlight} ticket${inFlight === 1 ? "" : "s"}`,
      detail: "Nothing to do. You'll get a Mac notification when a draft is ready or a run fails." };
  }
  return { kind: "idle", row: null, title: "Nothing to prep right now",
    detail: "Every open ticket is blocked, in progress, or not DeepSeek work. See the Not ready tab." };
}

// Tickets whose DeepSeek run just finished or failed since the last look.
export function finishedSince(previous, rows) {
  if (!previous) return [];
  return rows.filter((row) => (row.stage === "ready" || row.stage === "failed") && previous[row.key] && previous[row.key] !== row.stage);
}

async function notifyMac(title, message) {
  if (process.platform !== "darwin") {
    console.log(`[notify] ${title}: ${message}`);
    return;
  }
  const script = "on run argv\n display notification (item 2 of argv) with title (item 1 of argv) sound name \"Glass\"\nend run";
  await run("osascript", ["-e", script, title, message]).catch(() => {});
}

async function readState() {
  try { return JSON.parse(await readFile(STATE_FILE, "utf8")); } catch { return null; }
}

async function announce(rows) {
  const previous = await readState();
  for (const row of finishedSince(previous, rows)) {
    const label = `${repoName(row)} #${row.number}`;
    await notifyMac(
      row.stage === "ready" ? "DeepSeek draft ready" : "DeepSeek run needs a look",
      row.stage === "ready" ? `${label} is ready for Codex: ${row.title}` : `${label} didn't finish: ${row.title}`,
    );
  }
  await mkdir(path.dirname(STATE_FILE), { recursive: true });
  await writeFile(STATE_FILE, JSON.stringify(Object.fromEntries(rows.map((row) => [row.key, row.stage]))));
}

async function gh(args) {
  const { stdout } = await run("gh", args, { cwd: ROOT, maxBuffer: 32 * 1024 * 1024 });
  return JSON.parse(stdout);
}

let dependencyCache = null;
async function loadBoard({ forceDependencies = false } = {}) {
  const config = JSON.parse(await readFile(path.join(ROOT, ".github", "vera-roadmap.json"), "utf8"));
  const templates = {
    deepseek: await readFile(path.join(ROOT, ".github", "deepseek", "chat-prompt.md"), "utf8"),
    codex: await readFile(path.join(ROOT, ".github", "deepseek", "codex-prompt.md"), "utf8"),
  };
  const errors = [];
  const models = await Promise.all((config.progressProjects ?? [config]).map((projectConfig) =>
    loadProgressModel(ROOT, { projectConfig })));
  if (forceDependencies || !dependencyCache || Date.now() - dependencyCache.at > DEPENDENCY_TTL_MS) {
    dependencyCache = { at: Date.now(), value: await fetchNativeDependencies(ROOT, models) };
  }
  const pulls = {};
  await Promise.all(Object.keys(REPOS).map(async (repo) => {
    try {
      pulls[repo] = await gh(["pr", "list", "-R", `${OWNER}/${repo}`, "--state", "open", "--limit", "200", "--json", "number,url,headRefName"]);
    } catch (error) {
      pulls[repo] = [];
      errors.push(`${REPOS[repo].name} PRs: ${String(error?.stderr || error?.message || error).trim().slice(0, 200)}`);
    }
  }));
  const board = buildBoard(models, dependencyCache.value, pulls, templates);
  if (board.dependencyErrors.length) errors.push(`${board.dependencyErrors.length} dependency checks failed; those issues show as not verified.`);
  return { ...board, errors, at: new Date().toISOString() };
}

function page() {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VERA prep board</title><style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#1d2330;--mute:#677085;--line:#e2e5eb;--blue:#1f6feb;--green:#1a7f37;--amber:#9a6700;--red:#cf222e;--violet:#8250df;--track:#e8ebf0}
@media (prefers-color-scheme:dark){:root{--bg:#0f1218;--card:#171b23;--ink:#e6e9ef;--mute:#98a1b3;--line:#2a303c;--track:#232834}}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink)}
header{display:flex;gap:16px;align-items:center;padding:14px 24px;border-bottom:1px solid var(--line);background:var(--card);position:sticky;top:0;z-index:2;flex-wrap:wrap}
h1{font-size:18px;margin:0}.meta{color:var(--mute);font-size:12px}.spacer{flex:1}
button,.btn{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:7px;padding:5px 10px;cursor:pointer;text-decoration:none;white-space:nowrap;display:inline-block}
button:hover,.btn:hover{border-color:var(--blue)}.primary{background:var(--blue);border-color:var(--blue);color:#fff}
main{padding:16px 24px 48px;max-width:1200px;margin:0 auto}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin-bottom:14px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px}.stat b{font-size:22px;font-variant-numeric:tabular-nums}.stat small{display:block;color:var(--mute)}
.bar{height:6px;background:var(--track);border-radius:3px;margin-top:6px;overflow:hidden}.bar i{display:block;height:100%;background:var(--green)}
.next{background:var(--card);border:2px solid var(--blue);border-radius:10px;padding:12px 16px;margin-bottom:14px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.next.k-codex{border-color:var(--green)}.next.k-failed{border-color:var(--red)}.next.k-wait,.next.k-idle{border-color:var(--line)}
.next .lead{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--mute)}.next b{font-size:16px}.next small{display:block;color:var(--mute)}
.tabs{display:flex;gap:8px;margin:0 0 12px;flex-wrap:wrap}.tabs button[aria-pressed=true]{border-color:var(--blue);color:var(--blue);font-weight:600}
.filters{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;align-items:center}input,select{font:inherit;padding:5px 8px;border:1px solid var(--line);border-radius:7px;background:var(--card);color:var(--ink)}
ol{list-style:none;margin:0;padding:0;display:grid;gap:8px}
li{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;display:grid;grid-template-columns:28px 1fr auto;gap:10px;align-items:center}
.q{color:var(--mute);font-variant-numeric:tabular-nums;text-align:right}.t a{color:var(--ink);font-weight:600;text-decoration:none}.t a:hover{text-decoration:underline}
.chips{display:flex;gap:6px;margin-top:3px;flex-wrap:wrap}.chip{font-size:11px;color:var(--mute);border:1px solid var(--line);border-radius:999px;padding:0 7px}
.s-running{color:var(--amber);border-color:var(--amber)}.s-ready{color:var(--green);border-color:var(--green)}.s-failed,.why{color:var(--red);border-color:var(--red)}.s-opened{color:var(--violet);border-color:var(--violet)}
.acts{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}.err{background:#fff1f0;color:var(--red);border:1px solid var(--red);padding:8px 12px;border-radius:8px;margin-bottom:12px}
.empty{color:var(--mute);padding:24px;text-align:center}.toast{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);background:var(--ink);color:var(--bg);padding:8px 14px;border-radius:8px;opacity:0;transition:opacity .2s}.toast.on{opacity:.95}
</style></head><body>
<header><h1>VERA prep board</h1><span class="meta" id="meta">Loading…</span><span class="spacer"></span>
<button id="refresh">Refresh</button></header>
<main><div id="errors"></div><div class="stats" id="stats"></div><div id="next"></div>
<div class="tabs" id="tabs"></div>
<div class="filters"><input id="search" placeholder="Search title or #" size="26"><select id="repo"><option value="">Both repos</option><option value="vera-script-to-timeline">Timeline</option><option value="vera-research-video-clips">Research</option></select>
<select id="milestone"><option value="">All milestones</option></select></div>
<ol id="list"></ol></main><div class="toast" id="toast"></div>
<script>
const STAGES=[["groom","To groom"],["running","DeepSeek running"],["ready","Ready for Codex"],["failed","Needs a look"],["blocked","Not ready"],["all","All open"]];
const opened=JSON.parse((()=>{try{return localStorage.getItem("vera-prep-opened")||"{}"}catch{return"{}"}})());
let data={rows:[],errors:[],summary:null},stage="groom";
const $=(id)=>document.getElementById(id);
const esc=(s)=>String(s??"").replace(/[&<>"']/g,(c)=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
const num=(n)=>Number(n).toLocaleString("en-US");
function toast(msg){const t=$("toast");t.textContent=msg;t.classList.add("on");setTimeout(()=>t.classList.remove("on"),2600)}
function saveOpened(){try{localStorage.setItem("vera-prep-opened",JSON.stringify(opened))}catch{}}
function ago(ts){const m=Math.round((Date.now()-ts)/60000);return m<60?m+"m ago":Math.round(m/60)+"h ago"}
async function load(force){$("meta").textContent="Refreshing…";const r=await fetch("/api/board"+(force?"?force=1":""));data=await r.json();render()}
function stats(){
  const s=data.summary;if(!s){$("stats").innerHTML="";return}
  const proj=s.projects.map((p)=>esc(p.name)+" "+p.done+"/"+p.total).join(" · ");
  const lines=s.productionLines===null?"—":num(s.productionLines);
  const lineNote=s.projects.map((p)=>esc(p.name)+" "+(p.productionLines===null?"n/a":num(p.productionLines))).join(" · ");
  const hint=s.projects.find((p)=>p.productionLines===null&&p.codeHint);
  const m=s.nextMilestone;
  $("stats").innerHTML='<div class="stat"><small>Overall progress</small><b>'+s.percent+'%</b> <span class="meta">'+s.done+' of '+s.total+' work items</span><div class="bar"><i style="width:'+s.percent+'%"></i></div><small>'+proj+'</small></div>'
    +'<div class="stat"><small>Lines of production code</small><b>'+lines+'</b><small title="'+esc(hint?hint.codeHint:"")+'">'+lineNote+'</small></div>'
    +'<div class="stat"><small>Next milestone</small>'+(m?'<b style="font-size:16px">'+esc(m.name)+'</b><div class="bar"><i style="width:'+Math.round(100*m.done/m.total)+'%"></i></div><small>'+m.left+' of '+m.total+' stories left</small>':'<b>All done</b>')+'</div>';
  const sel=$("milestone"),cur=sel.value;sel.innerHTML='<option value="">All milestones</option>'+s.milestones.filter((x)=>x.done<x.total).map((x)=>'<option value="'+esc(x.name)+'">'+esc(x.name)+' ('+(x.total-x.done)+' left)</option>').join("")+'<option value="__none">No milestone</option>';sel.value=cur;
}
function nextBox(){
  const n=data.nextStep;if(!n){$("next").innerHTML="";return}
  const r=n.row;let acts="";
  if(n.kind==="codex"&&r){acts=(r.pr?'<a class="btn" href="'+esc(r.pr.url)+'" target="_blank" rel="noopener">See draft PR</a>':'<a class="btn" href="'+esc(r.url)+'" target="_blank" rel="noopener">'+(r.prep==="codex-brief"?"See brief":"See result")+'</a>')+'<button data-copy="Work on the next prepped ticket.">Copy “work on the next prepped ticket”</button><button class="primary" data-act="codex" data-key="'+esc(r.key)+'">Open in Codex</button>'}
  if(n.kind==="failed"&&r)acts='<a class="btn primary" href="'+esc(r.url)+'" target="_blank" rel="noopener">Read why</a>';
  if(n.kind==="groom"&&r)acts='<button class="primary" data-act="chat" data-key="'+esc(r.key)+'">Groom in ChatGPT</button>';
  $("next").innerHTML='<div class="next k-'+n.kind+'"><div><div class="lead">Your next step</div><b>'+esc(n.title)+'</b>'+(r?' <span class="meta">'+esc(r.title)+'</span>':'')+'<small>'+esc(n.detail)+'</small></div><span class="spacer"></span>'+acts+'</div>';
  const waiting=data.rows.filter((x)=>x.stage==="failed").length+(data.nextPrepped?1:0);
  document.title=(waiting?"("+waiting+") ":"")+"VERA prep board";
}
function render(){
  $("errors").innerHTML=data.errors.map((e)=>'<div class="err">'+esc(e)+'</div>').join("");
  $("meta").textContent="Updated "+new Date(data.at).toLocaleTimeString()+" · refreshes every 3 min";
  stats();nextBox();
  const counts=Object.fromEntries(STAGES.map(([k])=>[k,k==="all"?data.rows.length:data.rows.filter((r)=>r.stage===k).length]));
  $("tabs").innerHTML=STAGES.map(([k,n])=>'<button data-stage="'+k+'" aria-pressed="'+(k===stage)+'">'+n+' ('+counts[k]+')</button>').join("");
  const q=$("search").value.trim().toLowerCase(),repo=$("repo").value,ms=$("milestone").value;
  const rows=data.rows.filter((r)=>(stage==="all"||r.stage===stage)&&(!repo||r.repo===repo)&&(!ms||(ms==="__none"?!r.milestone:r.milestone===ms))&&(!q||(r.title+" #"+r.number).toLowerCase().includes(q)));
  $("list").innerHTML=rows.length?rows.map(row).join(""):'<li class="empty" style="display:block">Nothing here.</li>';
}
function row(r){
  const o=opened[r.key];
  const chips=['<span class="chip">'+esc(r.repoName)+'</span>','<span class="chip">'+esc(r.status)+'</span>','<span class="chip">'+esc(r.type)+'</span>',r.priority&&'<span class="chip">'+esc(r.priority)+'</span>',r.size&&'<span class="chip">Size '+esc(r.size)+'</span>',r.milestone&&'<span class="chip">'+esc(r.milestone)+'</span>',
    r.path==="codex"&&'<span class="chip">Codex only</span>',
    r.prep==="codex-brief"&&'<span class="chip s-ready">Codex brief ready</span>',
    r.deepseek!=="none"&&r.prep!=="codex-brief"&&'<span class="chip s-'+(r.deepseek==="queued"?"running":r.deepseek)+'">DeepSeek '+esc(r.deepseek)+'</span>',
    o&&r.stage==="groom"&&'<span class="chip s-opened">Chat opened '+ago(o)+'</span>',
    ...(r.stage==="blocked"?r.reasons.map((x)=>'<span class="chip why">'+esc(x)+'</span>'):[])].filter(Boolean).join("");
  let acts="";
  if(r.canGroom) acts+=r.path==="codex"
    ?'<button class="primary" data-act="chat" data-key="'+esc(r.key)+'" title="Opens ChatGPT with the Codex prep prompt (also copied). Chat maps the code, plans the work and posts a brief for Codex. No DeepSeek.">Prep for Codex in ChatGPT</button>'
    :'<button class="primary" data-act="chat" data-key="'+esc(r.key)+'" title="Opens ChatGPT with the grooming prompt (also copied). Chat works out the change, writes draft code, and launches DeepSeek.">Groom in ChatGPT</button>';
  if(r.stage==="running") acts+='<a class="btn" href="'+esc(r.url)+'" target="_blank" rel="noopener">Watch on issue</a>';
  if(r.stage==="ready"&&!r.pr) acts+=r.prep==="codex-brief"
    ?'<a class="btn" href="'+esc(r.url)+'" target="_blank" rel="noopener" title="ChatGPT&#39;s Codex prep brief is a comment on the issue">See brief</a>'
    :'<a class="btn" href="'+esc(r.url)+'" target="_blank" rel="noopener" title="The result comment links to the pushed branch">Open result on issue</a>';
  if(r.pr) acts+='<a class="btn" href="'+esc(r.pr.url)+'" target="_blank" rel="noopener">Draft PR #'+r.pr.number+'</a>';
  if(r.stage==="ready") acts+='<button data-act="codex" data-key="'+esc(r.key)+'" title="Opens Codex with a review-and-finish prompt (also copied)">Open in Codex</button>';
  return '<li><span class="q">'+(r.queueOrder??"")+'</span><div class="t"><a href="'+esc(r.url)+'" target="_blank" rel="noopener">#'+r.number+' '+esc(r.title)+'</a><div class="chips">'+chips+'</div></div><div class="acts">'+acts+'</div></li>';
}
async function copy(text){try{await navigator.clipboard.writeText(text);return true}catch{return false}}
document.addEventListener("click",async(e)=>{
  const t=e.target.closest("[data-stage],[data-act],[data-copy]");if(!t)return;
  if(t.dataset.copy){await copy(t.dataset.copy);toast("Copied. Paste it to Codex or Claude.");return}
  if(t.dataset.stage){stage=t.dataset.stage;render();return}
  const r=data.rows.find((x)=>x.key===t.dataset.key);if(!r)return;
  if(t.dataset.act==="chat"){window.open("https://chatgpt.com/?q="+encodeURIComponent(r.chatPrompt),"_blank","noopener");await copy(r.chatPrompt);opened[r.key]=Date.now();saveOpened();render();toast("ChatGPT opened. Prompt also copied, if you'd rather paste it into the desktop app.")}
  if(t.dataset.act==="codex"){await copy(r.codexPrompt);location.href="codex://new?prompt="+encodeURIComponent(r.codexPrompt)+"&originUrl="+encodeURIComponent("https://github.com/mbelinkie/"+r.repo+".git");toast("Codex prompt copied.")}
});
$("refresh").onclick=()=>load(true);["search","repo","milestone"].forEach((id)=>$(id).addEventListener("input",render));
load(false);setInterval(()=>{if(!document.hidden)load(false)},${REFRESH_MS});
</script></body></html>`;
}

export async function startServer({ port = PORT, open = true } = {}) {
  let cache = null;
  let pending = null;
  const board = async (force) => {
    if (!force && cache && Date.now() - Date.parse(cache.at) < 60_000) return cache;
    pending ??= loadBoard({ forceDependencies: force })
      .then(async (value) => {
        cache = value;
        await announce(value.rows).catch(() => {});
        return value;
      })
      .finally(() => (pending = null));
    return pending;
  };
  // Keep watching while the board runs, so a finished DeepSeek job pops a Mac
  // notification even when the browser tab is closed or in the background.
  board(false).catch(() => {});
  setInterval(() => board(false).catch(() => {}), WATCH_MS);
  const server = createServer(async (req, res) => {
    const url = new URL(req.url, `http://127.0.0.1:${port}`);
    const send = (status, body, type = "application/json") => {
      res.writeHead(status, { "content-type": type, "cache-control": "no-store", "x-content-type-options": "nosniff" });
      res.end(type === "application/json" ? JSON.stringify(body) : body);
    };
    try {
      if (req.method === "GET" && url.pathname === "/") return send(200, page(), "text/html; charset=utf-8");
      if (req.method === "GET" && url.pathname === "/api/board") return send(200, await board(url.searchParams.has("force")));
      if (req.method === "GET" && url.pathname === "/status") return send(200, { service: "vera-prep-board" });
      return send(404, { error: "Not found" });
    } catch (error) {
      return send(500, { ok: false, error: String(error?.stderr || error?.message || error).slice(0, 300) });
    }
  });
  const url = `http://127.0.0.1:${port}/`;
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", resolve);
  }).catch(async (error) => {
    if (error.code !== "EADDRINUSE") throw error;
    console.log(`Prep board already running at ${url}`);
    if (open) await run("open", [url]).catch(() => {});
    process.exit(0);
  });
  console.log(`VERA prep board: ${url}  (Ctrl+C to stop)`);
  if (open) run(process.platform === "darwin" ? "open" : "xdg-open", [url]).catch(() => {});
  return server;
}

async function printNext() {
  const board = await loadBoard();
  const next = board.nextPrepped;
  if (!next) {
    console.log("No prepped ticket is waiting. (Prepped = open issue labelled deepseek-done that nobody has started.)");
    return;
  }
  console.log(JSON.stringify({ ...next, instructions: codexPrompt(next) }, null, 2));
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const action = process.argv.includes("--next") ? printNext() : startServer({ open: !process.argv.includes("--no-open") });
  action.catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
}
