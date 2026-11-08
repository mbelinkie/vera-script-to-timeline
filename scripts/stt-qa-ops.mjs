#!/usr/bin/env node
// Local synthetic development-QA operator tool. Not a production backup service.
import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  closeSync, constants, createReadStream, fstatSync, lstatSync,
  mkdirSync, openSync, readFileSync, realpathSync, statSync, writeFileSync,
} from "node:fs";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath, URL } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const commonGit = spawnSync("git", ["rev-parse", "--git-common-dir"], {
  cwd: root, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"],
});
const mainRepository = commonGit.status === 0
  ? dirname(realpathSync(resolve(root, commonGit.stdout.trim())))
  : root;
const FAIL = new Error("refused");
const hex64 = /^[0-9a-f]{64}$/u;
const dbName = /^vera_stt_qa_[a-z0-9][a-z0-9_]{2,50}$/u;
const restoreName = /^vera_stt_qa_restore_[a-z0-9][a-z0-9_]{2,40}$/u;
const userName = /^[a-z_][a-z0-9_]{0,62}$/u;
const tableNames = [
  "vera_schema_migrations", "vera_identity_actors", "vera_project_members",
  "vera_project_write_sessions", "vera_project_membership_audit",
  "stt_projects", "stt_document_heads", "stt_document_revisions",
  "stt_project_settings", "stt_settings_revisions", "stt_project_title_mutations",
  "stt_build_pairing_offers", "stt_project_build_agents", "stt_build_submissions",
  "stt_build_source_pins", "stt_build_dispatches", "stt_build_events",
  "stt_build_evidence", "stt_build_preflight_refusals",
];
const migrations = [
  ["vera_project_identity_membership_001", "packages/project-authorization/migrations/001_identity_membership.sql"],
  ["stt_project_documents_001", "packages/project-documents/migrations/001_stt_projects_documents.sql"],
  ["stt_project_builds_001", "packages/project-builds/migrations/001_project_builds.sql"],
  ["stt_project_builds_002_preflight_refusals", "packages/project-builds/migrations/002_preflight_refusals.sql"],
].map(([name, file]) => ({
  name, version: 1,
  checksum: createHash("sha256").update(readFileSync(join(root, file))).digest("hex"),
})).sort((a, b) => a.name.localeCompare(b.name));

function refuse(condition) { if (condition) throw FAIL; }

function checkoutPin(env) {
  refuse(env.VERA_STT_MODE !== "development-qa" || !/^[0-9a-f]{40}$/u.test(env.VERA_STT_SOURCE_SHA ?? ""));
  const result = spawnSync("git", ["rev-parse", "HEAD"], {
    cwd: root, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"],
  });
  refuse(result.status !== 0 || result.stdout.trim() !== env.VERA_STT_SOURCE_SHA);
  return result.stdout.trim();
}

function parseDb(value, restore) {
  refuse(!value || value.length > 4096);
  let url;
  try { url = new URL(value); } catch { throw FAIL; }
  refuse(!["postgres:", "postgresql:"].includes(url.protocol) || url.hostname !== "127.0.0.1" ||
    url.search !== "" || url.hash !== "" || !/^\/[a-z0-9_]+$/u.test(url.pathname) ||
    !dbName.test(url.pathname.slice(1)) || !userName.test(url.username) ||
    ["root", "postgres"].includes(url.username) || !url.password ||
    (restore ? !restoreName.test(url.pathname.slice(1)) : restoreName.test(url.pathname.slice(1))) ||
    (url.port !== "" && (!/^\d+$/u.test(url.port) || Number(url.port) < 1 || Number(url.port) > 65535)));
  return {
    name: url.pathname.slice(1), user: url.username,
    port: url.port || "5432", password: decodeURIComponent(url.password),
  };
}

function privateDirectory(env, creating) {
  const path = env.VERA_STT_QA_ARCHIVE_DIR;
  refuse(!path || !isAbsolute(path) || path.includes("\0"));
  const absolute = resolve(path);
  const parent = realpathSync(dirname(absolute));
  const candidate = join(parent, absolute.split("/").at(-1));
  for (const repository of [root, mainRepository]) {
    const rel = relative(realpathSync(repository), candidate);
    refuse(rel === "" || (!rel.startsWith("../") && rel !== ".." && !isAbsolute(rel)));
  }
  if (creating) {
    // mkdir without recursive is atomic: preexisting dir/file/symlink always fails.
    mkdirSync(absolute, { mode: 0o700 });
  }
  const st = lstatSync(absolute);
  refuse(!st.isDirectory() || st.isSymbolicLink() || st.uid !== process.getuid() || (st.mode & 0o777) !== 0o700);
  refuse(realpathSync(absolute) !== absolute);
  return absolute;
}

