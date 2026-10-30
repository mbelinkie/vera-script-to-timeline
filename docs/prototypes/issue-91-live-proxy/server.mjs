import { constants, promises as fs } from 'node:fs';
import { createServer } from 'node:http';
import { extname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('.', import.meta.url));
const MIME_TYPES = {
  '.aif': 'audio/aiff', '.aiff': 'audio/aiff', '.aac': 'audio/aac', '.m4a': 'audio/mp4',
  '.mkv': 'video/x-matroska', '.mov': 'video/quicktime', '.mp3': 'audio/mpeg',
  '.mp4': 'video/mp4', '.mpeg': 'video/mpeg', '.mpg': 'video/mpeg', '.ogg': 'video/ogg',
  '.wav': 'audio/wav', '.webm': 'video/webm', '.m4v': 'video/x-m4v',
  '.html': 'text/html; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
};

function mimeType(filePath) {
  return MIME_TYPES[extname(filePath).toLowerCase()] ?? 'application/octet-stream';
}

async function localFile(filePath, label) {
  if (typeof filePath !== 'string' || !filePath) throw new Error(`${label} path is required`);
  const absolutePath = resolve(filePath);
  if (!(await fs.lstat(absolutePath)).isFile()) throw new Error(`${label} must be a regular, non-symlink file`);
  const canonicalPath = await fs.realpath(absolutePath);
  const details = await fs.stat(canonicalPath);
  if (!details.isFile()) throw new Error(`${label} must be a regular, non-symlink file`);
  return { path: canonicalPath, size: details.size };
}

function parseRange(value, size) {
  if (!value) return { start: 0, end: size - 1, status: 200 };
  const match = /^bytes=(\d*)-(\d*)$/.exec(value.trim());
  if (!match || (!match[1] && !match[2])) return { start: 0, end: size - 1, status: 200 };
  if (size === 0) return { status: 416 };

  let start;
  let end;
  if (!match[1]) {
    const suffix = Number(match[2]);
    if (suffix === 0) return { status: 416 };
    start = Number.isSafeInteger(suffix) ? Math.max(0, size - suffix) : 0;
    end = size - 1;
  } else {
    start = Number(match[1]);
    end = match[2] && Number.isSafeInteger(Number(match[2])) ? Number(match[2]) : size - 1;
    if (!Number.isSafeInteger(start) || start >= size || end < start) return { status: 416 };
    end = Math.min(end, size - 1);
  }
  return { start, end, status: 206 };
}

function securityHeaders(res) {
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; media-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'");
  res.setHeader('Cross-Origin-Opener-Policy', 'same-origin');
  res.setHeader('Cross-Origin-Resource-Policy', 'same-origin');
  res.setHeader('Permissions-Policy', 'camera=(), geolocation=(), microphone=()');
  res.setHeader('Referrer-Policy', 'no-referrer');
  res.setHeader('X-Content-Type-Options', 'nosniff');
}

function requestOrigin(req, server) {
  try {
    const host = new URL(`http://${req.headers.host}`);
    const port = server.address()?.port;
    if (!['localhost', '127.0.0.1'].includes(host.hostname) || host.username || host.password || Number(host.port || 80) !== port) return null;
    return host.origin;
  } catch {
    return null;
  }
}

function isSameOrigin(req, origin) {
  if (req.headers.origin === undefined) return true;
  try {
    const supplied = new URL(req.headers.origin);
    return supplied.protocol === 'http:' && !supplied.username && !supplied.password && supplied.origin === req.headers.origin && supplied.origin === origin;
  } catch {
    return false;
  }
}

function sendBuffer(req, res, buffer, contentType) {
  const range = parseRange(req.method === 'GET' ? req.headers.range : undefined, buffer.length);
  const headers = { 'Accept-Ranges': 'bytes', 'Content-Type': contentType };
  if (range.status === 416) {
    headers['Content-Range'] = `bytes */${buffer.length}`;
    headers['Content-Length'] = '0';
    res.writeHead(416, headers).end();
    return;
  }
  const length = Math.max(0, range.end - range.start + 1);
  headers['Content-Length'] = String(length);
  if (range.status === 206) headers['Content-Range'] = `bytes ${range.start}-${range.end}/${buffer.length}`;
  res.writeHead(range.status, headers);
  res.end(req.method === 'HEAD' ? undefined : buffer.subarray(range.start, range.end + 1));
}

