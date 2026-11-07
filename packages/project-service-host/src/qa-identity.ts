import { createHash, timingSafeEqual } from "node:crypto";
import { constants } from "node:fs";
import { lstat, open, realpath } from "node:fs/promises";
import { isAbsolute, relative } from "node:path";

import { ProjectAuthError, type SuiteIdentityPort } from "@vera/project-authorization";

/** Offline-issued 32-byte hex tokens; only their SHA-256 digests are stored. */
interface Credential {
  tokenSha256: Buffer;
  issuer: string;
  subject: string;
}

export class QaIdentityRefusal extends Error {
  override readonly name = "QaIdentityRefusal";
  constructor() { super("unsafe development-QA identity configuration"); }
}

const TOKEN = /^[a-f0-9]{64}$/u;
const ISSUER = "urn:vera:stt:development-qa";
const SUBJECT = /^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$/u;
const MAX_FILE_BYTES = 64 * 1024;
const denied = (): ProjectAuthError => new ProjectAuthError("authentication_required", 401);

function exactKeys(record: Record<string, unknown>, keys: readonly string[]): boolean {
  const actual = Object.keys(record);
  return actual.length === keys.length && actual.every((key) => keys.includes(key));
}

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown> : null;
}

/** Open without following the final symlink; verify the same file before reading. */
async function readPrivateFile(path: string, repositoryRoot?: string): Promise<string> {
  try {
    if (repositoryRoot) {
      const root = await realpath(repositoryRoot);
      const actual = await realpath(path);
      const rel = relative(root, actual);
      if (rel === "" || (!rel.startsWith("../") && rel !== ".." &&
          !rel.startsWith("..\\") && !isAbsolute(rel))) throw new QaIdentityRefusal();
    }
    const before = await lstat(path);
    if (!before.isFile() || before.isSymbolicLink() || before.nlink !== 1 ||
        (before.mode & 0o777) !== 0o600 || before.size < 1 || before.size > MAX_FILE_BYTES ||
        (process.getuid !== undefined && before.uid !== process.getuid())) {
      throw new QaIdentityRefusal();
    }
    const handle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
    try {
      const after = await handle.stat();
      if (!after.isFile() || after.dev !== before.dev || after.ino !== before.ino ||
          after.nlink !== 1 || (after.mode & 0o777) !== 0o600 ||
          after.size < 1 || after.size > MAX_FILE_BYTES ||
          (process.getuid !== undefined && after.uid !== process.getuid())) {
        throw new QaIdentityRefusal();
      }
      const contents = await handle.readFile("utf8");
      if (Buffer.byteLength(contents, "utf8") > MAX_FILE_BYTES) throw new QaIdentityRefusal();
      return contents;
    } finally {
      await handle.close();
    }
  } catch {
    // Neither the path, the file contents, nor OS error text is public.
    throw new QaIdentityRefusal();
  }
}

/** Load once on startup. No route can reload, issue or change QA credentials. */
export async function loadQaIdentity(path: string, repositoryRoot?: string): Promise<SuiteIdentityPort> {
  let value: unknown;
  try { value = JSON.parse(await readPrivateFile(path, repositoryRoot)) as unknown; }
  catch { throw new QaIdentityRefusal(); }
  const root = record(value);
  if (!root || !exactKeys(root, ["version", "credentials"]) || root.version !== 1 ||
      !Array.isArray(root.credentials) || root.credentials.length < 1 ||
      root.credentials.length > 32) throw new QaIdentityRefusal();

  const credentials: Credential[] = [];
  const seenDigests = new Set<string>();
  const seenSubjects = new Set<string>();
  for (const input of root.credentials as unknown[]) {
    const item = record(input);
    if (!item || !exactKeys(item, ["tokenSha256", "issuer", "subject"]) ||
        typeof item.tokenSha256 !== "string" || !TOKEN.test(item.tokenSha256) ||
        item.issuer !== ISSUER || typeof item.subject !== "string" ||
        !SUBJECT.test(item.subject) || seenDigests.has(item.tokenSha256) ||
        seenSubjects.has(item.subject)) throw new QaIdentityRefusal();
    seenDigests.add(item.tokenSha256);
    seenSubjects.add(item.subject);
    credentials.push({ tokenSha256: Buffer.from(item.tokenSha256, "hex"),
      issuer: item.issuer, subject: item.subject });
  }

  return {
    authenticate: (request: Request) => {
      const authorization = request.headers.get("authorization");
      const match = /^Bearer ([a-f0-9]{64})$/iu.exec(authorization ?? "");
      if (!match) return Promise.reject(denied());
      // Cannot prove entropy from a digest; reject obviously patterned tokens
      // even if an operator mistakenly hashed one into the private file.
      if (new Set(match[1]!.toLowerCase()).size < 8) return Promise.reject(denied());
      const incoming = createHash("sha256").update(match[1]!, "ascii").digest();
      let matching = -1;
      // Compare every candidate; never identify an actor from client-supplied headers.
      for (let i = 0; i < credentials.length; i += 1) {
        if (timingSafeEqual(incoming, credentials[i]!.tokenSha256)) matching = i;
      }
      if (matching < 0) return Promise.reject(denied());
      const actor = credentials[matching]!;
      return Promise.resolve({ issuer: actor.issuer, subject: actor.subject });
    },
  };
}
