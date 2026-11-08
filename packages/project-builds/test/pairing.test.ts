import { randomUUID } from "node:crypto";

import { PGlite } from "@electric-sql/pglite";
import {
  applyProjectAuthorizationMigration, ProjectAuthorizationService,
  type SqlPool,
} from "@vera/project-authorization";
import { applyProjectDocumentsMigration } from "@vera/project-documents";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectAgentAuthenticationService } from "../src/agent-auth.js";
import { applyProjectBuildsMigration } from "../src/migration.js";
import {
  AGENT_PROTOCOL_VERSION, HEARTBEAT_FRESH_MS, PAIRING_TTL_MS,
  ProjectAgentPairingService, tokenDigest,
} from "../src/pairing.js";

/* eslint-disable @typescript-eslint/require-await -- PGlite implements the async SQL interface. */
vi.setConfig({ testTimeout: 120_000 });
const databases: PGlite[] = [];
const first = Date.parse("2026-11-08T15:00:00Z");

export async function pairingHarness() {
  const db = new PGlite();
  databases.push(db);
  await db.waitReady;
  await applyProjectAuthorizationMigration(db);
  await applyProjectDocumentsMigration(db);
  await applyProjectBuildsMigration(db);
  const pool: SqlPool = { connect: async () => db };
  const auth = new ProjectAuthorizationService(pool);
  const producer = await auth.resolveActor({ issuer: "test.suite", subject: randomUUID() });
  const editor = await auth.resolveActor({ issuer: "test.suite", subject: randomUUID() });
  const viewer = await auth.resolveActor({ issuer: "test.suite", subject: randomUUID() });
  const outsider = await auth.resolveActor({ issuer: "test.suite", subject: randomUUID() });
  const project = randomUUID();
  const foreign = randomUUID();
  async function createProject(id: string) {
    await db.query(
      "INSERT INTO stt_projects(id,title,created_by,client_create_request_id,create_request_digest) " +
        "VALUES ($1,'Synthetic project',$2,$3,$4)",
      [id, producer.principalId, randomUUID(), "sha256:" + "c".repeat(64)],
    );
    await db.query("INSERT INTO vera_project_members(project_id,actor_id,role) " +
      "VALUES ($1,$2,'producer'),($1,$3,'editor'),($1,$4,'viewer')",
    [id, producer.principalId, editor.principalId, viewer.principalId]);
  }
  await createProject(project);
  await createProject(foreign);
  const clock = { ms: first };
  const now = () => new Date(clock.ms);
  const pairing = new ProjectAgentPairingService(pool, auth, now);
  const agents = new ProjectAgentAuthenticationService(pool, auth, now);
  const offerInput = { agentLabel: "Mac test agent", protocolVersion: AGENT_PROTOCOL_VERSION };
  const consumeInput = (offerToken: string, projectId = project) => ({
    offerToken, projectId, protocolVersion: AGENT_PROTOCOL_VERSION,
    capabilities: ["free_package_v1"],
  });
  return { db, auth, producer, editor, viewer, outsider, project, foreign, clock,
    pairing, agents, offerInput, consumeInput };
}

afterEach(async () => {
  for (const db of databases.splice(0)) await db.close();
});

