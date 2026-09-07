import { mkdtemp, writeFile, readFile, realpath } from 'node:fs/promises';
import { tmpdir, platform, release, arch } from 'node:os';
import path from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { chromium } from 'playwright';
import { PROFILE, hash, requireSafe, sanitized } from './profile.mjs';

const exec = promisify(execFile);
const shellQuote = (value) => `'${value.replaceAll("'", "'\\''")}'`;
const seatbeltQuote = (value) => JSON.stringify(value);

export function sandboxPolicy(browserRoot, scratch) {
  return `(version 1)
(deny default)
(allow process-exec process-fork sysctl-read)
(allow signal (target same-sandbox))
(allow mach-lookup
  (global-name-regex "^org[.]chromium[.]")
  (global-name "com.apple.cfprefsd.agent")
  (global-name "com.apple.cfprefsd.daemon")
  (global-name "com.apple.system.logger")
  (global-name "com.apple.system.notification_center")
  (global-name "com.apple.FontObjectsServer")
  (global-name "com.apple.FontServer"))
(allow mach-register (global-name-regex "^org[.]chromium[.]"))
(allow iokit-open (iokit-user-client-class "RootDomainUserClient"))
(allow file-read-metadata)
(allow file-read* file-map-executable (literal "/") (subpath "/System") (subpath "/usr") (subpath "/bin")
  (subpath "/Library/Fonts") (subpath "/Library/Apple")
  (subpath "/private/etc") (subpath "/private/var/db/timezone") (subpath "/dev")
  (subpath ${seatbeltQuote(browserRoot)}) (subpath ${seatbeltQuote(scratch)}))
(allow file-write* (subpath ${seatbeltQuote(scratch)}) (literal "/dev/null"))
; No network rule: TCP, UDP, DNS, loopback and inbound listeners are denied.
`;
}

