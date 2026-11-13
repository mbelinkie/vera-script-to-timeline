import { Buffer } from "node:buffer";

import type { PrincipalRef } from "@vera/contracts";
import { validateScriptDocumentV2 } from "@vera/contracts/authoring-v2";
import { sha256CanonicalJson } from "@vera/contracts/compiler-core";
import {
  ProjectAuthError,
  ProjectSerializationConflictError,
  type ProjectAuthorizationService,
  type SqlClient,
  type SqlPool,
} from "@vera/project-authorization";
import {
  checkedDocument,
  ProjectDocumentInputError,
  requireUuid,
  type ProjectDocumentService,
} from "@vera/project-documents";
import * as Y from "yjs";

import { applyRootChange, characterKey, readRoot, ROOT_KEY, sameJson, seedRoot, type JsonObject } from "./tree.js";

/** `current`: the saved script holds the live text. `pending`: not written yet. `unstorable`: the merge cannot be saved as a script. */
export type Materialization = "current" | "pending" | "unstorable";

export interface LiveDiagnostic { code: string; message: string; blockId?: string }

export interface LiveStatus {
  projectId: string;
  /** Server order of accepted changes. */
  liveSequence: number;
  /** Base64 Yjs state vector of everything the server has durably accepted. */
  stateVector: string;
  /** Newest saved script revision. This is the only thing a build may freeze. */
  documentRevision: number;
  ideasRevision: number;
  materialization: Materialization;
  /** True only when the saved revision holds the live text and passes script validation. */
  buildable: boolean;
  diagnostics: LiveDiagnostic[];
}

export interface LiveEvent {
  status: LiveStatus;
  /** Yjs updates accepted in this step, in order. Absent when only the status changed. */
  updates: Uint8Array[];
  /** Opaque tag of whoever sent the change, so they can recognise their own. */
  source?: unknown;
}

export interface LiveSession {
  actorId: string;
  canEdit: boolean;
  writeSessionId?: string;
  status: LiveStatus;
}

export interface LiveHistoryEntry {
  liveSequence: number;
  actorId: string;
  origin: "seed" | "client" | "document_save";
  createdAt: string;
}

export class CollaborationError extends Error {
  override readonly name = "CollaborationError";
  constructor(readonly code: "update_refused" | "update_too_large" | "client_identity_conflict" | "not_found") {
    super(code);
  }
}

export interface CollaborationOptions {
  /**
   * How long to wait after a change before writing the merged script as a new
   * saved revision. 0 writes it in the same transaction as the change. A delay
   * keeps revision history from growing with every keystroke; `flush` writes
   * immediately whenever something needs the saved script to be current.
   */
  materializeDelayMs?: number;
  maxUpdateBytes?: number;
}

interface Room {
  doc: Y.Doc;
  liveSequence: number;
  documentRevision: number;
  ideasRevision: number;
  materializedSequence: number;
  materialization: Materialization;
  diagnostics: LiveDiagnostic[];
  lastActor: string;
}

interface HeadRow {
  live_sequence: string;
  state_base64: string;
  document_revision: string;
  ideas_revision: string;
  materialized_sequence: string;
  materialization: Materialization;
  diagnostics_json: string;
  last_actor_id: string;
}

const LIVE_FIELDS = ["liveHeadSequence", "liveStateVector", "liveContentHash"] as const;
const MAX_DIAGNOSTICS = 20;

const base64 = (bytes: Uint8Array): string => Buffer.from(bytes).toString("base64");
const fromBase64 = (text: string): Uint8Array => new Uint8Array(Buffer.from(text, "base64"));

/** The collaboration-owned bookkeeping fields are not script content. */
function withoutLiveFields(document: unknown): JsonObject {
  const copy = { ...(document as JsonObject) };
  for (const field of LIVE_FIELDS) delete copy[field];
  return copy;
}

