import { createHash } from "node:crypto";

export type Capability =
  | "project:create"
  | "project:member"
  | "template:copy-out"
  | "template:discover"
  | "template:intake"
  | "template:manage"
  | "template:register"
  | "template:use";

export interface Actor {
  id: string;
  grants: Array<{ capability: Capability; scope: string }>;
}

export interface ProjectDefinition {
  id: string;
  name: string;
  suiteId: string;
  compatibility: string[];
}

export interface PackageFileDeclaration {
  path: string;
  byteLength: number;
  sha256: string;
  mediaType: string;
  rightsId: string;
}

export interface RightsDeclaration {
  id: string;
  holder: string;
  basis: string;
  embeddingAllowed: boolean;
  redistributionAllowed: boolean;
}

export interface PackageManifest {
  schemaVersion: "external-template-package/v1";
  packageKind: "graphic" | "music_cue";
  externalLineageKey: string;
  displayName: string;
  externalRevisionLabel: string;
  entryPoint: string;
  validator: { profile: string; version: string };
  compatibility: { requiredCapabilities: string[] };
  provenance: {
    author: string;
    publisher: string;
    organization: string;
    sourceTool: string;
    sourceToolVersion: string;
    sourceRevision: string;
    createdAt: string;
    attestedBy: string;
  };
  rights: {
    allowedProjectIds: string[] | "*";
    declarations: RightsDeclaration[];
  };
  files: PackageFileDeclaration[];
}

export interface ExternalTemplatePackage {
  transport: "directory" | "zip";
  manifest: PackageManifest;
  files: Array<{ path: string; bytes: Uint8Array }>;
}

export interface OperationIssue {
  code: string;
  message: string;
  status: "duplicate" | "failed" | "incompatible" | "unauthorized" | "unavailable";
  sourceRevisionId?: string;
  path?: string;
}

export interface OperationReport {
  operation: "create_project" | "list_templates" | "register_package" | "template_lifecycle" | "template_use";
  status: "failed";
  issues: OperationIssue[];
}

export type ServiceResult<T> =
  | { ok: true; value: T }
  | { ok: false; report: OperationReport };

export interface ProjectTemplateRevisionView {
  id: string;
  templateItemId: string;
  projectId: string;
  displayName: string;
  externalLineageKey: string;
  externalRevisionLabel: string;
  packageDigest: string;
  isCurrent: boolean;
  copiedFrom?: { projectId: string; revisionId: string };
}

export interface RegistrationValue {
  packageDigest: string;
  registeredRevisionId: string;
  projectRevision: ProjectTemplateRevisionView;
}

export interface TemplateUse {
  id: string;
  projectId: string;
  projectRevisionId: string;
  packageDigest: string;
  resolvedSnapshotHash: string;
}

export type TemplateSelection =
  | { mode: "none" }
  | { mode: "some"; revisionIds: string[] }
  | { mode: "all"; sourceProjectIds: string[] };

export interface CopyChoiceReport {
  sourceRevisionId: string;
  status: "copied" | "duplicate" | "failed" | "incompatible" | "unauthorized" | "unavailable";
  code: string;
  message: string;
  packageDigest?: string;
  destinationRevisionId?: string;
}

export interface ProjectCreationValue {
  projectId: string;
  selectionMode: TemplateSelection["mode"];
  selectionSnapshotHash: string;
  choices: CopyChoiceReport[];
  exclusions: CopyChoiceReport[];
  idempotencyKey: string;
}

interface RegisteredRevisionState {
  id: string;
  packageDigest: string;
  manifest: PackageManifest;
  files: Map<string, Uint8Array>;
  withdrawn: boolean;
  withdrawalReason?: string;
}

interface ProjectState extends ProjectDefinition {
  libraryVersion: number;
}

interface TemplateItemState {
  id: string;
  projectId: string;
  externalLineageKey: string;
  displayName: string;
  currentRevisionId: string;
  revisionIds: string[];
  active: boolean;
  retirementReason?: string;
}

interface ProjectRevisionState {
  id: string;
  templateItemId: string;
  projectId: string;
  registeredRevisionId: string;
  packageDigest: string;
  externalRevisionLabel: string;
  copiedFrom?: { projectId: string; revisionId: string };
}

interface IdempotencyRecord {
  requestHash: string;
  result: { ok: true; value: ProjectCreationValue };
}

interface PlannedCopy {
  source: ProjectRevisionState;
  item: TemplateItemState;
  registered: RegisteredRevisionState;
}

interface AuditEvent {
  kind: "package_registered" | "project_created" | "template_copied" | "template_retired" | "revision_withdrawn" | "template_use_created";
  actorId: string;
  projectId?: string;
  subjectId: string;
  packageDigest?: string;
  reason?: string;
}

