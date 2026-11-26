import { execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import { join } from "node:path";
import { isDeepStrictEqual } from "node:util";

import { findPrimaryResearchOwnerV2, snapshotResearchCandidateV2, validateScriptDocumentV2 } from "@vera/contracts/authoring-v2";
import { ResearchReadError } from "@vera/contracts/research-clip-client";
import type { ResearchFrameBindingV2, ScriptDocumentV2, SourceFrameMapV1 } from "@vera/contracts/v2";

import { ProjectAuthError } from "@vera/project-authorization";

import type { AuthoringResearchAccess } from "./authoring.js";

export interface ResearchMediaConfig {
  projectId: string;
  mediaRoot: string;
  exportRoot?: string;
  python: string;
  cwd: string;
}

const uuid = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/u;
const digest = /^sha256:[a-f0-9]{64}$/u;
const maximumPreviewBytes = 64 * 1024 * 1024;

const response = (status: number, body: unknown) =>
  Response.json(body, { status, headers: { "Cache-Control": "no-store" } });

function worker(config: ResearchMediaConfig, command: object) {
  return new Promise<Buffer>((resolve, reject) => {
    const child = execFile(config.python,
      ["-m", "vera_timeline_agent.research_authoring_media", config.mediaRoot,
        ...(config.exportRoot ? [config.exportRoot] : [])],
      { cwd: config.cwd, env: { ...process.env, PYTHONPATH: join(config.cwd, "python") }, timeout: 120_000, maxBuffer: maximumPreviewBytes, encoding: "buffer" },
      (error, stdout) => error ? reject(error) : resolve(stdout));
    child.stdin?.on("error", reject);
    child.stdin?.end(JSON.stringify(command));
  });
}

function target(document: ScriptDocumentV2, selector: string, id: string) {
  if (selector === "payloadId") {
    const owner = findPrimaryResearchOwnerV2(document, id);
    if (!owner?.payload.researchClip || !document.activeDraft.blocks.includes(owner.row)) return undefined;
    const { row, item, payload } = owner;
    const pin = payload.researchClip;
    if (!pin) return undefined;
    const sequence = row.primaryVisualSequence;
    return {
      rowId: row.id, payloadId: payload.payloadId, pin,
      binding: payload.frameBinding, range: payload.selectedSourceRange,
      attach(binding: ResearchFrameBindingV2) {
        if (!sequence || ![row.version, item.version, sequence.version].every(version =>
          Number.isSafeInteger(version + 1))) return false;
        payload.frameBinding = binding;
        payload.pictureKind = "clip";
        payload.source = { kind: "media_reference", mediaReferenceId: binding.mediaReferenceId };
        payload.selectedSourceRange = { startFrame: 0, durationFrames: binding.loggedEndFrame };
        payload.sourceUsage = { sourceInFrame: 0 };
        item.version++;
        sequence.version++;
        row.version++;
        return true;
      },
    };
  }
  const row = document.activeDraft.blocks.find(block => block.id === id);
  if (row?.type !== "visual_only" || !row.researchClip) return undefined;
  return {
    rowId: row.id, payloadId: row.payload.payloadId, pin: row.researchClip,
    binding: row.frameBinding, range: row.visualOnlyTiming.selectedSourceRange,
    attach(binding: ResearchFrameBindingV2) {
      if (!Number.isSafeInteger(row.version + 1)) return false;
      row.frameBinding = binding;
      row.payload.pictureKind = "clip";
      row.payload.source = { kind: "media_reference", mediaReferenceId: binding.mediaReferenceId };
      row.visualOnlyTiming.selectedSourceRange = { startFrame: 0, durationFrames: binding.loggedEndFrame };
      row.version++;
      return true;
    },
  };
}

type SavedHead = { revision: number; digest: string; document: ScriptDocumentV2 };

export async function handleResearchMedia(
  request: Request, config: ResearchMediaConfig, research: AuthoringResearchAccess,
  projects: (request: Request) => Promise<Response>, authorization: string,
) {
  const input: unknown = await request.json().catch(() => null);
  if (!input || typeof input !== "object" || Array.isArray(input)) return response(400, { error: "invalid_request" });
  const value = input as Record<string, unknown>;
  const selector = Object.hasOwn(value, "payloadId") ? "payloadId" : "clipRowId";
  const id = value[selector];
  const action = value.action;
  const preview = action === "saved" || action === "logged" || action === "frame";
  const keys = ["timelineProjectId", selector, "expectedRevision", "expectedDigest", "expectedRowEditRevision", "action",
    ...(action === "frame" ? ["frame"] : [])];
  if (Object.keys(value).length !== keys.length || !keys.every(key => Object.hasOwn(value, key)) ||
      typeof id !== "string" || !uuid.test(id) ||
      typeof value.timelineProjectId !== "string" || !uuid.test(value.timelineProjectId) ||
      !Number.isSafeInteger(value.expectedRevision) || Number(value.expectedRevision) < 0 ||
      !Number.isSafeInteger(value.expectedRowEditRevision) || Number(value.expectedRowEditRevision) < 0 ||
      typeof value.expectedDigest !== "string" || !digest.test(value.expectedDigest) ||
      (action !== "bind" && action !== "describe" && !preview) ||
      (action === "frame" && !Number.isSafeInteger(value.frame))) {
    return response(400, { error: "invalid_request" });
  }
  if (value.timelineProjectId !== config.projectId) return response(404, { error: "research_media_unconfigured" });
  const url = new URL(`/v1/projects/${config.projectId}/document`, request.url);
  const read = () => projects(new Request(url, { headers: { authorization } }));
  const matches = (head: SavedHead) => head.revision === value.expectedRevision && head.digest === value.expectedDigest &&
    (head.document.rowEditRevision ?? 0) === value.expectedRowEditRevision;
  const stale = () => response(409, { error: "research_media_stale" });
  const authorizeResearch = async (owner: NonNullable<ReturnType<typeof target>>) => {
    const current = await research.catalog.clip(owner.pin.researchProjectId, owner.pin.clipId);
    // The cut package verifies the logged artifact identity. The catalog independently
    // authorizes the source and establishes an exact match for the current revision.
    return isDeepStrictEqual(snapshotResearchCandidateV2(current), owner.pin);
  };
  await research.authorizeTimelineProject(config.projectId, action === "bind" ? "edit_document" : "view_document");
  const saved = await read();
  if (!saved.ok) return saved;
  const head = await saved.json() as SavedHead;
  if (head.document.projectId !== config.projectId || !matches(head)) return stale();
  const owner = target(head.document, selector, id);
  if (!owner) return response(404, { error: "research_occurrence_unavailable" });
  if (!(await authorizeResearch(owner))) return response(409, { error: "research_pin_changed" });
  const descriptorInput = { pin: owner.pin, rowId: owner.rowId, payloadId: owner.payloadId };
  try {
    const verified = JSON.parse((await worker(config, { action: "resolve", materialize: action === "bind" && !owner.binding, ...descriptorInput })).toString()) as {
      binding: ResearchFrameBindingV2; sourceFrameMap: SourceFrameMapV1;
    };
    if (owner.binding && !isDeepStrictEqual(owner.binding, verified.binding)) {
      return response(409, { error: "research_media_changed" });
    }
    if (preview && (!owner.binding || !owner.range)) return response(409, { error: "research_media_unbound" });
    const startFrame = action === "frame" ? Number(value.frame) : action === "saved" ? owner.range!.startFrame : 0;
    const endFrame = action === "frame" ? startFrame + 1 : action === "saved" ?
      startFrame + owner.range!.durationFrames : verified.binding.loggedEndFrame;
    if (startFrame < 0 || endFrame > verified.binding.loggedEndFrame || endFrame <= startFrame) {
      return response(422, { error: "research_media_range_invalid" });
    }
    const bytes = preview ? await worker(config, {
      action: action === "frame" ? "frame" : "preview", ...descriptorInput, binding: verified.binding, startFrame, endFrame,
    }) : undefined;
    if (!(await authorizeResearch(owner))) return response(409, { error: "research_pin_changed" });
    const latest = await read();
    if (!latest.ok) return latest;
    if (!matches(await latest.json() as SavedHead)) return stale();
    if (bytes) return new Response(new Uint8Array(bytes), { headers: {
      "Content-Type": action === "frame" ? "image/png" : "video/mp4", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    } });
    if (action === "describe" || owner.binding) {
      return response(200, { ...verified, bound: !!owner.binding, savedRange: owner.range ?? null,
        transcriptClock: null, revision: head.revision, digest: head.digest });
    }
    const revision = (head.document.rowEditRevision ?? 0) + 1;
    if (!Number.isSafeInteger(revision) || !owner.attach(verified.binding)) return stale();
    head.document.rowEditRevision = revision;
    if (!validateScriptDocumentV2(head.document).valid) return response(409, { error: "research_binding_invalid" });
    return await projects(new Request(url, {
      method: "PUT", headers: { authorization, "Content-Type": "application/json" },
      body: JSON.stringify({ expectedRevision: head.revision, clientMutationId: randomUUID(), document: head.document }),
    }));
  } catch (error) {
    if (error instanceof ResearchReadError || error instanceof ProjectAuthError) throw error;
    if (typeof error === "object" && error && "code" in error && error.code === 3) {
      return response(404, { error: "research_media_missing" });
    }
    return response(422, { error: "research_media_unavailable" });
  }
}
