import { createHash } from "node:crypto";

import { exportPrompter, type PrompterExportSettings } from "@vera/contracts/prompter-export";
import type { ScriptDocumentV2 } from "@vera/contracts/v2";
import { checkedDocument, type DocumentView } from "@vera/project-documents";
import { describe, expect, it } from "vitest";

import { prepareSavedPrompter, type PrompterExpectedSnapshot } from "../src/prompter-authoring.js";

const settings: PrompterExportSettings = {
  includeSectionNavigation: false, includeBeatNumbers: false,
};
const projectId = "00000000-0000-4000-8000-000000006004";
const rowId = "00000000-0000-4000-8000-000000006001";

function documentFixture(): ScriptDocumentV2 {
  return {
    schemaVersion: "script-document/v2",
    id: "00000000-0000-4000-8000-000000006003",
    projectId,
    title: "Saved prompter fixture",
    liveHeadSequence: 2, liveStateVector: "",
    liveContentHash: `sha256:${"a".repeat(64)}`,
    activeDraft: { blocks: [{
      type: "narration", id: rowId, orderKey: "active", text: "Spoken words.",
      tokens: [
        { id: "00000000-0000-4000-8000-000000006005", value: "Spoken", startOffset: 0, endOffset: 6 },
        { id: "00000000-0000-4000-8000-000000006006", value: "words.", startOffset: 7, endOffset: 13 },
      ],
      primaryVisualSequence: {
        id: "00000000-0000-4000-8000-000000006007", version: 1,
        slots: [{
          id: "00000000-0000-4000-8000-000000006008", version: 1,
          kind: "content", relation: { kind: "base" },
          boundaryBefore: { kind: "row_start" },
          payload: { kind: "on_camera", presenterChoiceId: null },
          playoutPolicy: "match_structural_interval",
        }],
      },
      overlayEvents: [], timingPolicy: "narration_spine", state: "active",
      notes: [], version: 1,
    }], supportingItems: [] },
    ideaOutline: [], extras: [],
  };
}

function savedView(document: ScriptDocumentV2 = documentFixture()): DocumentView {
  const checked = checkedDocument(document, projectId);
  return { projectId, revision: 7, digest: checked.digest, document: checked.document };
}

function snapshot(view: DocumentView): PrompterExpectedSnapshot {
  return { projectId: view.projectId, revision: view.revision, digest: view.digest };
}

function hash(value: string): string {
  return `sha256:${createHash("sha256").update(value, "utf8").digest("hex")}`;
}

