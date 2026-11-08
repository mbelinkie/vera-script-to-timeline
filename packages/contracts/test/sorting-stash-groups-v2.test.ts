import { describe, expect, it } from "vitest";
import {
  applyCommentOperationV2, applyRowEditV2, beginStashGroupMemberStageV2,
  createCommentStateV2, createSortingTrialV2, deserializeAuthoringDocumentV2,
  resumeSortingTrialV2, saveStashGroupStageCommandV2, serializeAuthoringDocumentV2,
  stageStashGroupMembersV2, validateScriptDocumentV2,
  type RowEditCommandV2,
} from "../src/authoring-v2.js";
import type { ScriptDocumentV2 } from "../src/generated/contracts-v2.js";
import { researchId as id, researchNote, researchStashFixture } from "./issue-367-fixture.js";

const gap = { sectionId: null, afterRowId: null, beforeRowId: null };
const savedIds = (document: ScriptDocumentV2) => document.stashOutline?.map((entry) => entry.rowId) ?? [];
const groupIds = (document: ScriptDocumentV2) => document.stashGroups?.[0]?.rowIds ?? [];
const rowById = (document: ScriptDocumentV2, idValue: string) =>
  [...document.activeDraft.blocks, ...(document.stash ?? []).flatMap((bundle) => bundle.rows)].find((row) => row.id === idValue);

function applied(document: ScriptDocumentV2, command: RowEditCommandV2): ScriptDocumentV2 {
  const result = applyRowEditV2(document, document.rowEditRevision ?? 0, command);
  expect(result.ok, JSON.stringify(result.diagnostics)).toBe(true);
  return result.document;
}

function grouped(withAttachment = true) {
  const { doc, anchor, note, clip } = researchStashFixture();
  if (!withAttachment) delete note.attachedFootage;
  const groupId = id(991000);
  const baseline = applied(doc, { kind: "group_stash_rows", groupId, rowIds: [anchor.id, note.id] });
  return { baseline, anchor, note, clip, groupId };
}

function trialApply(trial: ReturnType<typeof createSortingTrialV2>, command: RowEditCommandV2) {
  const result = trial.apply(command);
  expect(result.ok, `${command.kind} ${JSON.stringify(result.diagnostics)}`).toBe(true);
}

function settle(trial: ReturnType<typeof createSortingTrialV2>, baseline: ScriptDocumentV2, outcome: "all" | "edits_only" | "sorting_only" | "discard") {
  const pending = trial.preview();
  const json = trial.serialize();
  const resumed = resumeSortingTrialV2(json);
  expect(resumed.phase).toBe("preview");
  expect(resumed.document).toEqual(pending);
  expect(resumed.returnToSorting()).toBe(true);
  const result = outcome === "discard" ? resumed.discard(baseline) : resumed.accept(baseline, outcome);
  expect(result.ok, `${outcome} ${JSON.stringify(result.diagnostics)}`).toBe(true);
  expect(validateScriptDocumentV2(result.document).valid, JSON.stringify(validateScriptDocumentV2(result.document).diagnostics)).toBe(true);
  const reloaded = deserializeAuthoringDocumentV2(serializeAuthoringDocumentV2(result.document));
  expect(reloaded.ok).toBe(true);
  if (reloaded.ok) expect(reloaded.document).toEqual(result.document);
  return result.document;
}

