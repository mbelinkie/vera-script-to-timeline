import { request as nodeRequest } from "node:http";

import { afterEach, describe, expect, it, vi } from "vitest";

import { MAX_PROJECT_API_BODY_BYTES } from "@vera/project-documents";

import { listenQaHttp, QaHttpRefusal } from "../src/http.js";
import { unusedLoopbackPort } from "./loopback-port.js";

const closers: Array<() => Promise<void>> = [];

async function listener(handler: (request: Request) => Promise<Response>) {
  const port = await unusedLoopbackPort();
  const server = await listenQaHttp("127.0.0.1", port, handler);
  closers.push(async () => { await new Promise<void>((resolve) => server.close(() => resolve())); });
  return { port, base: `http://127.0.0.1:${port}` };
}

async function rawRequest(port: number, path: string, chunks: readonly Buffer[] = [],
  headers: Record<string, string> = {}) {
  return await new Promise<{ status: number; text: string; headers: Record<string, string | string[] | undefined> }>(
    (resolve, reject) => {
      const req = nodeRequest({ hostname: "127.0.0.1", port, path, method: "POST", headers }, (res) => {
        const result: Buffer[] = [];
        res.on("data", (part: Buffer) => { result.push(part); });
        res.on("end", () => { resolve({ status: res.statusCode ?? 0,
          text: Buffer.concat(result).toString("utf8"), headers: res.headers }); });
      });
      req.on("error", reject);
      for (const part of chunks) req.write(part);
      req.end();
    },
  );
}
afterEach(async () => { for (const close of closers.splice(0)) await close(); });

describe("restricted Node HTTP to Web Request bridge", () => {
  it("preserves raw method, path, body and response status/headers without trusting forwarded URL", async () => {
    const called = vi.fn((req: Request) => Promise.resolve(new Response("{\"ok\":true}", {
      status: 207, headers: { "x-service-result": "retained", "x-seen-method": req.method, "Cache-Control": "no-store" },
    })));
    const { port, base } = await listener(called);
    const result = await fetch(`${base}/v1/projects?probe=1`, {
      method: "POST", headers: { "content-type": "application/json",
        "x-forwarded-host": "evil.example", "x-test-suite-identity": "root" },
      body: JSON.stringify({ answer: 42 }),
    });
    expect(result.status).toBe(207);
    expect(result.headers.get("x-service-result")).toBe("retained");
    expect(result.headers.get("Cache-Control")).toBe("no-store");
    expect(result.headers.get("X-Content-Type-Options")).toBe("nosniff");
    expect(await result.json()).toEqual({ ok: true });
    const req = called.mock.calls[0]![0];
    expect(req.url).toBe(`http://127.0.0.1:${port}/v1/projects?probe=1`);
    expect(req.method).toBe("POST");
    expect(await req.text()).toBe('{"answer":42}');
    expect(req.headers.get("X-Forwarded-Host")).toBe("evil.example");
  });

  it("refuses malformed request targets and forged Host before reaching the handler", async () => {
    const handler = vi.fn(() => Promise.resolve(new Response("ok")));
    const { port } = await listener(handler);
    for (const path of ["http://evil.test/v1/projects", "//evil.test/v1/projects",
      "/v1/%2fprojects", "/v1/../admin", "/v1/%2e%2e/admin"]) {
      const response = await rawRequest(port, path);
      expect(response.status).toBe(400);
    }
    const forged = await rawRequest(port, "/v1/projects", [], { Host: "attacker.test" });
    expect(forged.status).toBe(400);
    expect(handler).not.toHaveBeenCalled();
  });

  it("refuses large declared and streamed bodies before API access", async () => {
    const handler = vi.fn(() => Promise.resolve(new Response("ok")));
    const { port } = await listener(handler);
    const declared = await rawRequest(port, "/v1/projects", [], {
      "Content-Length": String(MAX_PROJECT_API_BODY_BYTES + 1),
    });
    expect(declared.status).toBe(413);
    const chunks = [Buffer.alloc(256 * 1024), Buffer.alloc(256 * 1024), Buffer.alloc(12)];
    const streamed = await rawRequest(port, "/v1/projects", chunks);
    expect(streamed.status).toBe(413);
    expect(streamed.text).toContain("request_too_large");
    expect(handler).not.toHaveBeenCalled();
  });

  it("redacts unexpected handler failures and refuses unsafe listeners", async () => {
    const secret = "secret-db-credential-159";
    const { base } = await listener(() => Promise.reject(new Error(secret)));
    const response = await fetch(`${base}/v1/projects`);
    expect(response.status).toBe(503);
    expect(await response.text()).toBe('{"error":"service_unavailable"}');
    for (const [host, port] of [["0.0.0.0", await unusedLoopbackPort()],
      ["localhost", await unusedLoopbackPort()], ["127.0.0.1", 0]] as const) {
      let unexpected: Awaited<ReturnType<typeof listenQaHttp>> | undefined;
      try {
        unexpected = await listenQaHttp(host, port, () => Promise.resolve(new Response()));
        throw new Error("unsafe listener unexpectedly accepted");
      } catch (error) {
        expect(error).toBeInstanceOf(QaHttpRefusal);
      } finally {
        if (unexpected) {
          await new Promise<void>((resolve) => { unexpected!.close(() => resolve()); });
        }
      }
    }
  });
});
