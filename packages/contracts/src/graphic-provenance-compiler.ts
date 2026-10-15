import { canonicalJson, sha256CanonicalJson, type CompileDiagnostic } from "./compiler-core.js";
import type { CompilerDependenciesV1, FusionGraphicEvent, FusionTemplateSource } from "./generated/contracts.js";
import type { CompilerDependenciesV2, ScriptDocumentV2 } from "./generated/contracts-v2.js";
import type { ErrorObject } from "ajv/dist/2020.js";

type Snapshot = NonNullable<CompilerDependenciesV1["graphicProvenanceSnapshots"]>[number];
type Binding = NonNullable<FusionGraphicEvent["graphicProvenance"]>;
type TemplatePin = Pick<FusionTemplateSource, "templateKey" | "projectRevisionId" | "packageDigest" | "entryAssetHash">;
export interface GraphicProvenanceContext {
  entityId: string;
  projectId: string;
  template: TemplatePin;
  semanticSnapshot: FusionGraphicEvent["semanticSnapshot"];
  semanticSnapshotHash: string;
  binding?: Binding;
}

const same = (left: unknown, right: unknown): boolean => canonicalJson(left) === canonicalJson(right);
const problem = (code: string, message: string, entityId?: string): CompileDiagnostic => ({ code, message, ...(entityId ? { entityId } : {}) });

function finiteJson(value: unknown, ancestors = new Set<object>()): boolean {
  if (value === null || typeof value === "string" || typeof value === "boolean") return true;
  if (typeof value === "number") return Number.isFinite(value);
  if (typeof value !== "object" || ancestors.has(value)) return false;
  const prototype: unknown = Object.getPrototypeOf(value);
  if (!Array.isArray(value) && prototype !== Object.prototype && prototype !== null) return false;
  ancestors.add(value);
  const keys = Reflect.ownKeys(value);
  if (Array.isArray(value)) {
    if (keys.length !== value.length + 1) return false;
    for (let index = 0; index < value.length; index += 1) if (!Object.hasOwn(value, index)) return false;
  }
  for (const key of keys) {
    if (Array.isArray(value) && key === "length") continue;
    const descriptor = Object.getOwnPropertyDescriptor(value, key)!;
    if (typeof key !== "string" || !("value" in descriptor) || !descriptor.enumerable || !finiteJson(descriptor.value, ancestors)) return false;
  }
  ancestors.delete(value);
  return true;
}

/** Refuse non-wire JS values before recursive schema validation or canonical hashing. */
export function graphicProvenanceJsonProblem(input: unknown): CompileDiagnostic | undefined {
  if (input === null || typeof input !== "object") return undefined;
  for (const name of ["graphicProvenanceSnapshots", "resolvedGraphicContents"]) {
    const descriptor = Object.getOwnPropertyDescriptor(input, name);
    if (descriptor && (!("value" in descriptor) || !finiteJson(descriptor.value))) {
      return { code: "GRAPHIC_PROVENANCE_INCOMPLETE", message: "Graphic provenance inventories must contain finite JSON data without cycles or accessors.", jsonPath: `/${name}` };
    }
  }
  return undefined;
}

export function graphicProvenanceSchemaCode(error: ErrorObject): string | undefined {
  const path = `${error.instancePath}/${String(error.params.missingProperty ?? "")}/${error.schemaPath}`;
  if (!/graphicProvenance|graphicContent|resolvedGraphicContents|GraphicProvenance|ResolvedGraphicContent/.test(path)) return undefined;
  if (["required", "dependentRequired", "minItems", "minLength"].includes(error.keyword)) return "GRAPHIC_PROVENANCE_INCOMPLETE";
  return error.keyword === "additionalProperties" || error.keyword === "not" ? "GRAPHIC_PROVENANCE_UNEXPECTED" : "GRAPHIC_PROVENANCE_MISMATCH";
}

