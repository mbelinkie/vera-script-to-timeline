import { describe, expect, it } from "vitest";

import {
  EV24_COUNTRY_IDS,
  assembleEv24Package,
  prepareEv24Values,
  registerEv24LowerThird,
  type Ev24Approval,
} from "../src/ev24-lower-third.js";
import { TemplateLibraryService, type Actor, type ProjectDefinition } from "../src/template-library.js";

const project: ProjectDefinition = {
  id: "ev24-approved-project",
  name: "EV24 approved project",
  suiteId: "vera",
  compatibility: ["fusion", "resolve-studio:21.1.0.0014"],
};
const otherProject: ProjectDefinition = {
  ...project,
  id: "other-project",
  name: "Other project",
};
const approval: Ev24Approval = {
  projectId: project.id,
  producerName: "Producer Example",
  brandApproved: true,
  packageDistributionApproved: true,
  fontUseApproved: true,
  settingRightsHolder: "Producer Example",
  atlasRightsHolder: "Producer Example",
  fontRightsBasis: "Producer-confirmed licensed use in Resolve",
};
const admin: Actor = {
  id: "approved-admin",
  grants: [
    { capability: "template:intake", scope: "registry" },
    { capability: "template:register", scope: "registry" },
    { capability: "project:member", scope: project.id },
    { capability: "template:manage", scope: project.id },
    { capability: "template:discover", scope: project.id },
  ],
};

function library(projects: ProjectDefinition[] = [project, otherProject]): TemplateLibraryService {
  return new TemplateLibraryService({
    projects,
    validatorProfiles: [{ profile: "ev24-lower-third", version: "1" }],
  });
}

function failureCodes(result: ReturnType<typeof registerEv24LowerThird>): string[] {
  expect(result.ok).toBe(false);
  return result.ok ? [] : result.report.issues.map((issue) => issue.code);
}

