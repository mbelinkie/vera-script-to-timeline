import { describe, expect, it } from "vitest";
import {
  applyRowEditV2, createSortingTrialV2, deserializeAuthoringDocumentV2,
  resumeSortingTrialV2, serializeAuthoringDocumentV2, validateScriptDocumentV2,
  type RowEditCommandV2,
} from "../src/authoring-v2.js";
import type { NarrationBlockV2, ScriptDocumentV2, VisualOnlyBlockV2 } from "../src/generated/contracts-v2.js";
import { researchId as id, researchOccurrence, researchStashFixture } from "./issue-367-fixture.js";

const gap = (afterRowId: string | null = null, beforeRowId: string | null = null) => ({ sectionId: null, afterRowId, beforeRowId });
const ordinaryRows = (doc: ScriptDocumentV2) => [
  ...doc.activeDraft.blocks.filter((row) => row.type !== "section"),
  ...(doc.stash ?? []).flatMap((bundle) => bundle.rows),
];
const noteAt = (doc: ScriptDocumentV2, rowId: string): NarrationBlockV2 => {
  const row = ordinaryRows(doc).find((candidate) => candidate.id === rowId);
  if (row?.type !== "narration") throw new Error("Missing note");
  return row;
};
const independentClip = (doc: ScriptDocumentV2, rowId: string): VisualOnlyBlockV2 | undefined => {
  const row = ordinaryRows(doc).find((candidate) => candidate.id === rowId);
  return row?.type === "visual_only" ? row : undefined;
};
function apply(trial: ReturnType<typeof createSortingTrialV2>, command: RowEditCommandV2): void {
  const result = trial.apply(command);
  expect(result.ok, `${command.kind}: ${JSON.stringify(result.diagnostics)}`).toBe(true);
}
function saveAndAccept(trial: ReturnType<typeof createSortingTrialV2>, baseline: ScriptDocumentV2, mode: "all" | "edits_only" | "sorting_only" | "discard") {
  const pending = trial.preview();
  const resumed = resumeSortingTrialV2(trial.serialize());
  expect(resumed.phase).toBe("preview");
  expect(resumed.document).toEqual(pending);
  expect(resumed.returnToSorting()).toBe(true);
  const accepted = mode === "discard" ? resumed.discard(baseline) : resumed.accept(baseline, mode);
  expect(accepted.ok, `${mode}: ${JSON.stringify(accepted.diagnostics)}`).toBe(true);
  expect(validateScriptDocumentV2(accepted.document).valid, `${mode} invalid`).toBe(true);
  const reloaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(accepted.document));
  expect(reloaded.ok).toBe(true);
  if (reloaded.ok) expect(reloaded.document).toEqual(accepted.document);
  return accepted.document;
}

