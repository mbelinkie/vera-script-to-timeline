import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import type { AuthorizationDecisionRef, PrincipalRef } from "@vera/contracts";
import type { ScriptDocumentV2 } from "@vera/contracts/v2";
import { validateScriptDocumentV2 } from "@vera/contracts/authoring-v2";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PNG } from "pngjs";

/* eslint-disable @typescript-eslint/require-await -- Async fakes match the service's asynchronous authorization ports. */

import { inspectPublicUrl } from "../src/policy.js";
import { preparePublicWebpageVisuals, ProjectWebpageStillStore, type WebpagePrepMediaOptions } from "../src/prep-media.js";
import { intakeSuppliedPicture, ProjectSuppliedPictureStore } from "../src/supplied-picture.js";
import { CAPTURE_PROFILE_V2 } from "../src/profile.js";

const PROJECT = "00000000-0000-4000-8000-000000000002";
const CAPTURE = "22222222-2222-4222-8222-222222222222";
const REVISION = "33333333-3333-4333-8333-333333333334";
const ARTIFACT = "44444444-4444-4444-8444-444444444444";
const PAGE_URL = "https://www.example.org/articles/vera?edition=1";
const ACTOR: PrincipalRef = { principalKind: "user", principalId: "55555555-5555-4555-8555-555555555555" };
const raster = PNG.sync.write(new PNG({ width: 2, height: 2 }));
const hash = (value: string | Buffer): string => `sha256:${createHash("sha256").update(value).digest("hex")}`;
const directories: string[] = [];

async function root(): Promise<string> {
  const value = await mkdtemp(join(tmpdir(), "vera-394-"));
  directories.push(value);
  return value;
}

afterEach(async () => {
  vi.restoreAllMocks();
  for (const path of directories.splice(0)) await rm(path, { recursive: true, force: true });
});

async function authored(url = PAGE_URL): Promise<ScriptDocumentV2> {
  const source = JSON.parse(await readFile(new URL("../../../tests/data/authoring_v2/issue_173/compiler/visual-only-capture-still-25fps-default.input.golden.json", import.meta.url), "utf8")) as { document: ScriptDocumentV2 };
  const block = source.document.activeDraft.blocks[0];
  if (!block || block.type !== "visual_only") throw new Error("expected visual-only fixture");
  block.payload.source = { kind: "url", url };
  block.visualOnlyTiming.durationOverrideMs = 6250;
  expect(validateScriptDocumentV2(source.document).valid).toBe(true);
  return source.document;
}

class FakeCaptureService {
  jobState: "queued" | "committed_ready" | "committed_review_required" | "failed" = "committed_ready";
  readAllowed = true;
  revisionStatus: "ready" | "review_required" = "ready";
  revisionProjectId = PROJECT;
  profileVersion: number = CAPTURE_PROFILE_V2.profileVersion;
  rasterBytes = raster;
  artifactDigest = hash(raster);
  readonly selected = new Set<string>();
  readonly create = vi.fn(async (request: { requestedUrl: string; projectId: string; idempotencyKey: string }) => {
    expect(request.projectId).toBe(PROJECT);
    expect(request.requestedUrl).toBe(inspectPublicUrl(PAGE_URL).canonicalUrl);
    return { capture: { captureId: CAPTURE } };
  });
  readonly capture = vi.fn(async () => ({ capture: {
    captureId: CAPTURE, projectId: PROJECT, lifecycle: "active", rowVersion: 1,
    configuration: { requestedUrl: { canonicalDigest: hash(inspectPublicUrl(PAGE_URL).canonicalUrl) },
      captureProfileId: CAPTURE_PROFILE_V2.profileId, captureProfileVersion: this.profileVersion },
  } }));
  readonly job = vi.fn(async () => ({ job: {
    captureId: CAPTURE, state: this.jobState, outputRevisionId: this.jobState.startsWith("committed") ? REVISION : null,
  } }));
  readonly revision = vi.fn(async () => ({ revision: {
    projectId: this.revisionProjectId, captureId: CAPTURE, revisionId: REVISION, status: this.revisionStatus,
    artifact: { projectId: PROJECT, artifactId: ARTIFACT, kind: "capture_raster", mimeType: "image/png",
      accessClass: "project_visual", width: 2, height: 2, digest: this.artifactDigest, byteLength: raster.byteLength },
  } }));
  readonly select = vi.fn(async (request: { target: { occurrenceId: string; resourceVersionDigest: string }; revisionId: string }) => {
    if (request.revisionId !== REVISION || this.revisionStatus !== "ready") throw new Error("not selectable");
    this.selected.add(`${request.target.occurrenceId}:${request.target.resourceVersionDigest}`);
    return { effectId: "selected", duplicateDelivery: false, recordedAt: "2026-11-16T00:00:00Z" };
  });
  readonly readRaster = vi.fn(async (_projectId: string, _revisionId: string, reference: { projectId: string; occurrenceId: string; resourceVersionDigest: string }) => {
    if (!this.readAllowed) throw new Error("authorization denied");
    expect(reference.projectId).toBe(PROJECT);
    expect(this.selected.has(`${reference.occurrenceId}:${reference.resourceVersionDigest}`)).toBe(true);
    return { bytes: this.rasterBytes, descriptor: {
      artifactId: ARTIFACT, digest: this.artifactDigest, byteLength: raster.byteLength,
    } };
  });

