import { createHash } from "node:crypto";

import { describe, expect, it } from "vitest";

import {
  TemplateLibraryService,
  type Actor,
  type ExternalTemplatePackage,
  type PackageManifest,
  type ProjectDefinition,
} from "../src/template-library.js";

const sourceA: ProjectDefinition = {
  id: "project-a",
  name: "Project A",
  suiteId: "suite-1",
  compatibility: ["resolve:21", "fusion"],
};

const sourceB: ProjectDefinition = {
  id: "project-b",
  name: "Project B",
  suiteId: "suite-1",
  compatibility: ["resolve:21", "fusion"],
};

function digest(bytes: Uint8Array): string {
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
}

function packageFixture(
  lineageKey: string,
  displayName: string,
  revision: string,
  allowedProjectIds: string[] = [sourceA.id, sourceB.id, "project-new"],
): ExternalTemplatePackage {
  const payload = new TextEncoder().encode(`${lineageKey}:${revision}:payload`);
  const preview = new TextEncoder().encode(`${lineageKey}:${revision}:preview`);
  const manifest: PackageManifest = {
    schemaVersion: "external-template-package/v1",
    packageKind: "graphic",
    externalLineageKey: lineageKey,
    displayName,
    externalRevisionLabel: revision,
    entryPoint: "template.bin",
    validator: { profile: "synthetic-graphic", version: "1" },
    compatibility: { requiredCapabilities: ["resolve:21", "fusion"] },
    provenance: {
      author: "Example Artist",
      publisher: "Example Studio",
      organization: "Example Org",
      sourceTool: "External Designer",
      sourceToolVersion: "4.2",
      sourceRevision: revision,
      createdAt: "2026-09-01T12:00:00.000Z",
      attestedBy: "producer@example.test",
    },
    rights: {
      allowedProjectIds,
      declarations: [
        {
          id: "template-rights",
          holder: "Example Studio",
          basis: "owned",
          embeddingAllowed: true,
          redistributionAllowed: true,
        },
      ],
    },
    files: [
      {
        path: "template.bin",
        byteLength: payload.byteLength,
        sha256: digest(payload),
        mediaType: "application/octet-stream",
        rightsId: "template-rights",
      },
      {
        path: "preview.png",
        byteLength: preview.byteLength,
        sha256: digest(preview),
        mediaType: "image/png",
        rightsId: "template-rights",
      },
    ],
  };
  return {
    transport: "zip",
    manifest,
    files: [
      { path: "template.bin", bytes: payload },
      { path: "preview.png", bytes: preview },
    ],
  };
}

function actor(
  id: string,
  grants: ReadonlyArray<readonly [Actor["grants"][number]["capability"], string]>,
): Actor {
  return {
    id,
    grants: grants.map(([capability, scope]) => ({ capability, scope })),
  };
}

function registryAdmin(...projectIds: string[]): Actor {
  return actor("registry-admin", [
    ["template:intake", "registry"],
    ["template:register", "registry"],
    ...projectIds.flatMap((projectId) => [
      ["project:member", projectId] as const,
      ["template:manage", projectId] as const,
      ["template:discover", projectId] as const,
      ["template:use", projectId] as const,
      ["template:copy-out", projectId] as const,
    ]),
    ["project:create", "suite-1"],
    ["template:manage", "project-new"],
    ["project:member", "project-new"],
    ["template:discover", "project-new"],
    ["template:use", "project-new"],
  ]);
}

function service(): TemplateLibraryService {
  return new TemplateLibraryService({
    projects: [sourceA, sourceB],
    validatorProfiles: [{ profile: "synthetic-graphic", version: "1" }],
  });
}

function register(
  library: TemplateLibraryService,
  principal: Actor,
  projectId: string,
  candidate: ExternalTemplatePackage,
) {
  const result = library.registerPackage({ actor: principal, projectId, package: candidate });
  expect(result.ok).toBe(true);
  if (!result.ok) throw new Error(result.report.issues.map((issue) => issue.code).join(", "));
  return result.value;
}