describe("issue 367 attached footage in Sorting", () => {
  it.each(["all", "edits_only", "sorting_only", "discard"] as const)("composes %s after trim plus parent-only placement, preserving descendants and mirrored source", (mode) => {
    const { doc, note, clip } = researchStashFixture();
    const child = researchOccurrence(730300);
    const created = applyRowEditV2(doc, 0, {
      kind: "create_stash_clip", row: child, bundleId: id(740300), sectionId: null, parentRowId: note.id, afterRowId: null,
    });
    expect(created.ok, JSON.stringify(created.diagnostics)).toBe(true);
    const baseline = created.document;
    const trial = createSortingTrialV2(baseline);
    apply(trial, { kind: "trim_research_clip", clipRowId: clip.id, edge: "in", frame: 30 });
    apply(trial, { kind: "place_stash_rows", rowIds: [note.id], destination: gap(), includeDescendants: false });
    expect(trial.movedRowIds).toContain(note.id);
    expect(trial.movedRowIds).not.toContain(child.id);
    const result = saveAndAccept(trial, baseline, mode);
    const owner = noteAt(result, note.id);
    expect(owner.attachedFootage?.clip.id).toBe(clip.id);
    expect(owner.attachedFootage?.clip.visualOnlyTiming.selectedSourceRange).toEqual({
      startFrame: mode === "all" || mode === "edits_only" ? 30 : 24,
      durationFrames: mode === "all" || mode === "edits_only" ? 30 : 36,
    });
    expect(independentClip(result, clip.id)).toBeUndefined();
    const positioned = result.stashOutline?.find((entry) => entry.rowId === child.id);
    expect(positioned?.parentRowId).toBe(mode === "all" || mode === "sorting_only" ? null : note.id);
    expect(result.activeDraft.blocks.some((row) => row.id === note.id)).toBe(mode === "all" || mode === "sorting_only");
    if (mode === "sorting_only") {
      const returned = applyRowEditV2(result, result.rowEditRevision ?? 0, { kind: "stash_rows", rowIds: [note.id], bundleId: id(740400) });
      expect(returned.ok, JSON.stringify(returned.diagnostics)).toBe(true);
      expect(noteAt(returned.document, note.id).attachedFootage?.clip).toEqual(clip);
    }
  });

  it.each(["all", "edits_only", "sorting_only", "discard"] as const)("composes %s when independently placing and trimming the original attached clip", (mode) => {
    const { doc: baseline, note, clip } = researchStashFixture();
    const trial = createSortingTrialV2(baseline);
    apply(trial, { kind: "place_attached_footage", noteRowId: note.id, destination: gap() });
    expect(trial.movedRowIds).toContain(clip.id);
    apply(trial, { kind: "trim_research_clip", clipRowId: clip.id, edge: "out", frame: 48 });
    const accepted = saveAndAccept(trial, baseline, mode);
    const owner = noteAt(accepted, note.id);
    const separate = independentClip(accepted, clip.id);
    if (mode === "all" || mode === "sorting_only") {
      expect(owner.attachedFootage).toBeUndefined();
      expect(separate?.stashOrigin?.originalAttachedNoteRowId).toBe(note.id);
    } else {
      expect(owner.attachedFootage?.clip.id).toBe(clip.id);
      expect(separate).toBeUndefined();
    }
    const selected = separate ?? owner.attachedFootage?.clip;
    expect(selected?.visualOnlyTiming.selectedSourceRange).toEqual({
      startFrame: 24, durationFrames: mode === "all" || mode === "edits_only" ? 24 : 36,
    });
    if (mode === "sorting_only") {
      const returned = applyRowEditV2(accepted, accepted.rowEditRevision ?? 0, {
        kind: "stash_rows", rowIds: [clip.id], bundleId: id(740500),
      });
      expect(returned.ok, JSON.stringify(returned.diagnostics)).toBe(true);
      expect(noteAt(returned.document, note.id).attachedFootage?.clip).toEqual(clip);
    }
  });

  it("replays Undo of independent placement and trims without a detached ghost", () => {
    const { doc, note, clip } = researchStashFixture();
    const trial = createSortingTrialV2(doc);
    apply(trial, { kind: "place_attached_footage", noteRowId: note.id, destination: gap() });
    const afterPlace = trial.document;
    apply(trial, { kind: "trim_research_clip", clipRowId: clip.id, edge: "in", frame: 30 });
    const resumed = resumeSortingTrialV2(trial.serialize());
    expect(resumed.undo().ok).toBe(true);
    expect({ ...resumed.document, rowEditRevision: 0 }).toEqual({ ...afterPlace, rowEditRevision: 0 });
    expect(resumed.undo().ok).toBe(true);
    expect({ ...resumed.document, rowEditRevision: 0 }).toEqual({ ...doc, rowEditRevision: 0 });
    expect(resumed.accept(doc)).toMatchObject({ ok: true, changed: false });
  });

  it.each(["attach", "detach", "replace", "cleanup"] as const)("separates authored %s ownership changes from Sorting layout", (operation) => {
    const { doc: fixture, note, clip } = researchStashFixture();
    let baseline = fixture;
    let incoming: VisualOnlyBlockV2 | undefined;
    if (operation === "attach") {
      const detached = applyRowEditV2(baseline, 0, { kind: "detach_stash_footage", noteRowId: note.id, bundleId: id(741001) });
      expect(detached.ok).toBe(true);
      baseline = detached.document;
    } else if (operation === "replace") {
      incoming = researchOccurrence(730400);
      const created = applyRowEditV2(baseline, 0, { kind: "create_stash_clip", row: incoming, bundleId: id(741002), sectionId: null, parentRowId: note.id, afterRowId: null });
      expect(created.ok, JSON.stringify(created.diagnostics)).toBe(true);
      baseline = created.document;
    } else if (operation === "cleanup") {
      baseline = structuredClone(baseline);
      const blank = noteAt(baseline, note.id);
      blank.text = "";
      blank.tokens = [];
    }
    const trial = createSortingTrialV2(baseline);
    if (operation === "attach") apply(trial, { kind: "attach_stash_footage", noteRowId: note.id, clipRowId: clip.id });
    if (operation === "detach") apply(trial, { kind: "detach_stash_footage", noteRowId: note.id, bundleId: id(741003) });
    if (operation === "replace") apply(trial, { kind: "replace_stash_footage", noteRowId: note.id, clipRowId: incoming!.id, releasedBundleId: id(741004) });
    if (operation === "cleanup") apply(trial, { kind: "cleanup_blank_stash_note", noteRowId: note.id, clipBundleId: id(741005) });
    for (const mode of ["all", "edits_only", "sorting_only", "discard"] as const) {
      const accepted = saveAndAccept(resumeSortingTrialV2(trial.serialize()), baseline, mode);
      const changed = mode === "all" || mode === "edits_only";
      const owner = operation === "cleanup" && changed ? undefined : noteAt(accepted, note.id);
      expect(owner?.attachedFootage?.clip.id).toBe(
        operation === "attach" ? changed ? clip.id : undefined :
          operation === "detach" || operation === "cleanup" ? changed ? undefined : clip.id :
            changed ? incoming!.id : clip.id,
      );
      const free = operation === "replace" ? changed ? clip.id : incoming!.id : clip.id;
      expect(!!independentClip(accepted, free)).toBe(
        operation === "replace" ? true : operation === "attach" ? !changed : changed,
      );
      if (mode === "discard") expect(accepted).toEqual(baseline);
    }
  });

  it("preserves explicit ownership when grouping an ordinary descendant after separating footage", () => {
    const { doc, note, clip, anchor } = researchStashFixture();
    const child = researchOccurrence(730500);
    const created = applyRowEditV2(doc, 0, { kind: "create_stash_clip", row: child, bundleId: id(741100), sectionId: null, parentRowId: note.id, afterRowId: null });
    expect(created.ok).toBe(true);
    const baseline = created.document;
    const trial = createSortingTrialV2(baseline);
    apply(trial, { kind: "place_attached_footage", noteRowId: note.id, destination: gap() });
    apply(trial, { kind: "trim_research_clip", clipRowId: clip.id, edge: "in", frame: 36 });
    const nextOutline = trial.document.stashOutline!.map((entry) => entry.rowId === child.id ? { ...entry, parentRowId: null } : entry);
    // The child is now a root after its previous parent, but is never implicitly attached.
    apply(trial, { kind: "set_stash_outline", entries: nextOutline });
    for (const mode of ["all", "edits_only", "sorting_only", "discard"] as const) {
      const accepted = saveAndAccept(resumeSortingTrialV2(trial.serialize()), baseline, mode);
      expect(accepted.stashOutline?.find((entry) => entry.rowId === child.id)?.parentRowId).toBe(mode === "all" || mode === "sorting_only" ? null : note.id);
      expect(noteAt(accepted, note.id).attachedFootage?.clip.id).toBe(mode === "all" || mode === "sorting_only" ? undefined : clip.id);
      expect(!!independentClip(accepted, clip.id)).toBe(mode === "all" || mode === "sorting_only");
      expect(accepted.stashOutline?.find((entry) => entry.rowId === anchor.id)?.parentRowId).toBeNull();
    }
  });

  it("refuses ambiguous selective replacement followed by independent placement without partial acceptance", () => {
    const { doc, note, clip } = researchStashFixture();
    const incoming = researchOccurrence(730600);
    const created = applyRowEditV2(doc, 0, { kind: "create_stash_clip", row: incoming, bundleId: id(741200), sectionId: null, parentRowId: note.id, afterRowId: null });
    expect(created.ok).toBe(true);
    const baseline = created.document;
    const trial = createSortingTrialV2(baseline);
    apply(trial, { kind: "replace_stash_footage", noteRowId: note.id, clipRowId: incoming.id, releasedBundleId: id(741201) });
    apply(trial, { kind: "place_attached_footage", noteRowId: note.id, destination: gap() });
    const pending = trial.document;
    const serialized = trial.serialize();
    const unsupported = trial.accept(baseline, "edits_only");
    expect(unsupported.ok).toBe(false);
    expect(unsupported.changed).toBe(false);
    expect(unsupported.document).toEqual(baseline);
    expect(trial.document).toEqual(pending);
    expect(trial.serialize()).toBe(serialized);
    const all = trial.accept(baseline, "all");
    expect(all.ok).toBe(true);
    expect(noteAt(all.document, note.id).attachedFootage).toBeUndefined();
    expect(independentClip(all.document, incoming.id)).toBeDefined();
    expect(independentClip(all.document, clip.id)).toBeDefined();
    expect(validateScriptDocumentV2(all.document).valid).toBe(true);
  });

  it("rejects malformed attachment replay and key-smuggling without changing a pending Sorting trial", () => {
    const { doc, note, clip } = researchStashFixture();
    const trial = createSortingTrialV2(doc);
    const before = trial.document;
    const invalid = [
      { kind: "trim_research_clip", clipRowId: clip.id, edge: "clear_out", frame: 50 },
      { kind: "trim_research_clip", clipRowId: clip.id, edge: "out", frame: -1 },
      { kind: "place_attached_footage", noteRowId: note.id, destination: gap(), extra: true },
      { kind: "place_stash_rows", rowIds: [note.id], destination: gap(), includeDescendants: "false" },
      { kind: "replace_stash_footage", noteRowId: note.id, clipRowId: clip.id },
    ];
    for (const action of invalid) {
      const refused = trial.apply(action as RowEditCommandV2);
      expect(refused.diagnostics[0]?.code).toBe("SORTING_COMMAND_INVALID");
      expect(trial.document).toEqual(before);
    }
    apply(trial, { kind: "place_attached_footage", noteRowId: note.id, destination: gap() });
    const tampered = JSON.parse(trial.serialize()) as { actions: Array<Record<string, unknown>> };
    tampered.actions[0]!.extra = true;
    expect(() => resumeSortingTrialV2(JSON.stringify(tampered))).toThrow(/Invalid saved Sorting operation/);
    const invalidRange = JSON.parse(trial.serialize()) as { actions: Array<Record<string, unknown>> };
    invalidRange.actions.push({ kind: "trim_research_clip", clipRowId: clip.id, edge: "in", frame: 108 });
    expect(() => resumeSortingTrialV2(JSON.stringify(invalidRange))).toThrow(/Invalid saved Sorting operation/);
    expect(trial.document).toEqual(resumeSortingTrialV2(trial.serialize()).document);
  });

  it.each([false, true] as const)("preserves %s-returned separate footage through all outcomes", (edited) => {
    const { doc: baseline, note, clip } = researchStashFixture();
    const trial = createSortingTrialV2(baseline);
    apply(trial, { kind: "place_attached_footage", noteRowId: note.id, destination: gap() });
    if (edited) apply(trial, { kind: "trim_research_clip", clipRowId: clip.id, edge: "out", frame: 48 });
    apply(trial, { kind: "stash_rows", rowIds: [clip.id], bundleId: id(741350) });
    for (const mode of ["all", "edits_only", "sorting_only", "discard"] as const) {
      const accepted = saveAndAccept(resumeSortingTrialV2(trial.serialize()), baseline, mode);
      const originalOwner = noteAt(accepted, note.id).attachedFootage?.clip;
      const separate = independentClip(accepted, clip.id);
      if (edited && (mode === "all" || mode === "sorting_only")) {
        expect(originalOwner).toBeUndefined();
        expect(separate).toBeDefined();
      } else {
        expect(originalOwner).toBeDefined();
        expect(separate).toBeUndefined();
      }
      expect((originalOwner ?? separate)?.visualOnlyTiming.selectedSourceRange).toEqual({
        startFrame: 24, durationFrames: edited && (mode === "all" || mode === "edits_only") ? 24 : 36,
      });
    }
  });

  it("keeps a returned clip ordinary when the original note slot is occupied, and refuses unsafe edits-only composition", () => {
    const { doc, note, clip } = researchStashFixture();
    const alternative = researchOccurrence(730700);
    const created = applyRowEditV2(doc, 0, { kind: "create_stash_clip", row: alternative, bundleId: id(741400), sectionId: null, parentRowId: note.id, afterRowId: null });
    expect(created.ok).toBe(true);
    const baseline = created.document;
    const trial = createSortingTrialV2(baseline);
    apply(trial, { kind: "place_attached_footage", noteRowId: note.id, destination: gap() });
    apply(trial, { kind: "attach_stash_footage", noteRowId: note.id, clipRowId: alternative.id });
    apply(trial, { kind: "stash_rows", rowIds: [clip.id], bundleId: id(741401) });
    expect(noteAt(trial.document, note.id).attachedFootage?.clip.id).toBe(alternative.id);
    expect(independentClip(trial.document, clip.id)).toBeDefined();
    expect(trial.document.stashOutline?.find((entry) => entry.rowId === clip.id)?.parentRowId).toBe(note.id);
    const snapshot = trial.serialize();
    const rejected = resumeSortingTrialV2(snapshot).accept(baseline, "edits_only");
    expect(rejected.ok).toBe(false);
    expect(rejected.document).toEqual(baseline);
    const all = saveAndAccept(resumeSortingTrialV2(snapshot), baseline, "all");
    expect(noteAt(all, note.id).attachedFootage?.clip.id).toBe(alternative.id);
    expect(independentClip(all, clip.id)).toBeDefined();
    const sorting = resumeSortingTrialV2(snapshot).accept(baseline, "sorting_only");
    if (sorting.ok) {
      expect(validateScriptDocumentV2(sorting.document).valid).toBe(true);
      expect(independentClip(sorting.document, clip.id)).toBeDefined();
      expect(noteAt(sorting.document, note.id).attachedFootage).toBeUndefined();
    } else expect(sorting.changed).toBe(false); // Fail closed rather than creating two clip owners.
  });

  it("never invents a frame map while sorting an unresolved Research attachment", () => {
    const { doc: baseline, note, clip } = researchStashFixture(false);
    const trial = createSortingTrialV2(baseline);
    apply(trial, { kind: "place_stash_rows", rowIds: [note.id], destination: gap(), includeDescendants: false });
    for (const mode of ["all", "edits_only", "sorting_only", "discard"] as const) {
      const accepted = saveAndAccept(resumeSortingTrialV2(trial.serialize()), baseline, mode);
      const owned = noteAt(accepted, note.id).attachedFootage?.clip;
      expect(owned?.id).toBe(clip.id);
      expect(owned?.payload.pictureKind).toBe("unresolved_visual");
      expect(owned?.frameBinding).toBeUndefined();
      expect(owned?.visualOnlyTiming.selectedSourceRange).toBeUndefined();
    }
  });
});