describe("Sorting — atomic Stash groups (issue 366 phase 4)", () => {
  it.each(["all", "edits_only", "sorting_only", "discard"] as const)("composes %s on compact group formation, preserving embedded footage", (mode) => {
    const { doc, anchor, note, clip } = researchStashFixture();
    const trial = createSortingTrialV2(doc);
    trialApply(trial, { kind: "group_stash_rows", groupId: id(991100), rowIds: [anchor.id, note.id] });
    expect(trial.document.stashGroups?.[0]?.rowIds).toEqual([anchor.id, note.id]);
    expect(trial.undoDepth).toBe(1);
    const output = settle(trial, doc, mode);
    const groupedOutcome = mode === "all" || mode === "sorting_only";
    expect(groupIds(output)).toEqual(groupedOutcome ? [anchor.id, note.id] : []);
    expect(output.stashOutline?.map((entry) => entry.kind)).toEqual(groupedOutcome ? ["row", "row"] : ["note", "note"]);
    expect((rowById(output, note.id) as typeof note).attachedFootage?.clip).toEqual(clip);
    expect(savedIds(output)).toEqual([anchor.id, note.id]);
    const undone = resumeSortingTrialV2(trial.serialize());
    expect(undone.returnToSorting()).toBe(true);
    expect(undone.undo().ok).toBe(true);
    expect(undone.document.stashGroups).toBeUndefined();
  });

  it.each(["all", "edits_only", "sorting_only", "discard"] as const)("composes %s for group from Draft without a phantom saved group", (mode) => {
    const { doc, anchor, note } = researchStashFixture();
    delete note.attachedFootage;
    doc.stash = [];
    delete doc.stashOutline;
    doc.activeDraft.blocks = [anchor, note];
    const trial = createSortingTrialV2(doc);
    trialApply(trial, { kind: "stash_group_rows", groupId: id(991201), bundleId: id(991202),
      rowIds: [anchor.id, note.id], sectionId: null, parentRowId: null, afterRowId: null });
    expect(trial.movedRowIds).toEqual([anchor.id, note.id]);
    const output = settle(trial, doc, mode);
    expect(groupIds(output)).toEqual(mode === "all" || mode === "sorting_only" ? [anchor.id, note.id] : []);
    expect(output.activeDraft.blocks.map((row) => row.id)).toEqual(mode === "all" || mode === "sorting_only" ? [] : [anchor.id, note.id]);
  });

  it.each(["all", "edits_only", "sorting_only", "discard"] as const)("composes %s for a moved group under a compact note", (mode) => {
    const { baseline: original, anchor, note, groupId } = grouped();
    const baseline = structuredClone(original);
    const parent = researchNote(991300);
    const sectionId = id(991350);
    baseline.stash!.push({ id: id(991390), rows: [parent], supportingItems: [] });
    baseline.stashSections = [{ id: sectionId, title: "New section", rowIds: [] }];
    baseline.stashOutline!.push({ rowId: parent.id, kind: "note", sectionId, parentRowId: null });
    const trial = createSortingTrialV2(baseline);
    trialApply(trial, { kind: "move_stash_group", groupId, sectionId, parentRowId: parent.id, afterRowId: null });
    expect(trial.movedRowIds).toEqual([anchor.id, note.id]);
    const output = settle(trial, baseline, mode);
    expect(groupIds(output)).toEqual([anchor.id, note.id]);
    const parentFor = output.stashOutline!.find((entry) => entry.rowId === anchor.id)!;
    expect([parentFor.sectionId, parentFor.parentRowId]).toEqual(mode === "all" || mode === "sorting_only" ? [sectionId, parent.id] : [null, null]);
  });

  it.each(["ungroup_stash_group", "place_stash_group"] as const)("separates %s organization from authored content in four outcomes", (kind) => {
    const { baseline, anchor, note, groupId } = grouped();
    const trial = createSortingTrialV2(baseline);
    trialApply(trial, kind === "place_stash_group" ? { kind, groupId, destination: gap } : { kind, groupId });
    for (const outcome of ["all", "edits_only", "sorting_only", "discard"] as const) {
      const output = settle(resumeSortingTrialV2(trial.serialize()), baseline, outcome);
      expect(groupIds(output)).toEqual(outcome === "edits_only" || outcome === "discard" ? [anchor.id, note.id] : []);
      expect(output.activeDraft.blocks.map((row) => row.id)).toEqual(kind === "place_stash_group" && (outcome === "all" || outcome === "sorting_only") ? [anchor.id, note.id] : []);
      if (kind === "place_stash_group" && outcome === "sorting_only") {
        const row = rowById(output, note.id);
        expect(row?.type).toBe("narration");
        if (row?.type === "narration") expect(row.stashOrigin?.returnEligible).toBe(true);
      }
    }
  });

  it.each(["all", "edits_only", "sorting_only", "discard"] as const)("composes %s for atomic deletion as an edit", (mode) => {
    const { baseline, anchor, note, groupId } = grouped(false);
    const trial = createSortingTrialV2(baseline);
    trialApply(trial, { kind: "delete_stash_group", groupId });
    const output = settle(trial, baseline, mode);
    expect(savedIds(output)).toEqual(mode === "all" || mode === "edits_only" ? [] : [anchor.id, note.id]);
    expect(groupIds(output)).toEqual(mode === "sorting_only" || mode === "discard" ? [anchor.id, note.id] : []);
  });

  it.each([0, 1] as const)("normalizes Save with %s surviving members without losing the sorting-only baseline group", (count) => {
    const { baseline, anchor, note, groupId } = grouped(false);
    const trial = createSortingTrialV2(baseline);
    const stage = beginStashGroupMemberStageV2(trial.document, groupId)!;
    trialApply(trial, saveStashGroupStageCommandV2(stageStashGroupMembersV2(stage, stage.members.slice(0, count))));
    expect(trial.document.stashGroups).toBeUndefined();
    for (const mode of ["all", "edits_only", "sorting_only", "discard"] as const) {
      const output = settle(resumeSortingTrialV2(trial.serialize()), baseline, mode);
      expect(savedIds(output)).toEqual(mode === "all" || mode === "edits_only" ? [anchor.id].slice(0, count) : [anchor.id, note.id]);
      expect(groupIds(output)).toEqual(mode === "sorting_only" || mode === "discard" ? [anchor.id, note.id] : []);
    }
  });

  it("reconciles group member deletion as content and retains remaining group organization", () => {
    const { baseline: two, anchor, note, groupId } = grouped(false);
    const third = researchNote(991510);
    const open = beginStashGroupMemberStageV2(two, groupId)!;
    const baseline = applied(two, saveStashGroupStageCommandV2(stageStashGroupMembersV2(open, [...open.members, third])));
    const trial = createSortingTrialV2(baseline);
    const stage = beginStashGroupMemberStageV2(trial.document, groupId)!;
    trialApply(trial, saveStashGroupStageCommandV2(stageStashGroupMembersV2(stage, [stage.members[0]!, stage.members[2]!])));
    for (const outcome of ["all", "edits_only", "sorting_only", "discard"] as const) {
      const output = settle(resumeSortingTrialV2(trial.serialize()), baseline, outcome);
      expect(groupIds(output)).toEqual(outcome === "all" || outcome === "edits_only" ? [anchor.id, third.id] : [anchor.id, note.id, third.id]);
      expect(savedIds(output).includes(note.id)).toBe(outcome === "sorting_only" || outcome === "discard");
    }
  });

  it("refuses a split when a deleted group member cannot return to its precise moved sibling slot", () => {
    const { baseline: two, anchor, note, groupId } = grouped(false);
    const third = researchNote(991550);
    const open = beginStashGroupMemberStageV2(two, groupId)!;
    let baseline = applied(two, saveStashGroupStageCommandV2(stageStashGroupMembersV2(open, [...open.members, third])));
    baseline = applied(baseline, { kind: "create_stash_section", sectionId: id(991560), title: "Other location" });
    const trial = createSortingTrialV2(baseline);
    const stage = beginStashGroupMemberStageV2(trial.document, groupId)!;
    trialApply(trial, saveStashGroupStageCommandV2(stageStashGroupMembersV2(stage, [stage.members[0]!, stage.members[2]!])));
    trialApply(trial, { kind: "move_stash_group", groupId, sectionId: id(991560), parentRowId: null, afterRowId: null });
    const pending = trial.document;
    const snapshot = trial.serialize();
    const refused = trial.accept(baseline, "sorting_only");
    expect(refused).toMatchObject({ ok: false, changed: false, document: baseline });
    expect(refused.diagnostics[0]?.code).toMatch(/^SORTING_PROJECTION_/);
    expect(trial.serialize()).toBe(snapshot);
    expect(trial.document).toEqual(pending);
    expect(trial.phase).toBe("sorting");
    const all = trial.accept(baseline, "all");
    expect(all.ok, JSON.stringify(all.diagnostics)).toBe(true);
    if (all.ok) expect(groupIds(all.document)).toEqual([anchor.id, third.id]);
    expect(rowById(pending, note.id)).toBeUndefined();
  });

  it.each(["all", "edits_only", "sorting_only", "discard"] as const)("composes %s for staged Save: authored member revision, membership order and birth", (mode) => {
    const { baseline, anchor, note, groupId } = grouped(false);
    const trial = createSortingTrialV2(baseline);
    const stage = beginStashGroupMemberStageV2(trial.document, groupId)!;
    const edited = structuredClone(stage.members[0]!);
    edited.orderKey = "authored revision";
    const extra = researchNote(991600);
    trialApply(trial, saveStashGroupStageCommandV2(stageStashGroupMembersV2(stage, [extra, stage.members[1]!, edited])));
    expect(trial.document.stashGroups?.[0]?.rowIds).toEqual([extra.id, note.id, anchor.id]);
    const output = settle(trial, baseline, mode);
    expect(rowById(output, anchor.id)?.orderKey).toBe(mode === "all" || mode === "edits_only" ? "authored revision" : anchor.orderKey);
    expect(savedIds(output).includes(extra.id)).toBe(mode === "all" || mode === "edits_only");
    expect(groupIds(output)).toEqual(mode === "all" ? [extra.id, note.id, anchor.id] :
      mode === "edits_only" ? [anchor.id, note.id, extra.id] :
        mode === "sorting_only" ? [note.id, anchor.id] : [anchor.id, note.id]);
    expect(output.rowEditRevision).toBe(mode === "discard" ? baseline.rowEditRevision : (baseline.rowEditRevision ?? 0) + (mode === "sorting_only" || mode === "edits_only" || mode === "all" ? 1 : 0));
  });

  it("treats incorporation of an existing saved row as organization, without duplicating its payload", () => {
    const { baseline, anchor, note, groupId } = grouped(false);
    const independent = researchNote(991650);
    baseline.stash!.push({ id: id(991660), rows: [independent], supportingItems: [] });
    baseline.stashOutline!.push({ rowId: independent.id, kind: "row", sectionId: null, parentRowId: null });
    const trial = createSortingTrialV2(baseline);
    const stage = beginStashGroupMemberStageV2(trial.document, groupId)!;
    trialApply(trial, saveStashGroupStageCommandV2(stageStashGroupMembersV2(stage, [independent, stage.members[1]!, stage.members[0]!])));
    expect(trial.movedRowIds).toContain(independent.id);
    const all = settle(resumeSortingTrialV2(trial.serialize()), baseline, "all");
    const edits = settle(resumeSortingTrialV2(trial.serialize()), baseline, "edits_only");
    const sorting = settle(resumeSortingTrialV2(trial.serialize()), baseline, "sorting_only");
    expect(groupIds(all)).toEqual([independent.id, note.id, anchor.id]);
    expect(groupIds(edits)).toEqual([anchor.id, note.id]);
    expect(savedIds(edits)).toEqual([anchor.id, note.id, independent.id]);
    expect(groupIds(sorting)).toEqual([independent.id, note.id, anchor.id]);
    expect([all, edits, sorting].map((document) => (document.stash ?? []).flatMap((bundle) => bundle.rows).filter((row) => row.id === independent.id))).toEqual([[independent], [independent], [independent]]);
  });

  it("keeps a removed member and saved comment references in sorting-only, but honors edited deletion in edits-only", () => {
    const { baseline, anchor, note, groupId } = grouped(false);
    baseline.rowReferences = [{ id: id(991701), rowId: anchor.id, kind: "comment", anchor: { tokenId: anchor.tokens[0]!.id } }];
    const trial = createSortingTrialV2(baseline);
    const stage = beginStashGroupMemberStageV2(trial.document, groupId)!;
    const edited = structuredClone(stage.members[1]!);
    edited.orderKey = "new label";
    // This member is referenced, so remove the other member instead.
    trialApply(trial, saveStashGroupStageCommandV2(stageStashGroupMembersV2(stage, [stage.members[0]!, researchNote(991702), edited])));
    for (const mode of ["all", "edits_only", "sorting_only", "discard"] as const) {
      const output = settle(resumeSortingTrialV2(trial.serialize()), baseline, mode);
      expect(output.rowReferences).toEqual(baseline.rowReferences);
      expect(rowById(output, anchor.id)?.id).toBe(anchor.id);
      expect(rowById(output, note.id)?.orderKey).toBe(mode === "all" || mode === "edits_only" ? "new label" : note.orderKey);
    }
  });

  it("preserves a pending trial on stale canonical, invalid selective projection and tampered group action", () => {
    const { baseline, groupId } = grouped(false);
    const trial = createSortingTrialV2(baseline);
    trialApply(trial, { kind: "ungroup_stash_group", groupId });
    const snapshot = trial.serialize();
    const stale = structuredClone(baseline);
    stale.title = "External revision";
    expect(trial.accept(stale, "sorting_only")).toMatchObject({ ok: false, changed: false, document: stale, diagnostics: [{ code: "SORTING_BASELINE_CHANGED" }] });
    expect(trial.serialize()).toBe(snapshot);
    expect(trial.phase).toBe("sorting");
    const tampered = JSON.parse(snapshot) as { actions: Record<string, unknown>[] };
    tampered.actions[0]!.groupId = id(999999);
    expect(() => resumeSortingTrialV2(JSON.stringify(tampered))).toThrow(/Invalid saved Sorting operation/);
    const invalidShape = JSON.parse(snapshot) as { actions: Record<string, unknown>[] };
    invalidShape.actions[0]!.extra = "unexpected";
    expect(() => resumeSortingTrialV2(JSON.stringify(invalidShape))).toThrow(/Invalid saved Sorting operation/);
    expect(trial.accept(baseline, "sorting_only").ok).toBe(true);
  });

  it("rejects reused group identity in selective outcomes, without losing a valid all-changes trial", () => {
    const { baseline, anchor, note, groupId } = grouped(false);
    const trial = createSortingTrialV2(baseline);
    trialApply(trial, { kind: "ungroup_stash_group", groupId });
    trialApply(trial, { kind: "group_stash_rows", groupId, rowIds: [anchor.id, note.id] });
    const pending = trial.document;
    const projected = trial.accept(baseline, "sorting_only");
    expect(projected).toMatchObject({ ok: false, changed: false, document: baseline,
      diagnostics: [{ code: "SORTING_PROJECTION_IDENTITY_AMBIGUOUS" }] });
    expect(trial.document).toEqual(pending);
    expect(trial.accept(baseline, "all").ok).toBe(true);
  });

  it("reconciles group comments only on acceptance and leaves pending/discard comments unchanged", () => {
    const { baseline, groupId } = grouped(false);
    const activeNote = researchNote(991800);
    baseline.activeDraft.blocks.push(activeNote);
    let state = createCommentStateV2(baseline);
    const posted = applyCommentOperationV2(state, state.revision, { id: "group-post", actorId: "test-editor",
      kind: "create", threadId: "group-thread", messageId: "group-message", body: "Keep this saved-row comment",
      mentionActorIds: [], anchor: { kind: "block", blockId: activeNote.id } });
    expect(posted.ok).toBe(true);
    if (!posted.ok) return;
    state = posted.state;
    const trial = createSortingTrialV2(baseline);
    trialApply(trial, { kind: "ungroup_stash_group", groupId });
    expect(state.document).toEqual(baseline);
    const context = { state, id: "sorting-group-finish", actorId: "test-editor" };
    const accepted = trial.accept(baseline, "sorting_only", context);
    expect(accepted.ok, JSON.stringify(accepted.diagnostics)).toBe(true);
    expect(accepted.comments?.threads[0]?.messages[0]?.body).toBe("Keep this saved-row comment");
    expect(accepted.comments?.threads[0]?.attachment.status).toBe("attached");
    expect(accepted.comments?.document).toEqual(accepted.document);
    const discarded = createSortingTrialV2(baseline).discard(baseline, context);
    expect(discarded.comments).toBe(state);
  });
});
