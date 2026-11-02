import assert from 'node:assert/strict';
import { mkdtemp, readFile, stat, lstat, chmod, writeFile, symlink, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { loadLocalCodexSessionMap, linksForIssue } from './codex-session-links.mjs';
import { registerLocalCodexThread, readLocalInstallationId, defaultInstallationIdPath } from './codex-session-register-lib.mjs';

const ISSUE='https://github.com/mbelinkie/vera-script-to-timeline/issues/399';
const A='codex://threads/11111111-2222-3333-4444-555555555555';
const B='codex://threads/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
const FIXED='2026-11-01T20:00:00.000Z';
async function fixture(t) {
  const dir=await mkdtemp(path.join(os.tmpdir(),'vera399-register-'));
  t.after(()=>rm(dir,{force:true,recursive:true}));
  const mappingPath=path.join(dir,'private','codex-thread-map.v1.json');
  const installationIdPath=defaultInstallationIdPath(mappingPath);
  return {dir,mappingPath,installationIdPath,now:()=>FIXED};
}

test('requires confirmation and valid GitHub issue / pasted local link before writing',async t=>{
  const p=await fixture(t);
  await assert.rejects(registerLocalCodexThread({issueUrl:ISSUE,deepLink:A,...p}),/confirmation/);
  await assert.rejects(registerLocalCodexThread({issueUrl:ISSUE,deepLink:'https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc',confirmed:true,...p}),/exact GitHub/);
  await assert.rejects(registerLocalCodexThread({issueUrl:ISSUE+'?junk=1',deepLink:A,confirmed:true,...p}),/exact GitHub/);
  await assert.rejects(lstat(path.dirname(p.mappingPath)),{code:'ENOENT'});
});

test('registers exact existing thread with owner-only installation + map and inert read-only view',async t=>{
  const p=await fixture(t);
  const result=await registerLocalCodexThread({issueUrl:ISSUE,deepLink:A,confirmed:true,...p});
  assert.equal(result.issueKey,'mbelinkie/vera-script-to-timeline#399');
  assert.equal(result.threadSuffix,'55555555');
  assert.equal((await stat(path.dirname(p.mappingPath))).mode & 0o777,0o700);
  assert.equal((await stat(p.mappingPath)).mode & 0o777,0o600);
  assert.equal((await stat(p.installationIdPath)).mode & 0o777,0o600);
  const installationId=await readLocalInstallationId(p.installationIdPath);
  assert.match(installationId,/^[0-9a-f-]{36}$/);
  const saved=await loadLocalCodexSessionMap(p.mappingPath);
  assert.equal(saved.installationId,installationId);
  assert.equal(saved.mappings.length,1);
  const found=linksForIssue(ISSUE,saved,installationId);
  assert.equal(found.status,'verified-local');
  assert.equal(found.appUrl,A);
  assert.equal(found.lastConfirmedAt,FIXED);
  assert.equal(linksForIssue(ISSUE,saved,'another-id').appUrl,undefined);
});

test('same thread reconfirmation does not duplicate; replacement requires another explicit flag and keeps history',async t=>{
  const p=await fixture(t);
  await registerLocalCodexThread({issueUrl:ISSUE,deepLink:A,confirmed:true,...p});
  await registerLocalCodexThread({issueUrl:ISSUE,deepLink:A,confirmed:true,...p});
  assert.equal((await loadLocalCodexSessionMap(p.mappingPath)).mappings.length,1);
  const before=await readFile(p.mappingPath,'utf8');
  await assert.rejects(registerLocalCodexThread({issueUrl:ISSUE,deepLink:B,confirmed:true,...p}),/replacement confirmation/);
  assert.equal(await readFile(p.mappingPath,'utf8'),before);
  const result=await registerLocalCodexThread({issueUrl:ISSUE,deepLink:B,confirmed:true,replaceExisting:true,...p});
  assert.equal(result.replacedPrimary,true);
  const saved=await loadLocalCodexSessionMap(p.mappingPath);
  assert.deepEqual(saved.mappings.map(m=>[m.role,m.deepLink]),[['history',A],['primary',B]]);
});

test('corrupt or permissive existing mapping fails without modifying it',async t=>{
  const p=await fixture(t);
  await registerLocalCodexThread({issueUrl:ISSUE,deepLink:A,confirmed:true,...p});
  await writeFile(p.mappingPath,'{corrupt');
  await assert.rejects(registerLocalCodexThread({issueUrl:ISSUE,deepLink:B,confirmed:true,replaceExisting:true,...p}));
  assert.equal(await readFile(p.mappingPath,'utf8'),'{corrupt');
  await chmod(p.mappingPath,0o644);
  await assert.rejects(registerLocalCodexThread({issueUrl:ISSUE,deepLink:A,confirmed:true,...p}),/owner-only/);
});

test('rejects installation mismatches and permissive private directory',async t=>{
  const p=await fixture(t);
  await registerLocalCodexThread({issueUrl:ISSUE,deepLink:A,confirmed:true,...p});
  const before=await readFile(p.mappingPath,'utf8');
  await writeFile(p.installationIdPath,'aaaa1111-1111-1111-1111-111111111111\n');
  await assert.rejects(registerLocalCodexThread({issueUrl:ISSUE,deepLink:B,confirmed:true,replaceExisting:true,...p}),/different local installation/);
  assert.equal(await readFile(p.mappingPath,'utf8'),before);
  await chmod(path.dirname(p.mappingPath),0o755);
  assert.equal(await readLocalInstallationId(p.installationIdPath),null);
  await assert.rejects(registerLocalCodexThread({issueUrl:ISSUE,deepLink:A,confirmed:true,...p}),/owner-only/);
});

test('rejects symlinked private directory before writing',async t=>{
  const p=await fixture(t);
  const target=path.join(p.dir,'target');
  await (await import('node:fs/promises')).mkdir(target,{mode:0o700});
  await writeFile(path.join(target,path.basename(p.installationIdPath)),'11111111-2222-3333-4444-555555555555\n',{mode:0o600});
  await symlink(target,path.dirname(p.mappingPath));
  assert.equal(await readLocalInstallationId(p.installationIdPath),null);
  await assert.rejects(registerLocalCodexThread({issueUrl:ISSUE,deepLink:A,confirmed:true,...p}),/owner-only/);
});

test('registration lock prevents concurrent lost updates without touching the map',async t=>{
  const p=await fixture(t);
  await registerLocalCodexThread({issueUrl:ISSUE,deepLink:A,confirmed:true,...p});
  const original=await readFile(p.mappingPath,'utf8');
  await writeFile(`${p.mappingPath}.lock`,'locked',{mode:0o600});
  await assert.rejects(registerLocalCodexThread({issueUrl:ISSUE,deepLink:B,confirmed:true,replaceExisting:true,...p}),/Another local registration/);
  assert.equal(await readFile(p.mappingPath,'utf8'),original);
  assert.equal(await readFile(`${p.mappingPath}.lock`,'utf8'),'locked');
});

test('reconfirming same UUID with different casing preserves verified browser evidence',async t=>{
  const p=await fixture(t);
  await registerLocalCodexThread({issueUrl:ISSUE,deepLink:A,confirmed:true,...p});
  const stored=JSON.parse(await readFile(p.mappingPath,'utf8'));
  stored.mappings[0].browserUrl='https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc';
  stored.mappings[0].browserProvenance={method:'producer-confirmed-existing',confirmedAt:FIXED,relation:'same-thread'};
  await writeFile(p.mappingPath,JSON.stringify(stored),{mode:0o600});
  await assert.rejects(registerLocalCodexThread({
    issueUrl:ISSUE, deepLink:A.toUpperCase(), confirmed:true, ...p,
  }), /copied existing/); // Uppercase scheme/host is not the exact documented form.
  await registerLocalCodexThread({issueUrl:ISSUE,deepLink:A.toUpperCase().replace('CODEX://THREADS','codex://threads'),confirmed:true,...p});
  const result=JSON.parse(await readFile(p.mappingPath,'utf8'));
  assert.equal(result.mappings.length,1);
  assert.equal(result.mappings[0].browserUrl,stored.mappings[0].browserUrl);
});
