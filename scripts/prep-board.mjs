#!/usr/bin/env node
// VERA prep board: the pre-Codex pipeline for both repositories.
//   npm run prep            start (or reuse) the local board and open it
//   npm run prep -- --no-open
// Stages: To groom -> DeepSeek running -> Ready for Codex (draft PR) / Needs a look.
// Reads GitHub through the local `gh` CLI. The only write is adding a
// `deepseek`/`deepseek-pro` label when you click a launch button.
import { execFile } from "node:child_process";
import { randomBytes } from "node:crypto";
import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import path from "node:path";
import { fileURLToPath, URL } from "node:url";
import { promisify } from "node:util";

const run = promisify(execFile);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PORT = Number(process.env.VERA_PREP_PORT ?? 51750);
const REFRESH_MS = 3 * 60_000;

export const REPOS = {
  "vera-script-to-timeline": { short: "timeline", name: "Timeline", project: 2 },
  "vera-research-video-clips": { short: "research", name: "Research", project: 1 },
};
const OWNER = "mbelinkie";

function field(item, name) {
  const want = name.toLowerCase().replace(/[^a-z0-9]/g, "");
  const key = Object.keys(item).find((k) => k.toLowerCase().replace(/[^a-z0-9]/g, "") === want);
  const raw = key === undefined ? null : item[key];
  return raw && typeof raw === "object" ? raw.name ?? raw.number ?? raw.value ?? null : raw;
}

export function deepseekState(labels = []) {
  const set = new Set(labels);
  if (set.has("deepseek-running")) return "running";
  if (set.has("deepseek") || set.has("deepseek-pro")) return "queued";
  if (set.has("deepseek-done")) return "ready";
  if (set.has("deepseek-failed")) return "failed";
  return "none";
}

export function stageOf(row) {
  if (row.deepseek === "running" || row.deepseek === "queued") return "running";
  if (row.deepseek === "ready") return "ready";
  if (row.deepseek === "failed") return "failed";
  return "groom";
}

const CLOSED_STATUSES = new Set(["Done"]);

export function rowsFromProject(document, prsByIssue = new Map()) {
  const rows = [];
  for (const item of document?.items ?? []) {
    const content = item.content ?? {};
    if (content.type !== "Issue" || !content.url) continue;
    const match = /github\.com\/([^/]+)\/([^/]+)\/issues\/(\d+)/.exec(content.url);
    if (!match || match[1] !== OWNER || !REPOS[match[2]]) continue;
    const status = item.status ?? "No status";
    if (CLOSED_STATUSES.has(status)) continue;
    const labels = (item.labels ?? []).map((l) => (typeof l === "string" ? l : l?.name)).filter(Boolean);
    const queue = Number(field(item, "Queue Order"));
    const row = {
      key: `${match[2]}#${match[3]}`,
      repo: match[2],
      repoName: REPOS[match[2]].name,
      number: Number(match[3]),
      title: content.title ?? item.title ?? "",
      url: content.url,
      status,
      priority: field(item, "Priority"),
      size: field(item, "Size"),
      queueOrder: Number.isSafeInteger(queue) && queue > 0 ? queue : null,
      labels,
      deepseek: deepseekState(labels),
      pr: prsByIssue.get(`${match[2]}#${match[3]}`) ?? null,
    };
    row.stage = stageOf(row);
    rows.push(row);
  }
  return rows.sort(compareRows);
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
  return `Review and finish DeepSeek's draft PR ${row.pr?.url} for issue ${row.url}. Treat it as an unreviewed starting point: check its notes, verify the work against the issue and the repository rules in AGENTS.md, fix what's wrong, finish what's missing, and deliver it normally.`;
}

async function gh(args) {
  const { stdout } = await run("gh", args, { cwd: ROOT, maxBuffer: 32 * 1024 * 1024 });
  return JSON.parse(stdout);
}

