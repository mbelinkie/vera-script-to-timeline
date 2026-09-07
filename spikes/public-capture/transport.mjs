import { readFile } from 'node:fs/promises';
import { admitUrl, admitAddresses, verifyPeer } from './policy.mjs';
import { PROFILE, hash, json, requireSafe } from './profile.mjs';

export const FIXTURE_URL = 'https://capture.example.org/article';
export async function loadFixture(name) {
  requireSafe(['article-v1', 'article-v2', 'hostile'].includes(name), 'unknown_fixture');
  const body = await readFile(new URL(`./fixtures/${name}.html`, import.meta.url));
  const frozen = JSON.parse(await readFile(new URL('./fixtures/hashes.json', import.meta.url)));
  requireSafe(hash(body) === frozen[`${name}.html`], 'fixture_integrity_failure');
  return {
    name, digest: hash(body),
    routes: new Map([[FIXTURE_URL, { body, status: 200, contentType: 'text/html',
      answers: ['93.184.216.34'], peer: '93.184.216.34' }]]),
  };
}

// No fetch/http/DNS client exists here. All evidence is explicitly synthetic.
export class FixtureTransport {
  constructor(fixture) { this.fixture = fixture; this.manifest = []; this.bytes = 0; }
  request(raw, method = 'GET', kind = 'subresource') {
    requireSafe(this.manifest.length < PROFILE.limits.requests, 'request_limit');
    const event = { urlDigest: hash(raw), method, kind, observedAt: new Date().toISOString(), transport: 'synthetic' };
    this.manifest.push(event);
    try {
      requireSafe(PROFILE.methods.includes(method), 'method_denied');
      const url = admitUrl(raw);
      event.displayUrl = url.display;
      const response = this.fixture.routes.get(url.exact);
      requireSafe(response, 'offline_fixture_missing');
      const answers = admitAddresses(response.answers);
      const peer = verifyPeer(answers, response.peer);
      const body = response.body ?? Buffer.alloc(0);
      this.bytes += body.length;
      requireSafe(body.length <= PROFILE.limits.responseBytes && this.bytes <= PROFILE.limits.totalBytes, 'response_byte_limit');
      Object.assign(event, { syntheticAnswers: answers, syntheticPeer: peer,
        actualPeer: null, tls: 'unavailable-offline-no-socket', status: response.status,
        bytes: body.length, bodySha256: hash(body), result: 'admitted' });
      return { ...response, body, url };
    } catch (error) { event.result = error.code ?? 'transport_failed'; throw error; }
  }
  topLevel(raw) {
    const seen = new Set();
    const chain = [];
    let target = raw;
    for (let hop = 0; hop <= PROFILE.limits.redirects; hop += 1) {
      const canonical = admitUrl(target);
      requireSafe(!seen.has(canonical.exact), 'redirect_loop');
      seen.add(canonical.exact);
      const response = this.request(canonical.exact, 'GET', 'top-level-preflight');
      chain.push({ exact: canonical.exact, display: canonical.display, status: response.status });
      if (response.status >= 300 && response.status < 400) {
        requireSafe(typeof response.location === 'string', 'redirect_location_missing');
        target = new URL(response.location, canonical.exact).href;
      } else {
        requireSafe(response.status === 200 && response.contentType === 'text/html', 'top_level_response_denied');
        return { response, chain };
      }
    }
    requireSafe(false, 'redirect_limit');
  }
  evidence() {
    return { resolver: 'frozen-fixture-table-no-DNS', actualConnections: 0,
      bytes: this.bytes, requests: this.manifest.length, manifest: this.manifest,
      manifestSha256: hash(json(this.manifest)) };
  }
}
