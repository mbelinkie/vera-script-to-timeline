#!/usr/bin/env node
// Producer-only interactive approval. This is a manual fallback when ChatGPT
// cannot write to GitHub. It never approves on a dashboard click or chat launch.
import { createInterface } from 'node:readline/promises';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { pathToFileURL } from 'node:url';
import {
  approvalComment, assertChatReviewApproved, CHAT_APPROVAL_LABEL,
  DEFAULT_PRODUCER, evaluateChatReview, parseIssueUrl, chatReviewQuery,
  parseChatReviewGraphql,
} from './chat-review-lib.mjs';
const execFileAsync = promisify(execFile);

async function gh(args) {
  const { stdout } = await execFileAsync('gh', args, { maxBuffer: 6 * 1024 * 1024 });
  return JSON.parse(stdout);
}

function argsMap(argv) {
  const result = {};
  for (let i = 0; i < argv.length; i++) {
    if (!argv[i].startsWith('--') || !argv[i + 1]) throw new Error('Expected --issue URL and, for approve, --summary TEXT');
    result[argv[i].slice(2)] = argv[++i];
  }
  return result;
}

async function liveAudit(issue) {
  const data = await gh(['api', 'graphql', '-f', `query=${chatReviewQuery([issue])}`]);
  return parseChatReviewGraphql([issue], data)[issue.url.toLowerCase()];
}

export async function main(argv = process.argv.slice(2)) {
  const [action, ...rest] = argv;
  if (!['approve', 'verify'].includes(action)) throw new Error('Usage: node scripts/chat-review-approval.mjs <approve|verify> --issue https://github.com/mbelinkie/REPO/issues/N [--summary "..."]');
  const flags = argsMap(rest);
  const issue = parseIssueUrl(flags.issue);
  if (action === 'verify') {
    const result = await liveAudit(issue);
    console.log(`${issue.url}: ${result.status}`);
    if (!result.approved) process.exitCode = 1;
    return;
  }

  if (!process.stdin.isTTY || !process.stdout.isTTY) {
    throw new Error('Producer approval requires an interactive terminal; agents and scripts cannot auto-approve');
  }
  if (!flags.summary?.trim()) throw new Error('Approval requires --summary with a concise review outcome; do not paste private chat content');
  const login = await gh(['api', 'user']);
  if (login.login?.toLowerCase() !== DEFAULT_PRODUCER) throw new Error(`Only GitHub account ${DEFAULT_PRODUCER} can record the Producer approval`);
  const current = await gh(['api', `repos/${issue.owner}/${issue.repo}/issues/${issue.number}`]);
  if (current.state !== 'open') throw new Error('Only open issues can be newly approved');
  const existing = await liveAudit(issue);
  console.log(`\nIssue: ${issue.url}\nTitle: ${current.title}\nCurrent status: ${existing.status}`);
  console.log(`Your public review summary: ${flags.summary.trim()}`);
  console.log('This is NOT a release approval, implementation launch, or PR merge.');
  const required = `I approve this Chat review for ${issue.repo}#${issue.number}`;
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  let response;
  try { response = await rl.question(`\nType exactly: ${required}\n> `); }
  finally { rl.close(); }
  if (response !== required) throw new Error('Not approved; nothing was written to GitHub');
  const fresh = await gh(['api', `repos/${issue.owner}/${issue.repo}/issues/${issue.number}`]);
  if (fresh.title !== current.title || (fresh.body ?? '') !== (current.body ?? '')) {
    throw new Error('Issue changed during approval; review the current issue again. Nothing was written.');
  }
  const comment = approvalComment({ title: fresh.title, body: fresh.body ?? '', producer: DEFAULT_PRODUCER, summary: flags.summary });
  // Preserve existing labels. Adding a label to an issue is idempotent.
  await gh(['api', '-X', 'POST', `repos/${issue.owner}/${issue.repo}/issues/${issue.number}/comments`, '-f', `body=${comment}`]);
  await gh(['api', '-X', 'POST', `repos/${issue.owner}/${issue.repo}/issues/${issue.number}/labels`, '-f', `labels[]=${CHAT_APPROVAL_LABEL}`]);
  // A change to issue body after comment creation is detected here.
  const verified = await liveAudit(issue);
  if (!verified.approved) throw new Error(`GitHub write completed but review is ${verified.status}. Do not dispatch Codex.`);
  console.log(`Approved and verified: ${issue.url}. Dashboard will update on refresh.`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch(e => { console.error(e.message); process.exitCode = 1; });
}