async function loadBoard() {
  const template = await readFile(path.join(ROOT, ".github", "deepseek", "chat-prompt.md"), "utf8");
  const errors = [];
  const all = [];
  await Promise.all(Object.entries(REPOS).map(async ([repo, config]) => {
    try {
      const [project, pulls] = await Promise.all([
        gh(["project", "item-list", String(config.project), "--owner", OWNER, "--limit", "1000", "--format", "json"]),
        gh(["pr", "list", "-R", `${OWNER}/${repo}`, "--state", "open", "--limit", "200", "--json", "number,url,headRefName"]),
      ]);
      const rows = rowsFromProject(project, prsByIssue(repo, pulls)).filter((row) => row.repo === repo);
      for (const row of rows) {
        row.chatPrompt = chatPrompt(template, row);
        if (row.pr) row.codexPrompt = codexPrompt(row);
      }
      all.push(...rows);
    } catch (error) {
      errors.push(`${config.name}: ${String(error?.stderr || error?.message || error).trim().slice(0, 300)}`);
    }
  }));
  return { rows: all.sort(compareRows), errors, at: new Date().toISOString() };
}

async function launch(repo, number, model) {
  if (!REPOS[repo] || !Number.isSafeInteger(number) || number < 1) throw new Error("Unknown issue");
  const label = model === "pro" ? "deepseek-pro" : "deepseek";
  await run("gh", ["label", "create", label, "-R", `${OWNER}/${repo}`, "--color", label === "deepseek" ? "1f6feb" : "8250df", "--force"], { cwd: ROOT });
  await run("gh", ["issue", "edit", String(number), "-R", `${OWNER}/${repo}`, "--add-label", label], { cwd: ROOT });
}

