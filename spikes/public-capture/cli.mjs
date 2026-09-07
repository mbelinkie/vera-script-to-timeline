import path from 'node:path';
import { capture } from './capture.mjs';
import { LocalStore } from './store.mjs';
import { FIXTURE_URL } from './transport.mjs';
import { requireSafe } from './profile.mjs';

async function inspect(root) {
  const store = new LocalStore(root);
  return store.locked(async () => {
    const rows = await store.history();
    await store.audit('history_read', {}, 'local-operator');
    return rows.map(({ directory, receipt, commit }) => ({
      revision: commit.revisionNumber, revisionId: commit.revisionId,
      attemptId: commit.attemptId, jobId: commit.jobId, status: commit.status,
      change: receipt.change.signal, sha256: commit.artifact.sha256,
      reusesExactBytes: receipt.output.exactByteReuse,
      artifact: path.join(store.root, commit.artifact.path),
      restrictedReceipt: path.join(store.root, 'commits', directory, 'provenance.json'),
      actualConnections: receipt.network.actualConnections,
      importedState: receipt.runtime.importedState,
      warnings: receipt.honesty.warnings,
    }));
  });
}

try {
  const [action, root, command, fixtureName, url, ...extra] = process.argv.slice(2);
  requireSafe(root && extra.length === 0 && ['capture', 'demo', 'inspect'].includes(action), 'usage: capture <private-store> <command-key> <article-v1|article-v2|hostile> [URL], or demo|inspect <private-store>');
  requireSafe(action === 'capture' || !command, 'unexpected_arguments');
  if (action === 'capture') {
    requireSafe(command && fixtureName, 'command_and_fixture_required');
    const result = await capture({ root, command, fixtureName, url: url ?? FIXTURE_URL });
    // Normal stdout contains no exact source URLs or page text.
    console.log(JSON.stringify({ result: result.result, code: result.code,
      jobId: result.jobId, attemptId: result.attemptId, revisionId: result.revisionId,
      revision: result.revisionNumber, status: result.status,
      sha256: result.artifact?.sha256, duplicate: result.duplicate ?? false,
      navigationStarted: result.navigationStarted }, null, 2));
    if (result.result === 'failed') process.exitCode = 1;
  } else {
    if (action === 'demo') {
      for (const [key, fixture] of [['demo-first', 'article-v1'], ['demo-unchanged', 'article-v1'], ['demo-changed', 'article-v2']]) {
        const result = await capture({ root, command: key, fixtureName: fixture });
        requireSafe(result.result === 'committed', result.code ?? 'demo_failed');
      }
    }
    console.log(JSON.stringify(await inspect(root), null, 2));
  }
} catch (error) {
  console.error(error.name === 'CaptureDenied' ? error.code : 'local_spike_failed');
  process.exitCode = 1;
}
