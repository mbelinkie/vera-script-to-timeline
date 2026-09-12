import { mkdtemp, mkdir, rename, rm, writeFile } from "node:fs/promises";
import { execFile } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";

import { afterEach, describe, expect, it } from "vitest";

import {
  addShootSession,
  configureProjectLocalLibrary,
  createHandoffInventory,
  createShootRegistrationProject,
  type ProbeOutput,
  registerMaster,
  relinkFromLibrary,
  resolveMasterForJob,
} from "../src/shoot-registration.js";

const ids = {
  project: "40000000-0000-4000-8000-000000000001",
  libraryA: "40000000-0000-4000-8000-000000000002",
  libraryB: "40000000-0000-4000-8000-000000000003",
  session: "40000000-0000-4000-8000-000000000004",
  sourceA: "40000000-0000-4000-8000-000000000005",
  sourceB: "40000000-0000-4000-8000-000000000006",
} as const;

const documentRef = {
  documentId: "40000000-0000-4000-8000-000000000007",
  projectId: ids.project,
  liveHeadSequence: 9,
  contentHash: `sha256:${"a".repeat(64)}`,
};

const probe: ProbeOutput = {
  format: { format_name: "mov", duration: "2.5" },
  streams: [
    {
      codec_type: "video", codec_name: "prores", width: 1920, height: 1080,
      avg_frame_rate: "24000/1001", tags: { timecode: "01:00:00:00" },
      color_space: "bt709", color_transfer: "bt709", color_primaries: "bt709", color_range: "tv",
    },
    { codec_type: "audio", codec_name: "pcm_s24le", channels: 2, channel_layout: "stereo", sample_rate: "48000" },
  ],
};

const temporaryRoots: string[] = [];
const execFileAsync = promisify(execFile);

async function temporaryRoot(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "vera-shoot-registration-"));
  temporaryRoots.push(root);
  return root;
}

afterEach(async () => {
  await Promise.all(temporaryRoots.splice(0).map((root) => rm(root, { recursive: true, force: true })));
});

function project() {
  return addShootSession(
    createShootRegistrationProject(ids.project, { kind: "project_local", libraryId: ids.libraryA }),
    {
      id: ids.session, name: "Opening shoot", processingProfileVersion: "shoot/v1",
      frozenPrompter: {
        sourceDocument: documentRef,
        prompterExportSha256: `sha256:${"b".repeat(64)}`,
        beatMapSha256: `sha256:${"c".repeat(64)}`,
      },
    },
  );
}

