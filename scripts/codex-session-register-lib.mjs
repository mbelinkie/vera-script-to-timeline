/**
 * Explicit, local-only registration of an EXISTING Codex desktop thread.
 * Never calls Codex, launches the app, or infers a thread from local history.
 */
import { randomUUID } from 'node:crypto';
import { open, lstat, mkdir, readFile, rename, unlink } from 'node:fs/promises';
import path from 'node:path';
import {
  canonicalIssueKey, parseLocalCodexLink, parseSessionMapping,
  DEFAULT_MAPPING_PATH,
} from './codex-session-links.mjs';

const INSTALL_ID_NAME = 'codex-installation-id.v1';
const INSTALL_ID_RE = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/;

export function defaultInstallationIdPath(mappingPath = DEFAULT_MAPPING_PATH) {
  return path.join(path.dirname(mappingPath), INSTALL_ID_NAME);
}

function checkOwnerOnly(info, kind) {
  if ((kind === 'file' && !info.isFile()) || (kind === 'directory' && !info.isDirectory())
    || (info.mode & 0o077) !== 0
    || (typeof process.getuid === 'function' && info.uid !== process.getuid())) {
    throw new Error(`Local ${kind} must be a regular owner-only ${kind} (0700 directory / 0600 file)`);
  }
}

async function readPrivateFile(filePath) {
  try {
    const info = await lstat(filePath);
    checkOwnerOnly(info, 'file');
    return await readFile(filePath, 'utf8');
  } catch (error) {
    if (error?.code === 'ENOENT') return null;
    throw error;
  }
}

async function ensurePrivateDirectory(directory) {
  await mkdir(directory, { recursive: true, mode: 0o700 });
  checkOwnerOnly(await lstat(directory), 'directory');
}

async function writePrivateAtomic(filePath, contents) {
  const temporary = path.join(path.dirname(filePath), `.${path.basename(filePath)}.${randomUUID()}.tmp`);
  let handle;
  try {
    handle = await open(temporary, 'wx', 0o600);
    await handle.writeFile(contents, 'utf8');
    await handle.sync();
    await handle.close();
    handle = undefined;
    await rename(temporary, filePath);
  } finally {
    await handle?.close();
    await unlink(temporary).catch((error) => { if (error?.code !== 'ENOENT') throw error; });
  }
}

/** Independent read-only device identity source for dashboard generation. */
export async function readLocalInstallationId(filePath = defaultInstallationIdPath()) {
  try {
    const raw = await readPrivateFile(filePath);
    if (raw === null) return null;
    const id = raw.trim();
    return INSTALL_ID_RE.test(id) ? id : null;
  } catch {
    return null;
  }
}

/**
 * Only call after an interactive Producer confirmation of issue + pasted link.
 * Replacing a primary session requires an additional, explicit approval flag.
 * A failed preflight must never overwrite the existing private file.
 */
export async function registerLocalCodexThread({
  issueUrl, deepLink, confirmed = false, replaceExisting = false,
  mappingPath = DEFAULT_MAPPING_PATH,
  installationIdPath = defaultInstallationIdPath(mappingPath),
  now = () => new Date().toISOString(),
} = {}) {
  if (confirmed !== true) throw new Error('Explicit Producer confirmation is required');
  const issueKey = canonicalIssueKey(issueUrl);
  const session = parseLocalCodexLink(deepLink);
  if (!issueKey || !session) throw new Error('Expected an exact GitHub issue URL and copied existing Codex thread deep link');
  if (path.dirname(mappingPath) !== path.dirname(installationIdPath)) {
    throw new Error('Installation identity and mapping must be in the same private directory');
  }
  // Check before writing anything. The existing directory, if any, must be private.
  await ensurePrivateDirectory(path.dirname(mappingPath));
  const lockPath = `${mappingPath}.lock`;
  let lock;
  try {
    try { lock = await open(lockPath, 'wx', 0o600); }
    catch (error) {
      if (error?.code === 'EEXIST') throw new Error('Another local registration is in progress (or a stale lock needs manual inspection)');
      throw error;
    }
    const [existingRaw, identityRaw] = await Promise.all([
      readPrivateFile(mappingPath), readPrivateFile(installationIdPath),
    ]);
    const existing = existingRaw === null ? null : parseSessionMapping(existingRaw);
    const installationId = identityRaw === null ? randomUUID() : identityRaw.trim();
    if (!INSTALL_ID_RE.test(installationId)) throw new Error('Existing local installation identity is invalid');
    if (existing && existing.installationId !== installationId) {
      throw new Error('Mapping belongs to a different local installation');
    }
    const mappings = existing?.mappings ?? [];
    const primaries = mappings.filter((entry) => entry.role === 'primary'
      && canonicalIssueKey(entry.issueUrl) === issueKey);
    if (primaries.length > 1) throw new Error('Ambiguous existing primary session; manual repair required');
    const current = primaries[0];
    const sameThread = current && parseLocalCodexLink(current.deepLink)?.threadId === session.threadId;
    if (current && !sameThread && !replaceExisting) {
      throw new Error('Existing primary session differs; explicit replacement confirmation required');
    }
    const checkedAt = now();
    if (typeof checkedAt !== 'string' || !Number.isFinite(Date.parse(checkedAt))) {
      throw new Error('Invalid registration time');
    }
    const record = {
      issueUrl: `https://github.com/${issueKey.split('#')[0]}/issues/${issueKey.split('#')[1]}`,
      surface: 'codex-local', role: 'primary', deepLink: session.appUrl,
      provenance: { method: 'desktop-copy-deeplink', confirmedBy: 'producer', capturedAt: checkedAt },
      verification: { state: 'producer-confirmed-existing', checkedAt },
      ...(sameThread && current.browserUrl
        ? { browserUrl: current.browserUrl, browserProvenance: current.browserProvenance } : {}),
    };
    const nextMappings = mappings.filter((entry) => entry !== current).map((entry) => ({ ...entry }));
    if (current && !sameThread) {
      nextMappings.push({ ...current, role: 'history' });
    }
    nextMappings.push(record);
    const next = parseSessionMapping({ version: 1, installationId, mappings: nextMappings });
    // Do not turn user attestation into a claim that the actual app was probed.
    if (identityRaw === null) await writePrivateAtomic(installationIdPath, installationId + '\n');
    await writePrivateAtomic(mappingPath, JSON.stringify(next, null, 2) + '\n');
    return { issueKey, threadSuffix: session.threadId.slice(-8), replacedPrimary: !!current,
      recordedAt: checkedAt, mappingPath };
  } finally {
    await lock?.close();
    if (lock) await unlink(lockPath);
  }
}
