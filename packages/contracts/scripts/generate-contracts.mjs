import { spawnSync } from "node:child_process";
import {
  copyFileSync,
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
const v1SchemaFiles = [
  "script-document-v1.schema.json",
  "timeline-manifest-v1.schema.json",
  "build-report-v1.schema.json",
  "compiler-dependencies-v1.schema.json",
  "prompter-export-v1.schema.json",
];
const v2SchemaFiles = [
  "script-document-v2.schema.json",
  "authoring-project-settings-v1.schema.json",
  "compiler-dependencies-v2.schema.json",
  "timeline-manifest-v2.schema.json",
  "build-report-v2.schema.json",
];
const typeScriptGroups = [
  {
    schemas: v1SchemaFiles,
    title: "VeraContractsV1",
    output: "contracts.ts",
    roots: [
      ["scriptDocument", v1SchemaFiles[0]],
      ["timelineManifest", v1SchemaFiles[1]],
      ["buildReport", v1SchemaFiles[2]],
      ["compilerDependencies", v1SchemaFiles[3]],
      ["prompterExport", v1SchemaFiles[4]],
    ],
  },
  {
    schemas: v2SchemaFiles,
    title: "VeraContractsV2",
    output: "contracts-v2.ts",
    roots: [
      ["scriptDocument", v2SchemaFiles[0]],
      ["authoringProjectSettings", v2SchemaFiles[1]],
      ["compilerDependencies", v2SchemaFiles[2]],
      ["timelineManifest", v2SchemaFiles[3]],
      ["buildReport", v2SchemaFiles[4]],
      ["compilerResult", v2SchemaFiles[4] + "#/$defs/CompilerResultV2"],
    ],
  },
];
const pythonGroups = [
  {
    name: "v1",
    schemas: v1SchemaFiles,
    exports: [
      ["build_report_v1_schema", "BuildReportV1"],
      ["compiler_dependencies_v1_schema", "CompilerDependenciesV1"],
      ["prompter_export_v1_schema", "PrompterExportV1"],
      ["script_document_v1_schema", "ScriptDocumentV1"],
      ["timeline_manifest_v1_schema", "TimelineManifestV1"],
    ],
  },
  {
    name: "v2",
    schemas: v2SchemaFiles,
    exports: [
      ["authoring_project_settings_v1_schema", "AuthoringProjectSettingsV1"],
      ["build_report_v2_schema", "BuildReportV2"],
      ["build_report_v2_schema", "CompilerResultV2"],
      ["compiler_dependencies_v2_schema", "CompilerDependenciesV2"],
      ["script_document_v2_schema", "ScriptDocumentV2"],
      ["timeline_manifest_v2_schema", "TimelineManifestV2"],
    ],
  },
];

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function recreateDirectory(path) {
  rmSync(path, { force: true, recursive: true });
  mkdirSync(path, { recursive: true });
}

async function generateTypeScript(outputDirectory, group) {
  mkdirSync(outputDirectory, { recursive: true });
  const aggregateSchema = {
    $schema: "https://json-schema.org/draft/2020-12/schema",
    title: group.title,
    description:
      "Generated aggregate type surface for the VERA shared contracts.",
    type: "object",
    additionalProperties: false,
    required: group.roots.map(([name]) => name),
    properties: Object.fromEntries(
      group.roots.map(([name, schemaFile]) => [name, { $ref: schemaFile }]),
    ),
  };

  // Parse every source eagerly so malformed JSON fails before either language
  // generator can leave a partial checked-in output tree.
  for (const schemaFile of group.schemas) {
    readJson(join(contractsDirectory, schemaFile));
  }

  const generated = await compile(aggregateSchema, group.title, {
    bannerComment: [
      "/**\n * Generated from /contracts by npm run generate:contracts.\n * Do not edit by hand.\n */",
      ...(group.output === "contracts-v2.ts"
        ? [
            "/* eslint-disable @typescript-eslint/no-duplicate-type-constituents -- JSON Schema conditionals repeat shared token fields. */",
          ]
        : []),
    ].join("\n"),
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
  writeFileSync(join(outputDirectory, group.output), generated);
}

function generatePythonGroup(outputDirectory, group) {
  recreateDirectory(outputDirectory);
  const pythonSchemaDirectory = mkdtempSync(
    join(tmpdir(), "vera-contracts-" + group.name + "-inputs-"),
  );
  let result;
  try {
    for (const schemaFile of group.schemas) {
      writeFileSync(
        join(pythonSchemaDirectory, schemaFile),
        readFileSync(join(contractsDirectory, schemaFile)),
      );
    }
    result = spawnSync(
      "uv",
      [
        "run",
        "--frozen",
        "datamodel-codegen",
        "--input",
        pythonSchemaDirectory,
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
  } finally {
    rmSync(pythonSchemaDirectory, { force: true, recursive: true });
  }
  if (result.status !== 0) {
    process.stderr.write(result.stdout);
    process.stderr.write(result.stderr);
    throw new Error(`Python contract generation exited ${String(result.status)}`);
  }
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

function writePythonRegistry(outputDirectory) {
  const exports = pythonGroups.flatMap((group) => group.exports);
  writeFileSync(
    join(outputDirectory, "__init__.py"),
    [
      '"""Generated root models for the VERA shared JSON contracts."""',
      "",
      ...exports.map(
        ([moduleName, typeName]) => "from ." + moduleName + " import " + typeName,
      ),
      "",
      "__all__ = [",
      ...exports.map(([, typeName]) => '    "' + typeName + '",'),
      "]",
      "",
    ].join("\n"),
  );
}

function generatePython(outputDirectory) {
  recreateDirectory(outputDirectory);
  const stagedRoot = mkdtempSync(join(tmpdir(), "vera-contracts-python-groups-"));
  try {
    for (const group of pythonGroups) {
      const stagedGroup = join(stagedRoot, group.name);
      generatePythonGroup(stagedGroup, group);
      for (const file of listFiles(stagedGroup)) {
        if (file !== "__init__.py") {
          copyFileSync(join(stagedGroup, file), join(outputDirectory, file));
        }
      }
    }
    writePythonRegistry(outputDirectory);
  } finally {
    rmSync(stagedRoot, { force: true, recursive: true });
  }

  const lintResult = spawnSync(
    "uv",
    ["run", "--frozen", "ruff", "check", "--fix", outputDirectory],
    { cwd: repositoryRoot, encoding: "utf8" },
  );
  if (lintResult.status !== 0) {
    process.stderr.write(lintResult.stdout);
    process.stderr.write(lintResult.stderr);
    throw new Error(
      "Generated Python lint normalization exited " + String(lintResult.status),
    );
  }
  rmSync(join(outputDirectory, ".ruff_cache"), { force: true, recursive: true });
}

async function generate(typeScriptDirectory, pythonDirectory) {
  recreateDirectory(typeScriptDirectory);
  for (const group of typeScriptGroups) {
    await generateTypeScript(typeScriptDirectory, group);
  }
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