describe("issue #20 external template registration", () => {
  it("registers exact bytes atomically and exposes the revision only in its project", () => {
    const library = service();
    const admin = registryAdmin(sourceA.id, sourceB.id);
    const registered = register(library, admin, sourceA.id, packageFixture("lower-third", "Lower Third", "r1"));

    expect(registered.packageDigest).toMatch(/^sha256:[a-f0-9]{64}$/);
    expect(registered.projectRevision.packageDigest).toBe(registered.packageDigest);
    expect(library.listAvailableTemplates(admin, sourceA.id)).toEqual({
      ok: true,
      value: [expect.objectContaining({
        id: registered.projectRevision.id,
        displayName: "Lower Third",
        externalRevisionLabel: "r1",
        isCurrent: true,
      })],
    });
    expect(library.listAvailableTemplates(admin, sourceB.id)).toEqual({ ok: true, value: [] });
    expect(library.inspectCounts()).toEqual({ projects: 2, registeredRevisions: 1, templateItems: 1, projectRevisions: 1, uses: 0 });
  });

  it.each([
    ["malformed", (candidate: ExternalTemplatePackage) => { candidate.manifest.files[0]!.sha256 = "sha256:00"; }, "FILE_HASH_MISMATCH"],
    ["unlicensed", (candidate: ExternalTemplatePackage) => { candidate.manifest.files[0]!.rightsId = "missing-rights"; }, "RIGHTS_DECLARATION_MISSING"],
    ["incompatible", (candidate: ExternalTemplatePackage) => { candidate.manifest.compatibility.requiredCapabilities.push("resolve:99"); }, "TARGET_INCOMPATIBLE"],
  ])("rejects a %s package visibly without a partial registry or project entry", (_name, mutate, code) => {
    const library = service();
    const candidate = packageFixture("lower-third", "Lower Third", "r1");
    mutate(candidate);
    const result = library.registerPackage({ actor: registryAdmin(sourceA.id), projectId: sourceA.id, package: candidate });

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.report.issues).toEqual(expect.arrayContaining([expect.objectContaining({ code })]));
    expect(library.inspectCounts()).toEqual({ projects: 2, registeredRevisions: 0, templateItems: 0, projectRevisions: 0, uses: 0 });
  });

  it("reports duplicate package registration and does not create a second library entry", () => {
    const library = service();
    const admin = registryAdmin(sourceA.id, sourceB.id);
    const candidate = packageFixture("lower-third", "Lower Third", "r1");
    register(library, admin, sourceA.id, candidate);

    const duplicate = library.registerPackage({ actor: admin, projectId: sourceB.id, package: candidate });
    expect(duplicate.ok).toBe(false);
    if (duplicate.ok) return;
    expect(duplicate.report.issues).toEqual([expect.objectContaining({ code: "DUPLICATE_PACKAGE" })]);
    expect(library.inspectCounts().projectRevisions).toBe(1);
  });

  it("fails authorization before package validation or mutation", () => {
    const library = service();
    const malformed = packageFixture("lower-third", "Lower Third", "r1");
    malformed.manifest.files[0]!.sha256 = "sha256:00";
    const result = library.registerPackage({
      actor: actor("outsider", []),
      projectId: sourceA.id,
      package: malformed,
    });

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.report.issues.map((issue) => issue.code)).toEqual(["AUTHORIZATION_DENIED"]);
    expect(library.inspectCounts().registeredRevisions).toBe(0);
  });

  it("does not infer discovery access from a matching template name", () => {
    const library = service();
    const admin = registryAdmin(sourceA.id, sourceB.id);
    register(library, admin, sourceA.id, packageFixture("lineage-a", "Shared Name", "r1"));
    register(library, admin, sourceB.id, packageFixture("lineage-b", "Shared Name", "r1"));
    const onlyA = actor("project-a-viewer", [
      ["project:member", sourceA.id],
      ["template:discover", sourceA.id],
    ]);

    const aList = library.listAvailableTemplates(onlyA, sourceA.id);
    expect(aList.ok && aList.value).toHaveLength(1);
    const bList = library.listAvailableTemplates(onlyA, sourceB.id);
    expect(bList.ok).toBe(false);
    if (bList.ok) return;
    expect(bList.report.issues.map((item) => item.code)).toEqual(["AUTHORIZATION_DENIED"]);
  });
});