describe("prepareSavedPrompter", () => {
  it("returns one frozen #37 pair for the verified saved head, identical across runs without mutation", () => {
    const view = savedView();
    const before = structuredClone(view);
    const first = prepareSavedPrompter(view, snapshot(view), settings);
    const second = prepareSavedPrompter(view, snapshot(view), settings);
    expect(first.status).toBe(200);
    expect(second).toEqual(first);
    const exported = exportPrompter(view.document, settings);
    expect(exported.ok).toBe(true);
    if (first.status !== 200 || !exported.ok) return;

    expect(first.body).toMatchObject({
      projectId, revision: 7, digest: view.digest,
      text: exported.text, sidecarJson: exported.sidecarJson,
      textSha256: hash(exported.text), sidecarSha256: hash(exported.sidecarJson),
    });
    expect(first.body.sourceDocument).toEqual(exported.sidecar.sourceDocument);
    // The saved-service revision is not the exporter live-head sequence.
    expect(first.body.sourceDocument.liveHeadSequence).toBe(2);
    expect(first.body.sourceDocument.contentHash).toBe(view.document.liveContentHash);
    expect(first.body.revision).toBe(7);
    expect(view).toEqual(before);
  });

  it("excludes saved v2 Stash, active notes and nonspoken directions from both files", () => {
    const baseline = savedView();
    const changed = structuredClone(baseline.document);
    const parkedId = "00000000-0000-4000-8000-000000006002";
    changed.stash = [{
      id: "00000000-0000-4000-8000-000000006009",
      rows: [{ id: parkedId, type: "note_draft", orderKey: "saved",
        text: "STASH SECRET", state: "excluded", version: 1 }], supportingItems: [],
    }];
    changed.stashOutline = [{ rowId: parkedId, kind: "row",
      parentRowId: null, sectionId: null }];
    changed.activeDraft.blocks.push(
      { type: "direction", id: "00000000-0000-4000-8000-000000006010",
        orderKey: "direction", text: "DIRECTION SECRET", buildBehavior: "none", version: 1 },
      { type: "note_draft", id: "00000000-0000-4000-8000-000000006011",
        orderKey: "note", text: "NOTE SECRET", state: "excluded", version: 1 },
    );
    const saved = savedView(changed);
    expect(saved.digest).not.toBe(baseline.digest);
    const first = prepareSavedPrompter(baseline, snapshot(baseline), settings);
    const second = prepareSavedPrompter(saved, snapshot(saved), settings);
    expect(first.status).toBe(200);
    expect(second.status).toBe(200);
    if (first.status !== 200 || second.status !== 200) return;
    expect(second.body.text).toBe(first.body.text);
    expect(second.body.sidecarJson).toBe(first.body.sidecarJson);
    expect(second.body.text).toContain("Spoken words.");
    expect(second.body.sidecarJson).not.toMatch(/STASH SECRET|DIRECTION SECRET|NOTE SECRET/u);
  });

  it("refuses old expected revision and digest rather than exporting a newer head", () => {
    const view = savedView();
    const pinned = snapshot(view);
    expect(prepareSavedPrompter(view, { ...pinned, revision: 6 }, settings))
      .toEqual({ status: 409, body: { error: "saved_script_changed" } });
    expect(prepareSavedPrompter(view, { ...pinned, digest: `sha256:${"0".repeat(64)}` }, settings))
      .toEqual({ status: 409, body: { error: "saved_script_changed" } });
  });

  it("refuses missing, malformed, wrong-project, or unsafely revised saved views", () => {
    const view = savedView();
    const pinned = snapshot(view);
    const unavailable = { status: 503, body: { error: "saved_script_unavailable" } };
    expect(prepareSavedPrompter(null, pinned, settings)).toEqual(unavailable);
    expect(prepareSavedPrompter({ ...view, projectId: "00000000-0000-4000-8000-000000009999" }, pinned, settings))
      .toEqual(unavailable);
    expect(prepareSavedPrompter({ ...view, revision: Number.MAX_SAFE_INTEGER + 1 }, pinned, settings))
      .toEqual(unavailable);
    expect(prepareSavedPrompter({ ...view, digest: "bad-digest" }, pinned, settings))
      .toEqual(unavailable);

    const wrongDocument = { ...view.document, projectId: "00000000-0000-4000-8000-000000009999" };
    expect(prepareSavedPrompter({ ...view, document: wrongDocument }, pinned, settings))
      .toEqual({ status: 503, body: { error: "saved_script_invalid" } });
    expect(prepareSavedPrompter({ ...view, document: {} }, pinned, settings))
      .toEqual({ status: 503, body: { error: "saved_script_invalid" } });
  });

  it("refuses corrupted saved content even if expected digest matches the service's claim", () => {
    const view = savedView();
    const corruptDigest = `sha256:${"0".repeat(64)}`;
    const corrupt = { ...view, digest: corruptDigest };
    expect(prepareSavedPrompter(corrupt, snapshot(corrupt), settings))
      .toEqual({ status: 503, body: { error: "saved_script_digest_mismatch" } });
    const modified = structuredClone(view);
    modified.document.title = "Saved bytes tampered";
    expect(prepareSavedPrompter(modified, snapshot(view), settings))
      .toEqual({ status: 503, body: { error: "saved_script_digest_mismatch" } });
  });

  it("returns the frozen exporter's structured diagnostics without any file bytes", () => {
    const view = savedView();
    const invalidSettings = { ...settings, includeBeatNumbers: "true" } as unknown as PrompterExportSettings;
    const result = prepareSavedPrompter(view, snapshot(view), invalidSettings);
    expect(result).toEqual({ status: 422, body: {
      error: "prompter_validation_failed",
      diagnostics: [{
        code: "PROMPTER_SETTINGS_INVALID",
        message: "Prompter settings require boolean includeSectionNavigation and includeBeatNumbers values.",
        jsonPath: "/settings",
      }],
    } });
    expect(result.body).not.toHaveProperty("text");
    expect(result.body).not.toHaveProperty("sidecarJson");
  });

  it("returns real frozen-exporter coverage diagnostics for a saveable but unexportable v2 document", () => {
    const document = documentFixture();
    const row = document.activeDraft.blocks[0];
    if (row?.type !== "narration" || !row.primaryVisualSequence) {
      throw new Error("Expected narration with a primary sequence");
    }
    row.primaryVisualSequence.slots = [];
    const view = savedView(document);
    const result = prepareSavedPrompter(view, snapshot(view), settings);
    expect(result.status).toBe(422);
    if (result.status !== 422) return;
    expect(result.body.diagnostics.map(({ code }) => code)).toContain("PRIMARY_SEQUENCE_EMPTY");
    expect(result.body).not.toHaveProperty("text");
  });
});
