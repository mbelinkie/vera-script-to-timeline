import { isAbsolute, relative, resolve } from "node:path";

/** Local, never publicly reachable acceptance mode; not a hosted release. */
export interface QaConfig {
  readonly deploymentMode: "development-qa";
  readonly bindHost: "127.0.0.1";
  readonly port: number;
  readonly sourceSha: string;
  readonly databaseUrl: string;
  readonly databaseName: string;
  readonly databaseUser: string;
  readonly identityFile: string;
}

export class QaConfigError extends Error {
  override readonly name = "QaConfigError";
  constructor() {
    // Never interpolate values from environment, especially URLs or paths.
    super("invalid development-QA configuration");
  }
}

const SHA = /^[0-9a-f]{40}$/u;
// PostgreSQL silently truncates identifiers past 63 bytes: forbid ambiguity.
const QA_DB = /^vera_stt_qa_[a-z0-9][a-z0-9_]{2,50}$/u;
const SAFE_USER = /^[a-z_][a-z0-9_]{0,62}$/u;
const PORT = /^[1-9][0-9]{3,4}$/u;

function parseDatabaseUrl(value: string | undefined): {
  databaseUrl: string;
  databaseName: string;
  databaseUser: string;
} {
  if (!value || value.length > 4096) throw new QaConfigError();
  let url: URL;
  try { url = new URL(value); } catch { throw new QaConfigError(); }
  // Reject libpq overrides (options, service, host, search_path, etc.),
  // fragments, sockets, public hosts and accidental connection defaults.
  if (!(["postgres:", "postgresql:"].includes(url.protocol)) ||
      url.hostname !== "127.0.0.1" ||
      (url.port !== "" && (!/^\d+$/u.test(url.port) || Number(url.port) < 1)) ||
      url.search !== "" || url.hash !== "" ||
      !/^\/[a-z0-9_]+$/u.test(url.pathname) ||
      !QA_DB.test(url.pathname.slice(1)) ||
      !SAFE_USER.test(url.username) ||
      ["postgres", "root"].includes(url.username) ||
      url.password.length === 0) throw new QaConfigError();
  return { databaseUrl: value, databaseName: url.pathname.slice(1), databaseUser: url.username };
}

/** The source SHA must be independently supplied by the host's trusted build checkout. */
export function parseQaConfig(
  env: NodeJS.ProcessEnv,
  checkedOutSourceSha: string,
  repositoryRoot: string = process.cwd(),
): QaConfig {
  if (env.VERA_STT_MODE !== "development-qa" ||
      env.VERA_STT_QA_HOST !== "127.0.0.1" ||
      !SHA.test(checkedOutSourceSha) ||
      !SHA.test(env.VERA_STT_SOURCE_SHA ?? "") ||
      env.VERA_STT_SOURCE_SHA !== checkedOutSourceSha ||
      !PORT.test(env.VERA_STT_QA_PORT ?? "")) throw new QaConfigError();

  const port = Number(env.VERA_STT_QA_PORT);
  if (!Number.isSafeInteger(port) || port < 1024 || port > 65535) {
    throw new QaConfigError();
  }

  const identityFile = env.VERA_STT_QA_IDENTITY_FILE;
  if (!identityFile || !isAbsolute(identityFile) || identityFile.includes("\0")) {
    throw new QaConfigError();
  }
  const file = resolve(identityFile);
  const rootRelative = relative(resolve(repositoryRoot), file);
  if (rootRelative === "" ||
      (rootRelative !== ".." && !rootRelative.startsWith("../") &&
       !rootRelative.startsWith("..\\") && !isAbsolute(rootRelative))) {
    throw new QaConfigError();
  }
  // This is a *path* check, not a permission or symlink check. The phase-2
  // identity loader must use lstat/open/fstat on the private 0600 file.
  const database = parseDatabaseUrl(env.VERA_STT_QA_DATABASE_URL);
  return {
    deploymentMode: "development-qa",
    bindHost: "127.0.0.1",
    port,
    sourceSha: checkedOutSourceSha,
    identityFile: file,
    ...database,
  };
}
