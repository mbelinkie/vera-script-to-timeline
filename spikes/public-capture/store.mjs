import { constants } from 'node:fs';
import { mkdir, open, rename, readdir, lstat, realpath } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';
import path from 'node:path';
import { PNG } from 'pngjs';
import { PROFILE, hash, json, requireSafe } from './profile.mjs';

export async function syncDirectory(directory) {
  const fd = await open(directory, constants.O_RDONLY);
  try { await fd.sync(); } finally { await fd.close(); }
}
export async function writeNew(file, bytes) {
  const fd = await open(file, constants.O_CREAT | constants.O_EXCL | constants.O_WRONLY | constants.O_NOFOLLOW, 0o600);
  try { await fd.writeFile(bytes); await fd.sync(); } finally { await fd.close(); }
}
async function safeRead(file) {
  const fd = await open(file, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const info = await fd.stat();
    requireSafe(info.isFile() && info.size <= PROFILE.limits.rasterBytes * 2, 'store_file_denied');
    return await fd.readFile();
  } finally { await fd.close(); }
}

export function verifyPng(bytes) {
  requireSafe(bytes.length >= 33 && bytes.length <= PROFILE.limits.rasterBytes &&
    bytes.subarray(0, 8).equals(Buffer.from('89504e470d0a1a0a', 'hex')) &&
    bytes.readUInt32BE(8) === 13 && bytes.toString('ascii', 12, 16) === 'IHDR', 'raster_format_denied');
  // Chromium emits non-interlaced 8-bit RGB(A). Reject alternate decode paths
  // (including pngjs's unbounded interlaced inflate) before invoking a decoder.
  requireSafe(bytes[24] === 8 && [2, 6].includes(bytes[25]) && bytes[26] === 0 &&
    bytes[27] === 0 && bytes[28] === 0, 'raster_encoding_denied');
  let offset = 8, chunks = 0, ended = false;
  while (offset + 12 <= bytes.length) {
    const length = bytes.readUInt32BE(offset);
    const type = bytes.toString('ascii', offset + 4, offset + 8);
    requireSafe(++chunks <= 128 && length <= bytes.length - offset - 12 &&
      ['IHDR', 'IDAT', 'IEND', 'sRGB', 'gAMA', 'cHRM', 'pHYs'].includes(type) &&
      (type !== 'IHDR' || offset === 8), 'raster_chunk_denied');
    offset += length + 12;
    if (type === 'IEND') { requireSafe(length === 0 && offset === bytes.length, 'raster_trailing_bytes'); ended = true; break; }
  }
  requireSafe(ended, 'raster_incomplete');
  const width = bytes.readUInt32BE(16), height = bytes.readUInt32BE(20);
  requireSafe(width === PROFILE.viewport.width && height === PROFILE.viewport.height &&
    width * height <= PROFILE.limits.pixels, 'raster_dimensions_denied');
  let decoded;
  try { decoded = PNG.sync.read(bytes, { checkCRC: true }); } catch { requireSafe(false, 'raster_decoder_failure'); }
  requireSafe(decoded.width === width && decoded.height === height && decoded.data.length === width * height * 4, 'raster_decoder_failure');
  return { id: `sha256:${hash(bytes)}`, sha256: hash(bytes), byteLength: bytes.length,
    mime: 'image/png', width, height, decoder: 'pngjs/7.0.0 CRC+decode',
    color: 'srgb', alpha: decoded.alpha ? 'present' : 'opaque' };
}