function diagnosticsFor(document: unknown): LiveDiagnostic[] {
  return validateScriptDocumentV2(document).diagnostics.slice(0, MAX_DIAGNOSTICS)
    .map(({ code, message, blockId }) => ({ code, message, ...(blockId ? { blockId } : {}) }));
}

function isSerializationConflict(error: unknown): boolean {
  if (error instanceof ProjectSerializationConflictError) return true;
  const code = typeof error === "object" && error !== null ? (error as { code?: unknown }).code : undefined;
  return code === "40001" || code === "40P01";
}

function userId(principal: PrincipalRef): string {
  if (principal.principalKind !== "user") throw new ProjectAuthError("action_not_allowed", 403);
  return requireUuid(principal.principalId);
}

/**
 * One shared Yjs document per project, saved beside the existing script store.
 *
 * The saved script (`stt_document_heads`) stays the truth every other feature
 * reads. The Yjs state is the merge machinery: every accepted change is logged
 * with its author, and the merged result is written back as an ordinary
 * script revision. Whole-document saves made outside this service are folded
 * into the Yjs state as a three-way merge before the next change is applied.
 */
export class ProjectCollaborationService {
  private readonly rooms = new Map<string, Room>();
  private readonly chains = new Map<string, Promise<unknown>>();
  private readonly listeners = new Map<string, Set<(event: LiveEvent) => void>>();
  private readonly timers = new Map<string, ReturnType<typeof setTimeout>>();
  private readonly delay: number;
  private readonly maxUpdateBytes: number;

  constructor(
    private readonly pool: SqlPool,
    private readonly auth: ProjectAuthorizationService,
    private readonly documents: ProjectDocumentService,
    options: CollaborationOptions = {},
  ) {
    this.delay = options.materializeDelayMs ?? 0;
    this.maxUpdateBytes = options.maxUpdateBytes ?? 1024 * 1024;
  }

  // ---- plumbing ------------------------------------------------------------

  /** One operation at a time per project; a failed operation forgets the in-memory copy. */
  private serial<T>(projectId: string, work: () => Promise<T>): Promise<T> {
    const previous = this.chains.get(projectId) ?? Promise.resolve();
    const next = previous.catch(() => undefined).then(async () => {
      try {
        return await work();
      } catch (error) {
        this.rooms.delete(projectId);
        throw error;
      }
    });
    this.chains.set(projectId, next);
    void next.catch(() => undefined).finally(() => {
      if (this.chains.get(projectId) === next) this.chains.delete(projectId);
    });
    return next;
  }

  /** Retry a whole transaction on a serialization conflict, always from the stored state. */
  private async retry<T>(projectId: string, work: () => Promise<T>): Promise<T> {
    for (let attempt = 1; ; attempt += 1) {
      try {
        return await work();
      } catch (error) {
        this.rooms.delete(projectId);
        if (attempt >= 3 || !isSerializationConflict(error)) throw error;
      }
    }
  }

  private async transaction<T>(work: (db: SqlClient) => Promise<T>): Promise<T> {
    const db = await this.pool.connect();
    try {
      await db.query("BEGIN ISOLATION LEVEL SERIALIZABLE");
      try {
        const result = await work(db);
        await db.query("COMMIT");
        return result;
      } catch (error) {
        await db.query("ROLLBACK").catch(() => undefined);
        throw error;
      }
    } finally {
      db.release?.();
    }
  }

  private statusOf(projectId: string, room: Room): LiveStatus {
    return {
      projectId,
      liveSequence: room.liveSequence,
      stateVector: base64(Y.encodeStateVector(room.doc)),
      documentRevision: room.documentRevision,
      ideasRevision: room.ideasRevision,
      materialization: room.materialization,
      buildable: room.materialization === "current" && room.diagnostics.length === 0,
      diagnostics: room.diagnostics,
    };
  }

  private emit(projectId: string, event: LiveEvent): void {
    for (const listener of this.listeners.get(projectId) ?? []) {
      try { listener(event); } catch { /* one bad listener must not stop the others */ }
    }
  }