function privateFile(dir, file) {
  const path = join(dir, file);
  const st = lstatSync(path);
  refuse(!st.isFile() || st.isSymbolicLink() || st.nlink !== 1 ||
    st.uid !== process.getuid() || (st.mode & 0o777) !== 0o600);
  return path;
}

function pgEnv(db) {
  // A small allowlist prevents PGHOST/PGSERVICE/PGOPTIONS and shell overrides.
  return {
    PATH: process.env.PATH || "/usr/bin:/bin", PGPASSWORD: db.password,
    PGCONNECT_TIMEOUT: "5", PGSSLMODE: "disable", PGTZ: "UTC",
  };
}

function connectionArgs(db) {
  return ["--host", "127.0.0.1", "--port", db.port, "--username", db.user, "--dbname", db.name];
}

function run(tool, args, db, outputFd) {
  const result = spawnSync(tool, args, {
    env: pgEnv(db), encoding: outputFd === undefined ? "utf8" : undefined,
    stdio: ["ignore", outputFd ?? "pipe", "pipe"], maxBuffer: 16 * 1024 * 1024,
    timeout: 120_000,
  });
  // Never echo child stderr: libpq may include host, usernames or SQL.
  refuse(result.status !== 0 || result.error);
  return result.stdout?.toString() ?? "";
}

function query(db, sql) {
  return run("psql", ["-X", "-w", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1",
    ...connectionArgs(db), "-c", sql], db).trim();
}

function targetGuard(db, fresh) {
  const row = query(db, "SELECT current_database(),current_user,pg_get_userbyid(d.datdba)," +
    "r.rolsuper,r.rolcreatedb,r.rolcreaterole,r.rolreplication,r.rolbypassrls " +
    "FROM pg_database d JOIN pg_roles r ON r.rolname=current_user " +
    "WHERE d.datname=current_database()").split("|");
  refuse(row.length !== 8 || row[0] !== db.name || row[1] !== db.user || row[2] !== db.user ||
    row.slice(3).some((v) => v !== "f"));
  const objects = query(db, "SELECT n.nspname||'.'||c.relname,c.relkind FROM pg_class c " +
    "JOIN pg_namespace n ON n.oid=c.relnamespace " +
    "WHERE n.nspname NOT IN ('pg_catalog','pg_toast','information_schema') " +
    "AND n.nspname NOT LIKE 'pg_temp_%' AND n.nspname NOT LIKE 'pg_toast_temp_%' " +
    "AND c.relkind IN ('r','p','v','m','f','S','i','I')");
  const entries = objects === "" ? [] : objects.split("\n");
  refuse(entries.some((entry) => {
    const [name, kind] = entry.split("|");
    if (!name?.startsWith("public.")) return true;
    if (fresh) return true;
    if (kind === "r") return !tableNames.includes(name.slice(7));
    // Identity sequences are owned by the append-only build event ID column.
    if (kind === "S") return name === "public.stt_build_events_id_seq";
    return kind !== "i" || !/^(stt_|vera_|ix_vera_)[a-z0-9_]+$/u.test(name.slice(7));
  }));
  refuse(query(db, "SELECT count(*) FROM pg_namespace WHERE nspname NOT IN " +
    "('public','pg_catalog','pg_toast','information_schema') AND nspname NOT LIKE 'pg_temp_%' " +
    "AND nspname NOT LIKE 'pg_toast_temp_%'") !== "0");
  refuse(query(db, "SELECT count(*) FROM pg_extension WHERE extname <> 'plpgsql'") !== "0");
  if (fresh) {
    refuse(entries.length !== 0);
    refuse(query(db, "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace " +
      "WHERE n.nspname='public'") !== "0");
  } else {
    refuse(tableNames.some((name) => !entries.includes(`public.${name}|r`)));
    refuse(query(db, "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace " +
      "WHERE n.nspname='public' AND p.proname NOT IN " +
      "('stt_revision_immutable','vera_membership_audit_immutable','stt_build_record_immutable')") !== "0");
  }
  // The operator must stop the HTTP host and all other clients first.
  refuse(query(db, "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() " +
    "AND pid<>pg_backend_pid()") !== "0");
}

function migrationInventory(db) {
  const rows = query(db, "SELECT migration_name||'|'||schema_version||'|'||encode(checksum,'hex') " +
    "FROM vera_schema_migrations ORDER BY migration_name");
  const got = rows.split("\n").map((row) => {
    const [name, version, checksum] = row.split("|");
    return { name, version: Number(version), checksum };
  });
  refuse(JSON.stringify(got) !== JSON.stringify(migrations));
  return got;
}