describe("immutable shoot registration", () => {
  it("hashes and inspects a temporary synthetic camera master with ffprobe", async () => {
    const root = await temporaryRoot();
    const master = join(root, "synthetic.mp4");
    await execFileAsync("ffmpeg", [
      "-f", "lavfi", "-i", "testsrc=size=16x16:rate=24",
      "-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=48000",
      "-t", "0.2", "-c:v", "mpeg4", "-c:a", "aac", "-y", master,
    ]);

    const registered = await registerMaster(project(), ids.session, {
      id: ids.sourceA, path: master, library: { libraryId: ids.libraryA, rootPath: root },
    });

    expect(registered.source.mediaHash).toMatch(/^sha256:[a-f0-9]{64}$/u);
    expect(registered.source.inspection.durationMs).toBeGreaterThan(0);
    expect(registered.source.inspection.videoStreams[0]).toEqual(expect.objectContaining({ width: 16, height: 16, frameRate: "24/1" }));
    expect(registered.source.inspection.audioStreams[0]).toEqual(expect.objectContaining({ channels: 1, sampleRate: 48000 }));
  });

  it("registers a multi-file frozen shoot idempotently without serializing roots", async () => {
    const root = await temporaryRoot();
    const masters = join(root, "masters");
    await mkdir(masters);
    const first = join(masters, "A-cam.mov");
    const second = join(masters, "B-cam.mov");
    await writeFile(first, "authorized synthetic master one");
    await writeFile(second, "authorized synthetic master two");
    const library = { libraryId: ids.libraryA, rootPath: masters };

    const registered = await registerMaster(project(), ids.session, {
      id: ids.sourceA, path: first, library, probe: () => Promise.resolve(probe),
    });
    const multiFile = await registerMaster(registered.project, ids.session, {
      id: ids.sourceB, path: second, library, probe: () => Promise.resolve(probe),
    });
    const duplicate = await registerMaster(multiFile.project, ids.session, {
      id: "40000000-0000-4000-8000-000000000008", path: first, library, probe: () => Promise.resolve(probe),
    });

    expect(duplicate.duplicate).toBe(true);
    expect(duplicate.project.sessions[0]?.sources).toHaveLength(2);
    expect(duplicate.project.sessions[0]?.frozenPrompter.beatMapSha256).toBe(`sha256:${"c".repeat(64)}`);
    expect(JSON.stringify(duplicate.project)).not.toContain(root);
    expect(duplicate.source.locator).toEqual({ libraryId: ids.libraryA, relativePath: "A-cam.mov" });
  });

  it("does not publish a source when probing fails or lacks supported video", async () => {
    const root = await temporaryRoot();
    const master = join(root, "bad.mov");
    await writeFile(master, "authorized synthetic bad master");
    const initial = project();
    const registration = { id: ids.sourceA, path: master, library: { libraryId: ids.libraryA, rootPath: root }, probe: () => Promise.resolve({ format: { format_name: "mov", duration: "1" }, streams: [] }) };

    await expect(registerMaster(initial, ids.session, registration)).rejects.toThrow("supported video");
    expect(initial.sessions[0]?.sources).toEqual([]);
  });

  it("relinks a renamed master and a handed-off byte-identical master without a new source", async () => {
    const rootA = await temporaryRoot();
    const sourcePath = join(rootA, "original.mov");
    await writeFile(sourcePath, "authorized synthetic master one");
    const initial = await registerMaster(project(), ids.session, {
      id: ids.sourceA, path: sourcePath, library: { libraryId: ids.libraryA, rootPath: rootA }, probe: () => Promise.resolve(probe),
    });
    const renamed = join(rootA, "renamed.mov");
    await rename(sourcePath, renamed);
    const moved = await relinkFromLibrary(initial.project, { libraryId: ids.libraryA, rootPath: rootA }, "2026-09-09T00:00:00.000Z");

    const rootB = await temporaryRoot();
    await writeFile(join(rootB, "handed-off.mov"), "authorized synthetic master one");
    await writeFile(join(rootB, "wrong.mov"), "different synthetic bytes");
    const handedOff = await relinkFromLibrary(configureProjectLocalLibrary(moved.project, ids.libraryB), { libraryId: ids.libraryB, rootPath: rootB }, "2026-09-09T00:01:00.000Z");
    const source = handedOff.project.sessions[0]?.sources[0];

    expect(handedOff.relinked).toEqual([ids.sourceA]);
    expect(handedOff.unmatched).toBe(1);
    expect(source?.id).toBe(ids.sourceA);
    expect(source?.relinkHistory.map(({ locator }) => locator.relativePath)).toEqual(["renamed.mov", "handed-off.mov"]);
    await expect(resolveMasterForJob(handedOff.project, { projectId: ids.project, sourceId: ids.sourceA, purpose: "transcription" }, [{ libraryId: ids.libraryB, rootPath: rootB }])).resolves.toMatchObject({ sourceId: ids.sourceA, path: join(rootB, "handed-off.mov") });
    const inventory = createHandoffInventory(handedOff.project, ids.session);
    expect(JSON.stringify(inventory)).not.toContain(rootA);
    expect(JSON.stringify(inventory)).not.toContain(rootB);
  });

  it("keeps unconfigured masters unlocated and denies mismatched jobs", async () => {
    const root = await temporaryRoot();
    const path = join(root, "unlocated.mov");
    await writeFile(path, "authorized synthetic master one");
    const noLibrary = addShootSession(
      createShootRegistrationProject(ids.project, { kind: "unconfigured" }),
      { id: ids.session, name: "No library", processingProfileVersion: "shoot/v1", frozenPrompter: { sourceDocument: documentRef, prompterExportSha256: `sha256:${"b".repeat(64)}`, beatMapSha256: `sha256:${"c".repeat(64)}` } },
    );
    const registered = await registerMaster(noLibrary, ids.session, { id: ids.sourceA, path, probe: () => Promise.resolve(probe) });

    expect(registered.source.locator).toBeUndefined();
    await expect(resolveMasterForJob(registered.project, { projectId: ids.project, sourceId: ids.sourceA, purpose: "transcription" }, [])).rejects.toThrow("no verified locator");
    await expect(resolveMasterForJob(project(), { projectId: "40000000-0000-4000-8000-000000000099", sourceId: ids.sourceA, purpose: "transcription" }, [])).rejects.toThrow("does not authorize");
  });
});

