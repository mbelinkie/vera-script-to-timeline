import type { PrincipalRef } from "@vera/contracts";
import { ProjectAuthError } from "@vera/project-authorization";
import { ProjectDocumentError } from "@vera/project-documents";
import * as awarenessProtocol from "y-protocols/awareness";
import * as Y from "yjs";

import { awarenessClientIds, decodeMessage, encodeMessage, type Message, type RosterEntry } from "./protocol.js";
import { CollaborationError, type LiveEvent, type LiveStatus, type ProjectCollaborationService } from "./service.js";

/** Whatever carries bytes to one client: a WebSocket in production, a function pair in tests. */
export interface ConnectionTransport {
  send(bytes: Uint8Array): void;
  close(code: number, reason: string): void;
}

export const CLOSE_ACCESS_REMOVED = 4403;
export const CLOSE_SERVER_STOPPING = 1001;

export interface PresenceEntry { actorId: string; canEdit: boolean; states: unknown[] }

interface ProjectPresence {
  awareness: awarenessProtocol.Awareness;
  connections: Set<CollaborationConnection>;
  unsubscribe: () => void;
}

function base64ToBytes(text: string): Uint8Array {
  return new Uint8Array(Buffer.from(text, "base64"));
}

/** One signed-in person's live connection to one project. */
export class CollaborationConnection {
  readonly awarenessIds = new Set<number>();
  private queue: Promise<void> = Promise.resolve();
  private ackedSeq = 0;
  open = true;

  constructor(
    private readonly hub: CollaborationHub,
    readonly projectId: string,
    readonly principal: PrincipalRef,
    readonly actorId: string,
    public canEdit: boolean,
    public writeSessionId: string | undefined,
    private readonly transport: ConnectionTransport,
  ) {}

  send(message: Message): void {
    if (!this.open) return;
    try { this.transport.send(encodeMessage(message)); } catch { /* the close handler tidies up */ }
  }

  sendStatus(status: LiveStatus): void {
    this.send({ type: "status", body: { status, actorId: this.actorId, canEdit: this.canEdit, ackedSeq: this.ackedSeq } });
  }

  /** Feed one incoming binary message. Messages are handled strictly in order. */
  receive(bytes: Uint8Array): void {
    this.queue = this.queue.then(() => this.handle(bytes)).catch(() => undefined);
  }

  /** Resolves when everything received so far has been handled. */
  settled(): Promise<void> { return this.queue; }

  private async handle(bytes: Uint8Array): Promise<void> {
    if (!this.open) return;
    const message = decodeMessage(bytes);
    if (!message) return;
    if (message.type === "stateVector") {
      this.send({ type: "update", update: await this.hub.service.encodeState(this.projectId, message.stateVector) });
    } else if (message.type === "awareness") {
      this.hub.acceptAwareness(this, message.update);
    } else if (message.type === "clientUpdate") {
      await this.store(message.seq, message.update);
    }
  }

  private async store(seq: number, update: Uint8Array): Promise<void> {
    for (let attempt = 0; ; attempt += 1) {
      try {
        if (!this.canEdit || this.writeSessionId === undefined) throw new ProjectAuthError("action_not_allowed", 403);
        const status = await this.hub.service.applyUpdate(this.projectId, this.principal, this.writeSessionId, update, this);
        this.ackedSeq = Math.max(this.ackedSeq, seq);
        this.sendStatus(status);
        return;
      } catch (error) {
        // Their role may have changed since this session opened: recheck
        // against current membership, and try once more if they may still edit.
        const access = error instanceof ProjectAuthError ? await this.hub.recheck(this) : "view";
        if (attempt === 0 && error instanceof ProjectAuthError && access === "edit") continue;
        const code = error instanceof ProjectAuthError || error instanceof CollaborationError ||
          error instanceof ProjectDocumentError ? error.code : "service_unavailable";
        this.send({ type: "refused", body: { code, seq } });
        if (access === "gone") this.close(CLOSE_ACCESS_REMOVED, "access_removed");
        return;
      }
    }
  }

  close(code: number, reason: string): void {
    if (!this.open) return;
    this.open = false;
    try { this.transport.close(code, reason); } catch { /* already gone */ }
    this.hub.left(this);
  }

  /** Call when the transport closed on its own. */
  disconnected(): void {
    if (!this.open) return;
    this.open = false;
    this.hub.left(this);
  }
}

export interface HubOptions {
  /** How often to recheck every connection's permission. 0 turns the timer off. */
  revalidateIntervalMs?: number;
}

/**
 * Everything that is about connections rather than storage: who is connected,
 * presence, fan-out of accepted changes, and removing people who lose access.
 * Presence lives only in memory here; it is never saved and never touches the
 * script or a build.
 */
export class CollaborationHub {
  private readonly projects = new Map<string, ProjectPresence>();
  private readonly timer: ReturnType<typeof setInterval> | undefined;

  constructor(readonly service: ProjectCollaborationService, options: HubOptions = {}) {
    const interval = options.revalidateIntervalMs ?? 5_000;
    if (interval > 0) {
      this.timer = setInterval(() => { void this.revalidateAll().catch(() => undefined); }, interval);
      this.timer.unref();
    }
  }

