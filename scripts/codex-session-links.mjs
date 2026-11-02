/**
 * #399: read-only, Mac-local Codex desktop link correlation.
 *
 * This module does not register, launch, resume, or probe any Codex session.
 * Records are private user-attested associations, not evidence that an agent is
 * currently running, that an issue is approved, or that a browser URL exists.
 */
import { lstat, readFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import path from 'node:path';

const UUID = '[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}';
const LOCAL_LINK = new RegExp(`^codex://threads/(${UUID})$`);
const GITHUB_ISSUE = /^https:\/\/github\.com\/([a-zA-Z0-9-]+)\/([a-zA-Z0-9_.-]+)\/issues\/([1-9][0-9]*)$/;
const CHAT_WEB = /^https:\/\/chatgpt\.com\/c\/[a-zA-Z0-9_-]{8,128}$/;
const INSTALLATION = /^[A-Za-z0-9._-]{3,128}$/;
const MAX_RECORDS = 5000;

export const DEFAULT_MAPPING_PATH = path.join(
  homedir(), 'Library', 'Application Support', 'VERA', 'codex-session-links', 'codex-thread-map.v1.json',
);

/** Exact existing-local-thread link only. Syntax != trusted provenance. */
export function parseLocalCodexLink(raw) {
  if (typeof raw !== 'string') return null;
  const match = LOCAL_LINK.exec(raw);
  if (!match) return null;
  const threadId = match[1].toLowerCase();
  return { threadId, appUrl: `codex://threads/${threadId}` };
}

/** Canonical issue identity includes owner AND repo (issue number alone is unsafe). */
export function canonicalIssueKey(raw) {
  if (typeof raw !== 'string') return null;
  const match = GITHUB_ISSUE.exec(raw);
  if (!match || match[2] === '.' || match[2] === '..') return null;
  const num = Number(match[3]);
  if (!Number.isSafeInteger(num)) return null;
  return `${match[1].toLowerCase()}/${match[2].toLowerCase()}#${num}`;
}

function isTimestamp(raw) {
  return typeof raw === 'string' && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z$/.test(raw)
    && Number.isFinite(Date.parse(raw));
}

/** Fail closed on a corrupt mapping file; never partially trust its records. */
export function parseSessionMapping(raw) {
  const data = typeof raw === 'string' ? JSON.parse(raw) : raw;
  if (!data || Array.isArray(data) || typeof data !== 'object' || data.version !== 1
    || typeof data.installationId !== 'string' || !INSTALLATION.test(data.installationId)
    || !Array.isArray(data.mappings) || data.mappings.length > MAX_RECORDS) {
    throw new Error('Invalid VERA local Codex mapping schema');
  }
  for (const entry of data.mappings) {
    if (!entry || Array.isArray(entry) || typeof entry !== 'object'
      || !canonicalIssueKey(entry.issueUrl)
      || !['primary', 'secondary', 'history'].includes(entry.role)
      || !['codex-local', 'codex-cloud', 'chatgpt-web'].includes(entry.surface)) {
      throw new Error('Invalid VERA local Codex mapping record');
    }
    // Validate independent browser evidence even if no desktop link exists.
    if (entry.browserUrl != null && (
      typeof entry.browserUrl !== 'string' || !CHAT_WEB.test(entry.browserUrl)
      || entry.browserProvenance?.method !== 'producer-confirmed-existing'
      || !isTimestamp(entry.browserProvenance?.confirmedAt)
      || (entry.surface === 'codex-local'
        && entry.browserProvenance?.relation !== 'same-thread')
      || entry.surface === 'codex-cloud')) {
      throw new Error('Invalid or unverified browser conversation fallback');
    }
  }
  return data;
}

/** Loader is READ-ONLY. Missing and unusable files become inert error states. */
export async function loadLocalCodexSessionMap(filePath = DEFAULT_MAPPING_PATH) {
  try {
    const directory = await lstat(path.dirname(filePath));
    if (!directory.isDirectory() || (directory.mode & 0o077) !== 0
      || (typeof process.getuid === 'function' && directory.uid !== process.getuid())) {
      return { mappings: [], error: 'Private mapping directory must be a regular owner-only directory (mode 0700)' };
    }
    const info = await lstat(filePath);
    if (!info.isFile() || (info.mode & 0o077) !== 0
      || (typeof process.getuid === 'function' && info.uid !== process.getuid())) {
      return { mappings: [], error: 'Private mapping file must be a regular owner-only file (mode 0600)' };
    }
    const data = parseSessionMapping(await readFile(filePath, 'utf8'));
    return { ...data, error: null };
  } catch (error) {
    if (error?.code === 'ENOENT') return { mappings: [], error: null };
    return { mappings: [], error: 'Local session mapping unavailable or invalid' };
  }
}

function browserUrlFor(record) {
  // A known web URL alone is NOT evidence that it resumes the same local thread.
  const permittedSurface = record?.surface === 'chatgpt-web'
    || (record?.surface === 'codex-local'
      && record.browserProvenance?.relation === 'same-thread');
  return permittedSurface && record?.browserUrl && CHAT_WEB.test(record.browserUrl)
    && record.browserProvenance?.method === 'producer-confirmed-existing'
    && isTimestamp(record.browserProvenance?.confirmedAt)
    ? record.browserUrl : undefined;
}

function result(status, reason, other = {}) {
  return { status, reason, ...other };
}

/**
 * Produce inert link data for #401. App URL is never returned from syntax alone.
 * The caller supplies this Mac's independent installation ID; do not derive it
 * from the mapped file, or a copied file could self-attest to another machine.
 */
export function linksForIssue(issueUrl, snapshot, installationId) {
  const key = canonicalIssueKey(issueUrl);
  if (!key) return result('invalid', 'Invalid GitHub issue identity');
  const safeIssueUrl = `https://github.com/${key.split('#')[0]}/issues/${key.split('#')[1]}`;
  const issueLink = { issueUrl: safeIssueUrl };
  if (snapshot?.error) return result('invalid', 'Local Codex mapping file unavailable or invalid', issueLink);
  if (!snapshot || !Array.isArray(snapshot.mappings)) {
    return result('missing', 'No local Codex thread mapping loaded', issueLink);
  }
  // Resolve issue identity before checking local installation: an empty map is
  // "missing", and a separately confirmed web conversation is device-independent.
  // A malformed matching record or duplicate current primary is never guessed.
  const matches = snapshot.mappings.filter((entry) => canonicalIssueKey(entry?.issueUrl) === key);
  if (matches.length === 0) return result('missing', 'No linked local Codex thread', issueLink);
  const primaries = matches.filter((entry) => entry.role === 'primary');
  if (primaries.length > 1) return result('ambiguous', 'Multiple primary sessions require manual selection', issueLink);
  if (primaries.length === 0) return result('missing', 'No primary local Codex thread selected', issueLink);
  const selected = primaries[0];
  const browserUrl = browserUrlFor(selected);
  const fallback = { ...issueLink, ...(browserUrl ? { browserUrl } : {}) };
  if (selected.surface === 'chatgpt-web') return result('web-only', 'ChatGPT web conversation is not a local Codex thread', fallback);
  if (selected.surface === 'codex-cloud') return result('cloud-only', 'Cloud task is not a local Codex thread', fallback);
  if (selected.surface !== 'codex-local') return result('invalid', 'Unknown session type', fallback);
  if (!installationId || !INSTALLATION.test(installationId)
    || snapshot.installationId !== installationId) {
    return result('wrong-device', 'Mapping has not been verified for this Mac', fallback);
  }
  const parsed = parseLocalCodexLink(selected.deepLink);
  if (!parsed || (selected.threadId != null && (typeof selected.threadId !== 'string'
    || selected.threadId.toLowerCase() !== parsed.threadId))) {
    return result('invalid', 'Local Codex deep link missing or malformed', fallback);
  }
  if (selected.verification?.state === 'stale') return result('stale', 'Local session association needs reconfirmation', fallback);
  if (selected.provenance?.method !== 'desktop-copy-deeplink'
    || selected.provenance?.confirmedBy !== 'producer'
    || !isTimestamp(selected.provenance?.capturedAt)
    || selected.verification?.state !== 'producer-confirmed-existing'
    || !isTimestamp(selected.verification?.checkedAt)) {
    return result('unverified', 'Local Codex thread association is not Producer-confirmed', fallback);
  }
  return result('verified-local', 'Producer-confirmed local thread; availability not checked live', {
    ...fallback, ...parsed, lastConfirmedAt: selected.verification.checkedAt,
  });
}
