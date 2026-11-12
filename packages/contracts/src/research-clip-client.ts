/**
 * Read-only, development-only bridge to Research's logged clip API.
 * The bearer is deliberately confined to loopback HTTP requests and is never
 * included in errors or returned values.
 */
import {
  snapshotResearchCandidateV2,
  type ResearchLoggedCandidateInputV2,
} from "./authoring-v2-research-snapshot.js";

export interface ResearchProject {
  id: string;
  name: string;
}

const UUID = /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i;
const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "[::1]"]);
const DEFAULT_ORIGIN = "http://127.0.0.1:43111";

/** Refuse remote, credential-bearing, or path-extended service URLs. */
export function researchOrigin(raw = DEFAULT_ORIGIN): string {
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new Error("Research URL must be a bare loopback HTTP origin.");
  }
  if (
    (url.protocol !== "http:" && url.protocol !== "https:") ||
    !LOOPBACK_HOSTS.has(url.hostname) ||
    url.username !== "" || url.password !== "" ||
    url.pathname !== "/" || url.search !== "" || url.hash !== ""
  ) {
    throw new Error("Research URL must be a bare loopback HTTP origin.");
  }
  return url.origin;
}

function safeProjectLabel(project: ResearchProject): string {
  // API data can become CLI output, so never emit control characters/ANSI escapes.
  const name = [...project.name].map((char) => {
    const code = char.codePointAt(0)!;
    return code < 32 || (code >= 127 && code <= 159) ? " " : char;
  }).join("");
  return `${name} (${project.id})`;
}

/** A UUID is passed straight to the server (which enforces project access). */
export function resolveProjectName(nameOrId: string, visible: readonly ResearchProject[]): string {
  if (UUID.test(nameOrId)) return nameOrId.toLowerCase();
  const matches = visible.filter((project) =>
    project.name.toLocaleLowerCase("en-US") === nameOrId.toLocaleLowerCase("en-US"));
  if (matches.length === 1) return matches[0]!.id;
  const choices = (matches.length > 0 ? matches : visible).map(safeProjectLabel).join(", ") || "(none)";
  if (matches.length > 1) {
    throw new Error(`Several Research projects have that name; use an ID: ${choices}.`);
  }
  throw new Error(`No visible Research project matches that name; visible projects: ${choices}.`);
}

export function createResearchClient(options: {
  bearer: string | undefined;
  url?: string;
  request?: typeof fetch;
}) {
  const origin = researchOrigin(options.url);
  const bearer = options.bearer;
  if (!bearer?.trim() || /[\r\n]/.test(bearer)) {
    throw new Error("Set VERA_RESEARCH_BEARER before accessing Research.");
  }
  const request = options.request ?? fetch;

  async function get(path: string): Promise<unknown> {
    let response: Response;
    try {
      response = await request(new URL(path, origin), {
        method: "GET",
        redirect: "manual",
        headers: { Accept: "application/json", Authorization: `Bearer ${bearer}` },
        signal: AbortSignal.timeout(10_000),
      });
    } catch {
      // Fetch errors may embed the full request URL or headers, including secrets.
      throw new Error("Research is unavailable on this Mac.");
    }
    if (response.status >= 300 && response.status < 400 || response.redirected) {
      throw new Error("Research redirected the read-only request; no redirect was followed.");
    }
    if (response.status === 401 || response.status === 403) {
      throw new Error("Research refused the credential or project access.");
    }
    if (response.status === 404) {
      throw new Error("Research project or clip was not found.");
    }
    if (!response.ok) {
      throw new Error("Research could not complete this read-only request.");
    }
    try {
      return await response.json() as unknown;
    } catch {
      throw new Error("Research returned invalid JSON.");
    }
  }

  function validatedCandidate(input: unknown): ResearchLoggedCandidateInputV2 {
    try {
      snapshotResearchCandidateV2(input as ResearchLoggedCandidateInputV2);
      return input as ResearchLoggedCandidateInputV2;
    } catch {
      // Never forward upstream data or validation errors to CLI stderr.
      throw new Error("Research returned an invalid logged clip.");
    }
  }

  return {
    async projects(): Promise<ResearchProject[]> {
      const result = await get("/api/projects");
      if (!Array.isArray(result) || !result.every((project: unknown) =>
        project !== null && typeof project === "object" && !Array.isArray(project) &&
        UUID.test(String((project as ResearchProject).id)) &&
        typeof (project as ResearchProject).name === "string" &&
        (project as ResearchProject).name.trim().length > 0)) {
        throw new Error("Research returned an invalid project list.");
      }
      return result as ResearchProject[];
    },

    async clips(projectId: string): Promise<ResearchLoggedCandidateInputV2[]> {
      if (!UUID.test(projectId)) throw new Error("Research project ID must be a UUID.");
      const result = await get(`/api/projects/${projectId}/clips`);
      if (!Array.isArray(result)) throw new Error("Research returned an invalid clip list.");
      return result.map((item: unknown) => {
        const clip = validatedCandidate(item);
        if (clip.projectId.toLowerCase() !== projectId.toLowerCase()) {
          throw new Error("Research returned a clip from another project.");
        }
        return clip;
      });
    },

    async clip(projectId: string, clipId: string): Promise<ResearchLoggedCandidateInputV2> {
      if (!UUID.test(projectId) || !UUID.test(clipId)) {
        throw new Error("Research project and clip IDs must be UUIDs.");
      }
      const clip = validatedCandidate(await get(`/api/projects/${projectId}/clips/${clipId}`));
      if (clip.projectId.toLowerCase() !== projectId.toLowerCase() ||
          clip.id.toLowerCase() !== clipId.toLowerCase()) {
        throw new Error("Research returned a different clip identity.");
      }
      return clip;
    },
  };
}
