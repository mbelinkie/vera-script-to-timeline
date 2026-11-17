#!/usr/bin/env node

import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

import { validateScriptDocumentV2 } from "@vera/contracts/authoring-v2";

import { DEFAULT_AUTHORING_PORT } from "./authoring.js";

const UUID = /^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$/u;
const TOKEN = /^[a-f0-9]{64}$/u;
const REQUEST_TIMEOUT_MS = 10_000;

export const EXPORT_AUTHORING_EXIT = {
  ok: 0,
  refused: 1,
  usage: 64,
  write: 73,
} as const;

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

export async function runExportAuthoringCli(
  args: readonly string[],
  env: NodeJS.ProcessEnv = process.env,
  request: typeof fetch = fetch,
): Promise<number> {
  const suppliedProjectId = args[0];
  const requestedOutputPath = args[1];
  if (args.length !== 2 || !suppliedProjectId || !UUID.test(suppliedProjectId) || !requestedOutputPath) {
    process.stderr.write(
      "USAGE: export-authoring requires a project ID and output JSON path.\n" +
      "Usage: npm run export:script -- <project-id> <output.json>\n",
    );
    return EXPORT_AUTHORING_EXIT.usage;
  }
  const projectId = suppliedProjectId.toLowerCase();
  const outputPath = resolve(env.INIT_CWD || process.cwd(), requestedOutputPath);

  const token = env.VERA_STT_QA_AUTHORING_TOKEN;
  if (!token || !TOKEN.test(token)) {
    process.stderr.write("AUTH_ERROR: Set VERA_STT_QA_AUTHORING_TOKEN to the local QA authoring token.\n");
    return EXPORT_AUTHORING_EXIT.refused;
  }

  const portValue = env.VERA_STT_QA_PORT ?? DEFAULT_AUTHORING_PORT;
  const port = Number(portValue);
  if (!/^[0-9]{4,5}$/u.test(portValue) || !Number.isSafeInteger(port) || port < 1024 || port > 65535) {
    process.stderr.write("CONFIG_ERROR: VERA_STT_QA_PORT must be a valid localhost port.\n");
    return EXPORT_AUTHORING_EXIT.refused;
  }

  let response: Response;
  try {
    response = await request(
      `http://127.0.0.1:${port}/v1/projects/${projectId}/document`,
      {
        method: "GET",
        headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
        redirect: "error",
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      },
    );
  } catch (error: unknown) {
    const timedOut = error instanceof Error && error.name === "TimeoutError";
    process.stderr.write(timedOut
      ? `REQUEST_ERROR: Local authoring service did not respond within ${REQUEST_TIMEOUT_MS / 1000} seconds.\n`
      : `REQUEST_ERROR: Could not read the saved script from 127.0.0.1:${port}.\n`);
    return EXPORT_AUTHORING_EXIT.refused;
  }

  if (!response.ok) {
    process.stderr.write(`REQUEST_ERROR: Local authoring service returned HTTP ${response.status}.\n`);
    return EXPORT_AUTHORING_EXIT.refused;
  }

  let payload: unknown;
  try {
    payload = await response.json() as unknown;
  } catch {
    process.stderr.write("RESPONSE_ERROR: Local authoring service returned invalid JSON.\n");
    return EXPORT_AUTHORING_EXIT.refused;
  }

  const view = record(payload);
  const document = view?.document;
  if (view?.projectId !== projectId || record(document)?.projectId !== projectId) {
    process.stderr.write("RESPONSE_ERROR: Local authoring service returned a different or incomplete project document.\n");
    return EXPORT_AUTHORING_EXIT.refused;
  }

  let validation: ReturnType<typeof validateScriptDocumentV2>;
  try {
    validation = validateScriptDocumentV2(document);
  } catch {
    process.stderr.write("VALIDATION_ERROR: Could not validate the saved ScriptDocumentV2.\n");
    return EXPORT_AUTHORING_EXIT.refused;
  }
  if (!validation.valid) {
    process.stderr.write(
      `VALIDATION_ERROR: Saved document failed ScriptDocumentV2 validation (${validation.diagnostics.length} diagnostics).\n`,
    );
    return EXPORT_AUTHORING_EXIT.refused;
  }

  const serialized = JSON.stringify(document, null, 2);
  if (serialized === undefined) {
    process.stderr.write("RESPONSE_ERROR: Saved project document could not be serialized as JSON.\n");
    return EXPORT_AUTHORING_EXIT.refused;
  }

  try {
    // Exclusive creation refuses existing files and symlinks without a preflight race.
    writeFileSync(outputPath, `${serialized}\n`, { encoding: "utf8", flag: "wx", mode: 0o600 });
  } catch {
    process.stderr.write(`WRITE_ERROR: Could not create ${outputPath}; the command never overwrites files.\n`);
    return EXPORT_AUTHORING_EXIT.write;
  }

  process.stdout.write(`Saved project ${projectId} script to ${outputPath}\n`);
  return EXPORT_AUTHORING_EXIT.ok;
}

const invokedPath = process.argv[1];
if (invokedPath !== undefined && import.meta.url === pathToFileURL(invokedPath).href) {
  process.exitCode = await runExportAuthoringCli(process.argv.slice(2));
}
