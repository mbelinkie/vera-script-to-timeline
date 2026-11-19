#!/usr/bin/env node

/** Local Research commands and guarded, atomic script-v2 edits. */
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

const usageByMode = new Map<string, [number, string]>([
  ["clips", [2, "research:clips -- <project>"]],
  ["add-clip", [5, "research:add-clip -- <project> <clip UUID> <script.json> <after row UUID>"]],
  ["refresh-citations", [3, "research:refresh-citations -- <project> <script.json>"]],
  ["source-list", [3, "export:source-list -- <project> <script.json>"]],
  ["edit-use-citation", [5, "research:edit-use-citation -- <project> <script.json> <quote box ID> <text or --reset>"]],
  ["edit-quote-citation", [4, "research:edit-quote-citation -- <project> <quote UUID> <text or --reset>"]],
]);

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
    const [client, commands, citations, validation] = await Promise.all([
      import("./research-clip-client.ts"),
      import("./research-clip-commands.ts"),
      import("./research-citation-commands.ts"),
      import("./authoring-v2-validation.ts"),
    ]);
    return { ...client, ...commands, ...citations, ...validation };
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
  const usage = usageByMode.get(mode ?? "");
  if (args.length !== usage?.[0]) {
    err(usage ? `Usage: npm run ${usage[1]}.` : "Choose a Research command from npm run.");
    return RESEARCH_CLI_EXIT.usage;
  }

  try {
    const {
      createResearchClient, isResearchId, resolveProjectName, formatLoggedResearchClipV2, insertLoggedResearchClipV2,
      refreshScriptCitations, editScriptCitation, exportScriptSources, validateScriptDocumentV2,
    } = await loadCommands();
    const api = createResearchClient({
      bearer: io.env.bearer,
      ...(io.env.url === undefined ? {} : { url: io.env.url }),
      ...(io.request === undefined ? {} : { request: io.request }),
    });
    const projectArg = args[1]!;
    // Record endpoints authorize explicit project IDs without a project-list request.
    const projectId = resolveProjectName(projectArg, isResearchId(projectArg) ? [] : await api.projects());
    if (mode === "clips") {
      const clips = await api.clips(projectId);
      if (clips.length === 0) out("No logged clips in this Research project.\n");
      else for (const clip of clips) out(`${formatLoggedResearchClipV2(clip)}\n`);
      return RESEARCH_CLI_EXIT.ok;
    }
    if (mode === "edit-quote-citation") {
      const text = args[3]!;
      await api.setQuoteCitation(projectId, args[2]!, text === "--reset" ? undefined : text);
      out("Research quote citation saved. Refresh placed citations to apply it to an existing script.\n");
      return RESEARCH_CLI_EXIT.ok;
    }

    const clip = mode === "add-clip" ? await api.clip(projectId, args[2]!) : undefined;
    const path = (mode === "add-clip" ? args[3] : args[2])!;
    let snapshot: ResearchScriptSnapshot;
    try {
      snapshot = io.readScript(path);
    } catch {
      err("The script could not be read as a regular file; no changes were written.");
      return RESEARCH_CLI_EXIT.read;
    }
    let document: unknown;
    try {
      document = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(snapshot.bytes)) as unknown;
    } catch {
      err("The script is not valid JSON; no changes were written.");
      return RESEARCH_CLI_EXIT.parse;
    }
    if (!document || typeof document !== "object" ||
        !("schemaVersion" in document) || document.schemaVersion !== "script-document/v2") {
      err("The script must be a ScriptDocument v2; no changes were written.");
      return RESEARCH_CLI_EXIT.refused;
    }
    const script = document as ScriptDocumentV2;
    if (mode !== "add-clip" && !validateScriptDocumentV2(script).valid) {
      throw new Error("Script validation failed");
    }
    if (mode === "source-list") {
      const list = await exportScriptSources(script, projectId, api);
      if (list) out(`${list.replace(/\p{Cc}/gu, (character) => character === "\n" ? "\n" : "")}\n`);
      return RESEARCH_CLI_EXIT.ok;
    }
    const next = clip ? insertLoggedResearchClipV2(script, clip, args[4]!) : mode === "edit-use-citation"
      ? await editScriptCitation(script, projectId, api, args[3]!, args[4]!)
      : await refreshScriptCitations(script, projectId, api);
    if (next === script) {
      out("Script citations are already current.\n");
      return RESEARCH_CLI_EXIT.ok;
    }
    if (!clip && !validateScriptDocumentV2(next).valid) throw new Error("Script validation failed after citation edit");
    try {
      io.replaceScript(path, snapshot, `${JSON.stringify(next, null, 2)}\n`);
    } catch {
      err("The script changed or could not be written; no replacement was made.");
      return RESEARCH_CLI_EXIT.write;
    }
    out(clip ? "Research clip added to the script.\n" : "Script citations saved.\n");
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