function page(token) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VERA prep board</title><style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#1d2330;--mute:#677085;--line:#e2e5eb;--blue:#1f6feb;--green:#1a7f37;--amber:#9a6700;--red:#cf222e;--violet:#8250df}
@media (prefers-color-scheme:dark){:root{--bg:#0f1218;--card:#171b23;--ink:#e6e9ef;--mute:#98a1b3;--line:#2a303c}}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink)}
header{display:flex;gap:16px;align-items:center;padding:16px 24px;border-bottom:1px solid var(--line);background:var(--card);position:sticky;top:0;z-index:2;flex-wrap:wrap}
h1{font-size:18px;margin:0}.meta{color:var(--mute);font-size:12px}.spacer{flex:1}
button,.btn{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:7px;padding:5px 10px;cursor:pointer;text-decoration:none;white-space:nowrap;display:inline-block}
button:hover,.btn:hover{border-color:var(--blue)}.primary{background:var(--blue);border-color:var(--blue);color:#fff}
main{padding:16px 24px 48px;max-width:1200px;margin:0 auto}
.tabs{display:flex;gap:8px;margin:0 0 12px;flex-wrap:wrap}.tabs button[aria-pressed=true]{border-color:var(--blue);color:var(--blue);font-weight:600}
.filters{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap}input,select{font:inherit;padding:5px 8px;border:1px solid var(--line);border-radius:7px;background:var(--card);color:var(--ink)}
ol{list-style:none;margin:0;padding:0;display:grid;gap:8px}
li{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;display:grid;grid-template-columns:28px 1fr auto;gap:10px;align-items:center}
.q{color:var(--mute);font-variant-numeric:tabular-nums;text-align:right}.t a{color:var(--ink);font-weight:600;text-decoration:none}.t a:hover{text-decoration:underline}
.chips{display:flex;gap:6px;margin-top:3px;flex-wrap:wrap}.chip{font-size:11px;color:var(--mute);border:1px solid var(--line);border-radius:999px;padding:0 7px}
.s-running{color:var(--amber);border-color:var(--amber)}.s-ready{color:var(--green);border-color:var(--green)}.s-failed{color:var(--red);border-color:var(--red)}.s-opened{color:var(--violet);border-color:var(--violet)}
.acts{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}.err{background:#fff1f0;color:var(--red);border:1px solid var(--red);padding:8px 12px;border-radius:8px;margin-bottom:12px}
.empty{color:var(--mute);padding:24px;text-align:center}.toast{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);background:var(--ink);color:var(--bg);padding:8px 14px;border-radius:8px;opacity:0;transition:opacity .2s}.toast.on{opacity:.95}
</style></head><body>
<header><h1>VERA prep board</h1><span class="meta" id="meta">Loading…</span><span class="spacer"></span>
<button id="bulk" title="Add the deepseek label to every checked issue">Send checked to DeepSeek</button><button id="refresh">Refresh</button></header>
<main><div id="errors"></div>
<div class="tabs" id="tabs"></div>
<div class="filters"><input id="search" placeholder="Search title or #" size="28"><select id="repo"><option value="">Both repos</option><option value="vera-script-to-timeline">Timeline</option><option value="vera-research-video-clips">Research</option></select>
<label class="meta"><input type="checkbox" id="hideActive"> Hide In progress / In review</label></div>
<ol id="list"></ol></main><div class="toast" id="toast"></div>
<script>
const TOKEN=${JSON.stringify(token)};
const STAGES=[["groom","To groom"],["running","DeepSeek running"],["ready","Ready for Codex"],["failed","Needs a look"],["all","All"]];
const opened=JSON.parse((()=>{try{return localStorage.getItem("vera-prep-opened")||"{}"}catch{return"{}"}})());
let data={rows:[],errors:[]},stage="groom";
const $=(id)=>document.getElementById(id);
const esc=(s)=>String(s??"").replace(/[&<>"']/g,(c)=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
function toast(msg){const t=$("toast");t.textContent=msg;t.classList.add("on");setTimeout(()=>t.classList.remove("on"),2600)}
function saveOpened(){try{localStorage.setItem("vera-prep-opened",JSON.stringify(opened))}catch{}}
function ago(ts){const m=Math.round((Date.now()-ts)/60000);return m<60?m+"m ago":Math.round(m/60)+"h ago"}
async function load(force){$("meta").textContent="Refreshing…";const r=await fetch("/api/board"+(force?"?force=1":""));data=await r.json();render()}
function render(){
  $("errors").innerHTML=data.errors.map((e)=>'<div class="err">'+esc(e)+'</div>').join("");
  $("meta").textContent="Updated "+new Date(data.at).toLocaleTimeString()+" · refreshes every 3 min";
  const counts=Object.fromEntries(STAGES.map(([k])=>[k,k==="all"?data.rows.length:data.rows.filter((r)=>r.stage===k).length]));
  $("tabs").innerHTML=STAGES.map(([k,n])=>'<button data-stage="'+k+'" aria-pressed="'+(k===stage)+'">'+n+' ('+counts[k]+')</button>').join("");
  const q=$("search").value.trim().toLowerCase(),repo=$("repo").value,hide=$("hideActive").checked;
  const rows=data.rows.filter((r)=>(stage==="all"||r.stage===stage)&&(!repo||r.repo===repo)&&(!hide||!/In progress|In review/.test(r.status))&&(!q||(r.title+" #"+r.number).toLowerCase().includes(q)));
  $("list").innerHTML=rows.length?rows.map(row).join(""):'<li class="empty" style="display:block">Nothing here.</li>';
}
function row(r){
  const o=opened[r.key];
  const chips=['<span class="chip">'+esc(r.repoName)+'</span>','<span class="chip">'+esc(r.status)+'</span>',r.priority&&'<span class="chip">'+esc(r.priority)+'</span>',r.size&&'<span class="chip">Size '+esc(r.size)+'</span>',
    r.deepseek!=="none"&&'<span class="chip s-'+(r.deepseek==="queued"?"running":r.deepseek)+'">DeepSeek '+esc(r.deepseek)+'</span>',
    o&&r.stage==="groom"&&'<span class="chip s-opened">Chat opened '+ago(o)+'</span>'].filter(Boolean).join("");
  let acts="";
  if(r.stage==="groom"||r.stage==="failed") acts+='<button class="primary" data-act="chat" data-key="'+esc(r.key)+'" title="Opens ChatGPT with the grooming prompt (also copied). Chat grooms, asks only vital questions, then launches DeepSeek.">Groom in ChatGPT</button><button data-act="ds" data-key="'+esc(r.key)+'" title="Skip grooming: run DeepSeek Flash on the issue as written">DeepSeek now</button>';
  if(r.stage==="running") acts+='<a class="btn" href="'+esc(r.url)+'" target="_blank" rel="noopener">Watch on issue</a>';
  if(r.stage==="ready"&&!r.pr) acts+='<a class="btn" href="'+esc(r.url)+'" target="_blank" rel="noopener" title="The result comment links to the pushed branch">Open result on issue</a>';
  if(r.pr) acts+='<a class="btn" href="'+esc(r.pr.url)+'" target="_blank" rel="noopener">Draft PR #'+r.pr.number+'</a><button data-act="codex" data-key="'+esc(r.key)+'" title="Opens Codex with a review-and-finish prompt (also copied)">Open in Codex</button>';
  return '<li><span class="q">'+(r.stage==="groom"?'<input type="checkbox" data-pick="'+esc(r.key)+'" title="Select for bulk DeepSeek">':"")+'<br>'+(r.queueOrder??"")+'</span><div class="t"><a href="'+esc(r.url)+'" target="_blank" rel="noopener">#'+r.number+' '+esc(r.title)+'</a><div class="chips">'+chips+'</div></div><div class="acts">'+acts+'</div></li>';
}
async function copy(text){try{await navigator.clipboard.writeText(text);return true}catch{return false}}
async function launch(keys,model){
  const r=await fetch("/api/launch",{method:"POST",headers:{"content-type":"application/json","x-prep-token":TOKEN},body:JSON.stringify({keys,model})});
  const out=await r.json();toast(out.ok?"DeepSeek launched for "+out.launched.join(", "):"Launch failed: "+out.error);load(true);
}
document.addEventListener("click",async(e)=>{
  const t=e.target.closest("[data-stage],[data-act]");if(!t)return;
  if(t.dataset.stage){stage=t.dataset.stage;render();return}
  const r=data.rows.find((x)=>x.key===t.dataset.key);if(!r)return;
  if(t.dataset.act==="chat"){window.open("https://chatgpt.com/?q="+encodeURIComponent(r.chatPrompt),"_blank","noopener");await copy(r.chatPrompt);opened[r.key]=Date.now();saveOpened();render();toast("ChatGPT opened. Prompt also copied, if you'd rather paste it into the desktop app.")}
  if(t.dataset.act==="ds"&&confirm("Run DeepSeek Flash on #"+r.number+" as written, without Chat grooming?"))launch([r.key],"flash");
  if(t.dataset.act==="codex"){await copy(r.codexPrompt);location.href="codex://new?prompt="+encodeURIComponent(r.codexPrompt)+"&originUrl="+encodeURIComponent("https://github.com/mbelinkie/"+r.repo+".git");toast("Codex prompt copied.")}
});
$("bulk").onclick=()=>{const keys=[...document.querySelectorAll("[data-pick]:checked")].map((c)=>c.dataset.pick);if(!keys.length)return toast("Check some issues in To groom first.");if(confirm("Run DeepSeek Flash on "+keys.length+" issue(s) as written?"))launch(keys,"flash")};
$("refresh").onclick=()=>load(true);["search","repo","hideActive"].forEach((id)=>$(id).addEventListener("input",render));
load(false);setInterval(()=>{if(!document.hidden)load(false)},${REFRESH_MS});
</script></body></html>`;
}

export async function startServer({ port = PORT, open = true } = {}) {
  const token = randomBytes(16).toString("hex");
  let cache = null;
  let pending = null;
  const board = async (force) => {
    if (!force && cache && Date.now() - Date.parse(cache.at) < 60_000) return cache;
    pending ??= loadBoard().then((value) => (cache = value)).finally(() => (pending = null));
    return pending;
  };
  const server = createServer(async (req, res) => {
    const url = new URL(req.url, `http://127.0.0.1:${port}`);
    const send = (status, body, type = "application/json") => {
      res.writeHead(status, { "content-type": type, "cache-control": "no-store", "x-content-type-options": "nosniff" });
      res.end(type === "application/json" ? JSON.stringify(body) : body);
    };
    try {
      if (req.method === "GET" && url.pathname === "/") return send(200, page(token), "text/html; charset=utf-8");
      if (req.method === "GET" && url.pathname === "/api/board") return send(200, await board(url.searchParams.has("force")));
      if (req.method === "GET" && url.pathname === "/status") return send(200, { service: "vera-prep-board" });
      if (req.method === "POST" && url.pathname === "/api/launch") {
        if (req.headers["x-prep-token"] !== token) return send(403, { ok: false, error: "Reload the board and try again." });
        let body = "";
        for await (const chunk of req) { body += chunk; if (body.length > 10_000) return send(413, { ok: false, error: "Too large" }); }
        const { keys, model } = JSON.parse(body);
        const launched = [];
        for (const key of Array.isArray(keys) ? keys.slice(0, 50) : []) {
          const [repo, number] = String(key).split("#");
          await launch(repo, Number(number), model);
          launched.push(`${REPOS[repo]?.name} #${number}`);
        }
        cache = null;
        return send(200, { ok: true, launched });
      }
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

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  startServer({ open: !process.argv.includes("--no-open") }).catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
}
