import { readFileSync } from "node:fs";

import {
  sha256Bytes,
  TemplateLibraryService,
  type Actor,
  type ExternalTemplatePackage,
  type PackageManifest,
  type RegistrationValue,
  type ServiceResult,
} from "./template-library.js";

const SETTING = "EV24 Lower Third.setting";
const ATLAS = "ev24_badges_atlas.png";
const TEST_BADGE = "badge_override_test_only.png";
export const EV24_SETTING_HASH = "sha256:7abb4e07a3c6472fd93e6b752a8623855f2fa03a8591fff10e6e33746e7ff2df";
const SETTING_HASH = EV24_SETTING_HASH;
const ATLAS_HASH = "sha256:008cea751e3d18a15436fe5701755c0fd7a3a023f1b7f5c585f9796007c766fd";
const TEST_BADGE_HASH = "sha256:a631b15479a795f0f614b7681d9210dac74bd2583b311f8c8861682543a58003";

// These are VERA identities. The ordinal is used only at the trusted Fusion boundary.
export const EV24_COUNTRY_IDS = [
  "albania", "andorra", "armenia", "australia", "austria", "azerbaijan",
  "belarus", "belgium", "bosnia-and-herzegovina", "bulgaria", "canada",
  "croatia", "cyprus", "czechia", "denmark", "estonia", "finland", "france",
  "georgia", "germany", "greece", "hungary", "iceland", "ireland", "israel",
  "italy", "latvia", "lithuania", "luxembourg", "malta", "moldova", "monaco",
  "montenegro", "morocco", "netherlands", "north-macedonia", "norway",
  "poland", "portugal", "romania", "russia", "san-marino", "serbia",
  "serbia-and-montenegro", "slovakia", "slovenia", "spain", "sweden",
  "switzerland", "turkiye", "ukraine", "united-kingdom", "yugoslavia", "otis",
] as const;

export type Ev24Country = typeof EV24_COUNTRY_IDS[number];

export interface Ev24Approval {
  projectId: string;
  producerName: string;
  brandApproved: boolean;
  packageDistributionApproved: boolean;
  fontUseApproved: boolean;
  settingRightsHolder: string;
  atlasRightsHolder: string;
  fontRightsBasis: string;
}

const EV24_PROFILE = {
  graphFingerprint: SETTING_HASH,
  rootOperator: "EV24LowerThird",
  semanticControls: {
    country: { tool: "ControlHub", input: "Country", exposed: "Country" },
    year: { tool: "ControlHub", input: "Year", exposed: "Year" },
    topLineOverride: { tool: "ControlHub", input: "SongTitle", exposed: "TopLine" },
    bottomLineOverride: { tool: "ControlHub", input: "Singer", exposed: "BottomLine" },
    badgeOverrideAsset: { tool: "BadgeOverride", input: "Clip", exposed: "BadgeOverride" },
  },
  countryIds: EV24_COUNTRY_IDS,
  timing: { entranceFrames: 48, exitFrames: 16, minimumFrames: 64, hold: "flexible" },
  atlasReference: "Templates:/Edit/Titles/Eurovision/ev24_badges_atlas.png",
  requiredFonts: [
    { family: "ITC Franklin Gothic LT Pro", style: "SemiBold ExtraCondensed", bundled: false },
    { family: "ITC Franklin Gothic LT Pro", style: "UltraCondensed", bundled: false },
  ],
  testBadgeProductionUse: false,
} as const;

export interface Ev24Manifest extends PackageManifest {
  ev24: Omit<typeof EV24_PROFILE, "graphFingerprint"> & { graphFingerprint: string };
  fontRightsBasis: string;
}

export interface Ev24Package extends ExternalTemplatePackage {
  manifest: Ev24Manifest;
}

function packageBytes(name: string): Uint8Array {
  return readFileSync(new URL(`../assets/ev24-lower-third/${name}`, import.meta.url));
}

