import { createServer } from "node:http";
import { readFile, rename, rm } from "node:fs/promises";

const DEFAULT_REFRESH_INTERVAL_MS = 15 * 60_000;
const RETRY_INTERVAL_MS = 5 * 60_000;
const MANUAL_COOLDOWN_MS = 30_000;

/**
 * Serve a locally generated VERA dashboard. Reads from GitHub are performed only
 * while a browser is watching, at the configured interval or on explicit refresh.
 * The old HTML remains available if a refresh fails.
 *
 * @param {{outputPath:string, generate:(destination:string)=>Promise<unknown>,
 *   refreshIntervalMs?:number, now?:()=>number, port?:number, host?:string}} options
 */
export async function startProgressServer(options) {
  const {
    outputPath,
    generate,
    refreshIntervalMs = DEFAULT_REFRESH_INTERVAL_MS,
    now = Date.now,
    port = 0,
    host = "127.0.0.1",
  } = options;
  if (!Number.isInteger(refreshIntervalMs) || refreshIntervalMs < 60_000) {
    throw new Error("Dashboard refresh interval must be at least one minute");
  }

  let version = 1;
  let lastUpdated = now();
  let lastAttempt = now();
  let lastManual = -Infinity;
  let error = null;
  let pending = null;
  const tempPath = `${outputPath}.refresh-${process.pid}`;

  function snapshot() {
    return {
      version,
      updatedAt: new Date(lastUpdated).toISOString(),
      refreshing: pending !== null,
      error,
      refreshIntervalSeconds: Math.round(refreshIntervalMs / 1000),
    };
  }

  // Single-flight: concurrent tabs and clicks share one refresh. Writing to a
  // temporary path prevents partially written HTML from reaching any browser.
  function refresh({ manual = false } = {}) {
    if (pending) return pending;
    const time = now();
    if (manual) {
      if (time - lastManual < MANUAL_COOLDOWN_MS) return Promise.resolve(snapshot());
      lastManual = time;
    } else if (time - lastAttempt < (error ? RETRY_INTERVAL_MS : refreshIntervalMs)) {
      return Promise.resolve(snapshot());
    }
    lastAttempt = time;
    pending = (async () => {
      try {
        await generate(tempPath);
        await rename(tempPath, outputPath);
        version += 1;
        lastUpdated = now();
        error = null;
      } catch (cause) {
        error = (cause instanceof Error ? cause.message : String(cause)).slice(0, 350);
        await rm(tempPath, { force: true }).catch(() => {});
      }
    })();
    return pending.then(() => snapshot()).finally(() => { pending = null; });
  }

  const server = createServer(async (request, response) => {
    const route = new URL(request.url ?? "/", "http://localhost").pathname;
    response.setHeader("Cache-Control", "no-store, max-age=0");
    response.setHeader("X-Content-Type-Options", "nosniff");
    try {
      if (request.method === "GET" && route === "/") {
        // Version travels with the served snapshot, not with a later status
        // request, so a refresh racing page-load cannot strand stale content.
        const html = await readFile(outputPath, "utf8");
        const document = html.replace(
          '<html lang="en">',
          `<html lang="en" data-snapshot-version="${version}">`,
        );
        response.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        response.end(document);
      } else if (request.method === "GET" && route === "/status") {
        void refresh(); // Browser polling triggers refresh only when due.
        response.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
        response.end(JSON.stringify(snapshot()));
      } else if (request.method === "POST" && route === "/refresh"
        && request.headers["x-vera-refresh"] === "1") {
        const result = await refresh({ manual: true });
        response.writeHead(result.error ? 503 : 200, { "Content-Type": "application/json; charset=utf-8" });
        response.end(JSON.stringify(result));
      } else {
        response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
        response.end("Not found");
      }
    } catch (cause) {
      response.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" });
      response.end(`Dashboard unavailable: ${cause instanceof Error ? cause.message : String(cause)}`);
    }
  });

  try {
    await new Promise((resolve, reject) => {
      server.once("error", reject);
      server.listen(port, host, () => {
        server.off("error", reject);
        resolve();
      });
    });
  } catch (cause) {
    server.close();
    throw cause;
  }
  const address = server.address();
  return {
    url: `http://${host}:${address.port}/`,
    snapshot,
    refresh,
    close: () => new Promise((resolve, reject) => {
      server.close((cause) => cause ? reject(cause) : resolve());
    }),
  };
}