/** Compiler inputs are trusted resolver results; byte verification belongs to the retained resolver. */
export function validateGraphicSnapshotInventory(snapshots: readonly Snapshot[], contexts: readonly GraphicProvenanceContext[]): CompileDiagnostic[] {
  const diagnostics: CompileDiagnostic[] = [];
  const byHash = new Map<string, Snapshot>();
  const used = new Set<string>();
  for (const snapshot of snapshots) {
    const hash = sha256CanonicalJson(snapshot);
    if (byHash.has(hash)) diagnostics.push(problem("GRAPHIC_PROVENANCE_UNEXPECTED", "Duplicate provenance snapshot.", hash));
    byHash.set(hash, snapshot);
    const keys = snapshot.sources.map((source) => source.sourceKey);
    if (new Set(keys).size !== keys.length || !same(keys, [...keys].sort())) {
      diagnostics.push(problem("GRAPHIC_PROVENANCE_MISMATCH", "Provenance sources must be unique and frozen in source-key order.", hash));
    }
  }
  for (const context of contexts) {
    const badge = context.semanticSnapshot.badgeAsset;
    if (context.semanticSnapshot.values.badgeOverrideAssetId !== (badge?.assetId ?? null) ||
        sha256CanonicalJson(context.semanticSnapshot) !== context.semanticSnapshotHash) {
      diagnostics.push(problem("GRAPHIC_PROVENANCE_MISMATCH", "Resolved semantic values, badge and semantic hash disagree.", context.entityId));
    }
    if (context.binding?.kind !== "derived") continue;
    const hash = context.binding.snapshotHash;
    used.add(hash);
    const snapshot = byHash.get(hash);
    if (!snapshot) {
      diagnostics.push(problem("GRAPHIC_PROVENANCE_UNAVAILABLE", "The addressed retained provenance snapshot is unavailable.", context.entityId));
      continue;
    }
    if (snapshot.projectId !== context.projectId) {
      diagnostics.push(problem("GRAPHIC_PROVENANCE_UNAUTHORIZED", "The provenance snapshot belongs to another project.", context.entityId));
    } else if (!same(snapshot.template, context.template) || !same(snapshot.semanticSnapshot, context.semanticSnapshot) ||
        snapshot.semanticSnapshotHash !== context.semanticSnapshotHash) {
      diagnostics.push(problem("GRAPHIC_PROVENANCE_MISMATCH", "The provenance snapshot does not bind the exact template and semantic tuple.", context.entityId));
    }
  }
  for (const hash of byHash.keys()) if (!used.has(hash)) {
    diagnostics.push(problem("GRAPHIC_PROVENANCE_UNEXPECTED", "A supplied provenance snapshot is unused.", hash));
  }
  return diagnostics;
}

