import { describe, expect, it } from "vitest";

import { canonicalJson, sha256CanonicalJson } from "../src/compiler-core.js";
import {
  createGraphicContent,
  migrateGraphicTemplate,
  refreshGraphicContent,
  repeatGraphicContent,
  resolveRetainedGraphicRevision,
  type CreateGraphicContentInput,
  type GraphicProvenanceDerivation,
  type GraphicProvenanceRetainedRecords,
  type GraphicProvenanceSemanticSnapshot,
  type GraphicProvenanceSource,
  type GraphicTemplatePin,
  type ResolvedGraphicContent,
  type RetainedArtifactBytes,
  type RetainedGraphicRevisionRecord,
} from "../src/graphic-provenance.js";
import {
  computePackageDigest,
  sha256Bytes,
  type ExternalTemplatePackage,
  type PackageManifest,
} from "../src/template-library.js";

const projectId = "10000000-0000-4000-8000-000000000001";
const graphicId = "20000000-0000-4000-8000-000000000001";
const revisionId = "30000000-0000-4000-8000-000000000001";
const bytes = (value: string): Uint8Array => new TextEncoder().encode(value);
const sourcePayloads = new Map<string, string>();

function packageFixture(label: string): ExternalTemplatePackage {
  const entry = bytes("entry:" + label);
  const sidecar = bytes("sidecar:" + label);
  const manifest: PackageManifest = {
    schemaVersion: "external-template-package/v1",
    packageKind: "graphic",
    externalLineageKey: "ev24-lower-third",
    displayName: "EV24 fixture",
    externalRevisionLabel: label,
    entryPoint: "EV24.setting",
    validator: { profile: "ev24-lower-third", version: "1" },
    compatibility: { requiredCapabilities: ["fusion"] },
    provenance: {
      author: "Fixture author",
      publisher: "Fixture publisher",
      organization: "Fixture organization",
      sourceTool: "Fixture tool",
      sourceToolVersion: "1",
      sourceRevision: label,
      createdAt: "2026-10-15",
      attestedBy: "Fixture producer",
    },
    rights: {
      allowedProjectIds: [projectId],
      declarations: [{ id: "rights", holder: "Fixture holder", basis: "Fixture basis", embeddingAllowed: true, redistributionAllowed: false }],
    },
    files: [
      { path: "EV24.setting", byteLength: entry.byteLength, sha256: sha256Bytes(entry), mediaType: "application/vnd.blackmagic.fusion-setting", rightsId: "rights" },
      { path: "sidecar.bin", byteLength: sidecar.byteLength, sha256: sha256Bytes(sidecar), mediaType: "application/octet-stream", rightsId: "rights" },
    ],
  };
  return { transport: "directory", manifest, files: [{ path: "EV24.setting", bytes: entry }, { path: "sidecar.bin", bytes: sidecar }] };
}

function pinFor(pkg: ExternalTemplatePackage, revision = "revision_1"): GraphicTemplatePin {
  const entry = pkg.files.find((file) => file.path === pkg.manifest.entryPoint);
  if (entry === undefined) throw new Error("Fixture entry missing.");
  return {
    templateKey: "ev24-lower-third",
    projectRevisionId: revision,
    packageDigest: computePackageDigest(pkg),
    entryAssetHash: sha256Bytes(entry.bytes),
  };
}

function source(sourceKey: string, artifactId: string, raw: string, versionLabel = "v1"): GraphicProvenanceSource {
  sourcePayloads.set(artifactId, raw);
  return {
    sourceKey,
    citation: { title: "Source " + sourceKey, publisher: "Fixture publisher", originalLocator: null, versionLabel },
    snapshot: { artifactId, contentHash: sha256Bytes(bytes(raw)), mediaType: "text/plain" },
  };
}

const semanticSnapshot = {
  values: { country: "otis", topLineOverride: "Fixture title", bottomLineOverride: "Fixture subtitle", badgeOverrideAssetId: null },
  badgeAsset: null,
} as const;

const manualDerivation: GraphicProvenanceDerivation = {
  mode: "manual", version: "1", note: "Select the retained count and enter the displayed text.", method: null, parameters: {},
};

