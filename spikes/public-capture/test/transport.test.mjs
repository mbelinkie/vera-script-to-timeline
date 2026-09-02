import assert from 'node:assert/strict';
import test from 'node:test';
import { FixtureTransport, FIXTURE_URL, loadFixture } from '../transport.mjs';
import { PROFILE } from '../profile.mjs';

test('guarded redirect chain is resolved from frozen responses without sockets', async () => {
  const fixture = await loadFixture('article-v1');
  fixture.routes.set('https://capture.example.org/start', { answers: ['93.184.216.34'], peer: '93.184.216.34', status: 302, location: '/article' });
  const transport = new FixtureTransport(fixture);
  const result = transport.topLevel('https://capture.example.org/start');
  assert.equal(result.chain.length, 2);
  assert.equal(result.response.url.exact, FIXTURE_URL);
  assert.equal(transport.evidence().actualConnections, 0);
});

test('unsafe redirects, mixed DNS, peer rebind and redirect loops fail closed', async () => {
  for (const location of ['http://127.0.0.1/', 'http://metadata.google.internal/', 'file:///etc/passwd', '/article']) {
    const fixture = await loadFixture('article-v1');
    Object.assign(fixture.routes.get(FIXTURE_URL), { status: 302, location });
    assert.throws(() => new FixtureTransport(fixture).topLevel(FIXTURE_URL));
  }
  for (const change of [{ answers: ['93.184.216.34', '10.0.0.1'] }, { peer: '127.0.0.1' }, { peer: '8.8.8.8' }]) {
    const fixture = await loadFixture('article-v1');
    Object.assign(fixture.routes.get(FIXTURE_URL), change);
    assert.throws(() => new FixtureTransport(fixture).topLevel(FIXTURE_URL));
  }
});

test('methods, request, redirect and transfer budgets have finite enforced bounds', async () => {
  const fixture = await loadFixture('article-v1');
  for (const method of ['POST', 'PUT', 'DELETE', 'CONNECT']) {
    assert.throws(() => new FixtureTransport(fixture).request(FIXTURE_URL, method), /method_denied/);
  }
  const transport = new FixtureTransport(fixture);
  for (let count = 0; count < PROFILE.limits.requests; count += 1) transport.request(FIXTURE_URL);
  assert.throws(() => transport.request(FIXTURE_URL), /request_limit/);
  fixture.routes.get(FIXTURE_URL).body = Buffer.alloc(PROFILE.limits.responseBytes + 1);
  assert.throws(() => new FixtureTransport(fixture).topLevel(FIXTURE_URL), /response_byte_limit/);
  fixture.routes.get(FIXTURE_URL).body = Buffer.alloc(PROFILE.limits.responseBytes);
  const big = new FixtureTransport(fixture);
  for (let count = 0; count < 4; count += 1) big.request(FIXTURE_URL);
  assert.throws(() => big.request(FIXTURE_URL), /response_byte_limit/);
  for (let count = 0; count < 6; count += 1) {
    fixture.routes.set(`https://capture.example.org/r${count}`, { answers: ['93.184.216.34'], peer: '93.184.216.34', status: 302, location: `/r${count + 1}` });
  }
  assert.throws(() => new FixtureTransport(fixture).topLevel('https://capture.example.org/r0'), /redirect_limit/);
});