async function tableDigest(db, table) {
  const child = spawn("psql", ["-X", "-w", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1",
    ...connectionArgs(db), "-c", `COPY (SELECT row_to_json(t)::text FROM public.${table} t ` +
    "ORDER BY to_jsonb(t)::text) TO STDOUT"],
  { env: pgEnv(db), stdio: ["ignore", "pipe", "pipe"] });
  const hash = createHash("sha256");
  let rows = 0;
  child.stdout.on("data", (chunk) => {
    hash.update(chunk);
    for (const byte of chunk) if (byte === 10) rows += 1;
  });
  // Swallow tool errors rather than relaying SQL or credentials.
  child.stderr.resume();
  const status = await new Promise((done, reject) => {
    child.once("error", reject); child.once("close", done);
  }).catch(() => { throw FAIL; });
  refuse(status !== 0);
  return { rows, sha256: hash.digest("hex") };
}

async function inventory(db) {
  targetGuard(db, false);
  const receipts = migrationInventory(db);
  const tables = {};
  for (const name of tableNames) tables[name] = await tableDigest(db, name);
  targetGuard(db, false);
  return { migrations: receipts, tables };
}

async function fileDigest(path) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(path)) hash.update(chunk);
  return hash.digest("hex");
}

function checkManifest(manifest) {
  refuse(manifest?.version !== 1 || !dbName.test(manifest.sourceDatabase ?? "") ||
    restoreName.test(manifest.sourceDatabase) || !/^[0-9a-f]{40}$/u.test(manifest.sourceSha ?? "") ||
    !hex64.test(manifest.archiveSha256 ?? "") || !Number.isSafeInteger(manifest.archiveBytes) ||
    manifest.archiveBytes < 1 ||
    JSON.stringify(manifest.inventory?.migrations) !== JSON.stringify(migrations) ||
    Object.keys(manifest.inventory?.tables ?? {}).sort().join("|") !== tableNames.slice().sort().join("|"));
  for (const table of tableNames) {
    const value = manifest.inventory.tables[table];
    refuse(!Number.isSafeInteger(value?.rows) || value.rows < 0 || !hex64.test(value.sha256));
  }
}

async function backup(env) {
  const sourceSha = checkoutPin(env);
  const db = parseDb(env.VERA_STT_QA_DATABASE_URL, false);
  // All non-archive checks before creating a private directory.
  const before = await inventory(db);
  const dir = privateDirectory(env, true);
  const file = join(dir, "qa.dump");
  const fd = openSync(file, constants.O_CREAT | constants.O_EXCL | constants.O_WRONLY | constants.O_NOFOLLOW, 0o600);
  try {
    refuse((fstatSync(fd).mode & 0o777) !== 0o600);
    // Omitting --file sends bytes to our already-open exclusive 0600 fd.
    // --file=- means a *literal file named -* to pg_dump; never use it.
    run("pg_dump", [...connectionArgs(db), "--format=custom", "--no-owner", "--no-acl"], db, fd);
  } finally { closeSync(fd); }
  refuse(statSync(file).size === 0);
  run("pg_restore", ["--list", file], db);
  const after = await inventory(db);
  refuse(JSON.stringify(before) !== JSON.stringify(after));
  const manifest = {
    version: 1, mode: "development-qa", sourceDatabase: db.name, sourceSha,
    archiveBytes: statSync(file).size, archiveSha256: await fileDigest(file),
    inventory: after,
  };
  checkManifest(manifest);
  writeFileSync(join(dir, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n", { flag: "wx", mode: 0o600 });
  process.stdout.write("STT development-QA private backup complete\n");
}

async function restore(env) {
  const sourceSha = checkoutPin(env);
  const db = parseDb(env.VERA_STT_QA_RESTORE_DATABASE_URL, true);
  const dir = privateDirectory(env, false);
  const file = privateFile(dir, "qa.dump");
  const manifestPath = privateFile(dir, "manifest.json");
  let manifest;
  try { manifest = JSON.parse(readFileSync(manifestPath, "utf8")); } catch { throw FAIL; }
  checkManifest(manifest);
  refuse(manifest.sourceSha !== sourceSha || manifest.sourceDatabase === db.name ||
    statSync(file).size !== manifest.archiveBytes ||
    await fileDigest(file) !== manifest.archiveSha256);
  run("pg_restore", ["--list", file], db);
  targetGuard(db, true);
  // No --create, --clean or role/ACL restores. Any failure rolls back ALL changes.
  run("pg_restore", ["--exit-on-error", "--single-transaction", "--no-owner", "--no-acl",
    ...connectionArgs(db), file], db);
  const actual = await inventory(db);
  refuse(JSON.stringify(actual) !== JSON.stringify(manifest.inventory));
  process.stdout.write("STT development-QA fresh-database restore verified\n");
}

async function main() {
  refuse(process.argv.length !== 3 || !["backup", "restore"].includes(process.argv[2]));
  if (process.argv[2] === "backup") await backup(process.env);
  else await restore(process.env);
}

main().catch(() => {
  // No URLs, tool output, archive contents, user payloads or credentials in logs.
  process.stderr.write("STT development-QA backup/restore refused\n");
  process.exitCode = 1;
});
