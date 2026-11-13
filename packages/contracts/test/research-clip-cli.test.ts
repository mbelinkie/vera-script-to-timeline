import { spawnSync } from "node:child_process";
import { chmodSync, linkSync, lstatSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { afterEach, describe, expect, it } from "vitest";

import {
  RESEARCH_CLI_EXIT, readResearchScript, replaceResearchScript, runResearchClipCli,
  type ResearchClipCliIo,
} from "../src/research-clip-cli.js";
import { validateScriptDocumentV2 } from "../src/authoring-v2-validation.js";
import { researchCandidate, researchId, researchNote, researchStashFixture } from "./issue-367-fixture.js";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const cliPath = join(root, "packages/contracts/src/research-clip-cli.ts");
const validatorPath = join(root, "packages/contracts/src/script-validator-cli.ts");
const SECRET = "private-dev-credential-do-not-print";
const PROJECT = researchId(710002);
const CLIP = researchId(710001);
const ANCHOR = researchId(820100);
const paths: string[] = [];

function tempDirectory(): string {
  const directory = mkdtempSync(join(tmpdir(), "vera-research-cli-"));
  paths.push(directory);
  return directory;
}

function makeScript(): { path: string; before: string; directory: string } {
  const directory = tempDirectory();
  const path = join(directory, "script.json");
  const doc = researchStashFixture(false).doc;
  doc.activeDraft.blocks = [researchNote(820100), researchNote(820200)];
  const before = `${JSON.stringify(doc, null, 2)}\n`;
  writeFileSync(path, before);
  return { path, before, directory };
}

function fakeService(options: {
  status?: number;
  projects?: unknown;
  clips?: unknown;
  clip?: unknown;
  outage?: boolean;
} = {}) {
  const calls: Array<{ pathname: string; init: RequestInit | undefined }> = [];
  const request: typeof fetch = (input, init) => {
    const pathname = new URL(input instanceof Request ? input.url : input.toString()).pathname;
    calls.push({ pathname, init });
    if (options.outage) return Promise.reject(new Error(`Bearer ${SECRET}: connection refused`));
    if (options.status) return Promise.resolve(options.status === 302
      ? new Response(null, { status: 302, headers: { Location: `https://${SECRET}.example.net` } })
      : Response.json({ error: { message: SECRET } }, { status: options.status }));
    if (pathname === "/api/projects") return Promise.resolve(Response.json(options.projects ?? [{ id: PROJECT, name: "Field Research" }]));
    if (pathname.endsWith("/clips")) return Promise.resolve(Response.json(options.clips ?? [researchCandidate()]));
    return Promise.resolve(Response.json(options.clip ?? researchCandidate()));
  };
  return { request, calls };
}

function harness(options: Parameters<typeof fakeService>[0] = {}, overrides: Partial<ResearchClipCliIo> = {}) {
  const fake = fakeService(options);
  const output: string[] = [];
  const errors: string[] = [];
  const io: Partial<ResearchClipCliIo> = {
    stdout: (value) => { output.push(value); },
    stderr: (value) => { errors.push(value); },
    env: { bearer: SECRET },
    request: fake.request,
    ...overrides,
  };
  return {
    ...fake, output, errors,
    run: (...args: string[]) => runResearchClipCli(args, io),
  };
}

function expectSafeFailure(result: number, h: ReturnType<typeof harness>, file?: { path: string; before: string }) {
  expect(result).not.toBe(0);
  expect(h.output.join("")).toBe("");
  expect(h.errors).toHaveLength(1);
  expect(h.errors[0]).toMatch(/^[^\n\r]+\n$/u);
  expect(h.errors[0]).not.toContain("\u001b");
  expect(h.errors[0]).not.toContain(SECRET);
  if (file) expect(readFileSync(file.path, "utf8")).toBe(file.before);
}

afterEach(() => {
  for (const directory of paths.splice(0)) rmSync(directory, { recursive: true, force: true });
});

describe("Research clip CLI", () => {
  it("lists only sanitized clip lines, resolves case-insensitive names, and sends GET/manual requests", async () => {
    const clip = researchCandidate();
    clip.video.title = `Title\n\u001b[31m${SECRET} source`;
    const h = harness({ clips: [clip] });
    expect(await h.run("clips", "field research")).toBe(RESEARCH_CLI_EXIT.ok);
    expect(h.output).toHaveLength(1);
    expect(h.output[0]).toContain(`${CLIP} | Title [31m[redacted] source | Frozen English text | 00:00.500–00:04.500`);
    expect(h.output.join("")).not.toContain(SECRET);
    expect(h.errors).toEqual([]);
    expect(h.calls.map((call) => call.pathname)).toEqual([
      "/api/projects", `/api/projects/${PROJECT}/clips`,
    ]);
    expect(h.calls.every((call) => call.init?.method === "GET" && call.init.redirect === "manual")).toBe(true);
    expect(h.calls.every((call) => (call.init?.headers as Record<string, string>).Authorization === `Bearer ${SECRET}`)).toBe(true);
    const empty = harness({ clips: [] });
    expect(await empty.run("clips", PROJECT)).toBe(0);
    expect(empty.output).toEqual(["No logged clips in this Research project.\n"]);
  });

  it("saves frozen clip source fields after the active row; a second use creates a different row", async () => {
    const file = makeScript();
    chmodSync(file.path, 0o640);
    const originalOwner = statSync(file.path);
    const h = harness();
    for (let count = 1; count <= 2; count += 1) {
      expect(await h.run("add-clip", PROJECT, CLIP, file.path, ANCHOR)).toBe(0);
      const doc = JSON.parse(readFileSync(file.path, "utf8")) as ReturnType<typeof researchStashFixture>["doc"];
      expect(validateScriptDocumentV2(doc).valid).toBe(true);
      expect(doc.activeDraft.blocks).toHaveLength(count + 2);
      expect(doc.activeDraft.blocks[0]?.id).toBe(ANCHOR);
      const inserted = doc.activeDraft.blocks[1];
      expect(inserted?.type).toBe("visual_only");
      if (inserted?.type !== "visual_only") throw new Error("Missing clip row");
      expect(inserted.researchClip).toMatchObject({
        clipId: CLIP, video: researchCandidate().video, englishText: researchCandidate().englishText,
        loggedSelection: {
          text: researchCandidate().selection.text,
          exportStartMs: 500, exportEndMs: 4500,
        },
      });
      expect(inserted.frameBinding).toBeUndefined();
      expect(new Set(doc.activeDraft.blocks.map((row) => row.id)).size).toBe(doc.activeDraft.blocks.length);
      expect(lstatSync(file.path).mode & 0o777).toBe(0o640);
      expect(statSync(file.path).uid).toBe(originalOwner.uid);
      expect(statSync(file.path).gid).toBe(originalOwner.gid);
      expect(readdirSync(file.directory)).toEqual(["script.json"]);
    }
    expect(h.errors).toEqual([]);
    expect(h.output).toEqual(["Research clip added to the script.\n", "Research clip added to the script.\n"]);
    expect(h.calls.every((call) => call.init?.method === "GET" && call.init.redirect === "manual")).toBe(true);
    expect(readFileSync(file.path, "utf8")).not.toContain(SECRET);
  });

  it("uses the selected project UUID without relying on an unrelated project list", async () => {
    const h = harness({ projects: { invalid: "response" } });
    expect(await h.run("clips", PROJECT)).toBe(0);
    expect(h.calls.map((call) => call.pathname)).toEqual([`/api/projects/${PROJECT}/clips`]);
    expect(h.errors).toEqual([]);
  });

  it("refuses invalid usage, missing credential, unsafe origin, missing and duplicate project names", async () => {
    const file = makeScript();
    const examples = [
      [harness(), ["add-clip", PROJECT, CLIP, file.path]],
      [harness({}, { env: { bearer: undefined } }), ["add-clip", PROJECT, CLIP, file.path, ANCHOR]],
      [harness({}, { env: { bearer: SECRET, url: "https://research.example.org" } }), ["add-clip", PROJECT, CLIP, file.path, ANCHOR]],
      [harness(), ["add-clip", "not-visible", CLIP, file.path, ANCHOR]],
      [harness({ projects: [{ id: PROJECT, name: "Repeated" }, { id: researchId(777), name: "REPEATED" }] }),
        ["add-clip", "Repeated", CLIP, file.path, ANCHOR]],
    ] as const;
    for (const [h, args] of examples) {
      expectSafeFailure(await h.run(...args), h, file);
    }
  });

  it("never writes when server denies access, returns a redirect, goes offline or mismatches clip identity", async () => {
    const file = makeScript();
    for (const options of [
      { status: 401 }, { status: 403 }, { status: 404 }, { status: 302 },
      { outage: true }, { projects: { malformed: "list" } },
      { clip: { ...researchCandidate(), id: researchId(12345) } },
      { clip: { ...researchCandidate(), projectId: researchId(12345) } },
      { clip: { ...researchCandidate(), selection: null } },
    ]) {
      const h = harness(options);
      const project = "projects" in options ? "Field Research" : PROJECT;
      expectSafeFailure(await h.run("add-clip", project, CLIP, file.path, ANCHOR), h, file);
    }
    const mismatchedList = harness({ clips: [{ ...researchCandidate(), projectId: researchId(9876) }] });
    expectSafeFailure(await mismatchedList.run("clips", PROJECT), mismatchedList);
  });

  it("rejects missing clip IDs, invalid JSON, non-v2 and invalid v2 documents, and inactive anchors", async () => {
    const file = makeScript();
    for (const clipId of ["wrong-id", researchId(710999)]) {
      const h = clipId === "wrong-id" ? harness() : harness({ status: 404 });
      expectSafeFailure(await h.run("add-clip", PROJECT, clipId, file.path, ANCHOR), h, file);
    }
    for (const input of ["{broken", "{}", JSON.stringify({ ...researchStashFixture(false).doc, schemaVersion: "script-document/v1" })]) {
      writeFileSync(file.path, input);
      const h = harness();
      expectSafeFailure(await h.run("add-clip", PROJECT, CLIP, file.path, ANCHOR), h, { path: file.path, before: input });
    }
    const invalid = researchStashFixture(false).doc;
    invalid.activeDraft.blocks = [researchNote(820100)];
    invalid.activeDraft.blocks[0]!.orderKey = "";
    writeFileSync(file.path, JSON.stringify(invalid));
    const h = harness();
    expectSafeFailure(await h.run("add-clip", PROJECT, CLIP, file.path, ANCHOR), h,
      { path: file.path, before: JSON.stringify(invalid) });
    const valid = researchStashFixture(false).doc;
    valid.activeDraft.blocks = [researchNote(820100)];
    writeFileSync(file.path, JSON.stringify(valid));
    const wrongAnchor = harness();
    expectSafeFailure(await wrongAnchor.run("add-clip", PROJECT, CLIP, file.path, researchId(720100)), wrongAnchor,
      { path: file.path, before: JSON.stringify(valid) });
  });

  it("refuses symlink paths and does not modify the target or leave temp files", async () => {
    const file = makeScript();
    const link = join(file.directory, "linked.json");
    symlinkSync(file.path, link);
    const h = harness();
    expectSafeFailure(await h.run("add-clip", PROJECT, CLIP, link, ANCHOR), h, file);
    expect(lstatSync(link).isSymbolicLink()).toBe(true);
    expect(readdirSync(file.directory).sort()).toEqual(["linked.json", "script.json"]);
  });

  it("refuses hard-linked script paths without splitting their contents", async () => {
    const file = makeScript();
    const anotherLink = join(file.directory, "another-link.json");
    linkSync(file.path, anotherLink);
    const h = harness();
    expectSafeFailure(await h.run("add-clip", PROJECT, CLIP, file.path, ANCHOR), h, file);
    expect(readFileSync(anotherLink, "utf8")).toBe(file.before);
    expect(readdirSync(file.directory).sort()).toEqual(["another-link.json", "script.json"]);
  });

  it("rejects a FIFO promptly rather than hanging on its opening read", () => {
    const directory = tempDirectory();
    const fifoPath = join(directory, "script.pipe");
    expect(spawnSync("mkfifo", [fifoPath], { timeout: 3_000 }).status).toBe(0);
    const probe = `import { readResearchScript } from ${JSON.stringify(pathToFileURL(cliPath).href)};
try { readResearchScript(${JSON.stringify(fifoPath)}); process.exitCode = 1; }
catch { process.exitCode = 0; }`;
    const attempt = spawnSync(process.execPath, ["--input-type=module", "--eval", probe], {
      cwd: root, encoding: "utf8", timeout: 3_000,
    });
    expect(attempt.error).toBeUndefined();
    expect(attempt.status, attempt.stderr).toBe(0);
  });

  it("detects stale source replacements and in-place edits and preserves externally changed contents", () => {
    const file = makeScript();
    const snapshot = readResearchScript(file.path);
    writeFileSync(file.path, "external change");
    expect(() => replaceResearchScript(file.path, snapshot, "would overwrite")).toThrow(/changed/);
    expect(readFileSync(file.path, "utf8")).toBe("external change");
    const snapshot2 = readResearchScript(file.path);
    rmSync(file.path);
    writeFileSync(file.path, "replacement inode");
    expect(() => replaceResearchScript(file.path, snapshot2, "would overwrite")).toThrow(/changed/);
    expect(readFileSync(file.path, "utf8")).toBe("replacement inode");
    expect(readdirSync(file.directory)).toEqual(["script.json"]);
  });

  it("reports a failed write without damaging the script", async () => {
    const file = makeScript();
    const h = harness({}, { replaceScript: () => { throw new Error(`failed write: ${SECRET}`); } });
    expect(await h.run("add-clip", PROJECT, CLIP, file.path, ANCHOR)).toBe(RESEARCH_CLI_EXIT.write);
    expectSafeFailure(RESEARCH_CLI_EXIT.write, h, file);
  });

  it("runs direct Node TS and npm scripts with fake fetch in a real subprocess; v2 validator accepts result", () => {
    const file = makeScript();
    const preloadPath = join(file.directory, "fake-research.mjs");
    const candidate = JSON.stringify(researchCandidate());
    writeFileSync(preloadPath, `globalThis.fetch = async (input, init) => {
  if (init?.method !== "GET" || init?.redirect !== "manual") throw Error("Unexpected request");
  const pathname = new URL(String(input)).pathname;
  return Response.json(pathname === "/api/projects" ? [{ id: ${JSON.stringify(PROJECT)}, name: "Field Research" }] : pathname.endsWith("/clips") ? [${candidate}] : ${candidate});
};\n`);
    const env = {
      ...process.env, VERA_RESEARCH_BEARER: SECRET, VERA_RESEARCH_URL: "http://127.0.0.1:43111",
      NODE_OPTIONS: `--import=${preloadPath}`,
    };
    const run = (command: string, args: string[]) => spawnSync(command, args, {
      cwd: root, encoding: "utf8", env, timeout: 30_000,
    });
    const list = run(process.execPath, [cliPath, "clips", "Field Research"]);
    expect(list.status, list.stderr).toBe(0);
    expect(list.stdout).toContain(`${CLIP} | Frozen research source | Frozen English text`);
    const first = run("npm", ["run", "research:add-clip", "--", "Field Research", CLIP, file.path, ANCHOR]);
    expect(first.status, first.stderr).toBe(0);
    const second = run(process.execPath, [cliPath, "add-clip", PROJECT, CLIP, file.path, ANCHOR]);
    expect(second.status, second.stderr).toBe(0);
    const doc = JSON.parse(readFileSync(file.path, "utf8")) as ReturnType<typeof researchStashFixture>["doc"];
    expect(validateScriptDocumentV2(doc).valid).toBe(true);
    expect(doc.activeDraft.blocks).toHaveLength(4);
    expect(doc.activeDraft.blocks[1]?.id).not.toBe(doc.activeDraft.blocks[2]?.id);
    const validation = run(process.execPath, [validatorPath, file.path]);
    expect(validation.status, validation.stderr).toBe(0);
    expect(validation.stdout).toContain("4 row(s) validated.");
    for (const result of [list, first, second, validation]) {
      expect(`${result.stdout}${result.stderr}`).not.toContain(SECRET);
    }
  }, 90_000);
});