describe("project-library reconfiguration authorization", () => {
  it("invalidates stale source access until a hash-verified relink through the configured library", async () => {
    const rootA = await temporaryRoot();
    const masterA = join(rootA, "master.mov");
    await writeFile(masterA, "authorized synthetic master");
    const registered = await registerMaster(project(), ids.session, {
      id: ids.sourceA,
      path: masterA,
      library: { libraryId: ids.libraryA, rootPath: rootA },
      probe: () => Promise.resolve(probe),
    });
    const job = { projectId: ids.project, sourceId: ids.sourceA, purpose: "proxy" } as const;

    await expect(resolveMasterForJob(registered.project, job, [
      { libraryId: ids.libraryA, rootPath: rootA },
    ])).resolves.toEqual(expect.objectContaining({ path: masterA }));

    const configuredForB = configureProjectLocalLibrary(registered.project, ids.libraryB);
    await expect(resolveMasterForJob(configuredForB, job, [
      { libraryId: ids.libraryA, rootPath: rootA },
    ])).rejects.toThrow("no verified locator");

    const unconfigured = { ...structuredClone(registered.project), mediaLibrary: { kind: "unconfigured" } as const };
    await expect(resolveMasterForJob(unconfigured, job, [
      { libraryId: ids.libraryA, rootPath: rootA },
    ])).rejects.toThrow("configured local library");
    await expect(resolveMasterForJob(registered.project, { ...job, projectId: ids.libraryB }, [
      { libraryId: ids.libraryA, rootPath: rootA },
    ])).rejects.toThrow("does not authorize this project");
    await expect(resolveMasterForJob(registered.project, { ...job, sourceId: ids.sourceB }, [
      { libraryId: ids.libraryA, rootPath: rootA },
    ])).rejects.toThrow("does not authorize this source");

    const rootB = await temporaryRoot();
    const masterB = join(rootB, "relinked.mov");
    await writeFile(masterB, "authorized synthetic master");
    const relinked = await relinkFromLibrary(configuredForB, {
      libraryId: ids.libraryB,
      rootPath: rootB,
    }, "2026-09-12T00:00:00.000Z");
    const libraries = [
      { libraryId: ids.libraryA, rootPath: rootA },
      { libraryId: ids.libraryB, rootPath: rootB },
    ];

    await expect(resolveMasterForJob(relinked.project, job, libraries)).resolves.toEqual(
      expect.objectContaining({ sourceId: ids.sourceA, path: masterB }),
    );

    await writeFile(masterB, "changed bytes");
    await expect(resolveMasterForJob(relinked.project, job, libraries)).rejects.toThrow("no verified locator");
    expect(JSON.stringify(relinked.project)).not.toContain(rootA);
    expect(JSON.stringify(relinked.project)).not.toContain(rootB);
    expect(JSON.stringify(createHandoffInventory(relinked.project, ids.session))).not.toContain("purpose");
  });
});