  get port(): WebpagePrepMediaOptions["service"] {
    return { createCapture: this.create, getCapture: this.capture, requestCaptureJob: this.job,
      getRevision: this.revision, selectRevision: this.select,
      readRasterArtifact: this.readRaster } as unknown as WebpagePrepMediaOptions["service"];
  }
}

function options(projectRoot: string, service: FakeCaptureService, document: ScriptDocumentV2): WebpagePrepMediaOptions {
  const block = document.activeDraft.blocks[0];
  if (!block || block.type !== "visual_only") throw new Error("expected visual-only fixture");
  return { projectId: PROJECT, projectRoot, principal: ACTOR, service: service.port,
    reference: { kind: "draft_occurrence", projectId: PROJECT, resourceId: document.id,
      resourceVersionDigest: document.liveContentHash, occurrenceId: block.payload.payloadId } };
}

describe("#394 public webpage capture for Prep Media", () => {
  it("projects an authorized, verified still with the original row length and preserves the authored URL", async () => {
    const document = await authored();
    const service = new FakeCaptureService();
    const result = await preparePublicWebpageVisuals(document, options(await root(), service, document));
    expect(result.captures).toHaveLength(1);
    expect(result.captures[0]).toMatchObject({ status: "ready", captureId: CAPTURE, revisionId: REVISION, artifactDigest: hash(raster) });
    expect(await readFile(result.captures[0]!.rasterPath!)).toEqual(raster);
    expect(result.document.activeDraft.blocks[0]).toMatchObject({
      type: "visual_only", visualOnlyTiming: { durationOverrideMs: 6250 },
      payload: { pictureKind: "capture", source: { kind: "capture_revision", captureId: CAPTURE, revisionId: REVISION } },
    });
    expect(document.activeDraft.blocks[0]).toMatchObject({ payload: { source: { kind: "url", url: PAGE_URL } } });
    expect(validateScriptDocumentV2(result.document).valid).toBe(true);
    expect(service.create).toHaveBeenCalledTimes(1);
    expect(service.job).toHaveBeenCalledTimes(1);
    expect(service.readRaster).toHaveBeenCalledTimes(1);
    expect(service.select).toHaveBeenCalledTimes(1);
  });

  it("rebuilds from a disk-stored pinned revision without a new capture/job, and reauthorizes use", async () => {
    const document = await authored();
    const service = new FakeCaptureService();
    const projectRoot = await root();
    const first = await preparePublicWebpageVisuals(document, options(projectRoot, service, document));
    // The receipt format predates profile v2. Old project pins remain readable.
    service.profileVersion = 1;
    const second = await preparePublicWebpageVisuals(document, options(projectRoot, service, document));
    expect(second.captures[0]).toMatchObject({ status: "reused", revisionId: REVISION,
      rasterPath: first.captures[0]!.rasterPath });
    expect(service.create).toHaveBeenCalledTimes(1);
    expect(service.job).toHaveBeenCalledTimes(1);
    expect(service.revision).toHaveBeenCalledTimes(2);
    expect(service.readRaster).toHaveBeenCalledTimes(2);
    expect(service.select).toHaveBeenCalledTimes(2);
    service.readAllowed = false;
    await expect(preparePublicWebpageVisuals(document, options(projectRoot, service, document)))
      .rejects.toThrow("authorization denied");
  });

  it("selects a shared cached capture separately for each authored occurrence", async () => {
    const document = await authored();
    const first = document.activeDraft.blocks[0];
    if (!first || first.type !== "visual_only") throw new Error("expected visual-only fixture");
    const second = structuredClone(first);
    second.id = "66666666-6666-4666-8666-666666666666";
    second.payload.payloadId = "77777777-7777-4777-8777-777777777777";
    second.orderKey = "b0";
    document.activeDraft.blocks.push(second);
    expect(validateScriptDocumentV2(document).valid).toBe(true);
    const service = new FakeCaptureService();
    const output = await preparePublicWebpageVisuals(document, options(await root(), service, document));
    expect(output.captures.map((row) => row.status)).toEqual(["ready", "reused"]);
    expect(service.create).toHaveBeenCalledTimes(1);
    expect(service.job).toHaveBeenCalledTimes(1);
    expect(service.select).toHaveBeenCalledTimes(2);
    expect(service.readRaster).toHaveBeenCalledTimes(2);
    expect(service.selected.size).toBe(2);
    expect(output.document.activeDraft.blocks[1]).toMatchObject({
      visualOnlyTiming: { durationOverrideMs: 6250 },
      payload: { source: { kind: "capture_revision", captureId: CAPTURE, revisionId: REVISION } },
    });
  });

  it("reports capture failures by redacted page name and builds a visible placeholder without changing timing", async () => {
    const document = await authored();
    const service = new FakeCaptureService();
    service.jobState = "failed";
    const result = await preparePublicWebpageVisuals(document, options(await root(), service, document));
    expect(result.captures[0]).toMatchObject({ status: "failed", label: "https://www.example.org/articles/vera?edition=%5BREDACTED%5D",
      reason: "Webpage capture failed", rasterPath: null });
    expect(result.document.activeDraft.blocks[0]).toMatchObject({
      visualOnlyTiming: { durationOverrideMs: 6250 },
      payload: { pictureKind: "intentional_placeholder", source: { kind: "intentional_placeholder" } },
    });
    expect(validateScriptDocumentV2(result.document).valid).toBe(true);
  });

  it.each(["queued", "committed_review_required"] as const)("does not treat %s as a verified capture", async (status) => {
    const document = await authored();
    const service = new FakeCaptureService();
    service.jobState = status;
    const result = await preparePublicWebpageVisuals(document, options(await root(), service, document));
    expect(result.captures[0]?.status).toBe(status === "queued" ? "pending" : "review_required");
    expect(result.captures[0]?.rasterPath).toBeNull();
    expect(result.document.activeDraft.blocks[0]).toMatchObject({ payload: { pictureKind: "intentional_placeholder" } });
  });

  it("refuses forbidden URLs before contacting the capture service, without exposing credential text", async () => {
    const document = await authored("http://localhost/admin?token=veryprivate");
    const service = new FakeCaptureService();
    const result = await preparePublicWebpageVisuals(document, options(await root(), service, document));
    expect(result.captures[0]).toMatchObject({ status: "failed", label: "Blocked webpage" });
    expect(JSON.stringify(result)).not.toContain("veryprivate");
    expect(service.create).not.toHaveBeenCalled();
    expect(service.job).not.toHaveBeenCalled();
    expect(validateScriptDocumentV2(result.document).valid).toBe(true);
  });

  it("refuses wrong-project references, inconsistent revisions, and mismatched raster bytes", async () => {
    const document = await authored();
    const projectRoot = await root();
    const service = new FakeCaptureService();
    await expect(preparePublicWebpageVisuals(document, { ...options(projectRoot, service, document), projectId: "other" }))
      .rejects.toThrow("frozen project");
    service.revisionProjectId = "different";
    await expect(preparePublicWebpageVisuals(document, options(projectRoot, service, document)))
      .rejects.toThrow("provenance mismatch");
    service.revisionProjectId = PROJECT;
    service.rasterBytes = Buffer.from("forged image");
    await expect(preparePublicWebpageVisuals(document, options(projectRoot, service, document)))
      .rejects.toThrow("raster does not match");
  });

  it("refuses a reference to a different frozen document version before contacting the service", async () => {
    const document = await authored();
    const service = new FakeCaptureService();
    const valid = options(await root(), service, document);
    await expect(preparePublicWebpageVisuals(document, {
      ...valid,
      reference: { ...valid.reference, resourceVersionDigest: hash("stale content") },
    })).rejects.toThrow("frozen project");
    expect(service.create).not.toHaveBeenCalled();
  });

  it("detects tampering with cached bytes and never silently recaptures", async () => {
    const document = await authored();
    const projectRoot = await root();
    const service = new FakeCaptureService();
    const result = await preparePublicWebpageVisuals(document, options(projectRoot, service, document));
    // Mutate bytes without changing length so this specifically protects
    // the digest check, not merely the file-size check.
    await writeFile(result.captures[0]!.rasterPath!, Buffer.alloc(raster.byteLength, 0x41));
    await expect(preparePublicWebpageVisuals(document, options(projectRoot, service, document)))
      .rejects.toThrow("immutable byte verification");
    expect(service.job).toHaveBeenCalledTimes(1);
  });

  it("does not reuse a different project's receipt", async () => {
    const projectRoot = await root();
    const store = new ProjectWebpageStillStore(projectRoot);
    const document = await authored();
    const service = new FakeCaptureService();
    await preparePublicWebpageVisuals(document, options(projectRoot, service, document));
    await expect(store.read("another-project", hash(inspectPublicUrl(PAGE_URL).canonicalUrl)))
      .rejects.toThrow("invalid webpage still receipt");
  });
});

