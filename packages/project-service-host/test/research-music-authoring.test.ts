import { createHash } from "node:crypto";
import { mkdtemp, readFile, realpath, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it, vi } from "vitest";
import { createResearchClient } from "@vera/contracts/research-clip-client";
import { ProjectAuthError } from "@vera/project-authorization";
import { createAuthoringHandler } from "../src/authoring.js";
import { resolveResearchMusicSource } from "../src/research-music-authoring.js";

const timelineId = "10000000-0000-4000-8000-000000000001";
const researchId = "20000000-0000-4000-8000-000000000001";
const sourceId = "20000000-0000-4000-8000-000000000002";
const itemId = "20000000-0000-4000-8000-000000000003";
const clipId = "20000000-0000-4000-8000-000000000004";
const origin = "http://127.0.0.1:42117";
const editorBearer = "Bearer editor-fixture";
const project = "/api/projects/" + researchId;
const list = origin + "/authoring/research/" + timelineId + "/projects/" + researchId + "/music";
const browserHeaders = { "x-vera-authoring": "1", "sec-fetch-site": "same-origin", origin };
const cwd = fileURLToPath(new URL("../../../", import.meta.url));

function generatedWav() {
  const wav = Buffer.alloc(44 + 5 * 48_000 * 2);
  wav.write("RIFF");
  wav.writeUInt32LE(wav.length - 8, 4);
  wav.write("WAVEfmt ", 8);
  wav.writeUInt32LE(16, 16);
  wav.writeUInt16LE(1, 20);
  wav.writeUInt16LE(1, 22);
  wav.writeUInt32LE(48000, 24);
  wav.writeUInt32LE(96000, 28);
  wav.writeUInt16LE(2, 32);
  wav.writeUInt16LE(16, 34);
  wav.write("data", 36);
  wav.writeUInt32LE(wav.length - 44, 40);
  return wav;
}

function setup() {
  const wav = generatedWav();
  const playbackHash = "sha256:" + createHash("sha256").update(wav).digest("hex");
  const item = {
    id: itemId, projectId: researchId, sourceId, version: 3, kind: "audio",
    content: { title: "Harbor score", role: "music", startMs: 1000, endMs: 4000 },
  };
  const source = { id: sourceId, projectId: researchId, kind: "audio", version: 2, bibliography: {}, details: {} };
  const manifest = { durationMs: 5000, playbackDurationMs: 5000,
    mimeType: "audio/wav", playbackSha256: playbackHash.slice(7), origin: { kind: "url" } };
  const state = { visible: true, corrupt: false, denyEdit: false, denyView: false, changeDuringPlayback: false, absent: false };
  const request = vi.fn<typeof fetch>(async (input, init) => {
    expect(new Headers(init?.headers).get("authorization")).toBe("Bearer research-fixture");
    const url = new URL(String(input));
    if (url.pathname === "/api/projects") return Response.json(state.visible ? [{ id: researchId, name: "Research fixture" }] : []);
    if (url.pathname === project + "/items") {
      expect(url.search).toBe("?kind=audio&limit=13&offset=0");
      return Response.json([item, { ...item, id: clipId, content: { ...item.content, role: "speech" } }]);
    }
    if (url.pathname === project + "/items/" + itemId) {
      return state.absent ? new Response(null, { status: 404 }) : Response.json(item);
    }
    if (url.pathname === project + "/sources/" + sourceId) return Response.json(source);
    if (url.pathname === project + "/audio/" + sourceId) return Response.json(manifest);
    if (url.pathname === project + "/audio/" + sourceId + "/playback") {
      if (state.changeDuringPlayback) item.version++;
      return new Response(state.corrupt ? new Uint8Array([0]) : new Uint8Array(wav), {
        headers: { "Content-Type": "audio/wav" },
      });
    }
    return new Response(null, { status: 404 });
  });
  const catalog = createResearchClient({ bearer: "research-fixture", request });
  const authorizeTimelineProject = vi.fn(async (_id: string, action = "view_document") => {
    if (state.denyView || state.denyEdit && action === "edit_document") throw new ProjectAuthError("action_not_allowed", 403);
  });
  const research = { catalog, authorizeTimelineProject };
  const config = { projectId: timelineId, mediaRoot: "/unused", cwd, python: join(cwd, ".venv/bin/python") };
  const host = createAuthoringHandler(origin, editorBearer, () => Promise.resolve(new Response(null, { status: 500 })),
    research, false, authorizeTimelineProject, config);
  const listChoices = async () => {
    const enrolled = await host.handle(new Request(origin + "/authoring/session", {
      method: "POST", headers: { ...browserHeaders, "x-vera-launch": host.launchCode },
    }));
    const { sessionProof } = await enrolled!.json() as { sessionProof: string };
    return host.handle(new Request(list, { headers: { ...browserHeaders, "x-vera-session": sessionProof } }));
  };
  const selection = { researchProjectId: researchId, sourceId, itemId, itemVersion: 3, sourceVersion: 2,
    title: "Harbor score", startMs: 1000, endMs: 4000, playbackHash };
  return { config, host, item, listChoices, manifest, request, research, selection, source, state };
}

