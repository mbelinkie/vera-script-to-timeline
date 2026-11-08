import { randomUUID } from "node:crypto";

import { PGlite } from "@electric-sql/pglite";
import {
  applyProjectAuthorizationMigration, ProjectAuthorizationService, type SqlPool,
} from "@vera/project-authorization";
import {
  applyProjectCommentsMigration, applyProjectDocumentsMigration, ProjectDocumentService, sha256,
} from "@vera/project-documents";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectAgentAuthenticationService } from "../src/agent-auth.js";
import { applyProjectBuildsMigration } from "../src/migration.js";
import { AGENT_PROTOCOL_VERSION, ProjectAgentPairingService } from "../src/pairing.js";
import {
  ProjectBuildSubmissionService, type AcceptedSourceAuthority,
} from "../src/submission.js";
import {
  ProjectBuildStatusService, type IndependentEvidenceInspector,
} from "../src/status.js";

/* eslint-disable @typescript-eslint/require-await -- PGlite and fake inspectors implement async ports. */
vi.setConfig({ testTimeout: 120_000 });

const databases: PGlite[] = [];
const d = (value: string) => sha256(value);
const source = (sourceId = randomUUID(), revision = "v1", payload = "sample-media") =>
  ({ sourceId, revision, sha256: d(payload) });

