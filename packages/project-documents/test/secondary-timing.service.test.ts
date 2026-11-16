import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";

import { previewSecondaryTimingReconcileV2 } from "@vera/contracts/authoring-v2";
import { compileTimelineV2 } from "@vera/contracts/compiler-core-v2";
import type { CompilerDependenciesV2, ScriptDocumentV2, VisualOnlyBlockV2 } from "@vera/contracts/v2";
import type { SuiteIdentityPort } from "@vera/project-authorization";
import { afterEach, describe, expect, it, vi } from "vitest";

import { applyProjectBuildsMigration } from "../../project-builds/src/migration.js";
import { loadFrozen, ProjectBuildSubmissionService } from "../../project-builds/src/submission.js";
import { createProjectApiHandler } from "../src/api.js";
import { fingerprint, sha256 } from "../src/model.js";
import {
  SecondaryTimingReadService, type VerifiedSecondaryTimingEvidence,
  type VerifiedSecondaryTimingEvidencePort,
} from "../src/secondary-timing.js";
import { documentFor, harness, settingsFor } from "./helpers.js";

/* eslint-disable @typescript-eslint/require-await -- Synthetic identity and evidence ports. */
vi.setConfig({ testTimeout: 180_000 });
const cleaners: Array<() => Promise<void>> = [];
const identity: SuiteIdentityPort = {
  authenticate: async (request) => {
    const subject = request.headers.get("X-Test-Suite-Identity");
    if (!subject) throw new Error("unverified");
    return { issuer: "https://trusted.suite.test", subject };
  },
};
const base = "https://local.stt.test/v1/projects";
function request(path: string, subject: string | null, input: unknown, method = "POST"): Request {
  return new Request(base + path, { method, headers: {
    ...(subject ? { "X-Test-Suite-Identity": subject } : {}),
    "content-type": "application/json",
  }, body: JSON.stringify(input) });
}
async function body(response: Response): Promise<Record<string, unknown>> {
  return await response.json() as Record<string, unknown>;
}

function document(projectId: string): ScriptDocumentV2 {
  const doc = documentFor(projectId);
  const still = (orderKey: string): VisualOnlyBlockV2 => ({
    type: "visual_only", id: randomUUID(), version: 1, orderKey,
    payload: { kind: "visual", payloadId: randomUUID(), pictureKind: "intentional_placeholder",
      source: { kind: "intentional_placeholder", text: "Retained slate" },
      audioPolicy: "mute", framingPolicy: "contain" },
    visualOnlyTiming: { kind: "visual_only", durationOverrideMs: 1000 },
  });
  doc.activeDraft.blocks = [still("a0"), still("a1")];
  return doc;
}

function evidence(doc: ScriptDocumentV2, revision: number, digest: string): VerifiedSecondaryTimingEvidence {
  const dependencies = JSON.parse(readFileSync(new URL(
    "../../../tests/data/authoring_v2/compiler-dependencies-v2.json", import.meta.url,
  ), "utf8")) as CompilerDependenciesV2;
  dependencies.document = { ...dependencies.document,
    projectId: doc.projectId, documentId: doc.id, revision: revision + 1,
    liveHeadSequence: doc.liveHeadSequence, contentHash: doc.liveContentHash, textHash: sha256("") };
  dependencies.timeline.frameRate = { numerator: 24000, denominator: 1001 };
  dependencies.narrationTimingMaps = [];
  dependencies.occurrenceResolutions = [];
  dependencies.preparedMedia = [];
  dependencies.tracks.push(
    { id: "placeholder", kind: "video", index: 2, name: "Placeholder" },
    { id: "presenter", kind: "video", index: 3, name: "Presenter" },
    { id: "markers", kind: "video", index: 4, name: "Markers" },
  );
  dependencies.roles.presenterTrackId = "presenter";
  dependencies.roles.placeholderTrackId = "placeholder";
  dependencies.roles.markerTrackId = "markers";
  const compiled = compileTimelineV2(doc, dependencies);
  if (!compiled.ok || compiled.report.readiness.preview !== "ready") throw new Error("invalid synthetic manifest");
  return { projectId: doc.projectId, documentId: doc.id, revision, digest, dependencies,
    dependenciesHash: fingerprint(dependencies), manifest: compiled.manifest,
    manifestHash: fingerprint(compiled.manifest) };
}

