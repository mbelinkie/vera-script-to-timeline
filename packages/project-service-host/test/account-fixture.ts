import { createHash, randomBytes, randomUUID } from "node:crypto";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { PGlite } from "@electric-sql/pglite";
import { applyProjectAuthorizationMigration, ProjectAuthorizationService, type SqlClient } from "@vera/project-authorization";
import { applyProjectBuildsMigration } from "@vera/project-builds";
import { applyProjectCommentsMigration, applyProjectDocumentsMigration, applyProjectHistoryMigration,
  applyProjectIdeasMigration, applyProjectSubtitleCopiesMigration, ProjectDocumentService } from "@vera/project-documents";
import { applyProjectCollaborationMigration } from "@vera/project-collaboration";
import type { PrincipalRef } from "@vera/contracts";
import type { ScriptDocumentV2 } from "@vera/contracts/v2";
import { startQaServer } from "../src/serve.js";
import type { QaPgPool } from "../src/pg-pool.js";
import type { AccountMode } from "../src/account-session.js";
import { unusedLoopbackPort } from "./loopback-port.js";

/** Synthetic credentials never accepted outside this disposable harness. */
export async function accountFixture(unconfigured = false) {
  const db = new PGlite(); await db.waitReady;
  let previous = Promise.resolve();
  const pool: QaPgPool = { connect: async () => {
    const wait = previous;
    let unlock = () => {};
    previous = new Promise<void>((resolve) => { unlock = resolve; }); await wait;
    return { query: async <R>(sql: string, parameters?: readonly unknown[]) =>
      await db.query<R>(sql, parameters ? [...parameters] : []),
    exec: async (sql: string) => await db.exec(sql), release: unlock } satisfies SqlClient;
  }, close: async () => await db.close() };
  const directory = await mkdtemp(join(tmpdir(), "vera-account-"));
  const qaToken = randomBytes(32).toString("hex");
  const identityFile = join(directory, "identity.json");
  await writeFile(identityFile, JSON.stringify({ version: 1, credentials: [{
    tokenSha256: createHash("sha256").update(qaToken).digest("hex"),
    issuer: "urn:vera:stt:development-qa", subject: "local-qa-only",
  }] }), { mode: 0o600 });
  const tokens = new Map<string, string>();
  const sessions = new Map<string, { sessionId: string; authorization: string; csrfToken: string }>();
  const cookies: Record<string, string> = {};
  const bearers: Record<string, string> = {};
  for (const who of ["owner", "editor", "viewer", "outsider"]) {
    const bearer = randomBytes(32).toString("hex"); tokens.set(`Bearer ${bearer}`, who);
    const cookie = randomBytes(32).toString("hex"); cookies[who] = `qa_account=${cookie}`;
    bearers[who] = `Bearer ${bearer}`;
    sessions.set(cookies[who], { sessionId: cookie, authorization: `Bearer ${bearer}`,
      csrfToken: randomBytes(32).toString("hex") });
  }
  const mode: AccountMode = {
    identity: { authenticate: (request) => {
      const subject = tokens.get(request.headers.get("authorization") ?? "");
      if (!subject) return Promise.reject(new Error("unverified"));
      return Promise.resolve({ issuer: "https://account.synthetic.test", subject });
    } },
    ...(!unconfigured && { sessions: {
      session: (request: Request) => Promise.resolve(sessions.get(request.headers.get("cookie") ?? "") ?? null),
      signIn: () => Promise.resolve(Response.json({ url: "/synthetic-login" })),
      signOut: (request: Request) => {
        sessions.delete(request.headers.get("cookie") ?? "");
        return Promise.resolve(Response.json({ signedOut: true }));
      },
    } }),
  };
  const port = await unusedLoopbackPort();
  const host = await startQaServer({ deploymentMode: "development-qa", bindHost: "127.0.0.1", port,
    sourceSha: "a".repeat(40), databaseUrl: "postgresql://qa:synthetic@127.0.0.1:5432/vera_stt_qa_account",
    databaseName: "vera_stt_qa_account", databaseUser: "qa", identityFile, authoringToken: qaToken,
  }, { accountMode: mode, createPool: () => pool, migrate: async () => {
    await applyProjectAuthorizationMigration(db); await applyProjectDocumentsMigration(db);
    await applyProjectCommentsMigration(db); await applyProjectHistoryMigration(db);
    await applyProjectIdeasMigration(db); await applyProjectSubtitleCopiesMigration(db);
    await applyProjectBuildsMigration(db); await applyProjectCollaborationMigration(db); return [];
  } });
  const origin = `http://127.0.0.1:${port}`;
  const auth = new ProjectAuthorizationService(pool);
  const documents = new ProjectDocumentService(pool, auth);
  const actors: Record<string, PrincipalRef> = Object.fromEntries(await Promise.all(Object.keys(cookies).map(async (who) => [who,
    await auth.resolveActor({ issuer: "https://account.synthetic.test", subject: who })] as const)));
  const projectId = randomUUID();
  const document = (JSON.parse(readFileSync(new URL(
    "../../../tests/data/authoring_v2/issue_173/compiler/flat.input.golden.json", import.meta.url), "utf8")) as { document: ScriptDocumentV2 }).document;
  document.projectId = projectId; document.id = randomUUID(); document.title = "Synthetic account script";
  await documents.createProject(actors.owner!, { projectId, title: document.title, clientRequestId: randomUUID(), document });
  await auth.changeMembership(projectId, actors.owner!, actors.editor!.principalId, "editor");
  await auth.changeMembership(projectId, actors.owner!, actors.viewer!.principalId, "viewer");
  return { origin, projectId, document, auth, documents, actors, cookies, bearers, mode, qaToken,
    host, db, pool, sessions,
    stop: async () => { await host.stop(); await rm(directory, { recursive: true, force: true }); },
    request: (path: string, who = "owner", options: RequestInit = {}) => fetch(origin + path, {
      ...options, headers: { cookie: cookies[who]!, "sec-fetch-site": "same-origin", "x-vera-authoring": "1",
        origin, "x-vera-csrf": sessions.get(cookies[who]!)?.csrfToken ?? "", ...options.headers,
      },
    }),
  };
}