async function buildHarness(options?: { settings?: boolean }) {
  const db = new PGlite();
  databases.push(db);
  await db.waitReady;
  await applyProjectAuthorizationMigration(db);
  await applyProjectDocumentsMigration(db);
  // Document PUT now atomically checks the separate comment-head store, even
  // for build-only projects that have never created a comment.
  await applyProjectCommentsMigration(db);
  await applyProjectBuildsMigration(db);
  const pool: SqlPool = { connect: async () => db };
  const auth = new ProjectAuthorizationService(pool);
  const documents = new ProjectDocumentService(pool, auth);
  const producer = await auth.resolveActor({ issuer: "fixture", subject: randomUUID() });
  const editor = await auth.resolveActor({ issuer: "fixture", subject: randomUUID() });
  const viewer = await auth.resolveActor({ issuer: "fixture", subject: randomUUID() });
  const outsider = await auth.resolveActor({ issuer: "fixture", subject: randomUUID() });
  const projectId = randomUUID();
  const documentId = randomUUID();
  const settingsId = randomUUID();
  const document = {
    schemaVersion: "script-document/v2" as const, id: documentId, projectId,
    title: "synthetic build test", activeDraft: { blocks: [], supportingItems: [] },
    ideaOutline: [], extras: [], liveHeadSequence: 1, liveStateVector: "",
    liveContentHash: d("live-head-1"),
  };
  const settings = {
    schemaVersion: "authoring-project-settings/v1" as const, id: settingsId, projectId,
    version: 1, settingsHash: d("settings-v1"),
  };
  const created = await documents.createProject(producer, {
    clientRequestId: randomUUID(), projectId, title: "synthetic",
    document, ...(options?.settings === false ? {} : { settings }),
  });
  await db.query(
    "INSERT INTO vera_project_members(project_id,actor_id,role) " +
      "VALUES($1,$2,'editor'),($1,$3,'viewer')",
    [projectId, editor.principalId, viewer.principalId],
  );
  // Test-only stand-in for a real accepted-source service. Production does NOT
  // create this table; no raw client assertion is accepted by this adapter.
  await db.query("CREATE TABLE fixture_accepted_sources (" +
    "project_id uuid NOT NULL, source_id uuid NOT NULL, revision text NOT NULL," +
    "digest text NOT NULL, accepted boolean NOT NULL," +
    "PRIMARY KEY(project_id,source_id,revision))");
  const sources: AcceptedSourceAuthority = {
    verifySelected: async (client, project, pins) => {
      const records = [];
      for (const pin of pins) {
        const rows = await client.query<{ source_id: string; revision: string; digest: string }>(
          "SELECT source_id,revision,digest FROM fixture_accepted_sources " +
            "WHERE project_id=$1 AND source_id=$2 AND revision=$3 AND accepted=true",
          [project, pin.sourceId, pin.revision],
        );
        if (!rows.rows[0]) return null;
        records.push({ sourceId: rows.rows[0].source_id,
          revision: rows.rows[0].revision, sha256: rows.rows[0].digest });
      }
      return records;
    },
  };
  async function accept(pin: ReturnType<typeof source>, accepted = true, project = projectId) {
    await db.query(
      "INSERT INTO fixture_accepted_sources(project_id,source_id,revision,digest,accepted) " +
        "VALUES($1,$2,$3,$4,$5) ON CONFLICT(project_id,source_id,revision) " +
        "DO UPDATE SET digest=$4,accepted=$5",
      [project, pin.sourceId, pin.revision, pin.sha256, accepted],
    );
  }
  const clock = { ms: Date.parse("2026-11-08T16:00:00Z") };
  const now = () => new Date(clock.ms);
  const submissions = new ProjectBuildSubmissionService(pool, auth, sources, now);
  const pairing = new ProjectAgentPairingService(pool, auth, now);
  const agents = new ProjectAgentAuthenticationService(pool, auth, now);
  function status(inspector?: IndependentEvidenceInspector) {
    return new ProjectBuildStatusService(pool, auth, agents, sources, now, inspector);
  }
  async function pair(capabilities: string[] = ["free_package_v1"]) {
    const offer = await pairing.createOffer(projectId, producer,
      { agentLabel: "fake local agent", protocolVersion: AGENT_PROTOCOL_VERSION });
    const connected = await pairing.consumeOffer({
      projectId, offerToken: offer.offerToken,
      protocolVersion: AGENT_PROTOCOL_VERSION, capabilities,
    });
    return { projectId, agentToken: connected.agentToken,
      credentialVersion: connected.credentialVersion, agentId: connected.agentId };
  }
  function intent(selectedSources: ReturnType<typeof source>[] = [],
    extras: Partial<{
      buildClass: "preview" | "release"; mode: "free" | "studio";
      expectedRevision: number; expectedDigest: string; idempotencyKey: string;
    }> = {}) {
    return {
      buildClass: "preview" as const, mode: "free" as const,
      expectedRevision: created.documentRevision, expectedDigest: created.documentDigest,
      idempotencyKey: randomUUID(), selectedSources, render: false as const,
      delivery: false as const, ...extras,
    };
  }
  return { db, pool, auth, documents, document, settings, producer, editor, viewer,
    outsider, projectId, clock, now, sources, accept, submissions,
    agents, pairing, pair, status, intent };
}

afterEach(async () => {
  for (const db of databases.splice(0)) await db.close();
});

