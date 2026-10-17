import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { readdir, stat } from "node:fs/promises";
import { basename, isAbsolute, relative, resolve, sep } from "node:path";
import { promisify } from "node:util";
import { execFile } from "node:child_process";

import type {
  DocumentReference,
  PrompterExportReference,
  LocalSourceHandoffInventoryV1,
  ShootRegistrationProjectV1,
  ShootSession,
  ShootSource,
  SourceInspection,
  SourceLocator,
} from "./generated/contracts.js";

const execFileAsync = promisify(execFile);
const hashPattern = /^sha256:[a-f0-9]{64}$/u;
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;

export interface LibraryRoot {
  libraryId: string;
  /** Local-only configuration. Never place this value in a project record. */
  rootPath: string;
}

export interface ProbeOutput {
  format?: { format_name?: string; duration?: string };
  streams?: Array<{
    codec_type?: string;
    codec_name?: string;
    width?: number;
    height?: number;
    avg_frame_rate?: string;
    r_frame_rate?: string;
    tags?: { timecode?: string };
    color_space?: string;
    color_transfer?: string;
    color_primaries?: string;
    color_range?: string;
    channels?: number;
    channel_layout?: string;
    sample_rate?: string;
  }>;
}

export type Probe = (path: string) => Promise<ProbeOutput>;

export interface RegisterMasterInput {
  id: string;
  path: string;
  library?: LibraryRoot;
  probe?: Probe;
}

export interface JobAccess {
  projectId: string;
  sourceId: string;
  purpose: "proxy" | "transcription";
}

export interface RegisterMasterResult {
  project: ShootRegistrationProjectV1;
  source: ShootSource;
  duplicate: boolean;
}

export function createShootRegistrationProject(
  projectId: string,
  mediaLibrary: ShootRegistrationProjectV1["mediaLibrary"],
): ShootRegistrationProjectV1 {
  assertUuid(projectId, "project ID");
  if (mediaLibrary.kind === "project_local") assertUuid(mediaLibrary.libraryId, "library ID");
  return { schemaVersion: "shoot-registration/v1", projectId, mediaLibrary, sessions: [] };
}

/** Records the opaque local-library identity; its absolute root remains runtime-only. */
export function configureProjectLocalLibrary(
  project: ShootRegistrationProjectV1,
  libraryId: string,
): ShootRegistrationProjectV1 {
  assertUuid(libraryId, "library ID");
  return { ...structuredClone(project), mediaLibrary: { kind: "project_local", libraryId } };
}

export function addShootSession(
  project: ShootRegistrationProjectV1,
  session: Omit<ShootSession, "sources">,
): ShootRegistrationProjectV1 {
  assertUuid(session.id, "session ID");
  if (project.sessions.some(({ id }) => id === session.id)) throw new Error("Shoot session ID is already registered.");
  if (session.name.trim() === "" || [...session.name].length > 255 || session.processingProfileVersion.trim() === "") throw new Error("Shoot sessions need a safe name and processing-profile version.");
  assertFrozenPrompter(project.projectId, session.frozenPrompter);
  const next = structuredClone(project);
  next.sessions.push({ ...session, sources: [] });
  return next;
}

/** Hashes and probes a local file before adding one immutable source record. */
export async function registerMaster(
  project: ShootRegistrationProjectV1,
  sessionId: string,
  input: RegisterMasterInput,
): Promise<RegisterMasterResult> {
  const session = requireSession(project, sessionId);
  assertUuid(input.id, "source ID");
  const file = await stat(input.path);
  if (!file.isFile() || file.size < 1) throw new Error("A master must be a non-empty regular file.");
  const mediaHash = await hashFile(input.path);
  const duplicate = session.sources.find((source) => source.mediaHash === mediaHash);
  if (duplicate !== undefined) return { project, source: structuredClone(duplicate), duplicate: true };

  const inspection = inspect(await (input.probe ?? ffprobe)(input.path));
  const locator = locatorForRegistration(project, input.path, input.library);
  const safeDisplayName = safeName(basename(input.path));
  const source: ShootSource = {
    id: input.id,
    mediaHash,
    byteSize: file.size,
    safeDisplayName,
    ...(locator === undefined ? {} : { locator }),
    inspection,
    authorization: "authorized_local",
    status: "ready",
    relinkHistory: [],
  };
  const next = structuredClone(project);
  requireSession(next, sessionId).sources.push(source);
  return { project: next, source: structuredClone(source), duplicate: false };
}

