import type { PrincipalRef } from "@vera/contracts";
import type { AuthoringProjectSettingsV1, ScriptDocumentV2 } from "@vera/contracts/v2";
import {
  ProjectAuthError,
  ProjectAuthorizationService,
  ProjectSerializationConflictError,
  type SqlClient,
  type SqlPool,
} from "@vera/project-authorization";

import {
  checkedDocument,
  checkedSettings,
  fingerprint,
  ProjectDocumentError,
  ProjectDocumentInputError,
  requireRevision,
  requireTitle,
  requireUuid,
} from "./model.js";

type Digest = string;
interface HeadRow {
  document_id: string;
  revision: string;
  document_json: string;
  content_digest: Digest;
}
interface SettingsRow {
  settings_id: string;
  settings_revision: string;
  settings_json: string;
  content_digest: Digest;
}
interface ProjectRow {
  id: string;
  title: string;
  project_version: string;
  linked_research_project_ids: string[];
}
interface MutationRow {
  request_digest: string;
  revision: string;
  content_digest: string;
}
interface TitleMutationRow {
  request_digest: string;
  project_version: string;
  title: string;
}

export interface CreateProjectInput {
  clientRequestId: string;
  projectId: string;
  title: string;
  document: ScriptDocumentV2;
  settings?: AuthoringProjectSettingsV1;
}
export interface PutDocumentInput {
  expectedRevision: number;
  clientMutationId: string;
  document: ScriptDocumentV2;
  writeSessionId?: string;
}
export interface PutSettingsInput {
  expectedSettingsRevision: number;
  clientMutationId: string;
  settings: AuthoringProjectSettingsV1;
}
export interface PatchProjectInput {
  expectedProjectVersion: number;
  clientMutationId: string;
  title: string;
}
export interface ProjectView {
  projectId: string;
  title: string;
  projectVersion: number;
  linkedResearchProjectIds: readonly string[];
}
export interface DocumentView {
  projectId: string;
  revision: number;
  digest: string;
  document: ScriptDocumentV2;
}
export interface SettingsView {
  projectId: string;
  settingsRevision: number;
  digest: string;
  settings: AuthoringProjectSettingsV1;
}
export interface MutationReceipt {
  projectId: string;
  clientMutationId: string;
  revision: number;
  digest: string;
  duplicateDelivery: boolean;
}

const unavailable = (): ProjectDocumentError =>
  new ProjectDocumentError("service_unavailable", 503);
const missing = (): ProjectDocumentError =>
  new ProjectDocumentError("not_found", 404);
const conflict = (metadata?: Readonly<Record<string, string | number>>): ProjectDocumentError =>
  new ProjectDocumentError("version_conflict", 409, metadata);
const reused = (): ProjectDocumentError =>
  new ProjectDocumentError("idempotency_conflict", 409);

function pgCode(error: unknown): string | undefined {
  if (error && typeof error === "object" && "code" in error) {
    const code = (error as { code?: unknown }).code;
    return typeof code === "string" ? code : undefined;
  }
  return undefined;
}

/** Retry *whole* SERIALIZABLE operations only; never retry a genuine stale CAS. */
async function retryTransaction<T>(operation: () => Promise<T>): Promise<T> {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      return await operation();
    } catch (error) {
      if (error instanceof ProjectDocumentError || error instanceof ProjectAuthError) throw error;
      if (error instanceof ProjectSerializationConflictError ||
          pgCode(error) === "40001" || pgCode(error) === "40P01") {
        if (attempt < 2) continue;
        throw unavailable();
      }
      if (pgCode(error) === "23505") {
        throw new ProjectDocumentError("already_exists", 409);
      }
      throw unavailable();
    }
  }
  throw unavailable();
}