async function setup() {
  const h = await harness();
  cleaners.push(async () => { await h.db.close(); });
  const projectId = randomUUID();
  await h.service.createProject(h.owner, { projectId, title: "Secondary timing",
    clientRequestId: randomUUID(), document: document(projectId), settings: settingsFor(projectId) });
  await h.auth.changeMembership(projectId, h.owner, h.editor.principalId, "editor");
  await h.auth.changeMembership(projectId, h.owner, h.viewer.principalId, "viewer");
  const saved = await h.service.getDocument(projectId, h.owner);
  const verified = evidence(saved.document, saved.revision, saved.digest);
  const readVerified = vi.fn(async (): Promise<unknown> => verified);
  const evidencePort: VerifiedSecondaryTimingEvidencePort = { readVerified };
  const timing = new SecondaryTimingReadService(h.service, evidencePort);
  const api = createProjectApiHandler({ identity, authorization: h.auth,
    documents: h.service, secondaryTiming: timing });
  const route = `/${projectId}/document/secondary-timing/operations`;
  const first = saved.document.activeDraft.blocks[0] as VisualOnlyBlockV2;
  const firstEvent = verified.manifest.events.find((item) => item.provenance.blockId === first.id)!;
  const input = { expectedRevision: saved.revision, expectedDigest: saved.digest,
    clientMutationId: randomUUID(), command: {
      kind: "visual_only_duration", blockId: first.id, expectedBlockVersion: first.version,
      expectedRange: firstEvent.recordRange, durationOverrideMs: 1084,
    } };
  return { ...h, projectId, saved, verified, readVerified, route, input, api };
}

async function unchanged(h: Awaited<ReturnType<typeof setup>>) {
  expect(await h.service.getDocument(h.projectId, h.owner)).toEqual(h.saved);
  expect((await h.db.query<{ n: number }>(
    "SELECT count(*)::integer AS n FROM stt_document_revisions WHERE project_id=$1", [h.projectId],
  )).rows[0]?.n).toBe(1);
}

afterEach(async () => { for (const clean of cleaners.splice(0)) await clean(); });