export class LocalStore {
  constructor(root) { this.root = path.resolve(root); }
  async initialize() {
    await mkdir(this.root, { recursive: true, mode: 0o700 });
    const info = await lstat(this.root);
    requireSafe(info.isDirectory() && !info.isSymbolicLink() && (info.mode & 0o077) === 0 && info.uid === process.getuid(), 'store_must_be_private_owned_directory');
    this.root = await realpath(this.root);
    for (const name of ['commits', 'staging', 'jobs', 'audit']) {
      await mkdir(path.join(this.root, name), { mode: 0o700 }).catch((error) => { if (error.code !== 'EEXIST') throw error; });
      const child = await lstat(path.join(this.root, name));
      requireSafe(child.isDirectory() && !child.isSymbolicLink() && (child.mode & 0o077) === 0, 'store_directory_denied');
    }
  }
  async locked(work) {
    await this.initialize();
    const helper = spawn('/usr/bin/python3', [fileURLToPath(new URL('./lock.py', import.meta.url)), path.join(this.root, 'writer.lock')],
      { stdio: ['pipe', 'pipe', 'pipe'], env: { PATH: '/usr/bin:/bin' } });
    const exited = once(helper, 'exit');
    const ready = await Promise.race([once(helper.stdout, 'data').then(([data]) => data.toString() === 'locked\n'), exited.then(() => false)]);
    requireSafe(ready, 'store_busy_or_lock_unavailable');
    try { return await work(); }
    finally { helper.stdin.end(); await exited; }
  }
  async atomicRecord(relative, value) {
    const temp = path.join(this.root, 'staging', `${randomUUID()}.record`);
    await writeNew(temp, json(value));
    const target = path.join(this.root, relative);
    await lstat(target).then(() => requireSafe(false, 'immutable_record_exists'), (error) => { if (error.code !== 'ENOENT') throw error; });
    await rename(temp, target);
    await syncDirectory(path.dirname(target));
  }
  async audit(type, identities, result) {
    await this.atomicRecord(`audit/${randomUUID()}.json`, { type, ...identities,
      actor: 'local-operator', projectId: 'local-spike', policy: PROFILE.id,
      at: new Date().toISOString(), result });
  }
  async readRecord(relative) {
    try { return JSON.parse(await safeRead(path.join(this.root, relative))); }
    catch (error) { if (error.code === 'ENOENT') return null; throw error; }
  }
  async history() {
    const records = [];
    for (const directory of (await readdir(path.join(this.root, 'commits'))).sort()) {
      requireSafe(/^\d{6}-[a-f0-9-]{36}$/.test(directory), 'invalid_commit_directory');
      const dirInfo = await lstat(path.join(this.root, 'commits', directory));
      requireSafe(dirInfo.isDirectory() && !dirInfo.isSymbolicLink(), 'commit_directory_denied');
      const commit = await this.readRecord(`commits/${directory}/commit.json`);
      const provenanceBytes = await safeRead(path.join(this.root, 'commits', directory, 'provenance.json'));
      requireSafe(commit && hash(provenanceBytes) === commit.provenance.sha256, 'provenance_integrity_failure');
      const receipt = JSON.parse(provenanceBytes);
      const artifactPath = commit.artifact.path;
      requireSafe(/^commits\/\d{6}-[a-f0-9-]{36}\/artifact.png$/.test(artifactPath), 'artifact_path_denied');
      const parent = await lstat(path.dirname(path.join(this.root, artifactPath)));
      requireSafe(parent.isDirectory() && !parent.isSymbolicLink(), 'artifact_directory_denied');
      const raster = await safeRead(path.join(this.root, artifactPath));
      const artifact = verifyPng(raster);
      requireSafe(artifact.sha256 === commit.artifact.sha256 && artifact.byteLength === commit.artifact.byteLength &&
        receipt.identity.revisionId === commit.revisionId && receipt.identity.jobId === commit.jobId &&
        receipt.output.artifact.sha256 === artifact.sha256, 'artifact_integrity_failure');
      records.push({ directory, commit, receipt, raster });
    }
    return records;
  }
  async publish({ directory, receipt, raster, reuse, hit }) {
    const stage = path.join(this.root, 'staging', directory);
    await mkdir(stage, { mode: 0o700 });
    if (!reuse) await writeNew(path.join(stage, 'artifact.png'), raster);
    await hit('after-artifact-stage');
    const provenance = json(receipt);
    await writeNew(path.join(stage, 'provenance.json'), provenance);
    await hit('after-provenance-stage');
    const commit = {
      revisionId: receipt.identity.revisionId, revisionNumber: receipt.identity.revisionNumber,
      jobId: receipt.identity.jobId, attemptId: receipt.identity.attemptId,
      artifact: { ...receipt.output.artifact, path: reuse?.commit.artifact.path ?? `commits/${directory}/artifact.png` },
      provenance: { id: receipt.identity.provenanceId, sha256: hash(provenance), byteLength: provenance.length, mime: 'application/json' },
      status: receipt.honesty.classification, result: 'committed',
    };
    await writeNew(path.join(stage, 'commit.json'), json(commit));
    await syncDirectory(stage);
    await hit('before-publish');
    const stagedProvenance = await safeRead(path.join(stage, 'provenance.json'));
    const stagedRaster = await safeRead(reuse ? path.join(this.root, reuse.commit.artifact.path) : path.join(stage, 'artifact.png'));
    requireSafe(stagedProvenance.equals(provenance) && stagedRaster.equals(raster), 'staged_integrity_failure');
    verifyPng(stagedRaster);
    requireSafe(Date.now() < receipt.lease.expiresAtMs, 'lease_expired');
    await rename(stage, path.join(this.root, 'commits', directory));
    await syncDirectory(path.join(this.root, 'commits'));
    await hit('after-publish');
    return commit;
  }
}
