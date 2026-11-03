#!/usr/bin/env node

import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { chmod, lstat, mkdir, mkdtemp, rename, rm, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { randomUUID } from "node:crypto";

const execFileAsync = promisify(execFile);
const bundleId = "org.vera.dashboard-helper";
const bundleName = "VERA Dashboard Helper.app";
const executableName = "vera-dashboard-helper";
const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const outputRoot = path.join(homedir(), "Library", "Application Support", "VERA", "dashboard-actions");
const bundlePath = path.join(outputRoot, bundleName);
const uid = process.getuid?.();

async function run(command, args) {
  try {
    return await execFileAsync(command, args, { cwd: repositoryRoot, encoding: "utf8", timeout: 120_000, maxBuffer: 2 * 1024 * 1024 });
  } catch (error) {
    const detail = error.stderr?.trim();
    throw new Error(`${command} failed${detail ? `: ${detail}` : ""}`);
  }
}

async function ensureDirectory(directory, create = false) {
  let info;
  try {
    info = await lstat(directory);
  } catch (error) {
    if (error.code !== "ENOENT" || !create) throw new Error("Dashboard Helper directory is unavailable");
    try { await mkdir(directory, { mode: 0o700 }); } catch (mkdirError) {
      if (mkdirError.code !== "EEXIST") throw new Error("Dashboard Helper directory could not be created");
    }
    info = await lstat(directory);
  }
  if (info.isSymbolicLink() || !info.isDirectory() || (uid !== undefined && info.uid !== uid) || (info.mode & 0o022) !== 0) {
    throw new Error("Dashboard Helper directory must be a private directory owned by the current user");
  }
  return info;
}

async function privateOutputRoot() {
  const home = path.resolve(homedir());
  await ensureDirectory(home);
  let current = home;
  for (const name of ["Library", "Application Support", "VERA", "dashboard-actions"]) {
    current = path.join(current, name);
    const info = await ensureDirectory(current, true);
    if (name === "dashboard-actions" && (info.mode & 0o077) !== 0) {
      throw new Error("Dashboard Helper output directory must be private to the current user");
    }
  }
}

async function existingBundle() {
  let info;
  try { info = await lstat(bundlePath); } catch (error) {
    if (error.code === "ENOENT") return false;
    throw new Error("Existing Dashboard Helper bundle is unavailable");
  }
  if (info.isSymbolicLink() || !info.isDirectory() || (uid !== undefined && info.uid !== uid)) {
    throw new Error("Existing Dashboard Helper bundle is not owned by this user");
  }
  const contents = path.join(bundlePath, "Contents");
  const macOS = path.join(contents, "MacOS");
  await ensureDirectory(contents);
  await ensureDirectory(macOS);
  const plist = path.join(contents, "Info.plist");
  const plistInfo = await lstat(plist).catch(() => null);
  if (!plistInfo || plistInfo.isSymbolicLink() || !plistInfo.isFile() || (uid !== undefined && plistInfo.uid !== uid)) {
    throw new Error("Existing Dashboard Helper bundle has no safe Info.plist");
  }
  const { stdout } = await run("/usr/bin/plutil", ["-extract", "CFBundleIdentifier", "raw", "-o", "-", plist]);
  if (stdout.trim() !== bundleId) throw new Error("Refusing to replace a bundle with a different identifier");
  const executable = path.join(macOS, executableName);
  const executableInfo = await lstat(executable).catch(() => null);
  if (executableInfo && (executableInfo.isSymbolicLink() || !executableInfo.isFile()
      || (uid !== undefined && executableInfo.uid !== uid))) {
    throw new Error("Existing Dashboard Helper executable is not a safe file");
  }
  return true;
}

async function build() {
  if (process.platform !== "darwin") throw new Error("Dashboard Helper packaging requires macOS with Swift and codesign.");
  await privateOutputRoot();
  const hadBundle = await existingBundle();
  const tempRoot = await mkdtemp(path.join(outputRoot, ".dashboard-helper-"));
  const tempBundle = path.join(tempRoot, bundleName);
  const contents = path.join(tempBundle, "Contents");
  const macOS = path.join(contents, "MacOS");
  const executable = path.join(macOS, executableName);
  const source = path.join(repositoryRoot, "scripts", "dashboard-chrome-helper.swift");
  const plist = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>${executableName}</string>
<key>CFBundleIdentifier</key><string>${bundleId}</string>
<key>CFBundleName</key><string>VERA Dashboard Helper</string>
<key>CFBundleDisplayName</key><string>VERA Dashboard Helper</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>1.0</string>
<key>CFBundleVersion</key><string>1</string>
<key>LSUIElement</key><true/>
<key>NSAccessibilityUsageDescription</key><string>Send the review prompt you request to ChatGPT in Chrome.</string>
</dict></plist>
`;
  let backup = null;
  try {
    await chmod(tempRoot, 0o700);
    await mkdir(macOS, { recursive: true, mode: 0o700 });
    await writeFile(path.join(contents, "Info.plist"), plist, { mode: 0o644 });
    await run("/usr/bin/swiftc", ["-parse-as-library", source, "-framework", "AppKit", "-framework", "ApplicationServices", "-o", executable]);
    await run("/usr/bin/codesign", ["--force", "--sign", "-", "--identifier", bundleId, tempBundle]);
    if (hadBundle) {
      backup = path.join(outputRoot, `.dashboard-helper-backup-${randomUUID()}`);
      await rename(bundlePath, backup);
    }
    try {
      await rename(tempBundle, bundlePath);
    } catch (error) {
      if (backup) await rename(backup, bundlePath);
      throw error;
    }
    if (backup) await rm(backup, { recursive: true, force: true });
    console.log(`VERA Dashboard Helper built at ${bundlePath}`);
  } finally {
    await rm(tempRoot, { recursive: true, force: true }).catch(() => {});
  }
}

if (process.argv.length !== 3 || process.argv[2] !== "build") {
  console.error("Usage: node scripts/build-dashboard-helper.mjs build");
  process.exitCode = 2;
} else {
  try { await build(); } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
