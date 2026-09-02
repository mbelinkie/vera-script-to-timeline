import { createHash } from 'node:crypto';

export const hash = (bytes) => createHash('sha256').update(bytes).digest('hex');
export const json = (value) => Buffer.from(`${JSON.stringify(value, null, 2)}\n`);
export const PROFILE = Object.freeze({
  id: 'issue-28-offline-public-v1',
  adapter: 'issue-28-fixture-chromium/1',
  transport: 'frozen-fixture-only-no-live-network',
  viewport: { width: 800, height: 450 }, deviceScaleFactor: 1,
  region: { x: 0, y: 0, width: 800, height: 450 },
  normalizedRegion: { x: 0, y: 0, width: 1, height: 1 },
  encoding: 'png', color: 'srgb', background: 'opaque-white',
  locale: 'en-US', timezoneId: 'UTC', userAgent: 'VERA-Offline-Capture-Spike/1',
  javaScriptEnabled: false, serviceWorkers: 'block',
  animations: 'disabled', reducedMotion: 'reduce', fonts: 'system-only-no-webfonts',
  media: 'blocked', cookies: 'no-import-no-set-cookie-no-forwarding',
  methods: ['GET', 'HEAD'], schemes: ['http:', 'https:'], ports: [80, 443],
  wait: 'domcontentloaded-then-load; no interactive actions',
  warnings: 'any-warning-requires-review',
  limits: {
    url: 2048, redirects: 4, dnsAnswers: 8, connectionAttempts: 0,
    requests: 24, topLevelRequests: 1, subresources: 23, frameDepth: 0, popups: 0,
    responseBytes: 262144, totalBytes: 1048576, navigationMs: 5000,
    stabilityMs: 1000, totalMs: 15000, scriptCpuSeconds: 0,
    processCpuSeconds: 10, memoryMiB: 768, processes: 12, concurrentAttempts: 1,
    pixels: 360000, rasterBytes: 2097152, diagnostics: 32, fieldLength: 256,
    retries: 0, leaseMs: 20000, heartbeatMs: 0,
  },
});
export const PROFILE_HASH = hash(json(PROFILE));
export class CaptureDenied extends Error {
  constructor(code) { super(code); this.name = 'CaptureDenied'; this.code = code; }
}
export function requireSafe(condition, code) {
  if (!condition) throw new CaptureDenied(code);
}
export const sanitized = (value) => String(value).replace(/[\u0000-\u001f\u007f]/g, ' ').slice(0, PROFILE.limits.fieldLength);
