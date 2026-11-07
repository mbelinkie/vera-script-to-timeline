import assert from 'node:assert/strict';
import { mkdtemp, rm, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { createExperimentServer } from './server.mjs';

test('serves only the supplied files with ranges, HEAD, safe config, and same-origin checks', async (t) => {
  const directory = await mkdtemp(join(tmpdir(), 'vera-live-proxy-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const aPath = join(directory, 'a.mov');
  const bPath = join(directory, 'b.mp4');
  const audioAPath = join(directory, 'aligned.wav');
  await Promise.all([
    writeFile(aPath, Buffer.from('abcdefgh')),
    writeFile(bPath, Buffer.from('second')),
    writeFile(audioAPath, Buffer.from('toy wav bytes')),
  ]);

  const server = await createExperimentServer({ aPath, bPath, audioAPath });
  t.after(() => new Promise((resolve) => server.close(resolve)));
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  const base = `http://127.0.0.1:${server.address().port}`;

  const page = await fetch(`${base}/`);
  assert.equal(page.status, 200);
  assert.match(page.headers.get('content-type'), /^text\/html/);
  assert.match(await page.text(), /player\.mjs/);
  for (const route of ['/player.mjs', '/assembly.mjs']) {
    const script = await fetch(`${base}${route}`);
    assert.equal(script.status, 200, route);
    assert.match(script.headers.get('content-type'), /^application\/javascript/);
    assert.match(await script.text(), /^(?:export|import)\b/m);
  }

  const partial = await fetch(`${base}/media/a`, { headers: { Range: 'bytes=2-4' } });
  assert.equal(partial.status, 206);
  assert.equal(partial.headers.get('content-range'), 'bytes 2-4/8');
  assert.equal(await partial.text(), 'cde');
  assert.equal(partial.headers.get('content-type'), 'video/quicktime');

  const suffix = await fetch(`${base}/media/a`, { headers: { Range: 'bytes=-3' } });
  assert.equal(suffix.status, 206);
  assert.equal(await suffix.text(), 'fgh');

  const unsatisfied = await fetch(`${base}/media/a`, { headers: { Range: 'bytes=8-' } });
  assert.equal(unsatisfied.status, 416);
  assert.equal(unsatisfied.headers.get('content-range'), 'bytes */8');

  const head = await fetch(`${base}/media/b`, { method: 'HEAD' });
  assert.equal(head.status, 200);
  assert.equal(head.headers.get('content-length'), '6');
  assert.equal(await head.text(), '');

  const audio = await fetch(`${base}/audio/a`);
  assert.equal(audio.headers.get('content-type'), 'audio/wav');
  assert.equal(await audio.text(), 'toy wav bytes');

  const configResponse = await fetch(`${base}/config.json`);
  const configText = await configResponse.text();
  const config = JSON.parse(configText);
  assert.deepEqual(config, {
    a: { label: 'A', size: 8 },
    b: { label: 'B', size: 6 },
    audio: { a: { label: 'Audio A', size: 13 }, b: null },
  });
  assert.equal(configText.includes(directory), false);

  for (const route of ['/missing', '/media/a%2f..%2f..%2fetc%2fpasswd', '/audio/b']) {
    assert.equal((await fetch(`${base}${route}`)).status, 404, route);
  }
  assert.equal((await fetch(`${base}/media/a`, { method: 'POST' })).status, 405);
  const foreignOrigin = await fetch(`${base}/media/a`, { headers: { Origin: 'https://attacker.example' } });
  assert.equal(foreignOrigin.status, 403);
  assert.equal(foreignOrigin.headers.get('access-control-allow-origin'), null);
  assert.equal(partial.headers.get('cross-origin-resource-policy'), 'same-origin');
});

test('rejects directories and symlinks as supplied media', async (t) => {
  const directory = await mkdtemp(join(tmpdir(), 'vera-live-proxy-validation-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const aPath = join(directory, 'a.mov');
  const bPath = join(directory, 'b.mp4');
  const linkPath = join(directory, 'link.mov');
  await writeFile(aPath, 'toy a');
  await writeFile(bPath, 'toy b');
  await symlink(aPath, linkPath);

  await assert.rejects(createExperimentServer({ aPath: directory, bPath }), /regular, non-symlink file/);
  await assert.rejects(createExperimentServer({ aPath: linkPath, bPath }), /regular, non-symlink file/);
  await assert.rejects(createExperimentServer({ aPath, bPath, audioAPath: aPath }), /must be a \.wav file/);
});
