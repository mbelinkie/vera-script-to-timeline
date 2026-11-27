import { describe, expect, it } from "vitest";
import { createHash } from "node:crypto";
import {
  createResearchClient, researchOrigin, resolveProjectName, matchingResearchClipCues, matchingResearchCutTranscript,
  type ResearchProject,
} from "../src/research-clip-client.js";
import { snapshotResearchCandidateV2 } from "../src/authoring-v2-research-snapshot.js";
import { researchCandidate, researchId } from "./issue-367-fixture.js";

const SECRET = "private-dev-credential-do-not-print";
const PROJECT = researchId(710002);
const CLIP = researchId(710001);

function fakeService(handler: (url: URL) => Response | Promise<Response>) {
  const calls: { url: URL; init: RequestInit | undefined }[] = [];
  const request: typeof fetch = async (input, init) => {
    const url = new URL(input instanceof Request ? input.url : String(input));
    calls.push({ url, init });
    return handler(url);
  };
  return { request, calls };
}

function client(request: typeof fetch) {
  return createResearchClient({ bearer: SECRET, request });
}

const serviceError = (status: number) => new Response(JSON.stringify({
  error: { code: "upstream", message: SECRET },
}), { status, headers: { "content-type": "application/json" } });

describe("authorized Research quote records", () => {
  const sourceId = researchId(730000);
  const quoteId = researchId(730001);
  const quote = { id: quoteId, projectId: PROJECT, sourceId, version: 3, kind: "quote",
    createdBy: researchId(730002), topics: ["Engines"], content: {
      text: "The whole original quotation.", latestDisplayText: "The shortened quotation.",
      speaker: "Sam Writer", location: "11", hidden: "upstream-only",
    } };
  const source = { id: sourceId, projectId: PROJECT, kind: "offline",
    bibliography: { title: { value: "The Reference Book" }, authors: { value: ["Jo Author"] } }, details: {} };

  it("loads a bounded page, looks up a shared source once and preserves exact and display text", async () => {
    const fake = fakeService((url) => {
      if (url.pathname.endsWith("/items")) {
        expect([...url.searchParams]).toEqual([["kind", "quote"], ["limit", "21"], ["offset", "40"]]);
        return Response.json(Array.from({ length: 21 }, (_, i) => ({ ...quote, id: researchId(740000 + i) })));
      }
      expect(url.pathname).toBe(`/api/projects/${PROJECT}/sources/${sourceId}`);
      return Response.json(source);
    });
    const page = await client(fake.request).quotes(PROJECT, 40);
    expect(page.nextOffset).toBe(60);
    expect(page.quotes).toHaveLength(20);
    expect(page.quotes[0]).toMatchObject({ researchProjectId: PROJECT, itemVersion: 3,
      sourceTitle: "The Reference Book", speakerName: "Sam Writer", text: quote.content.text,
      displayText: quote.content.latestDisplayText, topics: ["Engines"] });
    expect(page.quotes[0]!.citationText).toContain("Author");
    expect(JSON.stringify(page)).not.toContain("upstream-only");
    expect(fake.calls).toHaveLength(2);
  });

  it("refuses a wrong item or source before using it to build a quotation", async () => {
    const wrongId = client(fakeService(() => Response.json({ ...quote, id: sourceId })).request);
    await expect(wrongId.quote(PROJECT, quoteId)).rejects.toThrow("different Library item");
    const wrongSource = client(fakeService((url) =>
      Response.json(url.pathname.includes("/items/") ? quote : { ...source, projectId: sourceId })).request);
    await expect(wrongSource.quote(PROJECT, quoteId)).rejects.toThrow("different Library source");
    const wrongProject = client(fakeService(() => Response.json([{ ...quote, projectId: sourceId }])).request);
    await expect(wrongProject.quotes(PROJECT, 0)).rejects.toThrow("different Library item");
  });

  it("reads only the exact article top revision from the quote's authorized source", async () => {
    const captureId = researchId(730003);
    const revisionId = researchId(730004);
    const bytes = Buffer.from("kept synthetic bytes");
    const original = { versionId: "kept-object-version",
      sha256: createHash("sha256").update(bytes).digest("hex"), byteCount: bytes.length,
      mimeType: "image/png", width: 8, height: 6 };
    const fake = fakeService((url) => {
      if (url.pathname.endsWith("/extension-captures")) {
        expect(url.pathname).toContain(sourceId);
        return Response.json([{ sourceId, captureId, assets: [
          { role: "passage", revisionId: quoteId, ...original },
          { role: "top", revisionId, ...original, provenance: { kind: "user_supplied", source: "browser_extension" } },
        ] }]);
      }
      expect(url.pathname).toBe(`/api/projects/${PROJECT}/extension-captures/${captureId}/assets/top`);
      expect(url.searchParams.get("revisionId")).toBe(revisionId);
      return new Response(bytes, { headers: { "Content-Type": original.mimeType } });
    });
    const record = { researchProjectId: PROJECT, sourceId, itemId: quoteId, itemVersion: 3,
      text: quote.content.text, displayText: quote.content.text, citationText: "", italicSpan: null, sourceKind: "web_page" as const };
    const kept = await client(fake.request).readQuotePicture(PROJECT, record);
    expect(kept?.picture).toEqual({ researchProjectId: PROJECT, ownerKind: "web_capture", ownerId: captureId, revisionId, original });
    expect(kept?.bytes).toEqual(new Uint8Array(bytes));
    expect(fake.calls).toHaveLength(2);
  });

  it("checks attached picture bytes and rechecks its revision before accepting the pin", async () => {
    const bytes = Buffer.from("kept synthetic bytes");
    const original = { versionId: "kept-object-version",
      sha256: createHash("sha256").update(bytes).digest("hex"), byteCount: bytes.length,
      mimeType: "image/png", width: 8, height: 6 };
    const choice = { researchProjectId: PROJECT, sourceId, itemId: quoteId, itemVersion: 3,
      text: quote.content.text, displayText: quote.content.text, citationText: "", italicSpan: null };
    const revisionId = researchId(730004);
    for (const issue of ["none", "changed-bytes", "changed-revision", "denied"] as const) {
      let reads = 0;
      const fake = fakeService((url) => {
        if (!url.pathname.includes(`/source/${sourceId}`)) return serviceError(404);
        if (url.pathname.endsWith("/original")) {
          if (issue === "denied") return serviceError(403);
          return new Response(issue === "changed-bytes" ? Buffer.alloc(bytes.length) : bytes,
            { headers: { "Content-Type": original.mimeType } });
        }
        reads++;
        return Response.json({ revisionId: issue === "changed-revision" && reads > 1 ? quoteId : revisionId,
          assets: { original } });
      });
      const operation = client(fake.request).readQuotePicture(PROJECT, choice);
      if (issue === "denied") await expect(operation).rejects.toThrow("refused");
      else if (issue !== "none") expect(await operation).toBeNull();
      else expect((await operation)?.picture).toEqual({
        researchProjectId: PROJECT, ownerKind: "source", ownerId: sourceId, revisionId, original,
      });
    }
  });
});