describe("producer-gated pairing", () => {
  it("restricts producer offers, rejects unknown roles and never persists a secret", async () => {
    const h = await pairingHarness();
    await expect(h.pairing.createOffer(h.project, h.editor, h.offerInput))
      .rejects.toMatchObject({ status: 403 });
    await expect(h.pairing.createOffer(h.project, h.viewer, h.offerInput))
      .rejects.toMatchObject({ status: 403 });
    await expect(h.pairing.createOffer(h.project, h.outsider, h.offerInput))
      .rejects.toMatchObject({ status: 403 });
    await expect(h.pairing.createOffer(h.project, h.producer, {
      ...h.offerInput, protocolVersion: "v2",
    })).rejects.toMatchObject({ status: 400 });
    await expect(h.pairing.createOffer(h.project, h.producer, {
      ...h.offerInput, agentLabel: "../unsafe\nlabel",
    })).rejects.toMatchObject({ status: 400 });
    const offer = await h.pairing.createOffer(h.project, h.producer, h.offerInput);
    expect(offer.offerToken).toMatch(/^stto_[A-Za-z0-9_-]{43}$/u);
    expect(offer.expiresAt).toBe(new Date(first + PAIRING_TTL_MS).toISOString());
    const stored = await h.db.query<{ offer_digest: string; created_by: string }>(
      "SELECT offer_digest,created_by FROM stt_build_pairing_offers WHERE id=$1", [offer.offerId],
    );
    expect(stored.rows[0]?.offer_digest).toBe(tokenDigest(offer.offerToken));
    expect(stored.rows[0]?.offer_digest).not.toContain(offer.offerToken);
    expect(stored.rows[0]?.created_by).toBe(h.producer.principalId);
  });

  it("consumes once, binds project and version; refuses replay and unrecognized capabilities", async () => {
    const h = await pairingHarness();
    const offer = await h.pairing.createOffer(h.project, h.producer, h.offerInput);
    await expect(h.pairing.consumeOffer(h.consumeInput(offer.offerToken, h.foreign)))
      .rejects.toMatchObject({ status: 401 });
    await expect(h.pairing.consumeOffer({ ...h.consumeInput(offer.offerToken),
      capabilities: ["fake_native_success"] })).rejects.toMatchObject({ status: 400 });
    await expect(h.pairing.consumeOffer({ ...h.consumeInput(offer.offerToken),
      capabilities: ["free_package_v1", "free_package_v1"] }))
      .rejects.toMatchObject({ status: 400 });
    const paired = await h.pairing.consumeOffer(h.consumeInput(offer.offerToken));
    expect(paired.agentToken).toMatch(/^sttag_[A-Za-z0-9_-]{43}$/u);
    expect(paired.agentToken).not.toBe(offer.offerToken);
    await expect(h.pairing.consumeOffer(h.consumeInput(offer.offerToken)))
      .rejects.toMatchObject({ status: 401 });
    const stored = await h.db.query<{ credential_digest: string; credential_version: number }>(
      "SELECT credential_digest,credential_version FROM stt_project_build_agents WHERE id=$1",
      [paired.agentId],
    );
    expect(stored.rows[0]?.credential_digest).toBe(tokenDigest(paired.agentToken));
    expect(stored.rows[0]?.credential_version).toBe(1);
    expect(JSON.stringify(stored.rows)).not.toContain(paired.agentToken);
  });

  it("refuses an offer exactly at TTL and leaves it unconsumed", async () => {
    const h = await pairingHarness();
    const offer = await h.pairing.createOffer(h.project, h.producer, h.offerInput);
    h.clock.ms += PAIRING_TTL_MS;
    await expect(h.pairing.consumeOffer(h.consumeInput(offer.offerToken)))
      .rejects.toMatchObject({ status: 401 });
    const rows = await h.db.query<{ consumed_at: string | null }>(
      "SELECT consumed_at FROM stt_build_pairing_offers WHERE id=$1", [offer.offerId],
    );
    expect(rows.rows[0]?.consumed_at).toBeNull();
    h.clock.ms -= 1;
    const paired = await h.pairing.consumeOffer(h.consumeInput(offer.offerToken));
    expect(paired.credentialVersion).toBe(1);
  });

  it("denies cancelled offers and issuer role revoked before or after pairing", async () => {
    const h = await pairingHarness();
    const cancelled = await h.pairing.createOffer(h.project, h.producer, h.offerInput);
    await h.pairing.revokeOffer(h.project, h.producer, cancelled.offerId);
    await expect(h.pairing.consumeOffer(h.consumeInput(cancelled.offerToken)))
      .rejects.toMatchObject({ status: 401 });
    const offer = await h.pairing.createOffer(h.project, h.producer, h.offerInput);
    await h.db.query("UPDATE vera_project_members SET active=false WHERE project_id=$1 " +
      "AND actor_id=$2", [h.project, h.producer.principalId]);
    await expect(h.pairing.consumeOffer(h.consumeInput(offer.offerToken)))
      .rejects.toMatchObject({ status: 401 });
    await h.db.query("UPDATE vera_project_members SET active=true WHERE project_id=$1 " +
      "AND actor_id=$2", [h.project, h.producer.principalId]);
    const paired = await h.pairing.consumeOffer(h.consumeInput(offer.offerToken));
    await h.agents.heartbeat({ projectId: h.project, agentToken: paired.agentToken, credentialVersion: 1 });
    await h.db.query("UPDATE vera_project_members SET role='viewer' WHERE project_id=$1 " +
      "AND actor_id=$2", [h.project, h.producer.principalId]);
    await expect(h.agents.pollAssignedJobs({ projectId: h.project,
      agentToken: paired.agentToken, credentialVersion: 1 })).rejects.toMatchObject({ status: 401 });
  });

  it("supports scoped reconnect, bounded readiness, rotation and permanent revocation", async () => {
    const h = await pairingHarness();
    const offer = await h.pairing.createOffer(h.project, h.producer, h.offerInput);
    const paired = await h.pairing.consumeOffer(h.consumeInput(offer.offerToken));
    const credential = { projectId: h.project, agentToken: paired.agentToken, credentialVersion: 1 };
    expect((await h.pairing.readiness(h.project, h.viewer)).agents[0]?.connected).toBe(false);
    await expect(h.agents.heartbeat({ ...credential, projectId: h.foreign }))
      .rejects.toMatchObject({ status: 401 });
    await expect(h.agents.heartbeat({ ...credential,
      agentToken: "sttag_" + "a".repeat(43) }))
      .rejects.toMatchObject({ status: 401 });
    await expect(h.agents.heartbeat({ ...credential, credentialVersion: 2 }))
      .rejects.toMatchObject({ status: 401 });
    expect((await h.agents.heartbeat(credential)).authenticated).toBe(true);
    expect((await h.agents.heartbeat(credential)).authenticated).toBe(true); // reconnect
    const ready = await h.pairing.readiness(h.project, h.viewer);
    expect(ready).toMatchObject({ canBuild: false, nativeVerified: false });
    expect(ready.agents[0]?.connected).toBe(true);
    h.clock.ms += HEARTBEAT_FRESH_MS;
    expect((await h.pairing.readiness(h.project, h.viewer)).agents[0]?.connected).toBe(false);
    await expect(h.pairing.rotateAgent(h.project, h.editor, paired.agentId))
      .rejects.toMatchObject({ status: 403 });
    const rotated = await h.pairing.rotateAgent(h.project, h.producer, paired.agentId);
    expect(rotated.credentialVersion).toBe(2);
    await expect(h.agents.heartbeat(credential)).rejects.toMatchObject({ status: 401 });
    const current = { projectId: h.project, agentToken: rotated.agentToken, credentialVersion: 2 };
    await h.agents.heartbeat(current);
    await expect(h.pairing.revokeAgent(h.foreign, h.producer, paired.agentId))
      .rejects.toMatchObject({ status: 404 });
    await expect(h.pairing.revokeAgent(h.project, h.editor, paired.agentId))
      .rejects.toMatchObject({ status: 403 });
    await h.pairing.revokeAgent(h.project, h.producer, paired.agentId);
    await expect(h.agents.heartbeat(current)).rejects.toMatchObject({ status: 401 });
    await expect(h.pairing.rotateAgent(h.project, h.producer, paired.agentId))
      .rejects.toMatchObject({ status: 404 });
    expect((await h.pairing.readiness(h.project, h.viewer)).agents).toHaveLength(0);
  });

  it("polls only actively assigned, in-project unexpired jobs; never creates claims", async () => {
    const h = await pairingHarness();
    const offer1 = await h.pairing.createOffer(h.project, h.producer, h.offerInput);
    const offer2 = await h.pairing.createOffer(h.project, h.producer, h.offerInput);
    const paired1 = await h.pairing.consumeOffer(h.consumeInput(offer1.offerToken));
    const paired2 = await h.pairing.consumeOffer(h.consumeInput(offer2.offerToken));
    const job = async (project: string, agentId: string, expiresAt: string | null) => {
      const jobId = randomUUID();
      const digest = "sha256:" + "a".repeat(64);
      await h.db.query("INSERT INTO stt_build_submissions" +
        "(id,project_id,target_id,submitted_by,idempotency_key,request_digest,build_class," +
        "mode,expected_revision,document_id,document_json,document_digest," +
        "settings_revision,settings_json,settings_digest,snapshot_digest) " +
        "VALUES($1,$2,$3,$4,$5,$6,'preview','free',0,$7,'{}',$8,1,'{}',$9,$10)",
      [jobId, project, randomUUID(), h.producer.principalId, randomUUID(), digest,
        randomUUID(), digest, digest, digest]);
      await h.db.query("INSERT INTO stt_build_dispatches" +
        "(project_id,job_id,assigned_agent_id,status,lease_epoch,lease_expires_at) " +
        "VALUES($1,$2,$3,'leased',5,$4)", [project, jobId, agentId, expiresAt]);
      return jobId;
    };
    const included = await job(h.project, paired1.agentId, new Date(first + 60_000).toISOString());
    await job(h.project, paired2.agentId, null);
    await job(h.project, paired1.agentId, new Date(first - 1).toISOString());
    const credential = { projectId: h.project, agentToken: paired1.agentToken, credentialVersion: 1 };
    expect(await h.agents.pollAssignedJobs(credential)).toEqual([{
      jobId: included, status: "leased", leaseEpoch: 5,
      leaseExpiresAt: new Date(first + 60_000).toISOString(),
    }]);
    await expect(h.agents.pollAssignedJobs({ ...credential, projectId: h.foreign }))
      .rejects.toMatchObject({ status: 401 });
    h.clock.ms += 60_000;
    expect(await h.agents.pollAssignedJobs(credential)).toEqual([]);
    await h.pairing.revokeAgent(h.project, h.producer, paired1.agentId);
    await expect(h.agents.pollAssignedJobs(credential)).rejects.toMatchObject({ status: 401 });
    expect((await h.db.query("SELECT * FROM stt_build_dispatches")).rows).toHaveLength(3);
  });
});