function actorId(principal: PrincipalRef): string {
  if (principal.principalKind !== "user") throw new ProjectDocumentInputError("Expected suite user actor.");
  return requireUuid(principal.principalId);
}
function int(value: string): number {
  const number = Number(value);
  if (!Number.isSafeInteger(number)) throw unavailable();
  return number;
}
function viewProject(row: ProjectRow): ProjectView {
  // Research links are deliberately disabled; the schema also rejects nonempty arrays.
  return {
    projectId: row.id,
    title: row.title,
    projectVersion: int(row.project_version),
    linkedResearchProjectIds: row.linked_research_project_ids,
  };
}
function viewDocument(projectId: string, row: HeadRow): DocumentView {
  return { projectId, revision: int(row.revision), digest: row.content_digest,
    document: JSON.parse(row.document_json) as ScriptDocumentV2 };
}
function viewSettings(projectId: string, row: SettingsRow): SettingsView {
  return { projectId, settingsRevision: int(row.settings_revision), digest: row.content_digest,
    settings: JSON.parse(row.settings_json) as AuthoringProjectSettingsV1 };
}

export class ProjectDocumentService {
  constructor(
    private readonly pool: SqlPool,
    private readonly auth: ProjectAuthorizationService,
  ) {}

  private async transaction<T>(operation: (db: SqlClient) => Promise<T>): Promise<T> {
    return await retryTransaction(async () => {
      const db = await this.pool.connect();
      try {
        await db.query("BEGIN ISOLATION LEVEL SERIALIZABLE");
        try {
          const result = await operation(db);
          await db.query("COMMIT");
          return result;
        } catch (error) {
          await db.query("ROLLBACK").catch(() => undefined);
          throw error;
        }
      } finally {
        db.release?.();
      }
    });
  }

  private async authorized<T>(
    projectId: string,
    principal: PrincipalRef,
    action: "view_document" | "edit_document" | "manage_settings",
    operation: (db: SqlClient, actor: string) => Promise<T>,
    writeSessionId?: string,
  ): Promise<T> {
    return await retryTransaction(async () =>
      await this.auth.withAuthorizedMutation(projectId, principal, action, operation, writeSessionId));
  }

  private async selectProject(db: SqlClient, projectId: string): Promise<ProjectRow> {
    const result = await db.query<ProjectRow>(
      "SELECT id,title,project_version::text,linked_research_project_ids FROM stt_projects WHERE id=$1",
      [projectId],
    );
    const row = result.rows[0];
    if (!row) throw missing();
    return row;
  }