  private schedule(projectId: string): void {
    if (this.timers.has(projectId)) return;
    const timer = setTimeout(() => {
      this.timers.delete(projectId);
      void this.flush(projectId).catch(() => undefined);
    }, this.delay);
    if (typeof timer === "object") timer.unref();
    this.timers.set(projectId, timer);
  }

  // ---- storage steps (all inside one caller transaction) ---------------------

  private async log(
    db: SqlClient, projectId: string, room: Room, actor: string,
    origin: LiveHistoryEntry["origin"], update: Uint8Array, clients: readonly number[],
  ): Promise<void> {
    room.liveSequence += 1;
    await db.query(
      "INSERT INTO stt_live_updates(project_id,live_sequence,actor_id,origin,update_base64) VALUES($1,$2,$3,$4,$5)",
      [projectId, room.liveSequence, actor, origin, base64(update)],
    );
    for (const client of clients) {
      await db.query(
        "INSERT INTO stt_live_clients(project_id,yjs_client_id,actor_id,origin,first_live_sequence)" +
          " VALUES($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING",
        [projectId, client, actor, origin, room.liveSequence],
      );
    }
  }

  /** The room as stored, creating it from the saved script the first time. */
  private async load(db: SqlClient, projectId: string, create: boolean): Promise<{ room: Room; created: boolean } | null> {
    const stored = await db.query<HeadRow>(
      "SELECT live_sequence::text,state_base64,document_revision::text,ideas_revision::text," +
        "materialized_sequence::text,materialization,diagnostics_json,last_actor_id" +
        " FROM stt_live_heads WHERE project_id=$1 FOR UPDATE",
      [projectId],
    );
    const row = stored.rows[0];
    if (row) {
      const cached = this.rooms.get(projectId);
      if (cached && cached.liveSequence === Number(row.live_sequence)) return { room: cached, created: false };
      const doc = new Y.Doc();
      Y.applyUpdate(doc, fromBase64(row.state_base64));
      return { created: false, room: {
        doc,
        liveSequence: Number(row.live_sequence),
        documentRevision: Number(row.document_revision),
        ideasRevision: Number(row.ideas_revision),
        materializedSequence: Number(row.materialized_sequence),
        materialization: row.materialization,
        diagnostics: JSON.parse(row.diagnostics_json) as LiveDiagnostic[],
        lastActor: row.last_actor_id,
      } };
    }
    if (!create) return null;
    const basis = await this.documents.readLiveBasis(db, projectId);
    const doc = new Y.Doc();
    const seed = { document: basis.document, ideas: basis.ideas } as unknown as JsonObject;
    doc.transact(() => { seedRoot(doc, seed); });
    // The shared form must hand back exactly the script it was given, or we
    // would rewrite someone's script just by opening it.
    if (!sameJson(readRoot(doc), seed)) throw new ProjectDocumentInputError("Script cannot be shared losslessly.");
    const room: Room = {
      doc, liveSequence: 0,
      documentRevision: basis.documentRevision, ideasRevision: basis.ideasRevision,
      materializedSequence: 1, materialization: "current",
      diagnostics: diagnosticsFor(basis.document), lastActor: basis.documentUpdatedBy,
    };
    await this.log(db, projectId, room, basis.documentUpdatedBy, "seed", Y.encodeStateAsUpdate(doc), [doc.clientID]);
    await db.query(
      "INSERT INTO stt_live_heads(project_id,live_sequence,state_base64,document_revision,ideas_revision," +
        "materialized_sequence,materialization,diagnostics_json,last_actor_id) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)",
      [projectId, room.liveSequence, base64(Y.encodeStateAsUpdate(doc)), room.documentRevision,
        room.ideasRevision, room.materializedSequence, room.materialization,
        JSON.stringify(room.diagnostics), room.lastActor],
    );
    return { room, created: true };
  }