describe("Research GET-only transport", () => {
  it("accepts bare loopback origins and rejects remote, embedded credentials, paths and other schemes", () => {
    expect(researchOrigin()).toBe("http://127.0.0.1:43111");
    expect(researchOrigin("http://localhost:43111/")).toBe("http://localhost:43111");
    expect(researchOrigin("http://[::1]:43111")).toBe("http://[::1]:43111");
    expect(researchOrigin("https://127.0.0.1:43111")).toBe("https://127.0.0.1:43111");
    for (const invalid of [
      "https://research.example.com", "http://192.168.1.2:43111", "http://127.0.0.2",
      "http://localhost.evil.test", "http://[::2]:43111", "file:///etc/passwd",
      "ftp://127.0.0.1:43111", "http://user:secret@localhost:43111",
      "http://localhost:43111/api", "http://localhost:43111/?q=1", "http://localhost:43111/#fragment",
      "not a URL", "",
    ]) {
      expect(() => researchOrigin(invalid)).toThrow("Research URL must be a bare loopback HTTP origin.");
    }
  });

  it("requires a well-formed dev bearer and never includes it in setup errors", () => {
    for (const bearer of [undefined, "", " \t ", `abc\r\n${SECRET}`]) {
      expect(() => createResearchClient({ bearer })).toThrow("Set VERA_RESEARCH_BEARER");
    }
    expect(() => createResearchClient({ bearer: SECRET, url: `http://${SECRET}.example.org` }))
      .toThrow("bare loopback HTTP origin");
  });

  it("fetches visible project summaries via GET with manual redirects and auth only to loopback", async () => {
    const visible = [{ id: PROJECT, name: "Field Research", currentUserRole: "viewer", memberCount: 1 }];
    const fake = fakeService(() => Response.json(visible));
    expect(await client(fake.request).projects()).toEqual(visible);
    expect(fake.calls).toHaveLength(1);
    expect(fake.calls[0]!.url.toString()).toBe("http://127.0.0.1:43111/api/projects");
    expect(fake.calls[0]!.init?.method).toBe("GET");
    expect(fake.calls[0]!.init?.redirect).toBe("manual");
    expect(fake.calls[0]!.init?.headers).toEqual({
      Accept: "application/json", Authorization: `Bearer ${SECRET}`,
    });
    expect(fake.calls[0]!.init?.signal).toBeInstanceOf(AbortSignal);
  });

  it("resolves exact case-insensitive names or UUIDs, and lists choices for no/ambiguous match", () => {
    const visible: ResearchProject[] = [
      { id: PROJECT, name: "Field Research" },
      { id: researchId(710010), name: "Other" },
      { id: researchId(710011), name: "FIELD RESEARCH" },
    ];
    expect(resolveProjectName(PROJECT.toUpperCase(), [])).toBe(PROJECT);
    expect(resolveProjectName("other", visible)).toBe(researchId(710010));
    expect(() => resolveProjectName("Field Research", visible)).toThrow(/Several Research projects.*Field Research/);
    expect(() => resolveProjectName("missing", visible)).toThrow(/No visible Research project.*Other/);
    expect(() => resolveProjectName("missing", [])).toThrow(/\(none\)/);
    expect(() => resolveProjectName("field", visible)).toThrow(/No visible Research project/);
    const tainted = [{ id: PROJECT, name: "Other\n\u001b[31m" }];
    expect(() => resolveProjectName("missing", tainted)).toThrow(/Other {2}\[31m/);
    const misleading = [{ id: PROJECT, name: "Other\u202e\u2028Name" }];
    expect(() => resolveProjectName("missing", misleading)).toThrow("Other  Name");
  });

  it("rejects invalid project-list DTOs rather than trusting the response", async () => {
    for (const body of [null, {}, { projects: [] }, [{ id: "not-a-uuid", name: "X" }],
      [{ id: PROJECT, name: "" }], [{ id: PROJECT, name: 123 }], [null],
    ]) {
      await expect(client(fakeService(() => Response.json(body)).request).projects())
        .rejects.toThrow("Research returned an invalid project list.");
    }
  });

  it("fetches a clip list and a selected clip with exact project/clip identity", async () => {
    const candidate = researchCandidate();
    const initial = structuredClone(candidate);
    const fake = fakeService((url) => {
      if (url.pathname.endsWith("/clips")) return Response.json([candidate]);
      return Response.json(candidate);
    });
    const api = client(fake.request);
    expect(await api.clips(PROJECT)).toEqual([candidate]);
    expect(await api.clip(PROJECT, CLIP)).toEqual(candidate);
    expect(candidate).toEqual(initial);
    expect(fake.calls.map(({ url }) => url.pathname)).toEqual([
      `/api/projects/${PROJECT}/clips`,
      `/api/projects/${PROJECT}/clips/${CLIP}`,
    ]);
    expect(fake.calls.every(({ init }) => init?.method === "GET" && init.redirect === "manual"))
      .toBe(true);
  });

  it("refuses invalid IDs before sending a request", async () => {
    const fake = fakeService(() => Response.json([]));
    const api = client(fake.request);
    await expect(api.clips("../another-project")).rejects.toThrow("Research project ID must be a UUID");
    await expect(api.clip(PROJECT, "not-a-uuid")).rejects.toThrow("Research project and clip IDs");
    await expect(api.clip("bad-id", CLIP)).rejects.toThrow("Research project and clip IDs");
    expect(fake.calls).toHaveLength(0);
  });

  it("refuses malformed clips and cross-project or cross-clip identities", async () => {
    const valid = researchCandidate();
    for (const malformed of [null, {}, { ...valid, projectId: "bad" },
      { ...valid, selection: { ...valid.selection, transcriptVersion: 0 } },
      { ...valid, englishText: undefined },
    ]) {
      await expect(client(fakeService(() => Response.json([malformed])).request).clips(PROJECT))
        .rejects.toThrow("Research returned an invalid logged clip.");
    }
    const wrongProject = { ...valid, projectId: researchId(710020) };
    await expect(client(fakeService(() => Response.json([wrongProject])).request).clips(PROJECT))
      .rejects.toThrow("Research returned a clip from another project.");
    await expect(client(fakeService(() => Response.json(wrongProject)).request).clip(PROJECT, CLIP))
      .rejects.toThrow("Research returned a different clip identity.");
    await expect(client(fakeService(() => Response.json({ ...valid, id: researchId(710021) })).request)
      .clip(PROJECT, CLIP)).rejects.toThrow("Research returned a different clip identity.");
    await expect(client(fakeService(() => Response.json({ clips: [valid] })).request).clips(PROJECT))
      .rejects.toThrow("Research returned an invalid clip list.");
  });

  it("refuses 302/307/308 without following Location, and translates 401/403/404/500 safely", async () => {
    for (const status of [302, 307, 308]) {
      const fake = fakeService(() => new Response(null, {
        status, headers: { Location: `https://${SECRET}.example.net/redirect` },
      }));
      await expect(client(fake.request).projects()).rejects.toThrow("no redirect was followed");
      expect(fake.calls).toHaveLength(1);
      expect(fake.calls[0]!.init?.redirect).toBe("manual");
    }
    for (const [status, message] of [
      [401, "refused the credential or project access"],
      [403, "refused the credential or project access"],
      [404, "project or clip was not found"],
      [500, "could not complete this read-only request"],
    ] as const) {
      await expect(client(fakeService(() => serviceError(status)).request).clips(PROJECT))
        .rejects.toThrow(message);
    }
  });

  it("translates outages, invalid JSON and hostile upstream errors without revealing the bearer", async () => {
    const outage: typeof fetch = () => Promise.reject(new Error(`fetch failed: Authorization: Bearer ${SECRET}`));
    const responses: Array<Promise<unknown>> = [
      client(outage).projects(),
      client(fakeService(() => new Response(`broken JSON with ${SECRET}`)).request).projects(),
      client(fakeService(() => serviceError(403)).request).projects(),
      client(fakeService(() => Response.json([{ id: "wrong", name: SECRET }])).request).projects(),
      client(fakeService(() => Response.json({ ...researchCandidate(), selection: { trackId: SECRET } })).request)
        .clip(PROJECT, CLIP),
    ];
    const results = await Promise.allSettled(responses);
    expect(results.every((r) => r.status === "rejected")).toBe(true);
    const messages = results.map((r) => r.status === "rejected" ? String(r.reason) : "");
    expect(messages.join(" | ")).not.toContain(SECRET);
    expect(messages[0]).toContain("Research is unavailable");
    expect(messages[1]).toContain("Research returned invalid JSON");
  });
});

describe("published transcript cue read", () => {
  const pin = snapshotResearchCandidateV2(researchCandidate());
  function workspace() {
    return {
      schemaVersion: 1, catalogState: "active_verified", projectId: pin.researchProjectId,
      catalogVideoId: pin.catalogVideoId, youtubeVideoId: pin.video.youtubeVideoId,
      english: { track: { id: pin.loggedSelection.trackId, version: pin.loggedSelection.transcriptVersion,
        videoId: pin.video.youtubeVideoId, kind: "english", language: "en", timingPrecision: "word" },
        segments: [
          { id: pin.loggedSelection.firstSegmentId, trackId: pin.loggedSelection.trackId,
            startMs: 1000, endMs: 2000, text: "First" },
          { id: pin.loggedSelection.lastSegmentId, trackId: pin.loggedSelection.trackId,
            startMs: 2000, endMs: 4000, text: "Last" },
          { id: researchId(710025), trackId: pin.loggedSelection.trackId,
            startMs: 4000, endMs: 5000, text: "Not logged" },
        ], tokens: [{ text: "not returned" }],
      },
    };
  }
  it("returns minimal caption intervals only, even from word-timed tracks", async () => {
    const fake = fakeService(() => Response.json(workspace()));
    expect(await client(fake.request).matchedClipCues(pin)).toEqual([
      { startMs: 1000, endMs: 2000, text: "First" }, { startMs: 2000, endMs: 4000, text: "Last" },
    ]);
    expect(fake.calls[0]!.url.pathname).toBe(`/api/projects/${pin.researchProjectId}/videos/${pin.catalogVideoId}/transcript`);
    expect(fake.calls[0]!.url.searchParams.get("preferredLanguage")).toBe("en");
    expect(fake.calls[0]!.init?.method).toBe("GET");
  });
  it("falls back on each identity mismatch, offline/estimated tracks or malformed segments", () => {
    for (const change of [
      (w: ReturnType<typeof workspace>) => { w.projectId = researchId(1); },
      (w: ReturnType<typeof workspace>) => { w.catalogVideoId = researchId(2); },
      (w: ReturnType<typeof workspace>) => { w.youtubeVideoId = "different"; },
      (w: ReturnType<typeof workspace>) => { w.english.track.id = researchId(3); },
      (w: ReturnType<typeof workspace>) => { w.english.track.version++; },
      (w: ReturnType<typeof workspace>) => { w.english.track.videoId = "different"; },
      (w: ReturnType<typeof workspace>) => { w.english.track.language = "es"; },
      (w: ReturnType<typeof workspace>) => { w.english.track.kind = "translation"; },
      (w: ReturnType<typeof workspace>) => { w.english.track.timingPrecision = "estimated"; },
      (w: ReturnType<typeof workspace>) => { w.catalogState = "offline_cached"; },
      (w: ReturnType<typeof workspace>) => { w.english.segments[0]!.trackId = researchId(4); },
      (w: ReturnType<typeof workspace>) => { w.english.segments[0]!.endMs = 1000; },
      (w: ReturnType<typeof workspace>) => { w.english.segments.shift(); },
    ]) {
      const changed = workspace();
      change(changed);
      expect(matchingResearchClipCues(changed, pin)).toBeNull();
    }
  });
  it("bounds the response and refuses invalid JSON", async () => {
    for (const body of ["not JSON", JSON.stringify({ large: "x".repeat(4 * 1024 * 1024) })]) {
      expect(await client(fakeService(() => new Response(body)).request).matchedClipCues(pin)).toBeNull();
    }
  });
});

describe("digest-bound Research cut transcript", () => {
  const pin = snapshotResearchCandidateV2(researchCandidate());
  const version = researchId(710099);
  const clock = {
    schemaVersion: 1 as const,
    transcriptVersionId: version,
    trackId: pin.loggedSelection.trackId,
    trackVersion: pin.loggedSelection.transcriptVersion,
    mediaSha256: "1".repeat(64),
    trackContentSha256: "2".repeat(64),
    alignmentFingerprint: "3".repeat(64),
    alignmentAudioSha256: `sha256:${"4".repeat(64)}`,
    firstFrame: { numerator: 1, denominator: 1 },
    frameDuration: { numerator: 1001, denominator: 24000 },
    frameCount: 96,
  };
  function workspace() {
    const { trackId, transcriptVersion, firstSegmentId, lastSegmentId } = pin.loggedSelection;
    return {
      schemaVersion: 1, catalogState: "active_verified", transcriptVersionId: version,
      projectId: pin.researchProjectId, catalogVideoId: pin.catalogVideoId, youtubeVideoId: pin.video.youtubeVideoId,
      english: {
        track: { id: trackId, version: transcriptVersion, videoId: pin.video.youtubeVideoId,
          contentSha256: clock.trackContentSha256, alignment: { fingerprint: clock.alignmentFingerprint,
            audio: { hash: clock.alignmentAudioSha256, sampleRate: 16000, durationSamples: 120000 } } },
        segments: [
          { id: firstSegmentId, trackId, startMs: 1000, endMs: 1500, text: "First cue" },
          { id: lastSegmentId, trackId, startMs: 1500, endMs: 3000, text: "Second cue" },
        ],
        tokens: [
          { id: researchId(100), segmentId: firstSegmentId, startMs: 1041, endMs: 1084,
            text: "First", alignmentStatus: "acoustic" },
          { id: researchId(101), segmentId: lastSegmentId, startMs: 1510, endMs: 1600,
            text: "Second", alignmentStatus: "acoustic" },
        ],
      },
    };
  }
  it("quantizes acoustic words against the rational cut clock", async () => {
    const service = fakeService(() => Response.json(workspace()));
    expect(await client(service.request).matchedCutTranscript(pin, clock)).toEqual({
      precision: "word", entries: [
        { startFrame: 0, activeStartFrame: 1, endFrame: 3, text: "First" },
        { startFrame: 12, activeStartFrame: 13, endFrame: 15, text: "Second" },
      ],
    });
  });
  it("falls back to verified cues for unaligned words or full text for a mismatched identity", () => {
    const partial = workspace();
    partial.english.tokens[0]!.alignmentStatus = "unaligned";
    expect(matchingResearchCutTranscript(partial, pin, clock)).toMatchObject({ precision: "cue" });
    const sameFrame = workspace();
    sameFrame.english.tokens.push({
      ...sameFrame.english.tokens[1]!, id: researchId(102), startMs: 1511, endMs: 1599, text: "Duplicate boundary",
    });
    expect(matchingResearchCutTranscript(sameFrame, pin, clock)).toMatchObject({ precision: "cue" });
    for (const different of [
      { ...clock, transcriptVersionId: researchId(105) },
      { ...clock, trackContentSha256: "5".repeat(64) },
      { ...clock, alignmentAudioSha256: `sha256:${"6".repeat(64)}` },
      { ...clock, frameCount: 1000 },
    ]) expect(matchingResearchCutTranscript(workspace(), pin, different)).toBeNull();
  });
});

describe("kept still catalog metadata", () => {
  const sourceId = researchId(750000);
  const still = { id: researchId(750001), projectId: PROJECT, sourceId, kind: "still", version: 3,
    createdAt: "2026-11-15T12:00:00Z", createdBy: researchId(750002), topics: ["Transport"],
    content: { title: " Harbor still ", credit: "Archive collection", licence: "Test licence", hidden: SECRET } };
  const asset = { versionId: "synthetic-kept", sha256: "a".repeat(64), byteCount: 12,
    width: 8, height: 8, mimeType: "image/png" };
  const manifest = { assets: { original: asset, thumbnail: asset }, provenance: { kind: "file", inputSha256: asset.sha256 } };
  const source = { id: sourceId, projectId: PROJECT, kind: "image", details: {},
    bibliography: { title: { value: "Coastal photographs" } } };

  it("returns validated list metadata and caches shared source titles within the raw page", async () => {
    const entries = Array.from({ length: 13 }, (_, i) => ({ ...still, id: researchId(751000 + i) }));
    const fake = fakeService((url) => {
      if (url.pathname.endsWith("/items")) {
        expect([...url.searchParams]).toEqual([["kind", "still"], ["limit", "13"], ["offset", "24"]]);
        return Response.json(entries);
      }
      if (url.pathname.endsWith("/assets")) {
        if (url.pathname.includes(entries[0]!.id)) return serviceError(404);
        return Response.json(manifest);
      }
      expect(url.pathname).toBe(`/api/projects/${PROJECT}/sources/${sourceId}`);
      return Response.json(source);
    });
    const page = await client(fake.request).stills(PROJECT, 24);
    expect(page.nextOffset).toBe(36);
    expect(page.stills).toHaveLength(11);
    expect(page.stills[0]).toEqual({ researchProjectId: PROJECT, itemId: entries[1]!.id, itemVersion: 3,
      title: "Harbor still", credit: "Archive collection", licence: "Test licence",
      createdAt: still.createdAt, logger: still.createdBy, topics: ["Transport"], sourceTitle: "Coastal photographs" });
    expect(fake.calls.filter(({ url }) => url.pathname.includes("/sources/"))).toHaveLength(1);
    expect(JSON.stringify(page)).not.toContain(SECRET);
  });

  it("keeps list-only metadata out of the saved snapshot and tolerates a missing source title", async () => {
    const fake = fakeService((url) => {
      if (url.pathname.endsWith("/items")) return Response.json([still]);
      if (url.pathname.endsWith("/assets")) return Response.json(manifest);
      if (url.pathname.includes("/sources/")) return serviceError(404);
      return Response.json(still);
    });
    const api = client(fake.request);
    expect((await api.stills(PROJECT, 0)).stills[0]).not.toHaveProperty("sourceTitle");
    const saved = await api.still(PROJECT, still.id, 3);
    expect(saved).toEqual({ researchProjectId: PROJECT, itemId: still.id, itemVersion: 3, sourceId,
      title: "Harbor still", credit: "Archive collection", licence: "Test licence",
      original: asset, provenance: manifest.provenance });
  });

  it("keeps valid stills on a page with malformed records and refuses authorization failures", async () => {
    const badAssets = { ...still, id: researchId(752000) };
    const entries = [
      { ...still, id: researchId(752001), createdBy: "invalid" },
      { ...still, id: researchId(752002), createdAt: "invalid" },
      { ...still, id: researchId(752003), topics: [123] },
      badAssets,
      still,
    ];
    const fake = fakeService((url) => {
      if (url.pathname.endsWith("/items")) return Response.json(entries);
      if (url.pathname.includes("/sources/")) return serviceError(503);
      if (url.pathname.includes(badAssets.id)) return Response.json({ assets: {} });
      return Response.json(manifest);
    });
    const page = await client(fake.request).stills(PROJECT, 0);
    expect(page.stills.map(({ itemId }) => itemId)).toEqual([still.id]);
    expect(page.stills[0]).not.toHaveProperty("sourceTitle");
    for (const status of [403, 429, 503]) {
      const unavailable = fakeService((url) => url.pathname.endsWith("/items")
        ? Response.json([still]) : serviceError(status));
      const page = client(unavailable.request).stills(PROJECT, 0);
      if (status === 403) await expect(page).rejects.toMatchObject({ status });
      else await expect(page).rejects.toThrow("Research could not complete this read-only request.");
    }
  });
});
