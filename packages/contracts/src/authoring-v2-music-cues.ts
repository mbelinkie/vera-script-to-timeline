import type { AuthoringDiagnosticV2 } from "./authoring-v2.js";
import { sameAuthoringJsonV2 } from "./authoring-v2-json.js";
import { isMusicCuePointCurrentV2, validateScriptDocumentV2, wordBoundaryOrderV2 } from "./authoring-v2-validation.js";
import { spokenTokensV2 } from "./authoring-v2-stage-directions.js";
import type { MusicCueTimingV2, ScriptDocumentV2 } from "./generated/contracts-v2.js";

export interface MusicCueEditV2 {
  cueId: string;
  timing?: MusicCueTimingV2;
  /** Null restores the default fade. Omit to keep the existing treatment. */
  fadeOutMs?: number | null;
}

export type MusicCueEditResultV2 =
  | { ok: true; document: ScriptDocumentV2; diagnostics: AuthoringDiagnosticV2[]; undoLabel: string }
  | { ok: false; document: ScriptDocumentV2; diagnostics: AuthoringDiagnosticV2[] };

/** Change one saved cue as a single undoable document edit. */
export function editMusicCueV2(
  document: ScriptDocumentV2,
  expectedRevision: number,
  edit: MusicCueEditV2,
): MusicCueEditResultV2 {
  const refuse = (code: string, message: string, jsonPath = "/rowAudioSpans"): MusicCueEditResultV2 =>
    ({ ok: false, document, diagnostics: [{ code, message, jsonPath, entityId: edit.cueId }] });
  if (!Number.isSafeInteger(expectedRevision) || expectedRevision < 0 ||
      expectedRevision === Number.MAX_SAFE_INTEGER || expectedRevision !== (document.rowEditRevision ?? 0)) {
    return refuse("ROW_REVISION_STALE", "The row document changed before this edit, or its revision cannot advance.");
  }
  const spans = document.rowAudioSpans ?? [];
  const index = spans.findIndex((span) => span.id === edit.cueId);
  const span = spans[index];
  if (!span) return refuse("MUSIC_CUE_MISSING", "Select an existing music cue.");
  const path = `/rowAudioSpans/${index}`;
  const settings = { ...span.settings };
  if (edit.fadeOutMs !== undefined) {
    if (edit.fadeOutMs === null) delete settings.fadeOutMs;
    else settings.fadeOutMs = edit.fadeOutMs;
    delete settings.fadeOutFrames;
  }
  const cue = { ...span, settings, ...(edit.timing !== undefined ? { timing: structuredClone(edit.timing) } : {}) };
  if (sameAuthoringJsonV2(cue, span)) return refuse("MUSIC_CUE_NO_CHANGE", "The music cue already has these settings.", path);
  const updated = { ...document, rowEditRevision: expectedRevision + 1,
    rowAudioSpans: spans.map((item, at) => at === index ? cue : item) };
  const validation = validateScriptDocumentV2(updated);
  if (!validation.valid) return { ok: false, document, diagnostics: validation.diagnostics };
  if (edit.timing !== undefined) {
    for (const endpoint of ["timelineIn", "timelineOut"] as const) {
      const point = edit.timing[endpoint];
      if (!point || point.kind === "frame") continue;
      const blockId = point.kind === "word" ? point.anchor.blockId : point.blockId;
      if (!isMusicCuePointCurrentV2(point, document.activeDraft.blocks.find((row) => row.id === blockId))) {
        return refuse("MUSIC_CUE_ANCHOR_INVALID", "Select a current spoken word or an active row edge.", `${path}/timing/${endpoint}`);
      }
    }
  }
  return { ok: true, document: updated, diagnostics: validation.diagnostics, undoLabel: "Edit music cue" };
}

/** A bracket gesture changes exactly one authored timeline pin. */
export type MusicCueEndpointV2 = Exclude<NonNullable<MusicCueTimingV2["timelineIn"]>, { kind: "frame" }>;
export type MoveMusicCueEndpointV2 = {
  kind: "move_music_cue_endpoint";
  cueId: string;
  endpoint: "timelineIn" | "timelineOut";
  point: MusicCueEndpointV2;
  /** Freeze the document revision when the gesture starts, not when it is queued. */
  expectedRevision: number;
};

export function moveMusicCueEndpointV2(
  document: ScriptDocumentV2, expectedRevision: number, command: MoveMusicCueEndpointV2,
): MusicCueEditResultV2 {
  const refuse = (code: string, message: string): MusicCueEditResultV2 => ({ ok: false, document,
    diagnostics: [{ code, message, jsonPath: "/rowAudioSpans", entityId: command.cueId }] });
  if (command.expectedRevision !== expectedRevision || expectedRevision !== (document.rowEditRevision ?? 0)) {
    return refuse("ROW_REVISION_STALE", "The script changed during the music bracket gesture. Choose the endpoint again.");
  }
  const span = document.rowAudioSpans?.find((item) => item.id === command.cueId);
  if (!span) return refuse("MUSIC_CUE_MISSING", "Select an existing music cue.");
  // A legacy row span implicitly starts at source zero. Promote only on an
  // explicit changed bracket; do not infer the length of the source.
  const timing: MusicCueTimingV2 = span.timing ?? { sourceInFrame: 0,
    timelineIn: { kind: "row_edge", blockId: span.startRowId, edge: "start" },
    timelineOut: { kind: "row_edge", blockId: span.endRowId, edge: "end" } };
  if (!timing[command.endpoint]) {
    return refuse("MUSIC_CUE_DERIVED_ENDPOINT", "This endpoint is derived from the other three pins. Change the pin selection in music timing first.");
  }
  if (sameAuthoringJsonV2(timing[command.endpoint], command.point)) {
    return refuse("MUSIC_CUE_NO_CHANGE", "The music cue already has this endpoint.");
  }
  const next = { ...timing, [command.endpoint]: command.point };
  const result = editMusicCueV2(document, expectedRevision, { cueId: command.cueId, timing: next });
  if (!result.ok) return result;
  // The authored order is knowable without fabricated word times. The compiler
  // remains responsible for frame geometry, source length and mixed frame pins.
  const rows = document.activeDraft.blocks.filter((row) => row.type === "visual_only" ||
    row.type === "narration" && row.state === "active" && row.plainDirection !== true && spokenTokensV2(row).length > 0);
  const order = (point: MusicCueTimingV2["timelineIn"]): [number, number] | undefined => {
    if (!point || point.kind === "frame") return undefined;
    const rowIndex = rows.findIndex((row) => row.id === (point.kind === "word" ? point.anchor.blockId : point.blockId));
    const row = rows[rowIndex];
    if (!row) return undefined;
    if (point.kind === "row_edge") return point.edge === "start" ? [rowIndex, 0] : [rowIndex + 1, 0];
    if (row.type !== "narration") return undefined;
    const boundary = wordBoundaryOrderV2(point.anchor, row);
    return boundary === null ? undefined : [rowIndex, boundary + 1];
  };
  const start = order(next.timelineIn), end = order(next.timelineOut);
  for (const point of [next.timelineIn, next.timelineOut]) {
    if (point && point.kind !== "frame" && !order(point)) {
      return refuse("MUSIC_CUE_ANCHOR_INVALID", "Choose a timed Draft word or row edge.");
    }
  }
  if (start && end && (start[0] > end[0] || start[0] === end[0] && start[1] >= end[1])) {
    return refuse("MUSIC_CUE_SPAN_REVERSED", "The music start must precede its end.");
  }
  return result;
}