  async createProject(principal: PrincipalRef, input: CreateProjectInput): Promise<{
    project: ProjectView; documentRevision: number; documentDigest: string;
    duplicateDelivery: boolean;
  }> {
    const projectId = requireUuid(input.projectId);
    const requestId = requireUuid(input.clientRequestId);
    const title = requireTitle(input.title);
    const document = checkedDocument(input.document, projectId);
    const settings = input.settings === undefined ? undefined : checkedSettings(input.settings, projectId);
    const createDigest = fingerprint({ projectId, title, document: document.document, settings: settings?.settings ?? null });
    const creator = actorId(principal);
    return await this.transaction(async (db) => {
      // Authentication happened before the request reached this transaction.
      // Recheck and lock the actor so a concurrent disable cannot interleave
      // between project insertion and first-Producer provisioning.
      const actor = await db.query<{ disabled_at: string | null }>(
        "SELECT disabled_at FROM vera_identity_actors WHERE id=$1 FOR SHARE", [creator],
      );
      if (!actor.rows[0] || actor.rows[0].disabled_at !== null) {
        throw new ProjectAuthError("action_not_allowed", 403);
      }
      // Unique per authenticated actor, independent of projectId. Replays must
      // be authorized again; the old bootstrap cannot act as a permission grant.
      const prior = await db.query<{ id: string; create_request_digest: string }>(
        "SELECT id,create_request_digest FROM stt_projects " +
          "WHERE created_by=$1 AND client_create_request_id=$2",
        [creator, requestId],
      );
      if (prior.rows[0]) {
        if (prior.rows[0].create_request_digest !== createDigest) throw reused();
        await this.auth.authorizeInTransaction(db, prior.rows[0].id, principal, "view_document");
        const project = await this.selectProject(db, prior.rows[0].id);
        const head = await db.query<HeadRow>(
          "SELECT document_id,revision::text,document_json,content_digest FROM stt_document_heads WHERE project_id=$1",
          [project.id],
        );
        if (!head.rows[0]) throw missing();
        return { project: viewProject(project), documentRevision: int(head.rows[0].revision),
          documentDigest: head.rows[0].content_digest, duplicateDelivery: true };
      }
      await db.query(
        "INSERT INTO stt_projects(id,title,created_by,client_create_request_id,create_request_digest) " +
          "VALUES($1,$2,$3,$4,$5)",
        [projectId, title, creator, requestId, createDigest],
      );
      await db.query(
        "INSERT INTO stt_document_heads(project_id,document_id,revision,document_json,content_digest,updated_by) " +
          "VALUES($1,$2,0,$3,$4,$5)",
        [projectId, document.document.id, document.documentJson, document.digest, creator],
      );
      await db.query(
        "INSERT INTO stt_document_revisions(project_id,revision,document_id,expected_revision,actor_id," +
          "client_mutation_id,request_digest,content_digest,document_json) " +
          "VALUES($1,0,$2,NULL,$3,$4,$5,$6,$7)",
        [projectId, document.document.id, creator, requestId, createDigest, document.digest, document.documentJson],
      );
      if (settings) {
        await db.query(
          "INSERT INTO stt_project_settings(project_id,settings_id,settings_revision,settings_json,content_digest,updated_by) " +
            "VALUES($1,$2,1,$3,$4,$5)",
          [projectId, settings.settings.id, settings.settingsJson, settings.digest, creator],
        );
        await db.query(
          "INSERT INTO stt_settings_revisions(project_id,settings_revision,settings_id,expected_revision," +
            "actor_id,client_mutation_id,request_digest,content_digest,settings_json) " +
            "VALUES($1,1,$2,NULL,$3,$4,$5,$6,$7)",
          [projectId, settings.settings.id, creator, requestId, createDigest, settings.digest, settings.settingsJson],
        );
      }
      await this.auth.provisionFirstProducerInProjectTransaction(db, projectId, principal);
      const project = await this.selectProject(db, projectId);
      return { project: viewProject(project), documentRevision: 0,
        documentDigest: document.digest, duplicateDelivery: false };
    });
  }

  async getProject(projectIdInput: string, principal: PrincipalRef): Promise<ProjectView> {
    const projectId = requireUuid(projectIdInput);
    return await this.authorized(projectId, principal, "view_document", async (db) =>
      viewProject(await this.selectProject(db, projectId)));
  }

  async getDocument(projectIdInput: string, principal: PrincipalRef): Promise<DocumentView> {
    const projectId = requireUuid(projectIdInput);
    return await this.authorized(projectId, principal, "view_document", async (db) => {
      const head = await db.query<HeadRow>(
        "SELECT document_id,revision::text,document_json,content_digest " +
          "FROM stt_document_heads WHERE project_id=$1",
        [projectId],
      );
      if (!head.rows[0]) throw missing();
      return viewDocument(projectId, head.rows[0]);
    });
  }

  async getSettings(projectIdInput: string, principal: PrincipalRef): Promise<SettingsView> {
    const projectId = requireUuid(projectIdInput);
    return await this.authorized(projectId, principal, "view_document", async (db) => {
      await this.selectProject(db, projectId);
      const head = await db.query<SettingsRow>(
        "SELECT settings_id,settings_revision::text,settings_json,content_digest " +
          "FROM stt_project_settings WHERE project_id=$1",
        [projectId],
      );
      if (!head.rows[0]) throw missing();
      return viewSettings(projectId, head.rows[0]);
    });
  }

