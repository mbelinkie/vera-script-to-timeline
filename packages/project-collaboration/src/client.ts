import * as awarenessProtocol from "y-protocols/awareness";
import * as Y from "yjs";

import { decodeMessage, encodeMessage, type Message, type RosterEntry } from "./protocol.js";
import type { LiveStatus } from "./service.js";
import { applyRootChange, readRoot, ROOT_KEY, type JsonObject } from "./tree.js";

/** The five states the editor shows (product spec 6.8). */
export type SyncState = "offline" | "local changes" | "syncing" | "synced" | "sync failed";

export interface ClientTransport {
  send(bytes: Uint8Array): void;
  close(): void;
}

export interface ClientOptions {
  /** Typing within this many milliseconds is undone as one step. Default 500. */
  undoCaptureMs?: number;
}

const REMOTE = "remote";

function base64ToBytes(text: string): Uint8Array {
  return Uint8Array.from(atob(text), (character) => character.charCodeAt(0));
}

/**
 * One person's copy of a project's shared document. It keeps working while
 * offline; whatever was changed is sent and merged on the next connection.
 * Transport-agnostic and browser-safe.
 */
export class CollaborationClient {
  readonly doc = new Y.Doc();
  readonly awareness = new awarenessProtocol.Awareness(this.doc);
  /** Undo and redo cover only this person's own changes in this session. */
  readonly undoManager: Y.UndoManager;
  status: LiveStatus | undefined;
  actorId: string | undefined;
  canEdit = false;
  roster: RosterEntry[] = [];
  /** Why the last change was not stored, when the state is `sync failed`. */
  failure: string | undefined;

  private readonly origin = {};
  private readonly listeners = new Set<() => void>();
  private transport: ClientTransport | undefined;
  private loaded = false;
  private handshaken = false;
  private localSeq = 0;
  private ackedSeq = 0;
  private batch: Uint8Array[] = [];
  /** Set when the server refused something: the next send carries everything it lacks. */
  private resend = false;
  private batching = false;

  constructor(options: ClientOptions = {}) {
    this.undoManager = new Y.UndoManager(this.doc.getMap(ROOT_KEY), {
      trackedOrigins: new Set([this.origin]),
      captureTimeout: options.undoCaptureMs ?? 500,
    });
    this.doc.on("update", (update: Uint8Array, origin: unknown) => {
      if (origin === REMOTE) return;
      this.localSeq += 1;
      this.failure = undefined;
      this.batch.push(update);
      if (!this.batching) {
        this.batching = true;
        queueMicrotask(() => { this.batching = false; this.sendBatch(); });
      }
      this.notify();
    });
    this.awareness.on("update", (changes: { added: number[]; updated: number[]; removed: number[] }, origin: unknown) => {
      if (origin !== "local") return;
      this.send({ type: "awareness", update: awarenessProtocol.encodeAwarenessUpdate(this.awareness,
        [...changes.added, ...changes.updated, ...changes.removed]) });
    });
  }

  get state(): SyncState {
    if (!this.transport) return "offline";
    if (this.failure !== undefined) return "sync failed";
    if (!this.handshaken) return "syncing";
    if (this.batch.length) return "local changes";
    return this.ackedSeq >= this.localSeq ? "synced" : "syncing";
  }

  /** True while this person has changes the server has not yet stored. */
  get hasUnsyncedChanges(): boolean { return this.ackedSeq < this.localSeq; }

  onChange(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  }

  private notify(): void {
    for (const listener of [...this.listeners]) listener();
  }

  private send(message: Message): void {
    try { this.transport?.send(encodeMessage(message)); } catch { /* the close handler reports it */ }
  }

  private sendBatch(): void {
    if (!this.transport || !this.handshaken || !this.batch.length) return;
    const known = this.resend && this.status ? base64ToBytes(this.status.stateVector) : undefined;
    const update = known ? Y.encodeStateAsUpdate(this.doc, known)
      : this.batch.length === 1 ? this.batch[0]! : Y.mergeUpdates(this.batch);
    this.batch = [];
    this.resend = false;
    this.send({ type: "clientUpdate", seq: this.localSeq, update });
    this.notify();
  }