/** Reads an authorized local root and appends only hash-verified relink evidence. */
export async function relinkFromLibrary(
  project: ShootRegistrationProjectV1,
  library: LibraryRoot,
  observedAt = new Date().toISOString(),
): Promise<{ project: ShootRegistrationProjectV1; relinked: string[]; unmatched: number }> {
  assertUuid(library.libraryId, "library ID");
  if (Number.isNaN(Date.parse(observedAt)) || !/T.*Z$/u.test(observedAt)) throw new Error("Relink evidence needs an ISO UTC observation time.");
  if (project.mediaLibrary.kind !== "project_local" || project.mediaLibrary.libraryId !== library.libraryId) throw new Error("Relink requires the configured project-local library.");
  const known = new Map<string, ShootSource>();
  for (const session of project.sessions) for (const source of session.sources) known.set(source.mediaHash, source);
  const next = structuredClone(project);
  const nextKnown = new Map<string, ShootSource>();
  for (const session of next.sessions) for (const source of session.sources) nextKnown.set(source.mediaHash, source);
  const relinked = new Set<string>();
  let unmatched = 0;
  for (const path of await filesIn(library.rootPath)) {
    const mediaHash = await hashFile(path);
    if (!known.has(mediaHash)) {
      unmatched += 1;
      continue;
    }
    const source = nextKnown.get(mediaHash)!;
    const locator = locatorFor(path, library);
    const alreadyKnown = [source.locator, ...source.relinkHistory.map(({ locator: item }) => item)]
      .some((item) => item?.libraryId === locator.libraryId && item.relativePath === locator.relativePath);
    if (!alreadyKnown) {
      source.relinkHistory.push({ locator, mediaHash, observedAt });
      relinked.add(source.id);
    }
  }
  return { project: next, relinked: [...relinked], unmatched };
}

/** Creates metadata only; it never reads, packages, or transfers master bytes. */
export function createHandoffInventory(
  project: ShootRegistrationProjectV1,
  sessionId: string,
): LocalSourceHandoffInventoryV1 {
  return {
    schemaVersion: "local-source-handoff-inventory/v1",
    projectId: project.projectId,
    sessionId,
    sources: structuredClone(requireSession(project, sessionId).sources),
  };
}

/** Resolves a master only for the exact project/source job; the returned path is local-only. */
export async function resolveMasterForJob(
  project: ShootRegistrationProjectV1,
  job: JobAccess,
  libraries: LibraryRoot[],
): Promise<{ sourceId: string; path: string; inspection: SourceInspection }> {
  if (job.projectId !== project.projectId) throw new Error("Job does not authorize this project.");
  const source = project.sessions.flatMap(({ sources }) => sources).find(({ id }) => id === job.sourceId);
  if (source === undefined) throw new Error("Job does not authorize this source.");
  if (project.mediaLibrary.kind !== "project_local") throw new Error("Project has no configured local library and source has no verified locator for job access.");
  const configuredLibraryId = project.mediaLibrary.libraryId;
  const locators = [...source.relinkHistory.map(({ locator }) => locator).reverse(), ...(source.locator === undefined ? [] : [source.locator])]
    .filter(({ libraryId }) => libraryId === configuredLibraryId);
  if (locators.length === 0) throw new Error("Source has no verified locator for job access.");
  for (const locator of locators) {
    const library = libraries.find(({ libraryId }) => libraryId === locator.libraryId);
    if (library === undefined) continue;
    const path = resolve(library.rootPath, locator.relativePath);
    try {
      if ((await stat(path)).isFile() && await hashFile(path) === source.mediaHash) return { sourceId: source.id, path, inspection: source.inspection };
    } catch { /* Try older verified locator without exposing a filesystem error. */ }
  }
  throw new Error("Source has no verified locator for job access.");
}

export async function ffprobe(path: string): Promise<ProbeOutput> {
  const { stdout } = await execFileAsync("ffprobe", ["-v", "error", "-show_format", "-show_streams", "-of", "json", path], { maxBuffer: 1024 * 1024 });
  return JSON.parse(stdout) as ProbeOutput;
}

