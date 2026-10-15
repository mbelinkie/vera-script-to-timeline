import { canonicalJson, sha256CanonicalJson } from "./compiler-core.js";
import { Ajv2020 } from "ajv/dist/2020.js";
import * as formatsModule from "ajv-formats";
import compilerDependenciesSchema from "../../../contracts/compiler-dependencies-v2.schema.json" with { type: "json" };
import scriptDocumentSchema from "../../../contracts/script-document-v2.schema.json" with { type: "json" };
import type {
  GraphicProvenanceDerivation,
  GraphicProvenanceSemanticSnapshot,
  GraphicProvenanceSnapshot,
  GraphicProvenanceSource,
  GraphicTemplatePin,
  ResolvedGraphicContent,
} from "./generated/contracts-v2.js";
import {
  computePackageDigest,
  sha256Bytes,
  type ExternalTemplatePackage,
} from "./template-library.js";

export type {
  GraphicProvenanceDerivation,
  GraphicProvenanceSemanticSnapshot,
  GraphicProvenanceSnapshot,
  GraphicProvenanceSource,
  GraphicTemplatePin,
  ResolvedGraphicContent,
} from "./generated/contracts-v2.js";

export type GraphicHash = GraphicTemplatePin["packageDigest"];
export type GraphicProvenanceBinding = ResolvedGraphicContent["provenance"];

export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };

export type ProvenanceBlockCode =
  | "GRAPHIC_PROVENANCE_INCOMPLETE"
  | "GRAPHIC_PROVENANCE_MISMATCH"
  | "GRAPHIC_PROVENANCE_UNAVAILABLE"
  | "GRAPHIC_PROVENANCE_UNAUTHORIZED"
  | "GRAPHIC_PROVENANCE_UNEXPECTED";

export interface ProvenanceBlock {
  code: ProvenanceBlockCode;
  message: string;
}

export type ProvenanceResult<T> = { ok: true; value: T } | { ok: false; block: ProvenanceBlock };

/**
 * These records are already authorized by the caller. This module only checks
 * that their immutable identities and bytes agree with the requested content.
 */
export type RetainedGraphicRevisionRecord =
  | { format: "legacy"; projectId: string; graphicId: string; revisionId: string; contentHash: GraphicHash; bytes: Uint8Array }
  | { format: "graphic-content/v1"; content: ResolvedGraphicContent; contentHash: GraphicHash };

export interface RetainedArtifactBytes {
  projectId: string;
  artifactId: string;
  contentHash: GraphicHash;
  mediaType: string;
  bytes: Uint8Array;
}

export interface RetainedBadgeBytes {
  projectId: string;
  assetId: string;
  contentHash: GraphicHash;
  bytes: Uint8Array;
}

export interface RetainedMethodBytes {
  projectId: string;
  methodId: string;
  version: string;
  artifactId: string;
  contentHash: GraphicHash;
  bytes: Uint8Array;
}

export interface RetainedTemplatePackage {
  projectId: string;
  templateKey: string;
  projectRevisionId: string;
  compatible: boolean;
  package: ExternalTemplatePackage;
}

export interface GraphicProvenanceRetainedRecords {
  revisions: readonly RetainedGraphicRevisionRecord[];
  snapshots: readonly GraphicProvenanceSnapshot[];
  sources: readonly RetainedArtifactBytes[];
  badges: readonly RetainedBadgeBytes[];
  methods: readonly RetainedMethodBytes[];
  templates: readonly RetainedTemplatePackage[];
}

export interface GraphicRevisionAddress {
  projectId: string;
  graphicId: string;
  revisionId: string;
}

export interface GraphicAuditReceipt {
  schemaVersion: "graphic-provenance-audit/v1";
  operation: "create" | "repeat" | "refresh" | "template_migration";
  projectId: string;
  graphicId: string;
  priorRevisionId: string | null;
  priorContentHash: GraphicHash | null;
  priorProvenanceHash: GraphicHash | null;
  newRevisionId: string;
  newContentHash: GraphicHash;
  newProvenanceHash: GraphicHash | null;
  actorId: string;
  recordedAt: string;
}

export interface ProposedGraphicRevision {
  content: Readonly<ResolvedGraphicContent>;
  contentHash: GraphicHash;
  snapshot: Readonly<GraphicProvenanceSnapshot> | null;
  provenanceHash: GraphicHash | null;
  methodAvailable: boolean | null;
  receipt: Readonly<GraphicAuditReceipt>;
}

export type ResolvedGraphicRevision =
  | {
      contentClass: "legacy_unclassified";
      content: null;
      contentHash: null;
      snapshot: null;
      provenanceHash: null;
      methodAvailable: null;
    }
  | {
      contentClass: "manual" | "derived";
      content: Readonly<ResolvedGraphicContent>;
      contentHash: GraphicHash;
      snapshot: Readonly<GraphicProvenanceSnapshot> | null;
      provenanceHash: GraphicHash | null;
      methodAvailable: boolean | null;
    };

interface AuditInputs {
  actorId: string;
  recordedAt: string;
}