it("prepares a pinned extension passage after recapture without requesting a public job", async () => {
  const projectRoot = await root();
  const document = await authored();
  const block = document.activeDraft.blocks[0];
  if (block?.type !== "visual_only") throw new Error("expected visual fixture");
  const service = new FakeCaptureService();
  const prep = options(projectRoot, service, document);
  const store = new ProjectSuppliedPictureStore(projectRoot);
  const authorization = { authorize: async (projectId: string, principal: PrincipalRef, action: string): Promise<AuthorizationDecisionRef> => ({
    projectId, principal, action, role: "editor", decisionId: "55555555-5555-4555-8555-555555555556",
    membershipVersion: 1, decidedAt: "2026-11-18T12:00:00Z", recheckMode: "every_request",
  }) };
  const references = { validate: vi.fn(async () => undefined), validatePicturePin: vi.fn(async () => undefined) };
  const upload = { projectId: PROJECT, principal: ACTOR, store, authorization, references,
    reference: { ...prep.reference, resourceVersionDigest: hash("before placement") },
    pictureKind: "passage" as const, bytes: raster, highlightRects: [{ x: 0, y: 1, width: 2, height: 1 }] };
  const first = await intakeSuppliedPicture(upload);
  const { captureId, revisionId } = first.metadata;
  const recapture = await intakeSuppliedPicture({ ...upload, captureId });
  expect(recapture.metadata.revisionId).not.toBe(revisionId);
  block.payload.source = { kind: "capture_revision", captureId, revisionId };
  const result = await preparePublicWebpageVisuals(document, { ...prep,
    suppliedPictures: { store, authorization, references, captureIds: new Set([captureId]) } });
  expect(result.captures).toHaveLength(1);
  expect(result.captures[0]).toMatchObject({ status: "reused", captureId, revisionId,
    highlightRects: upload.highlightRects, artifactDigest: hash(raster) });
  expect(await readFile(result.captures[0]!.rasterPath!)).toEqual(raster);
  expect(service.job).not.toHaveBeenCalled();
  expect(references.validatePicturePin).toHaveBeenCalledWith(PROJECT, prep.reference, { captureId, revisionId });
});