  async putDocument(
    projectIdInput: string, principal: PrincipalRef, input: PutDocumentInput,
  ): Promise<MutationReceipt> {
    const projectId = requireUuid(projectIdInput);
    const mutationId = requireUuid(input.clientMutationId);
    const expected = requireRevision(input.expectedRevision);
    const sessionId = input.writeSessionId === undefined ? undefined : requireUuid(input.writeSessionId);
    const document = checkedDocument(input.document, projectId);
    const requestDigest = fingerprint({ expectedRevision: expected, document: document.document });
    return await this.authorized(projectId, principal, "edit_document", async (db, actor) => {
      const prior = await db.query<MutationRow>(
        "SELECT request_digest,revision::text,content_digest FROM stt_document_revisions " +
          "WHERE project_id=$1 AND actor_id=$2 AND client_mutation_id=$3",
        [projectId, actor, mutationId],
      );
      if (prior.rows[0]) {
        if (prior.rows[0].request_digest !== requestDigest) throw reused();
        return { projectId, clientMutationId: mutationId, revision: int(prior.rows[0].revision),
          digest: prior.rows[0].content_digest, duplicateDelivery: true };
      }
      const head = await db.query<HeadRow>(
        "SELECT document_id,revision::text,document_json,content_digest " +
          "FROM stt_document_heads WHERE project_id=$1",
        [projectId],
      );
      const current = head.rows[0];
      if (!current) throw missing();
      if (requireUuid(document.document.id) !== requireUuid(current.document_id)) {
        throw new ProjectDocumentInputError("Document ID cannot change.");
      }
      if (int(current.revision) !== expected) {
        throw conflict({ currentRevision: int(current.revision), currentDigest: current.content_digest });
      }
      if (expected >= Number.MAX_SAFE_INTEGER) throw new ProjectDocumentInputError("Revision exhausted.");
      const revision = expected + 1;
      await db.query(
        "INSERT INTO stt_document_revisions(project_id,revision,document_id,expected_revision,actor_id," +
          "client_mutation_id,request_digest,content_digest,document_json) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)",
        [projectId, revision, current.document_id, expected, actor, mutationId,
          requestDigest, document.digest, document.documentJson],
      );
      const changed = await db.query<{ revision: string }>(
        "UPDATE stt_document_heads SET revision=$3,document_json=$4,content_digest=$5," +
          "updated_by=$6,updated_at=now() WHERE project_id=$1 AND revision=$2 RETURNING revision::text",
        [projectId, expected, revision, document.documentJson, document.digest, actor],
      );
      if (!changed.rows[0]) throw conflict({ currentRevision: expected });
      return { projectId, clientMutationId: mutationId, revision,
        digest: document.digest, duplicateDelivery: false };
    }, sessionId);
  }

  async patchProject(
    projectIdInput: string, principal: PrincipalRef, input: PatchProjectInput,
  ): Promise<{ project: ProjectView; clientMutationId: string; duplicateDelivery: boolean }> {
    const projectId = requireUuid(projectIdInput);
    const mutationId = requireUuid(input.clientMutationId);
    const expected = requireRevision(input.expectedProjectVersion);
    if (!expected) throw new ProjectDocumentInputError("Project version must be positive.");
    const title = requireTitle(input.title);
    const requestDigest = fingerprint({ expectedProjectVersion: expected, title });
    return await this.authorized(projectId, principal, "manage_settings", async (db, actor) => {
      const prior = await db.query<TitleMutationRow>(
        "SELECT request_digest,project_version::text,title FROM stt_project_title_mutations " +
          "WHERE project_id=$1 AND actor_id=$2 AND client_mutation_id=$3",
        [projectId, actor, mutationId],
      );
      if (prior.rows[0]) {
        if (prior.rows[0].request_digest !== requestDigest) throw reused();
        return { project: { projectId, title: prior.rows[0].title,
          projectVersion: int(prior.rows[0].project_version), linkedResearchProjectIds: [] },
        clientMutationId: mutationId, duplicateDelivery: true };
      }
      const row = await this.selectProject(db, projectId);
      if (int(row.project_version) !== expected) {
        throw conflict({ currentProjectVersion: int(row.project_version) });
      }
      if (expected >= Number.MAX_SAFE_INTEGER) throw new ProjectDocumentInputError("Project version exhausted.");
      const changed = await db.query<{ project_version: string }>(
        "UPDATE stt_projects SET title=$3,project_version=$4,updated_at=now() " +
          "WHERE id=$1 AND project_version=$2 RETURNING project_version::text",
        [projectId, expected, title, expected + 1],
      );
      if (!changed.rows[0]) throw conflict({ currentProjectVersion: expected });
      await db.query(
        "INSERT INTO stt_project_title_mutations(project_id,project_version,expected_project_version," +
          "actor_id,client_mutation_id,request_digest,title) VALUES($1,$2,$3,$4,$5,$6,$7)",
        [projectId, expected + 1, expected, actor, mutationId, requestDigest, title],
      );
      return { project: { ...viewProject(row), title, projectVersion: expected + 1 },
        clientMutationId: mutationId, duplicateDelivery: false };
    });
  }

