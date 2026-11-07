import { execFileSync, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { chmodSync, mkdtempSync, mkdirSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

const root = resolve(import.meta.dirname, "../../..");
const sha = execFileSync("git", ["rev-parse", "HEAD"], { cwd: root, encoding: "utf8" }).trim();
const emptySha = createHash("sha256").digest("hex");
const names = [
  "vera_schema_migrations", "vera_identity_actors", "vera_project_members", "vera_project_write_sessions",
  "vera_project_membership_audit", "stt_projects", "stt_document_heads", "stt_document_revisions",
  "stt_project_settings", "stt_settings_revisions", "stt_project_title_mutations",
];
const receipts = [
  ["stt_project_documents_001", "packages/project-documents/migrations/001_stt_projects_documents.sql"],
  ["vera_project_identity_membership_001", "packages/project-authorization/migrations/001_identity_membership.sql"],
].map(([name, file]) => `${name}|1|${createHash("sha256").update(readFileSync(join(root, file!))).digest("hex")}`);

interface Manifest {
  archiveSha256: string;
  inventory: {
    migrations: unknown[];
    tables: Record<string, { rows: number; sha256: string }>;
  };
}

const readManifest = (path: string): Manifest => JSON.parse(readFileSync(path, "utf8")) as Manifest;

describe("private development-QA backup/restore command guards", () => {
  let scratch: string;
  let archive: string;
  let environment: NodeJS.ProcessEnv;
  let fakeTools: string;

  function run(operation: "backup" | "restore", overrides: NodeJS.ProcessEnv = {}) {
    const result = spawnSync("bash", [join(root, "scripts", `stt-qa-${operation}.sh`)], {
      cwd: root, env: { ...environment, ...overrides }, encoding: "utf8", timeout: 20_000,
    });
    expect(result.error).toBeUndefined();
    return result;
  }

  beforeEach(() => {
    scratch = mkdtempSync(join(tmpdir(), "vera-159-backup-test-"));
    fakeTools = join(scratch, "bin");
    archive = join(scratch, "private-backup");
    mkdirSync(fakeTools);
    // The fake psql responds to bounded, read-only preflight queries. It never connects.
    const fakePsql = `#!/usr/bin/env bash
set -euo pipefail
db='' user='' sql=''
while (( $# )); do
  case "$1" in
    --dbname) db="$2"; shift 2;;
    --username) user="$2"; shift 2;;
    -c) sql="$2"; shift 2;;
    *) shift;;
  esac
done
case "$sql" in
  *'SELECT current_database()'*)
    if [[ "$db" == *privileged* ]]; then echo "$db|$user|$user|t|f|f|f|f";
    else echo "$db|$user|$user|f|f|f|f|f"; fi;;
  *'FROM pg_class c'*)
    if [[ "$db" != *restore* || "$db" == *existing* || -e '${join(scratch, "restored")}' ]]; then
      ${names.map((n) => `echo 'public.${n}|r'`).join("\n      ")}
    fi;;
  *'FROM vera_schema_migrations'*)
    printf '%s\\n' ${receipts.map((r) => `'${r}'`).join(" ")};;
  *'COPY (SELECT row_to_json'*) :;;
  *'SELECT count(*)'*)
    if [[ "$db" == *rogue* && "$sql" == *'proname NOT IN'* ]]; then echo 1;
    else echo 0; fi;;
  *) exit 9;;
esac
`;
    const fakeDump = `#!/usr/bin/env bash
set -euo pipefail
for arg in "$@"; do if [[ "$arg" == '--file=-' || "$arg" == '-f' ]]; then exit 8; fi; done
printf 'PRIVATE_FAKE_DUMP_159'`;
    const fakeRestore = `#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == '--list' ]]; then echo 'mock archive list'; exit 0; fi
touch '${join(scratch, "restored")}'`;
    for (const [name, script] of [["psql", fakePsql], ["pg_dump", fakeDump], ["pg_restore", fakeRestore]]) {
      writeFileSync(join(fakeTools, name!), script!, { mode: 0o700 });
    }
    environment = {
      ...process.env, PATH: `${fakeTools}:${process.env.PATH}`,
      VERA_STT_MODE: "development-qa", VERA_STT_SOURCE_SHA: sha,
      VERA_STT_QA_ARCHIVE_DIR: archive,
      VERA_STT_QA_DATABASE_URL: "postgres://qaowner:synthetic-only@127.0.0.1:5432/vera_stt_qa_synthetica",
      VERA_STT_QA_RESTORE_DATABASE_URL:
        "postgres://qaowner:synthetic-only@127.0.0.1:5432/vera_stt_qa_restore_synthetica",
    };
  });

  afterEach(() => { rmSync(scratch, { recursive: true, force: true }); });

  it("creates private fresh archive with SHA-256 and all migration/table inventories; verifies restore", () => {
    const backup = run("backup");
    expect(backup.status, backup.stderr).toBe(0);
    const manifest = readManifest(join(archive, "manifest.json"));
    expect(manifest.archiveSha256).toBe(createHash("sha256").update("PRIVATE_FAKE_DUMP_159").digest("hex"));
    expect(manifest.inventory.migrations).toHaveLength(2);
    expect(Object.keys(manifest.inventory.tables)).toEqual(names);
    expect(manifest.inventory.tables.stt_document_heads).toEqual({ rows: 0, sha256: emptySha });
    expect(run("restore").status).toBe(0);
  });

  it("refuses wrong DB names, loopback bypass, elevated role, source-as-destination and existing backups", () => {
    for (const url of [
      "postgres://qaowner:secret@localhost/vera_stt_qa_synthetica",
      "postgres://qaowner:secret@127.0.0.1/vera_production",
      "postgres://qaowner:secret@127.0.0.1/vera_stt_qa_restore_existing?options=-cfoo",
    ]) {
      expect(run("backup", { VERA_STT_QA_DATABASE_URL: url }).status).not.toBe(0);
    }
    expect(run("backup", { VERA_STT_QA_DATABASE_URL:
      "postgres://qaowner:secret@127.0.0.1/vera_stt_qa_privileged" }).status).not.toBe(0);
    expect(run("backup", { VERA_STT_QA_DATABASE_URL:
      "postgres://qaowner:secret@127.0.0.1/vera_stt_qa_rogue" }).status).not.toBe(0);
    expect(run("backup").status).toBe(0);
    expect(run("backup").status).not.toBe(0);
    expect(run("restore", { VERA_STT_QA_RESTORE_DATABASE_URL: environment.VERA_STT_QA_DATABASE_URL }).status).not.toBe(0);
    expect(run("restore", { VERA_STT_QA_RESTORE_DATABASE_URL:
      "postgres://qaowner:secret@127.0.0.1/vera_stt_qa_restore_existing" }).status).not.toBe(0);
    expect(run("restore", { VERA_STT_QA_RESTORE_DATABASE_URL:
      "postgres://qaowner:secret@127.0.0.2/vera_stt_qa_restore_synthetica" }).status).not.toBe(0);
    expect(run("restore", { VERA_STT_QA_ARCHIVE_DIR: join(root, "private-qa-dump") }).status).not.toBe(0);
  });

  it("refuses checksum/manifest tampering, soft permissions, symlink archives and source mismatch", () => {
    expect(run("backup").status).toBe(0);
    expect(run("restore", { VERA_STT_SOURCE_SHA: "a".repeat(40) }).status).not.toBe(0);
    chmodSync(join(archive, "manifest.json"), 0o644);
    expect(run("restore").status).not.toBe(0);
    chmodSync(join(archive, "manifest.json"), 0o600);
    const original = readFileSync(join(archive, "qa.dump"));
    const tampered = Buffer.from(original);
    tampered[0] = tampered[0]! ^ 1; // Same byte count: only SHA-256 can detect this.
    writeFileSync(join(archive, "qa.dump"), tampered);
    expect(run("restore").status).not.toBe(0);
    writeFileSync(join(archive, "qa.dump"), original);
    const manifest = readManifest(join(archive, "manifest.json"));
    (manifest.inventory.migrations[0] as { checksum: string }).checksum = "b".repeat(64);
    writeFileSync(join(archive, "manifest.json"), JSON.stringify(manifest));
    expect(run("restore").status).not.toBe(0);
    const link = join(scratch, "linked-archive");
    symlinkSync(archive, link);
    expect(run("restore", { VERA_STT_QA_ARCHIVE_DIR: link }).status).not.toBe(0);
  });

  it("fails closed when dump, list, or restore tool exits unsuccessfully", () => {
    writeFileSync(join(fakeTools, "pg_dump"), "#!/usr/bin/env bash\nexit 3\n", { mode: 0o700 });
    const refusedDump = run("backup");
    expect(refusedDump.status).not.toBe(0);
    expect(refusedDump.stderr).toBe("STT development-QA backup/restore refused\n");
    archive = join(scratch, "backup2");
    environment.VERA_STT_QA_ARCHIVE_DIR = archive;
    writeFileSync(join(fakeTools, "pg_dump"), "#!/usr/bin/env bash\nprintf 'PRIVATE_FAKE_DUMP_159'\n", { mode: 0o700 });
    expect(run("backup").status).toBe(0);
    writeFileSync(join(fakeTools, "pg_restore"), "#!/usr/bin/env bash\nexit 6\n", { mode: 0o700 });
    const refusedRestore = run("restore");
    expect(refusedRestore.status).not.toBe(0);
    expect(refusedRestore.stderr).toBe("STT development-QA backup/restore refused\n");
  });
});
