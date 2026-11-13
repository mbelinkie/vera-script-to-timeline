import type { IncomingMessage, Server } from "node:http";
import type { Duplex } from "node:stream";

import { ProjectAuthError, type ProjectAuthorizationService, type SuiteIdentityPort } from "@vera/project-authorization";
import { WebSocket, WebSocketServer, type RawData } from "ws";

import type { CollaborationClient } from "./client.js";
import type { CollaborationHub } from "./hub.js";

const PATH = /^\/v1\/projects\/([a-fA-F0-9-]{36})\/collaboration$/u;
const MAX_MESSAGE_BYTES = 2 * 1024 * 1024;

function bytes(data: RawData): Uint8Array {
  if (Array.isArray(data)) return new Uint8Array(Buffer.concat(data));
  return data instanceof ArrayBuffer ? new Uint8Array(data) : new Uint8Array(data);
}

function refuse(socket: Duplex, status: number, reason: string): void {
  if (socket.writable) {
    socket.end(`HTTP/1.1 ${status} ${reason}\r\nConnection: close\r\nContent-Length: 0\r\n\r\n`);
  } else {
    socket.destroy();
  }
}

export interface CollaborationSocketDeps {
  identity: SuiteIdentityPort;
  authorization: ProjectAuthorizationService;
  hub: CollaborationHub;
  /** The exact Host header this listener answers to, e.g. `127.0.0.1:43112`. */
  expectedHost: string;
}

/**
 * Handle WebSocket upgrades for `/v1/projects/:id/collaboration`. The upgrade
 * request is signed in exactly like every other API request before any
 * collaboration byte is exchanged. Returns the handler for `server.on("upgrade")`.
 */
export function createCollaborationUpgradeHandler(
  deps: CollaborationSocketDeps,
): (request: IncomingMessage, socket: Duplex, head: Buffer) => void {
  const sockets = new WebSocketServer({ noServer: true, maxPayload: MAX_MESSAGE_BYTES });
  return (request, socket, head) => {
    void (async () => {
      const match = PATH.exec(request.url ?? "");
      if (!match || request.headers.host !== deps.expectedHost) { refuse(socket, 404, "Not Found"); return; }
      const headers = new Headers();
      for (const [key, value] of Object.entries(request.headers)) {
        if (typeof value === "string") headers.set(key, value);
      }
      let principal;
      try {
        principal = await deps.authorization.authenticateRequest(
          new Request(`http://${deps.expectedHost}${request.url}`, { headers }), deps.identity);
        await deps.hub.service.assertMayView(match[1]!, principal);
      } catch (error) {
        const status = error instanceof ProjectAuthError ? error.status : 503;
        refuse(socket, status, status === 401 ? "Unauthorized" : status === 403 ? "Forbidden" : "Service Unavailable");
        return;
      }
      sockets.handleUpgrade(request, socket, head, (webSocket) => {
        // Messages that arrive while the connection is being set up are kept in order.
        const early: Uint8Array[] = [];
        let deliver = (data: Uint8Array): void => { early.push(data); };
        let closed = false;
        let onClose = (): void => { closed = true; };
        webSocket.on("message", (data) => { deliver(bytes(data)); });
        webSocket.on("close", () => { onClose(); });
        webSocket.on("error", () => { webSocket.terminate(); });
        void deps.hub.connect(match[1]!, principal, {
          send: (data) => { if (webSocket.readyState === WebSocket.OPEN) webSocket.send(data); },
          close: (code, reason) => { webSocket.close(code, reason); },
        }).then((connection) => {
          if (closed) { connection.disconnected(); return; }
          onClose = () => { connection.disconnected(); };
          deliver = (data) => { connection.receive(data); };
          for (const data of early) connection.receive(data);
        }).catch(() => { webSocket.close(1011, "unavailable"); });
      });
    })().catch(() => { socket.destroy(); });
  };
}

/** Attach to a plain Node HTTP server (used by the demo and tests). */
export function attachCollaborationSocket(server: Server, deps: CollaborationSocketDeps): void {
  server.on("upgrade", createCollaborationUpgradeHandler(deps));
}

/**
 * Connect a client over a real WebSocket (Node). Resolves once the socket is
 * open; the client goes `offline` by itself when the socket closes.
 */
export function connectCollaborationSocket(
  client: CollaborationClient, url: string, headers: Record<string, string>,
): Promise<{ close(): void; closed: Promise<number> }> {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(url, { headers, maxPayload: MAX_MESSAGE_BYTES });
    let opened = false;
    let settle: (code: number) => void = () => undefined;
    const closed = new Promise<number>((done) => { settle = done; });
    socket.on("open", () => {
      opened = true;
      client.attach({ send: (data) => { socket.send(data); }, close: () => { socket.close(); } });
      resolve({ close: () => { socket.close(); }, closed });
    });
    socket.on("message", (data) => { client.receive(bytes(data)); });
    socket.on("close", (code) => { client.detached(); settle(code); });
    socket.on("error", (error) => { if (!opened) reject(error); });
  });
}
