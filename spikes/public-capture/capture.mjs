import { randomUUID } from 'node:crypto';
import { mkdir, lstat } from 'node:fs/promises';
import path from 'node:path';
import { PROFILE, PROFILE_HASH, hash, json, requireSafe } from './profile.mjs';
import { admitUrl } from './policy.mjs';
import { FixtureTransport, FIXTURE_URL, loadFixture } from './transport.mjs';
import { LocalStore, verifyPng, syncDirectory } from './store.mjs';
import { renderFixture } from './browser.mjs';

export async function capture({ root, command, fixtureName = 'article-v1', url = FIXTURE_URL,
  render = renderFixture, fixture, hit = async () => {} }) {
  requireSafe(typeof command === 'string' && /^[a-zA-Z0-9_-]{1,64}$/.test(command), 'command_key_denied');
  requireSafe(typeof url === 'string', 'url_type_denied');
  const store = new LocalStore(root);
  return store.locked(async () => {
    let intent = await store.readRecord('capture.json');
    if (!intent) {
      intent = { captureId: randomUUID(), projectId: 'local-spike', createdAt: new Date().toISOString(), profile: PROFILE.id };
      await store.atomicRecord('capture.json', intent);
      await store.audit('capture_created', { captureId: intent.captureId }, 'active-local-only');
    }
    // Hash rejected input only: never retain credentials from a denied URL.
    const settingsHash = hash(json({ urlDigest: hash(url), profile: PROFILE_HASH }));
    const keyDigest = hash(command);
    const jobId = hash(json({ captureId: intent.captureId, trigger: 'now', actor: 'local-operator', keyDigest, settingsHash }));
    const ids = { captureId: intent.captureId, jobId, requestId: jobId };
    const history = await store.history();
    const previousResult = history.find((row) => row.commit.jobId === jobId);
    if (previousResult) return { ...previousResult.commit, duplicate: true };
    const outcome = await store.readRecord(`jobs/${jobId}/outcome.json`);
    if (outcome) return { ...outcome, duplicate: true };
    const jobDirectory = path.join(store.root, 'jobs', jobId);
    const previousDirectory = await lstat(jobDirectory).catch((error) => { if (error.code !== 'ENOENT') throw error; return null; });
    if (previousDirectory) {
      requireSafe(previousDirectory.isDirectory() && !previousDirectory.isSymbolicLink(), 'job_directory_denied');
      // No automatic retry: a lost process is terminal unless its atomic commit
      // already appeared above. A new command explicitly requests a new run.
      const failed = { result: 'failed', jobId, code: 'abandoned_after_process_loss', revisionId: null };
      await store.atomicRecord(`jobs/${jobId}/outcome.json`, failed);
      const priorAttempt = await store.readRecord(`jobs/${jobId}/attempt.json`);
      await store.audit(priorAttempt ? 'attempt_abandoned' : 'job_abandoned', { ...ids, attemptId: priorAttempt?.attemptId ?? null }, failed.code);
      return failed;
    }
    await mkdir(jobDirectory, { mode: 0o700 });
    await syncDirectory(path.join(store.root, 'jobs'));
    await hit('after-job-directory');
    const requestedAt = new Date().toISOString();
    await store.atomicRecord(`jobs/${jobId}/request.json`, { ...ids, keyDigest, settingsHash, requestedAt, urlDigest: hash(url) });
    await store.audit('job_requested', ids, 'now');
    let attemptId = null;
    let transport;
    try {
      const admitted = admitUrl(url);
      const source = fixture ?? await loadFixture(fixtureName);
      transport = new FixtureTransport(source);
      const preflight = transport.topLevel(admitted.exact);
      await hit('after-admission');
      attemptId = randomUUID();
      const lease = { id: randomUUID(), epoch: 1, issuedAt: new Date().toISOString(),
        expiresAtMs: Date.now() + PROFILE.limits.leaseMs, scope: 'one-local-offline-attempt',
        renewals: [], retryCount: 0, maxRetries: 0 };
      const startedAt = new Date().toISOString();
      const cleanProfileId = randomUUID();
      await store.atomicRecord(`jobs/${jobId}/attempt.json`, { ...ids, attemptId, lease, startedAt, cleanProfileId });
      await store.audit('lease_issued', { ...ids, attemptId, leaseId: lease.id }, 'epoch-1');
      await store.audit('attempt_started', { ...ids, attemptId, leaseId: lease.id }, 'fresh-browser');
      await hit('before-browser');
      const output = await render({ transport, preflight, cleanProfileId });
      await hit('after-browser');
      requireSafe(Date.now() < lease.expiresAtMs, 'lease_expired');
      const artifact = verifyPng(output.raster);
      await store.audit('artifact_verified', { ...ids, attemptId, artifactId: artifact.id }, 'PNG-decoded-and-hashed');
      requireSafe(output.runtime && output.timing && typeof output.title === 'string' && Array.isArray(output.warnings) &&
        output.runtime.cleanProfileId === cleanProfileId && output.runtime.importedState === false &&
        output.runtime.initialCookies === 0 && output.runtime.finalCookies === 0, 'missing_or_unsafe_provenance');
      const number = (history.at(-1)?.commit.revisionNumber ?? 0) + 1;
      const revisionId = randomUUID();
      const directory = `${String(number).padStart(6, '0')}-${revisionId}`;
      const baseline = history.at(-1);
      const reuse = history.find((row) => row.commit.artifact.sha256 === artifact.sha256);
      if (reuse) requireSafe(reuse.raster.equals(output.raster) && reuse.commit.artifact.mime === artifact.mime &&
        reuse.commit.artifact.byteLength === artifact.byteLength, 'digest_collision_or_metadata_mismatch');
      const network = transport.evidence();
      const committedAt = new Date().toISOString();
      const classification = output.warnings.length ? 'review_required' : 'ready';
      const change = { id: randomUUID(), algorithm: 'exact-bytes-and-provenance/1', at: committedAt,
        baselineRevisionId: baseline?.commit.revisionId ?? null, currentRevisionId: revisionId,
        baselineArtifactId: baseline?.commit.artifact.id ?? null, currentArtifactId: artifact.id,
        signal: !baseline ? 'initial_observation' : baseline.raster.equals(output.raster) ? 'same_exact_bytes' : 'different_exact_bytes',
        differences: {
          finalUrl: baseline ? baseline.receipt.request.final.exact !== preflight.response.url.exact : null,
          redirects: baseline ? hash(json(baseline.receipt.network.redirectChain)) !== hash(json(preflight.chain)) : null,
          profile: baseline ? baseline.receipt.request.profileHash !== PROFILE_HASH : null,
          region: false,
          warnings: baseline ? hash(json(baseline.receipt.honesty.warnings)) !== hash(json(output.warnings)) : null,
          load: baseline ? baseline.receipt.timing.load !== output.timing.load : null,
        }, meaning: 'non-semantic; no materiality, selection, replacement or notification' };
      const receipt = {
        schema: 'issue-28-local-provenance/1',
        identity: { projectId: intent.projectId, ...ids, attemptId, leaseId: lease.id, leaseEpoch: 1,
          revisionId, revisionNumber: number, artifactId: artifact.id, provenanceId: randomUUID(), changeSignalId: change.id },
        authorization: { actor: 'local-operator', trigger: 'now', decision: 'explicit-local-CLI-invocation',
          policy: 'offline-spike-only-no-production-authorization', authorizedAt: requestedAt, requestId: jobId,
          document: null, build: null, checkpoint: null },
        request: { requested: admitted, final: preflight.response.url, settingsHash, profileHash: PROFILE_HASH,
          profile: PROFILE, fixture: { name: source.name, digest: source.digest },
          requestedRegion: PROFILE.region, idempotency: { scope: 'capture+actor+now+settings+command', keyDigest },
          requestedAt, enqueuedAt: requestedAt },
        network: { ...network, redirectChain: preflight.chain,
          responseMetadata: { status: 200, contentType: 'text/html' },
          title: output.title, limitations: 'All addresses/peers are synthetic fixture evidence; no DNS lookup, TLS handshake or socket connection occurred.' },
        runtime: output.runtime,
        timing: { ...output.timing, startedAt, endedAt: committedAt, committedAt }, lease,
        output: { artifact, region: PROFILE.region, normalizedRegion: PROFILE.normalizedRegion,
          staging: 'verified', commit: 'atomic-directory-rename', exactByteReuse: Boolean(reuse) },
        honesty: { warnings: output.warnings, classification, partialStateReason: output.warnings.length ? 'blocked-or-failed-resources' : null,
          sanitization: 'issue-28-redaction/1', observation_not_reproduction: true,
          statement: 'Immutable anonymous offline fixture observation. Stored bytes and provenance are reproducible; live-page rendering is not guaranteed.',
          unavailable: ['production actor/project authorization', 'live DNS, TLS and actual peers', 'live-page completeness or public-content certification'] },
        change, selection: 'unselected', retention: 'all-local-history-retained-no-deletion',
        terminalEvents: ['artifact_verified', 'provenance_verified', 'revision_committed', 'attempt_committed', 'job_committed', 'lease_released'],
      };
      return await store.publish({ directory, receipt, raster: output.raster, reuse, hit });
    } catch (error) {
      // A commit may have succeeded just before loss of its acknowledgement.
      const committed = (await store.history()).find((row) => row.commit.jobId === jobId);
      if (committed) return { ...committed.commit, recoveredAfterCommit: true };
      const failed = { result: 'failed', jobId, attemptId, revisionId: null,
        code: error.name === 'CaptureDenied' ? error.code : 'capture_failed',
        navigationStarted: attemptId !== null,
        network: transport?.evidence() ?? null };
      await store.atomicRecord(`jobs/${jobId}/outcome.json`, failed);
      await store.audit(attemptId ? 'attempt_failed' : 'job_rejected', { ...ids, attemptId }, failed.code);
      return failed;
    }
  });
}
