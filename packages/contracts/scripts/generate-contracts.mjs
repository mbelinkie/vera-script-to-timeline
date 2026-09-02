import { spawnSync } from "node:child_process";
import {
  mkdtempSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { compile } from "json-schema-to-typescript";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(scriptDirectory, "../../..");
const contractsDirectory = join(repositoryRoot, "contracts");
const checkedInTypeScriptDirectory = join(
  repositoryRoot,
  "packages/contracts/src/generated",
);
const checkedInPythonDirectory = join(
  repositoryRoot,
  "python/vera_timeline_agent/generated/contracts",
);
const schemaFiles = [
  "script-document-v1.schema.json",
  "timeline-manifest-v1.schema.json",
  "build-report-v1.schema.json",
  "compiler-dependencies-v1.schema.json",
  "prompter-export-v1.schema.json",
];

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function recreateDirectory(path) {
  rmSync(path, { force: true, recursive: true });
  mkdirSync(path, { recursive: true });
}

async function generateTypeScript(outputDirectory) {
  recreateDirectory(outputDirectory);
  const aggregateSchema = {
    $schema: "https://json-schema.org/draft/2020-12/schema",
    title: "VeraContractsV1",
    description:
      "Generated aggregate type surface for the VERA shared contracts.",
    type: "object",
    additionalProperties: false,
    required: [
      "scriptDocument",
      "timelineManifest",
      "buildReport",
      "compilerDependencies",
      "prompterExport",
    ],
    properties: {
      scriptDocument: { $ref: schemaFiles[0] },
      timelineManifest: { $ref: schemaFiles[1] },
      buildReport: { $ref: schemaFiles[2] },
      compilerDependencies: { $ref: schemaFiles[3] },
      prompterExport: { $ref: schemaFiles[4] },
    },
  };

  // Parse every source eagerly so malformed JSON fails before either language
  // generator can leave a partial checked-in output tree.
  for (const schemaFile of schemaFiles) {
    readJson(join(contractsDirectory, schemaFile));
  }

  const generated = await compile(aggregateSchema, "VeraContractsV1", {
    bannerComment:
      "/**\n * Generated from /contracts by npm run generate:contracts.\n * Do not edit by hand.\n */",
    cwd: contractsDirectory,
    enableConstEnums: false,
    format: true,
    style: {
      bracketSpacing: true,
      printWidth: 88,
      semi: true,
      singleQuote: false,
      tabWidth: 2,
      trailingComma: "all",
      useTabs: false,
    },
    unknownAny: true,
    unreachableDefinitions: false,
  });
  writeFileSync(join(outputDirectory, "contracts.ts"), generated);
}

function generatePython(outputDirectory) {
  recreateDirectory(outputDirectory);
  const result = spawnSync(
    "uv",
    [
      "run",
      "--frozen",
      "datamodel-codegen",
      "--input",
      "contracts",
      "--input-file-type",
      "jsonschema",
      "--output",
      outputDirectory,
      "--output-model-type",
      "typing.TypedDict",
      "--target-python-version",
      "3.12",
      "--use-standard-collections",
      "--use-union-operator",
      "--use-title-as-name",
      "--disable-timestamp",
      "--no-use-closed-typed-dict",
      "--no-allow-remote-refs",
      "--formatters",
      "ruff-format",
    ],
    { cwd: repositoryRoot, encoding: "utf8" },
  );
  if (result.status !== 0) {
    process.stderr.write(result.stdout);
    process.stderr.write(result.stderr);
    throw new Error(`Python contract generation exited ${String(result.status)}`);
  }
  writeFileSync(
    join(outputDirectory, "__init__.py"),
    [
      '"""Generated root models for the VERA shared JSON contracts."""',
      "",
      "from .build_report_v1_schema import BuildReportV1",
      "from .compiler_dependencies_v1_schema import CompilerDependenciesV1",
      "from .prompter_export_v1_schema import PrompterExportV1",
      "from .script_document_v1_schema import ScriptDocumentV1",
      "from .timeline_manifest_v1_schema import TimelineManifestV1",
      "",
      "__all__ = [",
      '    "BuildReportV1",',
      '    "CompilerDependenciesV1",',
      '    "PrompterExportV1",',
      '    "ScriptDocumentV1",',
      '    "TimelineManifestV1",',
      "]",
      "",
    ].join("\n"),
  );
  const lintResult = spawnSync(
    "uv",
    ["run", "--frozen", "ruff", "check", "--fix", outputDirectory],
    { cwd: repositoryRoot, encoding: "utf8" },
  );
  if (lintResult.status !== 0) {
    process.stderr.write(lintResult.stdout);
    process.stderr.write(lintResult.stderr);
    throw new Error(
      `Generated Python lint normalization exited ${String(lintResult.status)}`,
    );
  }
  rmSync(join(outputDirectory, ".ruff_cache"), {
    force: true,
    recursive: true,
  });
}

function listFiles(root) {
  const files = [];
  function visit(directory) {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      if (entry.name === "__pycache__" || entry.name.startsWith(".")) {
        continue;
      }
      const path = join(directory, entry.name);
      if (entry.isDirectory()) {
        visit(path);
      } else if (entry.isFile() && !entry.name.endsWith(".pyc")) {
        files.push(relative(root, path));
      }
    }
  }
  visit(root);
  return files.sort();
}

function compareDirectories(expectedDirectory, actualDirectory, label) {
  const expectedFiles = listFiles(expectedDirectory);
  const actualFiles = listFiles(actualDirectory);
  const differences = [];
  const allFiles = new Set([...expectedFiles, ...actualFiles]);
  for (const file of [...allFiles].sort()) {
    if (!expectedFiles.includes(file)) {
      differences.push(`${label}: missing checked-in file ${file}`);
      continue;
    }
    if (!actualFiles.includes(file)) {
      differences.push(`${label}: unexpected checked-in file ${file}`);
      continue;
    }
    const expected = readFileSync(join(expectedDirectory, file));
    const actual = readFileSync(join(actualDirectory, file));
    if (!expected.equals(actual)) {
      differences.push(`${label}: stale checked-in file ${file}`);
    }
  }
  return differences;
}

async function generate(typeScriptDirectory, pythonDirectory) {
  await generateTypeScript(typeScriptDirectory);
  generatePython(pythonDirectory);
}

if (process.argv.includes("--check")) {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "vera_contracts_"));
  const temporaryTypeScriptDirectory = join(temporaryRoot, "typescript");
  const temporaryPythonDirectory = join(temporaryRoot, "python_contracts");
  try {
    await generate(temporaryTypeScriptDirectory, temporaryPythonDirectory);
    const differences = [
      ...compareDirectories(
        checkedInTypeScriptDirectory,
        temporaryTypeScriptDirectory,
        "TypeScript",
      ),
      ...compareDirectories(
        checkedInPythonDirectory,
        temporaryPythonDirectory,
        "Python",
      ),
    ];
    if (differences.length > 0) {
      process.stderr.write(`${differences.join("\n")}\n`);
      process.stderr.write(
        "Run `npm run generate:contracts` and commit the generated output.\n",
      );
      process.exitCode = 1;
    } else {
      process.stdout.write("Generated contract types are current.\n");
    }
  } finally {
    rmSync(temporaryRoot, { force: true, recursive: true });
  }
} else {
  await generate(checkedInTypeScriptDirectory, checkedInPythonDirectory);
  process.stdout.write("Generated TypeScript and Python contract types.\n");
}
