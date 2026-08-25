#!/usr/bin/env node

import type { ScriptDocumentV1 } from "./generated/contracts.js";
import type {
  ValidationDiagnostic,
  ValidationResult,
} from "./script-validator.js";

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

import { validateScriptDocument } from "./script-validator.ts";

export const SCRIPT_VALIDATOR_EXIT = {
  valid: 0,
  validation: 1,
  usage: 64,
  parse: 65,
  read: 66,
  internal: 70,
} as const;

interface CliIo {
  stdout: (text: string) => void;
  stderr: (text: string) => void;
  readFile: (path: string) => string;
  validate: (input: unknown) => ValidationResult;
}

const defaultIo: CliIo = {
  stdout: (text) => process.stdout.write(text),
  stderr: (text) => process.stderr.write(text),
  readFile: (path) => readFileSync(path, "utf8"),
  validate: validateScriptDocument,
};

export function runScriptValidatorCli(
  args: readonly string[],
  io: CliIo = defaultIo,
): number {
  try {
    if (args.length !== 1) {
      io.stderr(
        `USAGE: script-validator requires exactly one JSON file.\nUsage: node packages/contracts/src/script-validator-cli.ts <script-document.json>\n`,
      );
      return SCRIPT_VALIDATOR_EXIT.usage;
    }
    const path = args[0]!;
    let source: string;
    try {
      source = io.readFile(path);
    } catch (error: unknown) {
      io.stderr(`READ_ERROR: Cannot read ${path}: ${errorMessage(error)}\n`);
      return SCRIPT_VALIDATOR_EXIT.read;
    }

    let input: unknown;
    try {
      input = JSON.parse(source) as unknown;
    } catch (error: unknown) {
      io.stderr(`PARSE_ERROR: Invalid JSON in ${path}: ${errorMessage(error)}\n`);
      return SCRIPT_VALIDATOR_EXIT.parse;
    }

    const result = io.validate(input);
    if (!result.valid) {
      io.stdout(formatFailure(path, result));
      return SCRIPT_VALIDATOR_EXIT.validation;
    }
    io.stdout(formatPass(path, input as ScriptDocumentV1));
    return SCRIPT_VALIDATOR_EXIT.valid;
  } catch (error: unknown) {
    try {
      io.stderr(`INTERNAL_ERROR: ${errorMessage(error)}\n`);
    } catch {
      // Nothing else can be reported when the output channel itself failed.
    }
    return SCRIPT_VALIDATOR_EXIT.internal;
  }
}

function formatPass(path: string, document: ScriptDocumentV1): string {
  const lines = [`PASS ScriptDocument valid: ${path}`];
  for (const [index, block] of document.activeDraft.blocks.entries()) {
    lines.push(
      `Row ${index + 1} [${block.type}] order=${block.orderKey} id=${block.id}`,
    );
  }
  lines.push(`${document.activeDraft.blocks.length} row(s) validated.`);
  return `${lines.join("\n")}\n`;
}

function formatFailure(path: string, result: ValidationResult): string {
  const lines = [
    `FAIL ScriptDocument invalid: ${path}`,
    `${result.diagnostics.length} diagnostic(s):`,
  ];
  for (const diagnostic of result.diagnostics) {
    lines.push(`- ${formatDiagnostic(diagnostic)}`);
  }
  return `${lines.join("\n")}\n`;
}

function formatDiagnostic(diagnostic: ValidationDiagnostic): string {
  const references = [diagnostic.code];
  if (diagnostic.blockIndex !== undefined) {
    references.push(
      `Row ${diagnostic.blockIndex + 1}${
        diagnostic.orderKey === undefined
          ? ""
          : ` order=${diagnostic.orderKey}`
      }${diagnostic.blockId === undefined ? "" : ` block=${diagnostic.blockId}`}`,
    );
  }
  if (diagnostic.targetBlockIndex !== undefined) {
    references.push(
      `target Row ${diagnostic.targetBlockIndex + 1}${
        diagnostic.targetOrderKey === undefined
          ? ""
          : ` order=${diagnostic.targetOrderKey}`
      }${
        diagnostic.targetBlockId === undefined
          ? ""
          : ` block=${diagnostic.targetBlockId}`
      }`,
    );
  }
  if (diagnostic.entityKind !== undefined) {
    references.push(
      `${diagnostic.entityKind}${
        diagnostic.entityId === undefined ? "" : `=${diagnostic.entityId}`
      }`,
    );
  }
  if (diagnostic.tokenId !== undefined) {
    references.push(
      `tokens=${diagnostic.tokenId}${
        diagnostic.endTokenId === undefined
          ? ""
          : `..${diagnostic.endTokenId}`
      }`,
    );
  }
  references.push(diagnostic.jsonPath, diagnostic.message);
  return references.join(" | ");
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

const invokedPath = process.argv[1];
if (
  invokedPath !== undefined &&
  import.meta.url === pathToFileURL(invokedPath).href
) {
  process.exitCode = runScriptValidatorCli(process.argv.slice(2));
}
