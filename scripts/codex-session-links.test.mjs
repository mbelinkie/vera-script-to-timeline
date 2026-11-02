import assert from 'node:assert/strict';
import { chmod, mkdtemp, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import {
  canonicalIssueKey, parseLocalCodexLink, parseSessionMapping,
  loadLocalCodexSessionMap, linksForIssue,
} from './codex-session-links.mjs';

const ISSUE = 'https://github.com/mbelinkie/vera-script-to-timeline/issues/399';
const OTHER_ISSUE = 'https://github.com/mbelinkie/vera-research-video-clips/issues/399';
const UUID = '12345678-1234-1234-1234-123456789aBc';
const DEEPLINK = `codex://threads/${UUID}`;
const BROWSER = 'https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc';
const INSTALL = 'test-mac-installation';
const TIMESTAMP = '2026-11-01T20:00:00Z';
const primary = (overrides = {}) => ({
  issueUrl: ISSUE, surface: 'codex-local', role: 'primary', deepLink: DEEPLINK,
  provenance: { method: 'desktop-copy-deeplink', confirmedBy: 'producer', capturedAt: TIMESTAMP },
  verification: { state: 'producer-confirmed-existing', checkedAt: TIMESTAMP },
  ...overrides,
});
const snapshot = (mappings = [primary()]) => ({ version: 1, installationId: INSTALL, mappings });
const link = (snap = snapshot(), issue = ISSUE, installation = INSTALL) => linksForIssue(issue, snap, installation);

test('accepts only exact existing Codex thread UUID links (not only v4)', () => {
  assert.deepEqual(parseLocalCodexLink(DEEPLINK), {
    threadId: UUID.toLowerCase(), appUrl: `codex://threads/${UUID.toLowerCase()}`,
  });
  for (const invalid of [
    'codex://threads/new', 'codex://new?prompt=hi', DEEPLINK + '/', DEEPLINK + '?x=1',
    DEEPLINK + '#fragment', DEEPLINK + '/more', 'https://chatgpt.com/c/' + UUID,
    'CODEX://threads/' + UUID, 'codex://threads/%31' + UUID.slice(1),
    'codex://threads/' + UUID.replace('-', '%2f'), 'codex://user@threads/' + UUID,
    'codex://threads/' + UUID + '" onclick="alert(1)',
  ]) assert.equal(parseLocalCodexLink(invalid), null, invalid);
});

test('canonical issue key prevents same-number cross-repo collisions', () => {
  assert.equal(canonicalIssueKey(ISSUE), 'mbelinkie/vera-script-to-timeline#399');
  assert.equal(canonicalIssueKey(OTHER_ISSUE), 'mbelinkie/vera-research-video-clips#399');
  assert.notEqual(canonicalIssueKey(ISSUE), canonicalIssueKey(OTHER_ISSUE));
  assert.equal(canonicalIssueKey(ISSUE + '?query=1'), null);
  assert.equal(canonicalIssueKey('https://evil.example/issues/399'), null);
});

test('only explicitly associated local primary yields a zero-turn desktop link', () => {
  const found = link();
  assert.equal(found.status, 'verified-local');
  assert.equal(found.appUrl, DEEPLINK.toLowerCase());
  assert.equal(found.threadId, UUID.toLowerCase());
  assert.equal(found.issueUrl, ISSUE);
  assert.equal(found.lastConfirmedAt, TIMESTAMP);
  assert.equal(found.browserUrl, undefined);
  assert.equal(link(snapshot(), OTHER_ISSUE).status, 'missing');
});

test('missing, history-only, competing primaries, and wrong installation fail closed', () => {
  assert.equal(link(snapshot([])).status, 'missing');
  assert.equal(link(snapshot([primary({role:'history'})])).status, 'missing');
  assert.equal(link(snapshot([primary(),primary()])).status, 'ambiguous');
  assert.equal(link(snapshot(), ISSUE, 'other-device').status, 'wrong-device');
  assert.equal(linksForIssue(ISSUE, snapshot(), undefined).status, 'wrong-device');
  assert.equal(link({mappings:[],error:'error'}).status, 'invalid');
});

test('unverified, malformed, stale, cloud-only, and web-only never create Codex app actions', () => {
  const inputs = [
    [primary({provenance:{method:'manual-guess'}}),'unverified'],
    [primary({verification:{state:'stale',checkedAt:TIMESTAMP}}),'stale'],
    [primary({verification:{state:'unknown'}}),'unverified'],
    [primary({deepLink:'codex://threads/new'}),'invalid'],
    [primary({threadId:'00000000-0000-0000-0000-000000000000'}),'invalid'],
    [primary({surface:'codex-cloud'}),'cloud-only'],
    [primary({surface:'chatgpt-web',browserUrl:BROWSER,browserProvenance:{method:'producer-confirmed-existing',confirmedAt:TIMESTAMP}}),'web-only'],
  ];
  for (const [entry,status] of inputs) {
    const result = link(snapshot([entry]));
    assert.equal(result.status,status);
    assert.equal(result.appUrl,undefined,status);
  }
});

test('separately Producer-confirmed existing browser conversation is optional fallback', () => {
  const record = primary({browserUrl:BROWSER,browserProvenance:{method:'producer-confirmed-existing',confirmedAt:TIMESTAMP}});
  assert.equal(link(snapshot([record])).browserUrl,BROWSER);
  const unverified = primary({browserUrl:BROWSER});
  assert.throws(()=>parseSessionMapping(snapshot([unverified])));
  for (const bad of [
    'https://chatgpt.com/?prompt=issue',
    'https://chatgpt.com/share/123456789abc',
    'javascript:alert(1)',
    BROWSER + '?payload=x',
    BROWSER + '/more',
  ]) assert.throws(()=>parseSessionMapping(snapshot([primary({browserUrl:bad,browserProvenance:{method:'producer-confirmed-existing',confirmedAt:TIMESTAMP}})])));
});

test('rejects corrupt/unknown mapping schemas without using partial data', () => {
  assert.throws(()=>parseSessionMapping('not json'));
  assert.throws(()=>parseSessionMapping({version:2,installationId:INSTALL,mappings:[]}));
  assert.throws(()=>parseSessionMapping({version:1,installationId:INSTALL,mappings:[{issueUrl:ISSUE,role:'primary',surface:'injected'}]}));
  assert.deepEqual(parseSessionMapping(JSON.stringify(snapshot())).mappings,[primary()]);
});

test('owner-only read-only loader handles missing, insecure, and corrupt files safely', async (t) => {
  const dir = await mkdtemp(path.join(os.tmpdir(),'vera399-'));
  t.after(async()=>{ const {rm}=await import('node:fs/promises');await rm(dir,{recursive:true,force:true}); });
  const file = path.join(dir,'map.json');
  assert.deepEqual(await loadLocalCodexSessionMap(file),{mappings:[],error:null});
  await writeFile(file, JSON.stringify(snapshot()), {mode:0o600});
  await chmod(file,0o600);
  assert.equal((await loadLocalCodexSessionMap(file)).error,null);
  await chmod(file,0o644);
  assert.match((await loadLocalCodexSessionMap(file)).error,/owner-only/);
  await chmod(file,0o600);
  await writeFile(file,'{broken json');
  assert.equal((await loadLocalCodexSessionMap(file)).mappings.length,0);
  assert.ok((await loadLocalCodexSessionMap(file)).error);
});