describe("transactionally frozen submission from #380 and #379", () => {
  it("freezes exactly selected accepted revisions, exact stored bytes and one unique target", async () => {
    const h = await buildHarness();
    const one = source(), two = source(), unselected = source();
    for (const pin of [one, two, unselected]) await h.accept(pin);
    const input = h.intent([two, one]);
    const result = await h.submissions.submit(h.projectId, h.editor, input);
    expect(result).toMatchObject({ status: "queued", reasonCode: null, duplicateDelivery: false });
    const selected = (await h.db.query<{ source_id: string; source_revision: string; source_digest: string }>(
      "SELECT source_id,source_revision,source_digest FROM stt_build_source_pins " +
        "WHERE job_id=$1 ORDER BY source_id", [result.jobId],
    )).rows;
    expect(selected).toHaveLength(2);
    expect(selected.map((p) => p.source_id).sort()).toEqual([one.sourceId, two.sourceId].sort());
    expect(selected.every((p) => p.source_revision === "v1")).toBe(true);
    const frozen = (await h.db.query<{
      document_json: string; document_digest: string; settings_json: string;
      settings_digest: string; submitted_by: string; snapshot_digest: string;
    }>("SELECT document_json,document_digest,settings_json,settings_digest," +
      "submitted_by,snapshot_digest FROM stt_build_submissions WHERE id=$1", [result.jobId])).rows[0]!;
    const head = (await h.db.query<{ document_json: string; content_digest: string }>(
      "SELECT document_json,content_digest FROM stt_document_heads WHERE project_id=$1",
      [h.projectId])).rows[0]!;
    expect(frozen.document_json).toBe(head.document_json);
    expect(frozen.document_digest).toBe(head.content_digest);
    expect(frozen.settings_digest).toBe(d(frozen.settings_json));
    expect(frozen.submitted_by).toBe(h.editor.principalId);
    expect(frozen.snapshot_digest).toBe(result.snapshotDigest);
    const readback = await h.status().get(h.projectId, h.viewer, result.jobId);
    expect(readback.selectedSources).toHaveLength(2);
    expect(JSON.stringify(readback)).not.toContain("documentJson");
    expect(readback.events.map((e) => e.status)).toEqual(["queued"]);
    expect(readback.leaseEpoch).toBe(0);
  });

  it("replays exact intent after live head change without duplicate job, rejects 409 reuse", async () => {
    const h = await buildHarness();
    const input = h.intent();
    const first = await h.submissions.submit(h.projectId, h.producer, input);
    await h.documents.putDocument(h.projectId, h.producer, {
      expectedRevision: 0, clientMutationId: randomUUID(),
      document: { ...h.document, title: "edited" },
    });
    expect(await h.submissions.submit(h.projectId, h.producer, input))
      .toMatchObject({ ...first, duplicateDelivery: true });
    await expect(h.submissions.submit(h.projectId, h.producer, {
      ...input, mode: "studio",
    })).rejects.toMatchObject({ code: "idempotency_conflict", status: 409 });
    await expect(h.submissions.submit(h.projectId, h.producer, {
      ...input, idempotencyKey: randomUUID(),
    })).rejects.toMatchObject({ code: "stale_snapshot", status: 409 });
    expect((await h.db.query("SELECT * FROM stt_build_submissions")).rows).toHaveLength(1);
  });

  it("rechecks role and membership on replay, disallows Viewer/release Editor and outsiders", async () => {
    const h = await buildHarness();
    const preview = h.intent();
    const result = await h.submissions.submit(h.projectId, h.editor, preview);
    await expect(h.submissions.submit(h.projectId, h.viewer, h.intent()))
      .rejects.toMatchObject({ status: 403 });
    await expect(h.submissions.submit(h.projectId, h.outsider, h.intent()))
      .rejects.toMatchObject({ status: 403 });
    await expect(h.submissions.submit(h.projectId, h.editor,
      h.intent([], { buildClass: "release" }))).rejects.toMatchObject({ status: 403 });
    expect((await h.submissions.submit(h.projectId, h.producer,
      h.intent([], { buildClass: "release" }))).status).toBe("queued");
    await h.db.query("UPDATE vera_project_members SET active=false WHERE project_id=$1 AND actor_id=$2",
      [h.projectId, h.editor.principalId]);
    await expect(h.submissions.submit(h.projectId, h.editor, preview))
      .rejects.toMatchObject({ status: 403 });
    await expect(h.status().get(h.projectId, h.outsider, result.jobId))
      .rejects.toMatchObject({ status: 403 });
    await expect(h.submissions.resume(h.projectId, h.viewer, result.jobId))
      .rejects.toMatchObject({ status: 403 });
  });

  it("blocks unverified, stale and cross-project source claims without inventing acceptance", async () => {
    const h = await buildHarness();
    const pin = source();
    const input = h.intent([pin]);
    const blocked = await h.submissions.submit(h.projectId, h.editor, input);
    expect(blocked).toMatchObject({ status: "blocked", reasonCode: "source_unverified" });
    await h.accept(pin, true, randomUUID()); // foreign source is not accepted here
    expect(await h.submissions.resume(h.projectId, h.editor, blocked.jobId)).toBe("blocked");
    await h.accept({ ...pin, sha256: d("wrong-bytes") });
    expect(await h.submissions.resume(h.projectId, h.editor, blocked.jobId)).toBe("blocked");
    await h.accept(pin);
    expect(await h.submissions.resume(h.projectId, h.editor, blocked.jobId)).toBe("queued");
    const history = await h.status().get(h.projectId, h.viewer, blocked.jobId);
    expect(history.events.map((event) => event.status)).toEqual(["blocked", "blocked", "blocked", "queued"]);
    const noAdapter = new ProjectBuildSubmissionService(h.pool, h.auth);
    expect((await noAdapter.submit(h.projectId, h.editor,
      h.intent([pin]))).status).toBe("blocked");
  });

  it("refuses missing settings and tampered #380 storage, without inventing a snapshot", async () => {
    const missing = await buildHarness({ settings: false });
    const request = missing.intent();
    await expect(missing.submissions.submit(missing.projectId, missing.producer, request))
      .rejects.toMatchObject({ code: "settings_unavailable", status: 409 });
    expect((await missing.db.query("SELECT * FROM stt_build_submissions")).rows).toHaveLength(0);
    const refusal = await missing.db.query<{ request_digest: string; reason_code: string }>(
      "SELECT request_digest,reason_code FROM stt_build_preflight_refusals " +
        "WHERE project_id=$1 AND submitted_by=$2 AND idempotency_key=$3",
      [missing.projectId, missing.producer.principalId, request.idempotencyKey],
    );
    expect(refusal.rows).toHaveLength(1);
    expect(refusal.rows[0]?.reason_code).toBe("settings_unavailable");
    await missing.documents.putSettings(missing.projectId, missing.producer, {
      expectedSettingsRevision: 0, clientMutationId: randomUUID(), settings: missing.settings,
    });
    await expect(missing.submissions.submit(missing.projectId, missing.producer, request))
      .rejects.toMatchObject({ code: "settings_unavailable", status: 409 });
    await expect(missing.submissions.submit(missing.projectId, missing.producer,
      { ...request, mode: "studio" })).rejects.toMatchObject({
      code: "idempotency_conflict", status: 409,
    });
    expect((await missing.db.query("SELECT * FROM stt_build_preflight_refusals")).rows).toHaveLength(1);
    expect((await missing.submissions.submit(missing.projectId, missing.producer,
      { ...request, idempotencyKey: randomUUID() })).status).toBe("queued");
    const h = await buildHarness();
    const original = (await h.db.query<{ document_json: string }>(
      "SELECT document_json FROM stt_document_heads WHERE project_id=$1",
      [h.projectId],
    )).rows[0]!;
    const changed = { ...(JSON.parse(original.document_json) as Record<string, unknown>),
      title: "malicious alteration preserving document and project IDs" };
    await h.db.query("UPDATE stt_document_heads SET document_json=$2 WHERE project_id=$1",
      [h.projectId, JSON.stringify(changed)]);
    await expect(h.submissions.submit(h.projectId, h.editor, h.intent()))
      .rejects.toMatchObject({ code: "tampered_snapshot", status: 409 });
    expect((await h.db.query("SELECT * FROM stt_build_submissions")).rows).toHaveLength(0);
  });
});