export interface CreateGraphicContentInput extends AuditInputs {
  projectId: string;
  graphicId: string;
  revisionId: string;
  template: GraphicTemplatePin;
  semanticSnapshot: GraphicProvenanceSemanticSnapshot;
  content:
    | { kind: "manual" }
    | { kind: "derived"; sources: readonly GraphicProvenanceSource[]; derivation: GraphicProvenanceDerivation };
}

export interface RepeatGraphicContentInput extends AuditInputs, GraphicRevisionAddress {}

export interface RefreshGraphicContentInput extends AuditInputs, GraphicRevisionAddress {
  newRevisionId: string;
  semanticSnapshot: GraphicProvenanceSemanticSnapshot;
  sources: readonly GraphicProvenanceSource[];
  derivation: GraphicProvenanceDerivation;
}

export interface MigrateGraphicTemplateInput extends AuditInputs, GraphicRevisionAddress {
  newRevisionId: string;
  template: GraphicTemplatePin;
  semanticSnapshot: GraphicProvenanceSemanticSnapshot;
}

const HASH_PATTERN = /^sha256:[a-f0-9]{64}$/;
const EMPTY_RECORDS: GraphicProvenanceRetainedRecords = {
  revisions: [], snapshots: [], sources: [], badges: [], methods: [], templates: [],
};

const wireAjv = new Ajv2020({ allErrors: false, strict: true });
formatsModule.default.default(wireAjv);
wireAjv.addSchema(scriptDocumentSchema);
wireAjv.addSchema(compilerDependenciesSchema);
const compileGraphicDef = <T>(name: string) => wireAjv.compile<T>({
  $ref: `${compilerDependenciesSchema.$id}#/$defs/${name}`,
});
const wireValidators = {
  entityId: wireAjv.compile<string>({ $ref: `${scriptDocumentSchema.$id}#/$defs/EntityId` }),
  template: compileGraphicDef<GraphicTemplatePin>("GraphicTemplatePin"),
  semantic: compileGraphicDef<GraphicProvenanceSemanticSnapshot>("GraphicProvenanceSemanticSnapshot"),
  source: compileGraphicDef<GraphicProvenanceSource>("GraphicProvenanceSource"),
  derivation: compileGraphicDef<GraphicProvenanceDerivation>("GraphicProvenanceDerivation"),
  snapshot: compileGraphicDef<GraphicProvenanceSnapshot>("GraphicProvenanceSnapshot"),
  content: compileGraphicDef<ResolvedGraphicContent>("ResolvedGraphicContent"),
};

class ProvenanceFault extends Error {
  readonly code: ProvenanceBlockCode;

  constructor(code: ProvenanceBlockCode, message: string) {
    super(message);
    this.code = code;
  }
}

function fail(code: ProvenanceBlockCode, message: string): never {
  throw new ProvenanceFault(code, message);
}

function result<T>(run: () => T): ProvenanceResult<T> {
  try {
    return { ok: true, value: run() };
  } catch (error) {
    if (error instanceof ProvenanceFault) return { ok: false, block: { code: error.code, message: error.message } };
    return { ok: false, block: { code: "GRAPHIC_PROVENANCE_INCOMPLETE", message: error instanceof Error ? error.message : "Invalid provenance input." } };
  }
}

