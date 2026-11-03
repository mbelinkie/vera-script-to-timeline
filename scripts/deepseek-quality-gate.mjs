// Read-only authorization for a separately approved local calibration episode.
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { verifyReviewFromGh } from './chat-review-github.mjs';
import { verifyCurrentIssue, REPO } from './deepseek-dispatch.mjs';
import { readPublicGh } from './deepseek-receiver.mjs';

const MARKER = '<!-- VERA_DEEPSEEK_QUALITY_V1 ';
const TARGETS = new Map([
  [1, 'scripts/fixtures/deepseek-quality/prefix/target.py'],
  [2, 'scripts/fixtures/deepseek-quality/validator/target.py'],
  [3, 'scripts/fixtures/deepseek-quality/run_policy/target.ts']
]);

export function qualityApprovalMetadata({ manifestSha, sourceSha, episodeIndex, target }) {
  if (!/^[a-f0-9]{64}$/.test(manifestSha || '') || !/^[a-f0-9]{40}$/.test(sourceSha || '') ||
      !TARGETS.has(episodeIndex) || TARGETS.get(episodeIndex) !== target) {
    throw new Error('Invalid calibration identity');
  }
  return {
    campaign: 'quality-2026-11-02-v1', manifestSha256: manifestSha, sourceSha,
    episodeIndex, target, taskCapUsd: '0.80', campaignCapUsd: '2.40',
    lifetimeCapUsd: '10', models: ['deepseek-v4-pro', 'deepseek-flash'],
    repeats: 2, maxOutputTokens: 65536, maxInputUnits: 20000, effort: 'high',
    verifiedRates: {
      'deepseek-v4-pro': {
        peak_cache_hit_usd_per_million: '0.044',
        peak_cache_miss_usd_per_million: '1.32',
        peak_output_usd_per_million: '3.96'
      },
      'deepseek-flash': {
        peak_cache_hit_usd_per_million: '0.006',
        peak_cache_miss_usd_per_million: '0.30',
        peak_output_usd_per_million: '1.20'
      }
    }
  };
}

function sameMetadata(actual, expected) {
  return actual && typeof actual === 'object' && !Array.isArray(actual) &&
    Object.keys(actual).length === Object.keys(expected).length &&
    Object.entries(expected).every(([key, value]) => JSON.stringify(actual[key]) === JSON.stringify(value));
}

function snapshot(issue) {
  return JSON.stringify({ title: issue.title, body: issue.body, state: issue.state,
    labels: issue.labels.map(label => typeof label === 'string' ? label : label.name).sort(),
    comments: issue.comments, updated_at: issue.updated_at });
}

export function verifyQualityApproval(readGh, { issue: number, ...identity }) {
  if (!Number.isSafeInteger(number) || number < 1) throw new Error('Invalid calibration issue');
  const expected = qualityApprovalMetadata(identity);
  const route = 'repos/' + REPO + '/issues/' + number;
  const issue = JSON.parse(readGh(['api', route]));
  verifyCurrentIssue(issue, number);
  const markers = [...issue.body.matchAll(/<!-- VERA_DEEPSEEK_QUALITY_V1 (\{[^\r\n]*\}) -->/g)];
  if (markers.length !== 1 || issue.body.split(MARKER).length !== 2 ||
      !sameMetadata(JSON.parse(markers[0][1]), expected)) {
    throw new Error('Calibration manifest, source or budget differs from the approved issue');
  }
  const review = verifyReviewFromGh(readGh, REPO, number, issue);
  const current = JSON.parse(readGh(['api', route]));
  verifyCurrentIssue(current, number);
  if (snapshot(current) !== snapshot(issue)) throw new Error('Calibration authorization changed');
  return { approved: true, issue: number, ...expected, reviewCommentId: review.commentId, revision: review.revision };
}

export function main(argv = process.argv.slice(2), readGh = readPublicGh) {
  if (argv.length !== 5 || !/^[1-9]\d*$/.test(argv[0]) || !/^[123]$/.test(argv[3])) {
    throw new Error('Expected issue, manifest SHA256, source SHA, episode index and fixture target');
  }
  return verifyQualityApproval(readGh, {
    issue: Number(argv[0]), manifestSha: argv[1], sourceSha: argv[2],
    episodeIndex: Number(argv[3]), target: argv[4]
  });
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    console.log(JSON.stringify(main()));
  } catch {
    console.error('Calibration approval refused; no job or provider request was made.');
    process.exitCode = 1;
  }
}