  /**
   * Fold in a script or Ideas save made outside this service (a whole-document
   * save, an Extras operation, a restore, an Idea promotion). Only what that
   * save changed is applied, so live edits made meanwhile are kept.
   */
  private async reconcile(db: SqlClient, projectId: string, room: Room, updates: Uint8Array[]): Promise<void> {
    const basis = await this.documents.readLiveBasis(db, projectId);
    if (basis.documentRevision === room.documentRevision && basis.ideasRevision === room.ideasRevision) return;
    const old = await this.documents.readLiveRevisions(db, projectId, room.documentRevision, room.ideasRevision);
    // A fresh Yjs client per save, so its characters are attributed to the saver alone.
    const fork = new Y.Doc();
    Y.applyUpdate(fork, Y.encodeStateAsUpdate(room.doc));
    const before = Y.encodeStateVector(fork);
    fork.transact(() => {
      applyRootChange(fork,
        { document: old.document, ideas: old.ideas } as unknown as JsonObject,
        { document: basis.document, ideas: basis.ideas } as unknown as JsonObject);
    });
    const update = Y.encodeStateAsUpdate(fork, before);
    Y.applyUpdate(room.doc, update, "document_save");
    await this.log(db, projectId, room, basis.documentUpdatedBy, "document_save", update, [fork.clientID]);
    updates.push(update);
    room.documentRevision = basis.documentRevision;
    room.ideasRevision = basis.ideasRevision;
    const live = readRoot(room.doc);
    if (sameJson(withoutLiveFields(live.document), withoutLiveFields(basis.document)) &&
        sameJson(live.ideas, basis.ideas)) {
      room.materialization = "current";
      room.materializedSequence = room.liveSequence;
      room.diagnostics = diagnosticsFor(basis.document);
    } else if (room.materialization === "current") {
      room.materialization = "pending";
    }
  }

  /** Accept one client's Yjs update. Returns false when it changed nothing. */
  private async accept(
    db: SqlClient, projectId: string, room: Room, actor: string, update: Uint8Array,
  ): Promise<boolean> {
    if (update.byteLength > this.maxUpdateBytes) throw new CollaborationError("update_too_large");
    let clients: number[];
    try {
      clients = [...new Set(Y.decodeUpdate(update).structs.map((struct) => struct.id.client))];
    } catch {
      throw new CollaborationError("update_refused");
    }
    // A Yjs client ID belongs to one person for good; nobody can write as someone else.
    for (const client of clients) {
      const owner = await db.query<{ actor_id: string }>(
        "SELECT actor_id FROM stt_live_clients WHERE project_id=$1 AND yjs_client_id=$2",
        [projectId, client],
      );
      if (owner.rows[0] && owner.rows[0].actor_id !== actor) throw new CollaborationError("client_identity_conflict");
    }
    let changed = false;
    const onUpdate = (): void => { changed = true; };
    room.doc.on("update", onUpdate);
    try {
      Y.applyUpdate(room.doc, update, "client");
    } catch {
      throw new CollaborationError("update_refused");
    } finally {
      room.doc.off("update", onUpdate);
    }
    if (!changed) return false;
    await this.log(db, projectId, room, actor, "client", update, clients);
    room.lastActor = actor;
    room.materialization = "pending";
    return true;
  }