async function sendFile(req, res, entry) {
  let handle;
  try {
    handle = await fs.open(entry.path, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0));
    const details = await handle.stat();
    if (!details.isFile()) throw new Error('Not a regular file');
    const range = parseRange(req.method === 'GET' ? req.headers.range : undefined, details.size);
    const headers = { 'Accept-Ranges': 'bytes', 'Content-Type': mimeType(entry.path) };
    if (range.status === 416) {
      headers['Content-Range'] = `bytes */${details.size}`;
      headers['Content-Length'] = '0';
      await handle.close();
      res.writeHead(416, headers).end();
      return;
    }
    const length = Math.max(0, range.end - range.start + 1);
    headers['Content-Length'] = String(length);
    if (range.status === 206) headers['Content-Range'] = `bytes ${range.start}-${range.end}/${details.size}`;
    res.writeHead(range.status, headers);
    if (req.method === 'HEAD' || length === 0) {
      await handle.close();
      res.end();
      return;
    }
    const stream = handle.createReadStream({ start: range.start, end: range.end });
    stream.on('error', () => res.destroy());
    res.on('close', () => stream.destroy());
    stream.pipe(res);
  } catch {
    if (handle) await handle.close().catch(() => {});
    if (!res.headersSent) res.writeHead(404, { 'Content-Length': '0' }).end();
    else res.destroy();
  }
}

export async function createExperimentServer({ aPath, bPath, audioAPath, audioBPath }) {
  const [a, b, audioA, audioB] = await Promise.all([
    localFile(aPath, 'A'), localFile(bPath, 'B'),
    audioAPath ? localFile(audioAPath, 'Audio A') : null,
    audioBPath ? localFile(audioBPath, 'Audio B') : null,
  ]);
  for (const [entry, label] of [[audioA, 'Audio A'], [audioB, 'Audio B']]) {
    if (entry && extname(entry.path).toLowerCase() !== '.wav') throw new Error(`${label} must be a .wav file`);
  }

  const routes = new Map([
    ['/', { path: resolve(ROOT, 'player.html') }],
    ['/player.mjs', { path: resolve(ROOT, 'player.mjs') }],
    ['/assembly.mjs', { path: resolve(ROOT, 'assembly.mjs') }],
    ['/media/a', a], ['/media/b', b],
    ...(audioA ? [['/audio/a', audioA]] : []),
    ...(audioB ? [['/audio/b', audioB]] : []),
  ]);
  const config = Buffer.from(JSON.stringify({
    a: { label: 'A', size: a.size },
    b: { label: 'B', size: b.size },
    audio: {
      a: audioA ? { label: 'Audio A', size: audioA.size } : null,
      b: audioB ? { label: 'Audio B', size: audioB.size } : null,
    },
  }));

  return createServer(async (req, res) => {
    securityHeaders(res);
    const origin = requestOrigin(req, res.socket.server);
    if (!origin) return res.writeHead(421, { 'Content-Length': '0' }).end();
    if (!isSameOrigin(req, origin)) return res.writeHead(403, { 'Content-Length': '0' }).end();
    if (req.method !== 'GET' && req.method !== 'HEAD') return res.writeHead(405, { Allow: 'GET, HEAD', 'Content-Length': '0' }).end();

    let pathname;
    try {
      pathname = new URL(req.url, origin).pathname;
    } catch {
      return res.writeHead(400, { 'Content-Length': '0' }).end();
    }
    if (pathname === '/config.json') return sendBuffer(req, res, config, 'application/json; charset=utf-8');
    const entry = routes.get(pathname);
    if (!entry) return res.writeHead(404, { 'Content-Length': '0' }).end();
    await sendFile(req, res, entry);
  });
}

function parseArgs(argv) {
  const values = new Map();
  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    if (!['--a', '--b', '--audio-a', '--audio-b', '--port'].includes(key) || values.has(key)) throw new Error(`Unknown or repeated option: ${key}`);
    const value = argv[++i];
    if (!value || value.startsWith('--')) throw new Error(`Missing value for ${key}`);
    values.set(key, value);
  }
  const port = values.has('--port') ? Number(values.get('--port')) : 8766;
  if (!Number.isInteger(port) || port < 0 || port > 65535) throw new Error('--port must be an integer from 0 to 65535');
  if (!values.has('--a') || !values.has('--b')) throw new Error('Usage: node server.mjs --a <path> --b <path> [--audio-a <wav>] [--audio-b <wav>] [--port 0|N]');
  return { aPath: values.get('--a'), bPath: values.get('--b'), audioAPath: values.get('--audio-a'), audioBPath: values.get('--audio-b'), port };
}

async function main() {
  try {
    const options = parseArgs(process.argv.slice(2));
    const server = await createExperimentServer(options);
    await new Promise((resolveListen, reject) => {
      server.once('error', reject);
      server.listen(options.port, '127.0.0.1', resolveListen);
    });
    console.log(`Listening at http://127.0.0.1:${server.address().port}`);
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) void main();
