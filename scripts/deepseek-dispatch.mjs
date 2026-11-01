// GitHub issue-comment -> preinstalled private DeepSeek repair controller.
// This trusted dispatcher never calls a model or merges a PR.
import { readFileSync, writeFileSync, mkdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { homedir } from 'node:os';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';

export const REPO = 'mbelinkie/vera-script-to-timeline';
export const COMMAND = '/deepseek dispatch';
export const APPROVAL_LABELS = ['chat-reviewed', 'deepseek-eligible', 'deepseek-ready', 'deepseek-dispatch'];

export function requestFromEvent(event, allowedActors = []) {
  if (event?.repository?.full_name !== REPO) throw new Error('Wrong repository');
  if (event?.issue?.pull_request) throw new Error('Pull requests cannot be dispatched');
  if (event?.comment?.body !== COMMAND) throw new Error('Not an exact dispatch command');
  const login = event?.comment?.user?.login;
  if (!login || (login !== event?.repository?.owner?.login && !allowedActors.includes(login))) {
    throw new Error('Dispatch actor is not allowlisted');
  }
  if (!Number.isSafeInteger(event?.comment?.id) || event.comment.id < 1 ||
      !Number.isSafeInteger(event?.issue?.number) || event.issue.number < 1) {
    throw new Error('Invalid issue/comment identifier');
  }
  return { issue: event.issue.number, commentId: event.comment.id };
}

export function verifyCurrentIssue(issue, expectedIssue) {
  if (issue?.number !== expectedIssue || issue.state !== 'open' || issue.pull_request) {
    throw new Error('Issue no longer open or not an issue');
  }
  const labels = new Set((issue.labels || []).map(x => typeof x === 'string' ? x : x.name));
  for (const label of APPROVAL_LABELS) {
    if (!labels.has(label)) throw new Error('Missing required label: ' + label);
  }
  // Explicit opt-in is insufficient for work classified as design or non-DeepSeek.
  // Fail closed on conflicting classification; a human must re-triage the ticket.
  const prohibited = ['type:design', 'type:ux', 'type:research', 'type:product',
    'execution:codex', 'execution:design', 'execution:human', 'deepseek-excluded'];
  for (const label of prohibited) {
    if (labels.has(label)) throw new Error('DeepSeek excluded by classification: ' + label);
  }
  if (labels.has('owner:claude') || labels.has('owner:codex')) {
    throw new Error('Issue is assigned to another execution owner');
  }
  const types = [...labels].filter(label => label.startsWith('type:'));
  if (types.length !== 1 || !['type:implementation', 'type:bug'].includes(types[0])) {
    throw new Error('Only specifically classified implementation or bug issues may use DeepSeek');
  }
  if (labels.has('chat-review-pending')) throw new Error('Chat review still pending');
  if (labels.has('needs:model-escalation')) throw new Error('Model escalation still required');
  if (!/^## DeepSeek Handoff\s*$/m.test(issue.body || '')) throw new Error('Missing approved DeepSeek Handoff section');
  return true;
}

export function taskCap(value) {
  // This is an additional per-task ceiling, NOT a replacement for the
  // private controller's required cumulative USD10 campaign ledger.
  if (!value || !/^\d+(?:\.\d{1,4})?$/.test(value)) {
    throw new Error('Set VERA_DEEPSEEK_TASK_CAP_USD to a positive number');
  }
  const cap = Number(value);
  if (!(cap > 0 && cap <= 10)) throw new Error('Task cap must be >0 and <=10 USD');
  return cap;
}

export function reserveReceipt(root, issue, commentId) {
  // mkdir is atomic on one host. Never clear this guard automatically:
  // an interrupted/uncertain paid call requires manual ledger reconciliation.
  const dir = join(root, 'issue-' + issue);
  mkdirSync(root, { recursive: true, mode: 0o700 });
  mkdirSync(dir, { mode: 0o700 });
  const receipt = join(dir, 'receipt.json');
  writeFileSync(receipt, JSON.stringify({
    issue, commentId, state: 'reserved',
    timestamp: new Date().toISOString()
  }, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
  return receipt;
}

async function fetchIssue(token, issueNumber) {
  const url = 'https://api.github.com/repos/' + REPO + '/issues/' + issueNumber;
  const response = await globalThis.fetch(url, {
    headers: {
      Authorization: 'Bearer ' + token,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'vera-deepseek-dispatch'
    }
  });
  if (!response.ok) throw new Error('GitHub issue fetch failed: HTTP ' + response.status);
  return response.json();
}

export async function main(env = process.env) {
  if (env.VERA_DEEPSEEK_DISPATCH_ENABLED !== 'true') {
    throw new Error('Dispatch explicitly disabled');
  }
  const event = JSON.parse(readFileSync(env.GITHUB_EVENT_PATH, 'utf8'));
  const allowedActors = (env.VERA_DEEPSEEK_ALLOWED_ACTORS || '').split(',')
    .map(actor => actor.trim()).filter(Boolean);
  const req = requestFromEvent(event, allowedActors);
  if (!env.GITHUB_TOKEN) throw new Error('Missing GitHub issue-read token');
  const cap = taskCap(env.VERA_DEEPSEEK_TASK_CAP_USD);
  verifyCurrentIssue(await fetchIssue(env.GITHUB_TOKEN, req.issue), req.issue);
  if (env.VERA_DEEPSEEK_DRY_RUN === 'true') {
    console.log('DeepSeek dispatch dry run: issue #' + req.issue +
                ', actor approved, labels valid, task cap set. NO provider call or receipt.');
    return;
  }

  const runner = join(homedir(), '.codex', 'bin', 'vera-deepseek-runner');
  const st = statSync(runner); // Refuse if private wrapper is not installed.
  if (!st.isFile() || (st.mode & 0o111) === 0 || (st.mode & 0o022) !== 0 ||
      (typeof process.getuid === 'function' && st.uid !== process.getuid())) {
    throw new Error('Private runner must be owner-owned, executable, and not group/world-writable');
  }

  // Reserve before any possibility of provider usage. An issue is dispatched
  // at most once until a human reconciles and explicitly resets its receipt.
  const receipt = reserveReceipt(
    join(homedir(), '.codex', 'deepseek-dispatch-receipts'),
    req.issue, req.commentId
  );
  const childEnv = {
    HOME: homedir(),
    PATH: env.PATH || '/usr/bin:/bin',
    VERA_REPOSITORY: REPO,
    VERA_ISSUE_NUMBER: String(req.issue),
    VERA_DISPATCH_COMMENT_ID: String(req.commentId),
    VERA_DEEPSEEK_TASK_CAP_USD: String(cap),
    VERA_DEEPSEEK_CAMPAIGN_CAP_USD: '10',
    VERA_DEEPSEEK_RECEIPT: receipt
  };
  // No GITHUB_TOKEN or workflow secrets reach the DeepSeek process.
  const result = spawnSync(runner, [String(req.issue), String(req.commentId)], {
    env: childEnv, shell: false, stdio: 'inherit', timeout: 40 * 60 * 1000
  });
  const state = result.error || result.status !== 0 ? 'uncertain-or-failed' : 'worker-returned';
  // Never claim technical acceptance or PR delivery from this result.
  writeFileSync(receipt, JSON.stringify({
    issue: req.issue, commentId: req.commentId, state,
    timestamp: new Date().toISOString(),
    exitCode: result.status ?? null,
    detail: result.error?.code || null
  }, null, 2) + '\n', { mode: 0o600 });
  if (state !== 'worker-returned') throw new Error('Private worker failed or timed out: manual reconciliation required');
  console.log('DeepSeek worker returned for issue #' + req.issue +
              '; Sol integration, reviews and cloud CI remain separate.');
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch(error => {
    console.error('DeepSeek dispatch refused: ' + error.message);
    process.exitCode = 1;
  });
}
