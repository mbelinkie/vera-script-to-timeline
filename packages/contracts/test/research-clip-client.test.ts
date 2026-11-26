import { describe, expect, it } from "vitest";
import { createHash } from "node:crypto";
import {
  createResearchClient, researchOrigin, resolveProjectName,
  type ResearchProject,
} from "../src/research-clip-client.js";
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

  it("rejects malformed catalog metadata rather than fabricating filter values", async () => {
    for (const change of [{ createdBy: "invalid" }, { createdAt: "invalid" }, { topics: [123] }]) {
      const fake = fakeService((url) => url.pathname.endsWith("/items")
        ? Response.json([{ ...still, ...change }]) : Response.json(manifest));
      await expect(client(fake.request).stills(PROJECT, 0)).rejects.toThrow("invalid still catalog metadata");
    }
  });
});
