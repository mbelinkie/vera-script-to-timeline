import { once } from "node:events";
import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import type { Duplex } from "node:stream";

import { MAX_PROJECT_API_BODY_BYTES } from "@vera/project-documents";

const SAFE_HEADERS = {
  "Cache-Control": "no-store",
  "Content-Type": "application/json; charset=utf-8",
  "X-Content-Type-Options": "nosniff",
};
const HOP_HEADERS = new Set([
  "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
  "te", "trailer", "transfer-encoding", "upgrade",
]);

export class QaHttpRefusal extends Error {
  override readonly name = "QaHttpRefusal";
  constructor() { super("unsafe development-QA HTTP listener"); }
}

function fail(res: ServerResponse, status: number, code: string): void {
  if (res.destroyed || res.writableEnded) return;
  if (res.headersSent) { res.destroy(); return; }
  res.writeHead(status, { ...SAFE_HEADERS, Connection: "close" });
  res.end(JSON.stringify({ error: code }));
}

function validRequestTarget(target: string | undefined): target is string {
  if (!target || target.length > 2048 || !target.startsWith("/") || target.startsWith("//") ||
      Array.from(target).some((c) => c.charCodeAt(0) < 33) || /[\\#]/u.test(target) ||
      /%(?:2f|5c|2e|00)/iu.test(target) ||
      /\/{2,}/u.test(target) || /(?:^|\/)\.{1,2}(?:\/|\?|$)/u.test(target)) return false;
  try { decodeURIComponent(target); } catch { return false; }
  return true;
}

/** Consume stream in bounded memory; never rely only on Content-Length. */
function readBoundedBody(req: IncomingMessage): Promise<Buffer | null> {
  return new Promise((resolve, reject) => {
    const parts: Buffer[] = [];
    let bytes = 0;
    const cleanup = () => {
      req.off("data", onData);
      req.off("end", onEnd);
      req.off("error", onError);
      req.off("aborted", onAbort);
    };
    const onData = (chunk: Buffer | string) => {
      const part = typeof chunk === "string" ? Buffer.from(chunk) : chunk;
      bytes += part.byteLength;
      if (bytes > MAX_PROJECT_API_BODY_BYTES) {
        req.pause();
        cleanup();
        resolve(null);
      } else {
        parts.push(part);
      }
    };
    const onEnd = () => { cleanup(); resolve(Buffer.concat(parts, bytes)); };
    const onError = () => { cleanup(); reject(new Error("request_read_failed")); };
    const onAbort = () => { cleanup(); reject(new Error("request_aborted")); };
    req.on("data", onData);
    req.once("end", onEnd);
    req.once("error", onError);
    req.once("aborted", onAbort);
  });
}

async function writeWebResponse(out: ServerResponse, response: Response): Promise<void> {
  const headers = new Headers(SAFE_HEADERS);
  response.headers.forEach((value, key) => {
    if (!HOP_HEADERS.has(key.toLowerCase())) headers.set(key, value);
  });
  out.writeHead(response.status, Object.fromEntries(headers));
  const reader = response.body?.getReader();
  if (!reader) { out.end(); return; }
  try {
    while (!out.destroyed) {
      const chunk = await reader.read();
      if (chunk.done) break;
      if (!out.write(Buffer.from(chunk.value))) await once(out, "drain");
    }
  } finally {
    if (out.destroyed) await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
  if (!out.destroyed) out.end();
}

/** No proxy/forwarded URL interpretation, cookies, CORS or client identity headers. */
export function createQaHttpListener(
  expectedPort: number,
  handler: (request: Request) => Promise<Response>,
): (incoming: IncomingMessage, outgoing: ServerResponse) => void {
  return (incoming, outgoing) => {
    void (async () => {
      const hostHeaders = incoming.rawHeaders.filter((h, i) =>
        i % 2 === 0 && h.toLowerCase() === "host");
      const authHeaders = incoming.rawHeaders.filter((h, i) =>
        i % 2 === 0 && h.toLowerCase() === "authorization");
      if (hostHeaders.length !== 1 || incoming.headers.host !== `127.0.0.1:${expectedPort}` ||
          authHeaders.length > 1 || !validRequestTarget(incoming.url)) {
        fail(outgoing, 400, "invalid_request");
        return;
      }
      const length = incoming.headers["content-length"];
      if (length !== undefined && (typeof length !== "string" ||
          !/^\d+$/u.test(length) || !Number.isSafeInteger(Number(length)))) {
        fail(outgoing, 400, "invalid_request");
        return;
      }
      if (length !== undefined && Number(length) > MAX_PROJECT_API_BODY_BYTES) {
        fail(outgoing, 413, "request_too_large");
        return;
      }
      const body = await readBoundedBody(incoming);
      if (body === null) { fail(outgoing, 413, "request_too_large"); return; }
      if (body.length > 0 && (incoming.method === "GET" || incoming.method === "HEAD")) {
        fail(outgoing, 400, "invalid_request");
        return;
      }
      const headers = new Headers();
      for (let i = 0; i < incoming.rawHeaders.length; i += 2) {
        const key = incoming.rawHeaders[i];
        const value = incoming.rawHeaders[i + 1];
        if (key && value !== undefined && !HOP_HEADERS.has(key.toLowerCase()) &&
            key.toLowerCase() !== "host") headers.append(key, value);
      }
      const request = new Request(`http://127.0.0.1:${expectedPort}${incoming.url}`, {
        method: incoming.method ?? "GET",
        headers,
        ...(body.length ? { body: new Uint8Array(body) } : {}),
      });
      const result = await handler(request);
      await writeWebResponse(outgoing, result);
    })().catch(() => { fail(outgoing, 503, "service_unavailable"); });
  };
}

/** Bind must be numeric loopback; no wildcard, DNS alias or port-zero fallback. */
export async function listenQaHttp(
  bindHost: string,
  port: number,
  handler: (request: Request) => Promise<Response>,
  /** Optional WebSocket upgrade handler. Without one, every upgrade is dropped. */
  onUpgrade?: (request: IncomingMessage, socket: Duplex, head: Buffer) => void,
): Promise<Server> {
  if (bindHost !== "127.0.0.1" || !Number.isSafeInteger(port) || port < 1024 || port > 65535) {
    throw new QaHttpRefusal();
  }
  const server = createServer(createQaHttpListener(port, handler));
  server.headersTimeout = 10_000;
  server.requestTimeout = 15_000;
  server.keepAliveTimeout = 3_000;
  server.maxHeadersCount = 48;
  server.on("clientError", (_error, socket) => {
    if (socket.writable) socket.end("HTTP/1.1 400 Bad Request\r\nConnection: close\r\nContent-Length: 0\r\n\r\n");
  });
  server.on("upgrade", (request, socket, head) => {
    if (onUpgrade) onUpgrade(request, socket, head);
    else socket.destroy();
  });
  server.on("connect", (_request, socket) => { socket.destroy(); });
  try {
    await new Promise<void>((resolve, reject) => {
      server.once("error", reject);
      server.listen(port, "127.0.0.1", () => { server.off("error", reject); resolve(); });
    });
    return server;
  } catch {
    server.close();
    throw new QaHttpRefusal();
  }
}