describe("#391 secondary timing atomic authoring revisions", () => {
  it("saves exactly one compiler-verified still edit; previous build, checkpoint and revision remain frozen", async () => {
    const h = await setup();
    await applyProjectBuildsMigration(h.db);
    const builds = new ProjectBuildSubmissionService(h.pool, h.auth);
    const frozenJob = await builds.submit(h.projectId, h.owner, {
      buildClass: "preview", mode: "free", expectedRevision: h.saved.revision,
      expectedDigest: h.saved.digest, idempotencyKey: randomUUID(),
      selectedSources: [], render: false, delivery: false,
    });
    const frozen = await loadFrozen(h.db, h.projectId, frozenJob.jobId);
    const checkpointId = randomUUID();
    await h.service.createCheckpoint(h.projectId, h.owner, {
      checkpointId, clientMutationId: randomUUID(), sourceRevision: 0, name: "Prior timing",
    });
    const priorCheckpoint = await h.service.getCheckpoint(h.projectId, h.owner, checkpointId);
    const historical = await h.service.getDocumentRevision(h.projectId, h.owner, 0);
    const predicted = previewSecondaryTimingReconcileV2(h.saved.document,
      h.verified.dependencies, h.verified.manifest, h.input.command as
        Parameters<typeof previewSecondaryTimingReconcileV2>[3]);
    expect(predicted.ok).toBe(true);
    if (!predicted.ok) return;
    const writeSessionId = await h.auth.openWriteSession(h.projectId, h.editor);
    const requestInput = { ...h.input, writeSessionId };
    const first = await h.api(request(h.route, "editor", requestInput));
    expect(first.status).toBe(200);
    expect(await body(first)).toMatchObject({ schemaVersion: "secondary-timing/v1",
      disposition: "authoring_revision_saved", receipt: { revision: 1, duplicateDelivery: false } });
    const saved = await h.service.getDocument(h.projectId, h.owner);
    expect(saved.revision).toBe(1);
    expect(saved.document).toEqual(predicted.candidateDocument);
    expect(saved.digest).not.toBe(h.saved.digest);
    expect(saved.document.activeDraft.blocks[1]).toEqual(h.saved.document.activeDraft.blocks[1]);
    expect((saved.document.activeDraft.blocks[0] as VisualOnlyBlockV2).version).toBe(2);
    expect((await h.service.getDocumentRevision(h.projectId, h.owner, 0))).toEqual(historical);
    expect(await h.service.getCheckpoint(h.projectId, h.owner, checkpointId)).toEqual(priorCheckpoint);
    expect(await loadFrozen(h.db, h.projectId, frozenJob.jobId)).toEqual(frozen);
    expect(frozen.row.document_digest).toBe(h.saved.digest);
    expect(frozen.row.document_json).not.toBe(JSON.stringify(saved.document));
    const calls = h.readVerified.mock.calls.length;
    const replay = await h.api(request(h.route, "editor", requestInput));
    expect(replay.status).toBe(200);
    expect(await body(replay)).toMatchObject({ receipt: { revision: 1, digest: saved.digest, duplicateDelivery: true } });
    expect(h.readVerified.mock.calls.length).toBe(calls);
    expect((await h.db.query<{ n: number }>(
      "SELECT count(*)::integer AS n FROM stt_document_revisions WHERE project_id=$1", [h.projectId],
    )).rows[0]?.n).toBe(2);
    expect((await h.service.listDocumentRevisions(h.projectId, h.owner)).revisions.map((r) => r.revision))
      .toEqual([1, 0]);
  });

  it("refuses viewer writes, invalid lease, unknown fields, stale owner and unsupported quantized changes without SQL writes", async () => {
    const h = await setup();
    expect((await h.api(request(h.route, "viewer", h.input))).status).toBe(403);
    expect((await h.api(request(h.route, "editor", { ...h.input, writeSessionId: randomUUID() }))).status).toBe(403);
    expect((await h.api(request(h.route, "editor", { ...h.input, manifest: h.verified.manifest }))).status).toBe(400);
    expect((await h.api(request(h.route, "editor", { ...h.input, candidateDocument: h.saved.document }))).status).toBe(400);
    expect((await h.api(request(h.route, "editor", { ...h.input, clientMutationId: "forged" }))).status).toBe(400);
    const noChange = await h.api(request(h.route, "editor", { ...h.input, command: {
      ...h.input.command, durationOverrideMs: 1000,
    } }));
    expect(noChange.status).toBe(400);
    expect(await body(noChange)).toMatchObject({ error: "invalid_request", operationCode: "NO_FRAME_CHANGE" });
    expect((await h.api(request(h.route, "editor", { ...h.input, command: {
      ...h.input.command, expectedBlockVersion: 99,
    } }))).status).toBe(409);
    expect((await h.api(request(h.route, "editor", { ...h.input, expectedRevision: 1 }))).status).toBe(409);
    expect((await h.api(request(h.route, "editor", { ...h.input, expectedDigest: sha256("not head") }))).status).toBe(409);
    await unchanged(h);
  });

  it("uses actor-scoped replay identity, checks revoked lease on replay and never reuses a PUT mutation ID", async () => {
    const h = await setup();
    const writeSessionId = await h.auth.openWriteSession(h.projectId, h.editor);
    const command = { ...h.input, writeSessionId };
    expect((await h.api(request(h.route, "editor", command))).status).toBe(200);
    const changed = await h.service.getDocument(h.projectId, h.owner);
    const altered = await h.api(request(h.route, "editor", { ...command,
      command: { ...command.command, durationOverrideMs: 1125 } }));
    expect(altered.status).toBe(409);
    expect(await body(altered)).toMatchObject({ error: "idempotency_conflict" });
    await expect(h.service.putDocument(h.projectId, h.editor, {
      expectedRevision: 1, clientMutationId: command.clientMutationId, writeSessionId,
      document: changed.document,
    })).rejects.toMatchObject({ status: 409, code: "idempotency_conflict" });
    await h.auth.changeMembership(h.projectId, h.owner, h.editor.principalId, "viewer");
    expect((await h.api(request(h.route, "editor", command))).status).toBe(403);
    await h.auth.changeMembership(h.projectId, h.owner, h.editor.principalId, "editor");
    // Membership change invalidates the old lease even after editor restoration.
    expect((await h.api(request(h.route, "editor", command))).status).toBe(403);
    expect((await h.api(request(h.route, "editor", { ...command, writeSessionId: null }))).status).toBe(400);
    expect((await h.api(request(h.route, "editor", h.input))).status).toBe(200);
    expect(await h.service.getDocument(h.projectId, h.owner)).toEqual(changed);
  });

  it("rejects forged or unavailable frozen inputs and any concurrent PUT during evidence IO", async () => {
    const h = await setup();
    h.readVerified.mockResolvedValueOnce({ ...h.verified, manifestHash: sha256("forged") });
    expect((await h.api(request(h.route, "owner", h.input))).status).toBe(503);
    h.readVerified.mockRejectedValueOnce(new Error("forbidden artifact"));
    expect((await h.api(request(h.route, "owner", h.input))).status).toBe(503);
    await unchanged(h);
    h.readVerified.mockImplementationOnce(async () => {
      await h.service.putDocument(h.projectId, h.owner, { expectedRevision: 0,
        clientMutationId: randomUUID(), document: { ...h.saved.document, title: "Concurrent PUT" } });
      return h.verified;
    });
    expect((await h.api(request(h.route, "owner", h.input))).status).toBe(409);
    const final = await h.service.getDocument(h.projectId, h.owner);
    expect(final.revision).toBe(1);
    expect(final.document.title).toBe("Concurrent PUT");
    expect((final.document.activeDraft.blocks[0] as VisualOnlyBlockV2).version).toBe(1);
    expect((await h.db.query<{ n: number }>(
      "SELECT count(*)::integer AS n FROM stt_document_revisions WHERE project_id=$1", [h.projectId],
    )).rows[0]?.n).toBe(2);
  });

  it("rolls back the inserted revision if the locked head update fails", async () => {
    const h = await setup();
    await h.db.exec(`CREATE FUNCTION reject_timing_head_update() RETURNS trigger AS $$
      BEGIN RAISE EXCEPTION 'synthetic head failure'; END; $$ LANGUAGE plpgsql;
      CREATE TRIGGER reject_timing_head_update BEFORE UPDATE ON stt_document_heads
      FOR EACH ROW EXECUTE FUNCTION reject_timing_head_update();`);
    const result = await h.api(request(h.route, "owner", h.input));
    expect(result.status).toBe(503);
    await unchanged(h);
  });
});