function recordsFor(options: {
  pkg?: ExternalTemplatePackage;
  revision?: string;
  sources?: GraphicProvenanceSource[];
  methods?: GraphicProvenanceRetainedRecords["methods"];
  revisions?: RetainedGraphicRevisionRecord[];
  snapshots?: GraphicProvenanceRetainedRecords["snapshots"];
  compatible?: boolean;
} = {}): GraphicProvenanceRetainedRecords {
  const pkg = options.pkg ?? packageFixture("r1");
  return {
    revisions: options.revisions ?? [],
    snapshots: options.snapshots ?? [],
    sources: (options.sources ?? []).map((item) => retainedSource(item, sourcePayloads.get(item.snapshot.artifactId) ?? "")),
    badges: [],
    methods: options.methods ?? [],
    templates: [{ projectId, templateKey: "ev24-lower-third", projectRevisionId: options.revision ?? "revision_1", compatible: options.compatible ?? true, package: pkg }],
  };
}

function retainedSource(item: GraphicProvenanceSource, raw: string): RetainedArtifactBytes {
  return { projectId, artifactId: item.snapshot.artifactId, contentHash: item.snapshot.contentHash, mediaType: item.snapshot.mediaType, bytes: bytes(raw) };
}

function input(overrides: Partial<CreateGraphicContentInput> = {}): CreateGraphicContentInput {
  const pkg = packageFixture("r1");
  return {
    projectId,
    graphicId,
    revisionId,
    template: pinFor(pkg),
    semanticSnapshot,
    content: { kind: "derived", sources: [source("tally", "40000000-0000-4000-8000-000000000001", "source one")], derivation: manualDerivation },
    actorId: "actor-1",
    recordedAt: "2026-10-15T12:00:00.000Z",
    ...overrides,
  };
}

function successful<T>(value: { ok: true; value: T } | { ok: false; block: { code: string; message: string } }): T {
  if (!value.ok) throw new Error(value.block.code + ": " + value.block.message);
  return value.value;
}

function retainedRevision(content: ResolvedGraphicContent): RetainedGraphicRevisionRecord {
  return { format: "graphic-content/v1", content, contentHash: sha256CanonicalJson(content) };
}

function methodDerivation(methodContent = "method bytes"): { derivation: GraphicProvenanceDerivation; retained: GraphicProvenanceRetainedRecords["methods"][number] } {
  const methodBytes = bytes(methodContent);
  const derivation: GraphicProvenanceDerivation = {
    mode: "deterministic", version: "2", note: "Apply the registered total operation to the retained source rows.",
    method: { id: "50000000-0000-4000-8000-000000000001", version: "2", artifactId: "50000000-0000-4000-8000-000000000002", contentHash: sha256Bytes(methodBytes) },
    parameters: { fields: ["east", "west"], rounding: null },
  };
  return {
    derivation,
    retained: { projectId, methodId: "50000000-0000-4000-8000-000000000001", version: "2", artifactId: "50000000-0000-4000-8000-000000000002", contentHash: derivation.method!.contentHash, bytes: methodBytes },
  };
}