  /** Write the merged text as the next saved script/Ideas revision, if it can be saved. */
  private async materialize(db: SqlClient, projectId: string, room: Room): Promise<void> {
    const live = readRoot(room.doc);
    const basis = await this.documents.readLiveBasis(db, projectId);
    const problems: LiveDiagnostic[] = [];
    let documentRevision: number | null = null;
    let ideasRevision: number | null = null;

    const merged = live.document;
    if (!sameJson(withoutLiveFields(merged), withoutLiveFields(basis.document))) {
      const stamped: JsonObject = {
        ...withoutLiveFields(merged),
        liveHeadSequence: room.liveSequence,
        liveStateVector: base64(Y.encodeStateVector(room.doc)),
      };
      stamped.liveContentHash = sha256CanonicalJson(stamped);
      let storable = true;
      try {
        checkedDocument(stamped, projectId, basis.documentId);
      } catch (error) {
        if (!(error instanceof ProjectDocumentInputError)) throw error;
        storable = false;
      }
      if (storable) {
        const receipt = await this.documents.commitLiveDocument(db, projectId, room.lastActor, room.documentRevision, stamped);
        room.documentRevision = documentRevision = receipt.revision;
      } else {
        const found = diagnosticsFor(stamped);
        problems.push(...(found.length ? found : [{ code: "SCRIPT_UNSTORABLE", message: "The merged script cannot be saved yet." }]));
      }
    }

    try {
      const saved = await this.documents.commitLiveIdeas(db, projectId, room.lastActor, room.ideasRevision, live.ideas);
      if (saved.changed) room.ideasRevision = ideasRevision = saved.ideasRevision;
    } catch (error) {
      if (!(error instanceof ProjectDocumentInputError)) throw error;
      problems.push({ code: "IDEAS_UNSTORABLE", message: "The merged Ideas cannot be saved yet." });
    }

    if (documentRevision !== null || ideasRevision !== null) {
      await db.query(
        "INSERT INTO stt_live_materializations(project_id,live_sequence,document_revision,ideas_revision)" +
          " VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING",
        [projectId, room.liveSequence, documentRevision, ideasRevision],
      );
    }
    if (problems.length) {
      // Nothing is discarded: the live text stays as typed and the last good
      // saved revision stays in place until an edit makes the merge savable.
      room.materialization = "unstorable";
      room.diagnostics = problems.slice(0, MAX_DIAGNOSTICS);
    } else {
      room.materialization = "current";
      room.materializedSequence = room.liveSequence;
      room.diagnostics = documentRevision === null ? diagnosticsFor(basis.document) : diagnosticsFor(merged);
    }
  }

  private async save(db: SqlClient, projectId: string, room: Room): Promise<void> {
    await db.query(
      "UPDATE stt_live_heads SET live_sequence=$2,state_base64=$3,document_revision=$4,ideas_revision=$5," +
        "materialized_sequence=$6,materialization=$7,diagnostics_json=$8,last_actor_id=$9,updated_at=now()" +
        " WHERE project_id=$1",
      [projectId, room.liveSequence, base64(Y.encodeStateAsUpdate(room.doc)), room.documentRevision,
        room.ideasRevision, room.materializedSequence, room.materialization,
        JSON.stringify(room.diagnostics), room.lastActor],
    );
  }

  /** Shared tail of every operation: remember the room, tell listeners, schedule the write-back. */
  private finish(projectId: string, room: Room, updates: Uint8Array[], changed: boolean, source?: unknown): LiveStatus {
    this.rooms.set(projectId, room);
    const status = this.statusOf(projectId, room);
    if (changed) this.emit(projectId, { status, updates, ...(source === undefined ? {} : { source }) });
    if (room.materialization === "pending") this.schedule(projectId);
    return status;
  }

  // ---- public API -----------------------------------------------------------

  /** Join a project. Viewers may watch; only people who may edit get a write session. */
  async open(projectIdInput: string, principal: PrincipalRef): Promise<LiveSession> {
    const projectId = requireUuid(projectIdInput);
    const actorId = userId(principal);
    const status = await this.serial(projectId, () => this.retry(projectId, async () => {
      const updates: Uint8Array[] = [];
      const result = await this.auth.withAuthorizedMutation(projectId, principal, "view_document", async (db) => {
        const loaded = await this.load(db, projectId, true);
        const room = loaded!.room;
        const before = room.liveSequence;
        await this.reconcile(db, projectId, room, updates);
        if (room.liveSequence !== before) await this.save(db, projectId, room);
        return { room, changed: room.liveSequence !== before };
      });
      return this.finish(projectId, result.room, updates, result.changed);
    }));
    let writeSessionId: string | undefined;
    try {
      writeSessionId = await this.auth.openWriteSession(projectId, principal);
    } catch (error) {
      if (!(error instanceof ProjectAuthError) || error.code !== "action_not_allowed") throw error;
    }
    return { actorId, canEdit: writeSessionId !== undefined, status,
      ...(writeSessionId === undefined ? {} : { writeSessionId }) };
  }