  /** A connection is open. The server speaks first. */
  attach(transport: ClientTransport): void {
    this.transport = transport;
    this.handshaken = false;
    this.failure = undefined;
    if (this.awareness.getLocalState() !== null) {
      this.send({ type: "awareness", update: awarenessProtocol.encodeAwarenessUpdate(this.awareness, [this.doc.clientID]) });
    }
    this.notify();
  }

  /** The connection is gone. Local changes are kept for the next one. */
  detached(): void {
    if (!this.transport) return;
    this.transport = undefined;
    this.handshaken = false;
    const others = [...this.awareness.getStates().keys()].filter((id) => id !== this.doc.clientID);
    awarenessProtocol.removeAwarenessStates(this.awareness, others, REMOTE);
    this.roster = [];
    this.notify();
  }

  disconnect(): void {
    const transport = this.transport;
    this.detached();
    try { transport?.close(); } catch { /* already closed */ }
  }

  receive(bytes: Uint8Array): void {
    const message = decodeMessage(bytes);
    if (!message) return;
    if (message.type === "stateVector") {
      // The server told us what it has. Ask for what we lack, and send
      // everything of ours it lacks (including deletions made offline).
      this.send({ type: "stateVector", stateVector: Y.encodeStateVector(this.doc) });
      this.batch = [];
      this.resend = false;
      if (this.ackedSeq < this.localSeq) {
        this.send({ type: "clientUpdate", seq: this.localSeq,
          update: Y.encodeStateAsUpdate(this.doc, message.stateVector) });
      }
    } else if (message.type === "update") {
      Y.applyUpdate(this.doc, message.update, REMOTE);
      this.loaded = true;
      this.handshaken = true;
      this.sendBatch();
    } else if (message.type === "awareness") {
      awarenessProtocol.applyAwarenessUpdate(this.awareness, message.update, REMOTE);
    } else if (message.type === "status") {
      this.status = message.body.status;
      this.actorId = message.body.actorId;
      this.canEdit = message.body.canEdit;
      this.ackedSeq = Math.max(this.ackedSeq, message.body.ackedSeq);
    } else if (message.type === "refused") {
      // Nothing refused counts as stored: it is sent again with the next change, or on `retry`.
      this.failure = message.body.code;
      this.resend = true;
    } else if (message.type === "roster") {
      this.roster = message.body;
    }
    this.notify();
  }

  /** The shared document as plain JSON: `{ document, ideas }`. */
  read(): JsonObject {
    return readRoot(this.doc);
  }

  /**
   * Edit the shared document. `mutate` receives a private copy of the JSON and
   * changes it in place; only the difference is applied, so text edits merge
   * character by character with what other people are typing.
   */
  change(mutate: (root: JsonObject) => void): void {
    if (!this.loaded) throw new Error("The shared document has not been loaded yet.");
    const before = this.read();
    const after = structuredClone(before);
    mutate(after);
    this.doc.transact(() => { applyRootChange(this.doc, before, after); }, this.origin);
  }

  /** Send again whatever the server refused (for example after a brief outage). */
  retry(): void {
    if (!this.transport || !this.handshaken || !this.resend || !this.status) return;
    this.failure = undefined;
    this.resend = false;
    this.send({ type: "clientUpdate", seq: this.localSeq,
      update: Y.encodeStateAsUpdate(this.doc, base64ToBytes(this.status.stateVector)) });
    this.notify();
  }

  undo(): void { this.undoManager.undo(); }
  redo(): void { this.undoManager.redo(); }

  /** Publish this person's presence (cursor, selected row, ...). Never saved. */
  setPresence(state: JsonObject | null): void {
    this.awareness.setLocalState(state);
  }

  /** Resolves once everything changed here is durably stored; rejects if the server refused it. */
  whenSynced(): Promise<void> {
    return new Promise((resolve, reject) => {
      const check = (): boolean => {
        const state = this.state;
        if (state === "synced") { stop(); resolve(); return true; }
        if (state === "sync failed") { stop(); reject(new Error(this.failure ?? "sync failed")); return true; }
        return false;
      };
      const stop = this.onChange(() => { check(); });
      check();
    });
  }

  destroy(): void {
    this.disconnect();
    this.undoManager.destroy();
    this.awareness.destroy();
    this.doc.destroy();
  }
}