  async putSettings(
    projectIdInput: string, principal: PrincipalRef, input: PutSettingsInput,
  ): Promise<MutationReceipt> {
    const projectId = requireUuid(projectIdInput);
    const mutationId = requireUuid(input.clientMutationId);
    const expected = requireRevision(input.expectedSettingsRevision);
    const settings = checkedSettings(input.settings, projectId);
    const requestDigest = fingerprint({ expectedSettingsRevision: expected, settings: settings.settings });
    return await this.authorized(projectId, principal, "manage_settings", async (db, actor) => {
      const prior = await db.query<MutationRow>(
        "SELECT request_digest,settings_revision::text AS revision,content_digest " +
          "FROM stt_settings_revisions WHERE project_id=$1 AND actor_id=$2 AND client_mutation_id=$3",
        [projectId, actor, mutationId],
      );
      if (prior.rows[0]) {
        if (prior.rows[0].request_digest !== requestDigest) throw reused();
        return { projectId, clientMutationId: mutationId, revision: int(prior.rows[0].revision),
          digest: prior.rows[0].content_digest, duplicateDelivery: true };
      }
      await this.selectProject(db, projectId);
      const head = await db.query<SettingsRow>(
        "SELECT settings_id,settings_revision::text,settings_json,content_digest " +
          "FROM stt_project_settings WHERE project_id=$1",
        [projectId],
      );
      const current = head.rows[0];
      const currentRevision = current ? int(current.settings_revision) : 0;
      if (current && requireUuid(settings.settings.id) !== requireUuid(current.settings_id)) {
        throw new ProjectDocumentInputError("Settings ID cannot change.");
      }
      if (currentRevision !== expected) {
        throw conflict({ currentSettingsRevision: currentRevision,
          ...(current ? { currentDigest: current.content_digest } : {}) });
      }
      if (expected >= Number.MAX_SAFE_INTEGER) throw new ProjectDocumentInputError("Settings revision exhausted.");
      const revision = expected + 1;
      await db.query(
        "INSERT INTO stt_settings_revisions(project_id,settings_revision,settings_id,expected_revision," +
          "actor_id,client_mutation_id,request_digest,content_digest,settings_json) " +
          "VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)",
        [projectId, revision, settings.settings.id, expected, actor, mutationId,
          requestDigest, settings.digest, settings.settingsJson],
      );
      if (!current) {
        await db.query(
          "INSERT INTO stt_project_settings(project_id,settings_id,settings_revision," +
            "settings_json,content_digest,updated_by) VALUES($1,$2,$3,$4,$5,$6)",
          [projectId, settings.settings.id, revision, settings.settingsJson, settings.digest, actor],
        );
      } else {
        const changed = await db.query<{ settings_revision: string }>(
          "UPDATE stt_project_settings SET settings_revision=$3,settings_json=$4," +
            "content_digest=$5,updated_by=$6,updated_at=now() WHERE project_id=$1 AND settings_revision=$2 " +
            "RETURNING settings_revision::text",
          [projectId, expected, revision, settings.settingsJson, settings.digest, actor],
        );
        if (!changed.rows[0]) throw conflict({ currentSettingsRevision: expected });
      }
      return { projectId, clientMutationId: mutationId, revision,
        digest: settings.digest, duplicateDelivery: false };
    });
  }
}
