import { createHash } from 'node:crypto';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);
export const CHAT_APPROVAL_LABEL = 'chat-reviewed';
export const CHAT_PENDING_LABEL = 'chat-review-pending';
export const CHAT_APPROVAL_MARKER = 'VERA_CHAT_REVIEW_V1';
export const CHAT_REVIEW_PROMPT_VERSION = '1';
export const DEFAULT_PRODUCER = 'mbelinkie';

export function parseIssueUrl(url) {
  const match = /^https:\/\/github\.com\/(mbelinkie)\/(vera-script-to-timeline|vera-research-video-clips)\/issues\/([1-9]\d*)(?:\/?(?:[?#].*)?)?$/i.exec(url || '');
  if (!match) throw new Error('Expected a VERA GitHub issue URL in one of the two authorized repositories');
  return {
    owner: match[1].toLowerCase(), repo: match[2].toLowerCase(), number: Number(match[3]),
    url: `https://github.com/${match[1].toLowerCase()}/${match[2].toLowerCase()}/issues/${match[3]}`,
  };
}

// A review approves the issue's actual *title and body*, not its changing
// comment count, Project fields, or updatedAt (including label edits).
export function issueRevision(title, body) {
  if (typeof title !== 'string' || typeof body !== 'string') throw new Error('Issue title/body unavailable; review cannot be verified');
  return createHash('sha256').update(JSON.stringify([title, body]), 'utf8').digest('hex');
}

export function reviewPrompt(url) {
  const issue = parseIssueUrl(url);
  return [
    'VERA human-guided GitHub issue review — prompt v' + CHAT_REVIEW_PROMPT_VERSION,
    'Issue: ' + issue.url,
    '',
    'Read the CURRENT issue title, full body, labels, scope, prerequisites, and relevant repo context.',
    'Discuss with me: goal/value; browser-first milestone fit; Chat-reviewed-before-Codex rule; dependent issues; previously accepted design; scope and exclusions; exact testable acceptance; risk/permissions/cost; and opportunities to reduce Codex tokens.',
    'Identify contradictions and propose concrete edits; do not change the issue until I specifically ask.',
    'Work iteratively: ask me about unresolved product decisions, incorporate my feedback, and show me the final proposed issue text and readiness assessment.',
    'NEVER declare the review complete, post approval, apply chat-reviewed, move the issue to Ready, or start Codex unless I explicitly confirm: "I approve this Chat review for ' + issue.repo + '#' + issue.number + '."',
    'After that explicit confirmation, verify the current GitHub title/body, post a concise public review summary, and record the versioned issue-revision approval using the repo review helper. If GitHub write access is unavailable, give me the local approval instructions. Do not claim a GitHub write succeeded without verification.',
    'Reviewing is not dispatch. Do not write code, run the issue implementation, merge a PR, or bypass dependency/Producer-release approval rules.',
  ].join('\n');
}

export function reviewChatUrl(url) {
  return 'https://chatgpt.com/?prompt=' + encodeURIComponent(reviewPrompt(url));
}

export function approvalComment({ title, body, producer, summary, reviewedAt = new Date().toISOString() }) {
  if (!summary || !String(summary).trim()) throw new Error('Public review summary is required');
  if (!producer || !/^[A-Za-z0-9-]+$/.test(producer)) throw new Error('A GitHub producer login is required');
  const record = {
    revision: issueRevision(title, body),
    producer,
    reviewedAt,
    promptVersion: CHAT_REVIEW_PROMPT_VERSION,
  };
  return `<!-- ${CHAT_APPROVAL_MARKER} ${JSON.stringify(record)} -->\n` +
    `**VERA Chat review: Producer approved** (${reviewedAt})\n\n` +
    `${String(summary).trim()}\n\n` +
    `This review authorizes a current issue to be considered for Codex claiming; it does not dispatch the task, approve implementation or close a release milestone.`;
}

export function parseApprovalComment(comment, producer = DEFAULT_PRODUCER) {
  if (comment?.author?.login?.toLowerCase() !== producer.toLowerCase()) return null;
  if (typeof comment.body !== 'string') return null;
  const match = comment.body.match(new RegExp(`<!-- ${CHAT_APPROVAL_MARKER} (\\{[^\\n]*\\}) -->`));
  if (!match) return null;
  try {
    const record = JSON.parse(match[1]);
    if (record.producer?.toLowerCase() !== producer.toLowerCase()
      || record.promptVersion !== CHAT_REVIEW_PROMPT_VERSION
      || !/^[0-9a-f]{64}$/.test(record.revision)
      || !Number.isFinite(Date.parse(record.reviewedAt))) return null;
    return { ...record, url: comment.url ?? null };
  } catch { return null; }
}

export function evaluateChatReview(issue, producer = DEFAULT_PRODUCER) {
  const labels = (issue?.labels ?? []).map(l => typeof l === 'string' ? l : l?.name).filter(Boolean);
  if (!labels.includes(CHAT_APPROVAL_LABEL)) {
    return { status: labels.includes(CHAT_PENDING_LABEL) ? 'in-review' : 'not-reviewed', approved: false };
  }
  const comments = (issue.comments ?? []).map(c => parseApprovalComment(c, producer)).filter(Boolean);
  if (!comments.length) return { status: 'unverified', approved: false };
  // The latest Producer review supersedes earlier comments, even if the issue changed.
  const latest = comments.sort((a,b) => Date.parse(b.reviewedAt) - Date.parse(a.reviewedAt))[0];
  let digest;
  try { digest = issueRevision(issue.title, issue.body ?? ''); }
  catch { return { status: 'unverified', approved: false }; }
  const approved = latest.revision === digest;
  return { status: approved ? 'approved' : 'outdated', approved, record: latest, url: latest.url };
}

export function assertChatReviewApproved(issue, producer = DEFAULT_PRODUCER) {
  const result = evaluateChatReview(issue, producer);
  if (!result.approved) throw new Error(
    `Codex claim blocked: issue #${issue.number ?? '?'} has no current Producer-approved Chat review (${result.status}). Open the dashboard's Review in ChatGPT action; the Producer must approve explicitly.`
  );
  return result;
}

function graphqlText(value) { return JSON.stringify(value); }
export function chatReviewQuery(batch) {
  const byRepo = new Map();
  for (const entry of batch) {
    const p = parseIssueUrl(entry.url);
    const key = p.owner + '/' + p.repo;
    if (!byRepo.has(key)) byRepo.set(key, []);
    byRepo.get(key).push(p);
  }
  let i = 0;
  const repos = [...byRepo.entries()].map(([repo, issues]) => {
    const [owner, name] = repo.split('/');
    return `r${i++}: repository(owner:${graphqlText(owner)},name:${graphqlText(name)}) { ` +
      issues.map((p, k) => `i${k}: issue(number:${p.number}) { title body labels(first:100) { nodes { name } } comments(last:100) { nodes { body url author { login } } } }`).join(' ') + ' }';
  });
  return `query ChatReviewAudit { ${repos.join(' ')} rateLimit { limit remaining used resetAt cost } }`;
}

export function parseChatReviewGraphql(batch, response, producer = DEFAULT_PRODUCER) {
  const output = {};
  if (!response?.data || response.errors?.length) throw new Error('Chat review GraphQL response was incomplete');
  const groupOrder = [];
  for (const b of batch) {
    const p = parseIssueUrl(b.url);
    const key = p.owner + '/' + p.repo;
    let g = groupOrder.find(x => x.key === key);
    if (!g) { g = { key, items: [] }; groupOrder.push(g); }
    g.items.push(p);
  }
  groupOrder.forEach((g, index) => {
    const repo = response.data[`r${index}`];
    if (!repo) throw new Error('Chat review repository data unavailable');
    g.items.forEach((p, i) => {
      const issue = repo[`i${i}`];
      if (!issue) throw new Error('Chat review issue unavailable: ' + p.url);
      output[p.url.toLowerCase()] = evaluateChatReview({
        ...issue,
        comments: issue.comments?.nodes ?? [],
        labels: issue.labels?.nodes ?? [],
      }, producer);
    });
  });
  return output;
}

// Audits only issues whose Project snapshot carries a review label. Other
// issues need no comment/body API calls. An audit failure fails closed.
export async function fetchChatReviewSnapshot(repositoryRoot, models, options = {}) {
  const candidates = new Map();
  for (const model of models) for (const item of [...(model.goals ?? []), ...(model.workItems ?? [])]) {
    if (!item.url || !item.chatReviewLabels?.includes(CHAT_APPROVAL_LABEL)) continue;
    try { candidates.set(parseIssueUrl(item.url).url.toLowerCase(), item); } catch { /* ignore historical items */ }
  }
  const states = {}, errors = [];
  const entries = [...candidates.values()];
  for (let start = 0; start < entries.length; start += 15) {
    const batch = entries.slice(start, start + 15);
    try {
      const { stdout } = await (options.execFileAsync ?? execFileAsync)('gh', [
        'api', 'graphql', '-f', `query=${chatReviewQuery(batch)}`,
      ], { cwd: repositoryRoot, maxBuffer: 16 * 1024 * 1024 });
      Object.assign(states, parseChatReviewGraphql(batch, JSON.parse(stdout), options.producer ?? DEFAULT_PRODUCER));
    } catch (error) {
      errors.push(`Chat review audit unavailable for ${batch.length} issues; approval cannot be verified: ${error instanceof Error ? error.message : String(error)}`);
    }
  }
  return { states, errors };
}

export function chatStateForItem(item, snapshot = {}) {
  const labels = item.chatReviewLabels ?? [];
  if (labels.includes(CHAT_APPROVAL_LABEL)) {
    return snapshot[item.url?.toLowerCase()] ?? { status: 'unverified', approved: false };
  }
  return { status: labels.includes(CHAT_PENDING_LABEL) ? 'in-review' : 'not-reviewed', approved: false };
}
