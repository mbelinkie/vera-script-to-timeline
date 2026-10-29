import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { GitHub } from "./ci-queue-github.mjs";
import { assessRun } from "./ci-queue-policy.ts";

export const STATUS = "VERA queue validation";
const SHA = /^[0-9a-f]{40}$/;
const running = (run) => run.status !== "completed";
const runKey = (run) => `${run.id}:${run.run_attempt ?? 1}`;
const started = (run) => Date.parse(run.run_started_at ?? run.created_at);
const privileged = new Set(["admin", "maintain", "write"]);
const closesIssue = /\b(?:close[sd]?|fix(?:es|ed)?|resolve[sd]?):?\s+(?:(?:[\w.-]+\/[\w.-]+)?#[0-9]+|https:\/\/github\.com\/)/i;

export function initialState(controlIssue) {
  if (!Number.isSafeInteger(controlIssue) || controlIssue < 1) throw new Error("Invalid control issue");
  const initializedAt = Date.now();
  return { version: 1, controlIssue, initializedAt, cursorSince: initializedAt - 60000, failureCursor: 0, processedRuns: [], cursor: 0, entries: [], active: null, paused: { id: "initial", startedAt: initializedAt, reason: "Initialized paused; inspect protection, then /queue resume" }, completed: [] };
}

export function validateState(state) {
  if (state?.version !== 1 || !Number.isSafeInteger(state.controlIssue) || state.controlIssue < 1 ||
      !Number.isSafeInteger(state.cursor) || state.cursor < 0 || !Array.isArray(state.entries) ||
      !Number.isFinite(state.initializedAt) || !Array.isArray(state.processedRuns) || state.processedRuns.length > 500 ||
      !Number.isFinite(state.cursorSince) ||
      !Number.isSafeInteger(state.failureCursor) || state.failureCursor < 0 ||
      state.processedRuns.some((key) => !/^[1-9][0-9]*:[1-9][0-9]*$/.test(key)) ||
      !Array.isArray(state.completed) || state.entries.length > 100 || state.completed.length > 100 ||
      (state.paused !== null && (typeof state.paused?.reason !== "string" || typeof state.paused?.id !== "string"))) {
    throw new Error("Queue state is invalid; retain state branch and repair manually");
  }
  for (const entry of state.entries) {
    if (!Number.isSafeInteger(entry.pr) || entry.pr < 1 || !SHA.test(entry.submitted) || !SHA.test(entry.head) ||
        typeof entry.ready !== "boolean" || typeof entry.owner !== "string") throw new Error("Invalid queue entry");
  }
  if (new Set(state.entries.map((e) => e.pr)).size !== state.entries.length) throw new Error("Duplicate queue entries");
  if (state.active !== null) {
    const active = state.active;
    if (typeof active.id !== "string" || !["integrating", "validating", "merging", "smoke"].includes(active.phase) ||
        !SHA.test(active.base) || !state.entries.some((entry) => entry.pr === active.pr) ||
        (active.candidate !== undefined && !SHA.test(active.candidate)) ||
        (["validating", "smoke"].includes(active.phase) && (!active.expected || !Number.isFinite(active.expected.startedAt)))) {
      throw new Error("Invalid active transaction");
    }
    if (active.expected && (typeof active.expected.title !== "string" || active.expected.title.length > 256 ||
        !Number.isSafeInteger(active.expected.workflowId) || active.expected.workflowId < 1 || !SHA.test(active.expected.workflowHead) ||
        !Number.isFinite(active.expected.timeoutMs) || active.expected.timeoutMs <= 0 || active.expected.startedAt < 0)) {
      throw new Error("Invalid expected run identity");
    }
  }
  return state;
}

export function parseCommand(body) {
  const text = body.trim();
  let match = /^\/queue (ready|validate) ([1-9][0-9]*) ([0-9a-f]{40})$/.exec(text);
  if (match && Number.isSafeInteger(Number(match[2]))) return { action: match[1], pr: Number(match[2]), head: match[3] };
  match = /^\/queue remove ([1-9][0-9]*)$/.exec(text);
  if (match && Number.isSafeInteger(Number(match[1]))) return { action: "remove", pr: Number(match[1]) };
  match = /^\/queue recover ([0-9a-f]{40})$/.exec(text);
  if (match) return { action: "recover", head: match[1] };
  if (/^\/queue (pause|resume|inspect)$/.test(text)) return { action: text.slice(7) };
  return null;
}

export class Queue {
  constructor(github, { now = Date.now, uuid = randomUUID, enabled = false } = {}) {
    this.github = github;
    this.root = `/repos/${github.repository}`;
    this.now = now;
    this.uuid = uuid;
    this.enabled = enabled;
  }

  api(method, suffix, body) { return this.github.api(method, `${this.root}${suffix}`, body); }
  pages(suffix) { return this.github.pages(`${this.root}${suffix}`); }

  async save() {
    const saved = await this.github.saveState(validateState(this.state), this.sha);
    this.sha = saved.sha;
  }

  async comment(body) { return this.api("POST", `/issues/${this.state.controlIssue}/comments`, { body }); }

  async pause(reason) {
    if (!this.state.paused) {
      this.state.paused = { id: this.uuid(), startedAt: this.now(), reason };
    } else this.state.paused.reason = reason;
    await this.save();
    await this.alert();
  }

  async alert() {
    const { paused, active } = this.state;
    if (!paused) return;
    const marker = `<!-- vera-queue-pause:${paused.id} -->`;
    const since = encodeURIComponent(new Date((paused.startedAt ?? this.state.initializedAt) - 60000).toISOString());
    const comments = await this.pages(`/issues/${this.state.controlIssue}/comments?since=${since}`);
    const existing = comments.find((c) => c.user?.login === "github-actions[bot]" && c.body?.includes(marker));
    const run = active?.runUrl ? `\nRun: ${active.runUrl}` : "";
    const body = `${marker}\n@${this.github.repository.split("/")[0]} Queue paused: ${paused.reason}.${active ? `\nPR #${active.pr}, candidate \`${active.candidate ?? active.base}\`.` : ""}${run}\nWaiting entries are retained. Repair the cause, refresh readiness if code changed, then explicitly \`/queue resume\`. GitHub notification only; this does not wake a Codex chat.`;
    if (!existing) await this.comment(body);
    else if (existing.body !== body) await this.api("PATCH", `/issues/comments/${existing.id}`, { body });
  }

  async authorize(login) {
    try {
      const result = await this.api("GET", `/collaborators/${encodeURIComponent(login)}/permission`);
      return privileged.has(result.permission);
    } catch (error) {
      if ([403, 404].includes(error.status)) return false;
      throw error;
    }
  }

  async pull(pr) {
    const pull = await this.api("GET", `/pulls/${pr}`);
    if (pull.base?.ref !== "main" || pull.base?.repo?.full_name !== this.github.repository ||
        pull.head?.repo?.full_name !== this.github.repository || !SHA.test(pull.head?.sha)) {
      throw new Error(`PR #${pr} must target main from a branch in this repository`);
    }
    return pull;
  }

  async main() {
    const ref = await this.api("GET", "/git/ref/heads/main");
    if (!SHA.test(ref.object?.sha)) throw new Error("Cannot identify main");
    return ref.object.sha;
  }

  async runs() {
    // All pages matter: an older still-running manual run also owns the slot.
    const result = [];
    // Do not infer global idleness from a page of recent completed runs.
    for (const status of ["queued", "in_progress", "waiting", "requested", "pending"]) {
      const batch = await this.api("GET", `/actions/workflows/validate.yml/runs?per_page=100&status=${status}`);
      if (!Array.isArray(batch.workflow_runs) || batch.workflow_runs.length >= 100) throw new Error("Cannot bound active validation runs");
      result.push(...batch.workflow_runs.filter((run) => !(this.enabled && run.event === "pull_request")));
    }
    for (let page = 1; page <= 100; page += 1) {
      const batch = await this.api("GET", `/actions/workflows/validate.yml/runs?per_page=100&page=${page}`);
      if (!Array.isArray(batch.workflow_runs)) throw new Error("Cannot identify validation runs");
      result.push(...batch.workflow_runs.filter((run) => !(this.enabled && run.event === "pull_request") && !result.some((old) => old.id === run.id)));
      if (batch.workflow_runs.length < 100) return result;
      // Reruns keep old IDs/creation times. A page boundary cannot prove there
      // are no recent failed attempts later in history.
    }
    throw new Error("Validation run listing exceeded bound");
  }

  async idle() {
    const runs = await this.runs();
    if (runs.some(running)) throw new Error("Another Validate run occupies the slot; inspect it before resuming");
    return runs;
  }

  acknowledge(runs) {
    if (runs.some((r) => !Number.isSafeInteger(r.id) || r.id < 1)) throw new Error("Invalid validation run identifier");
    this.state.failureCursor = Math.max(this.state.failureCursor, ...runs.map((r) => r.id));
    this.state.processedRuns = [...new Set([...this.state.processedRuns, ...runs.map(runKey)])].slice(-500);
  }

  async checkFailures(runs) {
    const failure = runs.find((r) => (r.id > this.state.failureCursor || (r.run_attempt > 1 && !this.state.processedRuns.includes(runKey(r)))) && started(r) >= this.state.initializedAt && r.status === "completed" && r.conclusion !== "success");
    if (failure) throw new Error(`Validate failed: https://github.com/${this.github.repository}/actions/runs/${failure.id}; repair and explicitly resume`);
    if (!runs.some(running)) {
      const previous = this.state.failureCursor;
      this.acknowledge(runs);
      if (previous !== this.state.failureCursor) await this.save();
    }
  }

  async protection() {
    const protection = await this.api("GET", "/branches/main/protection/required_status_checks");
    if (protection.strict !== true || !protection.contexts?.includes(STATUS)) {
      throw new Error(`Main must require strict ${STATUS} status before enabling delivery`);
    }
  }

  async ownerClosure(pull) {
    if (closesIssue.test(`${pull.title ?? ""}\n${pull.body ?? ""}`)) throw new Error("Replace auto-closing PR keywords with Refs before queue readiness; the owner closes issues after acceptance");
    const commits = await this.pages(`/pulls/${pull.number}/commits`);
    if (commits.length >= 250 || commits.some((commit) => closesIssue.test(commit.commit?.message ?? ""))) {
      throw new Error("Candidate commits may auto-close an issue; repair their messages before readiness");
    }
    // Sidebar links can close issues too, without any keyword in the PR text.
    const [owner, name] = this.github.repository.split("/");
    const response = await this.github.api("POST", "/graphql", {
      query: "query($owner:String!,$name:String!,$pr:Int!){repository(owner:$owner,name:$name){pullRequest(number:$pr){closingIssuesReferences(first:100){totalCount}}}}",
      variables: { owner, name, pr: pull.number },
    });
    const count = response.data?.repository?.pullRequest?.closingIssuesReferences?.totalCount;
    if (response.errors || count !== 0) throw new Error("Remove issue-closing sidebar links before queue readiness; issue closure belongs to its owner");
  }

  async commands() {
    const since = encodeURIComponent(new Date(this.state.cursorSince).toISOString());
    const comments = await this.pages(`/issues/${this.state.controlIssue}/comments?since=${since}`);
    const pending = comments.filter((c) => c.id > this.state.cursor).sort((a, b) => a.id - b.id);
    for (const comment of pending) {
      const command = parseCommand(comment.body ?? "");
      // Save the cursor before effects: a crash must never replay a readiness grant.
      this.state.cursor = comment.id;
      const created = Date.parse(comment.created_at);
      this.state.cursorSince = Number.isFinite(created) ? created - 1000 : this.now() - 60000;
      await this.save();
      if (!command || !await this.authorize(comment.user.login)) continue;
      try {
        await this.command(command, comment.user.login);
      } catch (error) {
        await this.pause(error.message);
      }
    }
  }

  async command(command, login) {
    if (command.action === "inspect") {
      await this.comment(this.summary());
    } else if (command.action === "pause") {
      await this.pause(`Paused by @${login}`);
    } else if (command.action === "recover") {
      const active = this.state.active;
      if (!this.enabled || !this.state.paused || !active) throw new Error("Recover requires a paused delivered transaction");
      const runs = await this.idle();
      await this.protection();
      const pull = await this.pull(active.pr);
      if (!pull.merged || await this.main() !== command.head) throw new Error("Recover must name the exact current main after a delivered merge");
      this.acknowledge(runs);
      active.deliveredSha ??= pull.merge_commit_sha;
      await this.startSmoke(command.head, active);
      this.state.paused = null;
      await this.save();
    } else if (command.action === "resume") {
      if (!this.state.paused) return;
      if (!this.enabled) throw new Error("Queue delivery is disabled; enable it only after activation checks");
      const runs = await this.idle();
      await this.protection();
      this.acknowledge(runs);
      const active = this.state.active;
      if (active) {
        const pull = await this.pull(active.pr);
        if (pull.merged) {
          if (!SHA.test(pull.merge_commit_sha) || await this.main() !== pull.merge_commit_sha) throw new Error("Delivered main advanced; inspect and use /queue recover with its exact repaired SHA");
          active.deliveredSha ??= pull.merge_commit_sha;
          await this.startSmoke(pull.merge_commit_sha, active);
        } else {
          // A failed pre-merge attempt can be rebuilt, but an author push needs /queue ready again.
          this.state.active = null;
        }
      }
      this.state.paused = null;
      await this.save();
    } else if (command.action === "remove") {
      if (this.state.active?.pr === command.pr) throw new Error("Active entry cannot be removed; pause, repair/resume, or use the documented manual recovery");
      this.state.entries = this.state.entries.filter((e) => e.pr !== command.pr);
      await this.save();
    } else {
      const pull = await this.pull(command.pr);
      if (pull.state !== "open" || pull.head.sha !== command.head || (command.action === "ready" && pull.draft)) {
        throw new Error("Readiness requires the exact pushed head of an open, non-draft PR; validate also accepts drafts");
      }
      if (command.action === "ready") await this.ownerClosure(pull);
      if (this.state.active?.pr === command.pr) {
        if (!this.state.paused) throw new Error("Pause and finish any running validation before replacing active readiness");
        await this.idle();
        if (pull.merged) throw new Error("Delivered entries cannot be reauthorized");
        this.state.active = null;
      }
      const entry = { pr: command.pr, submitted: command.head, head: command.head, ready: command.action === "ready", owner: login };
      const index = this.state.entries.findIndex((e) => e.pr === command.pr);
      if (index < 0) this.state.entries.push(entry); else this.state.entries[index] = entry;
      await this.save();
    }
  }

  summary() {
    return `Queue: ${this.state.paused ? `PAUSED — ${this.state.paused.reason}` : "running"}\n${this.state.active ? `Active #${this.state.active.pr}: ${this.state.active.phase}, ${this.state.active.candidate ?? this.state.active.base}` : "Slot idle"}\nWaiting: ${this.state.entries.map((e) => `#${e.pr} ${e.head.slice(0, 8)} (${e.ready ? "merge ready" : "validate only"})`).join(", ") || "none"}\n[Durable state](https://github.com/${this.github.repository}/blob/vera-ci-queue-state/queue.json)`;
  }

  async status(sha, state, url, context = STATUS) {
    await this.api("POST", `/statuses/${sha}`, { state, context, description: `Queue validation ${state}`, ...(url ? { target_url: url } : {}) });
  }

  async dispatch(mode, candidate, base, active) {
    await this.idle();
    const workflow = await this.api("GET", "/actions/workflows/validate.yml");
    if (!Number.isSafeInteger(workflow.id) || workflow.path !== ".github/workflows/validate.yml" || workflow.state !== "active") throw new Error("Validation workflow is not active");
    const workflowHead = await this.main();
    if (workflowHead !== base && mode === "pr") throw new Error("Main changed before dispatch");
    const transaction = this.uuid();
    active.phase = mode === "pr" ? "validating" : "smoke";
    active.candidate = candidate;
    active.expected = { title: `vera-queue:${transaction}:${mode}:${candidate}:${base}`, workflowId: workflow.id, workflowHead, startedAt: this.now(), timeoutMs: mode === "pr" ? 100 * 60000 : 15 * 60000 };
    delete active.runUrl;
    await this.save();
    // Persist intent first. An uncertain dispatch is never automatically repeated.
    await this.api("POST", "/actions/workflows/validate.yml/dispatches", { ref: "main", inputs: { mode, candidate, base, transaction } });
  }

  async startSmoke(mergeSha, active) {
    active.mergeSha = mergeSha;
    await this.dispatch("smoke", mergeSha, mergeSha, active);
  }

  async begin() {
    const entry = this.state.entries[0];
    if (!entry) return;
    // A valid manual run already in the shared slot hands back on completion.
    const runs = await this.runs();
    await this.checkFailures(runs);
    if (runs.some(running)) return;
    await this.protection();
    const pull = await this.pull(entry.pr);
    if (pull.state !== "open" || pull.head.sha !== entry.head || (entry.ready && pull.draft)) throw new Error(`PR #${entry.pr} changed after readiness; owner must enqueue its new head`);
    if (entry.ready) await this.ownerClosure(pull);
    const base = await this.main();
    const active = { id: this.uuid(), pr: entry.pr, phase: "integrating", base };
    this.state.active = active;
    await this.save();
    const compare = await this.api("GET", `/compare/${base}...${entry.head}`);
    let candidate = entry.head;
    if (!["ahead", "identical"].includes(compare.status)) {
      const message = `VERA queue integration ${active.id}`;
      const merged = await this.api("POST", "/merges", { base: pull.head.ref, head: base, commit_message: message });
      if (!SHA.test(merged?.sha) || merged.parents?.length !== 2 || merged.parents[0].sha !== entry.head || merged.parents[1].sha !== base || merged.commit?.message !== message) {
        throw new Error("Unverifiable integration identity; inspect branch before resuming");
      }
      candidate = merged.sha;
    }
    const branch = await this.api("GET", `/git/ref/heads/${encodeURIComponent(pull.head.ref)}`);
    if (branch.object?.sha !== candidate || await this.main() !== base) throw new Error("Head/base changed during integration");
    active.candidate = candidate;
    entry.head = candidate;
    await this.save();
    await this.status(candidate, "pending", undefined, entry.ready ? STATUS : "VERA preview validation");
    await this.dispatch("pr", candidate, base, active);
  }

  async advance() {
    if (this.state.paused || !this.enabled) return;
    const active = this.state.active;
    if (!active) { await this.begin(); return; }
    if (!["validating", "smoke"].includes(active.phase)) throw new Error("Interrupted side effect; inspect before explicit resume");
    const runs = await this.runs();
    await this.checkFailures(runs);
    const matches = runs.filter((run) => run.display_title === active.expected.title);
    if (matches.length === 1 && Number.isSafeInteger(matches[0].id) && matches[0].id > 0) {
      active.runUrl = `https://github.com/${this.github.repository}/actions/runs/${matches[0].id}`;
    }
    const result = assessRun(active.expected, runs, this.now());
    if (result.kind === "pause") throw new Error(`${active.phase === "smoke" ? "Main smoke" : "Validate"}: ${result.reason}`);
    if (result.runId) {
      active.runUrl = result.url;
      await this.save();
    }
    // Main/head drift revokes readiness even while a validation is still running.
    const pull = await this.pull(active.pr);
    if (active.phase === "validating" && (pull.state !== "open" || pull.head.sha !== active.candidate || await this.main() !== active.base || (this.state.entries[0].ready && pull.draft))) {
      throw new Error("Author head, draft state or main changed during validation; readiness revoked");
    }
    if (result.kind === "wait") return;
    if (runs.some((run) => running(run) && run.id !== result.runId)) return;
    if (active.phase === "smoke") {
      if (await this.main() !== active.mergeSha) throw new Error("Main advanced before smoke handoff");
      this.state.completed.push({ id: active.id, pr: active.pr, candidate: this.state.entries[0].head, mergeSha: active.deliveredSha ?? active.mergeSha, smokeSha: active.mergeSha, runId: result.runId });
      this.state.completed = this.state.completed.slice(-100);
      this.state.entries = this.state.entries.filter((e) => e.pr !== active.pr);
      this.state.active = null;
      await this.save();
      await this.comment(`Delivered PR #${active.pr}; Main smoke passed: ${result.url}. Issue closure remains with its owner.`);
      await this.begin();
    } else {
      if (!this.state.entries[0].ready) {
        await this.status(active.candidate, "success", result.url, "VERA preview validation");
        this.state.entries.shift();
        this.state.active = null;
        await this.save();
        await this.comment(`Validation only passed for #${active.pr} at \`${active.candidate}\`: ${result.url}. No merge readiness was granted.`);
        await this.begin();
        return;
      }
      await this.protection();
      const current = await this.pull(active.pr);
      await this.ownerClosure(current);
      if (await this.main() !== active.base || current.head.sha !== active.candidate || current.draft) throw new Error("Candidate/base changed before protected merge");
      await this.status(active.candidate, "success", result.url);
      // A neutral message avoids automatic issue closure from a PR's title/body.
      active.phase = "merging";
      await this.save();
      const merged = await this.api("PUT", `/pulls/${active.pr}/merge`, { sha: active.candidate, merge_method: "merge", commit_title: `Deliver PR #${active.pr}`, commit_message: "Validated by VERA delivery queue; issue acceptance remains owner-managed." });
      if (!merged.merged || !SHA.test(merged.sha) || await this.main() !== merged.sha) throw new Error("Uncertain protected merge identity; inspect before resuming");
      active.deliveredSha = merged.sha;
      await this.startSmoke(merged.sha, active);
    }
  }

  async run({ eventName, event, action, controlIssue, actor }) {
    const loaded = await this.github.loadState();
    if (!loaded) {
      if (eventName !== "workflow_dispatch" || action !== "init" || !await this.authorize(actor)) throw new Error("Queue uninitialized; authorized init required");
      this.state = initialState(Number(controlIssue));
      const issue = await this.api("GET", `/issues/${this.state.controlIssue}`);
      if (issue.state !== "open" || issue.pull_request) throw new Error("Init requires an open dedicated control issue");
      this.sha = null;
      await this.save();
      await this.comment(this.summary());
      return;
    }
    this.sha = loaded.sha;
    this.state = validateState(loaded.state);
    if (eventName === "issue_comment" && event.issue?.number !== this.state.controlIssue) return;
    if (eventName === "workflow_dispatch" && !await this.authorize(actor)) throw new Error("Unauthorized queue control");
    try {
      await this.commands();
      const run = event.workflow_run;
      if (eventName === "workflow_run" && run && !this.state.processedRuns.includes(runKey(run))) {
        this.state.processedRuns.push(runKey(run));
        this.state.processedRuns = this.state.processedRuns.slice(-500);
        const activeTitle = this.state.active?.expected?.title;
        if ((run.id > this.state.failureCursor || run.run_attempt > 1) && run.display_title !== activeTitle && !(this.enabled && run.event === "pull_request") && started(run) >= this.state.initializedAt && run.conclusion !== "success") {
          await this.pause(`Validation outside the transaction failed: https://github.com/${this.github.repository}/actions/runs/${run.id}; inspect before resuming`);
          return;
        }
        await this.save();
      }
      await this.advance();
    } catch (error) {
      await this.pause(error.message);
    }
    await this.alert();
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const github = new GitHub({ repository: process.env.GITHUB_REPOSITORY, token: process.env.GITHUB_TOKEN });
    const queue = new Queue(github, { enabled: process.env.VERA_CI_QUEUE_ENABLED === "true" });
    await queue.run({ eventName: process.env.GITHUB_EVENT_NAME, event: JSON.parse(readFileSync(process.env.GITHUB_EVENT_PATH, "utf8")), action: process.env.VERA_QUEUE_ACTION, controlIssue: process.env.VERA_QUEUE_ISSUE, actor: process.env.GITHUB_ACTOR });
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
