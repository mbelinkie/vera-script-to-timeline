import { describe, expect, it } from "vitest";
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