export async function prepareSandbox() {
  requireSafe(platform() === 'darwin', 'unsupported_OS_no_sandbox');
  const scratch = await realpath(await mkdtemp(path.join(tmpdir(), 'vera-capture-')));
  const installed = chromium.executablePath();
  const revision = installed.match(/\/chromium-(\d+)\//)?.[1];
  requireSafe(revision, 'pinned_browser_path_unavailable');
  const executable = await realpath(path.join(installed.slice(0, installed.indexOf(`/chromium-${revision}/`)),
    `chromium_headless_shell-${revision}`, `chrome-headless-shell-mac-${arch() === 'arm64' ? 'arm64' : 'x64'}`, 'chrome-headless-shell'));
  const browserRoot = path.dirname(executable);
  const policy = sandboxPolicy(browserRoot, scratch);
  const policyPath = path.join(scratch, 'browser.sb');
  const wrapper = path.join(scratch, 'launch');
  await writeFile(policyPath, policy, { mode: 0o600 });
  await writeFile(wrapper, `#!/bin/sh\nset -eu\numask 077\nulimit -t ${PROFILE.limits.processCpuSeconds}\necho $$ > ${shellQuote(path.join(scratch, 'pid'))}\nfor arg do\n  shift\n  case "$arg" in\n    --user-data-dir=*) set -- "$@" ${shellQuote(`--user-data-dir=${path.join(scratch, 'profile')}`)} ;;\n    *) set -- "$@" "$arg" ;;\n  esac\ndone\nexec /usr/bin/sandbox-exec -f ${shellQuote(policyPath)} ${shellQuote(executable)} "$@"\n`, { mode: 0o700 });
  return { scratch, policyPath, wrapper, policyHash: hash(policy),
    executableSha256: hash(await readFile(executable)),
    // No inheritance of proxy variables, credentials, HOME or browser settings.
    env: { PATH: '/usr/bin:/bin', TMPDIR: scratch, LANG: 'en_US.UTF-8' } };
}

async function processUsage(rootPid) {
  const { stdout } = await exec('/bin/ps', ['-axo', 'pid=,ppid=,rss=']);
  const rows = stdout.trim().split('\n').map((line) => line.trim().split(/\s+/).map(Number));
  const descendants = new Set([rootPid]);
  for (let pass = 0; pass < PROFILE.limits.processes + 1; pass += 1) {
    for (const [pid, parent] of rows) if (descendants.has(parent)) descendants.add(pid);
  }
  return { count: descendants.size, rssKiB: rows.filter(([pid]) => descendants.has(pid)).reduce((total, row) => total + row[2], 0) };
}

export async function renderFixture({ transport, preflight, cleanProfileId }) {
  const sandbox = await prepareSandbox();
  let browser;
  let watchdog;
  let deadline;
  let failure;
  let navigationCount = 0;
  const warnings = [];
  const fail = (code) => { failure ??= code; void browser?.close().catch(() => {}); };
  const warn = (code) => {
    if (!warnings.includes(code)) warnings.push(code);
    if (warnings.length > PROFILE.limits.diagnostics) fail('diagnostic_limit');
  };
  const monotonicStart = performance.now();
  try {
    browser = await chromium.launch({
      executablePath: sandbox.wrapper, env: sandbox.env, headless: true,
      // macOS rejects nested Seatbelt initialization. The inherited outer
      // sandbox confines the entire browser tree, including the broker.
      chromiumSandbox: false, timeout: PROFILE.limits.navigationMs,
      args: ['--disable-gpu', '--disable-webgl', '--disable-quic',
        '--disable-background-networking', '--disable-extensions', '--disable-sync',
        '--disable-component-update', '--force-color-profile=srgb',
        '--disable-features=WebRTC,WebBluetooth,WebUSB', '--no-proxy-server'],
    });
    const pid = Number(await readFile(path.join(sandbox.scratch, 'pid'), 'utf8'));
    let checking = false;
    let peak = { count: 0, rssKiB: 0 };
    watchdog = setInterval(async () => {
      if (checking) return;
      checking = true;
      try {
        const usage = await processUsage(pid);
        peak = { count: Math.max(peak.count, usage.count), rssKiB: Math.max(peak.rssKiB, usage.rssKiB) };
        if (usage.count > PROFILE.limits.processes || usage.rssKiB > PROFILE.limits.memoryMiB * 1024) fail('browser_resource_limit');
      } catch { fail('resource_monitor_unavailable'); }
      finally { checking = false; }
    }, 100);
    deadline = setTimeout(() => fail('attempt_deadline'), PROFILE.limits.totalMs - (performance.now() - monotonicStart));
    const context = await browser.newContext({
      viewport: PROFILE.viewport, deviceScaleFactor: PROFILE.deviceScaleFactor,
      locale: PROFILE.locale, timezoneId: PROFILE.timezoneId, userAgent: PROFILE.userAgent,
      javaScriptEnabled: false, serviceWorkers: 'block', reducedMotion: 'reduce',
      acceptDownloads: false, permissions: [], colorScheme: 'light',
    });
    const initialCookies = await context.cookies();
    requireSafe(initialCookies.length === 0, 'dirty_browser_context');
    context.on('page', (page) => {
      if (context.pages().length > 1) fail('popup_denied');
      page.on('download', () => fail('download_denied'));
      page.on('crash', () => fail('browser_crash'));
      page.on('console', () => warn('page_console_message_redacted'));
    });
    await context.routeWebSocket('**/*', (socket) => { warn('websocket_denied'); socket.close(); });
    const csp = "default-src 'none'; style-src 'unsafe-inline'; img-src http: https:; script-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; connect-src 'none'; font-src 'none'";
    await context.route('**/*', async (route) => {
      const request = route.request();
      const top = request.isNavigationRequest() && request.frame().parentFrame() === null;
      try {
        requireSafe(['GET', 'HEAD'].includes(request.method()), 'method_denied');
        requireSafe(!('cookie' in request.headers()) && !('authorization' in request.headers()), 'credential_header_denied');
        let response;
        if (top) {
          navigationCount += 1;
          requireSafe(navigationCount === 1 && request.url() === preflight.response.url.exact, 'unexpected_navigation_denied');
          response = preflight.response;
        } else {
          requireSafe(!request.isNavigationRequest(), 'frame_denied');
          response = transport.request(request.url(), request.method(), request.resourceType());
          requireSafe(response.status === 200 && ['image/png', 'image/jpeg', 'text/css'].includes(response.contentType), 'resource_type_denied');
        }
        // Deliberately reconstruct safe headers; never forward Set-Cookie,
        // credentials, redirects, content disposition or arbitrary headers.
        await route.fulfill({ status: 200, body: response.body, headers: {
          'content-type': response.contentType, 'content-security-policy': csp,
          'referrer-policy': 'no-referrer', 'cache-control': 'no-store',
        } });
      } catch (error) {
        if (top) failure ??= error.code ?? 'navigation_denied';
        else warn(error.code ?? 'resource_denied');
        await route.abort('blockedbyclient').catch(() => {});
      }
    });
    const page = await context.newPage();
    const navStart = performance.now();
    await page.goto(preflight.response.url.exact, { waitUntil: 'domcontentloaded', timeout: PROFILE.limits.navigationMs });
    const domLoadedMs = performance.now() - navStart;
    await page.waitForLoadState('load', { timeout: PROFILE.limits.stabilityMs });
    requireSafe(!failure, failure ?? 'browser_failed');
    const title = sanitized(await page.title());
    const raster = await page.screenshot({ type: 'png', animations: 'disabled',
      caret: 'hide', fullPage: false, timeout: PROFILE.limits.navigationMs });
    const finalCookies = await context.cookies();
    requireSafe(finalCookies.length === 0, 'cookie_state_denied');
    requireSafe(!failure, failure ?? 'browser_failed');
    return { raster, title, warnings, navigationCount,
      runtime: { worker: PROFILE.adapter, installation: 'standalone-local-spike',
        os: `${platform()} ${release()} ${arch()}`, browser: `Chromium ${browser.version()}`,
        executableSha256: sandbox.executableSha256, isolation: 'macOS-seatbelt-deny-network',
        policyHash: sandbox.policyHash, chromiumInternalSandbox: false,
        outerSandbox: 'inherited-seatbelt', cleanProfileId, initialCookies: 0, finalCookies: 0,
        importedState: false, javaScript: 'disabled', permissions: [], peak },
      timing: { domContentLoadedMs: domLoadedMs, load: 'observed', wait: PROFILE.wait,
        monotonicStartMs: monotonicStart, monotonicEndMs: performance.now(),
        captureInstant: new Date().toISOString(), boundsReached: [] },
    };
  } catch (error) {
    // Do not persist browser errors: they can contain page text/URLs/environment.
    requireSafe(false, failure ?? error.code ?? 'browser_failed');
  } finally {
    clearInterval(watchdog); clearTimeout(deadline);
    await browser?.close().catch(() => {});
  }
}