describe("issue #12 EV24 registration", () => {
  it("registers one exact three-file revision only in its approved project", () => {
    const service = library();
    const candidate = assembleEv24Package(approval);
    expect(candidate.manifest.files.map((file) => file.path).sort()).toEqual([
      "EV24 Lower Third.setting", "badge_override_test_only.png", "ev24_badges_atlas.png",
    ]);
    expect(candidate.manifest.ev24.graphFingerprint).toBe(candidate.manifest.files[0]!.sha256);
    expect(candidate.manifest.ev24.timing).toEqual({ entranceFrames: 48, exitFrames: 16, minimumFrames: 64, hold: "flexible" });
    expect(Object.keys(candidate.manifest.ev24.semanticControls).sort()).toEqual([
      "badgeOverrideAsset", "bottomLineOverride", "country", "topLineOverride", "year",
    ]);
    const result = registerEv24LowerThird(service, admin, project.id, approval, candidate);
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.value.packageDigest).toMatch(/^sha256:[a-f0-9]{64}$/);
    expect(result.value.registeredRevisionId).toMatch(/^registered_[a-f0-9]{24}$/);
    expect(result.value.projectRevision.id).toMatch(/^revision_[a-f0-9]{24}$/);
    expect(result.value.projectRevision.projectId).toBe(project.id);
    expect(result.value.projectRevision.packageDigest).toBe(result.value.packageDigest);
    expect(service.listAvailableTemplates(admin, project.id)).toEqual({
      ok: true,
      value: [expect.objectContaining({ id: result.value.projectRevision.id, packageDigest: result.value.packageDigest })],
    });
    expect(service.listAvailableTemplates({ ...admin, grants: [
      ...admin.grants,
      { capability: "project:member", scope: otherProject.id },
      { capability: "template:discover", scope: otherProject.id },
    ] }, otherProject.id)).toEqual({ ok: true, value: [] });
    expect(service.inspectCounts()).toEqual({ projects: 2, registeredRevisions: 1, templateItems: 1, projectRevisions: 1, uses: 0 });
    expect(failureCodes(registerEv24LowerThird(service, admin, project.id, approval, candidate))).toContain("DUPLICATE_PACKAGE");
    expect(service.inspectCounts().projectRevisions).toBe(1);
  });

  it.each([
    ["missing", (candidate: ReturnType<typeof assembleEv24Package>) => { candidate.files.pop(); }, "DECLARED_FILE_MISSING"],
    ["altered", (candidate: ReturnType<typeof assembleEv24Package>) => { candidate.files[0]!.bytes[0] = 0; }, "FILE_HASH_MISMATCH"],
    ["undeclared", (candidate: ReturnType<typeof assembleEv24Package>) => { candidate.files.push({ path: "extra.png", bytes: new Uint8Array([1]) }); }, "UNDECLARED_FILE"],
    ["wrong graph", (candidate: ReturnType<typeof assembleEv24Package>) => { candidate.manifest.ev24.graphFingerprint = "sha256:" + "0".repeat(64); }, "GRAPH_FINGERPRINT_MISMATCH"],
    ["absolute path", (candidate: ReturnType<typeof assembleEv24Package>) => { candidate.manifest.provenance.sourceRevision = "/Users/example/title.setting"; }, "MACHINE_PATH_FORBIDDEN"],
    ["unlicensed", (candidate: ReturnType<typeof assembleEv24Package>) => { candidate.manifest.rights.declarations[0]!.basis = ""; }, "RIGHTS_EVIDENCE_MISMATCH"],
    ["incompatible", (candidate: ReturnType<typeof assembleEv24Package>) => { candidate.manifest.compatibility.requiredCapabilities.push("resolve-studio:99"); }, "TARGET_INCOMPATIBLE"],
    ["false provenance", (candidate: ReturnType<typeof assembleEv24Package>) => { candidate.manifest.provenance.author = "Someone Else"; }, "PROVENANCE_MISMATCH"],
  ])("rejects %s input atomically", (_name, mutate, code) => {
    const service = library();
    const candidate = assembleEv24Package(approval);
    mutate(candidate);
    expect(failureCodes(registerEv24LowerThird(service, admin, project.id, approval, candidate))).toContain(code);
    expect(service.inspectCounts()).toEqual({ projects: 2, registeredRevisions: 0, templateItems: 0, projectRevisions: 0, uses: 0 });
  });

  it("requires explicit project, brand, distribution, and font approval", () => {
    const service = library();
    expect(failureCodes(registerEv24LowerThird(service, admin, project.id, { ...approval, brandApproved: false }))).toContain("PRODUCER_APPROVAL_MISSING");
    expect(failureCodes(registerEv24LowerThird(service, admin, project.id, { ...approval, packageDistributionApproved: false }))).toContain("PRODUCER_APPROVAL_MISSING");
    expect(failureCodes(registerEv24LowerThird(service, admin, project.id, { ...approval, fontUseApproved: false }))).toContain("PRODUCER_APPROVAL_MISSING");
    expect(failureCodes(registerEv24LowerThird(service, admin, otherProject.id, approval))).toContain("PROJECT_NOT_APPROVED");
    expect(service.inspectCounts().registeredRevisions).toBe(0);
  });

  it("pins the supplied Fusion graph, exposed mappings, atlas reference, and timing without rewriting it", () => {
    const candidate = assembleEv24Package(approval);
    const setting = new TextDecoder().decode(candidate.files[0]!.bytes);
    expect(setting).toContain("EV24LowerThird = MacroOperator {");
    expect(setting).toContain('SourceOp = "ControlHub",\nSource = "Country",\nName = "Country"');
    expect(setting).toContain('SourceOp = "ControlHub",\nSource = "Year",\nName = "Year"');
    expect(setting).toContain('SourceOp = "ControlHub",\nSource = "SongTitle",\nName = "Top Line"');
    expect(setting).toContain('SourceOp = "ControlHub",\nSource = "Singer",\nName = "Bottom Line"');
    expect(setting).toContain('SourceOp = "BadgeOverride",\nSource = "Clip",\nName = "Badge Override"');
    expect(setting).toContain("BadgeOverride = Loader {");
    expect(setting).toContain('Filename = "Templates:/Edit/Titles/Eurovision/ev24_badges_atlas.png"');
    expect(setting).toContain("InDuration = Input { Value = 48, }, OutDuration = Input { Value = 16, }");
    const authoredCountryIds = [...setting.matchAll(/CCS_AddString = "([^"]+)"/g)].map((match) =>
      match[1]!.replaceAll("&", "and").normalize("NFD").replace(/\p{M}/gu, "")
        .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""),
    );
    expect(authoredCountryIds).toEqual(EV24_COUNTRY_IDS);
    expect(setting).toContain('{ CCS_AddString = "Otis" }');
    expect(setting).not.toMatch(/\/Users\/|\/Volumes\/|file:\/\//);
  });

  it("prepares typed controls while leaving authored auto-fill in Fusion", () => {
    const ordinary = prepareEv24Values({ country: "north-macedonia", year: 2024 });
    expect(ordinary.snapshot).toEqual({ country: "north-macedonia", year: 2024 });
    expect(ordinary.controls).toEqual({ Country: 35, Year: 2024, TopLine: "", BottomLine: "" });
    const otis = prepareEv24Values({ country: "otis", topLineOverride: "Custom" });
    expect(otis.snapshot).toEqual({ country: "otis", topLineOverride: "Custom" });
    expect(otis.controls).toEqual({ Country: 53, TopLine: "Custom", BottomLine: "" });
    const badge = prepareEv24Values({ country: "malta", year: 2024, badgeOverrideAsset: "asset_badge123" });
    expect(badge.snapshot.badgeOverrideAsset).toBe("asset_badge123");
    expect(badge.controls).toEqual({ Country: 29, Year: 2024, TopLine: "", BottomLine: "", BadgeOverrideAsset: "asset_badge123" });
    expect(() => prepareEv24Values({ country: "malta" })).toThrow(/year/i);
    expect(() => prepareEv24Values({ country: "otis", year: 2024 })).toThrow(/otis/i);
    expect(() => prepareEv24Values({ country: "malta", year: 2024, badgeOverrideAsset: "/tmp/badge.png" })).toThrow(/asset identity/i);
  });
});
