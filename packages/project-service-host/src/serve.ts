import { execFileSync } from "node:child_process";
import { realpathSync } from "node:fs";
import type { Server } from "node:http";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { ProjectAuthorizationService } from "@vera/project-authorization";
import { createProjectApiHandler, ProjectDocumentService } from "@vera/project-documents";

import { listenQaHttp } from "./http.js";
import { loadQaIdentity } from "./qa-identity.js";
import { parseQaConfig, type QaConfig } from "./qa-config.js";
import { applyQaMigrations } from "./migrate.js";
import { createQaPgPool, type QaPgPool } from "./pg-pool.js";

export class QaStartupRefusal extends Error {
  override readonly name = "QaStartupRefusal";
  constructor() { super("development-QA service unavailable"); }
}

const REPOSITORY_ROOT = fileURLToPath(new URL("../../../", import.meta.url));

function protectedCheckoutRoots(): readonly string[] {
  // A detached worktree can live outside the main repository. Secrets must be
  // outside BOTH trees, including paths that enter via parent symlinks.
  const commonGitDir = execFileSync("git", ["rev-parse", "--git-common-dir"], {
    cwd: REPOSITORY_ROOT, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"],
  }).trim();
  return [REPOSITORY_ROOT, dirname(realpathSync(resolve(REPOSITORY_ROOT, commonGitDir)))];
}

export interface QaRunningServer {
  readonly server: Server;
  stop(): Promise<void>;
}

/** Injectable infrastructure for isolated host tests; production uses real Postgres. */
export interface QaHostInfrastructure {
  createPool?: (config: QaConfig, onError: () => void) => QaPgPool;
  migrate?: typeof applyQaMigrations;
}

/** Fail before binding if credentials, migrations or database checks fail. */
export async function startQaServer(
  config: QaConfig,
  infrastructure: QaHostInfrastructure = {},
): Promise<QaRunningServer> {
  if (config.deploymentMode !== "development-qa" || config.bindHost !== "127.0.0.1" ||
      !Number.isSafeInteger(config.port) || config.port < 1024 || config.port > 65535) {
    throw new QaStartupRefusal();
  }
  let pool: QaPgPool | undefined;
  let server: Server | undefined;
  let closing: Promise<void> | undefined;
  let idleFailed = false;
  const stop = (): Promise<void> => {
    closing ??= (async () => {
      if (server?.listening) {
        await new Promise<void>((resolve) => {
          // Bound shutdown even if a client stops reading an active response.
          const timeout = setTimeout(() => { server?.closeAllConnections(); }, 5_000);
          timeout.unref();
          try {
            server!.close(() => { clearTimeout(timeout); resolve(); });
          } catch {
            clearTimeout(timeout);
            resolve();
          }
        });
      }
      await pool?.close();
    })();
    return closing;
  };
  try {
    const identity = await loadQaIdentity(config.identityFile, protectedCheckoutRoots());
    pool = (infrastructure.createPool ?? createQaPgPool)(config, () => {
      idleFailed = true;
      void stop().catch(() => undefined);
    });
    await (infrastructure.migrate ?? applyQaMigrations)(pool, config);
    if (idleFailed) throw new QaStartupRefusal();
    const auth = new ProjectAuthorizationService(pool);
    const documents = new ProjectDocumentService(pool, auth);
    server = await listenQaHttp(config.bindHost, config.port,
      createProjectApiHandler({ identity, authorization: auth, documents }));
    if (idleFailed) throw new QaStartupRefusal();
    return { server, stop };
  } catch {
    await stop().catch(() => undefined);
    throw new QaStartupRefusal();
  }
}

/** Only the trusted checkout's own HEAD is used for source pin verification. */
export async function serveQaFromEnvironment(env: NodeJS.ProcessEnv = process.env): Promise<QaRunningServer> {
  try {
    const sha = execFileSync("git", ["rev-parse", "HEAD"], {
      cwd: REPOSITORY_ROOT, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"],
    }).trim();
    const dirty = execFileSync("git", ["status", "--porcelain", "--untracked-files=normal"], {
      cwd: REPOSITORY_ROOT, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"],
    });
    if (dirty.trim() !== "") throw new QaStartupRefusal();
    return await startQaServer(parseQaConfig(env, sha, REPOSITORY_ROOT));
  } catch {
    throw new QaStartupRefusal();
  }
}

async function main(): Promise<void> {
  const running = await serveQaFromEnvironment();
  const addr = running.server.address();
  if (typeof addr !== "object" || addr === null) throw new QaStartupRefusal();
  // Do not print environment, database URLs, identity paths, actors or tokens.
  process.stdout.write(`STT development-QA listening on 127.0.0.1:${addr.port}\n`);
  const shutdown = () => { void running.stop().catch(() => { process.exitCode = 1; }); };
  process.once("SIGINT", shutdown);
  process.once("SIGTERM", shutdown);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  void main().catch(() => {
    process.stderr.write("STT development-QA host unavailable\n");
    process.exitCode = 1;
  });
}
