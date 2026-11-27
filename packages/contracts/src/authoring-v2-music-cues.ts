import type { AuthoringDiagnosticV2 } from "./authoring-v2.js";
import { sameAuthoringJsonV2 } from "./authoring-v2-json.js";
import { isMusicCuePointCurrentV2, validateScriptDocumentV2 } from "./authoring-v2-validation.js";
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