  /** Throws unless this person may still see the project. */
  async assertMayView(projectIdInput: string, principal: PrincipalRef): Promise<void> {
    await this.auth.authorizeRequest(requireUuid(projectIdInput), principal, "view_document");
  }

  /** Throws unless this person's write session is still good. */
  async assertMayEdit(projectIdInput: string, principal: PrincipalRef, writeSessionId: string): Promise<void> {
    await this.auth.authorizeRequest(requireUuid(projectIdInput), principal, "edit_document", writeSessionId);
  }

  /**
   * Accept one person's change. Permission and the write session are checked
   * in the same transaction that stores it, so a viewer or a removed member is
   * refused and nothing is stored.
   */
  async applyUpdate(
    projectIdInput: string, principal: PrincipalRef, writeSessionId: string,
    update: Uint8Array, source?: unknown,
  ): Promise<LiveStatus> {
    const projectId = requireUuid(projectIdInput);
    return await this.serial(projectId, () => this.retry(projectId, async () => {
      const updates: Uint8Array[] = [];
      const result = await this.auth.withAuthorizedMutation(projectId, principal, "edit_document", async (db, actor) => {
        const loaded = await this.load(db, projectId, true);
        const room = loaded!.room;
        const before = room.liveSequence;
        await this.reconcile(db, projectId, room, updates);
        if (await this.accept(db, projectId, room, actor, update)) updates.push(update);
        if (room.materialization === "pending" && this.delay <= 0) await this.materialize(db, projectId, room);
        if (room.liveSequence !== before) await this.save(db, projectId, room);
        return { room, changed: room.liveSequence !== before };
      }, writeSessionId);
      return this.finish(projectId, result.room, updates, result.changed, source);
    }));
  }

  /**
   * Make the saved script current with the live text (and fold in any save
   * made elsewhere). Call before anything reads the saved script and after
   * anything else writes it. Does nothing for a project nobody has opened live.
   */
  async flush(projectIdInput: string): Promise<LiveStatus | null> {
    const projectId = requireUuid(projectIdInput);
    const timer = this.timers.get(projectId);
    if (timer) { clearTimeout(timer); this.timers.delete(projectId); }
    return await this.serial(projectId, () => this.retry(projectId, async () => {
      const updates: Uint8Array[] = [];
      const result = await this.transaction(async (db) => {
        const loaded = await this.load(db, projectId, false);
        if (!loaded) return null;
        const room = loaded.room;
        const before = { sequence: room.liveSequence, state: room.materialization, revision: room.documentRevision,
          ideas: room.ideasRevision };
        await this.reconcile(db, projectId, room, updates);
        if (room.materialization !== "current") await this.materialize(db, projectId, room);
        const changed = room.liveSequence !== before.sequence || room.materialization !== before.state ||
          room.documentRevision !== before.revision || room.ideasRevision !== before.ideas;
        if (changed) await this.save(db, projectId, room);
        return { room, changed };
      });
      return result ? this.finish(projectId, result.room, updates, result.changed) : null;
    }));
  }

  /** True while this process holds live text that is not yet in the saved script. No database access. */
  hasPending(projectId: string): boolean {
    return this.timers.has(projectId.toLowerCase());
  }

  /** True while this process has the project open live. No database access. */
  isActive(projectId: string): boolean {
    const id = projectId.toLowerCase();
    return this.rooms.has(id) || this.listeners.has(id);
  }

  /** After a restart: write back anything that was accepted but not yet saved as a script revision. */
  async recover(): Promise<void> {
    const db = await this.pool.connect();
    let pending: readonly { project_id: string }[];
    try {
      pending = (await db.query<{ project_id: string }>(
        "SELECT project_id FROM stt_live_heads WHERE materialization='pending'")).rows;
    } finally {
      db.release?.();
    }
    for (const row of pending) await this.flush(row.project_id).catch(() => undefined);
  }