export function assembleEv24Package(approval: Ev24Approval): Ev24Package {
  const files = [SETTING, ATLAS, TEST_BADGE].map((path) => ({ path, bytes: packageBytes(path) }));
  const manifest: Ev24Manifest = {
    schemaVersion: "external-template-package/v1",
    packageKind: "graphic",
    externalLineageKey: "ev24-lower-third",
    displayName: "EV24 Lower Third",
    externalRevisionLabel: "ev24-producer-supplied-2026-09-21",
    entryPoint: SETTING,
    validator: { profile: "ev24-lower-third", version: "1" },
    compatibility: { requiredCapabilities: ["fusion", "resolve-studio:21.1.0.0014"] },
    provenance: {
      author: approval.producerName,
      publisher: approval.producerName,
      organization: "VERA",
      sourceTool: "DaVinci Resolve Studio",
      sourceToolVersion: "21.1.0.0014",
      sourceRevision: SETTING_HASH,
      createdAt: "2026-09-21",
      attestedBy: approval.producerName,
    },
    rights: {
      allowedProjectIds: [approval.projectId],
      declarations: [
        { id: "setting", holder: approval.settingRightsHolder, basis: "Producer-authorized project use and package distribution", embeddingAllowed: true, redistributionAllowed: false },
        { id: "atlas", holder: approval.atlasRightsHolder, basis: "Producer-authorized project use and package distribution", embeddingAllowed: true, redistributionAllowed: false },
        { id: "test-badge", holder: approval.producerName, basis: "Generated non-production validation art", embeddingAllowed: true, redistributionAllowed: false },
      ],
    },
    files: [
      { path: SETTING, byteLength: 210902, sha256: SETTING_HASH, mediaType: "application/vnd.blackmagic.fusion-setting", rightsId: "setting" },
      { path: ATLAS, byteLength: 2305230, sha256: ATLAS_HASH, mediaType: "image/png", rightsId: "atlas" },
      { path: TEST_BADGE, byteLength: 185, sha256: TEST_BADGE_HASH, mediaType: "image/png", rightsId: "test-badge" },
    ],
    ev24: structuredClone(EV24_PROFILE),
    fontRightsBasis: approval.fontRightsBasis,
  };
  return { transport: "directory", manifest, files };
}

function failed(code: string, message: string): ServiceResult<RegistrationValue> {
  return { ok: false, report: { operation: "register_package", status: "failed", issues: [{ code, message, status: "failed" }] } };
}

function isPathLike(value: string): boolean {
  return /(?:\/Users\/|\/Volumes\/|\/tmp\/|\/home\/|\/private\/|file:\/\/|[a-zA-Z]:\\|~\/)/.test(value);
}