/** Resolve each authored graphic reference, never infer legacy from a missing record. */
export function validateGraphicContentsV2(document: ScriptDocumentV2, dependencies: CompilerDependenciesV2): CompileDiagnostic[] {
  const diagnostics: CompileDiagnostic[] = [];
  const sources = new Map<string, { graphicId: string; revisionId: string }>();
  for (const block of document.activeDraft.blocks) {
    if (block.type === "visual_only") {
      if (block.payload.source.kind === "graphic_revision") sources.set(block.payload.payloadId, block.payload.source);
    } else if (block.type === "narration" && block.state === "active") {
      for (const slot of block.primaryVisualSequence?.slots ?? []) {
        if (slot.kind === "content" && slot.payload.kind === "visual" && slot.payload.source.kind === "graphic_revision") sources.set(slot.payload.payloadId, slot.payload.source);
      }
      for (const overlay of block.overlayEvents) if (overlay.payload.source.kind === "graphic_revision") sources.set(overlay.payload.payloadId, overlay.payload.source);
    }
  }
  const key = (source: { graphicId: string; revisionId: string }): string => `${source.graphicId}:${source.revisionId}`;
  const contents = new Map<string, NonNullable<CompilerDependenciesV2["resolvedGraphicContents"]>[number]>();
  for (const content of dependencies.resolvedGraphicContents ?? []) {
    const contentKey = key(content);
    if (contents.has(contentKey)) diagnostics.push(problem("GRAPHIC_PROVENANCE_UNEXPECTED", "Duplicate resolved graphic content.", content.revisionId));
    contents.set(contentKey, content);
  }
  const used = new Set<string>();
  const contexts: GraphicProvenanceContext[] = [];
  for (const descriptor of dependencies.occurrenceResolutions) {
    const source = sources.get(descriptor.payloadId);
    if (!source) {
      if (descriptor.graphicContentClass !== undefined || descriptor.graphicContentBinding !== undefined) diagnostics.push(problem("GRAPHIC_PROVENANCE_UNEXPECTED", "Only a graphic revision may carry graphic classification or binding.", descriptor.payloadId));
      continue;
    }
    const content = contents.get(key(source));
    if (descriptor.graphicContentClass === undefined) {
      diagnostics.push(problem("GRAPHIC_PROVENANCE_INCOMPLETE", "Graphic resolution requires explicit retained-record classification.", descriptor.payloadId));
      continue;
    }
    if (descriptor.sourceSnapshot.system !== "graphic_asset") diagnostics.push(problem("GRAPHIC_PROVENANCE_MISMATCH", "Graphic media must bind a graphic-asset snapshot.", descriptor.payloadId));
    if (descriptor.graphicContentClass === "legacy_unclassified") {
      if (content || descriptor.graphicContentBinding !== undefined) diagnostics.push(problem("GRAPHIC_PROVENANCE_UNEXPECTED", "Legacy classification forbids new content and provenance bindings.", descriptor.payloadId));
      continue;
    }
    if (!content) {
      diagnostics.push(problem("GRAPHIC_PROVENANCE_INCOMPLETE", "New-format graphic resolution requires matching retained content.", descriptor.payloadId));
      continue;
    }
    used.add(key(source));
    if (content.projectId !== document.projectId) diagnostics.push(problem("GRAPHIC_PROVENANCE_UNAUTHORIZED", "Resolved graphic content belongs to another project.", descriptor.payloadId));
    if (content.provenance.kind !== descriptor.graphicContentClass) diagnostics.push(problem("GRAPHIC_PROVENANCE_MISMATCH", "Graphic classification and retained content disagree.", descriptor.payloadId));
    if (descriptor.graphicContentClass === "derived") {
      const binding = descriptor.graphicContentBinding;
      if (!binding) diagnostics.push(problem("GRAPHIC_PROVENANCE_INCOMPLETE", "Derived media requires a retained content-to-media binding.", descriptor.payloadId));
      else if (key(binding) !== key(source) || content.provenance.kind !== "derived" || binding.provenanceHash !== content.provenance.snapshotHash) diagnostics.push(problem("GRAPHIC_PROVENANCE_MISMATCH", "Materialized media does not bind this exact graphic revision and provenance hash.", descriptor.payloadId));
    } else if (descriptor.graphicContentBinding !== undefined) diagnostics.push(problem("GRAPHIC_PROVENANCE_UNEXPECTED", "Manual content forbids a derived-media binding.", descriptor.payloadId));
    contexts.push({ entityId: descriptor.payloadId, projectId: document.projectId, template: content.template, semanticSnapshot: content.semanticSnapshot, semanticSnapshotHash: content.semanticSnapshotHash, binding: content.provenance });
  }
  for (const [payloadId] of sources) if (!dependencies.occurrenceResolutions.some((item) => item.payloadId === payloadId)) {
    diagnostics.push(problem("GRAPHIC_PROVENANCE_INCOMPLETE", "The graphic reference has no retained resolution.", payloadId));
  }
  for (const [contentKey, content] of contents) if (!used.has(contentKey)) diagnostics.push(problem("GRAPHIC_PROVENANCE_UNEXPECTED", "Supplied graphic content is unused.", content.revisionId));
  return [...diagnostics, ...validateGraphicSnapshotInventory(dependencies.graphicProvenanceSnapshots ?? [], contexts)];
}