describe("issue #218 retained graphic provenance", () => {
  it("creates sorted, deep-frozen derived content with the unchanged #7 semantic hash and a separate receipt", () => {
    const pkg = packageFixture("r1");
    const b = source("z-source", "40000000-0000-4000-8000-000000000002", "source z");
    const a = source("a-source", "40000000-0000-4000-8000-000000000003", "source a");
    a.citation.title = "Café  ";
    a.citation.originalLocator = "https://example.test/e\u0301";
    const candidate = input({ template: pinFor(pkg), content: { kind: "derived", sources: [b, a], derivation: manualDerivation } });
    const retained = recordsFor({ pkg, sources: [a, b] });
    const proposal = successful(createGraphicContent(candidate, retained));

    expect(proposal.snapshot?.sources.map((item) => item.sourceKey)).toEqual(["a-source", "z-source"]);
    expect(proposal.content.semanticSnapshotHash).toBe(sha256CanonicalJson({ values: semanticSnapshot.values, badgeAsset: null }));
    expect(proposal.content.provenance).toEqual({ kind: "derived", snapshotHash: proposal.provenanceHash });
    expect(proposal.content.semanticSnapshot).toEqual(semanticSnapshot);
    expect(proposal.snapshot?.sources[0]?.citation).toMatchObject({ title: "Café  ", originalLocator: "https://example.test/e\u0301" });
    expect(proposal.receipt).toMatchObject({ operation: "create", priorContentHash: null, priorProvenanceHash: null, actorId: "actor-1" });
    expect(proposal.receipt.newContentHash).toBe(proposal.contentHash);
    expect(proposal.provenanceHash).toBe(sha256CanonicalJson(proposal.snapshot));
    expect(Object.isFrozen(proposal.content)).toBe(true);
    expect(Object.isFrozen(proposal.content.semanticSnapshot.values)).toBe(true);
    expect(Object.isFrozen(proposal.snapshot?.sources)).toBe(true);
    expect(Object.isFrozen(proposal.receipt)).toBe(true);
    expect(canonicalJson(candidate.content)).toContain("z-source");
    expect(candidate.content.kind).toBe("derived");

    const reorderedSemantic: GraphicProvenanceSemanticSnapshot = {
      values: {
        bottomLineOverride: "Fixture subtitle",
        badgeOverrideAssetId: null,
        topLineOverride: "Fixture title",
        country: "otis",
      },
      badgeAsset: null,
    };
    const sameMaterial = successful(createGraphicContent({
      ...candidate,
      semanticSnapshot: reorderedSemantic,
      content: { kind: "derived", sources: [a, b], derivation: manualDerivation },
      actorId: "actor-other",
      recordedAt: "2026-10-15T12:09:00.000Z",
    }, retained));
    expect(sameMaterial.contentHash).toBe(proposal.contentHash);
    expect(sameMaterial.provenanceHash).toBe(proposal.provenanceHash);
    expect(sameMaterial.receipt).toMatchObject({ actorId: "actor-other", recordedAt: "2026-10-15T12:09:00.000Z" });

    const normalizedSource = {
      ...a,
      citation: { ...a.citation, title: "Café", originalLocator: "https://example.test/é" },
    };
    const normalizedCitation = successful(createGraphicContent({
      ...candidate,
      content: { kind: "derived", sources: [normalizedSource, b], derivation: manualDerivation },
    }, retained));
    expect(normalizedCitation.provenanceHash).not.toBe(proposal.provenanceHash);
  });

  it("blocks unknown revisions and only classifies legacy from an explicit trusted record", () => {
    const missing = resolveRetainedGraphicRevision({ projectId, graphicId, revisionId }, recordsFor());
    expect(missing).toMatchObject({ ok: false, block: { code: "GRAPHIC_PROVENANCE_UNAVAILABLE" } });

    const legacyBytes = bytes("legacy retained graphic bytes");
    const legacyRecord: RetainedGraphicRevisionRecord = { format: "legacy", projectId, graphicId, revisionId, bytes: legacyBytes, contentHash: sha256Bytes(legacyBytes) };
    const legacy = successful(resolveRetainedGraphicRevision({ projectId, graphicId, revisionId }, recordsFor({ revisions: [legacyRecord] })));
    expect(legacy).toMatchObject({ contentClass: "legacy_unclassified", content: null, provenanceHash: null });

    // These are new-format-shaped bytes under a false trusted legacy tag. The resolver
    // verifies their byte digest but cannot override the upstream format classification.
    const newShapedBytes = bytes(canonicalJson({ projectId, graphicId, revisionId, provenance: { kind: "derived" } }));
    const falselyLegacy: RetainedGraphicRevisionRecord = {
      format: "legacy", projectId, graphicId, revisionId, bytes: newShapedBytes,
      contentHash: sha256Bytes(newShapedBytes),
    };
    const falselyClassified = successful(resolveRetainedGraphicRevision({ projectId, graphicId, revisionId }, recordsFor({ revisions: [falselyLegacy] })));
    expect(falselyClassified.contentClass).toBe("legacy_unclassified");

    const wrongFormat = { format: "graphic-content/v1", content: { projectId, graphicId, revisionId }, contentHash: "sha256:" + "a".repeat(64) } as unknown as RetainedGraphicRevisionRecord;
    const invalidNew = resolveRetainedGraphicRevision({ projectId, graphicId, revisionId }, recordsFor({ revisions: [wrongFormat] }));
    expect(invalidNew).toMatchObject({ ok: false, block: { code: "GRAPHIC_PROVENANCE_INCOMPLETE" } });
  });

  it("validates legacy address IDs and refuses collisions with unknown-format records", () => {
    const retainedBytes = bytes("legacy retained bytes");
    for (const field of ["projectId", "graphicId", "revisionId"] as const) {
      const address = { projectId, graphicId, revisionId, [field]: "invalid-identity" };
      const legacy: RetainedGraphicRevisionRecord = { format: "legacy", ...address, bytes: retainedBytes, contentHash: sha256Bytes(retainedBytes) };
      expect(resolveRetainedGraphicRevision(address, recordsFor({ revisions: [legacy] })))
        .toMatchObject({ ok: false, block: { code: "GRAPHIC_PROVENANCE_MISMATCH" } });
    }
    const unknownRecord = { format: "unknown-version", projectId, graphicId, revisionId } as unknown as RetainedGraphicRevisionRecord;
    const records = recordsFor({ revisions: [unknownRecord] });
    expect(resolveRetainedGraphicRevision({ projectId, graphicId, revisionId }, records))
      .toMatchObject({ ok: false, block: { code: "GRAPHIC_PROVENANCE_INCOMPLETE" } });
    expect(createGraphicContent(input(), records))
      .toMatchObject({ ok: false, block: { code: "GRAPHIC_PROVENANCE_UNEXPECTED" } });
  });

  it("repeats frozen deterministic values without method bytes, but blocks a present wrong method identity", () => {
    const pkg = packageFixture("r1");
    const item = source("tally", "40000000-0000-4000-8000-000000000001", "source one");
    const { derivation, retained } = methodDerivation();
    const created = successful(createGraphicContent(input({ content: { kind: "derived", sources: [item], derivation } }),
      recordsFor({ pkg, sources: [item], methods: [retained] })));
    const revisionRecord = retainedRevision(created.content);
    const retainedWithoutMethod = recordsFor({ pkg, sources: [item], revisions: [revisionRecord], snapshots: [created.snapshot!] });
    const resolved = successful(resolveRetainedGraphicRevision({ projectId, graphicId, revisionId }, retainedWithoutMethod));
    expect(resolved.methodAvailable).toBe(false);

    const repeated = successful(repeatGraphicContent({ projectId, graphicId, revisionId, actorId: "actor-2", recordedAt: "2026-10-15T12:01:00.000Z" }, retainedWithoutMethod));
    expect(repeated.contentHash).toBe(created.contentHash);
    expect(repeated.provenanceHash).toBe(created.provenanceHash);
    expect(repeated.methodAvailable).toBe(false);
    expect(repeated.receipt).toMatchObject({ operation: "repeat", priorContentHash: created.contentHash, newContentHash: created.contentHash });

    retainedWithoutMethod.methods = [{ ...retained, bytes: bytes("changed method bytes") }];
    expect(resolveRetainedGraphicRevision({ projectId, graphicId, revisionId }, retainedWithoutMethod))
      .toMatchObject({ ok: false, block: { code: "GRAPHIC_PROVENANCE_MISMATCH" } });
  });

  it("requires every source byte and verifies package file hashes, lengths, entry bytes, and project scope", () => {
    const pkg = packageFixture("r1");
    const item = source("tally", "40000000-0000-4000-8000-000000000001", "source one");
    const created = successful(createGraphicContent(input({ content: { kind: "derived", sources: [item], derivation: manualDerivation } }), recordsFor({ pkg, sources: [item] })));
    const revisionRecord = retainedRevision(created.content);
    const base = recordsFor({ pkg, revisions: [revisionRecord], snapshots: [created.snapshot!] });
    base.sources = [];
    expect(resolveRetainedGraphicRevision({ projectId, graphicId, revisionId }, base))
      .toMatchObject({ ok: false, block: { code: "GRAPHIC_PROVENANCE_UNAVAILABLE" } });

    base.sources = [{ ...retainedSource(item, "source one"), projectId: "10000000-0000-4000-8000-000000000002" }];
    expect(resolveRetainedGraphicRevision({ projectId, graphicId, revisionId }, base))
      .toMatchObject({ ok: false, block: { code: "GRAPHIC_PROVENANCE_UNAUTHORIZED" } });

    const badPackage = packageFixture("r1");
    badPackage.files[0]!.bytes = bytes("tampered entry");
    const wrongBytes = recordsFor({ pkg: badPackage, sources: [item], revisions: [revisionRecord], snapshots: [created.snapshot!] });
    expect(resolveRetainedGraphicRevision({ projectId, graphicId, revisionId }, wrongBytes))
      .toMatchObject({ ok: false, block: { code: "GRAPHIC_PROVENANCE_MISMATCH" } });
  });

  it("checks the retained canonical content hash as well as the exact revision tuple", () => {
    const pkg = packageFixture("r1");
    const item = source("tally", "40000000-0000-4000-8000-000000000001", "source one");
    const created = successful(createGraphicContent(
      input({ content: { kind: "derived", sources: [item], derivation: manualDerivation } }),
      recordsFor({ pkg, sources: [item] }),
    ));
    const wrongHash: RetainedGraphicRevisionRecord = {
      ...retainedRevision(created.content),
      contentHash: sha256Bytes(bytes("other content")),
    };
    expect(resolveRetainedGraphicRevision({ projectId, graphicId, revisionId }, recordsFor({
      pkg,
      sources: [item],
      revisions: [wrongHash],
      snapshots: [created.snapshot!],
    }))).toMatchObject({ ok: false, block: { code: "GRAPHIC_PROVENANCE_MISMATCH" } });
  });

  it("verifies the retained badge asset bytes against the #7 semantic snapshot", () => {
    const pkg = packageFixture("r1");
    const badgeBytes = bytes("badge asset bytes");
    const semanticWithBadge: GraphicProvenanceSemanticSnapshot = {
      values: { country: "otis", topLineOverride: "Fixture title", bottomLineOverride: "Fixture subtitle", badgeOverrideAssetId: "asset_fixture_badge" },
      badgeAsset: { assetId: "asset_fixture_badge", contentHash: sha256Bytes(badgeBytes) },
    };
    const records = recordsFor({ pkg });
    records.badges = [{ projectId, assetId: "asset_fixture_badge", contentHash: sha256Bytes(badgeBytes), bytes: badgeBytes }];
    const created = createGraphicContent(input({ semanticSnapshot: semanticWithBadge, content: { kind: "manual" } }), records);
    expect(created.ok).toBe(true);

    records.badges = [{ projectId, assetId: "asset_fixture_badge", contentHash: sha256Bytes(badgeBytes), bytes: bytes("different bytes") }];
    expect(createGraphicContent(input({ semanticSnapshot: semanticWithBadge, content: { kind: "manual" } }), records))
      .toMatchObject({ ok: false, block: { code: "GRAPHIC_PROVENANCE_MISMATCH" } });
  });

  it("refreshes from explicit new source bytes, preserves the template, and records both hashes", () => {
    const pkg = packageFixture("r1");
    const oldSource = source("tally", "40000000-0000-4000-8000-000000000001", "source one", "v1");
    const newSource = source("tally", "40000000-0000-4000-8000-000000000004", "source two", "v2");
    const originalInput = input({ content: { kind: "derived", sources: [oldSource], derivation: manualDerivation } });
    const originalInputBefore = canonicalJson(originalInput);
    const original = successful(createGraphicContent(originalInput, recordsFor({ pkg, sources: [oldSource] })));
    const originalContentBefore = canonicalJson(original.content);
    const originalSnapshotBefore = canonicalJson(original.snapshot);
    const oldRecord = retainedRevision(original.content);
    const records = recordsFor({ pkg, sources: [oldSource, newSource], revisions: [oldRecord], snapshots: [original.snapshot!] });
    const refreshInput = {
      projectId, graphicId, revisionId, newRevisionId: "30000000-0000-4000-8000-000000000002", semanticSnapshot,
      sources: [newSource], derivation: { ...manualDerivation, version: "2", note: "Reviewed the v2 source and retained the displayed total." },
      actorId: "actor-3", recordedAt: "2026-10-15T12:02:00.000Z",
    };
    const refreshInputBefore = canonicalJson(refreshInput);
    const refreshed = successful(refreshGraphicContent(refreshInput, records));

    expect(refreshed.content.template).toEqual(original.content.template);
    expect(refreshed.content.semanticSnapshotHash).toBe(original.content.semanticSnapshotHash);
    expect(refreshed.provenanceHash).not.toBe(original.provenanceHash);
    expect(refreshed.receipt).toMatchObject({ operation: "refresh", priorRevisionId: revisionId, priorContentHash: original.contentHash, newContentHash: refreshed.contentHash });
    expect(original.content.revisionId).toBe(revisionId);
    expect(original.snapshot?.sources[0]?.snapshot.contentHash).toBe(oldSource.snapshot.contentHash);
    expect(canonicalJson(originalInput)).toBe(originalInputBefore);
    expect(canonicalJson(refreshInput)).toBe(refreshInputBefore);
    expect(canonicalJson(original.content)).toBe(originalContentBefore);
    expect(canonicalJson(original.snapshot)).toBe(originalSnapshotBefore);
  });

  it("refreshes an explicit bottom-line change while leaving the prior revision untouched", () => {
    const pkg = packageFixture("r1");
    const oldSource = source("tally", "40000000-0000-4000-8000-000000000001", "source one", "v1");
    const newSource = source("tally", "40000000-0000-4000-8000-000000000004", "source two", "v2");
    const original = successful(createGraphicContent(input({
      content: { kind: "derived", sources: [oldSource], derivation: manualDerivation },
    }), recordsFor({ pkg, sources: [oldSource] })));
    const priorContent = canonicalJson(original.content);
    const priorSnapshot = canonicalJson(original.snapshot);
    const oldRecord = retainedRevision(original.content);
    const records = recordsFor({ pkg, sources: [oldSource, newSource], revisions: [oldRecord], snapshots: [original.snapshot!] });
    const changedSemantic: GraphicProvenanceSemanticSnapshot = {
      ...semanticSnapshot,
      values: { ...semanticSnapshot.values, bottomLineOverride: "Updated displayed total" },
    };
    const refreshed = successful(refreshGraphicContent({
      projectId, graphicId, revisionId, newRevisionId: "30000000-0000-4000-8000-000000000006", semanticSnapshot: changedSemantic,
      sources: [newSource], derivation: { ...manualDerivation, version: "2", note: "Apply the retained v2 total." },
      actorId: "actor-5", recordedAt: "2026-10-15T12:05:00.000Z",
    }, records));

    expect(refreshed.content.semanticSnapshot.values.bottomLineOverride).toBe("Updated displayed total");
    expect(refreshed.content.semanticSnapshotHash).not.toBe(original.content.semanticSnapshotHash);
    expect(refreshed.content.template).toEqual(original.content.template);
    expect(canonicalJson(original.content)).toBe(priorContent);
    expect(canonicalJson(original.snapshot)).toBe(priorSnapshot);
  });

  it("migrates a template pin while preserving source citations and derivation, and blocks incompatibility", () => {
    const oldPackage = packageFixture("r1");
    const newPackage = packageFixture("r2");
    const item = source("tally", "40000000-0000-4000-8000-000000000001", "source one");
    const original = successful(createGraphicContent(input({ content: { kind: "derived", sources: [item], derivation: manualDerivation } }), recordsFor({ pkg: oldPackage, sources: [item] })));
    const oldRecord = retainedRevision(original.content);
    const records = recordsFor({ pkg: oldPackage, sources: [item], revisions: [oldRecord], snapshots: [original.snapshot!] });
    records.templates = [...records.templates, { projectId, templateKey: "ev24-lower-third", projectRevisionId: "revision_2", compatible: true, package: newPackage }];
    const migrated = successful(migrateGraphicTemplate({
      projectId, graphicId, revisionId, newRevisionId: "30000000-0000-4000-8000-000000000003", template: pinFor(newPackage, "revision_2"),
      semanticSnapshot, actorId: "actor-4", recordedAt: "2026-10-15T12:03:00.000Z",
    }, records));

    expect(migrated.content.template).toEqual(pinFor(newPackage, "revision_2"));
    expect(migrated.snapshot?.sources).toEqual(original.snapshot?.sources);
    expect(migrated.snapshot?.derivation).toEqual(original.snapshot?.derivation);
    expect(migrated.provenanceHash).not.toBe(original.provenanceHash);
    expect(original.content.template).toEqual(pinFor(oldPackage));

    const changedSemantic: GraphicProvenanceSemanticSnapshot = {
      ...semanticSnapshot,
      values: { ...semanticSnapshot.values, topLineOverride: "Changed title" },
    };
    expect(migrateGraphicTemplate({
      projectId, graphicId, revisionId, newRevisionId: "30000000-0000-4000-8000-000000000005", template: pinFor(newPackage, "revision_2"),
      semanticSnapshot: changedSemantic, actorId: "actor-4", recordedAt: "2026-10-15T12:03:30.000Z",
    }, records)).toMatchObject({ ok: false, block: { code: "GRAPHIC_PROVENANCE_MISMATCH" } });
    expect(original.content.semanticSnapshot).toEqual(semanticSnapshot);

    const incompatible = recordsFor({ pkg: oldPackage, sources: [item], revisions: [oldRecord], snapshots: [original.snapshot!] });
    incompatible.templates = [...incompatible.templates, { projectId, templateKey: "ev24-lower-third", projectRevisionId: "revision_2", compatible: false, package: newPackage }];
    expect(migrateGraphicTemplate({
      projectId, graphicId, revisionId, newRevisionId: "30000000-0000-4000-8000-000000000004", template: pinFor(newPackage, "revision_2"),
      semanticSnapshot, actorId: "actor-4", recordedAt: "2026-10-15T12:04:00.000Z",
    }, incompatible)).toMatchObject({ ok: false, block: { code: "GRAPHIC_PROVENANCE_MISMATCH" } });
    expect(original.content.revisionId).toBe(revisionId);
  });

  it.each(["missing", "incompatible", "corrupt"])("recovers from a %s old template while verifying the target and preserved evidence", (oldState) => {
    const oldPackage = packageFixture("r1");
    const newPackage = packageFixture("r2");
    const item = source("tally", "40000000-0000-4000-8000-000000000001", "source one");
    const original = successful(createGraphicContent(input({ content: { kind: "derived", sources: [item], derivation: manualDerivation } }), recordsFor({ pkg: oldPackage, sources: [item] })));
    const records = recordsFor({ pkg: oldPackage, sources: [item], revisions: [retainedRevision(original.content)], snapshots: [original.snapshot!] });
    if (oldState === "missing") records.templates = [];
    else if (oldState === "incompatible") records.templates[0]!.compatible = false;
    else records.templates[0]!.package = newPackage;
    records.templates = [...records.templates, { projectId, templateKey: "ev24-lower-third", projectRevisionId: "revision_2", compatible: true, package: newPackage }];
    const migration = { projectId, graphicId, revisionId, newRevisionId: "30000000-0000-4000-8000-000000000003", template: pinFor(newPackage, "revision_2"), semanticSnapshot, actorId: "actor-4", recordedAt: "2026-10-15T12:03:00.000Z" };
    expect(resolveRetainedGraphicRevision({ projectId, graphicId, revisionId }, records).ok).toBe(false);
    const migrated = successful(migrateGraphicTemplate(migration, records));
    expect(migrated.snapshot?.sources).toEqual(original.snapshot?.sources);
    expect(migrated.receipt).toMatchObject({ priorRevisionId: revisionId, priorContentHash: original.contentHash, priorProvenanceHash: original.provenanceHash });
    expect(migrateGraphicTemplate(migration, { ...records, templates: [] }).ok).toBe(false);
    expect(migrateGraphicTemplate(migration, { ...records, sources: [] }).ok).toBe(false);
    expect(migrateGraphicTemplate(migration, { ...records, revisions: [{ ...retainedRevision(original.content), contentHash: sha256Bytes(bytes("wrong")) }] }).ok).toBe(false);
  });

  it("refreshes from verified new evidence when old source bytes are missing, retaining prior receipt identities", () => {
    const pkg = packageFixture("r1");
    const oldSource = source("tally", "40000000-0000-4000-8000-000000000001", "source one");
    const newSource = source("tally", "40000000-0000-4000-8000-000000000004", "new source");
    const original = successful(createGraphicContent(input({ content: { kind: "derived", sources: [oldSource], derivation: manualDerivation } }), recordsFor({ pkg, sources: [oldSource] })));
    const records = recordsFor({ pkg, sources: [newSource], revisions: [retainedRevision(original.content)], snapshots: [original.snapshot!] });
    const refresh = { projectId, graphicId, revisionId, newRevisionId: "30000000-0000-4000-8000-000000000003", semanticSnapshot, sources: [newSource], derivation: manualDerivation, actorId: "actor-4", recordedAt: "2026-10-15T12:03:00.000Z" };
    expect(repeatGraphicContent({ projectId, graphicId, revisionId, actorId: "actor-4", recordedAt: refresh.recordedAt }, records).ok).toBe(false);
    const refreshed = successful(refreshGraphicContent(refresh, records));
    expect(refreshed.snapshot?.sources).toEqual([newSource]);
    expect(refreshed.receipt).toMatchObject({ priorRevisionId: revisionId, priorContentHash: original.contentHash, priorProvenanceHash: original.provenanceHash });
    expect(refreshGraphicContent(refresh, { ...records, sources: [] }).ok).toBe(false);
  });

  it("refuses unsafe integer parameters before hashing without rejecting safe integers or fractions", () => {
    const pkg = packageFixture("r1");
    const item = source("tally", "40000000-0000-4000-8000-000000000001", "source one");
    const { derivation, retained } = methodDerivation();
    for (const value of [Number.MAX_SAFE_INTEGER + 1, Number.MIN_SAFE_INTEGER - 1]) {
      const candidate = input({ content: { kind: "derived", sources: [item], derivation: { ...derivation, parameters: { value } } } });
      expect(createGraphicContent(candidate, recordsFor({ pkg, sources: [item], methods: [retained] })).ok).toBe(false);
    }
    const candidate = input({ content: { kind: "derived", sources: [item], derivation: { ...derivation, parameters: { safe: Number.MAX_SAFE_INTEGER, fraction: 1.25 } } } });
    expect(createGraphicContent(candidate, recordsFor({ pkg, sources: [item], methods: [retained] })).ok).toBe(true);
  });

  it("requires deterministic method bytes for create and refresh without executing the method", () => {
    const pkg = packageFixture("r1");
    const item = source("tally", "40000000-0000-4000-8000-000000000001", "source one");
    const { derivation, retained } = methodDerivation();
    const candidate = input({ content: { kind: "derived", sources: [item], derivation } });
    expect(createGraphicContent(candidate, recordsFor({ pkg, sources: [item] })))
      .toMatchObject({ ok: false, block: { code: "GRAPHIC_PROVENANCE_UNAVAILABLE" } });
    expect(createGraphicContent(candidate, recordsFor({ pkg, sources: [item], methods: [{ ...retained, bytes: bytes("wrong method bytes") }] })))
      .toMatchObject({ ok: false, block: { code: "GRAPHIC_PROVENANCE_MISMATCH" } });
    expect(successful(createGraphicContent(candidate, recordsFor({ pkg, sources: [item], methods: [retained] }))).methodAvailable).toBe(true);
  });

  it("keeps parameter array order in P", () => {
    const item = source("tally", "40000000-0000-4000-8000-000000000001", "source one");
    const { derivation, retained } = methodDerivation();
    const first = successful(createGraphicContent(input({ content: { kind: "derived", sources: [item], derivation } }),
      recordsFor({ sources: [item], methods: [retained] })));
    const reordered = successful(createGraphicContent(input({ content: {
      kind: "derived",
      sources: [item],
      derivation: { ...derivation, parameters: { fields: ["west", "east"], rounding: null } },
    } }), recordsFor({ sources: [item], methods: [retained] })));
    expect(first.snapshot?.sources).toEqual(reordered.snapshot?.sources);
    expect(first.provenanceHash).not.toBe(reordered.provenanceHash);
  });

  it("rejects non-finite or non-JSON arrays, missing null fields, unknown fields, and duplicate source keys", () => {
    const one = source("tally", "40000000-0000-4000-8000-000000000001", "source one");
    const nonFinite = input({ content: { kind: "derived", sources: [one], derivation: { ...manualDerivation, parameters: { value: Number.NaN } } } });
    expect(createGraphicContent(nonFinite, recordsFor()))
      .toMatchObject({ ok: false, block: { code: "GRAPHIC_PROVENANCE_INCOMPLETE" } });

    const { derivation } = methodDerivation();
    const customArray = ["east", "west"];
    Object.defineProperty(customArray, "annotation", { value: "not JSON", enumerable: true });
    const customArrayInput = input({ content: { kind: "derived", sources: [one], derivation: {
      ...derivation, parameters: { fields: customArray },
    } } });
    expect(createGraphicContent(customArrayInput, recordsFor()))
      .toMatchObject({ ok: false, block: { code: "GRAPHIC_PROVENANCE_INCOMPLETE" } });

    const accessorArray = ["east", "west"];
    Object.defineProperty(accessorArray, "0", { get: () => "east", enumerable: true });
    const accessorInput = input({ content: { kind: "derived", sources: [one], derivation: {
      ...derivation, parameters: { fields: accessorArray },
    } } });
    expect(createGraphicContent(accessorInput, recordsFor()))
      .toMatchObject({ ok: false, block: { code: "GRAPHIC_PROVENANCE_INCOMPLETE" } });

    const duplicate = input({ content: { kind: "derived", sources: [one, { ...one }], derivation: manualDerivation } });
    expect(createGraphicContent(duplicate, recordsFor()))
      .toMatchObject({ ok: false, block: { code: "GRAPHIC_PROVENANCE_INCOMPLETE" } });

    const extra = { ...semanticSnapshot, invented: true } as unknown as typeof semanticSnapshot;
    expect(createGraphicContent(input({ semanticSnapshot: extra }), recordsFor()))
      .toMatchObject({ ok: false, block: { code: "GRAPHIC_PROVENANCE_UNEXPECTED" } });

    const missingNull = {
      values: { country: "otis", topLineOverride: "Fixture title", bottomLineOverride: "Fixture subtitle" },
      badgeAsset: null,
    } as unknown as GraphicProvenanceSemanticSnapshot;
    expect(createGraphicContent(input({ semanticSnapshot: missingNull }), recordsFor()))
      .toMatchObject({ ok: false, block: { code: "GRAPHIC_PROVENANCE_INCOMPLETE" } });

    expect(createGraphicContent(input({ graphicId: "not-an-entity-id" }), recordsFor()))
      .toMatchObject({ ok: false, block: { code: "GRAPHIC_PROVENANCE_MISMATCH" } });
  });
});