  /** The Yjs update a client needs, given the state vector it already has. */
  async encodeState(projectIdInput: string, stateVector?: Uint8Array): Promise<Uint8Array> {
    const projectId = requireUuid(projectIdInput);
    return await this.serial(projectId, async () => {
      let room = this.rooms.get(projectId);
      if (!room) {
        const loaded = await this.transaction((db) => this.load(db, projectId, false));
        if (!loaded) throw new CollaborationError("not_found");
        room = loaded.room;
        this.rooms.set(projectId, room);
      }
      return Y.encodeStateAsUpdate(room.doc, stateVector);
    });
  }

  subscribe(projectIdInput: string, listener: (event: LiveEvent) => void): () => void {
    const projectId = requireUuid(projectIdInput);
    const set = this.listeners.get(projectId) ?? new Set();
    set.add(listener);
    this.listeners.set(projectId, set);
    return () => {
      set.delete(listener);
      if (!set.size) this.listeners.delete(projectId);
    };
  }

  /** Every accepted change, in server order, with the person who made it. */
  async history(projectIdInput: string, principal: PrincipalRef): Promise<LiveHistoryEntry[]> {
    const projectId = requireUuid(projectIdInput);
    return await this.auth.withAuthorizedMutation(projectId, principal, "view_history", async (db) => {
      const rows = await db.query<{ live_sequence: string; actor_id: string; origin: LiveHistoryEntry["origin"]; created_at: Date | string }>(
        "SELECT live_sequence::text,actor_id,origin,created_at FROM stt_live_updates" +
          " WHERE project_id=$1 ORDER BY live_sequence",
        [projectId],
      );
      return rows.rows.map((row) => ({
        liveSequence: Number(row.live_sequence), actorId: row.actor_id, origin: row.origin,
        createdAt: new Date(row.created_at).toISOString(),
      }));
    });
  }

  /** Who typed each stretch of one Draft row's current text. */
  async authorship(
    projectIdInput: string, principal: PrincipalRef, rowIdInput: string,
  ): Promise<{ actorId: string | null; text: string }[]> {
    const projectId = requireUuid(projectIdInput);
    const rowId = requireUuid(rowIdInput);
    const state = await this.encodeState(projectId);
    return await this.auth.withAuthorizedMutation(projectId, principal, "view_history", async (db) => {
      const owners = await db.query<{ yjs_client_id: string; actor_id: string }>(
        "SELECT yjs_client_id::text,actor_id FROM stt_live_clients WHERE project_id=$1", [projectId]);
      const byClient = new Map(owners.rows.map((row) => [row.yjs_client_id, row.actor_id]));
      const doc = new Y.Doc();
      Y.applyUpdate(doc, state);
      let node: unknown = doc.getMap(ROOT_KEY);
      for (const key of ["document", "activeDraft", "blocks", rowId, "text"]) {
        node = node instanceof Y.Map ? (node as Y.Map<unknown>).get(key) : undefined;
      }
      if (!(node instanceof Y.Text)) throw new CollaborationError("not_found");
      const content = node.toJSON();
      const runs: { actorId: string | null; text: string }[] = [];
      for (let index = 0; index < content.length; index += 1) {
        const client = characterKey(node, index)?.split(":")[0];
        const actorId = (client === undefined ? undefined : byClient.get(client)) ?? null;
        const last = runs.at(-1);
        if (last && last.actorId === actorId) last.text += content[index]!;
        else runs.push({ actorId, text: content[index]! });
      }
      return runs;
    });
  }

  /** Stop timers. Pending write-backs are flushed first. */
  async close(): Promise<void> {
    const pending = [...this.timers.keys()];
    for (const timer of this.timers.values()) clearTimeout(timer);
    this.timers.clear();
    await Promise.all(pending.map((projectId) => this.flush(projectId).catch(() => undefined)));
  }
}