  /** Authorizes, joins and greets one connection. Throws ProjectAuthError if the person may not view. */
  async connect(projectId: string, principal: PrincipalRef, transport: ConnectionTransport): Promise<CollaborationConnection> {
    const session = await this.service.open(projectId, principal);
    const id = session.status.projectId;
    const connection = new CollaborationConnection(this, id, principal, session.actorId,
      session.canEdit, session.writeSessionId, transport);
    let project = this.projects.get(id);
    if (!project) {
      const awareness = new awarenessProtocol.Awareness(new Y.Doc());
      awareness.setLocalState(null);
      const created: ProjectPresence = {
        awareness, connections: new Set(),
        unsubscribe: this.service.subscribe(id, (event) => { this.fanOut(created, event); }),
      };
      awareness.on("update", (changes: { added: number[]; updated: number[]; removed: number[] }, origin: unknown) => {
        const update = awarenessProtocol.encodeAwarenessUpdate(awareness,
          [...changes.added, ...changes.updated, ...changes.removed]);
        for (const other of created.connections) if (other !== origin) other.send({ type: "awareness", update });
      });
      this.projects.set(id, project = created);
    }
    project.connections.add(connection);
    connection.send({ type: "stateVector", stateVector: base64ToBytes(session.status.stateVector) });
    connection.sendStatus(session.status);
    const present = [...project.awareness.getStates().keys()];
    if (present.length) {
      connection.send({ type: "awareness", update: awarenessProtocol.encodeAwarenessUpdate(project.awareness, present) });
    }
    this.sendRoster(project);
    return connection;
  }

  private fanOut(project: ProjectPresence, event: LiveEvent): void {
    for (const connection of project.connections) {
      if (connection !== event.source) for (const update of event.updates) connection.send({ type: "update", update });
      connection.sendStatus(event.status);
    }
  }

  private roster(project: ProjectPresence): RosterEntry[] {
    return [...project.connections].map((connection) => ({
      actorId: connection.actorId, canEdit: connection.canEdit, awarenessClientIds: [...connection.awarenessIds],
    }));
  }

  private sendRoster(project: ProjectPresence): void {
    const body = this.roster(project);
    for (const connection of project.connections) connection.send({ type: "roster", body });
  }

  /** A connection may only speak for presence IDs that no other connection owns. */
  acceptAwareness(connection: CollaborationConnection, update: Uint8Array): void {
    const project = this.projects.get(connection.projectId);
    const ids = awarenessClientIds(update);
    if (!project || !ids) return;
    for (const other of project.connections) {
      if (other !== connection && ids.some((id) => other.awarenessIds.has(id))) return;
    }
    const before = connection.awarenessIds.size;
    for (const id of ids) connection.awarenessIds.add(id);
    awarenessProtocol.applyAwarenessUpdate(project.awareness, update, connection);
    if (connection.awarenessIds.size !== before) this.sendRoster(project);
  }

  left(connection: CollaborationConnection): void {
    const project = this.projects.get(connection.projectId);
    if (!project?.connections.delete(connection)) return;
    awarenessProtocol.removeAwarenessStates(project.awareness, [...connection.awarenessIds], connection);
    if (project.connections.size) {
      this.sendRoster(project);
    } else {
      project.unsubscribe();
      project.awareness.destroy();
      this.projects.delete(connection.projectId);
      // The last person left: make sure the saved script holds everything.
      void this.service.flush(connection.projectId).catch(() => undefined);
    }
  }

  /** Who is connected right now, with whatever presence state they published. */
  presence(projectId: string): PresenceEntry[] {
    const project = this.projects.get(projectId.toLowerCase());
    if (!project) return [];
    const states = project.awareness.getStates();
    return [...project.connections].map((connection) => ({
      actorId: connection.actorId, canEdit: connection.canEdit,
      states: [...connection.awarenessIds].map((id) => states.get(id)).filter((state) => state !== undefined),
    }));
  }

  /**
   * Recheck one connection against current membership, refreshing its write
   * session if its role changed. `gone` means the person may no longer view.
   */
  async recheck(connection: CollaborationConnection): Promise<"edit" | "view" | "gone"> {
    if (!connection.open) return "gone";
    const project = this.projects.get(connection.projectId);
    const was = connection.canEdit;
    try {
      await this.service.assertMayView(connection.projectId, connection.principal);
    } catch (error) {
      // An unreachable database is not a removal; keep the connection.
      if (error instanceof ProjectAuthError && error.code !== "authorization_unavailable") return "gone";
      return connection.canEdit ? "edit" : "view";
    }
    try {
      if (connection.writeSessionId === undefined) throw new ProjectAuthError("version_conflict", 409);
      await this.service.assertMayEdit(connection.projectId, connection.principal, connection.writeSessionId);
    } catch (error) {
      if (!(error instanceof ProjectAuthError) || error.code === "authorization_unavailable") {
        return connection.canEdit ? "edit" : "view";
      }
      // The write session is stale (role changed) or editing is no longer allowed.
      try {
        const session = await this.service.open(connection.projectId, connection.principal);
        connection.canEdit = session.canEdit;
        connection.writeSessionId = session.writeSessionId;
      } catch {
        connection.canEdit = false;
        connection.writeSessionId = undefined;
      }
    }
    if (project && connection.canEdit !== was) this.sendRoster(project);
    return connection.canEdit ? "edit" : "view";
  }

  /** Recheck everyone connected to one project (call after a membership change). */
  async revalidate(projectId: string): Promise<void> {
    const project = this.projects.get(projectId.toLowerCase());
    if (!project) return;
    await Promise.all([...project.connections].map(async (connection) => {
      if (await this.recheck(connection) === "gone") connection.close(CLOSE_ACCESS_REMOVED, "access_removed");
    }));
  }

  async revalidateAll(): Promise<void> {
    await Promise.all([...this.projects.keys()].map((projectId) => this.revalidate(projectId)));
  }

  async close(): Promise<void> {
    if (this.timer) clearInterval(this.timer);
    for (const project of [...this.projects.values()]) {
      for (const connection of [...project.connections]) connection.close(CLOSE_SERVER_STOPPING, "server_stopping");
    }
    await this.service.close();
  }
}