export function registerEv24LowerThird(
  library: TemplateLibraryService,
  actor: Actor,
  projectId: string,
  approval: Ev24Approval,
  candidate: Ev24Package = assembleEv24Package(approval),
): ServiceResult<RegistrationValue> {
  if (projectId !== approval.projectId || !/^[A-Za-z0-9][A-Za-z0-9_-]*$/.test(projectId)) {
    return failed("PROJECT_NOT_APPROVED", "The destination is not the Producer-approved project.");
  }
  if (!approval.brandApproved || !approval.packageDistributionApproved || !approval.fontUseApproved ||
      ![approval.producerName, approval.settingRightsHolder, approval.atlasRightsHolder, approval.fontRightsBasis]
        .every((value) => typeof value === "string" && value.trim().length > 0)) {
    return failed("PRODUCER_APPROVAL_MISSING", "Brand, package distribution, asset, and font rights need explicit Producer approval.");
  }
  if (candidate?.manifest == null || !Array.isArray(candidate.files) || candidate.manifest.ev24 == null ||
      candidate.files.some((file) => file == null || typeof file.path !== "string" || !(file.bytes instanceof Uint8Array))) {
    return failed("PACKAGE_MALFORMED", "The EV24 package envelope is malformed.");
  }
  if (isPathLike(JSON.stringify(candidate.manifest)) || candidate.files.some((file) => isPathLike(file.path))) {
    return failed("MACHINE_PATH_FORBIDDEN", "Package metadata must not contain machine-specific paths.");
  }
  if (candidate.manifest.ev24.graphFingerprint !== SETTING_HASH) {
    return failed("GRAPH_FINGERPRINT_MISMATCH", "The declared Fusion graph fingerprint differs from the pinned revision.");
  }
  if (JSON.stringify(candidate.manifest.ev24) !== JSON.stringify(EV24_PROFILE)) {
    return failed("EV24_PROFILE_MISMATCH", "The pinned controls, country identities, timing, or font requirements differ.");
  }
  const expected = assembleEv24Package(approval).manifest;
  if (JSON.stringify(Object.keys(candidate.manifest).sort()) !== JSON.stringify(Object.keys(expected).sort()) ||
      candidate.transport !== "directory") {
    return failed("PACKAGE_IDENTITY_MISMATCH", "The package envelope differs from the pinned revision.");
  }
  if (JSON.stringify(candidate.manifest.compatibility) !== JSON.stringify(expected.compatibility)) {
    return failed("TARGET_INCOMPATIBLE", "The package compatibility profile differs from the validated Resolve baseline.");
  }
  if (JSON.stringify(candidate.manifest.rights) !== JSON.stringify(expected.rights) ||
      candidate.manifest.fontRightsBasis !== expected.fontRightsBasis) {
    return failed("RIGHTS_EVIDENCE_MISMATCH", "Rights evidence must match the Producer declaration for the approved project.");
  }
  if (JSON.stringify(candidate.manifest.provenance) !== JSON.stringify(expected.provenance)) {
    return failed("PROVENANCE_MISMATCH", "Package provenance differs from the approved source declaration.");
  }
  for (const key of ["schemaVersion", "packageKind", "externalLineageKey", "displayName", "externalRevisionLabel", "entryPoint", "validator"] as const) {
    if (JSON.stringify(candidate.manifest[key]) !== JSON.stringify(expected[key])) {
      return failed("PACKAGE_IDENTITY_MISMATCH", "The package identity or validator profile differs from the pinned revision.");
    }
  }
  if (JSON.stringify(candidate.manifest.files) !== JSON.stringify(expected.files)) {
    return failed("FILE_DECLARATION_MISMATCH", "Declared file names, sizes, and hashes must match the pinned package.");
  }
  const expectedFiles = new Map([[SETTING, SETTING_HASH], [ATLAS, ATLAS_HASH], [TEST_BADGE, TEST_BADGE_HASH]]);
  for (const file of candidate.files) {
    const expected = expectedFiles.get(file.path);
    if (expected !== undefined && sha256Bytes(file.bytes) !== expected) {
      return failed("FILE_HASH_MISMATCH", `The pinned package file ${file.path} differs from the supplied bytes.`);
    }
  }
  return library.registerPackage({ actor, projectId, package: candidate });
}

export interface Ev24SemanticValues {
  country: Ev24Country;
  year?: number;
  topLineOverride?: string;
  bottomLineOverride?: string;
  badgeOverrideAsset?: string;
}

export function prepareEv24Values(values: Ev24SemanticValues): {
  snapshot: Ev24SemanticValues;
  controls: { Country: number; Year?: number; TopLine: string; BottomLine: string; BadgeOverrideAsset?: string };
} {
  const countryIndex = EV24_COUNTRY_IDS.indexOf(values.country);
  if (countryIndex < 0) throw new TypeError("Unknown stable country identity.");
  if (values.country === "otis" && values.year !== undefined) throw new TypeError("otis omits year from the semantic snapshot.");
  if (values.country !== "otis" && (!Number.isInteger(values.year) || (values.year ?? 0) < 1)) {
    throw new TypeError("A positive integer year is required for this country.");
  }
  if (values.badgeOverrideAsset !== undefined && !/^asset_[A-Za-z0-9_-]+$/.test(values.badgeOverrideAsset)) {
    throw new TypeError("Badge override must be a project asset identity.");
  }
  for (const value of [values.topLineOverride, values.bottomLineOverride]) {
    if (value !== undefined && typeof value !== "string") throw new TypeError("Text overrides must be strings.");
  }
  const snapshot: Ev24SemanticValues = {
    country: values.country,
    ...(values.year === undefined ? {} : { year: values.year }),
    ...(values.topLineOverride === undefined ? {} : { topLineOverride: values.topLineOverride }),
    ...(values.bottomLineOverride === undefined ? {} : { bottomLineOverride: values.bottomLineOverride }),
    ...(values.badgeOverrideAsset === undefined ? {} : { badgeOverrideAsset: values.badgeOverrideAsset }),
  };
  const controls = {
    Country: countryIndex,
    ...(values.year === undefined ? {} : { Year: values.year }),
    TopLine: values.topLineOverride ?? "",
    BottomLine: values.bottomLineOverride ?? "",
    ...(values.badgeOverrideAsset === undefined ? {} : { BadgeOverrideAsset: values.badgeOverrideAsset }),
  };
  return { snapshot, controls };
}
