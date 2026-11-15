import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";

import type { CompilerDependenciesV2, ScriptDocumentV2, VisualOnlyBlockV2 } from "@vera/contracts/v2";
import { compileTimelineV2 } from "@vera/contracts/compiler-core-v2";
import type { SuiteIdentityPort } from "@vera/project-authorization";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createProjectApiHandler } from "../src/api.js";
import { fingerprint, sha256 } from "../src/model.js";
import { SecondaryTimingReadService, type VerifiedSecondaryTimingEvidence,
  type VerifiedSecondaryTimingEvidencePort } from "../src/secondary-timing.js";
import { documentFor, harness } from "./helpers.js";

/* eslint-disable @typescript-eslint/require-await -- Fake identity and evidence readers only. */
vi.setConfig({ testTimeout: 90_000 });
const cleaners: Array<() => Promise<void>> = [];
const base = "https://local.stt.test/v1/projects";
const identity: SuiteIdentityPort = {
  authenticate: async (req) => {
    const subject = req.headers.get("X-Test-Suite-Identity");
    if (!subject) throw new Error("unverified");
    return { issuer: "https://trusted.suite.test", subject };
  },
};

function request(path: string, method: string, subject: string | null, body?: unknown): Request {
  return new Request(base + path, { method, headers: {
    ...(subject ? { "X-Test-Suite-Identity": subject } : {}),
    ...(body === undefined ? {} : { "content-type": "application/json" }),
  }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
}

async function json(response: Response): Promise<Record<string, unknown>> {
  return await response.json() as Record<string, unknown>;
}

function stillDocument(projectId: string): ScriptDocumentV2 {
  const doc = documentFor(projectId);
  const visual = (durationOverrideMs: number, orderKey: string): VisualOnlyBlockV2 => ({
    type: "visual_only", id: randomUUID(), version: 1, orderKey,
    payload: { kind: "visual", payloadId: randomUUID(), pictureKind: "intentional_placeholder",
      source: { kind: "intentional_placeholder", text: "Synthetic slate" },
      audioPolicy: "mute", framingPolicy: "contain" },
    visualOnlyTiming: { kind: "visual_only", durationOverrideMs },
  });
  doc.activeDraft.blocks = [visual(1000, "a0"), visual(1000, "a1")];
  return doc;
}

function frozenInputs(doc: ScriptDocumentV2, revision: number): CompilerDependenciesV2 {
  const deps = JSON.parse(readFileSync(new URL(
    "../../../tests/data/authoring_v2/compiler-dependencies-v2.json", import.meta.url,
  ), "utf8")) as CompilerDependenciesV2;
  deps.document = { ...deps.document,
    projectId: doc.projectId, documentId: doc.id, revision: revision + 1,
    liveHeadSequence: doc.liveHeadSequence, contentHash: doc.liveContentHash, textHash: sha256("") };
  deps.timeline.frameRate = { numerator: 24000, denominator: 1001 };
  deps.narrationTimingMaps = [];
  deps.occurrenceResolutions = [];
  deps.preparedMedia = [];
  deps.tracks.push(
    { id: "placeholder", kind: "video", index: 2, name: "Placeholder" },
    { id: "presenter", kind: "video", index: 3, name: "Presenter" },
    { id: "markers", kind: "video", index: 4, name: "Markers" },
  );
  deps.roles.presenterTrackId = "presenter";
  deps.roles.placeholderTrackId = "placeholder";
  deps.roles.markerTrackId = "markers";
  return deps;
}

function artifact(doc: ScriptDocumentV2, revision: number, digest: string): VerifiedSecondaryTimingEvidence {
  const dependencies = frozenInputs(doc, revision);
  const compilation = compileTimelineV2(doc, dependencies);
  if (!compilation.ok) throw new Error(JSON.stringify(compilation.diagnostics));
  if (compilation.report.readiness.preview !== "ready") {
    throw new Error(JSON.stringify(compilation.report.diagnostics));
  }
  return { projectId: doc.projectId, documentId: doc.id, revision, digest, dependencies,
    dependenciesHash: fingerprint(dependencies), manifest: compilation.manifest,
    manifestHash: fingerprint(compilation.manifest) };
}

async function setup() {
  const h = await harness();
  cleaners.push(async () => { await h.db.close(); });
  const projectId = randomUUID();
  const document = stillDocument(projectId);
  const readVerified = vi.fn(async (): Promise<unknown> => null);
  const evidenceReader: VerifiedSecondaryTimingEvidencePort = { readVerified };
  const timing = new SecondaryTimingReadService(h.service, evidenceReader);
  const api = createProjectApiHandler({ identity, authorization: h.auth, documents: h.service, secondaryTiming: timing });
  expect((await api(request("", "POST", "owner", {
    projectId, title: "Secondary timing tests", document, clientRequestId: randomUUID(),
  }))).status).toBe(201);
  const saved = await h.service.getDocument(projectId, h.owner);
  const verified = artifact(saved.document, saved.revision, saved.digest);
  readVerified.mockResolvedValue(verified);
  await h.auth.changeMembership(projectId, h.owner, h.viewer.principalId, "viewer");
  await h.auth.changeMembership(projectId, h.owner, h.editor.principalId, "editor");
  const route = `/${projectId}/document/secondary-timing`;
  const first = saved.document.activeDraft.blocks[0] as VisualOnlyBlockV2;
  const firstEvent = verified.manifest.events.find((event) => event.provenance.blockId === first.id)!;
  const input = { expectedRevision: saved.revision, expectedDigest: saved.digest,
    command: { kind: "visual_only_duration", blockId: first.id, expectedBlockVersion: first.version,
      expectedRange: firstEvent.recordRange, durationOverrideMs: 1084 } };
  return { ...h, api, route, projectId, document, saved, verified, readVerified, input };
}

afterEach(async () => { for (const cleanup of cleaners.splice(0)) await cleanup(); });

describe("#391 secondary timing verified API (read and proposal only)", () => {
  it("permits authorized viewer/editor read and preview with pinned 24000/1001 timing; never writes", async () => {
    const { api, route, input, saved, service, projectId, verified, readVerified, viewer, editor, owner } = await setup();
    for (const subject of ["viewer", "editor"]) {
      const get = await api(request(route, "GET", subject));
      expect(get.status).toBe(200);
      expect(get.headers.get("cache-control")).toBe("no-store");
      const getData = await json(get);
      expect(getData).toMatchObject({ schemaVersion: "secondary-timing/v1",
        revision: 0, digest: saved.digest, manifestHash: verified.manifestHash,
        disposition: "verified_read_only", comparison: {
          frameRate: { numerator: 24000, denominator: 1001 }, disposition: "proposed_not_applied",
        } });
      const getComparison = getData.comparison as { visualEvents: Array<{ durationDeltaFrames: number }> };
      expect(getComparison.visualEvents.some((event) => event.durationDeltaFrames === 0)).toBe(true);
      const preview = await api(request(route + "/preview", "POST", subject, input));
      expect(preview.status).toBe(200);
      const data = await json(preview);
      expect(data).toMatchObject({ revision: 0, digest: saved.digest,
        result: { ok: true, disposition: "proposed_not_applied" } });
      const previewResult = data.result as { comparison: { visualEvents: Array<{ durationDeltaFrames: number }> } };
      expect(previewResult.comparison.visualEvents.some((event) => event.durationDeltaFrames === 2)).toBe(true);
      expect(await service.getDocument(projectId, subject === "viewer" ? viewer : editor)).toEqual(saved);
    }
    expect(readVerified).toHaveBeenCalledWith({ projectId, documentId: saved.document.id,
      revision: 0, digest: saved.digest });
    expect(await service.getDocument(projectId, owner)).toEqual(saved);
  });

  it("fails closed before artifact IO for missing/foreign permission, and after mid-request revocation", async () => {
    const { api, route, projectId, owner, viewer, auth, readVerified, verified, input } = await setup();
    expect((await api(request(route, "GET", null))).status).toBe(401);
    expect((await api(request(`/${randomUUID()}/document/secondary-timing`, "GET", "viewer"))).status).toBe(403);
    expect((await api(request(route, "POST", "stranger", input))).status).toBe(404);
    const previousCalls = readVerified.mock.calls.length;
    expect((await api(request(`/${randomUUID()}/document/secondary-timing/preview`, "POST", "viewer", input))).status).toBe(403);
    expect(readVerified.mock.calls.length).toBe(previousCalls);
    readVerified.mockImplementationOnce(async () => {
      await auth.changeMembership(projectId, owner, viewer.principalId, null);
      return verified;
    });
    expect((await api(request(route, "GET", "viewer"))).status).toBe(403);
  });

  it("rejects unavailable and forged artifacts, wrong identities, stale pins, and recompiled timing drift", async () => {
    const { api, route, verified, readVerified, input } = await setup();
    const read = () => api(request(route, "GET", "owner"));
    readVerified.mockRejectedValueOnce(new Error("internal token: secret"));
    expect(await json(await read())).toEqual({ error: "service_unavailable", reason: "timing_evidence_unavailable" });
    for (const forged of [
      { ...verified, projectId: randomUUID() },
      { ...verified, documentId: randomUUID() },
      { ...verified, revision: 9 },
      { ...verified, digest: sha256("not saved") },
      { ...verified, manifestHash: sha256("forged manifest") },
      { ...verified, dependenciesHash: sha256("forged timing") },
      { ...verified, manifest: { ...verified.manifest, timeline: { ...verified.manifest.timeline, durationFrames: 123 } } },
      { ...verified, manifest: { ...verified.manifest, timeline: { ...verified.manifest.timeline, durationFrames: 123 } },
        manifestHash: fingerprint({ ...verified.manifest, timeline: { ...verified.manifest.timeline, durationFrames: 123 } }) },
      { ...verified, dependencies: { ...verified.dependencies, document: {
        ...verified.dependencies.document, textHash: sha256("replaced frozen words") } },
        dependenciesHash: fingerprint({ ...verified.dependencies, document: {
          ...verified.dependencies.document, textHash: sha256("replaced frozen words") } }) },
      { ...verified, extra: "untrusted" },
    ]) {
      readVerified.mockResolvedValueOnce(forged);
      const failure = await read();
      expect(failure.status).toBe(503);
      expect(await json(failure)).toEqual({ error: "service_unavailable", reason: "timing_evidence_unavailable" });
    }
    readVerified.mockResolvedValueOnce(null);
    expect((await api(request(route + "/preview", "POST", "viewer", input))).status).toBe(503);
  });

  it("refuses unknown fields, unsafe ranges, fake authority, stale expected head and no-port hosts", async () => {
    const { api, route, saved, input, auth, service, readVerified } = await setup();
    const noPort = createProjectApiHandler({ identity, authorization: auth, documents: service });
    expect(await json(await noPort(request(route, "GET", "viewer"))))
      .toEqual({ error: "service_unavailable", reason: "timing_evidence_unavailable" });
    expect((await api(request(route + "/operations", "POST", "editor", input))).status).toBe(400);
    expect((await api(request(route + "/preview", "GET", "viewer"))).status).toBe(404);
    expect((await api(request(route + "?roles=admin", "GET", "viewer"))).status).toBe(400);
    expect((await api(request(route + "/preview?x=1", "POST", "viewer", input))).status).toBe(400);
    const samples = [
      { ...input, role: "owner" },
      { ...input, manifest: {} },
      { ...input, expectedDigest: "not-a-digest" },
      { ...input, expectedRevision: "0" },
      { ...input, command: { ...input.command, actorId: randomUUID() } },
      { ...input, command: { ...input.command, expectedRange: { startFrame: 0, endFrame: 24, extra: 1 } } },
      { ...input, command: { ...input.command, expectedRange: { startFrame: 25, endFrame: 24 } } },
      { ...input, command: { ...input.command, durationOverrideMs: 1.5 } },
      { ...input, command: { ...input.command, durationOverrideMs: Number.MAX_SAFE_INTEGER + 1 } },
      { ...input, command: { ...input.command, blockId: "not-uuid" } },
      { ...input, command: { ...input.command, kind: "unknown" } },
      { expectedRevision: 0, expectedDigest: saved.digest, command: {
        kind: "primary_frame_offset", blockId: randomUUID(), slotId: randomUUID(),
        expectedSequenceVersion: 1, expectedBaselineFrame: 0, deltaFrames: 1.2 } },
      { expectedRevision: 0, expectedDigest: saved.digest, command: {
        kind: "overlay_duration", blockId: randomUUID(), overlayEventId: randomUUID(),
        expectedEventVersion: 1, expectedRange: { startFrame: 1, endFrame: 1 }, durationMs: 24 } },
    ];
    for (const item of samples) {
      const result = await api(request(route + "/preview", "POST", "viewer", item));
      expect(result.status, JSON.stringify(item)).toBe(400);
    }
    const callsBeforeStale = readVerified.mock.calls.length;
    expect((await api(request(route + "/preview", "POST", "viewer", {
      ...input, expectedRevision: 1,
    }))).status).toBe(409);
    expect((await api(request(route + "/preview", "POST", "viewer", {
      ...input, expectedDigest: sha256("stale"),
    }))).status).toBe(409);
    expect(readVerified.mock.calls).toHaveLength(callsBeforeStale);
    const noChange = await api(request(route + "/preview", "POST", "viewer", {
      ...input, command: { ...input.command, durationOverrideMs: 1000 },
    }));
    expect(noChange.status).toBe(200);
    expect(await json(noChange)).toMatchObject({ result: { ok: false, code: "NO_FRAME_CHANGE" } });
  });

  it("does not return a verified comparison when the saved head changes during artifact IO", async () => {
    const { api, route, saved, owner, service, readVerified, verified, projectId } = await setup();
    readVerified.mockImplementationOnce(async () => {
      await service.putDocument(projectId, owner, {
        expectedRevision: saved.revision, clientMutationId: randomUUID(),
        document: { ...saved.document, title: "New head during evidence read" },
      });
      return verified;
    });
    const conflict = await api(request(route, "GET", "viewer"));
    expect(conflict.status).toBe(409);
    expect(await json(conflict)).toEqual({ error: "version_conflict" });
    expect((await service.getDocument(projectId, owner)).revision).toBe(1);
  });
});