describe("issue #20 new-project immutable template copy", () => {
  it("creates a project with None and an explicit empty report", () => {
    const library = service();
    const result = library.createProjectWithTemplates({
      actor: registryAdmin(),
      project: { id: "project-new", name: "New Project", suiteId: "suite-1", compatibility: ["resolve:21", "fusion"] },
      selection: { mode: "none" },
      idempotencyKey: "create-none",
    });

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.value.projectId).toBe("project-new");
    expect(result.value.selectionMode).toBe("none");
    expect(result.value.selectionSnapshotHash).toMatch(/^sha256:[a-f0-9]{64}$/);
    expect(result.value.choices).toEqual([]);
    expect(library.inspectCounts().projects).toBe(3);
  });

  it("copies Some exact revisions as independent destination-owned snapshots", () => {
    const library = service();
    const admin = registryAdmin(sourceA.id);
    const first = register(library, admin, sourceA.id, packageFixture("lower-third", "Lower Third", "r1"));
    const second = register(library, admin, sourceA.id, packageFixture("callout", "Callout", "r3"));

    const result = library.createProjectWithTemplates({
      actor: admin,
      project: { id: "project-new", name: "New Project", suiteId: "suite-1", compatibility: ["resolve:21", "fusion"] },
      selection: { mode: "some", revisionIds: [first.projectRevision.id, second.projectRevision.id] },
      idempotencyKey: "create-some",
    });

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.value.choices).toEqual([
      expect.objectContaining({ sourceRevisionId: first.projectRevision.id, status: "copied", packageDigest: first.packageDigest }),
      expect.objectContaining({ sourceRevisionId: second.projectRevision.id, status: "copied", packageDigest: second.packageDigest }),
    ]);
    const destination = library.listAvailableTemplates(admin, "project-new");
    expect(destination.ok && destination.value).toHaveLength(2);
    if (!destination.ok) return;
    expect(destination.value.every((revision) => revision.projectId === "project-new")).toBe(true);
    expect(destination.value.map((revision) => revision.id)).not.toContain(first.projectRevision.id);
  });

  it("copies All as the current eligible exact set and reports exclusions", () => {
    const library = service();
    const admin = registryAdmin(sourceA.id);
    const first = register(library, admin, sourceA.id, packageFixture("lower-third", "Lower Third", "r1"));
    const old = register(library, admin, sourceA.id, packageFixture("callout", "Callout", "r1"));
    const current = register(library, admin, sourceA.id, packageFixture("callout", "Callout", "r2"));
    library.withdrawRegisteredRevision(admin, old.registeredRevisionId, "superseded package unavailable for new copy");

    const result = library.createProjectWithTemplates({
      actor: admin,
      project: { id: "project-new", name: "New Project", suiteId: "suite-1", compatibility: ["resolve:21", "fusion"] },
      selection: { mode: "all", sourceProjectIds: [sourceA.id] },
      idempotencyKey: "create-all",
    });

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.value.choices.filter((choice) => choice.status === "copied").map((choice) => choice.packageDigest)).toEqual([
      first.packageDigest,
      current.packageDigest,
    ]);
    expect(result.value.exclusions).toEqual([
      expect.objectContaining({ sourceRevisionId: old.projectRevision.id, status: "unavailable", code: "REVISION_WITHDRAWN" }),
    ]);
  });

  it("reports duplicate and unavailable Some choices and creates no project or association", () => {
    const library = service();
    const admin = registryAdmin(sourceA.id);
    const available = register(library, admin, sourceA.id, packageFixture("lower-third", "Lower Third", "r1"));
    const unavailable = register(library, admin, sourceA.id, packageFixture("callout", "Callout", "r1"));
    library.withdrawRegisteredRevision(admin, unavailable.registeredRevisionId, "withdrawn");
    const before = library.inspectCounts();

    const result = library.createProjectWithTemplates({
      actor: admin,
      project: { id: "project-new", name: "New Project", suiteId: "suite-1", compatibility: ["resolve:21", "fusion"] },
      selection: { mode: "some", revisionIds: [available.projectRevision.id, available.projectRevision.id, unavailable.projectRevision.id] },
      idempotencyKey: "create-blocked",
    });

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.report.issues).toEqual(expect.arrayContaining([
      expect.objectContaining({ code: "DUPLICATE_CHOICE", status: "duplicate" }),
      expect.objectContaining({ code: "REVISION_WITHDRAWN", status: "unavailable" }),
    ]));
    expect(library.inspectCounts()).toEqual(before);
    expect(library.hasProject("project-new")).toBe(false);
  });

  it("denies unauthorized source and destination combinations before creating a project", () => {
    const library = service();
    const admin = registryAdmin(sourceA.id);
    const registered = register(library, admin, sourceA.id, packageFixture("lower-third", "Lower Third", "r1"));
    const cannotCopy = actor("creator", [
      ["project:create", "suite-1"],
      ["template:manage", "project-new"],
      ["project:member", "project-new"],
    ]);

    const denied = library.createProjectWithTemplates({
      actor: cannotCopy,
      project: { id: "project-new", name: "New Project", suiteId: "suite-1", compatibility: ["resolve:21", "fusion"] },
      selection: { mode: "some", revisionIds: [registered.projectRevision.id] },
      idempotencyKey: "create-denied",
    });

    expect(denied.ok).toBe(false);
    if (denied.ok) return;
    expect(denied.report.issues).toEqual([
      expect.objectContaining({ code: "CHOICE_UNAVAILABLE_OR_UNAUTHORIZED", status: "unauthorized" }),
    ]);
    expect(library.hasProject("project-new")).toBe(false);
  });

  it("blocks cross-project copy when the package rights do not permit redistribution", () => {
    const library = service();
    const admin = registryAdmin(sourceA.id);
    const candidate = packageFixture("lower-third", "Lower Third", "r1");
    candidate.manifest.rights.declarations[0]!.redistributionAllowed = false;
    const registered = register(library, admin, sourceA.id, candidate);
    const before = library.inspectCounts();

    const denied = library.createProjectWithTemplates({
      actor: admin,
      project: { id: "project-new", name: "New Project", suiteId: "suite-1", compatibility: ["resolve:21", "fusion"] },
      selection: { mode: "some", revisionIds: [registered.projectRevision.id] },
      idempotencyKey: "create-rights-denied",
    });

    expect(denied.ok).toBe(false);
    if (denied.ok) return;
    expect(denied.report.issues).toEqual([
      expect.objectContaining({ code: "DESTINATION_RIGHTS_DENIED", status: "unauthorized" }),
    ]);
    expect(library.inspectCounts()).toEqual(before);
    expect(library.hasProject("project-new")).toBe(false);
  });

  it("returns the same logical project on an exact retry and rejects changed idempotency input", () => {
    const library = service();
    const admin = registryAdmin(sourceA.id);
    const registered = register(library, admin, sourceA.id, packageFixture("lower-third", "Lower Third", "r1"));
    const request = {
      actor: admin,
      project: { id: "project-new", name: "New Project", suiteId: "suite-1", compatibility: ["resolve:21", "fusion"] },
      selection: { mode: "some" as const, revisionIds: [registered.projectRevision.id] },
      idempotencyKey: "create-idempotent",
    };

    const first = library.createProjectWithTemplates(request);
    const counts = library.inspectCounts();
    expect(library.createProjectWithTemplates(request)).toEqual(first);
    expect(library.inspectCounts()).toEqual(counts);
    const changed = library.createProjectWithTemplates({ ...request, selection: { mode: "none" } });
    expect(changed.ok).toBe(false);
    if (changed.ok) return;
    expect(changed.report.issues[0]?.code).toBe("IDEMPOTENCY_KEY_REUSED");
  });

  it("keeps exact uses and copied snapshots reproducible after supersession, retirement, withdrawal, and source access loss", () => {
    const library = service();
    const admin = registryAdmin(sourceA.id);
    const r1 = register(library, admin, sourceA.id, packageFixture("lower-third", "Lower Third", "r1"));
    const use = library.createTemplateUse(admin, sourceA.id, r1.projectRevision.id, "sha256:resolved-r1");
    expect(use.ok).toBe(true);
    if (!use.ok) return;
    const copy = library.createProjectWithTemplates({
      actor: admin,
      project: { id: "project-new", name: "New Project", suiteId: "suite-1", compatibility: ["resolve:21", "fusion"] },
      selection: { mode: "some", revisionIds: [r1.projectRevision.id] },
      idempotencyKey: "create-retained",
    });
    expect(copy.ok).toBe(true);
    if (!copy.ok) return;
    const copiedRevisionId = copy.value.choices[0]!.destinationRevisionId!;

    register(library, admin, sourceA.id, packageFixture("lower-third", "Lower Third", "r2"));
    library.retireTemplateItem(admin, r1.projectRevision.templateItemId, "retired from new placements");
    library.withdrawRegisteredRevision(admin, r1.registeredRevisionId, "withdrawn from new copies");
    const destinationOnly = actor("destination-editor", [
      ["project:member", "project-new"],
      ["template:discover", "project-new"],
      ["template:use", "project-new"],
    ]);

    const resolved = library.resolveTemplateUse(admin, sourceA.id, use.value.id);
    expect(resolved.ok).toBe(true);
    if (!resolved.ok) return;
    expect(resolved.value).toMatchObject({
      projectRevisionId: r1.projectRevision.id,
      packageDigest: r1.packageDigest,
      resolvedSnapshotHash: "sha256:resolved-r1",
    });
    const destination = library.listAvailableTemplates(destinationOnly, "project-new");
    expect(destination.ok).toBe(true);
    if (!destination.ok) return;
    expect(destination.value).toEqual([
      expect.objectContaining({ id: copiedRevisionId, packageDigest: r1.packageDigest, projectId: "project-new" }),
    ]);
  });
});