function require(condition: unknown, message: string, code: ProvenanceBlockCode = "GRAPHIC_PROVENANCE_INCOMPLETE"): asserts condition {
  if (!condition) fail(code, message);
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype: unknown = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function assertJsonValue(value: unknown, label: string, seen = new Set<object>()): asserts value is JsonValue {
  if (value === null || typeof value === "string" || typeof value === "boolean") return;
  if (typeof value === "number") {
    require(Number.isFinite(value), `${label} must contain only finite JSON numbers.`);
    return;
  }
  if (Array.isArray(value)) {
    require(!seen.has(value), `${label} must not contain a cycle.`);
    seen.add(value);
    require(Reflect.ownKeys(value).every((key) => key === "length" ||
      typeof key === "string" && /^(0|[1-9]\d*)$/.test(key) && Number(key) < value.length),
    `${label} arrays must not have custom properties.`);
    for (let index = 0; index < value.length; index += 1) {
      const descriptor = Object.getOwnPropertyDescriptor(value, String(index));
      require(descriptor !== undefined && "value" in descriptor && descriptor.enumerable,
        `${label} arrays must contain only dense JSON elements.`);
      assertJsonValue(descriptor.value, label, seen);
    }
    seen.delete(value);
    return;
  }
  require(isPlainRecord(value), `${label} must contain only plain JSON objects.`);
  require(!seen.has(value), `${label} must not contain a cycle.`);
  seen.add(value);
  for (const key of Reflect.ownKeys(value)) {
    require(typeof key === "string", `${label} must not contain symbol keys.`);
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    require(descriptor !== undefined && "value" in descriptor && descriptor.enumerable,
      `${label} must contain only enumerable JSON data properties.`);
    assertJsonValue(descriptor.value, `${label}.${key}`, seen);
  }
  seen.delete(value);
}

function assertExactKeys(value: unknown, keys: readonly string[], label: string): asserts value is Record<string, unknown> {
  require(isPlainRecord(value), `${label} must be a JSON object.`);
  const actual = Reflect.ownKeys(value);
  require(actual.every((key) => typeof key === "string"), `${label} must not contain symbol keys.`);
  const expected = new Set(keys);
  require(actual.length === keys.length && actual.every((key) => expected.has(String(key))), `${label} has missing or unknown fields.`);
}

function cloneJson<T>(value: T, label: string): T {
  assertJsonValue(value, label);
  return structuredClone(value);
}

function deepFreeze<T>(value: T): T {
  if (value !== null && typeof value === "object" && !Object.isFrozen(value)) {
    for (const child of Object.values(value as Record<string, unknown>)) deepFreeze(child);
    Object.freeze(value);
  }
  return value;
}

function frozenClone<T>(value: T, label: string): Readonly<T> {
  return deepFreeze(cloneJson(value, label));
}

function requireText(value: unknown, label: string): asserts value is string {
  require(typeof value === "string" && value.trim().length > 0, `${label} must be a nonempty string.`);
}

function requireHash(value: unknown, label: string): asserts value is GraphicHash {
  require(typeof value === "string" && HASH_PATTERN.test(value), `${label} must be a lowercase SHA-256 hash.`);
}

type SchemaValidator = ((value: unknown) => boolean) & {
  errors?: readonly { keyword: string }[] | null;
};

function validateWireShape<T>(value: unknown, validator: SchemaValidator, label: string): T {
  assertJsonValue(value, label);
  if (!validator(value)) {
    const keyword = validator.errors?.[0]?.keyword;
    const code = keyword === "additionalProperties"
      ? "GRAPHIC_PROVENANCE_UNEXPECTED"
      : keyword === "required" || keyword === "minItems" || keyword === "minLength"
        ? "GRAPHIC_PROVENANCE_INCOMPLETE"
        : "GRAPHIC_PROVENANCE_MISMATCH";
    fail(code, `${label} does not match its approved provenance contract (${keyword ?? "invalid shape"}).`);
  }
  return structuredClone(value) as T;
}

function validateTemplatePin(value: unknown): GraphicTemplatePin {
  return validateWireShape(value, wireValidators.template, "template pin");
}

function validateSemanticSnapshot(value: unknown): GraphicProvenanceSemanticSnapshot {
  const semantic = validateWireShape<GraphicProvenanceSemanticSnapshot>(value, wireValidators.semantic, "semanticSnapshot");
  require(semantic.values.badgeOverrideAssetId === (semantic.badgeAsset?.assetId ?? null),
    "The semantic badge override must match the retained badge asset identity.", "GRAPHIC_PROVENANCE_MISMATCH");
  return semantic;
}

function semanticHash(semanticSnapshot: GraphicProvenanceSemanticSnapshot): GraphicHash {
  // Keep #7's established material exactly: {values, badgeAsset}.
  return sha256CanonicalJson({ values: semanticSnapshot.values, badgeAsset: semanticSnapshot.badgeAsset });
}

function validateSource(value: unknown): GraphicProvenanceSource {
  return validateWireShape(value, wireValidators.source, "source");
}

function validateDerivation(value: unknown): GraphicProvenanceDerivation {
  return validateWireShape(value, wireValidators.derivation, "derivation");
}

function validateSnapshot(value: unknown): GraphicProvenanceSnapshot {
  const snapshot = validateWireShape<GraphicProvenanceSnapshot>(value, wireValidators.snapshot, "provenance snapshot");
  const semantic = validateSemanticSnapshot(snapshot.semanticSnapshot);
  require(semanticHash(semantic) === snapshot.semanticSnapshotHash, "Provenance semanticSnapshotHash does not match the #7 semantic values.", "GRAPHIC_PROVENANCE_MISMATCH");
  const sources = snapshot.sources;
  const keys = sources.map((source) => source.sourceKey);
  require(new Set(keys).size === keys.length, "Provenance sourceKey values must be unique.");
  require(keys.every((key, index) => index === 0 || keys[index - 1]! < key), "Provenance sources must be sorted by sourceKey.");
  return cloneJson({ ...snapshot, semanticSnapshot: semantic }, "provenance snapshot");
}

function validateContent(value: unknown): ResolvedGraphicContent {
  const content = validateWireShape<ResolvedGraphicContent>(value, wireValidators.content, "resolved graphic content");
  const semantic = validateSemanticSnapshot(content.semanticSnapshot);
  require(semanticHash(semantic) === content.semanticSnapshotHash, "Graphic content semanticSnapshotHash does not match the #7 semantic values.", "GRAPHIC_PROVENANCE_MISMATCH");
  return cloneJson({ ...content, semanticSnapshot: semantic }, "resolved graphic content");
}

function validateRecords(records: GraphicProvenanceRetainedRecords): GraphicProvenanceRetainedRecords {
  require(records !== null && typeof records === "object", "Retained records are required.");
  for (const field of ["revisions", "snapshots", "sources", "badges", "methods", "templates"] as const) {
    require(Array.isArray(records[field]), `Retained ${field} records must be an array.`);
  }
  return records;
}

function sameJson(left: unknown, right: unknown): boolean {
  return canonicalJson(left) === canonicalJson(right);
}

function validateTemplatePackage(pin: GraphicTemplatePin, projectId: string, records: GraphicProvenanceRetainedRecords): void {
  const all = records.templates.filter((record) => record?.projectRevisionId === pin.projectRevisionId && record?.templateKey === pin.templateKey);
  const exact = all.filter((record) => record?.projectId === projectId);
  if (exact.length === 0) {
    if (all.length > 0) fail("GRAPHIC_PROVENANCE_UNAUTHORIZED", "Pinned template revision belongs to another project.");
    fail("GRAPHIC_PROVENANCE_UNAVAILABLE", "Pinned template package is not retained.");
  }
  require(exact.length === 1, "Pinned template resolver returned duplicate retained revisions.", "GRAPHIC_PROVENANCE_UNEXPECTED");
  const retained = exact[0]!;
  require(typeof retained.compatible === "boolean", "Trusted template resolver omitted compatibility status.");
  require(retained.compatible, "Pinned template revision is not compatible with this project.", "GRAPHIC_PROVENANCE_MISMATCH");
  require(retained.package?.manifest?.packageKind === "graphic" && retained.package.manifest.externalLineageKey === pin.templateKey,
    "Pinned package identity does not match the graphic template.", "GRAPHIC_PROVENANCE_MISMATCH");
  require(computePackageDigest(retained.package) === pin.packageDigest,
    "Pinned template package digest does not match the retained #20 package identity.", "GRAPHIC_PROVENANCE_MISMATCH");
  const declarations = retained.package.manifest.files;
  const supplied = retained.package.files;
  require(Array.isArray(declarations) && Array.isArray(supplied), "Pinned template package file inventory is malformed.");
  const declarationsByPath = new Map<string, (typeof declarations)[number]>();
  for (const declaration of declarations) {
    require(typeof declaration.path === "string" && !declarationsByPath.has(declaration.path), "Pinned package declares a duplicate file path.", "GRAPHIC_PROVENANCE_MISMATCH");
    declarationsByPath.set(declaration.path, declaration);
  }
  const bytesByPath = new Map<string, Uint8Array>();
  for (const file of supplied) {
    require(typeof file.path === "string" && file.bytes instanceof Uint8Array && !bytesByPath.has(file.path), "Pinned package has a duplicate or malformed retained file.", "GRAPHIC_PROVENANCE_MISMATCH");
    bytesByPath.set(file.path, file.bytes);
  }
  require(declarationsByPath.size === bytesByPath.size, "Pinned package retained file set differs from its declarations.", "GRAPHIC_PROVENANCE_MISMATCH");
  for (const [path, declaration] of declarationsByPath) {
    const bytes = bytesByPath.get(path);
    require(bytes !== undefined, `Pinned package file ${path} is unavailable.`, "GRAPHIC_PROVENANCE_UNAVAILABLE");
    require(Number.isSafeInteger(declaration.byteLength) && declaration.byteLength >= 0 && bytes.byteLength === declaration.byteLength,
      `Pinned package file ${path} has the wrong byte length.`, "GRAPHIC_PROVENANCE_MISMATCH");
    requireHash(declaration.sha256, `Pinned package file ${path} hash`);
    require(sha256Bytes(bytes) === declaration.sha256, `Pinned package file ${path} has the wrong byte hash.`, "GRAPHIC_PROVENANCE_MISMATCH");
  }
  const entry = bytesByPath.get(retained.package.manifest.entryPoint);
  require(entry !== undefined, "Pinned template entry asset is not retained.", "GRAPHIC_PROVENANCE_UNAVAILABLE");
  require(sha256Bytes(entry) === pin.entryAssetHash, "Pinned template entry asset hash does not match its retained bytes.", "GRAPHIC_PROVENANCE_MISMATCH");
}

function verifyArtifact(source: GraphicProvenanceSource, projectId: string, records: GraphicProvenanceRetainedRecords): void {
  const all = records.sources.filter((record) => record?.artifactId === source.snapshot.artifactId);
  const exact = all.filter((record) => record?.projectId === projectId);
  if (exact.length === 0) {
    if (all.length > 0) fail("GRAPHIC_PROVENANCE_UNAUTHORIZED", `Source artifact ${source.snapshot.artifactId} is outside the project scope.`);
    fail("GRAPHIC_PROVENANCE_UNAVAILABLE", `Retained source artifact ${source.snapshot.artifactId} is unavailable.`);
  }
  require(exact.length === 1, `Source artifact ${source.snapshot.artifactId} has ambiguous retained records.`, "GRAPHIC_PROVENANCE_UNEXPECTED");
  const retained = exact[0]!;
  require(retained.mediaType === source.snapshot.mediaType, `Source artifact ${source.snapshot.artifactId} media type differs from the snapshot.`, "GRAPHIC_PROVENANCE_MISMATCH");
  require(retained.contentHash === source.snapshot.contentHash && sha256Bytes(retained.bytes) === source.snapshot.contentHash,
    `Source artifact ${source.snapshot.artifactId} byte identity does not match the provenance snapshot.`, "GRAPHIC_PROVENANCE_MISMATCH");
}

function verifyBadge(semantic: GraphicProvenanceSemanticSnapshot, projectId: string, records: GraphicProvenanceRetainedRecords): void {
  if (semantic.badgeAsset === null) return;
  const all = records.badges.filter((record) => record?.assetId === semantic.badgeAsset!.assetId);
  const exact = all.filter((record) => record?.projectId === projectId);
  if (exact.length === 0) {
    if (all.length > 0) fail("GRAPHIC_PROVENANCE_UNAUTHORIZED", "The badge asset belongs to another project.");
    fail("GRAPHIC_PROVENANCE_UNAVAILABLE", "The pinned badge asset bytes are unavailable.");
  }
  require(exact.length === 1, "Pinned badge asset has ambiguous retained records.", "GRAPHIC_PROVENANCE_UNEXPECTED");
  const retained = exact[0]!;
  require(retained.contentHash === semantic.badgeAsset.contentHash && sha256Bytes(retained.bytes) === semantic.badgeAsset.contentHash,
    "Pinned badge asset bytes do not match the #7 semantic snapshot.", "GRAPHIC_PROVENANCE_MISMATCH");
}

function verifyMethod(derivation: GraphicProvenanceDerivation, projectId: string, records: GraphicProvenanceRetainedRecords, requireAvailable: boolean): boolean | null {
  if (derivation.mode !== "deterministic") return null;
  const method = derivation.method;
  require(method !== null, "Deterministic derivation has no method identity.");
  const all = records.methods.filter((record) => record?.artifactId === method.artifactId);
  const exact = all.filter((record) => record?.projectId === projectId);
  if (exact.length === 0) {
    if (all.length > 0) fail("GRAPHIC_PROVENANCE_UNAUTHORIZED", "The retained deterministic method belongs to another project.");
    if (requireAvailable) fail("GRAPHIC_PROVENANCE_UNAVAILABLE", "Deterministic method bytes are required for this operation but are not retained.");
    return false;
  }
  require(exact.length === 1, "Deterministic method identity has ambiguous retained records.", "GRAPHIC_PROVENANCE_UNEXPECTED");
  const retained = exact[0]!;
  require(retained.methodId === method.id && retained.version === method.version && retained.contentHash === method.contentHash,
    "Retained deterministic method identity differs from the declared method.", "GRAPHIC_PROVENANCE_MISMATCH");
  require(sha256Bytes(retained.bytes) === method.contentHash,
    "Retained deterministic method bytes do not match the declared hash.", "GRAPHIC_PROVENANCE_MISMATCH");
  return true;
}

function verifySnapshotEvidence(snapshot: GraphicProvenanceSnapshot, records: GraphicProvenanceRetainedRecords, requireMethod: boolean): boolean | null {
  validateTemplatePackage(snapshot.template, snapshot.projectId, records);
  verifyBadge(snapshot.semanticSnapshot, snapshot.projectId, records);
  for (const source of snapshot.sources) verifyArtifact(source, snapshot.projectId, records);
  return verifyMethod(snapshot.derivation, snapshot.projectId, records, requireMethod);
}

function makeSnapshot(input: {
  projectId: string;
  template: GraphicTemplatePin;
  semanticSnapshot: GraphicProvenanceSemanticSnapshot;
  sources: readonly GraphicProvenanceSource[];
  derivation: GraphicProvenanceDerivation;
}): GraphicProvenanceSnapshot {
  const sources = input.sources.map(validateSource).sort((left, right) => left.sourceKey < right.sourceKey ? -1 : left.sourceKey > right.sourceKey ? 1 : 0);
  require(sources.length > 0, "A derived graphic needs at least one retained source.");
  require(new Set(sources.map((source) => source.sourceKey)).size === sources.length, "Provenance sourceKey values must be unique.");
  const semantic = validateSemanticSnapshot(input.semanticSnapshot);
  return validateSnapshot({
    schemaVersion: "graphic-provenance/v1",
    projectId: input.projectId,
    template: validateTemplatePin(input.template),
    semanticSnapshot: semantic,
    semanticSnapshotHash: semanticHash(semantic),
    sources,
    derivation: validateDerivation(input.derivation),
  });
}

function makeContent(input: {
  projectId: string;
  graphicId: string;
  revisionId: string;
  template: GraphicTemplatePin;
  semanticSnapshot: GraphicProvenanceSemanticSnapshot;
  snapshot?: GraphicProvenanceSnapshot;
}): ResolvedGraphicContent {
  const semantic = validateSemanticSnapshot(input.semanticSnapshot);
  return validateContent({
    graphicId: input.graphicId,
    revisionId: input.revisionId,
    projectId: input.projectId,
    template: validateTemplatePin(input.template),
    semanticSnapshot: semantic,
    semanticSnapshotHash: semanticHash(semantic),
    provenance: input.snapshot === undefined ? { kind: "manual" } : { kind: "derived", snapshotHash: sha256CanonicalJson(input.snapshot) },
  });
}

function requireAddressMatch(content: ResolvedGraphicContent, address: GraphicRevisionAddress): void {
  require(content.projectId === address.projectId && content.graphicId === address.graphicId && content.revisionId === address.revisionId,
    "Resolved graphic content does not match the requested project, graphic, and revision.", "GRAPHIC_PROVENANCE_MISMATCH");
}

function findSnapshot(content: ResolvedGraphicContent, records: GraphicProvenanceRetainedRecords): GraphicProvenanceSnapshot | null {
  const provenance = content.provenance;
  if (provenance.kind === "manual") return null;
  const matchingProject = records.snapshots.filter((snapshot) => snapshot?.projectId === content.projectId &&
    sha256CanonicalJson(snapshot) === provenance.snapshotHash);
  require(matchingProject.length === 1, matchingProject.length === 0 ? "The bound provenance snapshot is unavailable." : "The bound provenance snapshot is duplicated.",
    matchingProject.length === 0 ? "GRAPHIC_PROVENANCE_UNAVAILABLE" : "GRAPHIC_PROVENANCE_UNEXPECTED");
  const snapshot = validateSnapshot(matchingProject[0]);
  require(snapshot.projectId === content.projectId && sameJson(snapshot.template, content.template) &&
    sameJson(snapshot.semanticSnapshot, content.semanticSnapshot) && snapshot.semanticSnapshotHash === content.semanticSnapshotHash,
  "The bound provenance snapshot does not match the exact content project, template, or semantic values.", "GRAPHIC_PROVENANCE_MISMATCH");
  require(sha256CanonicalJson(snapshot) === provenance.snapshotHash,
    "The bound provenance snapshot hash does not match its canonical contents.", "GRAPHIC_PROVENANCE_MISMATCH");
  return snapshot;
}

function recordMatchesAddress(record: unknown, address: GraphicRevisionAddress): boolean {
  if (!isPlainRecord(record)) return false;
  const content = record.format === "graphic-content/v1" ? record.content : record;
  return isPlainRecord(content) && content.projectId === address.projectId && content.graphicId === address.graphicId && content.revisionId === address.revisionId;
}

function findRevisionRecord(address: GraphicRevisionAddress, records: GraphicProvenanceRetainedRecords): RetainedGraphicRevisionRecord {
  const recordsForAddress = records.revisions.filter((record) => recordMatchesAddress(record, address));
  require(recordsForAddress.length === 1, recordsForAddress.length === 0 ? "The requested graphic revision record is unavailable." : "The requested graphic revision record is duplicated.",
    recordsForAddress.length === 0 ? "GRAPHIC_PROVENANCE_UNAVAILABLE" : "GRAPHIC_PROVENANCE_UNEXPECTED");
  return recordsForAddress[0]!;
}

function freezeResolution(contentClass: ResolvedGraphicRevision["contentClass"], content: ResolvedGraphicContent | null,
  snapshot: GraphicProvenanceSnapshot | null, methodAvailable: boolean | null): ResolvedGraphicRevision {
  if (content === null) return deepFreeze({ contentClass: "legacy_unclassified", content: null, contentHash: null, snapshot: null, provenanceHash: null, methodAvailable: null });
  const contentHash = sha256CanonicalJson(content);
  const provenanceHash = snapshot === null ? null : sha256CanonicalJson(snapshot);
  return deepFreeze({ contentClass, content: cloneJson(content, "resolved graphic content"), contentHash,
    snapshot: snapshot === null ? null : cloneJson(snapshot, "provenance snapshot"), provenanceHash, methodAvailable }) as ResolvedGraphicRevision;
}

/** Resolve only an exact authorized revision record. Missing records never imply legacy. */
export function resolveRetainedGraphicRevision(
  address: GraphicRevisionAddress,
  injected: GraphicProvenanceRetainedRecords,
): ProvenanceResult<ResolvedGraphicRevision> {
  return result(() => {
    const records = validateRecords(injected);
    for (const field of ["projectId", "graphicId", "revisionId"] as const) {
      validateWireShape<string>(address[field], wireValidators.entityId, `graphic address ${field}`);
    }
    const record = findRevisionRecord(address, records);
    if (record.format === "legacy") {
      assertExactKeys(record, ["format", "projectId", "graphicId", "revisionId", "contentHash", "bytes"], "legacy revision record");
      require(record.projectId === address.projectId && record.graphicId === address.graphicId && record.revisionId === address.revisionId,
        "Trusted legacy classification does not match the exact requested identity.", "GRAPHIC_PROVENANCE_MISMATCH");
      requireHash(record.contentHash, "legacy revision contentHash");
      require(record.bytes instanceof Uint8Array && sha256Bytes(record.bytes) === record.contentHash,
        "Retained legacy graphic bytes do not match their exact content hash.", "GRAPHIC_PROVENANCE_MISMATCH");
      return freezeResolution("legacy_unclassified", null, null, null);
    }
    require(record.format === "graphic-content/v1", "Trusted resolver returned an unknown graphic content format.", "GRAPHIC_PROVENANCE_INCOMPLETE");
    assertExactKeys(record, ["format", "content", "contentHash"], "new-format revision record");
    const content = validateContent(record.content);
    requireAddressMatch(content, address);
    requireHash(record.contentHash, "retained revision contentHash");
    require(sha256CanonicalJson(content) === record.contentHash,
      "Retained graphic content hash does not match the exact resolved revision.", "GRAPHIC_PROVENANCE_MISMATCH");
    const snapshot = findSnapshot(content, records);
    let methodAvailable: boolean | null = null;
    if (snapshot !== null) methodAvailable = verifySnapshotEvidence(snapshot, records, false);
    else {
      validateTemplatePackage(content.template, content.projectId, records);
      verifyBadge(content.semanticSnapshot, content.projectId, records);
    }
    return freezeResolution(content.provenance.kind === "manual" ? "manual" : "derived", content, snapshot, methodAvailable);
  });
}

function assertNoRevisionCollision(address: GraphicRevisionAddress, records: GraphicProvenanceRetainedRecords): void {
  const existing = records.revisions.some((record) => recordMatchesAddress(record, address));
  require(!existing, "The proposed immutable graphic revision ID already exists.", "GRAPHIC_PROVENANCE_UNEXPECTED");
}

function makeReceipt(operation: GraphicAuditReceipt["operation"], input: {
  projectId: string;
  graphicId: string;
  prior?: { revisionId: string; contentHash: GraphicHash; provenanceHash: GraphicHash | null };
  content: ResolvedGraphicContent;
  provenanceHash: GraphicHash | null;
  actorId: string;
  recordedAt: string;
}): Readonly<GraphicAuditReceipt> {
  requireText(input.actorId, "audit actorId");
  requireText(input.recordedAt, "audit recordedAt");
  const contentHash = sha256CanonicalJson(input.content);
  return frozenClone({
    schemaVersion: "graphic-provenance-audit/v1",
    operation,
    projectId: input.projectId,
    graphicId: input.graphicId,
    priorRevisionId: input.prior?.revisionId ?? null,
    priorContentHash: input.prior?.contentHash ?? null,
    priorProvenanceHash: input.prior?.provenanceHash ?? null,
    newRevisionId: input.content.revisionId,
    newContentHash: contentHash,
    newProvenanceHash: input.provenanceHash,
    actorId: input.actorId,
    recordedAt: input.recordedAt,
  }, "audit receipt");
}

function proposal(content: ResolvedGraphicContent, snapshot: GraphicProvenanceSnapshot | null,
  methodAvailable: boolean | null, receipt: Readonly<GraphicAuditReceipt>): ProposedGraphicRevision {
  const frozenContent = frozenClone(content, "proposed graphic content");
  const frozenSnapshot = snapshot === null ? null : frozenClone(snapshot, "proposed provenance snapshot");
  const contentHash = sha256CanonicalJson(frozenContent);
  const provenanceHash = frozenSnapshot === null ? null : sha256CanonicalJson(frozenSnapshot);
  return deepFreeze({ content: frozenContent, contentHash, snapshot: frozenSnapshot, provenanceHash, methodAvailable, receipt });
}

function checkCandidateEvidence(snapshot: GraphicProvenanceSnapshot | null, content: ResolvedGraphicContent,
  records: GraphicProvenanceRetainedRecords, requireMethod: boolean): boolean | null {
  if (snapshot === null) {
    validateTemplatePackage(content.template, content.projectId, records);
    verifyBadge(content.semanticSnapshot, content.projectId, records);
    return null;
  }
  const snapshotHash = sha256CanonicalJson(snapshot);
  require(content.provenance.kind === "derived" && content.provenance.snapshotHash === snapshotHash,
    "Proposed content is not bound to its exact provenance snapshot.", "GRAPHIC_PROVENANCE_MISMATCH");
  return verifySnapshotEvidence(snapshot, records, requireMethod);
}

function buildProposal(operation: GraphicAuditReceipt["operation"], content: ResolvedGraphicContent,
  snapshot: GraphicProvenanceSnapshot | null, methodAvailable: boolean | null,
  prior: ResolvedGraphicRevision | null, actorId: string, recordedAt: string): ProposedGraphicRevision {
  const priorHash = prior?.contentHash ?? null;
  const priorRevisionId = prior?.content?.revisionId ?? null;
  const priorP = prior?.provenanceHash ?? null;
  const receipt = makeReceipt(operation, { projectId: content.projectId, graphicId: content.graphicId,
    ...(priorHash === null || priorRevisionId === null ? {} : { prior: { revisionId: priorRevisionId, contentHash: priorHash, provenanceHash: priorP } }),
    content, provenanceHash: snapshot === null ? null : sha256CanonicalJson(snapshot), actorId, recordedAt });
  return proposal(content, snapshot, methodAvailable, receipt);
}

export function createGraphicContent(
  input: CreateGraphicContentInput,
  injected: GraphicProvenanceRetainedRecords = EMPTY_RECORDS,
): ProvenanceResult<ProposedGraphicRevision> {
  return result(() => {
    const records = validateRecords(injected);
    const address = { projectId: input.projectId, graphicId: input.graphicId, revisionId: input.revisionId };
    requireText(input.projectId, "projectId"); requireText(input.graphicId, "graphicId"); requireText(input.revisionId, "revisionId");
    assertNoRevisionCollision(address, records);
    const template = validateTemplatePin(input.template);
    const semantic = validateSemanticSnapshot(input.semanticSnapshot);
    let snapshot: GraphicProvenanceSnapshot | null = null;
    if (input.content.kind === "derived") {
      snapshot = makeSnapshot({ projectId: input.projectId, template, semanticSnapshot: semantic, sources: input.content.sources, derivation: input.content.derivation });
    } else {
      require(input.content.kind === "manual", "New graphic content must declare manual or derived format.");
    }
    const content = makeContent({ ...address, template, semanticSnapshot: semantic, ...(snapshot === null ? {} : { snapshot }) });
    const methodAvailable = checkCandidateEvidence(snapshot, content, records, snapshot?.derivation.mode === "deterministic");
    const built = buildProposal("create", content, snapshot, methodAvailable, null, input.actorId, input.recordedAt);
    return built;
  });
}

export function repeatGraphicContent(
  input: RepeatGraphicContentInput,
  injected: GraphicProvenanceRetainedRecords,
): ProvenanceResult<ProposedGraphicRevision> {
  return result(() => {
    const resolved = resolveRetainedGraphicRevision(input, injected);
    require(resolved.ok, resolved.ok ? "" : resolved.block.message, resolved.ok ? undefined : resolved.block.code);
    require(resolved.value.content !== null, "Legacy graphic content has no provenance-format revision to repeat here.", "GRAPHIC_PROVENANCE_UNEXPECTED");
    const content = validateContent(resolved.value.content);
    const snapshot = resolved.value.snapshot === null ? null : validateSnapshot(resolved.value.snapshot);
    return buildProposal("repeat", content, snapshot, resolved.value.methodAvailable, resolved.value, input.actorId, input.recordedAt);
  });
}

export function refreshGraphicContent(
  input: RefreshGraphicContentInput,
  injected: GraphicProvenanceRetainedRecords,
): ProvenanceResult<ProposedGraphicRevision> {
  return result(() => {
    const records = validateRecords(injected);
    const previousResult = resolveRetainedGraphicRevision(input, records);
    require(previousResult.ok, previousResult.ok ? "" : previousResult.block.message, previousResult.ok ? undefined : previousResult.block.code);
    const previous = previousResult.value;
    require(previous.content !== null && previous.content.provenance.kind === "derived" && previous.snapshot !== null,
      "Explicit data refresh requires an existing derived graphic revision.", "GRAPHIC_PROVENANCE_INCOMPLETE");
    const oldContent = validateContent(previous.content);
    const nextAddress = { projectId: input.projectId, graphicId: input.graphicId, revisionId: input.newRevisionId };
    requireText(input.newRevisionId, "newRevisionId"); assertNoRevisionCollision(nextAddress, records);
    const snapshot = makeSnapshot({ projectId: oldContent.projectId, template: oldContent.template, semanticSnapshot: input.semanticSnapshot,
      sources: input.sources, derivation: input.derivation });
    const content = makeContent({ ...nextAddress, template: oldContent.template, semanticSnapshot: input.semanticSnapshot, snapshot });
    const methodAvailable = checkCandidateEvidence(snapshot, content, records, snapshot.derivation.mode === "deterministic");
    return buildProposal("refresh", content, snapshot, methodAvailable, previous, input.actorId, input.recordedAt);
  });
}

export function migrateGraphicTemplate(
  input: MigrateGraphicTemplateInput,
  injected: GraphicProvenanceRetainedRecords,
): ProvenanceResult<ProposedGraphicRevision> {
  return result(() => {
    const records = validateRecords(injected);
    const previousResult = resolveRetainedGraphicRevision(input, records);
    require(previousResult.ok, previousResult.ok ? "" : previousResult.block.message, previousResult.ok ? undefined : previousResult.block.code);
    const previous = previousResult.value;
    require(previous.content !== null, "A legacy graphic revision cannot be migrated without an explicit provenance-format source revision.", "GRAPHIC_PROVENANCE_INCOMPLETE");
    const oldContent = validateContent(previous.content);
    const address = { projectId: input.projectId, graphicId: input.graphicId, revisionId: input.newRevisionId };
    requireText(input.newRevisionId, "newRevisionId"); assertNoRevisionCollision(address, records);
    const template = validateTemplatePin(input.template);
    const semantic = validateSemanticSnapshot(input.semanticSnapshot);
    require(sameJson(semantic, oldContent.semanticSnapshot),
      "Template migration must preserve the existing EV24 semantic values and badge identity.", "GRAPHIC_PROVENANCE_MISMATCH");
    let snapshot: GraphicProvenanceSnapshot | null = null;
    if (previous.snapshot !== null) {
      snapshot = makeSnapshot({ projectId: input.projectId, template, semanticSnapshot: semantic,
        sources: previous.snapshot.sources, derivation: previous.snapshot.derivation });
    }
    const content = makeContent({ ...address, template, semanticSnapshot: semantic, ...(snapshot === null ? {} : { snapshot }) });
    // Migration uses frozen evidence and caller-supplied resolved values; it never runs a method.
    const methodAvailable = checkCandidateEvidence(snapshot, content, records, false);
    return buildProposal("template_migration", content, snapshot, methodAvailable, previous, input.actorId, input.recordedAt);
  });
}

