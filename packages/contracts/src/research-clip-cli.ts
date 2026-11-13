#!/usr/bin/env node

/** Read-only Research listing and guarded, atomic script-v2 insertion. */
import {
  closeSync, constants, fchmodSync, fchownSync, fstatSync, fsyncSync, lstatSync,
  openSync, readFileSync, renameSync, unlinkSync, writeFileSync,
  type Stats,
} from "node:fs";
import { randomUUID } from "node:crypto";
import { registerHooks } from "node:module";
import { basename, dirname, join } from "node:path";
import { pathToFileURL } from "node:url";

import type { ScriptDocumentV2 } from "./generated/contracts-v2.js";

export const RESEARCH_CLI_EXIT = {
  ok: 0, refused: 1, usage: 64, parse: 65, read: 66, internal: 70, write: 73,
} as const;

export interface ResearchScriptSnapshot {
  readonly bytes: Buffer;
  readonly stat: Stats;
}

function matchingFile(left: Stats, right: Stats): boolean {
  return left.isFile() && right.isFile() &&
    left.dev === right.dev && left.ino === right.ino &&
    left.mode === right.mode && left.size === right.size &&
    left.mtimeMs === right.mtimeMs && left.ctimeMs === right.ctimeMs;
}

/** Open without following a symlink, including one swapped in during open. */
export function readResearchScript(path: string): ResearchScriptSnapshot {
  // O_NONBLOCK makes a swapped-in FIFO fail fast rather than wait for a writer.
  const fd = openSync(path, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
  try {
    const stat = fstatSync(fd);
    if (!stat.isFile() || !matchingFile(stat, lstatSync(path)) || stat.nlink !== 1 ||
        (typeof process.getuid === "function" && stat.uid !== process.getuid())) {
      throw new Error("The script must be an owned, singly linked, unchanged regular file.");
    }
    const bytes = readFileSync(fd);
    if (!matchingFile(stat, fstatSync(fd)) || !matchingFile(stat, lstatSync(path))) {
      throw new Error("The script changed during reading.");
    }
    return { stat, bytes };
  } finally {
    closeSync(fd);
  }
}

function requireUnchanged(path: string, source: ResearchScriptSnapshot): void {
  let current: ResearchScriptSnapshot;
  try {
    current = readResearchScript(path);
  } catch {
    throw new Error("The script changed since it was read; no replacement was made.");
  }
  if (!matchingFile(source.stat, current.stat) || !source.bytes.equals(current.bytes)) {
    throw new Error("The script changed since it was read; no replacement was made.");
  }
}

/** Write a sibling temp file, retain source permissions, then rename only if still fresh. */
export function replaceResearchScript(
  path: string, source: ResearchScriptSnapshot, content: string,
): void {
  requireUnchanged(path, source);
  const temporaryPath = join(dirname(path), `.${basename(path)}.research-${randomUUID()}.tmp`);
  let fd: number | undefined;
  let created = false;
  try {
    fd = openSync(temporaryPath, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600);
    created = true;
    writeFileSync(fd, content, "utf8");
    // A parent directory's setgid bit may otherwise change the script group.
    // Refuse safely if we cannot retain the original owner and group.
    fchownSync(fd, source.stat.uid, source.stat.gid);
    fchmodSync(fd, source.stat.mode & 0o7777);
    fsyncSync(fd);
    closeSync(fd);
    fd = undefined;
    requireUnchanged(path, source);
    renameSync(temporaryPath, path);
    created = false;
  } finally {
    if (fd !== undefined) closeSync(fd);
    if (created) unlinkSync(temporaryPath);
  }
}

export interface ResearchClipCliIo {
  stdout: (text: string) => void;
  stderr: (text: string) => void;
  env: { bearer: string | undefined; url?: string | undefined };
  request?: typeof fetch;
  readScript: (path: string) => ResearchScriptSnapshot;
  replaceScript: (path: string, source: ResearchScriptSnapshot, content: string) => void;
}

function defaultIo(): ResearchClipCliIo {
  return {
    stdout: (text) => process.stdout.write(text),
    stderr: (text) => process.stderr.write(text),
    env: { bearer: process.env.VERA_RESEARCH_BEARER, url: process.env.VERA_RESEARCH_URL },
    readScript: readResearchScript,
    replaceScript: replaceResearchScript,
  };
}

async function loadCommands() {
  // Direct `node file.ts` resolves internal source .js imports to their .ts files.
  // Vitest can also import this file and inject its own fake fetch + file IO.
  const sourceDirectory = new URL("./", import.meta.url).href;
  const hooks = registerHooks({
    resolve(specifier, context, nextResolve) {
      return nextResolve(
        context.parentURL?.startsWith(sourceDirectory) &&
          specifier.startsWith("./") && specifier.endsWith(".js")
          ? `${specifier.slice(0, -3)}.ts` : specifier,
        context,
      );
    },
  });
  try {
    const [client, commands] = await Promise.all([
      import("./research-clip-client.ts"),
      import("./research-clip-commands.ts"),
    ]);
    return { ...client, ...commands };
  } finally {
    hooks.deregister();
  }
}

function failureMessage(error: unknown): string {
  // Only allow known bridge/command errors; never relay fetch, file-system or
  // unknown exception text, which might include credentials or source content.
  const value = error instanceof Error ? error.message : "";
  if (/^(Research |Set VERA_RESEARCH_BEARER|No visible Research project|Several Research projects|The after-row ID)/u.test(value)) {
    return value;
  }
  if (value.startsWith("Script validation failed") || value.startsWith("Script refused insertion")) {
    return "The script was refused by v2 validation; no changes were written.";
  }
  return "The Research command was refused; no changes were written.";
}

/** Returns a stable exit code; errors are single-line, credential-redacted sentences. */
export async function runResearchClipCli(
  args: readonly string[], overrides: Partial<ResearchClipCliIo> = {},
): Promise<number> {
  const io = { ...defaultIo(), ...overrides };
  const redact = (value: string) => io.env.bearer
    ? value.replaceAll(io.env.bearer, "[redacted]") : value;
  const out = (message: string) => io.stdout(redact(message));
  const err = (message: string) => io.stderr(redact(message) + "\n");
  const mode = args[0];
  if (!(mode === "clips" && args.length === 2 || mode === "add-clip" && args.length === 5)) {
    err("Usage: research:clips -- <project> OR research:add-clip -- <project> <clip UUID> <script.json> <after row UUID>.");
    return RESEARCH_CLI_EXIT.usage;
  }

  try {
    const { createResearchClient, isResearchId, resolveProjectName, formatLoggedResearchClipV2, insertLoggedResearchClipV2 } = await loadCommands();
    const api = createResearchClient({
      bearer: io.env.bearer,
      ...(io.env.url === undefined ? {} : { url: io.env.url }),
      ...(io.request === undefined ? {} : { request: io.request }),
    });
    const projectArg = args[1]!;
    // An explicit UUID is checked by the clips endpoint itself. A broken or
    // unrelated project list must not prevent that authorized direct lookup.
    const projectId = resolveProjectName(projectArg, isResearchId(projectArg) ? [] : await api.projects());
    if (mode === "clips") {
      const clips = await api.clips(projectId);
      if (clips.length === 0) out("No logged clips in this Research project.\n");
      else for (const clip of clips) out(`${formatLoggedResearchClipV2(clip)}\n`);
      return RESEARCH_CLI_EXIT.ok;
    }

    const clip = await api.clip(projectId, args[2]!);
    const path = args[3]!;
    let snapshot: ResearchScriptSnapshot;
    try {
      snapshot = io.readScript(path);
    } catch {
      err("The script could not be read as a regular file; no changes were written.");
      return RESEARCH_CLI_EXIT.read;
    }
    let document: unknown;
    try {
      document = JSON.parse(snapshot.bytes.toString("utf8")) as unknown;
    } catch {
      err("The script is not valid JSON; no changes were written.");
      return RESEARCH_CLI_EXIT.parse;
    }
    if (!document || typeof document !== "object" ||
        !("schemaVersion" in document) || document.schemaVersion !== "script-document/v2") {
      err("The script must be a ScriptDocument v2; no changes were written.");
      return RESEARCH_CLI_EXIT.refused;
    }
    const next = insertLoggedResearchClipV2(document as ScriptDocumentV2, clip, args[4]!);
    try {
      io.replaceScript(path, snapshot, `${JSON.stringify(next, null, 2)}\n`);
    } catch {
      err("The script changed or could not be written; no replacement was made.");
      return RESEARCH_CLI_EXIT.write;
    }
    out("Research clip added to the script.\n");
    return RESEARCH_CLI_EXIT.ok;
  } catch (error: unknown) {
    err(failureMessage(error));
    return RESEARCH_CLI_EXIT.refused;
  }
}

const invokedPath = process.argv[1];
if (invokedPath !== undefined && import.meta.url === pathToFileURL(invokedPath).href) {
  process.exitCode = await runResearchClipCli(process.argv.slice(2));
}
