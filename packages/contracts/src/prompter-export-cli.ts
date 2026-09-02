#!/usr/bin/env node

import { lstatSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { pathToFileURL } from "node:url";

import {
  exportPrompter,
  type PrompterExportSettings,
} from "./prompter-export.ts";
import type { ValidationDiagnostic } from "./script-validator.js";

export const PROMPTER_EXPORT_EXIT = {
  ok: 0,
  validation: 1,
  usage: 64,
  parse: 65,
  read: 66,
  internal: 70,
  write: 73,
} as const;

interface CliIo {
  stdout: (text: string) => void;
  stderr: (text: string) => void;
  readFile: (path: string) => string;
  writeFile: (path: string, value: string) => void;
  checkOutputs?: (paths: readonly string[]) => void;
}

const defaultIo: CliIo = {
  stdout: (text) => process.stdout.write(text),
  stderr: (text) => process.stderr.write(text),
  readFile: (path) => readFileSync(path, "utf8"),
  // Exclusive creation also closes the race between preflight and a write.
  writeFile: (path, value) => writeFileSync(path, value, { encoding: "utf8", flag: "wx" }),
  checkOutputs: (paths) => {
    for (const path of paths) {
      try {
        lstatSync(path);
      } catch (error: unknown) {
        if (error instanceof Error && "code" in error && error.code === "ENOENT") {
          if (!statSync(dirname(resolve(path))).isDirectory()) throw new Error(`Output parent is not a directory: ${path}`, { cause: error });
          continue;
        }
        throw error;
      }
      throw new Error(`Refusing to overwrite existing output: ${path}`);
    }
  },
};

interface ParsedArguments {
  inputPath: string;
  textPath: string;
  sidecarPath: string;
  settings: PrompterExportSettings;
}

export function runPrompterExportCli(
  args: readonly string[],
  io: CliIo = defaultIo,
): number {
  try {
    const parsed = parseArguments(args);
    if (parsed === undefined) {
      io.stderr(
        "USAGE: prompter-export requires an input, --text path, and --sidecar path.\n" +
          "Usage: npm run export:prompter -- <script-document.json> --text <prompter.txt> --sidecar <prompter.json> [--include-section-navigation] [--include-beat-numbers]\n",
      );
      return PROMPTER_EXPORT_EXIT.usage;
    }

    let source: string;
    try {
      source = io.readFile(parsed.inputPath);
    } catch (error: unknown) {
      io.stderr(
        `READ_ERROR: Cannot read ${parsed.inputPath}: ${errorMessage(error)}\n`,
      );
      return PROMPTER_EXPORT_EXIT.read;
    }

    let input: unknown;
    try {
      input = JSON.parse(source) as unknown;
    } catch (error: unknown) {
      io.stderr(
        `PARSE_ERROR: Invalid JSON in ${parsed.inputPath}: ${errorMessage(error)}\n`,
      );
      return PROMPTER_EXPORT_EXIT.parse;
    }

    const result = exportPrompter(input, parsed.settings);
    if (!result.ok) {
      io.stdout(formatFailure(parsed.inputPath, result.diagnostics));
      return PROMPTER_EXPORT_EXIT.validation;
    }

    try {
      io.checkOutputs?.([parsed.textPath, parsed.sidecarPath]);
      io.writeFile(parsed.textPath, result.text);
      io.writeFile(parsed.sidecarPath, result.sidecarJson);
    } catch (error: unknown) {
      io.stderr(`WRITE_ERROR: ${errorMessage(error)}. Any newly created partial artifact is retained; no complete export was published.\n`);
      return PROMPTER_EXPORT_EXIT.write;
    }
    io.stdout(
      "PASS Prompter export written\n" +
        `text=${parsed.textPath} ${result.sidecar.textSha256}\n` +
        `sidecar=${parsed.sidecarPath} ${result.sidecarSha256}\n`,
    );
    return PROMPTER_EXPORT_EXIT.ok;
  } catch (error: unknown) {
    try {
      io.stderr(`INTERNAL_ERROR: ${errorMessage(error)}\n`);
    } catch {
      // Nothing else can be reported when the output channel itself failed.
    }
    return PROMPTER_EXPORT_EXIT.internal;
  }
}

function parseArguments(args: readonly string[]): ParsedArguments | undefined {
  if (args.length < 5 || !args[0] || args[0].startsWith("--")) return undefined;
  const inputPath = args[0];
  let textPath: string | undefined;
  let sidecarPath: string | undefined;
  let includeSectionNavigation = false;
  let includeBeatNumbers = false;

  for (let index = 1; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === "--text" && textPath === undefined) {
      textPath = args[index + 1];
      index += 1;
    } else if (argument === "--sidecar" && sidecarPath === undefined) {
      sidecarPath = args[index + 1];
      index += 1;
    } else if (argument === "--include-section-navigation") {
      includeSectionNavigation = true;
    } else if (argument === "--include-beat-numbers") {
      includeBeatNumbers = true;
    } else {
      return undefined;
    }
  }
  if (
    !textPath ||
    textPath.startsWith("--") ||
    !sidecarPath ||
    sidecarPath.startsWith("--")
  ) {
    return undefined;
  }
  if (new Set([inputPath, textPath, sidecarPath].map((path) => resolve(path))).size !== 3) return undefined;
  return {
    inputPath,
    textPath,
    sidecarPath,
    settings: { includeSectionNavigation, includeBeatNumbers },
  };
}

function formatFailure(
  path: string,
  diagnostics: readonly ValidationDiagnostic[],
): string {
  const lines = [
    `FAIL Prompter export blocked: ${path}`,
    `${diagnostics.length} diagnostic(s):`,
  ];
  for (const diagnostic of diagnostics) {
    lines.push(
      `- ${diagnostic.code} | ${diagnostic.jsonPath} | ${diagnostic.message}`,
    );
  }
  return `${lines.join("\n")}\n`;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

const invokedPath = process.argv[1];
if (
  invokedPath !== undefined &&
  import.meta.url === pathToFileURL(invokedPath).href
) {
  process.exitCode = runPrompterExportCli(process.argv.slice(2));
}