describe("epoch-CAS durable status and independently classified evidence", () => {
  it("polls only project-scoped queued builds and refuses revoked agent identity", async () => {
    const h = await buildHarness();
    const ready = await h.submissions.submit(h.projectId, h.producer, h.intent());
    const blocked = await h.submissions.submit(h.projectId, h.producer, h.intent([source()]));
    expect(blocked.status).toBe("blocked");
    const agent = await h.pair();
    expect(await h.status().pollQueued(agent)).toEqual([ready.jobId]);
    await expect(h.status().pollQueued({ ...agent, projectId: randomUUID() }))
      .rejects.toMatchObject({ status: 401 });
    await h.pairing.revokeAgent(h.projectId, h.producer, agent.agentId);
    await expect(h.status().pollQueued(agent)).rejects.toMatchObject({ status: 401 });
  });

  it("rejects stale head before claim and retains the refusal after service restart", async () => {
    const h = await buildHarness();
    const intent = h.intent();
    const job = await h.submissions.submit(h.projectId, h.producer, intent);
    const agent = await h.pair();
    await h.documents.putDocument(h.projectId, h.producer, {
      expectedRevision: 0, clientMutationId: randomUUID(),
      document: { ...h.document, title: "updated before worker" },
    });
    await expect(h.status().claim(agent, job.jobId))
      .rejects.toMatchObject({ code: "stale_snapshot", status: 409 });
    const restarted = new ProjectBuildStatusService(h.pool, h.auth, h.agents, h.sources, h.now);
    const result = await restarted.get(h.projectId, h.viewer, job.jobId);
    expect(result.status).toBe("stale_snapshot");
    expect(result.events.map((e) => e.status)).toEqual(["queued", "stale_snapshot"]);
    expect(result.leaseEpoch).toBe(0);
    await expect(restarted.claim(agent, job.jobId))
      .rejects.toMatchObject({ code: "invalid_transition", status: 409 });
  });

  it("rejects accepted-source revocation before claim, preserving a durable blocked event", async () => {
    const h = await buildHarness();
    const pin = source();
    await h.accept(pin);
    const job = await h.submissions.submit(h.projectId, h.producer, h.intent([pin]));
    const agent = await h.pair();
    await h.accept(pin, false);
    await expect(h.status().claim(agent, job.jobId))
      .rejects.toMatchObject({ code: "source_unverified", status: 409 });
    const state = await h.status().get(h.projectId, h.viewer, job.jobId);
    expect(state.status).toBe("blocked");
    expect(state.events.map((e) => e.status)).toEqual(["queued", "blocked"]);
    expect(state.leaseEpoch).toBe(0);
    await h.accept(pin);
    expect(await h.submissions.resume(h.projectId, h.producer, job.jobId)).toBe("queued");
  });

  it("retains frozen bytes, claims and partial evidence through database export/reload", async () => {
    const h = await buildHarness();
    const job = await h.submissions.submit(h.projectId, h.producer, h.intent());
    const agent = await h.pair();
    await h.status().claim(agent, job.jobId);
    await h.status().appendProgress(agent, job.jobId, {
      leaseEpoch: 1, status: "running", stageKey: "compile",
      receiptDigest: d("partial-before-crash"), reasonCode: null,
    });
    const dump = await h.db.dumpDataDir();
    const recovered = new PGlite({ loadDataDir: dump });
    databases.push(recovered);
    await recovered.waitReady;
    const recoveredPool: SqlPool = { connect: async () => recovered };
    const recoveredAuth = new ProjectAuthorizationService(recoveredPool);
    const recoveredAgents = new ProjectAgentAuthenticationService(recoveredPool, recoveredAuth, h.now);
    const recoveredStatus = new ProjectBuildStatusService(recoveredPool, recoveredAuth,
      recoveredAgents, h.sources, h.now);
    const state = await recoveredStatus.get(h.projectId, h.viewer, job.jobId);
    expect(state.status).toBe("running");
    expect(state.snapshotDigest).toBe(job.snapshotDigest);
    expect(state.events.map((e) => e.status)).toEqual(["queued", "leased", "running"]);
    expect((await recoveredStatus.frozenForAgent(agent, job.jobId, 1)).documentDigest)
      .toBe(state.documentDigest);
    await expect(recoveredStatus.claim(agent, job.jobId))
      .rejects.toMatchObject({ status: 409 });
  });

  it("scopes claims, verifies capability/epoch/expiry, and refuses forged native progress", async () => {
    const h = await buildHarness();
    const job = await h.submissions.submit(h.projectId, h.producer, h.intent());
    const weak = await h.pair(["studio_readback_v1"]);
    await expect(h.status().claim(weak, job.jobId)).rejects.toMatchObject({ status: 409 });
    const agent = await h.pair();
    await expect(h.status().claim({ ...agent, projectId: randomUUID() }, job.jobId))
      .rejects.toMatchObject({ status: 401 });
    const claim = await h.status().claim(agent, job.jobId);
    expect(claim).toMatchObject({ jobId: job.jobId, leaseEpoch: 1 });
    expect((await h.status().frozenForAgent(agent, job.jobId, 1)).documentDigest)
      .toBe((await h.status().get(h.projectId, h.viewer, job.jobId)).documentDigest);
    await expect(h.status().claim(agent, job.jobId)).rejects.toMatchObject({ status: 409 });
    await expect(h.status().frozenForAgent(agent, job.jobId, 2))
      .rejects.toMatchObject({ code: "lease_conflict", status: 409 });
    const report = { leaseEpoch: 1, stageKey: "compile", receiptDigest: d("receipt"),
      reasonCode: null, status: "running" as const };
    await expect(h.status().appendProgress(agent, job.jobId, { ...report, leaseEpoch: 2 }))
      .rejects.toMatchObject({ status: 409 });
    await expect(h.status().appendProgress(agent, job.jobId, {
      ...report, stageKey: "../unsafe",
    })).rejects.toMatchObject({ status: 400 });
    await expect(h.status().appendProgress(agent, job.jobId, {
      ...report, status: "verified_native" as "running",
    })).rejects.toMatchObject({ status: 400 });
    await h.status().appendProgress(agent, job.jobId, report);
    await expect(h.status().inspectEvidence(agent, job.jobId, 1, "compile", d("receipt")))
      .rejects.toMatchObject({ status: 409 });
    let view = await h.status().get(h.projectId, h.viewer, job.jobId);
    expect(view.events.at(-1)?.evidenceKind).toBe("untrusted_report");
    expect(view.status).toBe("running");
    expect(view.evidence).toHaveLength(0);
    h.clock.ms += 60_000;
    await expect(h.status().appendProgress(agent, job.jobId, report))
      .rejects.toMatchObject({ code: "lease_conflict", status: 409 });
    view = await h.status().get(h.projectId, h.viewer, job.jobId);
    expect(view.status).toBe("waiting_reconcile");
    expect(view.reasonCode).toBe("lease_expired");
    expect(view.events.map((e) => e.status))
      .toEqual(["queued", "leased", "running", "waiting_reconcile"]);
    // Readback is idempotent: never erase a prior receipt or append a second expiry.
    const again = await h.status().get(h.projectId, h.viewer, job.jobId);
    expect(again.events).toHaveLength(4);
    expect(again.events[2]?.receiptDigest).toBe(report.receiptDigest);
    await expect(h.status().claim(agent, job.jobId))
      .rejects.toMatchObject({ status: 409 });
  });

  it("appends inspected synthetic evidence without elevating it to native proof", async () => {
    const h = await buildHarness();
    const job = await h.submissions.submit(h.projectId, h.producer, h.intent());
    const agent = await h.pair();
    await h.status().claim(agent, job.jobId);
    const inspector: IndependentEvidenceInspector = {
      inspect: async (_db, projectId, jobId, stageKey, receiptDigest) => {
        if (projectId !== h.projectId || jobId !== job.jobId) return null;
        return { kind: "synthetic", stageKey, receiptDigest,
          outputDigest: d("output"), verificationDigest: d("independently inspected synthetic fixture") };
      },
    };
    const inspected = h.status(inspector);
    await inspected.inspectEvidence(agent, job.jobId, 1, "compile", d("receipt"));
    const restarted = new ProjectBuildStatusService(h.pool, h.auth, h.agents, h.sources, h.now);
    const result = await restarted.get(h.projectId, h.viewer, job.jobId);
    expect(result.status).toBe("leased");
    expect(result.events.at(-1)?.evidenceKind).toBe("synthetic");
    expect(result.evidence).toHaveLength(1);
    expect(result.evidence[0]).toMatchObject({
      stage_key: "compile", evidence_kind: "synthetic", output_digest: d("output"),
    });
    await expect(h.db.query("UPDATE stt_build_evidence SET evidence_kind='native_readback'"))
      .rejects.toThrow("append-only");
    await expect(h.db.query("DELETE FROM stt_build_events")).rejects.toThrow("append-only");
  });

  it("holds agent work after submitter role revocation, expires lease and preserves partials", async () => {
    const h = await buildHarness();
    const job = await h.submissions.submit(h.projectId, h.editor, h.intent());
    const agent = await h.pair();
    await h.status().claim(agent, job.jobId);
    await h.status().appendProgress(agent, job.jobId, {
      leaseEpoch: 1, status: "running", stageKey: "compile",
      receiptDigest: d("partial"), reasonCode: null,
    });
    await h.db.query("UPDATE vera_project_members SET active=false WHERE project_id=$1 AND actor_id=$2",
      [h.projectId, h.editor.principalId]);
    await expect(h.status().frozenForAgent(agent, job.jobId, 1))
      .rejects.toMatchObject({ status: 403 });
    await expect(h.status().appendProgress(agent, job.jobId, {
      leaseEpoch: 1, status: "failed", stageKey: "compile",
      receiptDigest: null, reasonCode: "aborted",
    })).rejects.toMatchObject({ status: 403 });
    const view = await h.status().get(h.projectId, h.viewer, job.jobId);
    expect(view.events.map((e) => e.status)).toEqual(["queued", "leased", "running"]);
    expect(view.status).toBe("running");
    await expect(h.status().cancel(h.projectId, h.viewer, job.jobId))
      .rejects.toMatchObject({ status: 403 });
  });

  it("allows authorized cancellation but never automatically replays an in-flight effect", async () => {
    const h = await buildHarness();
    const queued = await h.submissions.submit(h.projectId, h.producer, h.intent());
    expect(await h.status().cancel(h.projectId, h.producer, queued.jobId)).toBe("cancelled");
    const running = await h.submissions.submit(h.projectId, h.producer, h.intent());
    const agent = await h.pair();
    await h.status().claim(agent, running.jobId);
    expect(await h.status().cancel(h.projectId, h.producer, running.jobId)).toBe("waiting_reconcile");
    const view = await h.status().get(h.projectId, h.viewer, running.jobId);
    expect(view.events.map((e) => e.status)).toEqual(["queued", "leased", "waiting_reconcile"]);
    await expect(h.status().frozenForAgent(agent, running.jobId, 1))
      .rejects.toMatchObject({ status: 409 });
    await expect(h.submissions.resume(h.projectId, h.producer, running.jobId))
      .rejects.toMatchObject({ status: 409 });
    const uncertain = await h.submissions.submit(h.projectId, h.producer, h.intent());
    await h.status().claim(agent, uncertain.jobId);
    await h.status().appendProgress(agent, uncertain.jobId, {
      leaseEpoch: 1, status: "needs_action", stageKey: "compile",
      receiptDigest: d("partial-native-effect"), reasonCode: "uncertain_effect",
    });
    await expect(h.submissions.resume(h.projectId, h.producer, uncertain.jobId))
      .rejects.toMatchObject({ code: "invalid_transition", status: 409 });
    expect((await h.status().get(h.projectId, h.viewer, uncertain.jobId)).status)
      .toBe("needs_action");
  });
});