describe("project Research Music", () => {
  it("lists only named Music and checks the editor and both project permissions", async () => {
    const { host, listChoices, manifest, request, selection, state } = setup();
    expect((await host.handle(new Request(list, { headers: browserHeaders })))?.status).toBe(401);
    state.denyView = true;
    expect((await listChoices())?.status).toBe(403);
    expect(request).not.toHaveBeenCalled();
    state.denyView = false;
    expect(await (await listChoices())?.json()).toEqual({
      music: [{ status: "candidate", selection }], nextOffset: null,
    });
    expect(request.mock.calls.some(([url]) => String(url).endsWith("/playback"))).toBe(false);
    manifest.origin.kind = "file";
    expect(await (await listChoices())?.json()).toMatchObject({
      music: [{ status: "relink_required", selection: { itemId, title: "Harbor score" } }],
    });
    state.visible = false;
    expect((await listChoices())?.status).toBe(403);
  });

  it("resolves the exact kept bytes and refuses stale, missing, corrupt or unauthorized choices", async () => {
    const { config, manifest, request, research, selection, source, state } = setup();
    const scratch = await realpath(await mkdtemp(join(tmpdir(), "vera-music-")));
    try {
      config.mediaRoot = scratch;
      const resolve = () => resolveResearchMusicSource(research, config, timelineId, researchId, selection);
      state.denyEdit = true;
      await expect(resolve()).rejects.toMatchObject({ status: 403 });
      expect(request).not.toHaveBeenCalled();
      state.denyEdit = false;
      state.absent = true;
      await expect(resolve()).rejects.toMatchObject({ status: 404 });
      state.absent = false;
      source.version++;
      await expect(resolve()).rejects.toMatchObject({ status: 409 });
      source.version--;
      manifest.origin.kind = "file";
      await expect(resolve()).rejects.toThrow("Relink");
      manifest.origin.kind = "url";
      state.corrupt = true;
      await expect(resolve()).rejects.toMatchObject({ status: 422 });
      state.corrupt = false;
      const prepared = await resolve();
      expect(prepared.durationSamples).toBe(144000);
      expect(prepared.source.researchSelection).toEqual(selection);
      const preparedBytes = await readFile(join(scratch, "Research Music", timelineId, prepared.source.artifactId + ".wav"));
      expect(prepared.source.contentHash).toBe("sha256:" + createHash("sha256").update(preparedBytes).digest("hex"));
      state.changeDuringPlayback = true;
      await expect(resolve()).rejects.toMatchObject({ status: 409 });
    } finally {
      await rm(scratch, { recursive: true, force: true });
    }
  }, 15_000);
});
