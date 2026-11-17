import { randomUUID } from "node:crypto";

import type { ScriptDocumentV2 } from "@vera/contracts/v2";
import { describe, expect, it } from "vitest";

import {
  checkedDocument,
  checkedSettings,
  fingerprint,
  requireRevision,
  requireUuid,
  sha256,
} from "../src/model.js";

function draft(projectId: string): ScriptDocumentV2 {
  return {
    schemaVersion: "script-document/v2",
    id: randomUUID(), projectId, title: "Draft",
    activeDraft: { blocks: [], supportingItems: [] },
    ideaOutline: [], extras: [], liveHeadSequence: 3,
    liveStateVector: "", liveContentHash: "sha256:" + "a".repeat(64),
  };
}

describe("project storage typed boundary", () => {
  it("keeps internal and trailing LF bytes, frozen UTF-16 tokens and distinct save digests", () => {
    const projectId = randomUUID();
    const input = draft(projectId);
    const authoredText = "😀 hello\nworld\n";
    input.activeDraft.blocks = [{
      type: "narration", id: randomUUID(), orderKey: "a0", text: authoredText,
      tokens: [
        { id: randomUUID(), value: "😀", startOffset: 0, endOffset: 2 },
        { id: randomUUID(), value: "hello", startOffset: 3, endOffset: 8 },
        { id: randomUUID(), value: "world", startOffset: 9, endOffset: 14 },
      ],
      state: "active", timingPolicy: "narration_spine", notes: [], version: 1,
      overlayEvents: [], primaryVisualSequence: {
        id: randomUUID(), version: 1, slots: [{
          id: randomUUID(), version: 1, kind: "content", relation: { kind: "base" },
          boundaryBefore: { kind: "row_start" },
          payload: { kind: "on_camera", presenterChoiceId: null },
          playoutPolicy: "match_structural_interval",
        }],
      },
    }];

    const saved = checkedDocument(input, projectId);
    expect(saved.documentJson).toBe(JSON.stringify(input));
    expect(saved.documentJson).toContain(JSON.stringify(authoredText));
    expect(saved.document.activeDraft.blocks[0]).toEqual(input.activeDraft.blocks[0]);
    expect(saved.digest).toBe(sha256(saved.documentJson));
    expect(checkedDocument(JSON.parse(saved.documentJson), projectId)).toEqual(saved);

    const spaced = structuredClone(input);
    const row = spaced.activeDraft.blocks[0];
    if (row?.type !== "narration") throw new Error("Expected a narration row.");
    row.text = authoredText.replaceAll("\n", " ");
    const withoutBreaks = checkedDocument(spaced, projectId);
    expect(withoutBreaks.digest).not.toBe(saved.digest);
    expect(withoutBreaks.document.activeDraft.blocks[0]).toMatchObject({ tokens: saved.document.activeDraft.blocks[0]!.type === "narration" ? saved.document.activeDraft.blocks[0]!.tokens : [] });
  });

  it("roundtrips exact accepted authoring fields without advancing collaboration state", () => {
    const projectId = randomUUID();
    const input = draft(projectId);
    const saved = checkedDocument(input, projectId);
    expect(saved.document).toEqual(input);
    expect(saved.digest).toBe(sha256(saved.documentJson));
    expect(saved.document.liveHeadSequence).toBe(3);
    expect(saved.document.liveContentHash).toBe(input.liveContentHash);
    expect(checkedDocument(JSON.parse(saved.documentJson), projectId).digest).toBe(saved.digest);
  });

  it("refuses different identity, schema damage, invalid revision or request key", () => {
    const projectId = randomUUID();
    const input = draft(projectId);
    expect(() => checkedDocument(input, randomUUID())).toThrow();
    expect(() => checkedDocument(input, projectId, randomUUID())).toThrow();
    expect(() => checkedDocument({ ...input, extras: [{}] }, projectId)).toThrow();
    expect(() => checkedDocument({ ...input, unknown: "secret" }, projectId)).toThrow();
    expect(() => requireRevision(Number.MAX_SAFE_INTEGER + 1)).toThrow();
    expect(() => requireUuid("not-an-actor")).toThrow();
  });

  it("validates typed settings while keeping the supplied settingsHash opaque", () => {
    const projectId = randomUUID();
    const settings = {
      schemaVersion: "authoring-project-settings/v1", id: randomUUID(), projectId,
      version: 1, settingsHash: "sha256:" + "b".repeat(64),
    };
    const saved = checkedSettings(settings, projectId);
    expect(saved.settings.settingsHash).toBe(settings.settingsHash);
    expect(saved.digest).toBe(sha256(saved.settingsJson));
    expect(saved.digest).not.toBe(settings.settingsHash);
    expect(() => checkedSettings(settings, randomUUID())).toThrow();
    expect(() => checkedSettings({ ...settings, extra: 1 }, projectId)).toThrow();
    expect(() => checkedSettings({ ...settings, settingsHash: "invalid" }, projectId)).toThrow();
  });

  it("keeps idempotency fingerprint insensitive to field insertion order", () => {
    expect(fingerprint({ a: 2, z: { b: 1, a: 2 } }))
      .toBe(fingerprint({ z: { a: 2, b: 1 }, a: 2 }));
    expect(fingerprint({ a: 1 })).not.toBe(fingerprint({ a: 2 }));
  });
});