export interface TemplateLibraryServiceOptions {
  projects?: ProjectDefinition[];
  validatorProfiles: Array<{ profile: string; version: string }>;
}

function compareText(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0;
}

function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => compareText(left, right))
        .map(([key, nested]) => [key, canonicalize(nested)]),
    );
  }
  if (typeof value === "number" && !Number.isFinite(value)) {
    throw new TypeError("canonical JSON does not allow non-finite numbers");
  }
  return value;
}

function canonicalJson(value: unknown): string {
  return JSON.stringify(canonicalize(value));
}

export function sha256Bytes(bytes: Uint8Array): string {
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
}

function hashText(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function stableId(prefix: string, value: string): string {
  return `${prefix}_${hashText(value).slice(0, 24)}`;
}

function normalizedManifestForIdentity(manifest: PackageManifest): PackageManifest {
  const clone = structuredClone(manifest);
  clone.files.sort((left, right) => compareText(left.path, right.path));
  clone.compatibility.requiredCapabilities.sort(compareText);
  clone.rights.declarations.sort((left, right) => compareText(left.id, right.id));
  if (Array.isArray(clone.rights.allowedProjectIds)) {
    clone.rights.allowedProjectIds.sort(compareText);
  }
  return clone;
}

export function computePackageDigest(packageValue: ExternalTemplatePackage): string {
  const manifest = normalizedManifestForIdentity(packageValue.manifest);
  const identity = {
    canonicalization: "vera-external-template-v1",
    manifest,
    fileSet: manifest.files.map(({ path, byteLength, sha256 }) => ({ path, byteLength, sha256 })),
  };
  return `sha256:${hashText(canonicalJson(identity))}`;
}

function issue(
  code: string,
  message: string,
  status: OperationIssue["status"] = "failed",
  details: Pick<OperationIssue, "path" | "sourceRevisionId"> = {},
): OperationIssue {
  return { code, message, status, ...details };
}

function failure(operation: OperationReport["operation"], issues: OperationIssue[]): { ok: false; report: OperationReport } {
  return {
    ok: false,
    report: {
      operation,
      status: "failed",
      issues: issues.sort((left, right) =>
        compareText(left.sourceRevisionId ?? "", right.sourceRevisionId ?? "") ||
        compareText(left.code, right.code) ||
        compareText(left.path ?? "", right.path ?? ""),
      ),
    },
  };
}

function hasCapability(actor: Actor, capability: Capability, scope: string): boolean {
  return actor.grants.some((grant) =>
    grant.capability === capability && (grant.scope === scope || grant.scope === "*"),
  );
}

function hasProjectCapability(actor: Actor, capability: Capability, projectId: string): boolean {
  return hasCapability(actor, "project:member", projectId) && hasCapability(actor, capability, projectId);
}

function nonempty(value: string): boolean {
  return value.trim().length > 0;
}

function isSafePackagePath(value: string): boolean {
  if (!nonempty(value) || value.startsWith("/") || value.includes("\\") || value !== value.normalize("NFC")) {
    return false;
  }
  const parts = value.split("/");
  return parts.every((part) => part !== "" && part !== "." && part !== "..");
}

function rightsAllowProject(manifest: PackageManifest, projectId: string): boolean {
  return manifest.rights.allowedProjectIds === "*" || manifest.rights.allowedProjectIds.includes(projectId);
}

function rightsAllowCrossProjectCopy(manifest: PackageManifest, projectId: string): boolean {
  if (!rightsAllowProject(manifest, projectId)) return false;
  const declarations = new Map(manifest.rights.declarations.map((item) => [item.id, item]));
  return manifest.files.every((file) => declarations.get(file.rightsId)?.redistributionAllowed === true);
}

function isCompatible(manifest: PackageManifest, project: ProjectDefinition): boolean {
  const available = new Set(project.compatibility);
  return manifest.compatibility.requiredCapabilities.every((capability) => available.has(capability));
}

function cloneProject(project: ProjectDefinition): ProjectDefinition {
  return { ...project, compatibility: [...project.compatibility] };
}

export class TemplateLibraryService {
  readonly #projects = new Map<string, ProjectState>();
  readonly #registered = new Map<string, RegisteredRevisionState>();
  readonly #registeredByDigest = new Map<string, string>();
  readonly #items = new Map<string, TemplateItemState>();
  readonly #itemByProjectLineage = new Map<string, string>();
  readonly #projectRevisions = new Map<string, ProjectRevisionState>();
  readonly #uses = new Map<string, TemplateUse>();
  readonly #validatorProfiles: Set<string>;
  readonly #idempotency = new Map<string, IdempotencyRecord>();
  readonly #audit: AuditEvent[] = [];

  constructor(options: TemplateLibraryServiceOptions) {
    this.#validatorProfiles = new Set(
      options.validatorProfiles.map(({ profile, version }) => `${profile}@${version}`),
    );
    for (const project of options.projects ?? []) {
      if (this.#projects.has(project.id)) throw new Error(`Duplicate project id: ${project.id}`);
      this.#projects.set(project.id, { ...cloneProject(project), libraryVersion: 0 });
    }
  }

  registerPackage(input: {
    actor: Actor;
    projectId: string;
    package: ExternalTemplatePackage;
  }): ServiceResult<RegistrationValue> {
    const authorizationIssues = this.#registrationAuthorizationIssues(input.actor, input.projectId);
    if (authorizationIssues.length > 0) return failure("register_package", authorizationIssues);
    const project = this.#projects.get(input.projectId)!;
    const validationIssues = this.#validatePackage(input.package, project);
    if (validationIssues.length > 0) return failure("register_package", validationIssues);

    const packageDigest = computePackageDigest(input.package);
    if (this.#registeredByDigest.has(packageDigest)) {
      return failure("register_package", [
        issue("DUPLICATE_PACKAGE", "This exact immutable package revision is already registered.", "duplicate"),
      ]);
    }

    const registeredRevisionId = stableId("registered", packageDigest);
    const manifest = structuredClone(input.package.manifest);
    const files = new Map(input.package.files.map((file) => [file.path, new Uint8Array(file.bytes)]));
    const registered: RegisteredRevisionState = {
      id: registeredRevisionId,
      packageDigest,
      manifest,
      files,
      withdrawn: false,
    };

    const lineageKey = `${input.projectId}\u0000${manifest.externalLineageKey}`;
    const existingItemId = this.#itemByProjectLineage.get(lineageKey);
    const itemId = existingItemId ?? stableId("template", lineageKey);
    const projectRevisionId = stableId("revision", `${input.projectId}\u0000${packageDigest}`);
    const revision: ProjectRevisionState = {
      id: projectRevisionId,
      templateItemId: itemId,
      projectId: input.projectId,
      registeredRevisionId,
      packageDigest,
      externalRevisionLabel: manifest.externalRevisionLabel,
    };

    const existingItem = existingItemId === undefined ? undefined : this.#items.get(existingItemId);
    const item: TemplateItemState = existingItem === undefined
      ? {
          id: itemId,
          projectId: input.projectId,
          externalLineageKey: manifest.externalLineageKey,
          displayName: manifest.displayName,
          currentRevisionId: projectRevisionId,
          revisionIds: [projectRevisionId],
          active: true,
        }
      : {
          id: existingItem.id,
          projectId: existingItem.projectId,
          externalLineageKey: existingItem.externalLineageKey,
          displayName: manifest.displayName,
          currentRevisionId: projectRevisionId,
          revisionIds: [...existingItem.revisionIds, projectRevisionId],
          active: existingItem.active,
          ...(existingItem.retirementReason === undefined
            ? {}
            : { retirementReason: existingItem.retirementReason }),
        };

    this.#registered.set(registeredRevisionId, registered);
    this.#registeredByDigest.set(packageDigest, registeredRevisionId);
    this.#items.set(itemId, item);
    this.#itemByProjectLineage.set(lineageKey, itemId);
    this.#projectRevisions.set(projectRevisionId, revision);
    project.libraryVersion += 1;
    this.#audit.push({
      kind: "package_registered",
      actorId: input.actor.id,
      projectId: input.projectId,
      subjectId: registeredRevisionId,
      packageDigest,
    });

    return {
      ok: true,
      value: {
        packageDigest,
        registeredRevisionId,
        projectRevision: this.#revisionView(revision),
      },
    };
  }

  listAvailableTemplates(actor: Actor, projectId: string): ServiceResult<ProjectTemplateRevisionView[]> {
    if (!hasProjectCapability(actor, "template:discover", projectId) || !this.#projects.has(projectId)) {
      return failure("list_templates", [
        issue("AUTHORIZATION_DENIED", "Template discovery is not authorized for this project.", "unauthorized"),
      ]);
    }
    const result = [...this.#projectRevisions.values()]
      .filter((revision) => revision.projectId === projectId)
      .filter((revision) => this.#items.get(revision.templateItemId)?.active === true)
      .sort((left, right) =>
        compareText(this.#items.get(left.templateItemId)!.displayName, this.#items.get(right.templateItemId)!.displayName) ||
        compareText(left.externalRevisionLabel, right.externalRevisionLabel) ||
        compareText(left.id, right.id),
      )
      .map((revision) => this.#revisionView(revision));
    return { ok: true, value: result };
  }

  createProjectWithTemplates(input: {
    actor: Actor;
    project: ProjectDefinition;
    selection: TemplateSelection;
    idempotencyKey: string;
  }): ServiceResult<ProjectCreationValue> {
    const requestHash = `sha256:${hashText(canonicalJson({
      actorId: input.actor.id,
      project: cloneProject(input.project),
      selection: input.selection,
    }))}`;
    const prior = this.#idempotency.get(input.idempotencyKey);
    if (prior !== undefined) {
      if (prior.requestHash === requestHash) return structuredClone(prior.result);
      return failure("create_project", [
        issue("IDEMPOTENCY_KEY_REUSED", "The idempotency key was already committed for different project input.", "failed"),
      ]);
    }

    const boundaryIssues = this.#projectCreationBoundaryIssues(input.actor, input.project);
    if (boundaryIssues.length > 0) return failure("create_project", boundaryIssues);
    if (this.#projects.has(input.project.id)) {
      return failure("create_project", [issue("PROJECT_ALREADY_EXISTS", "The destination project already exists.")]);
    }

    const { planned, issues, exclusions } = this.#planSelection(input.actor, input.project, input.selection);
    if (issues.length > 0) return failure("create_project", issues);

    const project: ProjectState = { ...cloneProject(input.project), libraryVersion: 0 };
    const choices: CopyChoiceReport[] = [];
    const newItems: TemplateItemState[] = [];
    const newRevisions: ProjectRevisionState[] = [];
    for (const copy of planned) {
      const lineageKey = `${project.id}\u0000${copy.item.externalLineageKey}`;
      const itemId = stableId("template", lineageKey);
      const destinationRevisionId = stableId("revision", `${project.id}\u0000${copy.registered.packageDigest}`);
      const item: TemplateItemState = {
        id: itemId,
        projectId: project.id,
        externalLineageKey: copy.item.externalLineageKey,
        displayName: copy.item.displayName,
        currentRevisionId: destinationRevisionId,
        revisionIds: [destinationRevisionId],
        active: true,
      };
      const revision: ProjectRevisionState = {
        id: destinationRevisionId,
        templateItemId: itemId,
        projectId: project.id,
        registeredRevisionId: copy.registered.id,
        packageDigest: copy.registered.packageDigest,
        externalRevisionLabel: copy.source.externalRevisionLabel,
        copiedFrom: { projectId: copy.source.projectId, revisionId: copy.source.id },
      };
      newItems.push(item);
      newRevisions.push(revision);
      choices.push({
        sourceRevisionId: copy.source.id,
        status: "copied",
        code: "COPIED",
        message: "Exact immutable revision copied into the destination project.",
        packageDigest: copy.registered.packageDigest,
        destinationRevisionId,
      });
    }

    this.#projects.set(project.id, project);
    for (const item of newItems) {
      this.#items.set(item.id, item);
      this.#itemByProjectLineage.set(`${project.id}\u0000${item.externalLineageKey}`, item.id);
    }
    for (const revision of newRevisions) this.#projectRevisions.set(revision.id, revision);
    project.libraryVersion += newRevisions.length;
    this.#audit.push({ kind: "project_created", actorId: input.actor.id, projectId: project.id, subjectId: project.id });
    for (const choice of choices) {
      this.#audit.push({
        kind: "template_copied",
        actorId: input.actor.id,
        projectId: project.id,
        subjectId: choice.destinationRevisionId!,
        packageDigest: choice.packageDigest!,
      });
    }

    const selectionSnapshotHash = `sha256:${hashText(canonicalJson({
      mode: input.selection.mode,
      destinationProjectId: project.id,
      sources: planned.map((copy) => ({
        projectId: copy.source.projectId,
        projectLibraryVersion: this.#projects.get(copy.source.projectId)!.libraryVersion,
        sourceRevisionId: copy.source.id,
        packageDigest: copy.registered.packageDigest,
      })).sort((left, right) => compareText(left.sourceRevisionId, right.sourceRevisionId)),
    }))}`;
    const value: ProjectCreationValue = {
      projectId: project.id,
      selectionMode: input.selection.mode,
      selectionSnapshotHash,
      choices: choices.sort((left, right) => compareText(left.sourceRevisionId, right.sourceRevisionId)),
      exclusions,
      idempotencyKey: input.idempotencyKey,
    };
    const result = { ok: true as const, value };
    this.#idempotency.set(input.idempotencyKey, { requestHash, result: structuredClone(result) });
    return result;
  }

  createTemplateUse(
    actor: Actor,
    projectId: string,
    projectRevisionId: string,
    resolvedSnapshotHash: string,
  ): ServiceResult<TemplateUse> {
    if (!hasProjectCapability(actor, "template:use", projectId)) {
      return failure("template_use", [issue("AUTHORIZATION_DENIED", "Template use is not authorized.", "unauthorized")]);
    }
    const revision = this.#projectRevisions.get(projectRevisionId);
    const item = revision === undefined ? undefined : this.#items.get(revision.templateItemId);
    if (revision?.projectId !== projectId || item?.active !== true) {
      return failure("template_use", [issue("REVISION_UNAVAILABLE", "The exact project revision is unavailable for new use.", "unavailable")]);
    }
    if (!/^sha256:[A-Za-z0-9._-]+$/.test(resolvedSnapshotHash)) {
      return failure("template_use", [issue("SNAPSHOT_HASH_INVALID", "A resolved snapshot hash is required.")]);
    }
    const id = stableId("use", `${projectId}\u0000${projectRevisionId}\u0000${resolvedSnapshotHash}\u0000${this.#uses.size}`);
    const value: TemplateUse = {
      id,
      projectId,
      projectRevisionId,
      packageDigest: revision.packageDigest,
      resolvedSnapshotHash,
    };
    this.#uses.set(id, value);
    this.#audit.push({ kind: "template_use_created", actorId: actor.id, projectId, subjectId: id, packageDigest: revision.packageDigest });
    return { ok: true, value: structuredClone(value) };
  }

  resolveTemplateUse(actor: Actor, projectId: string, useId: string): ServiceResult<TemplateUse> {
    if (!hasProjectCapability(actor, "template:use", projectId)) {
      return failure("template_use", [issue("AUTHORIZATION_DENIED", "Template use resolution is not authorized.", "unauthorized")]);
    }
    const value = this.#uses.get(useId);
    if (value?.projectId !== projectId) {
      return failure("template_use", [issue("USE_UNAVAILABLE", "The template use is unavailable.", "unavailable")]);
    }
    return { ok: true, value: structuredClone(value) };
  }

  retireTemplateItem(actor: Actor, templateItemId: string, reason: string): ServiceResult<{ templateItemId: string }> {
    const item = this.#items.get(templateItemId);
    if (item === undefined || !hasProjectCapability(actor, "template:manage", item.projectId)) {
      return failure("template_lifecycle", [issue("AUTHORIZATION_DENIED", "Template retirement is not authorized.", "unauthorized")]);
    }
    item.active = false;
    item.retirementReason = reason;
    this.#projects.get(item.projectId)!.libraryVersion += 1;
    this.#audit.push({ kind: "template_retired", actorId: actor.id, projectId: item.projectId, subjectId: item.id, reason });
    return { ok: true, value: { templateItemId } };
  }

  withdrawRegisteredRevision(actor: Actor, registeredRevisionId: string, reason: string): ServiceResult<{ registeredRevisionId: string }> {
    if (!hasCapability(actor, "template:register", "registry")) {
      return failure("template_lifecycle", [issue("AUTHORIZATION_DENIED", "Revision withdrawal is not authorized.", "unauthorized")]);
    }
    const registered = this.#registered.get(registeredRevisionId);
    if (registered === undefined) {
      return failure("template_lifecycle", [issue("REVISION_UNAVAILABLE", "The registered revision does not exist.", "unavailable")]);
    }
    registered.withdrawn = true;
    registered.withdrawalReason = reason;
    this.#audit.push({ kind: "revision_withdrawn", actorId: actor.id, subjectId: registered.id, packageDigest: registered.packageDigest, reason });
    return { ok: true, value: { registeredRevisionId } };
  }

  hasProject(projectId: string): boolean {
    return this.#projects.has(projectId);
  }

  inspectCounts(): {
    projects: number;
    registeredRevisions: number;
    templateItems: number;
    projectRevisions: number;
    uses: number;
  } {
    return {
      projects: this.#projects.size,
      registeredRevisions: this.#registered.size,
      templateItems: this.#items.size,
      projectRevisions: this.#projectRevisions.size,
      uses: this.#uses.size,
    };
  }

  listAuditEvents(): readonly AuditEvent[] {
    return structuredClone(this.#audit);
  }

  #registrationAuthorizationIssues(actor: Actor, projectId: string): OperationIssue[] {
    const authorized =
      hasCapability(actor, "template:intake", "registry") &&
      hasCapability(actor, "template:register", "registry") &&
      hasProjectCapability(actor, "template:manage", projectId) &&
      this.#projects.has(projectId);
    return authorized
      ? []
      : [issue("AUTHORIZATION_DENIED", "Package registration is not authorized for this project.", "unauthorized")];
  }

  #validatePackage(packageValue: ExternalTemplatePackage, project: ProjectState): OperationIssue[] {
    const issues: OperationIssue[] = [];
    const manifest = packageValue.manifest;
    const maximumFiles = 1_000;
    const maximumExpandedBytes = 512 * 1024 * 1024;
    if (packageValue.transport !== "directory" && packageValue.transport !== "zip") {
      issues.push(issue("TRANSPORT_UNSUPPORTED", "Only a directory or non-self-extracting ZIP package is accepted."));
    }
    if (manifest.schemaVersion !== "external-template-package/v1") {
      issues.push(issue("MANIFEST_SCHEMA_UNSUPPORTED", "The external template manifest schema is unsupported."));
    }
    for (const [field, value] of Object.entries({
      externalLineageKey: manifest.externalLineageKey,
      displayName: manifest.displayName,
      externalRevisionLabel: manifest.externalRevisionLabel,
      entryPoint: manifest.entryPoint,
      author: manifest.provenance.author,
      publisher: manifest.provenance.publisher,
      organization: manifest.provenance.organization,
      sourceTool: manifest.provenance.sourceTool,
      sourceToolVersion: manifest.provenance.sourceToolVersion,
      sourceRevision: manifest.provenance.sourceRevision,
      createdAt: manifest.provenance.createdAt,
      attestedBy: manifest.provenance.attestedBy,
    })) {
      if (!nonempty(value)) issues.push(issue("MANIFEST_FIELD_REQUIRED", `Manifest field ${field} is required.`));
    }
    if (!this.#validatorProfiles.has(`${manifest.validator.profile}@${manifest.validator.version}`)) {
      issues.push(issue("VALIDATOR_PROFILE_UNSUPPORTED", "The exact validator profile and version are not approved."));
    }
    if (!isCompatible(manifest, project)) {
      issues.push(issue("TARGET_INCOMPATIBLE", "The package requirements do not match the destination project.", "incompatible"));
    }
    if (!rightsAllowProject(manifest, project.id)) {
      issues.push(issue("RIGHTS_SCOPE_DENIED", "The recorded rights do not allow this destination project.", "unauthorized"));
    }
    if (manifest.files.length === 0 || manifest.files.length > maximumFiles || packageValue.files.length > maximumFiles) {
      issues.push(issue("PACKAGE_FILE_COUNT_INVALID", `A package must contain between 1 and ${maximumFiles} declared files.`));
    }
    const expandedBytes = packageValue.files.reduce((total, file) => total + file.bytes.byteLength, 0);
    if (!Number.isSafeInteger(expandedBytes) || expandedBytes > maximumExpandedBytes) {
      issues.push(issue("PACKAGE_EXPANDED_SIZE_EXCEEDED", "The decoded package exceeds the 512 MiB intake limit."));
    }

    const declaredPaths = new Set<string>();
    const declaredCasefold = new Set<string>();
    const providedByPath = new Map<string, Uint8Array>();
    for (const file of packageValue.files) {
      if (providedByPath.has(file.path)) {
        issues.push(issue("PACKAGE_FILE_DUPLICATE", "A provided package path occurs more than once.", "duplicate", { path: file.path }));
      } else {
        providedByPath.set(file.path, file.bytes);
      }
    }
    const rightsById = new Map(manifest.rights.declarations.map((declaration) => [declaration.id, declaration]));
    if (rightsById.size !== manifest.rights.declarations.length) {
      issues.push(issue("RIGHTS_DECLARATION_DUPLICATE", "Rights declaration identifiers must be unique.", "duplicate"));
    }
    for (const declaration of manifest.rights.declarations) {
      if (!nonempty(declaration.id) || !nonempty(declaration.holder) || !nonempty(declaration.basis)) {
        issues.push(issue("RIGHTS_DECLARATION_INCOMPLETE", "Every rights declaration needs an id, holder, and basis."));
      }
    }
    for (const declaration of manifest.files) {
      if (!isSafePackagePath(declaration.path) || declaration.path.length > 512) {
        issues.push(issue("PACKAGE_PATH_UNSAFE", "Package paths must be normalized, relative POSIX paths without traversal.", "failed", { path: declaration.path }));
      }
      const folded = declaration.path.toLocaleLowerCase("en-US");
      if (declaredPaths.has(declaration.path) || declaredCasefold.has(folded)) {
        issues.push(issue("MANIFEST_PATH_DUPLICATE", "Manifest paths must be unique, including case-insensitive collisions.", "duplicate", { path: declaration.path }));
      }
      declaredPaths.add(declaration.path);
      declaredCasefold.add(folded);
      const bytes = providedByPath.get(declaration.path);
      if (bytes === undefined) {
        issues.push(issue("DECLARED_FILE_MISSING", "A declared package file is missing.", "unavailable", { path: declaration.path }));
      } else {
        if (!Number.isSafeInteger(declaration.byteLength) || declaration.byteLength < 0 || bytes.byteLength !== declaration.byteLength) {
          issues.push(issue("FILE_SIZE_MISMATCH", "The declared byte length does not match the package bytes.", "failed", { path: declaration.path }));
        }
        if (!/^sha256:[a-f0-9]{64}$/.test(declaration.sha256) || sha256Bytes(bytes) !== declaration.sha256) {
          issues.push(issue("FILE_HASH_MISMATCH", "The declared SHA-256 does not match the package bytes.", "failed", { path: declaration.path }));
        }
      }
      const rights = rightsById.get(declaration.rightsId);
      if (rights === undefined) {
        issues.push(issue("RIGHTS_DECLARATION_MISSING", "Every package file must reference a complete rights declaration.", "failed", { path: declaration.path }));
      } else if (declaration.mediaType.startsWith("font/") && !rights.embeddingAllowed) {
        issues.push(issue("FONT_EMBEDDING_DENIED", "Bundled font bytes require explicit embedding authority.", "failed", { path: declaration.path }));
      }
    }
    for (const providedPath of providedByPath.keys()) {
      if (!declaredPaths.has(providedPath)) {
        issues.push(issue("UNDECLARED_FILE", "The package contains a file not declared by the manifest.", "failed", { path: providedPath }));
      }
    }
    if (!declaredPaths.has(manifest.entryPoint)) {
      issues.push(issue("ENTRY_POINT_MISSING", "The declared entry point is not in the package file set.", "unavailable", { path: manifest.entryPoint }));
    }
    return issues;
  }

  #projectCreationBoundaryIssues(actor: Actor, project: ProjectDefinition): OperationIssue[] {
    if (
      !hasCapability(actor, "project:create", project.suiteId) ||
      !hasProjectCapability(actor, "template:manage", project.id)
    ) {
      return [issue("AUTHORIZATION_DENIED", "Project creation and destination template management are not authorized.", "unauthorized")];
    }
    if (!nonempty(project.id) || !nonempty(project.name) || !nonempty(project.suiteId)) {
      return [issue("PROJECT_INVALID", "Destination project id, name, and suite are required.")];
    }
    return [];
  }

  #planSelection(
    actor: Actor,
    project: ProjectDefinition,
    selection: TemplateSelection,
  ): { planned: PlannedCopy[]; issues: OperationIssue[]; exclusions: CopyChoiceReport[] } {
    if (selection.mode === "none") return { planned: [], issues: [], exclusions: [] };
    if (selection.mode === "some") return this.#planSome(actor, project, selection.revisionIds);
    return this.#planAll(actor, project, selection.sourceProjectIds);
  }

  #planSome(
    actor: Actor,
    project: ProjectDefinition,
    revisionIds: string[],
  ): { planned: PlannedCopy[]; issues: OperationIssue[]; exclusions: CopyChoiceReport[] } {
    const issues: OperationIssue[] = [];
    const planned: PlannedCopy[] = [];
    const seen = new Set<string>();
    for (const revisionId of revisionIds) {
      if (seen.has(revisionId)) {
        issues.push(issue("DUPLICATE_CHOICE", "The exact source revision was selected more than once.", "duplicate", { sourceRevisionId: revisionId }));
        continue;
      }
      seen.add(revisionId);
      const result = this.#eligibleExactCopy(actor, project, revisionId);
      if (result instanceof Array) issues.push(...result);
      else planned.push(result);
    }
    issues.push(...this.#selectionConflictIssues(planned));
    return { planned, issues, exclusions: [] };
  }

  #planAll(
    actor: Actor,
    project: ProjectDefinition,
    sourceProjectIds: string[],
  ): { planned: PlannedCopy[]; issues: OperationIssue[]; exclusions: CopyChoiceReport[] } {
    const issues: OperationIssue[] = [];
    const planned: PlannedCopy[] = [];
    const exclusions: CopyChoiceReport[] = [];
    const uniqueSources = [...new Set(sourceProjectIds)].sort(compareText);
    if (uniqueSources.length !== sourceProjectIds.length) {
      issues.push(issue("DUPLICATE_SOURCE_PROJECT", "An All selection named the same source project more than once.", "duplicate"));
    }
    for (const sourceProjectId of uniqueSources) {
      if (
        !this.#projects.has(sourceProjectId) ||
        !hasProjectCapability(actor, "template:discover", sourceProjectId) ||
        !hasProjectCapability(actor, "template:copy-out", sourceProjectId)
      ) {
        issues.push(issue("SOURCE_UNAVAILABLE_OR_UNAUTHORIZED", "A requested source project is unavailable or unauthorized.", "unauthorized"));
        continue;
      }
      const items = [...this.#items.values()]
        .filter((item) => item.projectId === sourceProjectId)
        .sort((left, right) => compareText(left.id, right.id));
      for (const item of items) {
        if (!item.active) {
          for (const revisionId of item.revisionIds) exclusions.push(this.#exclusion(revisionId, "ITEM_RETIRED", "unavailable", "Template item is retired."));
          continue;
        }
        for (const revisionId of item.revisionIds) {
          if (revisionId === item.currentRevisionId) continue;
          const revision = this.#projectRevisions.get(revisionId)!;
          const registered = this.#registered.get(revision.registeredRevisionId)!;
          if (registered.withdrawn) {
            exclusions.push(this.#exclusion(revisionId, "REVISION_WITHDRAWN", "unavailable", "Revision is withdrawn from new copies."));
          }
        }
        const current = this.#eligibleExactCopy(actor, project, item.currentRevisionId);
        if (current instanceof Array) {
          for (const itemIssue of current) {
            exclusions.push(this.#exclusion(
              item.currentRevisionId,
              itemIssue.code,
              itemIssue.status,
              itemIssue.message,
            ));
          }
        } else {
          planned.push(current);
        }
      }
    }
    issues.push(...this.#selectionConflictIssues(planned));
    return {
      planned,
      issues,
      exclusions: exclusions.sort((left, right) => compareText(left.sourceRevisionId, right.sourceRevisionId)),
    };
  }

  #eligibleExactCopy(actor: Actor, project: ProjectDefinition, revisionId: string): PlannedCopy | OperationIssue[] {
    const source = this.#projectRevisions.get(revisionId);
    const item = source === undefined ? undefined : this.#items.get(source.templateItemId);
    if (
      source === undefined ||
      item === undefined ||
      !hasProjectCapability(actor, "template:copy-out", source.projectId)
    ) {
      return [issue(
        "CHOICE_UNAVAILABLE_OR_UNAUTHORIZED",
        "The requested exact revision is unavailable or unauthorized.",
        "unauthorized",
        { sourceRevisionId: revisionId },
      )];
    }
    if (!item.active) {
      return [issue("ITEM_RETIRED", "The source template is retired from new copies.", "unavailable", { sourceRevisionId: revisionId })];
    }
    const registered = this.#registered.get(source.registeredRevisionId);
    if (registered === undefined || registered.files.size === 0) {
      return [issue("REVISION_BYTES_UNAVAILABLE", "The exact registered bytes are unavailable.", "unavailable", { sourceRevisionId: revisionId })];
    }
    if (registered.withdrawn) {
      return [issue("REVISION_WITHDRAWN", "The exact revision is withdrawn from new copies.", "unavailable", { sourceRevisionId: revisionId })];
    }
    if (!rightsAllowCrossProjectCopy(registered.manifest, project.id)) {
      return [issue("DESTINATION_RIGHTS_DENIED", "The exact revision is not licensed for the destination.", "unauthorized", { sourceRevisionId: revisionId })];
    }
    if (!isCompatible(registered.manifest, project)) {
      return [issue("TARGET_INCOMPATIBLE", "The exact revision is incompatible with the destination.", "incompatible", { sourceRevisionId: revisionId })];
    }
    return { source, item, registered };
  }

  #selectionConflictIssues(planned: PlannedCopy[]): OperationIssue[] {
    const issues: OperationIssue[] = [];
    const byLineage = new Map<string, PlannedCopy>();
    const byName = new Map<string, PlannedCopy>();
    for (const copy of planned) {
      const lineage = copy.item.externalLineageKey;
      const name = copy.item.displayName.toLocaleLowerCase("en-US");
      const lineagePrior = byLineage.get(lineage);
      if (lineagePrior !== undefined && lineagePrior.registered.packageDigest !== copy.registered.packageDigest) {
        issues.push(issue("DIFFERENT_REVISION_CONFLICT", "Two different revisions of one lineage cannot be copied implicitly.", "duplicate", { sourceRevisionId: copy.source.id }));
      } else {
        byLineage.set(lineage, copy);
      }
      const namePrior = byName.get(name);
      if (namePrior !== undefined && namePrior.item.externalLineageKey !== lineage) {
        issues.push(issue("NAME_CONFLICT", "Different template lineages use the same destination display name.", "duplicate", { sourceRevisionId: copy.source.id }));
      } else {
        byName.set(name, copy);
      }
    }
    return issues;
  }

  #exclusion(
    sourceRevisionId: string,
    code: string,
    status: OperationIssue["status"],
    message: string,
  ): CopyChoiceReport {
    return { sourceRevisionId, code, status, message };
  }

  #revisionView(revision: ProjectRevisionState): ProjectTemplateRevisionView {
    const item = this.#items.get(revision.templateItemId)!;
    return {
      id: revision.id,
      templateItemId: revision.templateItemId,
      projectId: revision.projectId,
      displayName: item.displayName,
      externalLineageKey: item.externalLineageKey,
      externalRevisionLabel: revision.externalRevisionLabel,
      packageDigest: revision.packageDigest,
      isCurrent: item.currentRevisionId === revision.id,
      ...(revision.copiedFrom === undefined ? {} : { copiedFrom: structuredClone(revision.copiedFrom) }),
    };
  }
}