function inspect(output: ProbeOutput): SourceInspection {
  const duration = Number(output.format?.duration);
  if (!output.format?.format_name || !Number.isFinite(duration) || duration <= 0) throw new Error("Probe did not return a supported format and positive duration.");
  const videoStreams = (output.streams ?? []).filter(({ codec_type }) => codec_type === "video").map((stream) => {
    const frameRate = stream.avg_frame_rate ?? stream.r_frame_rate;
    const { codec_name: codec, width, height } = stream;
    if (width === undefined || height === undefined) throw new Error("Probe did not return supported video stream facts.");
    if (!codec || !Number.isInteger(width) || !Number.isInteger(height) || width < 1 || height < 1 || !validRate(frameRate)) throw new Error("Probe did not return supported video stream facts.");
    return { codec, width, height, frameRate, timecode: stream.tags?.timecode ?? null, colorMetadata: { space: stream.color_space ?? null, transfer: stream.color_transfer ?? null, primaries: stream.color_primaries ?? null, range: stream.color_range ?? null } };
  });
  if (videoStreams.length === 0) throw new Error("Probe did not return supported video streams.");
  const audioStreams = (output.streams ?? []).filter(({ codec_type }) => codec_type === "audio").map((stream) => {
    const sampleRate = Number(stream.sample_rate);
    const { codec_name: codec, channels } = stream;
    if (channels === undefined) throw new Error("Probe did not return supported audio stream facts.");
    if (!codec || !Number.isInteger(channels) || channels < 1 || !Number.isInteger(sampleRate) || sampleRate < 1) throw new Error("Probe did not return supported audio stream facts.");
    return { codec, channels, layout: stream.channel_layout ?? null, sampleRate };
  });
  return { formatName: output.format.format_name, durationMs: Math.round(duration * 1000), videoStreams: videoStreams as SourceInspection["videoStreams"], audioStreams };
}

function locatorForRegistration(project: ShootRegistrationProjectV1, path: string, library: LibraryRoot | undefined): SourceLocator | undefined {
  if (project.mediaLibrary.kind === "unconfigured") {
    if (library !== undefined) throw new Error("An unconfigured project cannot publish a library locator.");
    return undefined;
  }
  if (library === undefined || library.libraryId !== project.mediaLibrary.libraryId) throw new Error("Registration requires the configured project-local library.");
  return locatorFor(path, library);
}

function locatorFor(path: string, library: LibraryRoot): SourceLocator {
  const relativePath = relative(resolve(library.rootPath), resolve(path));
  if (relativePath === "" || relativePath === ".." || relativePath.startsWith(`..${sep}`) || isAbsolute(relativePath)) throw new Error("Master is outside the authorized project-local library.");
  const portablePath = relativePath.split(sep).join("/");
  if ([...portablePath].length > 4096 || /[\\]/u.test(portablePath) || [...portablePath].some((character) => character.charCodeAt(0) < 32)) throw new Error("Master locator is not safe for a project record.");
  return { libraryId: library.libraryId, relativePath: portablePath };
}

async function hashFile(path: string): Promise<string> {
  const hash = createHash("sha256");
  const stream = createReadStream(path) as AsyncIterable<Buffer>;
  for await (const chunk of stream) hash.update(chunk);
  return `sha256:${hash.digest("hex")}`;
}

async function filesIn(root: string): Promise<string[]> {
  const files: string[] = [];
  async function visit(directory: string): Promise<void> {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const path = resolve(directory, entry.name);
      if (entry.isDirectory()) await visit(path);
      else if (entry.isFile()) files.push(path);
    }
  }
  await visit(resolve(root));
  return files;
}

function requireSession(project: ShootRegistrationProjectV1, sessionId: string): ShootSession {
  const session = project.sessions.find(({ id }) => id === sessionId);
  if (session === undefined) throw new Error("Shoot session is not registered.");
  return session;
}

function assertFrozenPrompter(projectId: string, frozen: PrompterExportReference): void {
  const document: DocumentReference = frozen.sourceDocument;
  if (!uuidPattern.test(document.documentId) || !uuidPattern.test(document.projectId) || !Number.isSafeInteger(document.liveHeadSequence) || document.liveHeadSequence < 0 || !hashPattern.test(document.contentHash) || document.projectId !== projectId || !hashPattern.test(frozen.prompterExportSha256) || !hashPattern.test(frozen.beatMapSha256)) throw new Error("Shoot sessions require one frozen prompter and beat-map identity for this project.");
}

function assertUuid(value: string, label: string): void {
  if (!uuidPattern.test(value)) throw new Error(`Invalid ${label}.`);
}

function safeName(name: string): string {
  if (name === "" || name === "." || name === ".." || [...name].length > 255 || /[\\/]/u.test(name) || [...name].some((character) => character.charCodeAt(0) < 32)) throw new Error("Master filename is not safe for a project record.");
  return name;
}

function validRate(rate: string | undefined): rate is string {
  if (rate === undefined || !/^[1-9][0-9]*\/[1-9][0-9]*$/u.test(rate)) return false;
  const [numerator, denominator] = rate.split("/").map(Number);
  return numerator !== undefined && denominator !== undefined && numerator > 0 && denominator > 0;
}
